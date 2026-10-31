"""Windows-native frozen import/serve/stop smoke; synthetic files and loopback only.

Never uploads to a console or prints the private bootstrap URL/cookie. This does
not establish NSIS upgrade/uninstall, WebView GUI or PS4 playback approval.
"""

import argparse
import http.cookiejar
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import urllib.request
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def codec_fixture(root, rate):
    """Generate a synthetic original; phase markers survive native Windows exits."""
    print(
        f"codec fixture {rate}: importing numpy/soundfile", file=sys.stderr, flush=True
    )
    import numpy as np
    import soundfile as sf

    print(f"codec fixture {rate}: generating samples", file=sys.stderr, flush=True)
    times = np.arange(12 * rate + 1) / rate
    fixture = root / f"original-{rate}.ogg"
    samples = np.stack(
        [0.25 * np.sin(2 * np.pi * 440 * times), 0.2 * np.sin(2 * np.pi * 660 * times)],
        axis=1,
    )
    print(f"codec fixture {rate}: writing Vorbis", file=sys.stderr, flush=True)
    # A single twelve-second Vorbis write exhausts the Windows wheel encoder's
    # native stack. Bound fixture generation without shortening the audio or
    # avoiding any frozen decoder/resampler checks.
    with sf.SoundFile(
        fixture,
        mode="w",
        samplerate=rate,
        channels=2,
        format="OGG",
        subtype="VORBIS",
        compression_level=0.5,
    ) as stream:
        for offset in range(0, len(samples), 4096):
            stream.write(samples[offset : offset + 4096])
    print(f"codec fixture {rate}: complete", file=sys.stderr, flush=True)
    return fixture


