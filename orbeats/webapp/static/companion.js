const $ = (id) => document.getElementById(id);
const escapeHTML = (v) =>
	String(v ?? "").replace(
		/[&<>"']/g,
		(c) =>
			({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
				c
			],
	);
const state = {
	page: 0,
	maps: [],
	songs: [],
	selectedSongs: new Set(),
	editingSelection: false,
	removing: false,
	libraryLoading: false,
	libraryReady: false,
	confirming: false,
	busy: false,
	jobId: null,
	lineIndex: 0,
	rawLog: "",
	logFollowing: true,
	logRunning: false,
	queue: { pending: [], history: [], active: null, paused: true },
	queueError: "",
	adding: new Set(),
	selected: null,
};
const duration = (s) =>
	Number.isFinite(Number(s))
		? `${Math.floor(Number(s) / 60)}:${String(Math.floor(Number(s) % 60)).padStart(2, "0")}`
		: "—";
const number = (n) =>
	n !== null && n !== undefined && n !== "" && typeof n !== "boolean" && Number.isFinite(Number(n)) ? Number(n).toLocaleString() : "—";
function mediaURL(value) {
	try {
		const u = new URL(value);
		return u.protocol === "https:" &&
			(u.hostname === "beatsaver.com" || u.hostname.endsWith(".beatsaver.com"))
			? u.href
			: null;
	} catch {
		return null;
	}
}
function imageURL(value) {
	return mediaURL(value) || "/static/map-placeholder.svg";
}
const previewAudio = new Audio();
previewAudio.preload = "none";
function artwork(title, cover, preview) {
	return `<button class="art-button" type="button" data-preview="${escapeHTML(preview || "")}" data-title="${escapeHTML(title)}" aria-label="${preview ? "Play preview of" : "No preview available for"} ${escapeHTML(title)}" aria-pressed="false" ${preview ? "" : "disabled"}><img class="art" src="${escapeHTML(cover)}" alt="${escapeHTML(title)} cover" loading="lazy" referrerpolicy="no-referrer">${preview ? '<span class="preview-icon" aria-hidden="true">▶</span>' : ""}</button>`;
}
function installedArtwork(title, id) {
	return `<img class="art installed-art" src="/api/orbis/library/${encodeURIComponent(id)}/cover" alt="${escapeHTML(title)} cover" loading="lazy">`;
}
function updatePreviewButtons() {
	for (const button of document.querySelectorAll("[data-preview]")) {
		if (!button.dataset.preview) continue;
		const playing = !previewAudio.paused && new URL(button.dataset.preview, location.href).href === previewAudio.src;
		button.setAttribute("aria-pressed", String(playing));
		button.setAttribute("aria-label", `${playing ? "Stop" : "Play"} preview of ${button.dataset.title}`);
		button.querySelector(".preview-icon").textContent = playing ? "Ⅱ" : "▶";
	}
}
for (const name of ["play", "pause", "ended"]) previewAudio.addEventListener(name, updatePreviewButtons);
async function togglePreview(button) {
	const src = new URL(button.dataset.preview, location.href).href;
	if (!previewAudio.paused && previewAudio.src === src) {
		previewAudio.pause();
		previewAudio.currentTime = 0;
		return;
	}
	previewAudio.pause();
	previewAudio.src = src;
	try {
		await previewAudio.play();
	} catch (e) {
		if (e.name !== "AbortError") notify("Preview unavailable. Check your connection and try again.");
	}
	updatePreviewButtons();
}
function relativeDate(value, now = Date.now()) {
	const t = Date.parse(value);
	if (!Number.isFinite(t)) return "Unknown upload date";
	const days = Math.max(0, Math.floor((now - t) / 86400000));
	if (days === 0) return "Today";
	if (days === 1) return "Yesterday";
	const [count, unit] = days < 7 ? [days, "day"] : days < 30 ? [Math.floor(days / 7), "week"] : days < 365 ? [Math.max(1, Math.floor(days / 30.4375)), "month"] : [Math.max(1, Math.floor(days / 365.25)), "year"];
	return `${count} ${unit}${count === 1 ? "" : "s"} ago`;
}
function positionNotice() {
	const notice = $("notice");
	if (notice.hidden) return;
	// Outside a modal, even a top-layer popover is inert. Keep the toast
	// within the frontmost modal's subtree so its close button remains usable.
	const host = [...document.querySelectorAll("dialog[open]")].filter(d => d.matches(":modal")).at(-1) || document.body;
	if (notice.parentElement !== host) {
		if (typeof notice.hidePopover === "function" && notice.matches(":popover-open")) notice.hidePopover();
		host.append(notice);
	}
	if (typeof notice.showPopover === "function" && !notice.matches(":popover-open")) notice.showPopover();
}
function notify(text) {
	$("notice").hidden = false;
	$("notice-message").textContent = text;
	positionNotice();
}
new MutationObserver((records) => {
	if (records.some(record => record.target instanceof HTMLDialogElement)) positionNotice();
}).observe(document.body, {subtree: true, attributes: true, attributeFilter: ["open"]});
$("dismiss-notice").onclick = () => {
	const notice = $("notice");
	if (typeof notice.hidePopover === "function" && notice.matches(":popover-open")) notice.hidePopover();
	notice.hidden = true;
	$("notice-message").textContent = "";
};
function confirmAction(title, message, action) {
	const dialog = $("confirm-action");
	// close is queued by the browser. Do not reopen before its previous close
	// event resolves, or a cancelled prompt can inherit the next returnValue.
	if (state.confirming || dialog.open) return Promise.resolve(false);
	state.confirming = true;
	$("confirm-title").textContent = title;
	$("confirm-message").textContent = message;
	$("confirm-accept").textContent = action;
	dialog.returnValue = "";
	return new Promise((resolve) => {
		const closed = () => {
			const accepted = dialog.returnValue === "confirm";
			state.confirming = false;
			resolve(accepted);
		};
		dialog.addEventListener("close", closed, { once: true });
		try { dialog.showModal(); }
		catch {
			dialog.removeEventListener("close", closed);
			state.confirming = false;
			resolve(false);
		}
	});
}
async function api(path, options = {}) {
	const r = await fetch(path, {
		...options,
		headers: {
			...(options.body ? { "Content-Type": "application/json" } : {}),
			...options.headers,
		},
	});
	let data;
	try {
		data = await r.json();
	} catch {
		throw Error(`Server returned ${r.status}`);
	}
	if (!r.ok)
		throw Error(
			typeof data.detail === "string"
				? data.detail
				: JSON.stringify(data.detail || data),
		);
	return data;
}
function safely(action) {
	return async (event) => {
		try {
			await action(event);
		} catch (e) {
			notify(e.message);
		}
	};
}
function setTab(name) {
	previewAudio.pause();
	for (const e of document.querySelectorAll(".page")) e.hidden = e.id !== name;
	for (const b of document.querySelectorAll("nav button")) {
		if (b.dataset.tab === name) b.setAttribute("aria-current", "page");
		else b.removeAttribute("aria-current");
	}
	location.hash = name;
	if (name === "library" && !state.songs.length)
		loadLibrary().catch((e) => notify(e.message));
}
function theme() {
	const current = document.documentElement.dataset.theme;
	document.documentElement.dataset.theme =
		current === "dark" ? "light" : "dark";
	try {
		localStorage.setItem("orbis-theme", document.documentElement.dataset.theme);
	} catch {}
}
function diffBadges(diffs) {
 const values = new Map();
 for (const d of diffs) if (typeof d?.difficulty === "string") values.set(`${d.characteristic || "Standard"}/${d.difficulty}`,d);
 return [...values.values()].map(d => `<span class="badge diff-${escapeHTML(d.difficulty)}">${escapeHTML((d.characteristic && d.characteristic !== "Standard" ? d.characteristic + " " : "") + d.difficulty.replace("ExpertPlus", "Expert+"))}</span>`).join("");
}
function installedCharts(s) {
 const labels=["Easy","Normal","Hard","Expert","ExpertPlus"];
 return [["Standard",s], ...Object.entries(s.modes || {})].flatMap(([mode,entry]) => labels.flatMap((name,i) => entry.mask & (1 << i) ? [{characteristic:mode,difficulty:name,stats:entry.stats[i]}] : []));
}
function mapData(map) {
	const meta = map.metadata || {},
		v = map.versions?.[0] || {},
		stats = map.stats || {};
	return {
		meta,
		v,
		stats,
		title: meta.songName || map.name || "Untitled map",
		artist: meta.songAuthorName || "Unknown artist",
		mapper: meta.levelAuthorName || map.uploader?.name || "Unknown mapper",
		diffs: v.diffs || [],
	};
}
// These flags can reveal blockers, not prove that an archive will convert.
// Keep this aligned with the fail-closed whole-pack import policy.
function compatibility(map) {
	const diffs = map.versions?.[0]?.diffs;
	if (!Array.isArray(diffs) || !diffs.length) return {status: "unknown", label: "Needs validation", reason: "Chart metadata is missing. The archive will be validated before installation."};
	const reasons = new Set();
	let incomplete = false;
	const mods = {ne: "Noodle Extensions", me: "Mapping Extensions", chroma: "Chroma", cinema: "Cinema"};
	for (const d of diffs) {
		if (!d || typeof d !== "object") { incomplete = true; continue; }
		if (d.characteristic && !["Standard", "OneSaber", "NoArrows", "90Degree", "360Degree"].includes(d.characteristic)) reasons.add(`${d.characteristic} charts are unsupported`);
		if (!d.characteristic || !["Easy", "Normal", "Hard", "Expert", "ExpertPlus"].includes(d.difficulty)) incomplete = true;
		for (const [key, label] of Object.entries(mods)) {
			if (d[key] === true) reasons.add(label);
			else if (d[key] !== false) incomplete = true;
		}
		if (Array.isArray(d.requirements) && d.requirements.length) reasons.add("Declared mod requirements");
	}
	if (reasons.size) return {status: "unsupported", label: "Not compatible", reason: [...reasons].join("; ") + ". OrBeats refuses the whole pack rather than stripping unsupported charts/effects."};
	return incomplete ? {status: "unknown", label: "Needs validation", reason: "Some compatibility flags are missing. The archive will be validated before installation."} : {status: "likely", label: "No known blockers", reason: "Metadata check only, not a compatibility guarantee. Chart format, geometry, lighting and audio are validated from the downloaded archive before installation."};
}
function compatibilityBadge(map) {
	const c = compatibility(map), icon = c.status === "unsupported" ? "✕" : c.status === "likely" ? "✓" : "?";
	return `<span class="compatibility compatibility-${c.status}" title="${escapeHTML(c.reason)}">${icon} ${c.label}</span>`;
}
function votes(stats) {
	return [stats.upvotes, stats.downvotes].every(n => Number.isSafeInteger(n) && n >= 0) && Number.isSafeInteger(stats.upvotes + stats.downvotes) ? stats.upvotes + stats.downvotes : null;
}
function rating(stats) {
	const count = votes(stats);
	const score = Number.isFinite(stats.score) && stats.score >= 0 && stats.score <= 1 && count !== 0 ? `${Math.round(stats.score * 100)}%` : "—";
	return `<span class="rating" title="BeatSaver score · total up/down votes">♡ ${score} · ${count === null ? "— votes" : `${number(count)} ${count === 1 ? "vote" : "votes"}`}</span>`;
}
function card(map, index) {
	const { meta, v, stats, title, artist, mapper, diffs } = mapData(map);
	const c = compatibility(map);
	return `<article class="card">${artwork(title, imageURL(v.coverURL), mediaURL(v.previewURL))}<h3 title="${escapeHTML(title)}">${escapeHTML(title)}</h3><p class="artist">${escapeHTML(artist)}</p><p class="mapper">Mapped by ${escapeHTML(mapper)}</p><div class="meta"><span>◷ ${duration(meta.duration)}</span><span>♫ ${number(meta.bpm)} BPM</span>${rating(stats)}</div><div class="diffs">${diffBadges(diffs)}</div>${compatibilityBadge(map)}<div class="meta"><span title="${escapeHTML(map.uploaded || v.createdAt || "Upload time unavailable")}">${relativeDate(map.uploaded || v.createdAt)}</span></div><div class="card-bottom"><button data-detail="${index}">View details</button><button class="primary" data-install="${escapeHTML(map.id)}" data-unsupported="${c.status === "unsupported"}" title="${escapeHTML(c.reason)}">Add to queue ＋</button></div></article>`;
}
async function search(reset = true) {
	if (reset) state.page = 0;
	$("results").innerHTML = '<div class="empty">Finding your next beat…</div>';
	const q = $("query").value.trim(),
		match = q.match(
			/^(?:https:\/\/beatsaver.com\/maps\/)?([0-9a-f]{1,12})\/?$/i,
		);
	let maps;
	if (match) {
		maps = [await api("/api/orbis/map/" + match[1])];
	} else {
		const p = new URLSearchParams({
			q,
			sort: $("sort").value,
			period: $("period").value,
			page: state.page,
		});
		const r = await api("/api/orbis/search?" + p);
		maps = r.docs || [];
	}
	state.maps = maps;
	$("results").innerHTML = maps.length
		? maps.map(card).join("")
		: '<div class="empty">No maps found. Try a different artist, mapper or filter.</div>';
	$("page-number").textContent = "Page " + (state.page + 1);
	$("previous").disabled = state.page === 0;
	$("next").disabled = maps.length < 20;
	updateQueueButtons();
}
function showDetails(index, installedId = null) {
	const map = state.maps[index];
	if (!map) return;
	const { meta, v, stats, title, artist, mapper, diffs } = mapData(map);
	state.selected = map;
	const bool = (v) => (v ? "Yes" : "No");
	const c = compatibility(map);
	$("detail-content").innerHTML =
		`<div class="detail-top">${installedId ? installedArtwork(title, installedId) : artwork(title, imageURL(v.coverURL), mediaURL(v.previewURL))}<div><span class="eyebrow">BEATSAVER ${escapeHTML(map.id)}</span><h2>${escapeHTML(title)}</h2><p>${escapeHTML(artist)}<br>Mapped by ${escapeHTML(mapper)}</p><div class="diffs">${diffBadges(diffs)}</div>${installedId ? `<button class="danger" data-remove="${escapeHTML(installedId)}">Remove from PS4</button>` : `<button class="primary" data-install="${escapeHTML(map.id)}" data-unsupported="${c.status === "unsupported"}" title="${escapeHTML(c.reason)}">Add to queue ＋</button>`}</div></div><div class="stats"><div><strong>${duration(meta.duration)}</strong><small>DURATION</small></div><div><strong>${number(meta.bpm)}</strong><small>BPM</small></div><div>${rating(stats)}<small>BEATSAVER SCORE</small></div><div><strong>${number(stats.upvotes)} / ${number(stats.downvotes)}</strong><small>UP / DOWN VOTES</small></div></div><p>${compatibilityBadge(map)}</p><p class="hint">${escapeHTML(c.reason)}</p><p title="${escapeHTML(map.uploaded || v.createdAt || "")}">Uploaded ${escapeHTML(relativeDate(map.uploaded || v.createdAt))}<br>Curated: ${bool(map.curatedAt)} · Ranked: ${bool(map.ranked || map.blRanked)} · Tags: ${escapeHTML((map.tags || []).join(", "))}</p><p class="description">${escapeHTML(map.description || "No mapper description supplied.")}</p><div class="table-wrap"><table><thead><tr><th>Chart</th><th>Notes / bombs / walls</th><th>NPS</th><th>NJS</th><th>Stars</th><th>Requirements</th></tr></thead><tbody>${diffs.map((d) => `<tr><td>${escapeHTML(d.characteristic)} ${escapeHTML(d.difficulty)}</td><td>${number(d.notes)} / ${number(d.bombs)} / ${number(d.obstacles)}</td><td>${number(d.nps)}</td><td>${number(d.njs)}</td><td>${number(d.stars || d.blStars)}</td><td>${escapeHTML([d.ne && "Noodle Extensions", d.me && "Mapping Extensions", d.chroma && "Chroma", d.cinema && "Cinema"].filter(Boolean).join(", ") || "Vanilla")}</td></tr>`).join("")}</tbody></table></div><p class="hint">Support: validated vanilla V2/V3/V4, arcs, chains, native V4 NJS/lighting, available stock environments, Standard, One Saber, No Arrows and 90°/360° characteristics. Expanded features require OrBeats 0.8075; hardware validation is pending. Mod-dependent effects remain unsupported. Unsupported formats and requirements are explicitly refused, not silently removed. Original maps are downloaded and converted in temporary storage, not kept as a local song library.</p><details><summary>Complete BeatSaver API data</summary><pre>${escapeHTML(JSON.stringify(map, null, 2))}</pre></details><p><a href="https://beatsaver.com/maps/${escapeHTML(map.id)}" target="_blank" rel="noopener noreferrer">Open on BeatSaver ↗</a></p>`;
	updateQueueButtons();
	$("details").showModal();
}
function cleanLogLine(line) {
	const text = String(line).replace(/^\s*\[additive\]\s*/i, "").trim();
	if (!text || /^Project:/i.test(text) || /^Retaining \d+ (library entries|other songs)/i.test(text) || /OrBeats Pipeline \d/.test(text)) return null;
	return text;
}
function updateLogControls() {
	const open = !$('diagnostics').hidden;
	$('toggle-log').textContent = open ? 'Hide log' : 'Show log';
	$('toggle-log').setAttribute('aria-expanded', String(open));
	$('log-title').textContent = state.logRunning ? 'Installation log' : 'Last installation log';
	$('log-follow').textContent = state.logFollowing ? 'Following latest' : 'Reading earlier output';
	$('log-latest').hidden = state.logFollowing;
}
function followLogTail() {
	// Never scroll the dialog/page or steal focus. Closed panels retain the
	// reader's follow preference; recheck it when the animation frame runs.
	if (state.logFollowing && !$('diagnostics').hidden && $('downloads').open) {
		requestAnimationFrame(() => {
			if (state.logFollowing && !$('diagnostics').hidden && $('downloads').open)
				$('log').scrollTop = $('log').scrollHeight;
		});
	}
}
function setLogOpen(open) {
	$('diagnostics').hidden = !open;
	updateLogControls();
	followLogTail();
}
function logLines(lines) {
	if (!lines.length) return;
	state.rawLog += lines.join("\n") + "\n";
	const clean = lines.map(cleanLogLine).filter(Boolean);
	if (clean.length) {
		$("log").textContent += clean.join("\n") + "\n";
		$("job-stage").textContent = clean.at(-1);
		followLogTail();
	}
}
function updateQueueButtons() {
	const queued = new Set([...state.queue.pending, ...(state.queue.active ? [state.queue.active] : [])].map(e => e.map_id));
	for (const button of document.querySelectorAll("[data-install]")) {
		button.disabled = button.dataset.unsupported === "true" || state.removing || queued.has(button.dataset.install) || state.adding.has(button.dataset.install);
		button.textContent = queued.has(button.dataset.install) ? "Queued ✓" : button.dataset.unsupported === "true" ? "Not supported" : "Add to queue ＋";
	}
	for (const button of document.querySelectorAll("[data-retry-map]")) {
		const key = button.dataset.retryMap;
		button.disabled = state.removing || queued.has(key) || state.adding.has(key);
		button.textContent = queued.has(key) ? "Queued ✓" : "Retry";
	}
}
function renderQueue(queue) {
	state.queue = queue;
	const count = queue.pending.length + (queue.active ? 1 : 0);
	const failed = Boolean(state.queueError || queue.error || (queue.paused && (queue.history[0]?.status === "failed" || queue.history[0]?.status === "cancelled")));
	$("download-count").hidden = !count;
	$("download-count").textContent = String(count);
	$("download-activity").hidden = !state.busy && !failed;
	$("download-activity").classList.toggle("failed", failed);
	$("open-downloads").classList.toggle("is-active", state.busy);
	$("open-downloads").setAttribute("aria-label", `Downloads, ${count} maps${failed ? ", attention needed" : state.busy ? ", installation in progress" : ""}`);
	$("queue-message").textContent = state.queueError || queue.message || "Add maps from Discover, then start when Beat Saber is closed.";
	$("queue-start").disabled = state.removing || !queue.pending.length || (!queue.paused && Boolean(queue.active));
	$("queue-start").textContent = queue.history.length ? "Resume queue" : "Start queue";
	$("queue-pause").disabled = queue.paused || !count;
	$("queue-clear").disabled = !queue.pending.length;
	$("queue-total").textContent = String(queue.pending.length);
	const signature = JSON.stringify([queue.pending, queue.history]);
	if (state.queueSignature !== signature) {
		state.queueSignature = signature;
		$("queue-list").innerHTML = queue.pending.length ? queue.pending.map((entry, i) => `<li><span class="queue-number">${i + 1}</span><div><strong>${escapeHTML(entry.title)}</strong><small>BeatSaver ${escapeHTML(entry.map_id)} · Waiting</small></div><button data-queue-remove="${escapeHTML(entry.id)}" aria-label="Remove ${escapeHTML(entry.title)} from queue">×</button></li>`).join("") : '<li class="queue-empty">Your next beat starts in Discover.</li>';
		$("queue-history").innerHTML = queue.history.length ? queue.history.map(entry => `<li><span class="queue-result ${escapeHTML(entry.status)}">${entry.status === "complete" ? "✓" : "!"}</span><div><strong>${escapeHTML(entry.title)}</strong><small>${escapeHTML(entry.status)}${entry.error ? ` · ${escapeHTML(entry.error)}` : ""}</small></div>${["failed", "cancelled"].includes(entry.status) ? `<button type="button" data-queue-retry="${escapeHTML(entry.id)}" data-retry-map="${escapeHTML(entry.map_id)}" aria-label="Retry ${escapeHTML(entry.title)}">Retry</button>` : ""}</li>`).join("") : '<li class="queue-empty">Completed installations will appear here.</li>';
	}
	updateQueueButtons();
	updateLibraryControls();
}
async function install(key, retryTitle = null) {
	if (state.removing) return;
	if (state.adding.has(key) || state.queue.pending.some(e => e.map_id === key) || state.queue.active?.map_id === key) return;
	state.adding.add(key);
	updateQueueButtons();
	try {
		const map = state.maps.find(m => m.id === key) || (state.selected?.id === key ? state.selected : null);
		if (map && compatibility(map).status === "unsupported") throw Error(compatibility(map).reason);
		await api("/api/install-queue", { method: "POST", body: JSON.stringify({ map_id: key, title: retryTitle ?? (map ? mapData(map).title : key) }) });
		state.queueError = "";
		renderQueue(await api("/api/install-queue"));
	} catch (e) {
		state.queueError = e.message;
		renderQueue(state.queue);
	} finally {
		state.adding.delete(key);
		updateQueueButtons();
	}
}
async function queueAction(action, entryId = null) {
	if (action === "start" && state.removing) return;
	try {
		if (action === "start" && !await confirmAction("Start installation queue?", "Keep Beat Saber fully closed and GoldHEN FTP on until the queue finishes. Failed maps are skipped; other maps continue. Pause or Cancel stops the queue.", "Start queue")) return;
		const path = entryId ? "/api/install-queue/" + encodeURIComponent(entryId) : "/api/install-queue/" + action;
		state.queueError = "";
		renderQueue(await api(path, { method: entryId ? "DELETE" : "POST" }));
	} catch (e) {
		state.queueError = e.message;
		renderQueue(state.queue);
	}
}
async function pollActivity() {
	try {
		const [progress, queue] = await Promise.all([
			api(`/api/jobs/lines?after=${state.lineIndex}&job_id=${encodeURIComponent(state.jobId || "")}`),
			api("/api/install-queue"),
		]);
		state.busy = progress.running || Boolean(queue.active);
		state.logRunning = Boolean(progress.running);
		if (progress.job) {
			if (state.jobId !== progress.job.id) {
				state.jobId = progress.job.id;
				state.rawLog = "";
				$("log").textContent = "";
				$("job-stage").textContent = "";
				$("log-feedback").textContent = "";
				state.logFollowing = true;
			}
			state.lineIndex = progress.index;
			logLines(progress.lines);
			$("job").hidden = false;
			$("job-title").textContent = progress.running ? (queue.active?.title || "Installation in progress") : progress.job.cancelled ? "Installation cancelled" : progress.job.exit_code === 0 ? "Installation complete" : "Installation stopped";
			$("cancel-job").disabled = !progress.running;
			$("progress").classList.toggle("complete", !progress.running && progress.job.exit_code === 0);
			$("progress").classList.toggle("stopped", !progress.running && progress.job.exit_code !== 0);
			$("progress").setAttribute("aria-valuetext", progress.running ? "Working; exact progress unavailable" : progress.job.exit_code === 0 ? "Installation complete" : "Installation stopped");
		}
		updateLogControls();
		state.queueError = state.queueError === "Connection interrupted. Refresh or wait to reconnect; do not retry installations blindly." ? "" : state.queueError;
		renderQueue(queue);
	} catch {
		state.queueError = "Connection interrupted. Refresh or wait to reconnect; do not retry installations blindly.";
		renderQueue(state.queue);
	} finally {
		setTimeout(pollActivity, 900);
	}
}
function removalBlockReason() {
	if (state.busy || state.queue.active)
		return "A job is running. Wait for it to finish before removing maps.";
	const n = state.queue.pending.length;
	return n ? `${n} ${n === 1 ? "map is" : "maps are"} waiting in Downloads${state.queue.paused ? " (queue paused)" : ""}. Finish the queue or clear pending maps in Downloads before removing songs.` : "";
}
function updateLibraryControls() {
	const selected = state.selectedSongs.size;
	const reason = removalBlockReason();
	$("library-guard").hidden = !reason;
	$("library-guard-message").textContent = reason;
	$("library-selection").hidden = !state.editingSelection || !state.songs.length;
	$("edit-selection").hidden = !state.songs.length;
	$("edit-selection").textContent = state.editingSelection ? "Done editing" : "Edit selection";
	$("edit-selection").setAttribute("aria-pressed", String(state.editingSelection));
	$("edit-selection").disabled = state.removing || state.libraryLoading || !state.libraryReady;
	$("installed").classList.toggle("editing-selection", state.editingSelection);
	$("selection-count").textContent = `${selected} selected`;
	$("remove-selected").textContent = `Remove selected${selected ? ` (${selected})` : ""}`;
	$("remove-selected").disabled = !selected || state.removing || state.libraryLoading || !state.libraryReady || Boolean(reason);
	$("select-all-songs").disabled = state.removing || state.libraryLoading || !state.libraryReady || !state.songs.length;
	$("clear-selection").disabled = state.removing || state.libraryLoading || !selected;
	$("refresh-library").disabled = state.removing || state.libraryLoading;
	for (const tile of document.querySelectorAll("[data-song-tile]")) {
		const selected = state.selectedSongs.has(tile.dataset.songTile);
		tile.classList.toggle("is-selected", state.editingSelection && selected);
		tile.tabIndex = state.editingSelection ? 0 : -1;
		if (state.editingSelection) {
			tile.setAttribute("role", "checkbox");
			tile.setAttribute("aria-checked", String(selected));
			tile.setAttribute("aria-disabled", String(state.removing || state.libraryLoading || !state.libraryReady));
		} else {
			tile.removeAttribute("role");
			tile.removeAttribute("aria-checked");
			tile.removeAttribute("aria-disabled");
		}
	}
	for (const button of document.querySelectorAll("[data-remove]")) {
		button.disabled = state.removing || state.libraryLoading || !state.libraryReady || Boolean(reason);
		button.title = reason || "Remove this custom map from your PS4";
	}
}
async function loadLibrary() {
	if (state.libraryLoading) return;
	state.libraryLoading = true;
	updateLibraryControls();
	$("installed").innerHTML =
		'<div class="empty">Reading maps directly from your PS4…</div>';
	try {
		const result = await api("/api/orbis/library");
		state.songs = result.songs;
		state.libraryReady = true;
		if (!state.songs.length) state.editingSelection = false;
		state.selectedSongs = new Set([...state.selectedSongs].filter(id => state.songs.some(s => s.id === id)));
		const labels = ["Easy", "Normal", "Hard", "Expert", "ExpertPlus"];
		$("installed").innerHTML = state.songs.length
			? state.songs
					.map(
						(s, i) =>
							`<article class="card" data-song-tile="${escapeHTML(s.id)}" aria-label="${escapeHTML(s.title)}">${installedArtwork(s.title, s.id)}<h3>${escapeHTML(s.title)}</h3><p class="artist">${escapeHTML(s.author)}</p><p class="mapper">${escapeHTML(s.info?.metadata?.levelAuthorName || "Mapper not recorded for this older install")}</p><div class="meta"><span>◷ ${duration(s.duration)}</span><span>♫ ${number(s.bpm)} BPM</span><span>${(s.bytes / 1048576).toFixed(1)} MB</span></div><div class="diffs">${diffBadges(installedCharts(s))}</div><div class="card-bottom"><button data-installed-info="${i}">Map information</button><button class="danger" data-remove="${escapeHTML(s.id)}">Remove</button></div></article>`,
					)
					.join("")
			: '<div class="empty">Your library is empty. Find a map in Discover to start a new session.</div>';
	} catch (e) {
		state.libraryReady = false;
		$("installed").innerHTML =
			'<div class="empty">Your PS4 is unreachable. Turn it on, enable GoldHEN FTP and check the connection in Settings.</div>';
		throw e;
	} finally {
		state.libraryLoading = false;
		updateLibraryControls();
	}
}
function installedInfo(index) {
	const s = state.songs[index];
	if (s.info?.metadata) {
		state.maps.push(s.info);
		showDetails(state.maps.length - 1, s.id);
		updateLibraryControls();
		return;
	}
	const names = ["Easy", "Normal", "Hard", "Expert", "ExpertPlus"];
	$("detail-content").innerHTML =
		`<div class="detail-top">${installedArtwork(s.title, s.id)}<div><h2>${escapeHTML(s.title)}</h2><p>${escapeHTML(s.author)} · ${duration(s.duration)} · ${number(s.bpm)} BPM</p></div></div><p class="hint">BeatSaver metadata was not saved by this older import. These are the verified native-library values, not guessed online details.</p><div class="table-wrap"><table><tr><th>Difficulty</th><th>Notes</th><th>Bombs</th><th>Walls</th><th>NJS</th></tr>${installedCharts(s).map(d => `<tr><td>${escapeHTML(d.characteristic + " " + d.difficulty)}</td>${d.stats.slice(0,4).map(v=>`<td>${number(v)}</td>`).join("")}</tr>`).join("")}</table></div><details><summary>Installed descriptor</summary><pre>${escapeHTML(JSON.stringify(s, null, 2))}</pre></details>`;
	updateQueueButtons();
	$("details").showModal();
}
async function removeMap(id) {
	return removeMaps([id]);
}
async function removeMaps(ids) {
	if (state.removing || state.libraryLoading || $("confirm-action").open) return;
	$("library-feedback").textContent = "";
	if (!state.libraryReady) { notify("Refresh the library before removing maps."); return; }
	const blocked = removalBlockReason();
	if (blocked) {
		notify(blocked);
		updateLibraryControls();
		return;
	}
	const songs = [...new Set(ids)].map(id => state.songs.find(s => s.id === id));
	if (!songs.length || songs.some(s => !s)) return;
	const plural = songs.length !== 1;
	if (!await confirmAction(plural ? `Remove ${songs.length} maps?` : "Remove map?",
		`${songs.map(s => s.title).join("; ")}\n\nOnly these custom maps will be removed. Keep Beat Saber fully closed and FTP enabled. Maps are removed one at a time; removal stops on the first error.`,
		plural ? `Remove ${songs.length} maps` : "Remove")) return;
	if (state.removing) return;
	if ($("details").open) $("details").close();
	previewAudio.pause();
	state.removing = true;
	updateLibraryControls();
	renderQueue(state.queue);
	let completed = 0, cleanup = 0, resultMessage = "";
	try {
		for (const song of songs) {
			// A queue started in another browser tab must still block the next DELETE.
			// The server independently enforces this plus the per-map title/FTP lock.
			const reason = removalBlockReason();
			if (reason) throw Error(reason);
			$("library-feedback").textContent = `Removing ${completed + 1} of ${songs.length}: ${song.title}…`;
			const result = await api("/api/orbis/library/" + encodeURIComponent(song.id), { method: "DELETE" });
			completed++;
			cleanup += result.cleanup_pending?.length || 0;
			state.selectedSongs.delete(song.id);
		}
		resultMessage = `${completed === 1 ? "Map removed" : `${completed} maps removed`}.${cleanup ? " Some unreferenced files need cleanup." : ""} Changes appear on the next game launch.`;
	} catch (e) {
		resultMessage = `Removal stopped: ${completed} of ${songs.length} removed. ${e.message} Refresh the library before retrying if the connection was lost.`;
	} finally {
		try { await loadLibrary(); }
		catch (e) { resultMessage += ` Could not refresh the library: ${e.message}`; }
		state.removing = false;
		$("library-feedback").textContent = "";
		updateLibraryControls();
		renderQueue(state.queue);
		notify(resultMessage);
	}
}
async function loadSettings() {
	const s = await api("/api/orbis/settings");
	$("ip").value = s.ip;
	$("template").value = s.template;
	$("updates").textContent = s.updates.message;
}
async function initialize() {
	try {
		document.documentElement.dataset.theme =
			localStorage.getItem("orbis-theme") ||
			(matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
	} catch {
		document.documentElement.dataset.theme = "light";
	}
	for (const b of document.querySelectorAll("nav button"))
		b.addEventListener("click", () => setTab(b.dataset.tab));
	$("open-downloads").onclick = () => { if (!$("downloads").open) $("downloads").showModal(); followLogTail(); };
	$("close-downloads").onclick = () => $("downloads").close();
	// Share the geometry/gesture guard across panels: padding is not backdrop,
	// and a drag starting inside must never dismiss a dialog on release outside.
	for (const dialog of [$("downloads"), $("details")]) {
		let backdropPress = false;
		const outside = (e) => {
			const r = dialog.getBoundingClientRect();
			return e.target === dialog &&
				(e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom);
		};
		dialog.addEventListener("pointerdown", (e) => {
			backdropPress = e.isPrimary && e.button === 0 && outside(e);
		});
		dialog.addEventListener("pointercancel", () => { backdropPress = false; });
		dialog.addEventListener("close", () => { backdropPress = false; });
		dialog.addEventListener("click", (e) => {
			if (backdropPress && outside(e)) dialog.close();
			backdropPress = false;
		});
	}
	$("queue-start").onclick = () => queueAction("start");
	$("queue-pause").onclick = () => queueAction("pause");
	$("queue-clear").onclick = () => queueAction("clear");
	$("theme-settings").onclick = theme;
	$("close-details").onclick = () => $("details").close();
	$("search-form").onsubmit = safely(async (e) => {
		e.preventDefault();
		await search();
	});
	for (const id of ["sort", "period"]) $(id).onchange = safely(() => search());
	$("previous").onclick = safely(async () => {
		if (state.page) state.page--;
		await search(false);
	});
	$("next").onclick = safely(async () => {
		state.page++;
		await search(false);
	});
	$("refresh-library").onclick = safely(loadLibrary);
	$("edit-selection").onclick = () => {
		if (state.removing || state.libraryLoading || !state.libraryReady) return;
		state.editingSelection = !state.editingSelection;
		state.selectedSongs.clear();
		updateLibraryControls();
	};
	$("library-downloads").onclick = () => { if (!$("downloads").open) $("downloads").showModal(); followLogTail(); };
	$("select-all-songs").onclick = () => {
		if (state.removing || state.libraryLoading) return;
		state.selectedSongs = new Set(state.songs.map(s => s.id));
		updateLibraryControls();
	};
	$("clear-selection").onclick = () => {
		if (state.removing || state.libraryLoading) return;
		state.selectedSongs.clear();
		updateLibraryControls();
	};
	$("remove-selected").onclick = safely(() => removeMaps([...state.selectedSongs]));
	const toggleTile = (e) => {
		const tile = e.target.closest("[data-song-tile]");
		if (!tile || !state.editingSelection || state.removing || state.libraryLoading || !state.libraryReady) return;
		if (state.selectedSongs.has(tile.dataset.songTile)) state.selectedSongs.delete(tile.dataset.songTile);
		else state.selectedSongs.add(tile.dataset.songTile);
		updateLibraryControls();
	};
	$("installed").addEventListener("click", toggleTile);
	$("installed").addEventListener("keydown", e => {
		if (e.target.matches("[data-song-tile]") && state.editingSelection && [" ", "Enter"].includes(e.key)) {
			e.preventDefault(); toggleTile(e);
		}
	});
	document.addEventListener(
		"click",
		safely(async (e) => {
			const b = e.target.closest("button");
			if (!b || (state.editingSelection && b.closest("#installed"))) return;
			if (b.dataset.preview) await togglePreview(b);
			if (b.dataset.detail !== undefined) showDetails(Number(b.dataset.detail));
			if (b.dataset.install) await install(b.dataset.install);
			if (b.dataset.queueRemove) await queueAction("remove", b.dataset.queueRemove);
			if (b.dataset.remove) await removeMap(b.dataset.remove);
			if (b.dataset.installedInfo !== undefined)
				installedInfo(Number(b.dataset.installedInfo));
		}),
	);
	$("connection").onsubmit = safely(async (e) => {
		e.preventDefault();
		const body = { ip: $("ip").value.trim() };
		await api("/api/orbis/settings", {
			method: "POST",
			body: JSON.stringify(body),
		});
		notify(
			"Connection saved. Test it with your PS4 on and GoldHEN FTP enabled.",
		);
	});
	$("template-settings").onsubmit = safely(async (e) => {
		e.preventDefault();
		await api("/api/orbis/settings", {method: "POST", body: JSON.stringify({ip: $("ip").value.trim(), template: $("template").value.trim()})});
		notify("Conversion seed saved. No files were uploaded.");
	});
	$("test-connection").onclick = safely(async () => {
		const button = $("test-connection");
		button.disabled = true;
		try {
			const result = await api("/api/orbis/connection/test", {
				method: "POST",
				body: JSON.stringify({ip: $("ip").value.trim()}),
			});
			notify(`FTP connected to ${result.ip}:2121. Save connection to use this address. Library setup was not checked.`);
		} finally {
			button.disabled = false;
		}
	});
	async function checkPluginVersion() {
        const target = $("plugin-version");
        target.textContent = "Checking the installed plugin binary…";
        try {
            const r = await api("/api/orbis/plugin");
            const installed = !r.installed ? "Not installed" : r.installed_version || "Unknown binary";
            const checks = r.capability_matches && r.declared_version_matches ? "Capability matches" : "Capability needs review";
            const registration = r.registration === "registered_once" ? "Registered once" : "Registration needs review";
            target.textContent = `Installed: ${installed} · Available: ${r.available_version || "Not built"}. ${checks} · ${registration}${r.max_songs ? ` · ${r.max_songs}-song profile` : ""}. Version read from disk, not a running-game check.`;
        } catch (e) {
            target.textContent = "Version check failed. Check the PS4 connection and try again.";
            throw e;
        }
    }
    $("check-plugin-version").onclick = safely(checkPluginVersion);
	$("deploy-plugin").onclick = safely(async () => {
		if (state.busy) throw Error("Wait for the active job.");
		if (
			!await confirmAction("Update plugin?", "Beat Saber must be closed. Other plugins are preserved. Recovery backups stay on this computer.", "Update")
		)
			return;
		notify(
			"Installing OrBeats with readback and local recovery. Keep Beat Saber closed.",
		);
		const r = await api("/api/orbis/plugin", { method: "POST" });
		notify(r.message);
        await checkPluginVersion();
	});
    async function checkExtrasVersion() {
        const r = await api("/api/orbis/extras");
        $("extras-version").textContent = `Installed: ${r.installed_version || (r.installed ? "Unknown binary" : "Not installed")} · Bundled: ${r.available_version || "Unavailable"} · ${r.registration}. Disk check, not an in-game check.`;
    }
    $("check-extras-version").onclick = safely(checkExtrasVersion);
    $("deploy-extras").onclick = safely(async () => {
        if (state.busy) throw Error("Wait for the active job.");
        if (!await confirmAction("Install Extras?", "Beat Saber must be fully closed. Extras will be enabled for CUSA12878. Existing songs and health settings are preserved.", "Install")) return;
        notify("Installing Extras with readback and local recovery. Keep Beat Saber closed.");
        const r = await api("/api/orbis/extras", {method: "POST"});
        notify(r.message); await checkExtrasVersion();
    });
    $("check-updates").onclick = safely(async () => {
        $("updates").textContent = "Checking official GitHub release…";
        const r = await api("/api/orbis/updates");
        $("updates").textContent = r.message + (r.versions ? " " + Object.entries(r.versions).map(([k,v]) => `${k}: bundled ${v.current || "unknown"}, latest ${v.latest}${v.update_available ? " (update available)" : ""}`).join(" · ") : "");
    });
    $("copy-release-link").onclick = safely(async () => { await navigator.clipboard.writeText("https://github.com/Wkrotik/OrBeats/releases/latest"); notify("Official download link copied."); });
    for (const kind of ["main", "extras"]) $("release-" + kind).onclick = safely(async () => {
        if (state.busy) throw Error("Wait for the active job.");
        if (!await confirmAction("Install latest " + kind + "?", "Download from the official GitHub release, verify its SHA-256, then install with readback and local recovery. Beat Saber must be fully closed.", "Download and install")) return;
        notify("Downloading and verifying official plugin. Keep Beat Saber closed.");
        const r = await api("/api/orbis/updates/" + kind, {method:"POST"}); notify(r.message);
        await (kind === "main" ? checkPluginVersion() : checkExtrasVersion());
    });
	$("cancel-job").onclick = safely(async () => {
		await api("/api/jobs/cancel", { method: "POST" });
		$("queue-message").textContent = "Stopping installation. The queue is paused; wait for the process to stop.";
	});
	$('toggle-log').onclick = () => setLogOpen($('diagnostics').hidden);
	$('log-latest').onclick = () => {
		state.logFollowing = true;
		updateLogControls();
		followLogTail();
	};
	$('log').addEventListener('scroll', () => {
		if ($('diagnostics').hidden || !$('downloads').open) return;
		const log = $('log');
		state.logFollowing = log.scrollHeight - log.clientHeight - log.scrollTop <= 4;
		updateLogControls();
	});
	updateLogControls();
	$("copy-log").onclick = safely(async () => {
		await navigator.clipboard.writeText(state.rawLog);
		$("log-feedback").textContent = "Copied full diagnostic log.";
	});
	$("save-log").onclick = () => {
		const url = URL.createObjectURL(
			new Blob([state.rawLog], { type: "text/plain" }),
		);
		const a = document.createElement("a");
		a.href = url;
		a.download = "orbeats-install-report.txt";
		a.click();
		URL.revokeObjectURL(url);
	};
	await loadSettings();
	const ping = await api("/api/ping");
	$("versions").textContent =
		`App ${ping.webapp_version} · Pipeline ${ping.pipeline_version}`;
	setTab(
		["library", "settings"].includes(location.hash.slice(1))
			? location.hash.slice(1)
			: "discover",
	);
	pollActivity();
	await search();
}
document.addEventListener("click", (event) => {
	const button = event.target.closest("[data-queue-retry]");
	if (!button || button.disabled) return;
	const entry = state.queue.history.find(e => e.id === button.dataset.queueRetry);
	if (entry && ["failed", "cancelled"].includes(entry.status)) install(entry.map_id, entry.title);
});
document.addEventListener(
	"error",
	(event) => {
		const img = event.target;
		if (!(img instanceof HTMLImageElement) || img.src.endsWith("/static/map-placeholder.svg")) return;
		const url = new URL(img.src);
		if (url.pathname.startsWith("/api/orbis/library/") && !img.dataset.retried) {
			img.dataset.retried = "true";
			url.searchParams.set("retry", "1");
			setTimeout(() => { if (img.isConnected) img.src = url.href; }, 500);
			return;
		}
		img.src = "/static/map-placeholder.svg";
	},
	true,
);
initialize().catch((e) => notify(e.message));
