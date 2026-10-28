"""Synthetic fixtures only: no copyrighted dump, SDK, console, or network required."""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "development/scripts/probe_additive_registration.py"
_spec = importlib.util.spec_from_file_location("additive_probe", SCRIPT)
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)

DUMP = """// Namespace: Example
public class BeatmapLevelsModel : Object // TypeDefIndex: 1
{
    private object _repository; // 0x28
    // RVA: 0x1234 Offset: 0x1200 VA: 0x81234
    public object GetLevel(string id) { }
    // RVA: 0x5678 Offset: 0x5600 VA: 0x85678
    [ExampleAttribute]
    public object GetLevel(int index) { }
}
// Namespace: Other
public class Irrelevant : Object // TypeDefIndex: 2
{
    // RVA: 0x9999 Offset: 0x9900 VA: 0x89999
    public void NeverHook() { }
}
// Namespace:
public class BeatmapLevelPackSO : Object // TypeDefIndex: 3
{
    private string _packID; // 0x30
}
"""
CATALOG = {
    "m_InternalIds": [
        "unrelated",
        "Packages/example/ExampleBeatmapLevelPack.asset",
        "PS4/example_pack_assets_all_123.bundle",
    ],
    "m_ResourceTypes": [
        {"m_AssemblyName": "Example", "m_ClassName": "BeatmapLevelPackSO"},
        {"m_AssemblyName": "Example", "m_ClassName": "Other"},
    ],
}


def test_candidate_classes_only_and_exact_source_locations():
    result = probe.inspect_dump(DUMP)
    assert [c["name"] for c in result["classes"]] == ["BeatmapLevelsModel", "BeatmapLevelPackSO"]
    first = result["classes"][0]
    assert first["namespace"] == "Example"
    assert first["line"] == 2
    assert first["fields"][0]["offset"] == "0x28"
    assert first["fields"][0]["declaration"] == "private object _repository; // 0x28"
    assert result["classes"][1]["namespace"] == ""


def test_overloads_are_preserved_with_rva_not_file_offset():
    methods = probe.inspect_dump(DUMP)["classes"][0]["methods"]
    assert len(methods) == 2
    assert methods[0]["addresses"] == {"RVA": "0x1234", "Offset": "0x1200", "VA": "0x81234"}
    assert methods[0]["signature"] == "public object GetLevel(string id) { }"
    assert methods[0]["line"] == 6
    assert methods[1]["addresses"]["RVA"] == "0x5678"
    assert all(not method["hook_verified"] for method in methods)


def test_no_address_is_inferred_for_abstract_or_missing_method():
    text = "public class BeatmapLevelsModel\n{\npublic abstract void A();\n}"
    assert probe.inspect_dump(text)["classes"][0]["methods"] == []


def test_negative_rva_does_not_reuse_previous_method():
    text = """public class BeatmapLevelsModel
{
// RVA: 0x1234 Offset: 0x1200 VA: 0x81234
public void A() { }
// RVA: -1 Offset: -1 VA: -1
public void B() { }
}"""
    assert probe.inspect_dump(text)["classes"][0]["methods"][1]["addresses"]["RVA"] == "-1"


def test_unrelated_nested_type_ends_candidate_scope():
    text = """public class BeatmapLevelsModel
{
public class Nested
{
// RVA: 0xAA Offset: 0xBB VA: 0xCC
public void NotModelMethod() { }
}
}"""
    assert probe.inspect_dump(text)["classes"][0]["methods"] == []


def test_no_matches_is_explicit_not_successful_registration():
    result = probe.inspect_dump("// no supported classes in this synthetic file")
    assert result["classes"] == []
    assert result["missing_candidates"] == sorted(probe.TARGET_CLASSES)


def test_catalog_inventory_does_not_claim_pack_discovery():
    before = json.dumps(CATALOG)
    report = probe.inspect_catalog(CATALOG)
    assert len(report["candidate_internal_ids"]) == 2
    assert report["candidate_resource_types"] == [CATALOG["m_ResourceTypes"][0]]
    assert report["enumeration_proven"] is False
    assert json.dumps(CATALOG) == before


