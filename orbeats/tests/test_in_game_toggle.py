"""In-game global plugin toggle (M11, Exp 278/278c) — hermetic source-level tests.

The plugin change is C++ (compiled by make, not unit-testable from Python), so
these tests pin the researched facts and the behavioral contract in the source,
mirroring the TestSongPreviewsFlagGating pattern. The researched facts (hook
targets, NID resolution, Move button bits, struct layout, time source) were
verified against the game's real eboot imports + the game's own dump.cs enum —
see the plan: .agent/plans/in-game-global-plugin-enable-toggle-plan.md
"""
import os
import re
import sys

TOOLS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tools')
sys.path.insert(0, TOOLS)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_CPP = os.path.join(PROJECT_ROOT, "src", "main.cpp")
WEBAPP = os.path.join(PROJECT_ROOT, "webapp")


def _code():
    with open(MAIN_CPP, encoding="utf-8") as f:
        return f.read()


def _def_body(code, name, span=2000):
    """Find a function DEFINITION (not a forward declaration) and return its
    first `span` chars. Definitions have a '{' before the next ';'."""
    for variant in (f"static void* {name}(", f"static void {name}(",
                    f"static int {name}(", f"static void *{name}(",
                    f"static uint64_t {name}("):
        idx = 0
        while True:
            idx = code.find(variant, idx)
            if idx < 0:
                break
            brace = code.find("{", idx)
            semi = code.find(";", idx)
            if brace >= 0 and (semi < 0 or brace < semi):
                return code[idx:idx + span]
            idx += 1
    return ""


class TestInGameToggleFlagGating:
    """The enable_in_game_plugin_toggle flag gates the hook installs AND
    bodies (feature-flag enforcement, CLAUDE.md §2)."""

    def test_plugin_parses_toggle_flag(self):
        code = _code()
        assert 'strcmp(key, "enable_in_game_plugin_toggle")' in code
        assert "g_feature_in_game_plugin_toggle" in code

    def test_flag_not_decorative(self):
        """Real conditional use outside load_features (gating-audit rule)."""
        code = _code()
        lf_start = code.find("static void load_features(")
        lf_end = code.find('extern "C" FILE *fopen', lf_start)
        lf_body = code[lf_start:lf_end]
        rest = code.replace(lf_body, "")
        conds = re.findall(r"(?:if\s*\(|&&\s*|!\s*)g_feature_in_game_plugin_toggle", rest)
        assert len(conds) >= 1, \
            "g_feature_in_game_plugin_toggle has no behavioral gate outside load_features"

    def test_hotkey_not_gated_by_kill_switch(self):
        """ONE-WAY-DOOR PREVENTION (plan §2.4): the hotkey must keep working
        when enable_plugin=false, or a user toggled OFF could never re-enable
        without a PC. No toggle-path function may require g_feature_plugin_enabled."""
        code = _code()
        for fn in ("try_install_pad_hook", "try_install_move_hook",
                   "pad_read_hook", "move_read_hook", "combo_feed",
                   "in_game_toggle_plugin"):
            body = _def_body(code, fn)
            assert body, f"{fn} definition not found"
            assert "g_feature_plugin_enabled" not in body, \
                f"{fn} must NOT be gated by the kill switch (one-way-door rule)"

    def test_toggle_only_writes_file_not_runtime_state(self):
        """PERSIST-ONLY (plan §2.2): the flip must not change the session's
        runtime state — in_game_toggle_plugin never assigns g_feature_plugin_enabled."""
        body = _def_body(_code(), "in_game_toggle_plugin", span=6000)
        assert "g_feature_plugin_enabled =" not in body.replace("==", "")
        assert "features.json" in body or "FEATURES_PATH" in body


