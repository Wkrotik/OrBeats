/* OrBeats web app — Phase 1 client.
 * Vanilla JS (plan §7.1): no build step, same bundle runs on GitHub Pages.
 * Mode detection: /api/ping answers only in local-backend mode; the Pages
 * build stubs it and the app switches to command-builder mode.
 */

"use strict";

// ---------------------------------------------------------------- state
const state = {
  mode: "detecting",           // local-backend | pages
  dumpOk: false,
  connOk: false,
  pickedSong: null,            // slim BeatSaver doc — or {source:"local", dir, …} (M13)
  catalog: [],                  // albums from /api/catalog
  staged: [],                   // staged local songs (M13)
  pollTimer: null,
  bsageTimer: null,
};

const $ = (id) => document.getElementById(id);

// ---------------------------------------------------------------- mode detection
async function detectMode() {
  try {
    const r = await fetch("/api/ping", { signal: AbortSignal.timeout(2500) });
    const j = await r.json();
    state.mode = j.mode === "local-backend" ? "local-backend" : "unknown";
  } catch {
    state.mode = "pages"; // no backend → command-builder mode
  }
  const badge = $("mode-badge");
  badge.textContent =
    state.mode === "local-backend" ? "● local backend (full function)"
    : state.mode === "pages" ? "◐ pages mode (command builder)"
    : "● checking…";
  badge.className = state.mode === "local-backend" ? "local" : "pages";
  if (state.mode === "pages") {
    document.querySelectorAll(".local-only").forEach(el => el.classList.add("hidden"));
    // Command-builder mode: the Deploy button can't run anything — relabel
    // it so the expectation is correct before the click.
    const deployBtn = document.getElementById("btn-deploy");
    if (deployBtn) deployBtn.textContent = "Copy deploy command";
  }
}

// ---------------------------------------------------------------- nav
function showPage(name) {
  document.querySelectorAll("main .page").forEach(p => p.classList.add("hidden"));
  $(`page-${name}`).classList.remove("hidden");
  document.querySelectorAll("#nav button").forEach(b =>
    b.classList.toggle("active", b.dataset.page === name));
}
document.querySelectorAll("#nav button").forEach(b =>
  b.addEventListener("click", () => showPage(b.dataset.page)));
document.addEventListener("click", e => {
  if (e.target.dataset && e.target.dataset.nav) { e.preventDefault(); showPage(e.target.dataset.nav); }
});

// ---------------------------------------------------------------- helpers
async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    let msg = `${r.status} ${r.statusText}`;
    try { msg = (await r.json()).detail || msg; } catch { /* keep default */ }
    throw new Error(msg);
  }
  return r.json();
}

function setResult(id, text, cls) {
  const el = $(id);
  el.textContent = text;
  el.className = `result ${cls || ""}`;
}

function nativeDiffBadges(song) {
  const want = ["Easy", "Normal", "Hard"];
  const missing = want.filter(d => !(song.nativeDifficulties || []).includes(d));
  const ok = missing.length === 0;
  return `<span class="badge ${ok ? "ok" : "miss"}">${
    ok ? "E/N/H native" : `missing ${missing.join("/")}`}</span>`;
}

function renderPickedSong() {
  const box = $("picked-song");
  if (!state.pickedSong) { box.classList.add("hidden"); return; }
  const s = state.pickedSong;
  box.classList.remove("hidden");
  if (s.source === "local") {
    // M13: a staged local folder (Beat Sage / zip / user folder)
    const diffs = (s.difficulties || []).join("/") || "?";
    $("picked-song-body").innerHTML =
      `<div class="song"><div class="meta"><b>${esc(s.name)}</b>
       <span class="muted">by ${esc(s.artist || "?")} · ${esc(s.schema || "map")} ·
       ${diffs} · BPM ${s.bpm ?? "?"}</span></div>
       <div class="badges"><span class="badge ok">local folder</span></div></div>
       <div class="muted" style="margin-top:.4rem"><code>${esc(s.dir)}</code></div>`;
    return;
  }
  $("picked-song-body").innerHTML =
    `<div class="song"><div class="meta"><b>${esc(s.name)}</b>
     <span class="muted">${esc(s.songAuthorName || "?")} — mapped by ${esc(s.levelAuthorName || "?")} ·
     BPM ${s.bpm ?? "?"} · ${s.downloads ?? "?"} downloads</span></div>
     <div class="badges">${nativeDiffBadges(s)}</div></div>
     <div class="muted" style="margin-top:.4rem">Map ID <code>${esc(s.id)}</code>
     ${s.hash ? `· hash <code>${esc(s.hash.slice(0, 12))}…</code>` : ""}</div>`;
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = String(s ?? '');
  return d.innerHTML;
}

// ---------------------------------------------------------------- wizard
async function checkDump(path) {
  if (!path) { setResult("dump-result", "Enter a dump folder path first.", "bad"); return; }
  setResult("dump-result", "Validating…", "");
  try {
    const j = await api(`/api/dump/validate?path=${encodeURIComponent(path)}`);
    state.dumpOk = j.ok;
    if (j.ok) {
      setResult("dump-result",
        `✅ Valid dump.\nFound DLC packs (${j.dlc_packs_found.length}): ${j.dlc_packs_found.join(", ") || "none"}`,
        "ok");
    } else {
      setResult("dump-result", `❌ Problems found:\n${j.errors.map(e => "• " + e).join("\n")}`, "bad");
    }
    if (j.warnings && j.warnings.length)
      $("dump-result").textContent += `\n⚠ ${j.warnings.join("\n⚠ ")}`;
    updateSaveButton();
  } catch (e) { setResult("dump-result", "Validation failed: " + e.message, "bad"); }
}

async function loadDumpDefault() {
  try {
    const j = await api("/api/dump/default-location");
    $("dump-default-path").textContent = j.default_path;
    if (j.exists) { $("dump-path").value = j.default_path; checkDump(j.default_path); }
  } catch { /* Pages mode: skip */ }
}

async function testConnection() {
  setResult("conn-result", "Testing…", "");
  try {
    const j = await api("/api/ps4/test");
    if (j.ok) {
      state.connOk = true;
      setResult("conn-result",
        `✅ PS4 reachable — ${j.count} files in the AFR dir.`, "ok");
    } else {
      state.connOk = false;
      setResult("conn-result",
        `❌ Couldn't reach the PS4 (${j.error || "no response"}). ` +
        `Check the IP, that GoldHEN's FTP server is running (Settings → GoldHEN → FTP), ` +
        `and that this machine can reach it.`, "bad");
    }
    updateSaveButton();
  } catch (e) { setResult("conn-result", "Test failed: " + e.message, "bad"); }
}

function updateSaveButton() {
  const host = $("ps4-ip").value.trim();
  const port = Number($("ps4-port").value);
  $("btn-save-config").disabled = !host || !Number.isInteger(port) || port < 1 || port > 65535;
  $("btn-save-config").textContent = "Save PS4 connection (no dump needed for additive imports)";
}

async function saveConfig() {
  try {
    const j = await api("/api/config/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        dump_root: $("dump-path").value.trim(),
        ps4_ip: $("ps4-ip").value.trim(),
        ftp_port: parseInt($("ps4-port").value, 10) || 2121,
      }),
    });
    setResult("save-result",
      `✅ Saved ${j.config_path}\nSetup complete — go pick a song!`, "ok");
  } catch (e) { setResult("save-result", "Save failed: " + e.message, "bad"); }
}

// ---------------------------------------------------------------- song picker
async function searchBeatSaver() {
  const q = $("bs-query").value.trim();
  if (!q) return;
  $("bs-results").innerHTML = "<p class='muted'>Searching…</p>";
  let docs;
  try {
    const j = await api(`/api/beatsaver/search?q=${encodeURIComponent(q)}&per_page=30`);
    docs = j.docs;
  } catch (e) {
    $("bs-results").innerHTML = `<p class='result bad'>Search failed: ${esc(e.message)}</p>`;
    return;
  }
  const filter = $("bs-filter-enh").checked;
  if (filter) docs = docs.filter(s => s.nativeDifficulties.length === 3);
  if (!docs.length) {
    $("bs-results").innerHTML = "<p class='muted'>No results" +
      (filter ? " with native Easy/Normal/Hard — try unchecking the filter." : ".") + "</p>";
    return;
  }
  $("bs-results").innerHTML = docs.map(s =>
    `<div class="song">
       <div class="meta">
         <b>${esc(s.name)}</b>
         <span class="muted">${esc(s.songAuthorName || "?")} · mapped by ${esc(s.levelAuthorName || "?")} ·
         BPM ${s.bpm ?? "?"} · ${s.downloads ?? "?"} downloads</span>
       </div>
       <div class="badges">${nativeDiffBadges(s)}</div>
       <button class="pick" data-mapid="${esc(s.id)}">Pick</button>
     </div>`).join("");
  $("bs-results").querySelectorAll("button.pick").forEach(b =>
    b.addEventListener("click", () => pickSong(b.dataset.mapid)));
}

async function pickSong(mapId) {
  try {
    state.pickedSong = await api(`/api/beatsaver/map/${encodeURIComponent(mapId)}`);
    renderPickedSong();
    showPage("deployPage");
  } catch (e) {
    alert("Couldn't load map " + mapId + ":\n" + e.message +
      "\n\nMaps do get deleted from BeatSaver — search for the song and pick another upload.");
  }
}

async function lookupMapId() {
  const id = $("bs-mapid").value.trim();
  if (!id) return;
  setResult("bs-mapid-result", "Looking up…", "");
  try {
    state.pickedSong = await api(`/api/beatsaver/map/${encodeURIComponent(id)}`);
    setResult("bs-mapid-result", `✅ Found: ${state.pickedSong.name}`, "ok");
    renderPickedSong();
    showPage("deployPage");
  } catch (e) { setResult("bs-mapid-result", "❌ " + e.message, "bad"); }
}

// ---------------------------------------------------------------- M13: Beat Sage + local songs
async function loadBeatsageGuide() {
  try {
    const g = await api("/api/beatsage/guide");
    renderBeatsageGuide(g.recommended || {}, g.steps || [], g);
  } catch (e) {
    // Pages/command-builder mode (no backend): the guide is static constants
    // — the same steps + our recommended options, rendered locally.
    if (state.mode === "pages") {
      renderBeatsageGuide(
        { difficulties: ["Normal", "Hard", "Expert", "ExpertPlus"],
          modes: ["Standard"], events: ["DotBlocks", "Obstacles"],
          environment: "DefaultEnvironment" },
        ["Open beatsage.com (the button below).",
         "Upload your audio file (you must have the rights to it).",
         "Pick the recommended options shown on this card.",
         "Click Generate and wait a few minutes.",
         "Download the generated zip when it completes.",
         "Extract the zip — its folder is what --song-dir takes (command-builder mode)."],
        { density_note: "What to expect: Beat Sage's Easy/Normal/Hard are one mellow band — "
            + "the density lives in Expert/Expert+. No density slider exists on their service." });
    } else {
      $("bsage-guide").innerHTML =
        `<p class="result bad">Guide unavailable (${esc(e.message)}). To fix: open
         <a href="https://beatsage.com" target="_blank" rel="noopener">beatsage.com</a> directly.</p>`;
    }
  }
}