def test_ps4_catalog_resource_types_casing_preserves_input():
    catalog = {"m_InternalIds": CATALOG["m_InternalIds"],
               "m_resourceTypes": CATALOG["m_ResourceTypes"]}
    before = json.dumps(catalog)
    report = probe.inspect_catalog(catalog)
    assert report["resource_type_count"] == 2
    assert report["candidate_resource_types"][0]["m_ClassName"] == "BeatmapLevelPackSO"
    assert json.dumps(catalog) == before


def test_malformed_ps4_resource_types_does_not_fall_back_to_alias():
    catalog = dict(CATALOG, m_resourceTypes=None)
    with pytest.raises(ValueError, match="m_resourceTypes must be an array"):
        probe.inspect_catalog(catalog)


@pytest.mark.parametrize(
    "catalog",
    [
        None,
        [],
        {},
        {"m_InternalIds": "bad"},
        {"m_InternalIds": [1], "m_ResourceTypes": []},
        {"m_InternalIds": [], "m_ResourceTypes": [1]},
        {"m_InternalIds": [], "m_ResourceTypes": [{}]},
    ],
)
def test_invalid_catalog_is_rejected(catalog):
    with pytest.raises(ValueError):
        probe.inspect_catalog(catalog)


def test_at_least_one_input_required():
    with pytest.raises(ValueError, match="provide"):
        probe.build_report()


def test_report_is_bound_to_exact_input_bytes_and_preserves_inputs(tmp_path):
    dump = tmp_path / "dump.cs"
    catalog = tmp_path / "catalog.json"
    dump.write_text(DUMP)
    catalog.write_text(json.dumps(CATALOG))
    before = dump.read_bytes(), catalog.read_bytes()
    report = probe.build_report(dump, catalog)
    assert report["runtime_ready"] is False
    assert report["mode"] == "offline-read-only"
    assert report["sources"]["dump_cs"]["path"] == str(dump.resolve())
    assert len(report["sources"]["dump_cs"]["sha256"]) == 64
    dump.write_text(DUMP + "\n")
    assert probe.build_report(dump)["sources"]["dump_cs"]["sha256"] != report["sources"]["dump_cs"]["sha256"]
    assert catalog.read_bytes() == before[1]


def test_cli_never_overwrites_input_or_prior_report(tmp_path):
    dump = tmp_path / "dump.cs"
    dump.write_text(DUMP)
    with pytest.raises(SystemExit) as exc:
        probe.main(["--dump-cs", str(dump), "--output", str(dump)])
    assert exc.value.code == 2
    assert dump.read_text() == DUMP


def test_cli_creates_evidence_report(tmp_path):
    catalog = tmp_path / "catalog.json"
    catalog.write_text("\ufeff" + json.dumps(CATALOG), encoding="utf-8")
    output = tmp_path / "report.json"
    assert probe.main(["--catalog", str(catalog), "--output", str(output)]) == 0
    assert json.loads(output.read_text())["runtime_ready"] is False
    with pytest.raises(SystemExit):
        probe.main(["--catalog", str(catalog), "--output", str(output)])


def test_no_network_or_console_access_is_needed(tmp_path, monkeypatch):
    import socket
    import subprocess

    def forbidden(*args, **kwargs):
        pytest.fail("offline probe attempted network or subprocess access")

    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    dump = tmp_path / "dump.cs"
    dump.write_text(DUMP)
    assert probe.build_report(dump)["runtime_ready"] is False


def test_cli_missing_file_exits_with_error(tmp_path):
    with pytest.raises(SystemExit) as exc:
        probe.main(["--dump-cs", str(tmp_path / "absent.cs")])
    assert exc.value.code == 2


def test_no_need_to_import_game_or_platform_modules():
    assert "UnityPy" not in probe.__dict__
    assert sys.version_info >= (3, 10)


@pytest.mark.parametrize("name", [
    "BeatmapLevelPack", "PackDefinitionSO", "BeatmapLevelLoader",
    "BeatmapLevelDataLoader", "IBeatmapLevelLoader",
])
def test_runtime_pack_definition_and_loader_candidates(name):
    kind = "interface" if name.startswith("I") else "class"
    text = f"// Namespace:\npublic {kind} {name}\n{{\n    private object _data; // 0x10\n}}\n"
    report = probe.inspect_dump(text)
    assert [entry["name"] for entry in report["classes"]] == [name]
    assert name not in report["missing_candidates"]
