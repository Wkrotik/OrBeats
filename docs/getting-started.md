# Getting started with OrBeats

[← OrBeats](../README.md)

## Requirements

- PS4 with GoldHEN plugin support and its FTP server enabled.
- **Beat Saber CUSA12878, patch 2.04**. Other regions/patches are not supported.
- Windows x64 or Linux x64 computer on the same network as the PS4.
- Your own legally obtained game data for the one-time conversion template. A
  fresh setup is **not ready after FTP connects or the plugin is installed**.

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

## First setup: connection, plugin and conversion template

**Local 0.1.17 candidate:** the guided flow below is new development work, not a
feature of the currently published 0.1.16 installer. On 0.1.16 an empty setup
still requires a manually obtained, compatible prepared template in the advanced
conversion setting. Updating the app does not itself obtain game assets.

The **First setup** page opens automatically until a local template is validated
and any temporary extraction settings have been restored. It remains accessible
from the sidebar afterwards. Opening the app does not automatically connect to or
change the PS4.

1. **Fully close Beat Saber**, leaving the PS4 on and GoldHEN FTP enabled.
2. Open **Console & settings**, enter the PS4's **IP address only**, test it, then
   **Save connection**. The test does not save the address or validate the library.
   GoldHEN uses port **2121**, anonymous access and no password.
3. Check/install the bundled main `orbeats.prx` using the plugin controls. Keep
   it enabled in GoldHEN; do not register two copies under different names.
4. Return to **First setup** and choose **Fetch / check template**. An existing
   verified OrBeats library or retained template can supply the required schema,
   so existing users normally do not need another extraction.
5. If no compatible template exists, keep Beat Saber **fully closed**, choose
   **Prepare extraction**, and confirm. OrBeats temporarily requests just the
   base-game `100Bills` asset through the main plugin's existing extractor. It
   archives the exact previous request file and feature settings for restoration;
   it does not reactivate unrelated extraction requests, dump the entire game,
   edit stock songs/saves/DLC or bypass entitlements.
6. **Launch Beat Saber yourself**, with the main plugin enabled, and wait at its
   main menu. Keep GoldHEN FTP available. Choose **Fetch / check template** in
   OrBeats. This step only reads the PS4, so it can run while the title is open.
   A successful FTP connection or extraction notification alone is not completion:
   OrBeats must perform a synthetic conversion and independently validate it.
7. **Fully close Beat Saber**, then choose **Restore settings / finish** and
   confirm. Only the request/features bytes changed by this setup are restored,
   with title checks and transaction readback. Plugin-owned extraction status and
   output are preserved. Do not install songs until setup reports ready.

If extraction is still pending, wait and fetch again. An explicit extraction
failure requires fully closing and relaunching the game before retrying; the
native extractor runs once per game boot. Unsupported or invalid assets are
refused, not accepted as a completed setup. If connection/settings files change
independently, stop and inspect the retained recovery state instead of overwriting
it. Do not delete recovery files to get past a refusal.

The local cache contains only a derived, validated conversion template with
synthetic song content, under the app data folder's `setup/` directory. The
configured template path is displayed in advanced settings. Original extracted
data/status remain on the user's PS4; OrBeats neither ships nor uploads them.
The raw-stock first-run path still requires hardware validation; offline tests
are not a claim that this sequence has been confirmed on a fresh console.

A title-state refusal means the game must be closed; it is not a reason to bypass
the guard. The companion never launches or closes the game for you.

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

## Installation diagnostics (local 0.1.17 candidate)

0.1.16 keeps live job output in memory; it does not automatically save a complete
installation log. The local candidate adds flushed, bounded per-job logs under:

- **Windows:** `%LOCALAPPDATA%\io.orbeats.companion\logs\installation-*.log`
- **Linux:** the app's local data directory, normally
  `~/.local/share/io.orbeats.companion/logs/installation-*.log`

At most20 app-owned job logs are retained, roughly4MiB each. They include worker
startup stages, merged stdout/stderr, and exit status. A startup stack trace is
requested after30seconds; this is diagnostic, not an automatic retry, kill or a
proven fix for the reported native Windows stall. A no-output warning does not
mean it is safe to start a second install. The Downloads panel's Copy/Save log
controls can also export the current live log.

For a bug report, send only the relevant job log after reviewing it for personal
paths, addresses or song names. Do **not** send the whole app-data folder: it can
contain settings, private templates, recovery records and downloads. Logs are
never uploaded automatically.

### Testing-candidate follow-up (0.1.18; not a public release)

Setup is no longer a permanent navigation tab. An incomplete first setup opens
automatically; reopen it with **Setup** at the right of the Console & settings
heading. The template check reports live transfer/conversion stages and elapsed
time. It is read-only on the PS4; validation can take a minute. Do not start
another check while it is working. Its private `setup-*.log` files sit beside
`installation-*.log` in the app-data `logs` folder (at most 20 setup logs; phase
output is capped at about 1 MB plus a delayed diagnostic stack). Never share the
whole app-data folder. No logs are uploaded automatically.

An `.install-lock` refusal must be inspected, not automatically cleared. Close
other companion/CLI instances, keep Beat Saber closed, and retain any interrupted
transaction data. A lock's age, empty directory or absent owner file does not
prove it is safe to delete. A permission failure to create the directory is now
reported separately from a confirmed existing lock.

### Interrupted installation lock (0.1.18 testing candidate)

If an import reports `.install-lock`, **do not clear it while any import, plugin
update, setup or CLI task is running on any computer**. Close Beat Saber and stop
all writers first. The current app cannot reliably detect another computer's work.

In the0.1.18 candidate, Console & settings has **Installation recovery** below
Updates. Its confirmation permits only removal of an empty lock after readable,
stable manifest/file-name checks and a local inspection archive. Nonempty locks,
pending staging/rollback files and inaccessible or inconsistent state are refused;
keep that evidence for manual inspection. Historical backups and songs are never
deleted. This is not automatic stale-lock detection, and recovery does not restart
an import. This button is not present in the public0.1.16 or earlier0.1.17 candidate.
