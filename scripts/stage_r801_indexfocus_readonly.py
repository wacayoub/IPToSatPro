#!/usr/bin/env python3
"""Stage ONLY a R80.0 Index Focus based Preview hot-path IPK on the Vu+.

The exact installed core.py is the source of truth. The verified old R80.1
package supplies public resources/control metadata, NOT an executable core.
No opkg, installation, restart, mappings, settings, logs or upload.

Default --check fully rebuilds in memory, prints results, writes nothing.
--stage saves one *non-production* IPK in /tmp for separate, explicit review.
"""
import argparse
import ast
import base64
import copy
import gzip
import hashlib
import io
import json
import os
import re
import sys
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge")
ARCHIVE = Path("/tmp/IPToSatPro_R80_0_Index_Focus_CORE_ONLY.tar.gz")
PATCH = Path("/tmp/r80_preview_hotpath_patch.py")
DEST = Path("/tmp/iptosatpro-r801-indexfocus-hotpath-rc1-NOT_INSTALLED.ipk")
OLD = "1.0.46-r80.0-rc1-index-focus"
CANDIDATE_VERSION = "1.0.46-r80.1-preview-hotpath-beta"
NEW = "1.0.46-r80.1-indexfocus-hotpath-rc1"
CORE_SHA = "795b3bb206ec9ca4a285db7a85f497af1037248837d5a299442cea10e608ee1b"
PATCHED_SHA = "74cd89b8c6a41b4537fd758cedb3a07b2bc0f9a5c215063e4c45b99e5d92cd2a"
CANDIDATE_SHA = "210fe7de203353b71f02829f4f2b31acc582dfc663ce7bc8971425e0ecd2f173"
URL = ("https://raw.githubusercontent.com/wacayoub/IPToSatPro/"
       "3e60a5b2b9dcb2576ce746ceddeace81b15ba17a/payload/r801-preview-hotpath.b64")
PFX = "usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"
ALLOWED_MISSING = {"R80-RELEASE-CANDIDATE.md", "R801-EXPERIMENTAL-HOTPATH.txt"}
ALLOWED_CHANGED = {"core.py", "plugin.py", "updater.py"}
POSTINST = ("#!/bin/sh\n"
            "printf '%s\\n' 'IPToSatPro Index Focus Preview hot-path RC staged; restart GUI manually.'\n"
            "exit 0\n").encode("utf-8")

def sha(b):
    return hashlib.sha256(b).hexdigest()

def require(cond, description):
    if not cond:
        raise ValueError(description)

def check_version(blob, var, expected):
    text = blob.decode("utf-8")
    expression = re.compile(r'(?m)^\s*' + re.escape(var) + r'\s*=\s*["\']([^"\'\r\n]+)["\']')
    hits = expression.findall(text)
    require(hits == [expected], "VERSION_MARKER_INVALID: " + var)
    return text

def new_version(blob, var):
    source = check_version(blob, var, OLD)
    old_mark = var + ' = "' + OLD + '"'
    require(source.count(old_mark) == 1, "VERSION_ANCHOR_NOT_EXACT: " + var)
    updated = source.replace(old_mark, var + ' = "' + NEW + '"', 1).encode("utf-8")
    check_version(updated, var, NEW)
    return updated

def ar_unpack(raw):
    require(raw.startswith(b"!<arch>\n"), "IPK_AR_MAGIC")
    result, order, pos = {}, [], 8
    while pos < len(raw):
        require(pos + 60 <= len(raw), "TRUNCATED_AR_HEADER")
        h = raw[pos:pos + 60]
        require(h[58:60] == b"\x60\n", "AR_TRAILER")
        name = h[:16].decode("ascii").strip().rstrip("/")
        size = int(h[48:58].strip())
        require(size >= 0 and pos + 60 + size <= len(raw), "AR_MEMBER_SIZE")
        payload = raw[pos + 60:pos + 60 + size]
        require(name not in result, "DUPLICATE_AR_MEMBER")
        result[name] = (h, payload)
        order.append(name)
        pos += 60 + size + size % 2
    require(set(result) == {"debian-binary", "control.tar.gz", "data.tar.gz"}, "UNEXPECTED_AR_MEMBERS")
    return result, order

def ar_pack(blocks, order):
    out = bytearray(b"!<arch>\n")
    for name in order:
        header, payload = blocks[name]
        require(len(header) == 60, "INVALID_AR_HEADER_LENGTH")
        out.extend(header[:48] + str(len(payload)).encode("ascii").ljust(10) + b"\x60\n")
        out.extend(payload)
        if len(payload) % 2:
            out.extend(b"\n")
    return bytes(out)