function renderBeatsageGuide(rec, steps, g) {
  if (g && g.density_note) $("bsage-density-note").textContent = g.density_note;
  if (g && g.systems) {
    const sysSel = $("bsage-system");
    sysSel.innerHTML = Object.entries(g.systems).map(([k, v]) =>
      `<option value="${k}" title="${esc(v.description)}">${esc(v.label)}</option>`).join("");
  }
  const envSel = $("bsage-env");
  const envs = ["DefaultEnvironment", "Origins", "TriangleEnvironment", "NiceEnvironment",
    "BigMirrorEnvironment", "DragonsEnvironment", "KDAEnvironment", "MonstercatEnvironment",
    "CrabRaveEnvironment", "PanicEnvironment", "RocketEnvironment", "GreenDayEnvironment",
    "GreenDayGrenadeEnvironment", "TimbalandEnvironment", "FitBeatEnvironment", "LinkinParkEnvironment"];
  envSel.innerHTML = envs.map(e =>
    `<option value="${e}" ${e === (rec.environment || "DefaultEnvironment") ? "selected" : ""}>${e}</option>`).join("");
  const stepsHtml = (steps || []).map(s => `<li>${esc(s)}</li>`).join("");
  const pagesNote = state.mode === "pages"
    ? `<p class="muted">(command-builder mode: the zip drop needs the local web app —
       extract the zip and pass its folder with <code>--song-dir</code> instead.)</p>` : "";
  $("bsage-guide").innerHTML =
    `<p class="muted">Their UI's options, pre-filled with OUR recommendations for PS4 deploys:</p>
    <ul class="guide-opts">
      <li>Difficulties: <b>${(rec.difficulties || []).join(", ") || "Normal, Hard, Expert, Expert+"}</b></li>
      <li>Modes: <b>${(rec.modes || []).join(", ") || "Standard"}</b> (the pipeline builds the extra modes itself)</li>
      <li>Events: <b>${(rec.events || []).join(", ") || "DotBlocks, Obstacles"}</b></li>
      <li>Environment: <b>${esc(rec.environment || "DefaultEnvironment")}</b></li>
    </ul>
    <ol class="guide-steps">${stepsHtml}</ol>
    ${pagesNote}
    <a class="btnish" href="https://beatsage.com" target="_blank" rel="noopener">Open beatsage.com ↗</a>`;
}

function bsageCheckedValues(cls) {
  return Array.from(document.querySelectorAll(`input.${cls}:checked`)).map(c => c.value);
}

async function generateWithBeatsage() {
  const result = $("bsage-result");
  const log = $("bsage-log");
  if (!$("bsage-rights").checked) {
    setResult("bsage-result", "⛔ Tick the rights box first — you must have the rights to " +
      "process this audio (it gets uploaded to beatsage.com).", "bad");
    return;
  }
  const file = $("bsage-audio").files[0];
  if (!file) {
    setResult("bsage-result", "Pick an audio file first (.wav/.ogg/.flac/.mp3/.aiff/.egg).", "bad");
    return;
  }
  const diffs = bsageCheckedValues("bsage-diff");
  if (!diffs.length) {
    setResult("bsage-result", "Pick at least one difficulty.", "bad");
    return;
  }
  if (state.mode !== "local-backend") {
    setResult("bsage-result", "Command-builder mode can't upload — use the guided flow below.", "bad");
    return;
  }
  setResult("bsage-result", "", "");
  const btn = $("btn-bsage-generate");
  btn.disabled = true;
  btn.textContent = "Generating… (beatsage.com)";
  log.classList.remove("hidden");
  log.textContent = "";
  const fd = new FormData();
  fd.append("audio", file);
  fd.append("title", $("bsage-title").value.trim() || file.name.replace(/\.[^.]+$/, ""));
  fd.append("artist", $("bsage-artist").value.trim() || "Unknown Artist");
  fd.append("difficulties", diffs.join(","));
  fd.append("modes", bsageCheckedValues("bsage-mode").join(",") || "Standard");
  fd.append("events", bsageCheckedValues("bsage-event").join(","));
  fd.append("environment", $("bsage-env").value);
  fd.append("system_tag", $("bsage-system").value || "v2");
  try {
    await api("/api/jobs/beatsage", { method: "POST", body: fd });
    pollBeatsageJob(0);
  } catch (e) {
    setResult("bsage-result", "❌ " + e.message + " — the guided flow below always works.", "bad");
    $("bsage-guide-details").open = true;
    btn.disabled = false;
    btn.textContent = "Generate map with Beat Sage";
  }
}

function pollBeatsageJob(after) {
  api(`/api/jobs/lines?after=${after}`)
    .then(j => {
      const log = $("bsage-log");
      if (j.lines && j.lines.length) {
        log.textContent += j.lines.join("\n") + "\n";
        log.scrollTop = log.scrollHeight;
      }
      if (j.running) {
        state.bsageTimer = setTimeout(() => pollBeatsageJob(j.index || after), 1200);
      } else {
        const btn = $("btn-bsage-generate");
        btn.disabled = false;
        btn.textContent = "Generate map with Beat Sage";
        if (j.job && j.job.exit_code === 0) {
          setResult("bsage-result", "✅ Beat Sage done — the map is staged below. Pick it in " +
            "the staged list, then Deploy as usual.", "ok");
        } else {
          setResult("bsage-result", `❌ Generation failed (exit ${j.job ? j.job.exit_code : "?"}). ` +
            "The guided flow below always works — generate on beatsage.com yourself " +
            "and drop the zip in section 3.", "bad");
          $("bsage-guide-details").open = true;
        }
        loadStaged();
      }
    })
    .catch(() => { state.bsageTimer = setTimeout(() => pollBeatsageJob(after), 2000); });
}

async function validateLocalDir() {
  const path = $("local-song-path").value.trim();
  if (!path) {
    setResult("local-validate-result", "Type or paste the folder path that contains Info.dat.", "bad");
    return;
  }
  if (state.mode !== "local-backend") {
    setResult("local-validate-result", "Command-builder mode: pass the folder to the pipeline " +
      "with --song-dir <folder>.", "bad");
    return;
  }
  setResult("local-validate-result", "Validating…", "");
  try {
    const j = await api("/api/songs/validate-dir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    if (j.ok) {
      const v = j.validation;
      const nps = Object.entries(v.charts || {})
        .map(([d, c]) => `${d} ${c.nps}/s`).join(" · ") || "?";
      setResult("local-validate-result",
        `✅ Valid ${v.schema || "map"}: "${v.name || "?"}" by ${v.artist || "?"} — ` +
        `BPM ${v.bpm ?? "?"}${v.duration_s ? ` · ~${v.duration_s}s` : ""}` +
        `${v.environment ? ` · env ${v.environment}` : ""} — staged ✓\n` +
        `notes/sec: ${nps}`, "ok");
      if (v.warnings && v.warnings.length)
        $("local-validate-result").textContent += "\n⚠ " + v.warnings.join("\n⚠ ");
      loadStaged();
    } else {
      setResult("local-validate-result", "❌ Problems found:\n• " + j.errors.join("\n• "), "bad");
    }
  } catch (e) {
    setResult("local-validate-result", "❌ " + e.message, "bad");
  }
}

async function useTestSong() {
  // Fetch the rights-clean synth theme on demand and attach it to the form —
  // one click and the Generate flow is ready (no audio hunting). The song is
  // 100% mathematical synthesis: deterministic, and the 48s default is
  // byte-identical to the already-deployed 'BSD Deluxe Theme (An Original)'.
  // The button itself tells the story (disable + relabel) — the click must be
  // OBVIOUSLY doing something (the Exp 283e user report: "does nothing that
  // I can notice").
  const btn = $("btn-bsage-testsong");
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = "⏳ Synthesizing the test song…";
  setResult("bsage-result", "Synthesizing the original test song (pure math, " +
    "deterministic)…", "");
  try {
    const r = await fetch("/api/songs/test-song?seconds=48");
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    const blob = await r.blob();
    const file = new File([blob], "bsd_deluxe_theme_48s.wav", { type: "audio/wav" });
    const dt = new DataTransfer();
    dt.items.add(file);
    $("bsage-audio").files = dt.files;   // attach programmatically
    if (!$("bsage-title").value) $("bsage-title").value = "BSD Deluxe Theme (An Original)";
    if (!$("bsage-artist").value) $("bsage-artist").value = "OrBeats Synth";
    btn.textContent = "✓ Test song attached — now press Generate";
    setResult("bsage-result", "✅ Test song attached to the form (48s, rights-clean — " +
      "synthesized from scratch, the same song every time). Press Generate to " +
      "send it to Beat Sage.", "ok");
  } catch (e) {
    // DataTransfer/file-input restrictions or fetch failure → plain download
    btn.textContent = original;
    setResult("bsage-result", "Starting a plain download instead — pick the " +
      `downloaded .wav as the audio file. (${esc(e.message)})`, "warn");
    window.location = "/api/songs/test-song?seconds=48";
    return;
  }
  setTimeout(() => { btn.disabled = false; btn.textContent = original; }, 10000);
}

async function stageZipFile(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".zip")) {
    setResult("zip-result", "That's not a .zip — drop the map zip itself (the downloaded file).", "bad");
    return;
  }
  if (state.mode !== "local-backend") {
    setResult("zip-result", "Command-builder mode: extract the zip and pass its folder " +
      "with --song-dir <folder>.", "bad");
    return;
  }
  setResult("zip-result", `Extracting + validating ${file.name}…`, "");
  const fd = new FormData();
  fd.append("zip_file", file);
  try {
    const j = await api("/api/songs/stage-zip", { method: "POST", body: fd });
    const s = j.staged;
    setResult("zip-result", `✅ Staged "${s.name || file.name}" by ${s.artist || "?"} ` +
      `(${s.schema || "map"}, ${(s.difficulties || []).join("/") || "?"}) — pick it below.`, "ok");
    loadStaged();
  } catch (e) {
    setResult("zip-result", "❌ " + e.message, "bad");
  }
}

