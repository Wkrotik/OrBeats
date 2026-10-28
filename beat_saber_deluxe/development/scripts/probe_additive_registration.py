#!/usr/bin/env python3
"""Read-only reconnaissance for additive PS4 song packs; never emits live hooks.

Supply Il2CppDumper's dump.cs and/or the game's aa/catalog.json from YOUR build.
Addresses are reported as unverified evidence, not callable function pointers.
No game files are modified and no console/network access is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

TARGET_CLASSES = frozenset(
    {
        "BeatmapLevelsModel",
        "BeatmapLevelPack",
        "PackDefinitionSO",
        "BeatmapLevelLoader",
        "BeatmapLevelDataLoader",
        "IBeatmapLevelLoader",
        "BeatmapLevelPackSO",
        "BeatmapLevelCollectionSO",
        "BeatmapLevelPackCollectionSO",
        "BeatmapLevelSO",
        "BeatmapLevel",
        "BeatmapLevelsRepository",
        "AdditionalContentModel",
        "AnnotatedBeatmapLevelCollectionsViewController",
        "LevelCollectionViewController",
        "StandardLevelDetailViewController",
    }
)
TYPE_DECL = re.compile(
    r"^\s*(?:(?:public|private|protected|internal|sealed|abstract|static|partial|readonly)\s+)*"
    r"(?P<kind>class|struct|interface|enum)\s+(?P<name>[^\s:{]+)"
)
METHOD_ADDRESS = re.compile(r"\b(RVA|Offset|VA):\s*(0x[0-9a-fA-F]+|-1)\b")
FIELD_OFFSET = re.compile(r"//\s*(0x[0-9a-fA-F]+)\s*$")


def inspect_dump(text: str) -> dict:
    """Extract candidate declarations, preserving signatures and dump line numbers.

    Il2CppDumper emits each type (including nested types) as a separate declaration.
    This intentionally does not parse C# or assume a Quest/PC type layout matches PS4.
    """
    classes = []
    namespace = ""
    current = None
    pending_address = None
    pending_line = None
    for line_number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("// Namespace:"):
            namespace = stripped.partition(":")[2].strip()
            current = None
            pending_address = None
            continue
        declaration = TYPE_DECL.match(line)
        if declaration:
            name = declaration.group("name")
            current = None
            pending_address = None
            if name in TARGET_CLASSES:
                current = {
                    "name": name,
                    "namespace": namespace,
                    "kind": declaration.group("kind"),
                    "line": line_number,
                    "declaration": stripped,
                    "fields": [],
                    "methods": [],
                }
                classes.append(current)
            continue
        if current is None:
            continue
        if stripped.startswith("//"):
            addresses = dict(METHOD_ADDRESS.findall(stripped))
            # A new RVA comment always replaces the old one, including RVA: -1.
            if "RVA" in addresses:
                pending_address = addresses
                pending_line = line_number
            continue
        if pending_address is not None:
            if not stripped or stripped.startswith("["):
                continue  # method attributes can sit between its RVA and signature
            if "(" in stripped and ")" in stripped:
                current["methods"].append(
                    {
                        "signature": stripped,
                        "line": line_number,
                        "address_line": pending_line,
                        "addresses": pending_address,
                        "hook_verified": False,
                    }
                )
            pending_address = None
        elif ";" in stripped and "(" not in stripped:
            offset = FIELD_OFFSET.search(stripped)
            current["fields"].append(
                {
                    "declaration": stripped,
                    "line": line_number,
                    "offset": offset.group(1) if offset else None,
                }
            )
    found = {c["name"] for c in classes}
    return {"classes": classes, "missing_candidates": sorted(TARGET_CLASSES - found)}


def inspect_catalog(catalog: object) -> dict:
    """Inventory evidence only; do not rewrite Addressables' encoded entry tables."""
    if not isinstance(catalog, dict):
        raise ValueError("Addressables catalog must be a JSON object")
    ids = catalog.get("m_InternalIds")
    # PS4 catalogs use m_resourceTypes; retain support for earlier synthetic inputs.
    types_key = "m_resourceTypes" if "m_resourceTypes" in catalog else "m_ResourceTypes"
    resource_types = catalog.get(types_key)
    if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
        raise ValueError("catalog m_InternalIds must be an array of strings")
    if not isinstance(resource_types, list):
        raise ValueError(f"catalog {types_key} must be an array")
    if not all(isinstance(item, dict) for item in resource_types):
        raise ValueError(f"catalog {types_key} entries must be objects")
    relevant_types = []
    for item in resource_types:
        class_name = item.get("m_ClassName")
        if not isinstance(class_name, str):
            raise ValueError("catalog resource type m_ClassName must be a string")
        if any(name in class_name for name in TARGET_CLASSES):
            relevant_types.append(item)
    relevant_ids = [
        item
        for item in ids
        if any(
            marker in item.lower()
            for marker in (
                "beatmaplevel",
                "_pack_assets",
                "levelpack",
                "levelcollection",
            )
        )
    ]
    return {
        "internal_id_count": len(ids),
        "resource_type_count": len(resource_types),
        "candidate_resource_types": relevant_types,
        "candidate_internal_ids": relevant_ids,
        "enumeration_proven": False,
        "note": "Catalog presence does not prove menu enumeration or entitlement behavior.",
    }


def source_record(path: Path, data: bytes) -> dict:
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def build_report(dump: Path | None = None, catalog: Path | None = None) -> dict:
    if dump is None and catalog is None:
        raise ValueError("provide --dump-cs and/or --catalog from your own game build")
    report = {
        "schema": "bsd-additive-recon-v1",
        "mode": "offline-read-only",
        "runtime_ready": False,
        "sources": {},
        "next_gate": (
            "Verify this PS4 build's pack enumeration and level-ID resolution; "
            "only then design a main-thread, GC-rooted stock-duplicate experiment."
        ),
    }
    if dump is not None:
        data = dump.read_bytes()
        report["sources"]["dump_cs"] = source_record(dump, data)
        report["il2cpp"] = inspect_dump(data.decode("utf-8-sig"))
    if catalog is not None:
        data = catalog.read_bytes()
        report["sources"]["catalog"] = source_record(catalog, data)
        report["addressables"] = inspect_catalog(json.loads(data.decode("utf-8-sig")))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dump-cs", type=Path, help="Il2CppDumper dump.cs from your PS4 build")
    parser.add_argument("--catalog", type=Path, help="the same build's aa/catalog.json")
    parser.add_argument("--output", type=Path, help="create a NEW JSON report; never overwrite")
    args = parser.parse_args(argv)
    try:
        report = build_report(args.dump_cs, args.catalog)
        encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output is not None:
            # Exclusive create protects both source files and earlier evidence.
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(encoded)
        else:
            print(encoded, end="")
    except (OSError, ValueError, UnicodeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
