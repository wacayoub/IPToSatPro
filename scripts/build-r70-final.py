#!/usr/bin/env python3
"""Build NON-PUBLISHED IPToSatPro r70-final candidate from verified r69.

Conservative finalization: EXACT same runtime logic, native fast-lock path,
audio, IPTV source configuration, mapping, timeshift and TS relay.
Only package version labels and changelog change. Enforces content diff gate.
Does NOT publish to main, touch receiver, run IPTV or enable TOD.
"""
import ast
import base64
import hashlib
import io
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "123e1118a7471075ad18dee3014b7367fa9a2cf02f8cdd52ad1e5e65034035ed"
BASE_VERSION = "1.0.46-r69-beta"
NEW_VERSION = "1.0.46-r70-final"
EXT_PATH = "usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"
CHANGELOG = EXT_PATH + "CHANGELOG-r70-FINAL-STABILITY.txt"
VERSION_PATHS = {
    EXT_PATH + "plugin.py": 'PLUGIN_VERSION = "' + BASE_VERSION + '"',
    EXT_PATH + "updater.py": 'CURRENT_VERSION = "' + BASE_VERSION + '"',
}
DESCRIPTION = (
    "r70 FINAL conservative upgrade from verified r69 beta.\\n"
    "Keeps exactly the existing Fast Zap, MANUAL LOCK, preview matching, sound,\\n"
    "timeshift, IPTV source settings, TS relay and quality-fallback code.\\n"
    "Correct French/Italian/Polish feed decisions remain guarded.\\n"
    "Does not include or activate experimental TOD mapping.\\n"
    "Hardware performance and rare black-screen cases remain receiver-specific.\\n"
)


def unpack_ar(data):
    with tempfile.TemporaryDirectory() as tmp:
        file = Path(tmp) / "baseline.ipk"
        file.write_bytes(data)
        members = subprocess.check_output(["ar", "t", str(file)]).decode().splitlines()
        if set(members) != {"debian-binary", "control.tar.gz", "data.tar.gz"}:
            raise ValueError("unrecognized IPK format")
        return {name: subprocess.check_output(["ar", "p", str(file), name])
                for name in members}


def members_from(blob):
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
        found = {}
        for member in tar.getmembers():
            name = member.name.lstrip("./")
            if member.isfile():
                found[name] = tar.extractfile(member).read()
        return found


def make_tar(blob, changes, new_files=None):
    """Repack TAR retaining original members' metadata and non-file entries."""
    new_files = new_files or {}
    names = set()
    output = io.BytesIO()
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as original:
        with tarfile.open(fileobj=output, mode="w:gz",
                          format=tarfile.GNU_FORMAT) as target:
            for entry in original.getmembers():
                key = entry.name.lstrip("./")
                if key in names:
                    raise ValueError("duplicate tar member " + key)
                names.add(key)
                contents = original.extractfile(entry).read() if entry.isfile() else None
                if key in changes:
                    if not entry.isfile():
                        raise ValueError("cannot patch special tar member")
                    contents = changes[key]
                    entry.size = len(contents)
                target.addfile(entry, io.BytesIO(contents) if contents is not None else None)
            for name, raw in new_files.items():
                if name in names:
                    raise ValueError("existing changelog name")
                added = tarfile.TarInfo("./" + name)
                added.mode = 0o644
                added.size = len(raw)
                target.addfile(added, io.BytesIO(raw))
    return output.getvalue()


def assemble(parts, output):
    with tempfile.TemporaryDirectory() as tmp:
        directory = Path(tmp)
        for key, contents in parts.items():
            (directory / key).write_bytes(contents)
        with open(os.devnull, "wb") as silent:
            subprocess.run(
                ["ar", "q", str(output),
                 str(directory / "debian-binary"),
                 str(directory / "control.tar.gz"),
                 str(directory / "data.tar.gz")],
                check=True, stdout=silent)
    return output.read_bytes()


def build(path=None):
    base = base64.b64decode((ROOT / "payload/r69-beta.b64").read_bytes())
    if hashlib.sha256(base).hexdigest() != BASE_SHA or len(base) != 276666:
        raise ValueError("published r69 package not the verified baseline")
    parts = unpack_ar(base)
    data = members_from(parts["data.tar.gz"])
    control = members_from(parts["control.tar.gz"])
    expected = {}
    modifications = {}
    for filename, anchor in VERSION_PATHS.items():
        text = data[filename].decode("utf-8")
        if text.count(anchor) != 1:
            raise ValueError("missing or duplicate pinned version constant in " + filename)
        updated = text.replace(anchor, anchor.replace(BASE_VERSION, NEW_VERSION))
        modifications[filename] = updated.encode("utf-8")
        expected[filename] = modifications[filename]
    pkg_control = control["control"].decode("utf-8")
    find = "Version: " + BASE_VERSION
    if pkg_control.count(find) != 1:
        raise ValueError("unexpected package version")
    control_changed = pkg_control.replace(find, "Version: " + NEW_VERSION, 1).encode()
    parts["data.tar.gz"] = make_tar(
        parts["data.tar.gz"], modifications,
        {CHANGELOG: DESCRIPTION.encode()})
    parts["control.tar.gz"] = make_tar(parts["control.tar.gz"],
                                     {"control": control_changed})
    out = Path(path) if path else ROOT / "r70-final.ipk"
    if out.exists():
        out.unlink()
    built = assemble(parts, out)
    after = unpack_ar(built)
    data2 = members_from(after["data.tar.gz"])
    ctrl2 = members_from(after["control.tar.gz"])
    if set(data2) != set(data) | {CHANGELOG}:
        raise AssertionError("r70 added or removed unexpected package files")
    for path, raw in data.items():
        if data2[path] != (expected.get(path) or raw):
            raise AssertionError("UNEXPECTED PACKAGE FILE MODIFICATION: " + path)
    if set(ctrl2) != set(control):
        raise AssertionError("control file list altered")
    for key, raw in control.items():
        if ctrl2[key] != (control_changed if key == "control" else raw):
            raise AssertionError("UNEXPECTED CONTROL MODIFICATION: " + key)
    for key, raw in data2.items():
        if key.endswith(".py"):
            compile(raw, key, "exec")
    meta = {"version": NEW_VERSION, "size": len(built),
            "sha256": hashlib.sha256(built).hexdigest(),
            "files_original_unchanged": len(data)-len(expected),
            "patched_files": sorted(expected),
            "added_files": [CHANGELOG],
            "baseline_sha256": BASE_SHA, "logic_changed": False,
            "published": False, "receiver_tested": False, "tod_included": False}
    print("R70_BUILD_PROTECTED_OK", meta)
    return meta


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else None)