function wireZipDrop() {
  const zone = $("zip-drop");
  ["dragenter", "dragover"].forEach(ev =>
    zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach(ev =>
    zone.addEventListener(ev, e => { e.preventDefault(); zone.classList.remove("dragover"); }));
  zone.addEventListener("drop", e => {
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    stageZipFile(file);
  });
  $("zip-file-input").addEventListener("change", e => stageZipFile(e.target.files[0]));
  zone.querySelector("label").addEventListener("click", () => $("zip-file-input").click());
}

async function loadStaged() {
  if (state.mode !== "local-backend") return;
  try {
    const j = await api("/api/songs/staged");
    state.staged = j.songs || [];
    renderStagedList();
  } catch { /* staged list is optional sugar */ }
}

function npsBadge(diff, c) {
  if (!c) return "";
  const cls = c.nps < 0.3 ? "miss" : c.nps < 0.75 ? "warn" : "ok";
  const sparse = c.nps < 0.75 ? " ⚠" : "";
  return `<span class="badge ${cls}" title="${diff}: ${c.notes} notes over ${c.span_s}s (peak ${c.peak_nps}/s in any 10s window)${c.bombs ? ` · ${c.bombs} bombs` : ""}${c.obstacles ? ` · ${c.obstacles} obstacles` : ""}">${diff} ${c.nps}/s${sparse}</span>`;
}

function stagedStatsHtml(s) {
  const charts = s.charts || {};
  const rows = Object.entries(charts).map(([d, c]) =>
    `<tr><td><b>${esc(d)}</b></td><td>${c.notes} notes</td><td>${c.nps}/s avg</td>
     <td>${c.peak_nps}/s peak</td><td>${c.bombs} bombs · ${c.obstacles} walls</td>
     <td>${c.events} light events</td><td>${c.span_s}s</td></tr>`).join("");
  const gen = s.generation && s.system_tag ? s.generation : (s.generation || {});
  const genBits = Object.keys(gen).length ?
    ` · generated with system ${esc(gen.system_tag || "?")}, env ${esc(gen.environment || "?")}` +
    (gen.events && gen.events.length ? `, events ${esc(gen.events.join(","))}` : "") : "";
  const modeBits = Object.entries(s.mode_notes || {}).map(([m, n]) =>
    `${esc(m)}: ${n} notes`).join(" · ");
  return `<details class="staged-stats"><summary>chart statistics</summary>
    ${rows ? `<table class="stats">${rows}</table>` : `<span class="muted">no chart stats parsed</span>`}
    <div class="muted">duration ≈ ${s.duration_s || "?"}s · environment “${esc(s.environment || "(none)")}”${s.cover_art ? ` · cover art ${esc(s.cover_art)}` : ""}${genBits}</div>
    ${modeBits ? `<div class="muted">mode variants — ${modeBits}</div>` : ""}
    ${(s.warnings || []).map(w => `<div class="result warn">⚠ ${esc(w)}</div>`).join("")}
  </details>`;
}

function renderStagedList() {
  const el = $("staged-list");
  const songs = state.staged || [];
  if (!songs.length) {
    el.className = "muted";
    el.textContent = "None yet — stage one above (Beat Sage, a zip, or a folder).";
    return;
  }
  el.className = "";
  el.innerHTML = songs.map(s =>
    `<div class="song staged-row">
       <div class="meta">
         <b>${esc(s.name || "(unnamed)")}</b>
         <span class="muted">by ${esc(s.artist || "?")} · ${esc(s.schema || "map")} · BPM ${s.bpm ?? "?"}
         ${s.source === "beatsage" ? " · <b>Beat Sage</b>" : s.source === "zip" ? " · zip" : ""}</span>
         <div class="badges">${Object.entries(s.charts || {}).map(([d, c]) => npsBadge(d, c)).join("")}</div>
       </div>
       ${stagedStatsHtml(s)}
       <div class="badges">
         <button class="pick" data-stage="${esc(s.id)}">Deploy →</button>
         <button class="clear-slot" data-unstage="${esc(s.id)}" title="Remove from the staged list">✕</button>
       </div>
     </div>`).join("");
  el.querySelectorAll("button[data-stage]").forEach(b =>
    b.addEventListener("click", () => {
      const s = state.staged.find(x => x.id === b.dataset.stage);
      if (s) pickStagedSong(s);
    }));
  el.querySelectorAll("button[data-unstage]").forEach(b =>
    b.addEventListener("click", async () => {
      try {
        await api(`/api/songs/staged/${encodeURIComponent(b.dataset.unstage)}`, { method: "DELETE" });
        loadStaged();
      } catch (e) { alert("Couldn't remove: " + e.message); }
    }));
}

function pickStagedSong(s) {
  state.pickedSong = {
    source: "local", dir: s.dir, id: s.id,
    name: s.name || "(unnamed)", artist: s.artist,
    bpm: s.bpm, schema: s.schema, difficulties: s.difficulties || [],
  };
  renderPickedSong();
  updateDeployPreview();
  showPage("deployPage");
}

// ---------------------------------------------------------------- deploy
function loadCatalogIntoPicker() {
  $("deploy-pack").innerHTML = "<option value='custom'>Custom Songs</option>";
  $("deploy-slot").innerHTML = "<option value='additive'>New independent entry (no replacement)</option>";
  $("deploy-pack").disabled = true; $("deploy-slot").disabled = true;
  updateDeployPreview();
}

function currentOpts() {
  return {
    map_id: state.pickedSong && state.pickedSong.source !== "local" ? state.pickedSong.id : "",
    song_dir: state.pickedSong && state.pickedSong.source === "local" ? state.pickedSong.dir : "",
    target: "",
    additive: true,
    audio: $("opt-audio").value,
    pad_fsb5: $("opt-pad").checked,
    convert_to_v3: $("opt-v3").checked,
    deploy_full: true,
    skip_plugin: $("opt-skip-plugin").checked,
    song_name: $("opt-songname").value.trim(),
    artist: $("opt-artist").value.trim(),
  };
}

async function updateDeployPreview() {
  $("deploy-slot-info").textContent = "Adds to Custom Songs; original songs and existing custom entries are preserved.";
  $("deploy-slot-label").textContent = "Custom Songs";
  const o = currentOpts();
  // The picked-song info line (M13): shows WHAT is being deployed — a
  // BeatSaver map or a staged local folder — right above the Deploy button.
  const pickedInfo = $("deploy-picked-info");
  if (state.pickedSong && state.pickedSong.source === "local") {
    pickedInfo.innerHTML = `Deploying staged folder: <b>${esc(state.pickedSong.name)}</b>` +
      ` <span class="muted">(${esc(state.pickedSong.schema || "map")}, ` +
      `${(state.pickedSong.difficulties || []).join("/") || "?"})</span>`;
  } else if (state.pickedSong) {
    pickedInfo.innerHTML = `Deploying BeatSaver map: <b>${esc(state.pickedSong.name)}</b>` +
      ` <span class="muted">(map ID <code>${esc(state.pickedSong.id)}</code>)</span>`;
  } else {
    pickedInfo.textContent = "";
  }
  if (!o.map_id && !o.song_dir) {
    $("deploy-command").textContent = state.pickedSong
      ? "→ pick a target slot to preview the command"
      : "→ pick a song first (Pick a Song tab — search, Beat Sage, or a local folder)";
    return;
  }
  if (state.mode === "pages") {
    // Command-builder mode: build the exact pipeline argv LOCALLY (no
    // backend exists). Mirrors adapters/deploy.py's build_argv order 1:1 —
    // the local command path is validated by tests; keep both in sync.
    const argv = ["--additive-install", ...(o.song_dir
      ? ["--song-dir", o.song_dir] : ["--download-beat-saver-song", o.map_id]),
      "--config", "beat_saber_deluxe/ps4_config.json"];
    $("deploy-command").textContent =
      "→ python3 beat_saber_deluxe/tools/full_custom_song_pipeline.py " + argv.join(" ") +
      "\n⚠ command-builder mode: copy this command and run it on the machine with Python/FFmpeg and PS4 FTP access";
    return;
  }
  try {
    const j = await api(`/api/command-preview?map_id=${encodeURIComponent(o.map_id)}` +
      `&target=${encodeURIComponent(o.target)}&audio=${o.audio}` +
      `&pad_fsb5=${o.pad_fsb5}&convert_to_v3=${o.convert_to_v3}` +
      `&skip_plugin=${o.skip_plugin}` +
      `&song_dir=${encodeURIComponent(o.song_dir)}`);
    $("deploy-command").textContent = "→ " + j.command;
  } catch (e) { $("deploy-command").textContent = "→ " + e.message; }
}


function copyDeployCommand() {
  const cmd = $("deploy-command").textContent
    .replace(/^→ /, "").split("\n⚠")[0].trim();
  if (!cmd || cmd.startsWith("→")) {
    setResult("deploy-status", "Pick a song first.", "bad");
    return;
  }
  const done = () => setResult("deploy-status",
    "Command copied! Run it on the machine with Python/FFmpeg and PS4 FTP access " +
    "(from the release root or a repo checkout).", "ok");
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(cmd).then(done, () => fallbackCopy(cmd, done));
  } else {
    fallbackCopy(cmd, done);
  }
}

function fallbackCopy(text, done) {
  const ta = document.createElement("textarea");
  ta.value = text;
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand("copy"); done(); }
  catch { setResult("deploy-status", "Copy failed — select the command above manually.", "bad"); }
  document.body.removeChild(ta);
}

async function deploy() {
  const o = currentOpts();
  if (!o.map_id && !o.song_dir) {
    setResult("deploy-status", "Pick a song first.", "bad");
    return;
  }
  if (state.mode === "pages") {
    // Command-builder mode: cannot run anything (no backend, no PS4 access
    // from a hosted page) — offer the copyable command instead.
    copyDeployCommand();
    return;
  }
  const label = $("deploy-slot-label").textContent;
  const what = state.pickedSong.source === "local"
    ? `your local folder "${state.pickedSong.name}"`
    : `"${state.pickedSong.name}" (downloaded from BeatSaver)`;
  if (!confirm(
    `Add ${what} to Custom Songs?\n\n` +
    `Fully CLOSE Beat Saber and keep GoldHEN FTP enabled. This converts and installs ` +
    `an independent entry; original songs and existing custom maps are preserved. ` +
    `The library appears on the next game launch. No live refresh.`)) return;

  setResult("deploy-status", "", "");
  $("deploy-log").classList.remove("hidden");
  $("deploy-log").textContent = "";
  $("deploy-progress").scrollIntoView({ behavior: "smooth", block: "start" });
  const deployBtn = $("btn-deploy");
  deployBtn.disabled = true;
  deployBtn.innerHTML = '<span class="spinner spinning"></span> Deploying…';
  $("btn-deploy-cancel").classList.remove("hidden");
  setDeployProgress(true, "Deploying", `${state.pickedSong.name} → ${label}`);
  try {
    const j = await api("/api/jobs/deploy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(o),
    });
    pollLog(0);
  } catch (e) {
    setResult("deploy-status", "❌ " + e.message, "bad");
    deployBtn.disabled = false;
    deployBtn.innerHTML = "Deploy to PS4";
    $("btn-deploy-cancel").classList.add("hidden");
    setDeployProgress(false);
  }
}

function setDeployProgress(show, status, label) {
  const row = $("deploy-progress");
  if (!row) return;
  row.hidden = !show;
  row.classList.toggle("hidden", !show);
  if (show) {
    $("deploy-progress-status").textContent = status || "Working…";
    $("deploy-progress-label").textContent = label || "";
  }
}

let pollIndex = 0;
function pollLog() {
  api(`/api/jobs/lines?after=${pollIndex}`)
    .then(j => {
      if (j.lines && j.lines.length) {
        const logEl = $("deploy-log");
        logEl.textContent += j.lines.join("\n") + "\n";
        logEl.scrollTop = logEl.scrollHeight;
      }
      pollIndex = j.index || pollIndex;
      if (j.running) {
        state.pollTimer = setTimeout(pollLog, 900);
      } else if (j.job) {
        finishJob(j.job);
      }
    })
    .catch(() => { state.pollTimer = setTimeout(pollLog, 1500); });
}

function finishJob(job) {
  $("btn-deploy").disabled = false;
  $("btn-deploy").innerHTML = "Deploy to PS4";
  $("btn-deploy-cancel").classList.add("hidden");
  setDeployProgress(false);
  if (job.cancelled) {
    setResult("deploy-status", "⛔ Cancelled. The PS4 may hold a partial deploy — " +
      "run Verify, or re-deploy to complete it.", "warn");
    return;
  }
  if (job.exit_code === 0) {
    setResult("deploy-status", "✅ Deploy PASSED (post-deploy validation green). " +
      "Launch the game and check your song!", "ok");
    $("btn-verify").classList.remove("hidden");
  } else {
    setResult("deploy-status", `❌ Deploy FAILED (exit ${job.exit_code}). ` +
      "Read the log above — the pipeline prints exactly what went wrong.", "bad");
  }
}

async function cancelJob() {
  try { await api("/api/jobs/cancel", { method: "POST" }); }
  catch (e) { /* runner gone — poll loop will notice */ }
}

// ---------------------------------------------------------------- manage + loadout
let loadoutData = null;   // last /api/loadout payload (re-render on filter change)

async function fetchLoadout() {
  const errs = [];
  try {
    loadoutData = await api("/api/loadout");
  } catch (e) {
    loadoutData = null;
    errs.push(e.message);
  }
  return loadoutData;
}

function renderReadErrors(status, el) {
  if (!status) { el.innerHTML = ""; return; }
  const bits = [];
  if (status.redirectsReadError)
    bits.push(`<span class="result bad">⚠ Couldn't read redirects.json from the PS4
      (${esc(status.redirectsReadError)}). "Served" status unknown — check the
      connection and refresh.</span>`);
  if (status.afrReadError)
    bits.push(`<span class="result warn">⚠ Couldn't list the AFR folder on the PS4
      (${esc(status.afrReadError)}). Stale-bundle detection unavailable.</span>`);
  if (status.metadataReadError)
    bits.push(`<span class="result warn">⚠ Couldn't read song_metadata.json from the PS4
      (${esc(status.metadataReadError)}). Custom names unavailable — showing slots only.</span>`);
  el.innerHTML = bits.join(" ");
}

