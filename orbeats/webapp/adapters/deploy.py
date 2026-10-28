"""
deploy.py — the pipeline CLI surface → typed argv builder.

Thin-layer rule (plan §9.4 invariant 1): the web app NEVER re-implements
deploy logic; it assembles the exact argv the CLI accepts and hands it to the
single-job runner (adapters/runner.py) as a subprocess. The safe-default
command matches the example scripts byte-for-byte:

  python3 tools/full_custom_song_pipeline.py \
      --download-beat-saver-song <MAP_ID> --target <SLOT> \
      --pcm16 --no-pad --convert-to-v3 --deploy-full

(`--deploy-full` = build song bundle with all modes + pack bundles + catalog,
deploy, regenerate redirects, post-deploy validation, plugin build/deploy.)
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from . import paths

# Flags whose value is free text (everything else is a boolean switch).
_VALUE_FLAGS = {
    "--target", "--song-dir", "--audio", "--song-name", "--artist",
    "--enable-modes", "--one-saber-min-gap", "--rotation-cycle-beats",
    "--fallback-mode-map", "--download-beat-saver-song", "--config",
    "--clear-target-song", "--set-feature", "--beatsaver-api-base",
}


@dataclasses.dataclass
class DeployOptions:
    """Typed options for one song deploy. Defaults = the example scripts'."""

    additive: bool = False      # Explicit in companion routes; legacy builder retained.
    map_id: str = ""            # BeatSaver map key (e.g. '1d6c7c2')
    target: str = ""            # slot name from beat_saber_song_ids.json
    # M13: local song-folder deploys (--song-dir) — the Beat Sage + local-
    # folder sections stage a validated folder and hand it to the pipeline
    # unchanged. Mirrors the pipeline's own precedence: a song_dir overrides
    # the download flow ("Using local song directory: … (ignoring
    # --download-beat-saver-song)").
    song_dir: str = ""
    # Audio codec: --pcm16 is the default/recommended; --vorbis/--hevag opt out.
    audio: str = "pcm16"        # pcm16 | vorbis | hevag
    pad_fsb5: bool = False      # DANGER: truncates songs longer than the slot
    convert_to_v3: bool = True
    deploy_full: bool = True    # the one-command end-to-end flow
    skip_plugin: bool = False   # --skip-plugin-deployment (pinned plugin)
    song_name: str = ""         # optional display-name override
    artist: str = ""            # optional artist override
    enable_modes: str = ""      # extra characteristics, e.g. "OneSaber,90Degree"
    skip_mode_generation: bool = False
    disable_mode_mapping: bool = False

    def validate(self) -> None:
        if not self.map_id and not self.song_dir:
            raise ValueError("Deploy needs a BeatSaver map ID or a local song "
                             "folder (Pick a Song tab) — nothing was picked.")
        if not self.additive and not self.target:
            raise ValueError("Pick a target slot first (the stock song the "
                            "custom replaces).")
        if self.song_dir and not Path(self.song_dir).is_dir():
            raise ValueError(f"The staged song folder is missing: {self.song_dir}. "
                             "To fix: re-stage it in the Pick a Song tab "
                             "(folders can move or get deleted between "
                             "staging and deploy).")
        if self.audio not in ("pcm16", "vorbis", "hevag"):
            raise ValueError(f"Unknown audio codec: {self.audio!r}")

    def build_argv(self) -> list[str]:
        """Assemble the pipeline argv. Raises if required options are missing."""
        self.validate()
        if self.additive:
            if self.audio!='pcm16' or self.pad_fsb5 or self.enable_modes or self.song_name or self.artist:
                raise ValueError('Additive install supports original metadata, Standard maps and full PCM16 only.')
            source=['--song-dir',self.song_dir] if self.song_dir else ['--download-beat-saver-song',self.map_id]
            return ['--additive-install',*source,'--config',str(paths.CONFIG_PATH)]
        # M13: local folder wins over the BeatSaver download (the pipeline's
        # own precedence — see the class docstring)
        if self.song_dir:
            argv = ["--song-dir", self.song_dir, "--target", self.target]
        else:
            argv = ["--download-beat-saver-song", self.map_id,
                    "--target", self.target]
        # Audio codec: pcm16 is the pipeline default; only pass the opt-outs.
        if self.audio == "vorbis":
            argv.append("--vorbis")
        elif self.audio == "hevag":
            argv.append("--hevag")
        else:
            argv.append("--pcm16")
        if self.pad_fsb5:
            argv.append("--pad-fsb5")
        else:
            argv.append("--no-pad")
        if self.convert_to_v3:
            argv.append("--convert-to-v3")
        if self.song_name:
            argv += ["--song-name", self.song_name]
        if self.artist:
            argv += ["--artist", self.artist]
        if self.enable_modes:
            argv += ["--enable-modes", self.enable_modes]
        if self.skip_mode_generation:
            argv.append("--skip-mode-generation")
        if self.disable_mode_mapping:
            argv.append("--disable-beatmap-mode-mapping")
        if self.deploy_full:
            argv.append("--deploy-full")
        if self.skip_plugin:
            argv.append("--skip-plugin-deployment")
        return argv

    def describe(self) -> str:
        """One-line human summary for confirm dialogs (PS4-is-production)."""
        if self.additive:
            return "add independent custom song; game must be closed; original songs unchanged"
        src = (f"local folder “{Path(self.song_dir).name}”"
               if self.song_dir else f"map {self.map_id}")
        bits = [f"{src} → slot '{self.target}'",
                f"audio {self.audio}",
                "pad" if self.pad_fsb5 else "no-pad"]
        if self.convert_to_v3:
            bits.append("v3")
        if self.deploy_full:
            bits.append("deploy-full")
        if self.skip_plugin:
            bits.append("skip-plugin")
        return ", ".join(bits)


def pipeline_command(argv: list[str]) -> str:
    """Render the full shell command (what the Pages command-builder shows)."""
    script = Path(paths.PIPELINE)
    rel = script.relative_to(paths.RELEASE_ROOT) if script.is_relative_to(paths.RELEASE_ROOT) \
        else script
    return f"python3 {rel} {' '.join(argv)}"


def flags_only_command(flag_name: str, value: bool) -> list[str]:
    """argv for a feature-flag change via --features-only (Flags page)."""
    return ["--features-only", "--set-feature", f"{flag_name}={str(bool(value)).lower()}"]


def clear_target_command(slot: str) -> list[str]:
    """argv for the surgical revert (PS4 page, per-row)."""
    return ["--clear-target-song", slot]


def verify_command() -> list[str]:
    """argv for a read-only PS4 verification (Deploy page's post-deploy)."""
    return ["--verify-ps4"]


def game_data_request_command(packs: list[str] | None,
                              slots: list[str] | None) -> list[str]:
    """argv for --request-game-data (M12: write the extraction manifest)."""
    argv = ["--request-game-data"]
    if packs:
        argv += ["--game-data-packs", ",".join(packs)]
    if slots:
        argv += ["--game-data-slots", ",".join(slots)]
    return argv


def game_data_pull_command() -> list[str]:
    """argv for --pull-game-data (M12: mirror the extractor output locally)."""
    return ["--pull-game-data"]


def plugin_deploy_command(debug: bool = False) -> list[str]:
    """argv for a plugin-only deploy (M12, Exp 280b). In a source checkout the
    pipeline builds via make; in a release extraction it falls back to the
    bundled plugins/ binary (Exp 235). --debug-logging deploys the DEBUG build."""
    return ["--deploy-plugin"] + (["--debug-logging"] if debug else [])