class TestInGameToggleResearchedFacts:
    """Pins the Exp-278/278c/278d/278e research: GOT-SLOT HIJACKING (the
    definitive mechanism after THREE hardware failures), hook targets, Move
    button bits, timing, and the release-logging policy.

    Hardware iteration history: v0.8049 — readable-name dlsym finds nothing
    (Sony libs export NIDs). v0.8050 — NID dlsym ALSO finds nothing (dlsym
    cannot see kernel-loaded SPRX exports AT ALL). v0.8051 — GOT resolution
    WORKED but Detouring the real library code built a trampoline over a
    non-relocatable prologue → the game HUNG at a black screen on the first
    scePadRead call (also revealed: JUMP_SLOTs bind LAZILY — the move slot
    held a sentinel until the game's first call). v0.8052 — hijack the GOT
    SLOT VALUE (atomic 8-byte write; no trampoline, no code patching; the
    hook calls the saved original pointer directly).
    """

    def test_hooks_installed_via_got_hijack(self):
        """THE v0.8052 mechanism: overwrite the GOT slot value with the hook
        address after mprotect RW — no dlsym, no Detour on library code."""
        code = _code()
        assert "#define GOT_RVA_SCE_MOVE_READ_RECENT 0x1c634e8" in code
        assert "#define GOT_RVA_SCE_PAD_READ         0x1c63500" in code
        assert "try_hijack_got_slot" in code
        assert 'strcmp(info.name, "eboot.bin")' in code
        assert "sceKernelMprotect" in code
        # dlsym must NOT be used for system-library functions at all
        assert 'dlsym(RTLD_DEFAULT, "scePadRead")' not in code
        assert 'dlsym(RTLD_DEFAULT, "sceMoveReadStateRecent")' not in code
        assert 'dlsym(RTLD_DEFAULT, NID_' not in code

    def test_no_trampoline_on_library_code(self):
        """THE v0.8051 black-screen hang pin: never Detour Sony library
        functions (non-relocatable prologues corrupt the trampoline). The
        hooks call the SAVED ORIGINALS directly — no HOOK_CONTINUE."""
        code = _code()
        assert "HOOK_CONTINUE(hook_pad_read" not in code
        assert "HOOK_CONTINUE(hook_move_read" not in code
        assert "HOOK_INIT(hook_pad_read)" not in code
        assert "HOOK_INIT(hook_move_read)" not in code
        body = _def_body(code, "pad_read_hook", span=1500)
        assert "g_orig_pad_read(handle" in body
        mbody = _def_body(code, "move_read_hook", span=3000)
        assert "g_orig_move_read(handle" in mbody

    def test_hijack_waits_for_lazy_binding(self):
        """JUMP_SLOTs bind on the game's FIRST call — until then the slot holds
        a lazy sentinel (0xeffffffe000001a0) or the in-eboot PLT resolver
        stub. The hijack must reject both and keep retrying."""
        body = _def_body(_code(), "try_hijack_got_slot", span=3000)
        assert body, "try_hijack_got_slot definition not found"
        assert "EBOOT_TEXT_SPAN" in body          # rejects in-eboot PLT stubs
        assert "fn_addr < 0x1000000ULL" in body   # rejects unbound/garbage
        # mprotect BEFORE the write, page protection restored after
        assert body.find("sceKernelMprotect(page_start") < body.find("*(uint64_t *)slot_addr = (uint64_t)hook")
        assert body.count("sceKernelMprotect") >= 2

    def test_hijack_never_crashes_the_game(self):
        """Any mprotect/query failure must ABORT the hijack (give up) — never
        write blindly to a page we could not flip RW."""
        body = _def_body(_code(), "try_hijack_got_slot", span=3000)
        assert "mprotect RW failed" in body
        assert "no write attempted" in body

    def test_verbose_diagnostics_gated_behind_debug_build(self):
        """RELEASE-PERFORMANCE DIRECTIVE (user, Exp 278e): per-call diagnostics
        (raw-word dumps, change logging, retry progress) are DEBUG-BUILD ONLY
        (#ifdef VERBOSE_LOG — the Makefile's DEBUG=1 flag). Release logs
        one-time events only (ARMED, hijack installed, form detected, ERROR
        give-ups, toggle flips, cooldown)."""
        code = _code()
        assert code.count("#ifdef VERBOSE_LOG") >= 4  # pad diag + move diag + 2 retry loops
        # the raw-word diagnostics live inside the gates
        pad_body = _def_body(code, "pad_read_hook", span=1800)
        assert "#ifdef VERBOSE_LOG" in pad_body
        move_body = _def_body(code, "move_read_hook", span=4000)
        assert "#ifdef VERBOSE_LOG" in move_body

    def test_form_detection_cached(self):
        """The move call form (3-arg vs 4-arg) is detected ONCE and cached —
        the steady-state hot path runs no pointer-validation syscalls."""
        body = _def_body(_code(), "move_read_hook", span=4000)
        assert "g_move_form == 0" in body   # detect only while unknown
        assert "g_move_form = 4" in body
        assert "g_move_form = 3" in body

    def test_primary_hook_target_is_sceMoveReadStateRecent(self):
        """Beat Saber reads both Moves every frame via sceMoveReadStateRecent
        (NID f2bcpK6kJfg) — the ONLY Move state read in the eboot's imports;
        sceMoveReadStateLatest is NOT imported. scePadRead (NID q1cHNfGycLI)
        stays as the secondary DS4 path."""
        code = _code()
        assert "move_read_hook" in code
        # the Latest variant must never be a hook target (not imported by the game;
        # comments documenting that fact are fine)
        assert 'dlsym(RTLD_DEFAULT, "sceMoveReadStateLatest")' not in code
        assert 'GOT_RVA_SCE_MOVE_READ_RECENT' in code  # the Recent variant is the hook target

    def test_move_button_bits_from_game_enum(self):
        """Move bits reconstructed from the game's OWN PSMoveButton enum
        (dump.cs: Select=1, [2=trigger], Move=4, Start=8, Triangle=16,
        Circle=32, Cross=64, Square=128 — the enum skips 2 because the game
        reads the trigger via GetPSMoveAnalog; the trigger's digital bit is 0x2)."""
        code = _code()
        assert "#define MOVE_BUTTON_TRIGGER 0x0002u" in code
        assert "#define MOVE_BUTTON_MOVE 0x0004u" in code
        assert "(MOVE_BUTTON_TRIGGER | MOVE_BUTTON_MOVE)" in code

    def test_ds4_combo_bits_kept_for_pad_path(self):
        """L3=0x2, R3=0x4 (dual-verified) stay for the secondary DS4 path."""
        code = _code()
        assert "#define PAD_BUTTON_L3 0x0002u" in code
        assert "#define PAD_BUTTON_R3 0x0004u" in code

    def test_move_data_offsets_and_trigger_fallback(self):
        """SceMoveData layout per shadPS4Plus's SDK-derived OrbisMoveData:
        button_data u16 @ +0x18, trigger analog u16 @ +0x1A. Trigger counts as
        held via its digital bit OR the analog value (robust to either
        reporting form). Raw-word change diagnostics must exist to confirm
        the offsets empirically on the first hardware boot."""
        code = _code()
        assert "#define MOVE_DATA_BUTTON_OFF 0x18" in code
        assert "#define MOVE_DATA_TRIGGER_OFF 0x1A" in code
        assert "#define MOVE_TRIGGER_ANALOG_THRESH 0x0080u" in code
        # change-logging diagnostics (empirical offset confirmation)
        assert "MOVE_DIAG_CHANGE_MAX" in code
        assert "g_move_prev_words" in code

    def test_signature_ambiguity_handled_safely(self):
        """shadPS4 documents sceMoveReadStateRecent as 4-arg
        (handle, timestamp, data, out_count); a 3-arg form would put the data
        buffer in RSI instead of RDX. The hook detects the form at runtime via
        sceKernelQueryMemoryProtection (the v0.8045-proven signal-free
        technique), CACHES it, and calls the saved original with ALL FOUR
        registers (a 3-arg original ignores the extra) — no HOOK_CONTINUE
        exists anymore."""
        code = _code()
        assert "is_mapped_rw_pointer" in code
        assert "sceKernelQueryMemoryProtection" in code
        body = _def_body(code, "move_read_hook", span=4000)
        assert body, "move_read_hook definition not found"
        assert "g_move_form = 4" in body and "g_move_form = 3" in body
        assert "HOOK_CONTINUE(hook_move_read" not in code

    def test_two_second_hold_with_kernel_time(self):
        """2 s hold timed by sceKernelGetProcessTime (µs) = 2,000,000, fed
        through the shared combo detector (both Move handles interleave — the
        250 ms gap window keeps one handle's non-combo polls from resetting a
        hold the other handle sustains)."""
        code = _code()
        assert "#define COMBO_HOLD_US 2000000ULL" in code
        assert "#define COMBO_GAP_US 250000ULL" in code
        cf = _def_body(code, "combo_feed")
        assert cf, "combo_feed definition not found"
        assert "sceKernelGetProcessTime()" in cf
        assert "COMBO_HOLD_US" in cf

    def test_release_latch_and_cooldown(self):
        """After a toggle fires: combo must be RELEASED (latch) and a global
        cooldown prevents double-fires from both hook paths seeing one hold."""
        cf = _def_body(_code(), "combo_feed")
        assert "g_combo_latched = 0" in cf
        assert "!g_combo_latched" in cf
        assert "TOGGLE_COOLDOWN_US" in cf

    def test_clean_combo_exact_match(self):
        """Anti-accidental-trigger: the pad path requires buttons == the combo
        EXACTLY; the Move path requires no OTHER button bit set beyond the
        combo mask."""
        code = _code()
        assert "buttons == PAD_COMBO" in code
        assert "(bd & ~MOVE_COMBO) == 0" in code

    def test_giveup_flags_stop_retry_spam(self):
        """v0.8049 re-logged its ERROR on every open_hook call after giving
        up. The retry loops must set a gave-up flag and stop."""
        code = _code()
        assert "g_pad_hijack_gave_up" in code
        assert "g_move_hijack_gave_up" in code
        # the move slot binds LAZILY (at VR init) — its retry budget is far
        # larger than the pad's (bound at open #1)
        assert "#define MOVE_HIJACK_MAX_ATTEMPTS 2000" in code
        assert "#define PAD_HIJACK_MAX_ATTEMPTS 100" in code

    def test_surgical_in_place_flip(self):
        """The flip edits the enable_plugin value in place (memmove for the
        1-byte true/false size delta), preserving every other key (plan §2.3)."""
        body = _def_body(_code(), "in_game_toggle_plugin", span=6000)
        assert 'strstr(buf, "\\"enable_plugin\\"")' in body
        assert "memmove(" in body
        assert "O_TRUNC" in body  # write-back replaces the file atomically

    def test_notification_shows_state_and_restart_hint(self):
        code = _code()
        assert "Plugin %s\\nRestart game to apply" in code
        assert "ENABLED" in code
        assert "DISABLED" in code