function customCell(row) {
  if (row.customDeployed) {
    const name = row.customName || "(name unavailable)";
    const artist = row.customArtist || "";
    return `<td><span class="badge ok">custom</span></td>
            <td><b>${esc(name)}</b>${artist ? ` <span class="muted">/ ${esc(artist)}</span>` : ""}</td>`;
  }
  if (row.staleBundle) {
    return `<td><span class="badge miss" title="Bundle file on PS4 but no redirect — uploaded by an earlier deploy, not currently served">stale</span></td>
            <td class="muted">bundle on PS4, not served (no redirect)</td>`;
  }
  if (row.customName) {
    return `<td><span class="badge miss" title="Name/artist relabeled in the UI but no custom bundle is served over this slot">label only</span></td>
            <td><b>${esc(row.customName)}</b>${row.customArtist ? ` <span class="muted">/ ${esc(row.customArtist)}</span>` : ""}</td>`;
  }
  return `<td class="muted">—</td><td class="muted">stock</td>`;
}

function clearButton(row, refreshFn) {
  if (!row.customDeployed && !row.staleBundle && !row.customName) return "<td></td>";
  return `<td><button class="clear-slot danger" data-slot="${esc(row.songID)}"
      data-stock="${esc(row.songName)}">Clear</button></td>`;
}

function wireClearButtons(container, refreshFn, panelId) {
  container.querySelectorAll("button.clear-slot").forEach(b =>
    b.addEventListener("click", async () => {
      const slot = b.dataset.slot, stock = b.dataset.stock;
      if (!confirm(
        `Revert "${stock}" (${slot}) back to stock?\n\n` +
        `This removes ONLY this song's custom bundle, redirect, and metadata — ` +
        `the other songs in its pack and every other pack stay untouched.`))
        return;
      b.disabled = true;
      b.textContent = "clearing…";
      try {
        const j = await api("/api/jobs/clear-target", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ slot }),
        });
        if (panelId) {
          showJobPanel(panelId, { label: `clear ${stock} (${slot})`, command: j.command });
          await runJobWithPanel(panelId, j, { doneLabel: `${stock} reverted to stock` });
          await refreshFn();
        } else {
          // legacy inline poll (no panel on this page)
          pollIndex = 0;
          const poll = async () => {
            try {
              const j2 = await api(`/api/jobs/lines?after=${pollIndex}`);
              pollIndex = j2.index || pollIndex;
              if (j2.running) { setTimeout(poll, 900); return; }
              if (j2.job && j2.job.exit_code === 0) { await refreshFn(); }
              else { b.disabled = false; b.textContent = "Clear";
                     alert(`Clear failed (exit ${j2.job ? j2.job.exit_code : "?"}) — see the job output.`); }
            } catch { setTimeout(poll, 1500); }
          };
          poll();
        }
      } catch (e) {
        b.disabled = false; b.textContent = "Clear";
        alert("Couldn't start the clear job: " + e.message);
      }
      b.disabled = false; b.textContent = "Clear";
    }));
}

async function manageRefresh() {
  const packSel = $("manage-pack");
  const body = $("manage-table").querySelector("tbody");
  body.innerHTML = "<tr><td colspan='6' class='muted'>Reading PS4 state…</td></tr>";
  await fetchLoadout();
  if (!loadoutData) {
    body.innerHTML = `<tr><td colspan='6' class='result bad'>Couldn't load: ${esc("see errors above")}</td></tr>`;
    return;
  }
  renderReadErrors(loadoutData.readStatus, $("manage-read-errors"));
  const pack = packSel.value;
  const album = loadoutData.packs.find(p => p.pack === pack);
  const named = album ? album.songs.filter(s => s.customName).length : 0;
  $("manage-pack-title").textContent = album
    ? `${album.pack} — ${album.deployedCount} served / ${named} labeled / ${album.songs.length} songs`
    : "Songs";
  if (!album) { body.innerHTML = ""; return; }
  body.innerHTML = album.songs.map(row =>
    `<tr class="${row.customDeployed ? "has-custom" : ""}">
       <td><code>${esc(row.songID)}</code></td>
       <td>${esc(row.songName)}</td>
       <td>${esc(row.songAuthorName)}</td>
       ${customCell(row)}
       ${clearButton(row)}
     </tr>`).join("");
  wireClearButtons(body, manageRefresh, "manage-job-panel");
}

async function loadManagePacks() {
  const packSel = $("manage-pack");
  try {
    const j = await api("/api/loadout/packs");
    packSel.innerHTML = "";
    j.packs.forEach(p => {
      const opt = document.createElement("option");
      opt.value = p;
      opt.textContent = `${p} (${j.songCounts[p]} songs)`;
      packSel.appendChild(opt);
    });
  } catch (e) {
    packSel.innerHTML = `<option value=''>couldn't load packs: ${esc(e.message)}</option>`;
    return;
  }
  packSel.onchange = manageRefresh;
  // default to the first pack with anything custom (served or labeled)
  await fetchLoadout();
  if (loadoutData) {
    const withCustoms = loadoutData.packs.find(
      p => p.deployedCount > 0 || p.songs.some(s => s.customName || s.staleBundle));
    if (withCustoms) packSel.value = withCustoms.pack;
  }
  manageRefresh();
}

function renderLoadoutTables() {
  const host = $("loadout-tables");
  if (!loadoutData) { host.innerHTML = "<p class='result bad'>No data — refresh.</p>"; return; }
  renderReadErrors(loadoutData.readStatus, $("loadout-read-errors"));
  const onlyCustom = $("loadout-only-custom").checked;
  const packs = onlyCustom
    ? loadoutData.packs.filter(
        p => p.deployedCount > 0 || p.songs.some(s => s.customName || s.staleBundle))
    : loadoutData.packs;
  $("loadout-summary").textContent =
    `${loadoutData.redirectedSlotCount} custom songs served · ` +
    `${loadoutData.staleBundleCount} stale bundles (uploaded, not served) · ` +
    `${loadoutData.customNameCount} metadata entries · ${loadoutData.packs.length} packs total` +
    (loadoutData.unmatchedMetadata.length
      ? ` · ${loadoutData.unmatchedMetadata.length} metadata entries matched no slot` : "");
  $("loadout-generated").textContent = new Date().toLocaleString();

  host.innerHTML = packs.map(album => `
    <div class="card loadout-pack">
      <h3>${esc(album.pack)} <span class="muted">(${album.deployedCount} served /
        ${album.songs.filter(s => s.customName).length} labeled / ${album.songs.length} songs)</span></h3>
      <table class="loadout">
        <thead><tr><th>Slot</th><th>Stock song</th><th>Stock artist</th>
          <th>Custom?</th><th>Custom song / artist</th><th></th></tr></thead>
        <tbody>
          ${album.songs.map(row =>
            `<tr class="${row.customDeployed ? "has-custom" : ""}">
               <td><code>${esc(row.songID)}</code></td>
               <td>${esc(row.songName)}</td>
               <td>${esc(row.songAuthorName)}</td>
               ${customCell(row)}
               ${clearButton(row)}
             </tr>`).join("")}
        </tbody>
      </table>
    </div>`).join("")
    || "<p class='muted'>No packs match the current filter.</p>";
  wireClearButtons(host, async () => { await fetchLoadout(); renderLoadoutTables(); }, "loadout-job-panel");
}

async function loadoutRefresh() {
  const btn = $("btn-loadout-refresh");
  btn.disabled = true; btn.textContent = "Reading PS4…";
  await fetchLoadout();
  renderLoadoutTables();
  btn.disabled = false; btn.textContent = "Refresh from PS4";
}

// ---------------------------------------------------------------- feature flags
const FLAG_ORDER = ["enable_plugin", "enable_custom_song_replacements",
                     "enable_song_metadata_modification", "enable_beatmap_mode_mapping",
                     "enable_in_game_plugin_toggle", "enable_game_data_extractor",
                     "enable_additive_song_packs"];
// NOTE: the pipeline's canonical key is the PLURAL enable_custom_song_replacements.
let flagsDirty = false;

// Simulated PS4 launch toast — mirrors the plugin's exact format
// (main.cpp module_start): "OrBeats vX\nBy Wkrotik"
// — or "disabled … (official songs only)" when the kill switch is off.
const TOAST_VERSION = "v0.8077";

function updateToastSim() {
  const checks = $("flags-list").querySelectorAll("input[type=checkbox]");
  if (!checks.length) return;
  const state = {};
  checks.forEach(cb => { state[cb.dataset.flag] = cb.checked; });
  const on = state["enable_plugin"];
  $("toast-title").textContent = `OrBeats ${TOAST_VERSION}${on ? "" : " — disabled"}`;
  $("toast-status").textContent = on ? "" : "(official songs only)";
  $("toast-status").hidden = !!on;
  $("toast-note").textContent = on
    ? "With these toggles, the next boot shows this toast and the features above are active."
    : "Kill switch OFF: the toast reads (official songs only) and the game is 100% stock — your deployments stay on the PS4 untouched.";
}

async function flagsRefresh() {
  const host = $("flags-list");
  host.innerHTML = "<p class='muted'>Reading flags from the PS4…</p>";
  try {
    const j = await api("/api/flags");
    if (!j.ok) {
      host.innerHTML = `<span class="result bad">Couldn't read flags from the PS4
        (${esc(j.error)}). Check the connection, then refresh.</span>`;
      $("btn-flags-apply").disabled = true;
      return;
    }
    host.innerHTML = j.flags
      .sort((a, b) => FLAG_ORDER.indexOf(a.name) - FLAG_ORDER.indexOf(b.name))
      .map(f => `
        <div class="flag-row">
          <label class="chk">
            <input type="checkbox" data-flag="${esc(f.name)}" ${f.value ? "checked" : ""}
                   ${f.name === "enable_plugin" ? "data-killswitch='1'" : ""}>
            <b>${esc(f.name)}</b> ${f.pending ? `<span class="badge miss">pending → ${f.pendingValue ? "ON" : "OFF"}</span>` : ""}
          </label>
          <div class="muted flag-desc">${esc(f.description)}</div>
        </div>`).join("");
    host.querySelectorAll("input[type=checkbox]").forEach(cb =>
      cb.addEventListener("change", () => {
        flagsDirty = true;
        $("btn-flags-apply").disabled = false;
        $("flags-apply-status").textContent = "";
        if (cb.dataset.killswitch && !cb.checked) {
          $("flags-apply-status").innerHTML =
            "<span class='result warn'>⚠ Kill switch going OFF — the game will play 100% official songs next boot.</span>";
        }
        updateToastSim();
      }));
    flagsDirty = false;
    $("btn-flags-apply").disabled = true;
    $("flags-read-error").textContent = "";
    updateToastSim();
  } catch (e) {
    host.innerHTML = `<span class="result bad">${esc(e.message)}</span>`;
  }
}

async function flagsApply() {
  const wanted = {};
  $("flags-list").querySelectorAll("input[type=checkbox]").forEach(cb => {
    wanted[cb.dataset.flag] = cb.checked;
  });
  const turningOff = wanted["enable_plugin"] === false;
  const msg = turningOff
    ? "Turn the ENTIRE plugin OFF?\n\nNext boot plays 100% official songs (your customs stay deployed and come back the moment you re-enable)."
    : "Apply this flag loadout to the PS4?\n\nTakes effect on the next game boot.";
  if (!confirm(msg)) return;
  const applyBtn = $("btn-flags-apply");
  applyBtn.disabled = true;
  applyBtn.innerHTML = '<span class="spinner spinning"></span> Applying…';
  $("flags-apply-status").textContent = "";
  try {
    const j = await api("/api/jobs/flags-apply", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ flags: wanted }),
    });
    if (j.job_id === null) {
      applyBtn.innerHTML = "Apply to PS4";
      $("flags-apply-status").innerHTML =
        `<span class="result ok">✅ ${esc(j.message)}</span>`;
      flagsRefresh();
      return;
    }
    flagsDirty = false;
    pollJobInto("flags-log", "flags-apply-status", () => {
      applyBtn.innerHTML = "Apply to PS4";
      flagsRefresh();
    });
  } catch (e) {
    applyBtn.disabled = false;
    applyBtn.innerHTML = "Apply to PS4";
    $("flags-apply-status").innerHTML = `<span class="result bad">❌ ${esc(e.message)}</span>`;
  }
}

