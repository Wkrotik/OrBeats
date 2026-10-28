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

Release downloads belong on the official [GitHub Releases page](https://github.com/Wkrotik/OrBeats/releases/latest):
Windows x64 installer (`.exe` directly, not a ZIP), Linux x64 AppImage, and the
separate `orbeats.prx` and `orbeats_extras.prx` plugins. If no release is listed,
use the source/build instructions; a release must not be assumed to exist.
[Actions builds](https://github.com/Wkrotik/OrBeats/actions/workflows/private-build.yml)
are development candidates. GitHub wraps **Actions artifacts**, not the intended
release installer, in a ZIP. See the [distribution checklist](public-release-checklist.md)
for evidence and remaining validation limits.

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

## Optional Extras and updates

Install/check the main plugin first, then use **Install Extras** in Console &
settings while Beat Saber is fully closed. Extras is registered only for
CUSA12878; it does not replace the main plugin or modify your song library.
Unknown existing binaries/ambiguous registrations are refused rather than erased.

Extras adds health-warning auto-dismiss (preserving existing settings) and a
**read-only top-ten ScoreSaber leaderboard** for supported Standard custom-map
difficulties. It does not submit scores or sign into a ScoreSaber account. Older
songs imported without their original map identity must be reimported for score
lookup. Unranked/unsupported maps and network failures are not fake empty success.

**Check updates** queries the official public GitHub release for the desktop app
and both bundled plugin versions. This is separate from **Check PS4 version**;
a bundled-version comparison is not a claim about the console's installed files.
An unavailable/offline feed does not mean up to date. Desktop upgrades are manual:
copy the release link and download the new installer/AppImage. Plugin release
installation is explicit and confirmed; it verifies the manifest's SHA-256,
byte count and embedded version before the usual closed-title/readback/local
recovery transaction. No program is downloaded and automatically executed.

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
