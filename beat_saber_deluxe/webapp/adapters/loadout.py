"""
loadout.py — the song-loadout merge (pure functions, zero I/O).

Both new tabs need the SAME data: every stock song in the catalog, joined with
what is currently deployed over it. Three sources:

1. `beat_saber_song_ids.json` (local catalog) — every pack, slot songID,
   stock songName/songAuthorName. THE join key is the slot `songID` —
   redirects reference slots as `BeatmapLevelsData/<songID>`.
2. Live `redirects.json` (from the PS4) — a slot appears here ⇔ a custom
   bundle is deployed over it (`BeatmapLevelsData/<songID>` → `<songID>_v3.bundle`).
3. Live `song_metadata.json` (from the PS4) — keyed by STOCK songName (NOT
   songID!). `song_names[<stock name>] = "<Custom> / <Artist>"`. Joining to
   the catalog needs case/space-insensitive matching — the real files have
   `'You Should See Me In A Crown '` (trailing space in the catalog) vs
   `'You Should See Me In A Crown'` (no space in song_metadata).

The PS4 is production (plan §9.4 invariant 6): this module only READS state
and renders it; clearing a slot goes through the pipeline subprocess
(`--clear-target-song <songID>`) via the runner, never a direct state write.
"""

from __future__ import annotations

import json

from . import paths


def _norm(name: str) -> str:
    """Normalize a song name for the metadata join (case/space/punct-fold)."""
    return " ".join(name.strip().lower().split())


def load_catalog() -> dict:
    """Parse beat_saber_song_ids.json → {pack: [{songID, songName, songAuthorName}...]}."""
    with open(paths.SONG_CATALOG, encoding="utf-8") as f:
        data = json.load(f)
    return {a["pack"]: a["songs"] for a in data.get("albums", [])}


def merge_loadout(catalog: dict, redirects: dict | None,
                  song_names: dict | None,
                  song_artists: dict | None,
                  slot_bundles: list | None = None) -> dict:
    """
    Build the per-pack song tables.

    Deployed-truth model (verified against live PS4 state + plugin source,
    Exp 245): the game serves a custom song ONLY via its redirects.json entry
    (open_hook matches the redirect table). A `<slot>_v3.bundle` in the AFR
    dir WITHOUT a redirect is a STALE payload — uploaded, not served. Both
    are surfaced distinctly; neither is hidden.

    Args:
        catalog: {pack: [song dict with songID/songName/songAuthorName]}
        redirects: live redirects dict (None = couldn't read — status carried)
        song_names: live song_metadata song_names (None = couldn't read)
        song_artists: live song_metadata song_artists (may be empty/None)
        slot_bundles: live AFR `<slot>_v3.bundle` stem list (None = unread)

    Returns:
        {
          "packs": [
            {"pack": str, "songs": [
              {"songID", "songName", "songAuthorName",
               "customDeployed": bool,     # SERVED: redirect present for slot
               "staleBundle": bool,        # bundle file present, NO redirect
               "customName", "customArtist",   # from song_metadata (or None)
               "metadataEntry"}                # raw metadata value, diagnostics
            ]}
          ],
          "unmatchedMetadata": [...], "unmatchedBundles": [...],
          "redirectedSlotCount", "customNameCount", "staleBundleCount",
        }
    """
    redirects = redirects or {}
    song_names = song_names or {}
    song_artists = song_artists or {}
    bundle_set = {b.lower() for b in (slot_bundles or [])}

    # Deployed slots: BeatmapLevelsData/<songID> → <songID>_v3.bundle
    deployed_slots = {k.split("BeatmapLevelsData/", 1)[1].lower()
                      for k in redirects if k.startswith("BeatmapLevelsData/")}

    # Metadata join: normalized stock songName → (custom display value, raw key)
    meta_by_norm: dict[str, tuple[str, str]] = {}
    for raw_key, value in song_names.items():
        meta_by_norm[_norm(raw_key)] = (value, raw_key)

    catalog_ids_lower = {s["songID"].lower()
                         for songs in catalog.values() for s in songs}
    matched_bundles: set[str] = set()
    packs_out = []
    matched_meta_keys: set[str] = set()
    for pack, songs in catalog.items():
        rows = []
        for s in songs:
            sid, sname = s["songID"], s["songName"]
            deployed = sid.lower() in deployed_slots
            stale = (not deployed) and (sid.lower() in bundle_set)
            if sid.lower() in bundle_set:
                matched_bundles.add(sid.lower())
            row = {
                "songID": sid,
                "songName": sname,
                "songAuthorName": s.get("songAuthorName", ""),
                "customDeployed": deployed,
                "staleBundle": stale,
                "customName": None,
                "customArtist": None,
                "metadataEntry": None,
            }
            hit = meta_by_norm.get(_norm(sname))
            if hit is not None:
                value, raw_key = hit
                matched_meta_keys.add(raw_key)
                row["metadataEntry"] = value
                # song_names value format: "<Custom Song> / <Artist>" (the
                # pipeline's combined display line). Artist may be missing.
                if "/" in value:
                    title, _, artist = value.partition("/")
                    row["customName"] = title.strip() or None
                    row["customArtist"] = artist.strip() or None
                else:
                    row["customName"] = value.strip() or None
            rows.append(row)
        packs_out.append({
            "pack": pack,
            "deployedCount": sum(1 for r in rows if r["customDeployed"]),
            "songs": rows,
        })

    return {
        "packs": packs_out,
        "unmatchedMetadata": sorted(set(song_names) - matched_meta_keys),
        "unmatchedBundles": sorted(b for b in bundle_set - matched_bundles
                                   - catalog_ids_lower),
        "redirectedSlotCount": len(deployed_slots),
        "customNameCount": len(song_names),
        "staleBundleCount": sum(1 for p in packs_out for r in p["songs"]
                                if r["staleBundle"]),
    }


def loadout_from_state(state: dict) -> dict:
    """
    Convenience: merge the catalog with a read_deployment_state() payload.

    Read failures stay explicit (never rendered as "nothing deployed"):
    a missing redirects half yields customDeployed=False rows PLUS a
    redirectsReadError the UI must surface; missing metadata yields no
    custom names PLUS metadataReadError.
    """
    return merge_loadout(
        load_catalog(),
        None if state.get("redirects_read_error") else state.get("redirects", {}),
        None if state.get("metadata_read_error") else state.get("song_names", {}),
        state.get("song_artists", {}),
        None if state.get("afr_read_error") else state.get("slot_bundles", []),
    )