// ---------------------------------------------------------------- job panel
// The shared live-output surface: every command the app launches (deploy,
// verify, flags-apply, backup, restore, clear) renders here — spinner +
// status + the exact command + a live console. One job at a time (the
// runner enforces it; the UI makes it visible).
function showJobPanel(panelId, { label, command }) {
  const panel = $(panelId);
  panel.classList.remove("hidden");
  $(panelId + "-status").textContent = "Working…";
  $(panelId + "-label").textContent = label || "";
  $(panelId + "-spinner").classList.add("spinning");
  $(panelId + "-command").textContent = command ? "→ " + command : "";
  $(panelId + "-log").textContent = "";
  // The panels sit at the TOP of their pages (above long tables) so the
  // spinner + live output are always in view while a job runs (Exp 253:
  // they used to live below everything and the user saw nothing).
  window.scrollTo({ top: 0, behavior: "smooth" });
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function finishJobPanel(panelId, job) {
  const spinner = $(panelId + "-spinner");
  spinner.classList.remove("spinning");
  const status = $(panelId + "-status");
  if (job.cancelled) {
    status.textContent = "⛔ Cancelled — the PS4 may hold partial state; verify or re-run.";
    status.className = "job-status warn";
  } else if (job.exit_code === 0) {
    status.textContent = "✅ Done";
    status.className = "job-status ok";
  } else {
    status.textContent = `❌ FAILED (exit ${job.exit_code}) — read the output above`;
    status.className = "job-status bad";
  }
}

function runJobWithPanel(panelId, startResponse, { doneLabel } = {}) {
  // Poll the runner's shared job lines into the panel's console.
  // Returns a Promise that resolves when the job ENDS — callers awaiting it
  // (clear → refresh) act at the right moment (Exp 253: the fire-and-forget
  // version resolved immediately and the table refreshed mid-job).
  return new Promise((resolve) => {
    let idx = 0;
    const logEl = $(panelId + "-log");
    const poll = async () => {
      try {
        const j = await api(`/api/jobs/lines?after=${idx}`);
        if (j.lines && j.lines.length) {
          logEl.textContent += j.lines.join("\n") + "\n";
          logEl.scrollTop = logEl.scrollHeight;
        }
        idx = j.index || idx;
        if (j.running) { setTimeout(poll, 900); return; }
        if (j.job) {
          finishJobPanel(panelId, j.job);
          if (doneLabel && j.job.exit_code === 0) {
            $(panelId + "-label").textContent = doneLabel;
          }
          resolve(j.job);
        } else {
          resolve(null);
        }
      } catch { setTimeout(poll, 1500); }
    };
    poll();
  });
}

// shared job poller for legacy call sites (flags page)
function pollJobInto(logId, statusId, afterFn) {
  let idx = 0;
  const poll = async () => {
    try {
      const j = await api(`/api/jobs/lines?after=${idx}`);
      if (j.lines && j.lines.length) {
        const el = $(logId);
        el.textContent += j.lines.join("\n") + "\n";
        el.classList.remove("hidden");
      }
      idx = j.index || idx;
      if (j.running) { setTimeout(poll, 900); return; }
      if (j.job) {
        const s = $(statusId);
        if (j.job.cancelled) {
          s.innerHTML = "<span class='result warn'>⛔ Job cancelled — the PS4 may hold partial state; run a backup or verify.</span>";
        } else if (j.job.exit_code === 0) {
          s.innerHTML = "<span class='result ok'>✅ Done.</span>";
        } else {
          s.innerHTML = `<span class='result bad'>❌ Job FAILED (exit ${j.job.exit_code}) — read the log above.</span>`;
        }
        $("btn-job-cancel") && $("btn-job-cancel").classList.add("hidden");
        afterFn && afterFn();
      }
    } catch { setTimeout(poll, 1500); }
  };
  poll();
}

// ---------------------------------------------------------------- backup / restore
async function backupRefresh() {
  const body = $("backup-table").querySelector("tbody");
  body.innerHTML = "<tr><td colspan='4' class='muted'>Listing backups…</td></tr>";
  try {
    const j = await api("/api/backup/list");
    $("backup-dir-display").textContent = j.backup_dir;
    if (!j.backups.length) {
      body.innerHTML = `<tr><td colspan='4' class='muted'>No backups yet in
        <code>${esc(j.backup_dir)}</code> — make one before experimenting.</td></tr>`;
      return;
    }
    body.innerHTML = j.backups.map(b => `
      <tr>
        <td><code>${esc(b.name)}</code></td>
        <td>${(b.size / 1024).toFixed(0)} KB</td>
        <td>${new Date(b.mtime * 1000).toLocaleString()}</td>
        <td><button class="restore-backup" data-name="${esc(b.name)}">Restore</button></td>
      </tr>`).join("");
    body.querySelectorAll("button.restore-backup").forEach(btn =>
      btn.addEventListener("click", () => backupRestore(btn.dataset.name)));
  } catch (e) {
    body.innerHTML = `<tr><td colspan='4' class='result bad'>${esc(e.message)}</td></tr>`;
  }
}

// backups-folder browser (server lists dirs; the picker is folder-only)
let browsePath = null;

async function browseLoad(path) {
  try {
    const j = await api(`/api/backup/browse?path=${encodeURIComponent(path || "")}`);
    browsePath = j.path;
    $("browse-crumbs").textContent = j.path;
    $("browse-path-input").value = j.path;
    $("browse-list").innerHTML = j.dirs.length
      ? j.dirs.map(d =>
          `<div class="browse-entry" data-path="${esc(d.path)}">📁 ${esc(d.name)}</div>`).join("")
      : "<p class='muted' style='padding:.4rem'>No subfolders here.</p>";
    $("browse-list").querySelectorAll(".browse-entry").forEach(el =>
      el.addEventListener("click", () => browseLoad(el.dataset.path)));
    $("btn-browse-up").disabled = !j.parent;
    $("btn-browse-up").onclick = () => j.parent && browseLoad(j.parent);
  } catch (e) {
    $("browse-crumbs").textContent = "couldn't browse: " + e.message;
  }
}

async function backupChooseFolder(path) {
  try {
    const j = await api("/api/backup/dir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    });
    $("backup-browser").classList.add("hidden");
    $("backup-dir-display").textContent = j.backup_dir;
    backupRefresh();
  } catch (e) {
    alert("Couldn't set the backups folder: " + e.message);
  }
}

async function backupNow() {
  const clean = $("backup-clean-ps4").checked;
  if (clean && !confirm(
    "Backup AND clean the PS4?\n\nThe backup will be made first, then every BS " +
    "Deluxe file is wiped from the console (fresh-slate redeploy posture). " +
    "The backup zip is your only safety net — make sure it completes."))
    return;
  if (!clean && !confirm("Backup the PS4's OrBeats state now?")) return;
  const btn = $("btn-backup-now");
  btn.disabled = true; btn.textContent = "Backing up…";
  try {
    const j = await api("/api/jobs/backup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ clean_ps4: clean }),
    });
    showJobPanel("backup-job-panel", {
      label: clean ? "backup + clean PS4" : "backup",
      command: j.command,
    });
    await runJobWithPanel("backup-job-panel", j, { doneLabel: "backup complete" });
    // refresh the list when the job ends (poll resolves only at completion)
    setTimeout(backupRefresh, 1500);
    btn.disabled = false; btn.textContent = "Backup now";
  } catch (e) {
    btn.disabled = false; btn.textContent = "Backup now";
    alert("Couldn't start the backup: " + e.message);
  }
}

async function backupRestore(name) {
  if (!confirm(
    `Restore "${name}" to the PS4?\n\n` +
    `This overwrites the console's current OrBeats state (bundles, redirects, ` +
    `metadata, features) with the backup's contents. The current state is NOT ` +
    `saved automatically — make a fresh backup first if you might want it back.`))
    return;
  try {
    const j = await api("/api/jobs/restore", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ backup: name, clean_ps4: false }),
    });
    showJobPanel("backup-job-panel", { label: `restore ${name}`, command: j.command });
    await runJobWithPanel("backup-job-panel", j, { doneLabel: `restored ${name}` });
    setTimeout(backupRefresh, 1500);
  } catch (e) {
    alert("Couldn't start the restore: " + e.message);
  }
}

// ---------------------------------------------------------------- batch
let examplePacks = [];      // parsed from the example scripts
let savedBatches = [];      // webapp/batches/*.json
let batchSongs = [];        // the current working batch (array of entries)
let batchMode = "example";  // example | custom | saved
let batchFile = null;       // filename when a saved batch is loaded

async function batchRefresh() {
  const sel = $("batch-select");
  try {
    const [ex, cu] = await Promise.all([api("/api/batch/examples"),
                                        api("/api/batch/custom")]);
    examplePacks = ex.packs;
    savedBatches = cu.batches;
    sel.innerHTML = "";
    const groupEx = document.createElement("optgroup");
    groupEx.label = "Pre-defined packs (from the example scripts)";
    examplePacks.forEach((p, i) => {
      const o = document.createElement("option");
      o.value = `ex:${i}`;
      o.textContent = `${p.name} (${p.songs.length} songs)`;
      groupEx.appendChild(o);
    });
    sel.appendChild(groupEx);
    const groupCu = document.createElement("optgroup");
    groupCu.label = "My saved batches";
    if (!savedBatches.length) {
      const o = document.createElement("option");
      o.value = "none:saved";
      o.textContent = "(none saved yet)";
      o.disabled = true;
      groupCu.appendChild(o);
    } else {
      savedBatches.forEach((b, i) => {
        const o = document.createElement("option");
        o.value = `sv:${i}`;
        o.textContent = `${b.name} (${b.song_count} songs)`;
        if (b.error) o.textContent += " ⚠ unreadable";
        groupCu.appendChild(o);
      });
    }
    sel.appendChild(groupCu);
    const oCustom = document.createElement("option");
    oCustom.value = "custom";
    oCustom.textContent = "＋ Build a custom batch…";
    sel.appendChild(oCustom);
    sel.onchange = batchSelectChanged;
    multiRenderList();
  } catch (e) {
    sel.innerHTML = `<option value=''>couldn't load: ${esc(e.message)}</option>`;
  }
}

async function batchSelectChanged() {
  const v = $("batch-select").value;
  batchFile = null;
  if (v === "custom") {
    batchMode = "custom";
    batchSongs = [];
    batchRender("New custom batch", "", true);
  } else if (v.startsWith("ex:")) {
    batchMode = "example";
    const pack = examplePacks[parseInt(v.slice(3), 10)];
    batchSongs = JSON.parse(JSON.stringify(pack.songs));
    batchRender(pack.name, pack.description, false);
  } else if (v.startsWith("sv:")) {
    const meta = savedBatches[parseInt(v.slice(3), 10)];
    try {
      const j = await api(`/api/batch/custom/${encodeURIComponent(meta.file)}`);
      batchMode = "saved";
      batchFile = meta.file;
      batchSongs = j.batch.songs;
      batchRender(j.batch.name, j.batch.description, true);
    } catch (e) {
      alert("Couldn't load the saved batch: " + e.message);
    }
  }
}