def check_codecs(executable, env, root):
    """Synthetic frozen-media checks; callable in host tests without Windows."""
    # Exercise the frozen codec path, including48kHz preserved-audio
    # verification, with no host Python/FFmpeg in the child search path.
    codec_rates = []
    for rate in (44100, 48000):
        fixture = codec_fixture(root, rate)
        print(f"frozen codec {rate}: starting helper", file=sys.stderr, flush=True)
        checked = subprocess.run(
            [str(executable), "--desktop-check-codecs", str(fixture)],
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
        if checked.returncode:
            raise ValueError(
                f"Frozen {rate}Hz codec check failed: " + checked.stderr[-4000:]
            )
        codec = json.loads(checked.stdout)
        assert codec["bundled_codecs_only"] and codec["host_discovery_disabled"]
        assert codec["independent_decode"] and codec["console_writes"] is False
        assert codec["rate"] == rate and codec["frames"] == 12 * rate + 1
        codec_rates.append(rate)
    return codec_rates


def smoke(executable):
    if sys.platform != "win32":
        raise ValueError("Native Windows execution required")
    from PIL import Image

    executable = Path(executable).resolve()
    runtime = executable.parent / "_internal/runtime"
    env = {
        k: v for k, v in os.environ.items() if not k.startswith(("ORBEATS_", "PYTHON"))
    }
    env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
    env["ORBEATS_RUNTIME_ROOT"] = str(runtime)
    (ROOT / "temp").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="windows-smoke-", dir=ROOT / "temp") as tmp:
        root = Path(tmp)
        codec_rates = check_codecs(executable, env, root)
        from smoke_fresh_library import check as check_fresh_library

        fresh_library = check_fresh_library(executable, env, root)
        source = root / "source"
        source.mkdir()
        Image.new("RGB", (64, 64), (50, 80, 120)).save(source / "cover.png")
        with wave.open(str(source / "song.wav"), "wb") as audio:
            audio.setnchannels(2)
            audio.setsampwidth(2)
            audio.setframerate(44100)
            audio.writeframes(b"\0" * 44100 * 4 * 12)
        info = {
            "_version": "2.0.0",
            "_songName": "Synthetic CI fixture",
            "_songSubName": "",
            "_songAuthorName": "OrBeats tests",
            "_levelAuthorName": "CI",
            "_beatsPerMinute": 120,
            "_songTimeOffset": 0,
            "_previewStartTime": 0,
            "_previewDuration": 8,
            "_songFilename": "song.wav",
            "_coverImageFilename": "cover.png",
            "_environmentName": "DefaultEnvironment",
            "_difficultyBeatmapSets": [
                {
                    "_beatmapCharacteristicName": "Standard",
                    "_difficultyBeatmaps": [
                        {
                            "_difficulty": "ExpertPlus",
                            "_difficultyRank": 9,
                            "_beatmapFilename": "ExpertPlus.dat",
                            "_noteJumpMovementSpeed": 16,
                            "_noteJumpStartBeatOffset": 0,
                        }
                    ],
                }
            ],
        }
        chart = {
            "_version": "2.0.0",
            "_notes": [
                {
                    "_time": 2,
                    "_lineIndex": 1,
                    "_lineLayer": 1,
                    "_type": 0,
                    "_cutDirection": 1,
                }
            ],
            "_obstacles": [
                {"_time": 0, "_lineIndex": 0, "_type": 0, "_duration": 0, "_width": 0}
            ],
            "_events": [],
        }
        (source / "Info.dat").write_text(json.dumps(info))
        (source / "ExpertPlus.dat").write_text(json.dumps(chart))
        output = root / "normalized"
        run = subprocess.run(
            [
                str(executable),
                "--desktop-task",
                "import-v3",
                "--",
                "--experimental",
                "--source",
                str(source),
                "--output",
                str(output),
            ],
            env=env,
            check=False,
            capture_output=True,
            text=True,
            timeout=90,
        )
        if run.returncode:
            raise ValueError("Frozen synthetic import failed: " + run.stderr[-4000:])
        report = json.loads(run.stdout)
        assert report["note_counts"]["ExpertPlus"] == 1, report.keys()
        state = root / "state"
        with (root / "backend-stderr.log").open("w") as stderr:
            proc = subprocess.Popen(
                [
                    str(executable),
                    "--state-dir",
                    str(state),
                    "--resources",
                    str(runtime),
                ],
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr,
                text=True,
            )
            try:
                lines = queue.Queue()
                threading.Thread(
                    target=lambda: lines.put(proc.stdout.readline(4097)), daemon=True
                ).start()
                ready = json.loads(lines.get(timeout=40))
                assert ready["protocol"] == 1 and set(ready) == {"protocol", "url"}
                opener = urllib.request.build_opener(
                    urllib.request.ProxyHandler({}),
                    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()),
                )
                assert ready["url"].startswith("http://127.0.0.1:")
                with opener.open(ready["url"], timeout=10) as response:
                    assert response.status == 200
                from urllib.parse import urlsplit

                url = urlsplit(ready["url"])
                base = f"{url.scheme}://{url.netloc}"
                with opener.open(base + "/api/ping", timeout=10) as response:
                    ping = json.load(response)
                    assert ping["pipeline_present"]
            finally:
                # STOP then normal wait: no force-kill during transaction work.
                if proc.poll() is None:
                    proc.stdin.write("STOP\n")
                    proc.stdin.flush()
                    proc.stdin.close()
                proc.wait(timeout=45)
            assert proc.returncode == 0
        saved = json.loads((state / "queue.json").read_text())
        assert saved["paused"] and not saved["pending"]
    return {
        "native_windows": True,
        "frozen_import": True,
        "frozen_codec_rates": codec_rates,
        "fresh_library": fresh_library,
        "host_python_or_ffmpeg_on_path": False,
        "private_bootstrap": True,
        "graceful_stop": True,
        "ps4_operations": False,
        "native_gui_tested": False,
        "installer_approved": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    import faulthandler

    faulthandler.enable()
    parser.add_argument("--helper", type=Path)
    parser.add_argument("--fixtures-only", action="store_true")
    args = parser.parse_args()
    if args.fixtures_only:
        with tempfile.TemporaryDirectory(prefix="orbeats-codec-fixtures-") as tmp:
            for rate in (44100, 48000):
                codec_fixture(Path(tmp), rate)
    elif args.helper:
        print(json.dumps(smoke(args.helper), indent=2))
    else:
        parser.error("choose --helper or --fixtures-only")