def tar_read(blob):
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as ar:
        members, raw = [], {}
        for m in ar.getmembers():
            name = m.name
            require(name not in raw, "DUPLICATE_TAR_MEMBER")
            require(not m.issym() and not m.islnk(), "UNSUPPORTED_PACKAGE_SYMLINK")
            require(m.isfile() or m.isdir(), "UNSUPPORTED_PACKAGE_ENTRY")
            raw[name] = ar.extractfile(m).read() if m.isfile() else None
            members.append(m)
    return members, raw

def tar_pack(members, originals, replace):
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", filename="", mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode="w", format=tarfile.GNU_FORMAT) as archive:
            for m in members:
                member = copy.copy(m)
                data = replace.get(m.name, originals[m.name])
                if m.isfile():
                    require(isinstance(data, bytes), "MISSING_TAR_FILE")
                    member.size = len(data)
                    archive.addfile(member, io.BytesIO(data))
                else:
                    archive.addfile(member)
    return output.getvalue()

def code_only_archive():
    require(ARCHIVE.is_file(), "MISSING_CORE_EXPORT")
    with tarfile.open(ARCHIVE, "r:gz") as ar:
        members = ar.getmembers()
        require({m.name for m in members} == {"core.py", "manifest.json"}, "CORE_ARCHIVE_MEMBERS")
        require(all(m.isfile() for m in members), "CORE_ARCHIVE_FILE_TYPE")
        core = ar.extractfile("core.py").read()
        meta = json.loads(ar.extractfile("manifest.json").read())
    require(sha(core) == CORE_SHA and meta.get("core_sha256") == CORE_SHA, "CORE_ARCHIVE_SHA")
    require((ROOT / "core.py").read_bytes() == core, "CORE_INSTALLED_CHANGED")
    return core

def patch_core(core):
    require(PATCH.is_file(), "MISSING_PATCH")
    scope = {"__name__": "r801_hotpath"}
    exec(compile(PATCH.read_bytes(), str(PATCH), "exec"), scope)
    require(scope.get("TAG") == "R80_PREVIEW_PURE_HOTPATH_V1", "WRONG_PATCH_SCRIPT")
    before = core.decode("utf-8")
    after = scope["patch_core"](before)
    require(sha(after.encode("utf-8")) == PATCHED_SHA, "PATCHED_CORE_SHA_DIFFERS_FROM_PROVEN_AUDIT")
    require(scope["patch_core"](after) == after, "PATCH_NOT_IDEMPOTENT")
    compile(after, "core.py", "exec")
    return after.encode("utf-8")

def downloaded_candidate():
    with urllib.request.urlopen(URL, timeout=35) as response:
        encoded = response.read(800_000)
    require(0 < len(encoded) < 800_000, "CANDIDATE_FETCH_SIZE")
    data = base64.b64decode(encoded, validate=True)
    require(len(data) == 461044 and sha(data) == CANDIDATE_SHA, "CANDIDATE_PACKAGE_SHA")
    return data

def normalized_name(name):
    while name.startswith("./"):
        name = name[2:]
    return name.lstrip("/")