function batchRender(name, desc, editable) {
  $("batch-title").textContent = name || "Batch";
  $("batch-desc").textContent = desc || "";
  const body = $("batch-table").querySelector("tbody");
  if (!batchSongs.length) {
    body.innerHTML = `<tr><td colspan='7' class='muted'>${
      editable ? "No songs yet — use ＋ Add song below."
               : "This pack has no songs (parse error?)"}</td></tr>`;
  } else {
    body.innerHTML = batchSongs.map((s, i) => `
      <tr>
        <td>${i + 1}</td>
        <td><code>${esc(s.map_id)}</code></td>
        <td>${esc(s.song_name || "(name from BeatSaver)")}</td>
        <td>${esc(s.artist || "")}</td>
        <td><code>${esc(s.target)}</code></td>
        <td>${esc(s.audio || "pcm16")}</td>
        <td>${editable
            ? `<button class="batch-remove" data-i="${i}">✕</button>`
            : ""}</td>
      </tr>`).join("");
    body.querySelectorAll("button.batch-remove").forEach(b =>
      b.addEventListener("click", () => {
        batchSongs.splice(parseInt(b.dataset.i, 10), 1);
        batchRender($("batch-title").textContent, $("batch-desc").textContent, true);
      }));
  }
  const isEditable = editable || batchMode === "saved";
  $("btn-batch-add").classList.toggle("hidden", !isEditable);
  $("btn-batch-save").classList.toggle("hidden", !isEditable);
  $("btn-batch-export").classList.toggle("hidden", !batchSongs.length);
  $("btn-batch-import").classList.toggle("hidden", batchMode !== "custom");
  $("btn-batch-delete").classList.toggle("hidden", batchMode !== "saved");
  $("batch-edit-name-row").classList.toggle("hidden", !isEditable);
  if (isEditable && !$("batch-name").value) $("batch-name").value = name || "";
  $("btn-batch-deploy").disabled = !batchSongs.length;
}

function batchEntryFromSong(s, target) {
  return { map_id: s.id, target,
           song_name: s.songAuthorName ? s.name.split(" - ")[0] : s.name,
           artist: s.songAuthorName || "",
           audio: "pcm16", pad_fsb5: false, convert_to_v3: true };
}

async function batchSearch() {
  const q = $("batch-search").value.trim();
  if (!q) return;
  $("batch-search-results").innerHTML = "<p class='muted'>Searching…</p>";
  let docs;
  try {
    const j = await api(`/api/beatsaver/search?q=${encodeURIComponent(q)}&per_page=30`);
    docs = j.docs;
  } catch (e) {
    $("batch-search-results").innerHTML =
      `<p class='result bad'>Search failed: ${esc(e.message)}</p>`;
    return;
  }
  if ($("batch-filter-enh").checked)
    docs = docs.filter(s => s.nativeDifficulties.length === 3);
  if (!docs.length) {
    $("batch-search-results").innerHTML = "<p class='muted'>No results.</p>";
    return;
  }
  $("batch-search-results").innerHTML = docs.map(s => `
    <div class="song">
      <div class="meta">
        <b>${esc(s.name)}</b>
        <span class="muted">${esc(s.songAuthorName || "?")} · mapped by ${esc(s.levelAuthorName || "?")} ·
        BPM ${s.bpm ?? "?"} · ${s.downloads ?? "?"} downloads</span>
      </div>
      <div class="badges">${nativeDiffBadges(s)}</div>
      <button class="batch-pick" data-mapid="${esc(s.id)}"
              data-name="${esc(s.name)}" data-artist="${esc(s.songAuthorName || "")}">
        Pick →</button>
    </div>`).join("");
  $("batch-search-results").querySelectorAll("button.batch-pick").forEach(b =>
    b.addEventListener("click", () => {
      // slot selection happens in a small prompt-driven flow: open the slot dropdown
      const slot = $("batch-manual-slot");
      const pending = batchEntryFromSong(
        {id: b.dataset.mapid, name: b.dataset.name, songAuthorName: b.dataset.artist,
         nativeDifficulties: ["Easy", "Normal", "Hard"]}, "");
      pending._pickName = b.dataset.name;
      batchPendingPick = pending;
      $("batch-add-card").scrollIntoView({behavior: "smooth", block: "nearest"});
      slot.focus();
      setResult("batch-add-status", "Picked '" + b.dataset.name + "' — now choose the target slot below.", "");
    }));
}

let batchPendingPick = null;

async function batchDeploy() {
  if (!batchSongs.length) return;
  const n = batchSongs.length;
  if (!confirm(
    `Deploy this batch of ${n} song${n > 1 ? "s" : ""} to the PS4?\n\n` +
    `Each song runs the full --deploy-full pipeline in sequence (download, ` +
    `build all modes, deploy, validate). The batch STOPS at the first ` +
    `failure — songs before it stay deployed. Existing customs in other ` +
    `packs are preserved.`))
    return;
  try {
    const j = await api("/api/jobs/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ songs: batchSongs }),
    });
    showJobPanel("batch-job-panel", {
      label: `batch deploy — ${j.count} songs`,
      command: j.command,
    });
    $("btn-batch-cancel").classList.remove("hidden");
    runJobWithPanel("batch-job-panel", j);
  } catch (e) {
    alert("Couldn't start the batch: " + e.message);
  }
}

async function batchSave() {
  const name = $("batch-name").value.trim();
  if (!name) { alert("Give the batch a name first."); return; }
  const doc = { format: "bsd-batch", version: 1, name,
                description: $("batch-desc-input").value.trim(),
                songs: batchSongs };
  try {
    const j = await api("/api/batch/custom", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: batchFile, batch: doc }),
    });
    batchFile = j.file;
    batchMode = "saved";
    batchRender(name, doc.description, true);
    await batchRefresh();
    $("batch-select").value = `sv:${savedBatches.findIndex(b => b.file === batchFile)}`;
  } catch (e) {
    alert("Save failed: " + e.message);
  }
}

