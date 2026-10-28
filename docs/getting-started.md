# Getting started with OrBeats

[← OrBeats](../README.md)

## Requirements

- PS4 with GoldHEN plugin support and its FTP server enabled.
- **Beat Saber CUSA12878, patch 2.04**. Other regions/patches are not supported.
- Windows x64 or Linux x64 computer on the same network as the PS4.
- Your own legally obtained conversion template on a completely empty setup.

The companion and native plugin are separate components: the computer prepares
and installs maps; `orbeats.prx` makes the custom pack appear in the game.

## Install the companion

Use a Windows installer (`.exe`) or Linux AppImage from the project's builds.
Before a public release, candidates are available through the private
[Actions builds](https://github.com/Wkrotik/OrBeats/actions/workflows/private-build.yml).
GitHub wraps Actions artifacts in a ZIP; extract the installer before running it.
Release readiness and platform test results belong in the
[distribution checklist](public-release-checklist.md), not the main README.

- **Windows:** run the installer. Unsigned candidates may trigger SmartScreen;
  verify the source and checksum before deciding whether to proceed.
- **Linux:** make the AppImage executable, then open it. The baseline is
  Ubuntu 22.04 / GLIBC 2.35 or newer; distribution details are in the
  [Linux packaging notes](../desktop/packaging/LINUX-BASELINE.md).

Packaged builds include their Python backend and media tools. You do not need
Python, FFmpeg or a proprietary FMOD SDK installed to use them.

## Connect and set up the plugin

1. **Fully close Beat Saber**, leaving the PS4 on and GoldHEN FTP enabled.
2. In **Console & settings**, enter the PS4's IP address. GoldHEN uses FTP
   port **2121**, anonymous access and no password.
3. Use the plugin controls to check or install the bundled `orbeats.prx`.
   Keep it enabled in GoldHEN. Do not register two copies under different names.
4. On a new empty installation, supply your own validated prepared template in
   the advanced conversion settings. An existing additive library can supply
   its template from the PS4. OrBeats does not distribute copyrighted game assets.

A title-state refusal means the game must be closed; it is not a reason to bypass
the guard. The companion never launches the game for you.

## Add and manage songs

Search **Discover** by title, artist, mapper or BeatSaver link. Open a map's
information to inspect its difficulties, then add it to **Downloads**. Start
installation explicitly; a restored queue starts paused.

The current/last installation log sits above pending entries and history. Expand
it to read progress, use **Jump to latest** to resume following output, or copy
or save it when reporting a failure. Unsupported map requirements are explained
there; see [map compatibility](native-map-expansion.md).

When the queue finishes, launch Beat Saber and select **OrBeats**. Stock and DLC
songs stay in place. Return to **Your library** with the title closed to remove
custom songs individually or in a selection.

## Recovery and privacy

Settings, queue history and rollback files are local to your computer. Writes use
staging, readback and a final library publication; successful operations remove
temporary remote files while retaining local recovery data.

If an interrupted operation leaves an installation lock, preserve the log and
journal. Do not delete the lock or unknown console files blindly. See the
[recovery documentation](additive-companion.md).

The source web server is a local administrative interface, not a public hosting
service. Do not expose it or GoldHEN FTP to the Internet.