def prepare():
    current_plugin = (ROOT / "plugin.py").read_bytes()
    current_updater = (ROOT / "updater.py").read_bytes()
    check_version(current_plugin, "PLUGIN_VERSION", OLD)
    check_version(current_updater, "CURRENT_VERSION", OLD)
    core = code_only_archive()
    patched_core = patch_core(core)
    pieces, order = ar_unpack(downloaded_candidate())
    data_members, orig_data = tar_read(pieces["data.tar.gz"][1])
    control_members, orig_control = tar_read(pieces["control.tar.gz"][1])
    # Fail closed if package would install any other files outside the plugin.
    files = {}
    for m in data_members:
        name = normalized_name(m.name)
        if m.isfile():
            require(name.startswith(PFX), "PACKAGE_FILE_OUTSIDE_PLUGIN: " + name[:120])
            rel = name[len(PFX):]
            require(rel and ".." not in Path(rel).parts, "UNSAFE_RELATIVE_PACKAGE_PATH")
            require(rel not in files, "DUPLICATE_PLUGIN_ENTRY")
            files[rel] = m.name
    require(len(files) == 87, "CANDIDATE_EXPECTED_87_ASSETS")
    require(ALLOWED_CHANGED <= set(files), "CANDIDATE_MISSING_CORE_CODE")
    changes, missing, identical = [], [], 0
    for rel, key in files.items():
        on_disk = ROOT / rel
        if not on_disk.is_file():
            require(rel in ALLOWED_MISSING, "UNEXPECTED_INSTALLED_ASSET_MISSING: " + rel)
            missing.append(rel)
        elif on_disk.read_bytes() != orig_data[key]:
            require(rel in ALLOWED_CHANGED, "UNEXPECTED_INSTALLED_ASSET_DIFF: " + rel)
            changes.append(rel)
        else:
            identical += 1
    require(set(missing) == ALLOWED_MISSING, "MISSING_ASSET_SET_UNEXPECTED")
    require(set(changes) == ALLOWED_CHANGED and identical == 82, "INSTALLED_PARITY_DIFFERENT")
    # No extra installed Python source gets silently omitted from the package.
    package_py = {rel for rel in files if rel.endswith(".py")}
    live_py = {p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.py") if p.is_file()}
    require(live_py <= package_py, "UNPACKAGED_PYTHON_RUNTIME")
    replacements = {
        files["core.py"]: patched_core,
        files["plugin.py"]: new_version(current_plugin, "PLUGIN_VERSION"),
        files["updater.py"]: new_version(current_updater, "CURRENT_VERSION"),
    }
    # Leave all other candidate data files exactly as verified.
    for rel, key in files.items():
        expected = replacements.get(key, orig_data[key])
        if rel in ("plugin.py", "updater.py", "core.py"):
            compile(expected, rel, "exec")
    new_data = tar_pack(data_members, orig_data, replacements)
    ctr_names = {normalized_name(m.name):m.name for m in control_members if m.isfile()}
    require("control" in ctr_names and "postinst" in ctr_names, "CONTROL_FILES_MISSING")
    require(not (set(ctr_names) & {"preinst","prerm","postrm"}), "DANGEROUS_CONTROL_SCRIPT")
    original_control = orig_control[ctr_names["control"]].decode("utf-8")
    original_postinst = orig_control[ctr_names["postinst"]]
    require(b"exit 0" in original_postinst and b"opkg " not in original_postinst,
            "ORIGINAL_POSTINST_UNEXPECTED")
    marker = "Version: " + CANDIDATE_VERSION
    require(original_control.count(marker) == 1, "ORIGINAL_CONTROL_VERSION_UNEXPECTED")
    control_changes = {
        ctr_names["control"]: original_control.replace(marker, "Version: " + NEW, 1).encode("utf-8"),
        ctr_names["postinst"]: POSTINST,
    }
    new_control = tar_pack(control_members, orig_control, control_changes)
    pieces["data.tar.gz"] = (pieces["data.tar.gz"][0], new_data)
    pieces["control.tar.gz"] = (pieces["control.tar.gz"][0], new_control)
    raw = ar_pack(pieces, order)
    # Independent re-extraction of the output.
    verified, _ = ar_unpack(raw)
    member_list, final_data = tar_read(verified["data.tar.gz"][1])
    actual = {normalized_name(m.name):final_data[m.name] for m in member_list if m.isfile()}
    require(set(actual) == {PFX + x for x in files}, "FINAL_PACKAGE_FILE_SET_CHANGED")
    for rel, key in files.items():
        require(actual[PFX + rel] == replacements.get(key, orig_data[key]),
                "FINAL_DATA_MISMATCH: " + rel)
    control_members2, control_data2 = tar_read(verified["control.tar.gz"][1])
    require(control_data2[ctr_names["postinst"]] == POSTINST, "POSTINST_NOT_PASSIVE")
    require(("Version: " + NEW).encode("utf-8") in control_data2[ctr_names["control"]],
            "FINAL_CONTROL_VERSION")
    return raw, {"installed_base": OLD, "candidate_version": NEW,
                 "original_core_sha256": CORE_SHA, "patched_core_sha256": PATCHED_SHA,
                 "unchanged_assets": identical, "rebased_code_files": sorted(changes),
                 "candidate_only_notes": sorted(missing),
                 "packaged_assets": len(files), "package_sha256": sha(raw),
                 "package_bytes": len(raw), "installed_or_restarted": False,
                 "configuration_and_mappings_read": False,
                 "receiver_av_validated": False, "final_publication_authorized": False}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--check", action="store_true", help="Default; build and verify in memory")
    group.add_argument("--stage", action="store_true", help="Write verified test-only IPK under /tmp")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        raw, report = prepare()
        if args.stage:
            require(not DEST.exists(), "STAGING_FILE_EXISTS_REJECT_OVERWRITE")
            with DEST.open("xb") as output:
                output.write(raw)
            require(sha(DEST.read_bytes()) == report["package_sha256"],
                    "STAGED_FILE_SHA_MISMATCH")
            report["stage_path"] = str(DEST)
            report["result"] = "TEST_ONLY_PACKAGE_STAGED__NOT_INSTALLED"
        else:
            report["result"] = "SOURCE_REBASE_AND_PACKAGE_CHECK_PASSED__NOT_STAGED"
        print(json.dumps(report, sort_keys=True, indent=2))
    except Exception as error:
        print(json.dumps({"result":"REBASE_BLOCKED",
                          "reason": type(error).__name__+": "+str(error)[:190],
                          "receiver_plugin_modified":False,
                          "install_authorized":False}, indent=2))
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