class TestInGameToggleVersions:
    def test_plugin_version_bumped(self):
        assert '#define PLUGIN_VERSION "v0.8079"' in _code()

    def test_debug_variant_identity_is_log_only(self):
        """Keep diagnostic identity in logs, never in the player boot toast."""
        code = _code()
        assert '#ifdef VERBOSE_LOG\n#define PLUGIN_VARIANT " DEBUG"' in code.replace('\r\n', '\n')
        assert '#define PLUGIN_VARIANT ""' in code
        assert 'log_write("=== OrBeats " PLUGIN_VERSION PLUGIN_VARIANT " started ===")' in code
        assert '"OrBeats %s\\nBy Wkrotik"' in code
        assert 'PLUGIN_VERSION, PLUGIN_VARIANT);' not in code
        assert 'BS Deluxe' not in code
        assert 'OrBeats %s — disabled' in code

    def test_toast_has_no_feature_counter(self):
        code = _code()
        assert " features ON)" not in code
        assert "enabled_count" not in code
        assert 'Wkrotik' in code and 'Chris Primeish' not in code
        assert "(official songs only)" in code


class TestInGameTogglePipeline:
    def test_default_features_has_toggle_flag(self):
        """Exp 281: ALL flags default ON (fresh installs work out of the box)."""
        import full_custom_song_pipeline as fp
        assert fp.DEFAULT_FEATURES.get("enable_in_game_plugin_toggle") is True


class TestInGameToggleWebappSurfaces:
    """The webapp must list + describe the 5th flag everywhere it surfaces flags."""

    def test_adapter_known_flags(self):
        with open(os.path.join(WEBAPP, "adapters", "ps4.py"), encoding="utf-8") as f:
            code = f.read()
        assert '"enable_in_game_plugin_toggle"' in code

    def test_server_flag_descriptions(self):
        with open(os.path.join(WEBAPP, "server.py"), encoding="utf-8") as f:
            code = f.read()
        assert '"enable_in_game_plugin_toggle"' in code

    def test_static_toast_and_flag_list(self):
        with open(os.path.join(WEBAPP, "static", "app.js"), encoding="utf-8") as f:
            code = f.read()
        assert '"enable_in_game_plugin_toggle"' in code
        assert 'TOAST_VERSION = "v0.8079"' in code

    def test_index_placeholder_uses_current_count_free_toast(self):
        with open(os.path.join(WEBAPP, "static", "index.html"), encoding="utf-8") as f:
            code = f.read()
        assert " features ON)" not in code
        assert 'id="toast-count"' not in code
        assert 'OrBeats v0.8079' in code
        assert 'id="toast-status" hidden' in code
