"""Baseline setup/ABI fault guards. No network, rootfs provisioning or PS4 use."""

import hashlib
import importlib.util
import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def dev(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "desktop/development" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


baseline = dev("setup_linux_baseline")
abi = dev("audit_linux_baseline")


def archive(tmp_path, entries):
    result = tmp_path / "layer.tar.gz"
    with tarfile.open(result, "w:gz") as stream:
        for name, kind, value in entries:
            info = tarfile.TarInfo(name)
            if kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = value
                stream.addfile(info)
            elif kind == "node":
                info.type = tarfile.CHRTYPE
                stream.addfile(info)
            else:
                data = value.encode()
                info.size = len(data)
                stream.addfile(info, io.BytesIO(data))
    return result


def test_rootfs_absolute_link_is_rebased_inside_owned_root(tmp_path):
    file = archive(tmp_path, [("usr/bin/tool", "file", "data"), ("bin", "symlink", "/usr/bin")])
    out = tmp_path / "root"
    out.mkdir()
    baseline.extract_layer(file, out)
    assert (out / "bin/tool").read_text() == "data"
    assert not (out / "bin").readlink().is_absolute()
    assert (out / "bin/tool").resolve().is_relative_to(out)


@pytest.mark.parametrize(
    "name,kind,value",
    [
        ("../escape", "file", "bad"),
        ("/etc/escape", "file", "bad"),
        ("dev/node", "node", ""),
        (".wh.secret", "file", "bad"),
        ("link", "symlink", "../../escape"),
        ("link", "symlink", "/../escape"),
    ],
)
def test_rootfs_refuses_unsafe_tar_members(tmp_path, name, kind, value):
    out = tmp_path / "root"
    out.mkdir()
    with pytest.raises((ValueError, tarfile.TarError)):
        baseline.extract_layer(archive(tmp_path, [(name, kind, value)]), out)
    assert not (tmp_path / "escape").exists()


def test_root_run_is_project_local_and_drops_host_environment(tmp_path, monkeypatch):
    monkeypatch.setattr(baseline, "ROOT", tmp_path)
    root = tmp_path / ".tools/root"
    root.mkdir(parents=True)
    (root / "orbeats-image-lock.json").write_bytes(baseline.LOCK.read_bytes())
    work = tmp_path / "temp/work"
    work.mkdir(parents=True)
    args = baseline.command(root, ["/usr/bin/id"], work=work)
    assert "--unshare-user" in args and "--clearenv" in args and "--die-with-parent" in args
    assert args[args.index("--uid") + 1] == "0"
    assert args[-1] == "/usr/bin/id"
    assert str(Path.home()) not in args and "LD_PRELOAD" not in args
    with pytest.raises(ValueError, match="scratch work"):
        baseline.command(root, ["true"], work=tmp_path)
    (root / "orbeats-image-lock.json").write_text("changed")
    with pytest.raises(ValueError, match="pinned project-local"):
        baseline.command(root, ["true"])


def test_oci_digest_mismatch_is_refused():
    with pytest.raises(ValueError, match="digest mismatch"):
        baseline.checked(b"tampered", "sha256:" + "0" * 64)


@pytest.mark.parametrize(
    "text",
    [
        "GLIBC_2.36",
        "GLIBC_2.44",
        "GLIBC_2.35 GLIBC_2.350",
        "GLIBC_ABI_DT_RELR",
        "GLIBC_ABI_UNKNOWN",
        "GLIBC_PRIVATE",
    ],
)
def test_baseline_gate_refuses_numeric_and_symbolic_too_new_requirements(text):
    with pytest.raises(ValueError, match="GLIBC"):
        abi.references(text, "2.35")


def test_baseline_versions_are_numeric_not_lexical():
    assert abi.references("GLIBC_2.9 GLIBC_2.2.5 GLIBC_2.35 GLIBC_2.9", "2.35") == [
        "GLIBC_2.2.5",
        "GLIBC_2.9",
        "GLIBC_2.35",
    ]
    assert abi.references("no dynamic GLIBC references", "2.35") == []
    assert abi.references("GLIBC_ABI_DT_RELR", "2.36") == []
    with pytest.raises(ValueError, match="major.minor"):
        abi.references("GLIBC_2.35", "latest")


def test_baseline_audit_rejects_build_only_and_private_files(tmp_path, monkeypatch):
    monkeypatch.setattr(abi, "ROOT", tmp_path)
    root = tmp_path / "temp/AppDir"
    for rel in ["usr/bin/orbeats-desktop", "usr/lib/OrBeats/backend/orbeats-backend"]:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"\x7fELFfake")
    monkeypatch.setattr(abi.subprocess, "check_output", lambda *a, **k: "GLIBC_2.35")
    result = abi.audit(root)
    assert len(result["elf_files"]) == 2 and result["static_abi_gate_passed"]
    assert not result["legal_approval"] and not result["clean_machine_approval"]
    (root / "libbaseline-ownership.so").write_bytes(b"build-only")
    with pytest.raises(ValueError, match="Build-only/private"):
        abi.audit(root)