function batchExport() {
  // Browser download — platform-agnostic by design
  const doc = { format: "bsd-batch", version: 1,
                name: $("batch-name").value.trim() || $("batch-title").textContent,
                description: $("batch-desc-input").value.trim(),
                songs: batchSongs };
  const blob = new Blob([JSON.stringify(doc, null, 2)], {type: "application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = (doc.name.toLowerCase().replace(/[^a-z0-9]+/g, "_") || "batch") + ".json";
  a.click();
  URL.revokeObjectURL(a.href);
}

async function batchImportFile(file) {
  try {
    const text = await file.text();
    const doc = JSON.parse(text);
    batchMode = "custom";
    batchFile = null;
    batchSongs = doc.songs || [];
    $("batch-name").value = doc.name || file.name.replace(/\.json$/, "");
    $("batch-desc-input").value = doc.description || "";
    batchRender(doc.name || file.name, doc.description || "", true);
  } catch (e) {
    alert("Import failed (not valid batch JSON): " + e.message);
  }
}

async function batchDelete() {
  if (!batchFile || !confirm(`Delete the saved batch "${batchFile}"?\n\nThe working copy stays; only the saved file is removed.`))
    return;
  try {
    await api(`/api/batch/custom/${encodeURIComponent(batchFile)}`, { method: "DELETE" });
    batchFile = null;
    batchMode = "custom";
    await batchRefresh();
    batchRender($("batch-name").value, $("batch-desc-input").value, true);
  } catch (e) {
    alert("Delete failed: " + e.message);
  }
}

// slot dropdown for manual/picked adds — reuse the catalog
function batchFillSlotDropdown() {
  const sel = $("batch-manual-slot");
  if (sel.options.length > 1) return;  // already filled
  state.catalog.forEach(album => {
    const g = document.createElement("optgroup");
    g.label = album.pack;
    album.songs.forEach(s => {
      const o = document.createElement("option");
      o.value = s.songID;
      o.textContent = `${s.songID} — ${s.songName}`;
      g.appendChild(o);
    });
    sel.appendChild(g);
  });
}

// ---------------------------------------------------------------- multi-pack batch
let multiSelected = new Set();   // indexes into examplePacks

function multiRenderList() {
  const host = $("multi-pack-list");
  if (!examplePacks.length) {
    host.innerHTML = "<p class='muted' style='padding:.4rem'>Packs load on first visit — hit Refresh above.</p>";
    return;
  }
  host.innerHTML = examplePacks.map((p, i) => `
    <label class="multi-pack-row">
      <input type="checkbox" data-i="${i}" ${multiSelected.has(i) ? "checked" : ""}>
      <b>${esc(p.name)}</b>
      <span class="muted">${p.songs.length} songs — ${p.songs[0].target}…${p.songs[p.songs.length - 1].target}</span>
    </label>`).join("");
  host.querySelectorAll("input[type=checkbox]").forEach(cb =>
    cb.addEventListener("change", () => {
      const i = parseInt(cb.dataset.i, 10);
      if (cb.checked) multiSelected.add(i); else multiSelected.delete(i);
      multiUpdateCount();
    }));
  multiUpdateCount();
}

function multiUpdateCount() {
  const packs = multiSelected.size;
  const songs = [...multiSelected].reduce(
    (n, i) => n + examplePacks[i].songs.length, 0);
  $("multi-count").textContent = `${packs} pack${packs === 1 ? "" : "s"} · ${songs} songs selected`;
  $("btn-multi-deploy").disabled = packs === 0;
  // order preview: the selection deploys in the order shown (pack index)
  const ordered = [...multiSelected].sort((a, b) => a - b);
  $("btn-multi-deploy").title = ordered.length
    ? `Deploy order: ${ordered.map(i => examplePacks[i].name).join(" → ")}`
    : "";
}

async function multiDeploy() {
  if (!multiSelected.size) return;
  const ordered = [...multiSelected].sort((a, b) => a - b);
  const packNames = ordered.map(i => examplePacks[i].name);
  const songs = ordered.flatMap(i =>
    JSON.parse(JSON.stringify(examplePacks[i].songs)));
  const n = songs.length;
  if (!confirm(
    `Deploy ${packNames.length} music pack${packNames.length > 1 ? "s" : ""} — ${n} songs total?\n\n` +
    `Packs in order: ${packNames.join(", ")}\n\n` +
    `Each song runs the full --deploy-full pipeline sequentially (this is the ` +
    `web-app equivalent of chaining the example scripts). The run STOPS at the ` +
    `first failure — everything before it stays deployed. Existing customs in ` +
    `packs you have NOT selected are preserved. Expect this to take a while.`))
    return;
  try {
    const j = await api("/api/jobs/batch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ songs }),
    });
    showJobPanel("batch-job-panel", {
      label: `multi-pack deploy — ${packNames.join(", ")}`,
      command: j.command,
    });
    $("btn-batch-cancel").classList.remove("hidden");
    runJobWithPanel("batch-job-panel", j);
  } catch (e) {
    alert("Couldn't start the multi-pack deploy: " + e.message);
  }
}

// ---------------------------------------------------------------- feature request
const FR_REPO = "free5ty1e/BeatSaberPcCustomSongToPs4InstallConverter";

function frCompose() {
  const title = $("fr-title").value.trim();
  const body = $("fr-body").value.trim();
  if (!title || !body) {
    $("fr-status").textContent = "Fill in both the summary and the details first.";
    return null;
  }
  let text = `### Feature request (from the web app)\n\n${body}\n`;
  if ($("fr-include-state").checked) {
    text += `\n---\n**App context:** web app mode=${state.mode}`;
    if (loadoutData) {
      const packs = loadoutData.packs.filter(p => p.deployedCount > 0)
        .map(p => `${p.pack} (${p.deployedCount})`).join(", ");
      text += ` · deployed packs: ${packs || "none read yet"}`;
    }
    text += `\n`;
  }
  return { title, body: text };
}

function frPreview() {
  const issue = frCompose();
  if (!issue) return;
  $("fr-preview").textContent =
    `Title: [webapp] ${issue.title}\n\n${issue.body}`;
  $("fr-preview-box").classList.remove("hidden");
  $("btn-fr-open").classList.remove("hidden");
  $("fr-status").textContent = "";
}

function frOpen() {
  const issue = frCompose();
  if (!issue) return;
  const url = `https://github.com/${FR_REPO}/issues/new`
    + `?title=${encodeURIComponent("[webapp] " + issue.title)}`
    + `&body=${encodeURIComponent(issue.body)}`;
  window.open(url, "_blank", "noopener");
}

// ---------------------------------------------------------------- ps4 page
async function refreshPs4() {
  const el = $("ps4-state");
  el.innerHTML = '<div class="row"><span class="spinner spinning"></span> ' +
    'Reading PS4 state (banner-free transport)…</div>';
  try {
    const j = await api("/api/ps4/state");
    const rows = [];
    const red = j.redirects, feat = j.features, meta = j.song_metadata;
    const absentNote = "not present — clean slate (fresh install / after Clear PS4)";
    rows.push(["PS4 redirects", !red.ok
      ? `couldn't read (${red.error})`
      : red.absent ? absentNote
      : `${red.song_count} song redirects · ${red.pack_count} pack redirects · catalog redirect ${red.catalog_redirect_present ? "present" : "absent"}`]);
    rows.push(["Feature flags", !feat.ok
      ? `couldn't read (${feat.error})`
      : feat.absent ? absentNote
      : Object.entries(feat).filter(([k]) => k.startsWith("enable_"))
          .map(([k, v]) => `${k}=${v ? "ON" : "OFF"}`).join(" · ")]);
    rows.push(["Song metadata", !meta.ok
      ? `couldn't read (${meta.error})`
      : meta.absent ? absentNote
      : `${meta.custom_song_count} custom song names deployed`]);
    const banner = j.clean_slate
      ? `<div class="result good" style="margin-bottom:8px">✅ <b>Clean slate</b> — no BSD state on the console.
           This is the correct state for a fresh install or right after Clear PS4;
           state files appear here as you deploy.</div>`
      : "";
    el.innerHTML = banner + "<table>" + rows.map(([k, v]) =>
      `<tr><th>${esc(k)}</th><td>${esc(v)}</td></tr>`).join("") + "</table>";
  } catch (e) {
    el.innerHTML = `<span class='result bad'>Couldn't read PS4 state: ${esc(e.message)}</span>`;
  }
}

// ---------------------------------------------------------------- boot
async function boot() {
  await detectMode();
  if (state.mode === "local-backend") {
    loadDumpDefault();
    loadBeatsageGuide();   // M13: the guided card + recommended options
    loadStaged();          // M13: the recent-songs list (persists restarts)
    try {
      const cfg = await api("/api/config");
      if (cfg.ps4 && cfg.ps4.ip) $("ps4-ip").value = cfg.ps4.ip;
      if (cfg.ps4 && cfg.ps4.ftp_port) $("ps4-port").value = cfg.ps4.ftp_port;
      state.catalog = (await api("/api/catalog")).albums;
      loadCatalogIntoPicker();
    } catch { /* wizard-first flow */ }
    loadManagePacks();   // Manage Songs dropdown (catalog-only — works offline)
    fillVersionBadge();  // live versions from the running server
  }
}

// ---------------------------------------------------------------- versions
async function fillVersionBadge() {
  try {
    const j = await api("/api/ping");
    if (j.webapp_version) $("ver-webapp").innerHTML = `web app <b>${esc(j.webapp_version)}</b>`;
    if (j.pipeline_version) $("ver-pipeline").innerHTML = `pipeline <b>${esc(j.pipeline_version)}</b>`;
    if (j.plugin_version) $("ver-plugin").innerHTML = `plugin <b>${esc(j.plugin_version)}</b>`;
  } catch { /* pages mode bakes versions at build time; badge hidden if absent */ }
}

document.addEventListener("DOMContentLoaded", () => {
  boot();
  $("btn-dump-check").addEventListener("click", () => checkDump($("dump-path").value.trim()));
  $("btn-dump-default").addEventListener("click", loadDumpDefault);
  $("btn-conn-test").addEventListener("click", testConnection);
  $("btn-save-config").addEventListener("click", saveConfig);
  $("ps4-ip").addEventListener("input", updateSaveButton);
  $("ps4-port").addEventListener("input", updateSaveButton);
  updateSaveButton();
  $("btn-bs-search").addEventListener("click", searchBeatSaver);
  $("bs-query").addEventListener("keydown", e => { if (e.key === "Enter") searchBeatSaver(); });
  $("bs-filter-enh").addEventListener("change", searchBeatSaver);
  $("btn-bs-lookup").addEventListener("click", lookupMapId);
  $("btn-bsage-generate").addEventListener("click", generateWithBeatsage);
  $("btn-bsage-testsong").addEventListener("click", useTestSong);
  $("btn-local-validate").addEventListener("click", validateLocalDir);
  $("local-song-path").addEventListener("keydown", e => { if (e.key === "Enter") validateLocalDir(); });
  wireZipDrop();
  $("deploy-pack").addEventListener("change", () => {});
  ["opt-audio", "opt-v3", "opt-skip-plugin", "opt-pad", "opt-songname", "opt-artist"]
    .forEach(id => $(id).addEventListener("change", updateDeployPreview));
  $("opt-songname").addEventListener("input", updateDeployPreview);
  $("opt-artist").addEventListener("input", updateDeployPreview);
  $("btn-deploy").addEventListener("click", deploy);
  $("btn-deploy-cancel").addEventListener("click", cancelJob);
  $("btn-verify").addEventListener("click", async () => {
    const btn = $("btn-verify");
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner spinning"></span> Verifying…';
    setDeployProgress(true, "Verifying", "read-only PS4 validation");
    $("deploy-log").classList.remove("hidden");
    $("deploy-log").textContent = "";
    setResult("deploy-status", "", "");
    try {
      await api("/api/jobs/verify", { method: "POST" });
      pollIndex = 0;
      // pollLog's finishJob re-enables the deploy button; restore verify's too
      const origFinish = finishJob;
      pollLog();
      const restore = setInterval(() => {
        if (!btn.isConnected || btn.disabled === false) return;
        btn.disabled = false; btn.innerHTML = "Verify PS4";
      }, 1000);
      setTimeout(() => clearInterval(restore), 120000);
    } catch (e) {
      btn.disabled = false; btn.innerHTML = "Verify PS4";
      setDeployProgress(false);
      setResult("deploy-status", "❌ " + e.message, "bad");
    }
  });
  $("btn-ps4-refresh").addEventListener("click", refreshPs4);
  $("btn-manage-refresh").addEventListener("click", manageRefresh);
  $("btn-loadout-refresh").addEventListener("click", loadoutRefresh);
  $("loadout-only-custom").addEventListener("change", renderLoadoutTables);
  $("btn-flags-refresh").addEventListener("click", flagsRefresh);
  $("btn-flags-apply").addEventListener("click", flagsApply);
  $("btn-backup-now").addEventListener("click", backupNow);
  $("btn-backup-refresh").addEventListener("click", backupRefresh);
  $("btn-backup-browse").addEventListener("click", () => {
    const box = $("backup-browser");
    box.classList.toggle("hidden");
    if (!box.classList.contains("hidden")) browseLoad("");
  });
  $("btn-browse-go").addEventListener("click", () =>
    browseLoad($("browse-path-input").value.trim()));
  $("btn-browse-choose").addEventListener("click", () =>
    browsePath && backupChooseFolder(browsePath));
  $("btn-backup-reset-dir").addEventListener("click", async () => {
    try {
      const def = await api("/api/backup/dir");
      await backupChooseFolder(def.default);
    } catch (e) { alert(e.message); }
  });
  $("btn-job-cancel").addEventListener("click", cancelJob);
  document.querySelectorAll(".os-tab").forEach(b =>
    b.addEventListener("click", () => {
      document.querySelectorAll(".os-tab").forEach(x => x.classList.toggle("active", x === b));
      document.querySelectorAll(".os-pane").forEach(p =>
        p.classList.toggle("hidden", p.dataset.os !== b.dataset.os));
    }));
  $("btn-fr-preview").addEventListener("click", frPreview);
  $("btn-batch-refresh").addEventListener("click", batchRefresh);
  $("btn-batch-deploy").addEventListener("click", batchDeploy);
  $("btn-batch-add").addEventListener("click", () => {
    $("batch-add-card").classList.remove("hidden");
    batchFillSlotDropdown();
    $("batch-search").focus();
  });
  $("btn-batch-search").addEventListener("click", batchSearch);
  $("batch-search").addEventListener("keydown", e => { if (e.key === "Enter") batchSearch(); });
  $("batch-filter-enh").addEventListener("change", batchSearch);
  $("batch-manual-slot").addEventListener("change", () => {
    // completing a searched-song pick: attach the chosen slot
    const slot = $("batch-manual-slot").value;
    if (batchPendingPick && slot) {
      batchPendingPick.target = slot;
      batchSongs.push(batchPendingPick);
      batchPendingPick = null;
      $("batch-manual-slot").value = "";
      batchRender($("batch-name").value || "Custom batch", $("batch-desc-input").value, true);
      setResult("batch-add-status", "Added to the batch.", "ok");
    }
  });
  $("btn-batch-manual-add").addEventListener("click", () => {
    const id = $("batch-manual-id").value.trim();
    const slot = $("batch-manual-slot").value;
    if (!id || !slot) { alert("Enter both the map ID and the target slot."); return; }
    batchSongs.push({ map_id: id, target: slot, song_name: "", artist: "",
                      audio: "pcm16", pad_fsb5: false, convert_to_v3: true });
    $("batch-manual-id").value = ""; $("batch-manual-slot").value = "";
    batchRender($("batch-name").value || "Custom batch", $("batch-desc-input").value, true);
  });
  $("btn-batch-save").addEventListener("click", batchSave);
  $("btn-batch-export").addEventListener("click", batchExport);
  $("btn-batch-import").addEventListener("click", () => $("batch-import-file").click());
  $("batch-import-file").addEventListener("change", e => {
    if (e.target.files.length) batchImportFile(e.target.files[0]);
    e.target.value = "";
  });
  $("btn-batch-delete").addEventListener("click", batchDelete);
  $("btn-multi-select-all").addEventListener("click", () => {
    examplePacks.forEach((_, i) => multiSelected.add(i));
    multiRenderList();
  });
  $("btn-multi-select-none").addEventListener("click", () => {
    multiSelected.clear();
    multiRenderList();
  });
  $("btn-multi-deploy").addEventListener("click", multiDeploy);
  $("btn-batch-cancel").addEventListener("click", () => {
    api("/api/jobs/cancel", { method: "POST" }).catch(() => {});
  });
  $("btn-fr-open").addEventListener("click", frOpen);
  const gdReq = $("gamedata-request-btn"), gdPull = $("gamedata-pull-btn"),
        gdUse = $("gamedata-use-btn");
  if (gdReq) gdReq.addEventListener("click", gamedataRequest);
  if (gdPull) gdPull.addEventListener("click", gamedataPull);
  if (gdUse) gdUse.addEventListener("click", gamedataUseCache);
  const dpBtn = $("btn-deploy-plugin"), dpStartBtn = $("btn-deploy-plugin-start");
  if (dpBtn) dpBtn.addEventListener("click", () => deployPlugin(false));
  if (dpStartBtn) dpStartBtn.addEventListener("click", () => deployPlugin(true));
  // lazy-load tab data on first visit
  document.querySelectorAll("#nav button").forEach(b =>
    b.addEventListener("click", () => {
      if (b.dataset.page === "flagsPage") flagsRefresh();
      if (b.dataset.page === "backupPage") backupRefresh();
      if (b.dataset.page === "batchPage") batchRefresh();
      if (b.dataset.page === "guide") { gamedataLoadPacks(); gamedataRefresh(); }
    }));
  // Landing (Exp 266): pages mode lands on the guided download funnel — but
  // detectMode()'s startBtn click already ran, and this DOMContentLoaded
  // handler fires AFTER it, stomping startPage back to the wizard (the race
  // the live Pages deploy exposed). The unconditional wizard landing must
  // respect the mode: pages → startPage stays; local → wizard.
  if (state.mode !== "pages") showPage("wizard");
});

// Plugin-only deploy (M12, Exp 280b) — fromStart picks the Get Started
// surface's log/status elements; otherwise the Deploy tab's card.
async function deployPlugin(fromStart) {
  const suffix = fromStart ? "-start" : "";
  const logEl = $("deploy-plugin" + suffix + "-log");
  const stEl = $("deploy-plugin" + suffix + "-status");
  const debug = !fromStart && $("opt-plugin-debug") && $("opt-plugin-debug").checked;
  try {
    const res = await fetch("/api/jobs/deploy-plugin", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({debug}),
    });
    const start = await res.json();
    if (!res.ok) {
      stEl.textContent = "❌ " + (start.detail || "could not start the job");
      return;
    }
    logEl.classList.remove("hidden");
    let idx = 0;
    for (;;) {
      await new Promise(r => setTimeout(r, 900));
      const j = await (await fetch(`/api/jobs/lines?after=${idx}`)).json();
      if (j.lines && j.lines.length) {
        logEl.textContent += j.lines.join("\n") + "\n";
        logEl.scrollTop = logEl.scrollHeight;
      }
      idx = j.index || idx;
      if (!j.running && j.job) {
        stEl.innerHTML = j.job.exit_code === 0
          ? `✅ Plugin deployed${debug ? " (DEBUG build)" : ""} — restart Beat Saber to run it.`
          : `❌ Plugin deploy failed (exit ${j.job.exit_code}) — the log lines above carry the fix`;
        return;
      }
    }
  } catch (e) { stEl.textContent = "❌ " + e; }
}

