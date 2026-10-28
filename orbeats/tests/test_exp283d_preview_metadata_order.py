"""
test_exp283d_preview_metadata_order.py — the deploy-order regression pin.

The bug (the user's field report, 2026-10-23): a freshly deployed song kept
its STOCK menu preview while earlier deploys' previews worked. Root cause:
the pack/preview pass (deploy_pack_bundle → _ensure_previews_variants →
song_previews.build_preview_map) gates slots on the LOCAL song_metadata.json
— which Step 11 only wrote at the END of the deploy. So build_preview_map saw
the just-deployed slot as "not custom" and baked no preview for it: every
deploy baked the PREVIOUS deploy's preview, never its own.

The fix: register the target's metadata LOCALLY (deploy=False — no upload)
BEFORE the pack pass; Step 11 still performs the upload. This test pins the
source ordering so a refactor can never silently reintroduce the gap.
"""

from pathlib import Path

PIPELINE = Path(__file__).resolve().parents[1] / "tools" / "full_custom_song_pipeline.py"


def _src() -> str:
    return PIPELINE.read_text(encoding="utf-8")


class TestPreviewMetadataOrder:
    def test_early_registration_precedes_the_pack_pass(self):
        src = _src()
        # the early registration call (Exp 283d) with deploy=False …
        early = src.find("Exp 283d: register the target's song metadata LOCALLY BEFORE")
        assert early > 0, "the Exp 283d early-registration block is missing"
        # … must precede the deploy_pack_bundle call that runs the preview pass
        pack_pass = src.find("deploy_pack_bundle(deploy_cfg, packs=deploy_packs")
        assert pack_pass > 0, "the single-song pack pass call not found"
        assert early < pack_pass, \
            ("the metadata registration must run BEFORE the pack/preview pass "
             "(otherwise build_preview_map treats the new slot as not-custom and "
             "the deploy's own song gets no menu preview — the Exp 283d bug)")

    def test_early_registration_writes_locally_only(self):
        """The early call must be deploy=False — the upload stays with Step 11
        (an early upload would ship metadata before its bundle exists)."""
        src = _src()
        block_start = src.find("Exp 283d: register the target's song metadata LOCALLY BEFORE")
        block_end = src.find("if should_deploy:\n        deploy_pack_bundle", block_start)
        assert block_start > 0 and block_end > block_start
        block = src[block_start:block_end]
        assert "deploy=False" in block, \
            "the early registration must not upload (deploy=False); Step 11 owns the upload"

    def test_step_eleven_still_uploads(self):
        """The END-OF-DEPLOY metadata step (the upload) must remain after the
        pack pass — idempotent local write + the actual PS4 upload."""
        src = _src()
        pack_pass = src.find("deploy_pack_bundle(deploy_cfg, packs=deploy_packs")
        step11 = src.find("Step 11: Song metadata")
        assert pack_pass > 0 and step11 > pack_pass

    def test_build_preview_map_gates_on_song_metadata(self):
        """The gating itself is BY DESIGN (metadata = the truth of which
        slots are custom); the bug was only the write ordering. Pin the gate
        so nobody 'fixes' it by removing the metadata check (which would
        build previews for every stock slot's stale local bundle)."""
        import sys
        tools = Path(__file__).resolve().parents[1] / "tools"
        sys.path.insert(0, str(tools))
        import song_previews
        src = (tools / "song_previews.py").read_text(encoding="utf-8")
        fn_start = src.find("def build_preview_map")
        fn_end = src.find("def _display_title", fn_start)
        body = src[fn_start:fn_end]
        assert "if stock not in meta" in body, \
            "build_preview_map must keep gating on song_metadata.json"
        assert song_previews.PREVIEW_SECONDS > 0
