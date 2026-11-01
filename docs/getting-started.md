# Installing and setting up OrBeats

[← OrBeats](../README.md)

This guide covers **0.1.20 and later**. It consolidates first-time setup, existing
libraries, diagnostics and recovery; older releases may lack these controls.

## Requirements

- PS4 with GoldHEN plugin support and its FTP server enabled.
- **Beat Saber CUSA12878, patch 2.04**. Other regions/patches are not supported.
- Windows x64 or Linux x64 computer on the same local network as the PS4.
- Your own legally obtained game data for the one-time conversion template.

The computer prepares and installs maps; the main `orbeats.prx` plugin makes the
custom pack appear in the game. **Connecting to FTP or installing the plugin alone
does not complete an empty setup.** OrBeats does not include game assets.

## 1. Install the companion

Download from the official [GitHub Releases page](https://github.com/Wkrotik/OrBeats/releases/latest).
Normal users need only their platform's application:

- **Windows:** run `OrBeats_0.1.20_x64-setup.exe`. It includes the backend, media
  tools and both plugins. The installer is unsigned; verify the source and
  `SHA256SUMS` before deciding whether to proceed through a security warning.
- **Linux:** download `OrBeats_0.1.20_amd64.AppImage`, make it executable and open
  it. The baseline is Ubuntu 22.04 / GLIBC 2.35 or newer. See the
  [Linux packaging notes](../desktop/packaging/LINUX-BASELINE.md).
- The separate `orbeats.prx` and `orbeats_extras.prx` downloads are available for
  manual plugin management. They are also bundled with the application.

Python, FFmpeg and a proprietary FMOD SDK are **not** required on your computer.
GitHub **Actions artifacts** are development candidates wrapped in ZIP files;
public releases provide the installer/AppImage directly. The sources/notices
archive is for source and licensing material, not an additional runtime install.

**Bottles:** 0.1.20 fixes the reproduced startup crash in the unused native
file-drop handler. Update the application in your existing bottle. WebView2 is
still required. Do not disable the WebView sandbox or add GPU workarounds for
this fix. Startup was verified with Soda 11 and WebView2; this is not a claim of
complete Wine/Windows feature parity.

## 2. Connect and install the main plugin

1. **Fully close Beat Saber**. Keep the PS4 on with GoldHEN FTP enabled.
2. In **Console & settings**, enter the PS4's **IP address only**, choose **Test**,
   then **Save connection**. Testing uses the address currently typed, but does
   not save it or validate the song library. GoldHEN FTP uses port **2121**,
   anonymous access and no password; do not append the port to the IP field.
3. Check/install the bundled main plugin. Keep `orbeats.prx` enabled in GoldHEN;
   do not register multiple copies under different names.

The companion never launches or closes Beat Saber for you. Opening the app or
setup page does not automatically connect to or change the PS4.

## 3. Complete first-time setup

An incomplete setup opens automatically. To reopen it later, choose **Setup** at
the top right of **Console & settings**; it is not a permanent sidebar tab.

The activity panel **above the instructions** shows the current step, elapsed
time and an animated loading bar while work runs. The bar indicates activity,
**not a percentage**. Template validation can take a while. Keep OrBeats open and
do not start another check or installation while it is working.

### Existing library or retained template: check this first

Choose **Check existing setup / Fetch template**. A verified existing OrBeats
library, retained conversion template or explicitly configured compatible template
can supply the schema. OrBeats validates it through a synthetic conversion and
independent readback before treating it as ready.

- If setup reports **complete**, install songs normally. **Do not prepare a new
  extraction or finalize anything when no temporary settings are pending.**
- A subsequent check of an intact, hash-verified local cache does not reconnect
  to FTP or reconvert the template.
- If a previous extraction still requires restoration, a ready template alone is
  not enough: follow the close-and-restore step below.

### Empty library with no compatible template: extract once

1. Keep Beat Saber **fully closed**, choose **Prepare first-time extraction**, and
   confirm. OrBeats temporarily requests only the base-game `100Bills` schema
   through the main plugin's extractor. It retains the exact previous request
   and feature settings for restoration.
2. **Launch Beat Saber yourself**, with the main plugin enabled. Wait at its main
   menu for the extraction notification; keep GoldHEN FTP available.
3. Leave the game running and choose **Check existing setup / Fetch template**.
   This step only reads the PS4. OrBeats must fetch the data, perform a synthetic
   conversion and independently validate it. A notification or FTP connection
   alone does not mean setup is complete.
4. **Fully close Beat Saber**, choose **Restore settings / finish**, and confirm.
   This restores only the temporary request/features changes, with title checks
   and transaction readback. Plugin-owned extraction status/output are preserved.
5. Start song installation only after setup reports **complete**.

If extraction is pending, wait and fetch again. An explicit extraction failure
requires fully closing and relaunching the game before retrying: the native
extractor runs once per game boot. Invalid/unsupported assets are refused.
If connection/settings files change independently, stop and inspect the retained
recovery state; do not delete recovery files to bypass a refusal.

This flow does not dump the whole game, reactivate unrelated extraction requests,
modify stock songs, saves or DLC, or bypass entitlements. The local `setup/` cache
contains a derived, validated template with synthetic content, not bundled game
data. Its configured path appears in advanced settings. No templates are uploaded.
The raw-stock path has not been independently confirmed on a completely fresh
console; offline tests are not a substitute for that hardware validation.

## 4. Add and manage songs

Search **Discover** by title, artist, mapper or BeatSaver link, inspect the map's
difficulties, add it to **Downloads**, then explicitly start installation.
Keep Beat Saber **fully closed** for installs, removals, plugin writes and setup
preparation/restoration. A restored queue starts paused.

The current/last job log is above pending entries and history. Expand it, choose
**Jump to latest** to resume following output, or copy/save it when reporting an
error. Unsupported map requirements are explained there; see
[map compatibility](native-map-expansion.md).

When installation finishes, launch Beat Saber and select **OrBeats**. Stock and
DLC songs remain in place. Use **Your library** with the game closed to remove
custom songs individually or in a selection.

## Optional Extras and updates

Install/check the main plugin first, then use **Install Extras** in Console &
settings with Beat Saber fully closed. Extras is optional, registered only for
CUSA12878 and does not replace the main plugin or alter your song library.
Unknown binaries or ambiguous registrations are refused rather than erased.

Extras hides supported promotional tiles, auto-dismisses the health warning
while preserving settings, and provides a **read-only top-ten ScoreSaber
leaderboard** for supported Standard custom-map difficulties. It does not submit
scores or sign into an account. Songs imported without their original map identity
must be reimported for score lookup. Unsupported/unranked maps and network errors
are not presented as a successful empty leaderboard.

**Check updates** in Settings queries the official public release for the desktop
application and both bundled plugin versions. This is separate from **Check PS4
version**: bundled-version information does not prove what is installed on the
console. An unavailable feed does not mean up to date. Desktop upgrades are manual;
no downloaded program is automatically executed. Explicit plugin updates verify
SHA-256, byte count and embedded version before closed-title transaction/readback.

## Interrupted installation recovery

If an operation reports `.install-lock`, do not delete it blindly. Stop all
imports, CLI tasks, plugin writes and setup operations **on every computer**, and
fully close Beat Saber. The app cannot reliably detect another computer's work.
Keep the original log and interrupted transaction evidence.

**Installation recovery**, below Updates in Console & settings, can explicitly
inspect and remove **only an empty lock** after readable, stable manifest/file
checks and a local inspection archive. Nonempty locks, pending staging/rollback
files, unreadable or inconsistent state are refused. Lock age alone is not proof
of safety. Recovery does not delete songs/historical backups or restart an import.
See the [recovery documentation](additive-companion.md) if inspection is refused.

## Diagnostics and privacy

Bounded per-job logs are saved under the application data directory:

- **Windows:** `%LOCALAPPDATA%\io.orbeats.companion\logs\`
- **Linux:** normally `~/.local/share/io.orbeats.companion/logs/`

`installation-*.log` records worker startup, output and exit status (up to 20 files,
about 4 MiB each). `setup-*.log` records validation phases (up to 20 files, about
1 MB of phase output plus a delayed diagnostic stack). A stack trace may be
requested after 30 seconds; it is diagnostic, **not** an automatic retry or proof
that an operation stopped. A no-output warning is not permission to start a second
writer. Downloads also offers Copy/Save for the current installation log.

Review relevant logs for personal paths, addresses and song names before sharing.
**Do not send or delete the whole app-data folder:** it also contains settings,
private templates, queue state and recovery records. Logs are not uploaded
automatically. Do not expose the local administrative web server or GoldHEN FTP
to the Internet.