// ═════════════════════════════════════════════════════════════════════════════
// M12 Game-data extraction (Exp 280) — the "no dump required" flow.
// Thin layer: two pipeline job subprocesses + one state read + one config
// switch. The pack list comes from /api/catalog (same data as the picker).
// ═════════════════════════════════════════════════════════════════════════════

let gamedataPacksLoaded = false;

async function gamedataRefresh() {
  const el = $("gamedata-status");
  if (!el) return;
  try {
    const st = await (await fetch("/api/game-data/state")).json();
    if (!st.ok) {
      el.innerHTML = `❌ PS4 unreachable — ${esc(st.error || "")}. ` +
        `To fix: power on the PS4 with GoldHEN's FTP (README Prerequisites).`;
      return;
    }
    const nReq = st.requests.length, nDone = st.extracted.length;
    const pending = st.pending || [];
    const errs = st.errors || [];
    const c = st.cache || {};
    let html = "";
    if (nReq === 0) {
      html += `No extraction request on the PS4 yet — pick packs below and ` +
              `<b>Request extraction</b>.<br>`;
    } else {
      html += `Requested: <b>${nReq}</b> file(s) · extracted on console: ` +
              `<b>${nDone}</b>${pending.length ? ` · pending: <b>${pending.length}</b>` : ""}`;
      if (nDone >= nReq && nReq > 0) html += ` ✅ <b>all extracted — pull when ready</b>`;
      html += `<br>`;
      if (nDone === 0) {
        html += `⏳ <b>Extraction pending — boot Beat Saber once.</b> The plugin ` +
                `extracts during a normal boot (you'll see a PS4 notification ` +
                `when it finishes). This page updates automatically — no need to click.<br>`;
      }
    }
    if (errs.length) {
      html += `⚠️ ${errs.length} extraction error(s) on the console — the log ` +
              `(bs_log.txt) has details; they retry on the next boot.<br>`;
    }
    if (c.files > 0) {
      html += `Local cache: <b>${c.files}</b> file(s), ` +
              `<b>${(c.bytes / 1e6).toFixed(1)} MB</b> at <code>${esc(c.dir)}</code>` +
              (c.cache_is_active ? ` — <b>✅ active</b> (game_dump_dir points here)` : ``);
    } else {
      html += `Local cache: empty — pull after the boot step.`;
    }
    el.innerHTML = html;
    // Step highlighting (the big numbered guide): 1=request, 2=boot watch,
    // 3=pull, 4=use, 5=deploy. The first unmet step is ACTIVE; met ones DONE.
    const mark = (id, state) => {
      const stepEl = $("gamedata-step-" + id);
      if (stepEl) { stepEl.classList.toggle("active", state === "active");
                    stepEl.classList.toggle("done", state === "done"); }
    };
    const markDone = (id) => mark(id, "done");
    const markActive = (id) => mark(id, "active");
    [1,2,3,4,5].forEach(i => mark(i, ""));
    const cacheActive = c.cache_is_active && c.files > 0;
    if (cacheActive) { [1,2,3,4].forEach(markDone); markActive(5); }
    else if (c.files > 0 && st.requests.length && nDone >= nReq) { [1,2,3].forEach(markDone); markActive(4); }
    else if (nDone > 0) { [1,2].forEach(markDone); markActive(3); }
    else if (st.requests.length > 0) { markDone(1); markActive(2); }
    else markActive(1);
    // Auto-poll while an extraction is pending (requests on the console,
    // nothing extracted yet) — the web app is "listening": the boot's
    // extraction shows up here within seconds of the game finishing it.
    if (pending.length > 0 || (st.requests.length > 0 && st.extracted.length === 0)) {
      if (!gamedataPollTimer) {
        gamedataPollTimer = setInterval(gamedataRefresh, 5000);
      }
    } else if (gamedataPollTimer && st.requests.length === 0) {
      clearInterval(gamedataPollTimer); gamedataPollTimer = null;
    }
  } catch (e) {
    el.innerHTML = `❌ ${esc(String(e))}`;
  }
}

let gamedataPollTimer = null;

async function gamedataLoadPacks() {
  if (gamedataPacksLoaded) return;
  const holder = $("gamedata-pack-list");
  if (!holder) return;
  try {
    const cat = await (await fetch("/api/catalog")).json();
    holder.innerHTML = "";
    for (const album of cat.albums) {
      const id = `gamedata-pack-${album.pack}`;
      const chip = document.createElement("label");
      chip.className = "chip";
      chip.innerHTML = `<input type="checkbox" id="${id}" data-pack="${esc(album.pack)}" data-slots="${album.songs.length}"> ` +
        `${esc(album.pack)} <span class="muted">(${album.songs.length} slots)</span>`;
      holder.appendChild(chip);
    }
    gamedataPacksLoaded = true;
    // size hint: slots × ~13MB per pack (measured average)
    const allBoxes = () => [...document.querySelectorAll("#gamedata-pack-list input")];
    const updateHint = () => {
      const n = allBoxes().filter(cb => cb.checked).length;
      const slots = allBoxes().filter(cb => cb.checked)
        .reduce((sum, cb) => sum + (parseInt(cb.dataset.slots) || 0), 0);
      $("gamedata-size-hint").textContent = n
        ? `${n} pack(s) · ${slots} slots · ~${(slots * 13 / 1000).toFixed(1)}GB to extract`
        : "";
    };
    allBoxes().forEach(cb => cb.addEventListener("change", updateHint));
    const sa = $("gamedata-select-all-btn"), sn = $("gamedata-select-none-btn");
    if (sa) sa.addEventListener("click", () => {
      allBoxes().forEach(cb => cb.checked = true); updateHint();
    });
    if (sn) sn.addEventListener("click", () => {
      allBoxes().forEach(cb => cb.checked = false); updateHint();
    });
  } catch (e) {
    holder.innerHTML = `<span class="muted">could not load the pack list: ${esc(String(e))}</span>`;
  }
}

async function gamedataRequest() {
  const packs = [...document.querySelectorAll("#gamedata-pack-list input:checked")]
    .map(cb => cb.dataset.pack);
  if (!packs.length) {
    alert("Pick at least one pack (or use the deploy flow's per-song request).");
    return;
  }
  const res = await fetch("/api/jobs/game-data-request", {
    method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({packs}),
  });
  await gamedataWatchJob(res);
  setTimeout(gamedataRefresh, 2000);
}

async function gamedataPull() {
  const res = await fetch("/api/jobs/game-data-pull", {method: "POST"});
  const start = await res.json();
  if (!start.ok) {
    $("gamedata-status").innerHTML = "❌ " + esc(start.detail || "could not start");
    return;
  }
  // Progress bar: local cache files vs the console's extracted count.
  const wrap = $("gamedata-pull-progress-wrap"),
        fill = $("gamedata-pull-progress-fill"),
        label = $("gamedata-pull-progress-label");
  if (wrap) { wrap.hidden = false; }
  let idx = 0;
  for (;;) {
    await new Promise(r => setTimeout(r, 900));
    try {
      const [j, stNow] = await Promise.all([
        fetch(`/api/jobs/lines?after=${idx}`).then(r => r.json()),
        fetch("/api/game-data/state").then(r => r.json()),
      ]);
      if (j.lines && j.lines.length) {
        $("gamedata-status").innerHTML = `<pre style="white-space:pre-wrap">` +
          esc(j.lines.slice(-4).join("\n")) + `</pre>`;
      }
      idx = j.index || idx;
      const total = (stNow.extracted || []).length;
      const have = (stNow.cache || {}).files || 0;
      const pct = total > 0 ? Math.min(100, Math.round(have / total * 100)) : 0;
      if (fill) fill.style.width = pct + "%";
      if (label) label.textContent = have + " / " + total + " files (" + pct + "%)";
      if (!j.running && j.job) {
        if (label) label.textContent = j.job.exit_code === 0
          ? "✅ complete (" + have + " files)"
          : "❌ failed (exit " + j.job.exit_code + ")";
        if (j.job.exit_code === 0 && fill) fill.style.width = "100%";
        break;
      }
    } catch (e) { /* transient */ }
  }
  setTimeout(gamedataRefresh, 1500);
}

// Watch a game-data job: poll the shared job lines, show tail + verdict.
async function gamedataWatchJob(startRes) {
  const el = $("gamedata-status");
  const start = await startRes.json();
  if (!start.ok) {
    el.innerHTML = `❌ could not start: ${esc(start.detail || "job runner busy")}`;
    return;
  }
  let idx = 0;
  for (;;) {
    await new Promise(r => setTimeout(r, 900));
    try {
      const j = await (await fetch(`/api/jobs/lines?after=${idx}`)).json();
      const lines = j.lines || [];
      if (lines.length) {
        el.innerHTML = `<pre style="white-space:pre-wrap">` +
          esc(lines.slice(-6).join("\n")) + `</pre>`;
      }
      idx = j.index || idx;
      if (!j.running && j.job) {
        el.innerHTML += (j.job.exit_code === 0
          ? `<br>✅ done — refresh follows`
          : `<br>❌ job failed (exit ${j.job.exit_code}) — the log lines above carry the fix`);
        return;
      }
    } catch (e) { /* transient */ }
  }
}

async function gamedataUseCache() {
  try {
    const res = await fetch("/api/game-data/use-cache", {method: "POST"});
    const data = await res.json();
    if (!res.ok) {
      $("gamedata-status").innerHTML =
        `❌ ${esc(data.detail || "could not switch config")}`;
      return;
    }
    $("gamedata-status").innerHTML =
      `✅ The pipeline now uses the extracted cache: ` +
      `<code>${esc(data.game_dump_dir)}</code> — deploy songs as usual!`;
  } catch (e) {
    $("gamedata-status").innerHTML = `❌ ${esc(String(e))}`;
  }
}