def freezer():
    spec = importlib.util.spec_from_file_location("baseline_freeze_backend", ROOT / "desktop/freeze_backend.py")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "desktop"))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(ROOT / "desktop"))
    return module


def test_generated_helper_uses_os_matching_glibc_companion(tmp_path):
    module = freezer()
    internal = tmp_path / "dist/orbeats-backend/_internal"
    internal.mkdir(parents=True)
    companion = internal / "libmvec.so.1"
    companion.write_bytes(b"\x7fELFgenerated fixture")
    other = internal / "libvorbis.so.0"
    other.write_bytes(b"untouched")
    assert module.omit_glibc_companion(tmp_path, platform="linux") == ["libmvec.so.1"]
    assert not companion.exists() and other.read_bytes() == b"untouched"
    assert module.omit_glibc_companion(tmp_path, platform="linux") == []


def test_generated_companion_refuses_symlink_and_non_elf(tmp_path):
    module = freezer()
    internal = tmp_path / "dist/orbeats-backend/_internal"
    internal.mkdir(parents=True)
    outside = tmp_path / "original"
    outside.write_bytes(b"keep")
    companion = internal / "libmvec.so.1"
    companion.symlink_to(outside)
    with pytest.raises(ValueError, match="symlink"):
        module.omit_glibc_companion(tmp_path, platform="linux")
    assert outside.read_bytes() == b"keep"
    companion.unlink()
    companion.write_bytes(b"not ELF")
    with pytest.raises(ValueError, match="ELF"):
        module.omit_glibc_companion(tmp_path, platform="linux")
    assert companion.read_bytes() == b"not ELF"
    assert module.omit_glibc_companion(tmp_path, platform="win32") == []


@pytest.fixture
def legal_fixture(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("baseline_build_legal", ROOT / "desktop/build_legal.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    folder = tmp_path / "desktop/legal"
    folder.mkdir(parents=True)
    notice = (ROOT / "desktop/legal/fsb5-LICENSE.txt").read_bytes()
    (folder / "fsb5-LICENSE.txt").write_bytes(notice)
    record = json.loads((ROOT / "desktop/legal/fsb5-provenance.json").read_text())
    installed = tmp_path / "installed"
    (installed / "fsb5").mkdir(parents=True)
    for name in module.FSB5_MODULES:
        value = ("fixture " + name).encode()
        (installed / "fsb5" / name).write_bytes(value)
        record["module_sha256"][name] = hashlib.sha256(value).hexdigest()
    (folder / "fsb5-provenance.json").write_text(json.dumps(record))

    class Distribution:
        version = "1.0"

        @staticmethod
        def locate_file(name):
            return installed / name

    monkeypatch.setattr(module.importlib.metadata, "distribution", lambda name: Distribution())
    return module, folder, installed


def test_recovered_notice_requires_exact_installed_source(legal_fixture):
    module, folder, installed = legal_fixture
    assert [p.name for p in module.legal_inputs()] == ["fsb5-LICENSE.txt", "fsb5-provenance.json"]
    (installed / "fsb5/vorbis.py").write_text("different revision")
    with pytest.raises(ValueError, match="altered dependency source"):
        module.legal_inputs()


@pytest.mark.parametrize("fault", ["notice", "version", "escape", "symlink"])
def test_recovered_notice_refuses_mismatch(legal_fixture, fault):
    module, folder, installed = legal_fixture
    if fault == "notice":
        (folder / "fsb5-LICENSE.txt").write_text("invented notice")
    elif fault == "version":

        class Distribution:
            version = "2.0"

        module.importlib.metadata.distribution = lambda name: Distribution()
    elif fault == "escape":
        file = folder / "fsb5-provenance.json"
        record = json.loads(file.read_text())
        record["module_sha256"]["../escape.py"] = "0" * 64
        file.write_text(json.dumps(record))
    else:
        file = installed / "fsb5/utils.py"
        file.unlink()
        file.symlink_to(folder / "fsb5-LICENSE.txt")
    with pytest.raises(ValueError):
        module.legal_inputs()
