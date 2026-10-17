#!/usr/bin/env python3
"""Build a SHA-pinned, UNPUBLISHED R80.3 test IPK from official UNMAP RC2.

No Enigma2 access, opkg, network, or receiver mutation. A file is written only
with explicit --build and never uploaded automatically. SHA verifies the
complete input package, then checks all changed archive paths exactly.
"""
import argparse
import base64
import copy
import gzip
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD = "1.0.46-r80.2.2-unmap-rc2"
NEW = "1.0.46-r80.3-playback-rc1"
SOURCE_SHA = "61acad0521f98ad8ea12c1d42e53d36d595ccd479874ee706a9ff52e69e9af4b"
SOURCE_BYTES = 463008
SOURCE_CORE_SHA = "74cd89b8c6a41b4537fd758cedb3a07b2bc0f9a5c215063e4c45b99e5d92cd2a"
PREFIX = "usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"
OLD_MANIFEST = ("https://raw.githubusercontent.com/wacayoub/IPToSatPro/"
                "fix/r80-unmap-stale-candidate-20261017/staging/r80-unmap-rc2.update.json")
NEW_MANIFEST = ("https://raw.githubusercontent.com/wacayoub/IPToSatPro/"
                "fix/r803-playback-verification-20261017/staging/r803-playback-rc1.update.json")
CHANGED = {PREFIX + n for n in ("monitor.py", "plugin.py", "updater.py")}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(b):
    return hashlib.sha256(b).hexdigest()


def normalize(s):
    while s.startswith("./"):
        s = s[2:]
    require(s and not s.startswith("/") and ".." not in Path(s).parts,
            "UNSAFE_ARCHIVE_PATH")
    return s


def read_ar(data):
    require(data.startswith(b"!<arch>\n"), "INPUT_NOT_IPK")
    at, result, order = 8, {}, []
    while at < len(data):
        require(at + 60 <= len(data), "BAD_AR_HEADER")
        head = data[at:at+60]
        require(head[58:60] == b"`\n", "BAD_AR_MAGIC")
        name = head[:16].decode("ascii").strip().rstrip("/")
        count = int(head[48:58].strip())
        require(count >= 0 and at + 60 + count <= len(data), "BAD_AR_SIZE")
        require(name not in result, "DUPLICATE_AR_ENTRY")
        result[name] = [head, data[at+60:at+60+count]]
        order.append(name)
        at += 60 + count + count % 2
    require(set(result) == {"debian-binary", "control.tar.gz", "data.tar.gz"},
            "UNEXPECTED_PACKAGE_AR_FILES")
    return result, order


def repack_ar(entries, order):
    out = bytearray(b"!<arch>\n")
    for name in order:
        head, body = entries[name]
        out += head[:48] + str(len(body)).encode("ascii").ljust(10) + b"`\n"
        out += body
        if len(body) & 1:
            out += b"\n"
    return bytes(out)


def unpack_tar(blob):
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tf:
        members = tf.getmembers()
        files = {}
        for member in members:
            require(member.isfile() or member.isdir(), "UNSAFE_TAR_MEMBER")
            if member.isfile():
                name = normalize(member.name)
                require(name not in files, "DUPLICATE_TAR_ENTRY")
                files[name] = tf.extractfile(member).read()
    return members, files


def repack_tar(members, original, replacements):
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", filename="", mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tf:
            for member in members:
                item = copy.copy(member)
                if item.isfile():
                    name = normalize(item.name)
                    data = replacements.get(name, original[name])
                    item.size = len(data)
                    tf.addfile(item, io.BytesIO(data))
                else:
                    tf.addfile(item)
    return out.getvalue()


def replace_one(data, old, new, marker):
    require(data.count(old) == 1, "AMBIGUOUS_REPLACEMENT:" + marker)
    return data.replace(old, new, 1)


def build(source):
    require(len(source) == SOURCE_BYTES and digest(source) == SOURCE_SHA,
            "SOURCE_UNMAP_RC2_PACKAGE_SHA_MISMATCH")
    parts, order = read_ar(source)
    data_members, files = unpack_tar(parts["data.tar.gz"][1])
    ctrl_members, ctrl = unpack_tar(parts["control.tar.gz"][1])
    require(PREFIX + "core.py" in files, "CORE_NOT_PRESENT")
    require(digest(files[PREFIX+"core.py"]) == SOURCE_CORE_SHA,
            "SOURCE_CORE_NOT_APPROVED")
    require("control" in ctrl and "postinst" in ctrl, "CONTROL_OR_PASSIVE_HOOK_MISSING")
    require(not (set(ctrl) & {"preinst", "prerm", "postrm"}),
            "UNEXPECTED_MUTATING_INSTALL_HOOK")
    before = (ROOT / "staging/r803/monitor_rc2_baseline.py").read_bytes()
    updated = (ROOT / "staging/r803/monitor_rc2_candidate.py").read_bytes()
    require(files[PREFIX+"monitor.py"] == before, "MONITOR_RC2_SNAPSHOT_MISMATCH")
    compile(updated, "<r803-monitor>", "exec")
    require(b"AUDIO_SAFE_RESCUE_PLAN" in updated and b"IPTV_TS_PENDING" in updated,
            "R803_MARKER_MISSING")
    plugin = replace_one(files[PREFIX+"plugin.py"],
        ("PLUGIN_VERSION = \"" + OLD + "\"").encode(),
        ("PLUGIN_VERSION = \"" + NEW + "\"").encode(), "plugin version")
    updater = replace_one(files[PREFIX+"updater.py"],
        ("CURRENT_VERSION = \"" + OLD + "\"").encode(),
        ("CURRENT_VERSION = \"" + NEW + "\"").encode(), "updater version")
    updater = replace_one(updater, OLD_MANIFEST.encode(), NEW_MANIFEST.encode(),
                          "isolated candidate feed")
    require(b"/main/update.json" not in updater, "STABLE_FEED_REFERENCE")
    control = replace_one(ctrl["control"], ("Version: " + OLD).encode(),
                          ("Version: " + NEW).encode(), "control version")
    replacements = {
        PREFIX + "monitor.py": updated,
        PREFIX + "plugin.py": plugin,
        PREFIX + "updater.py": updater,
    }
    parts["data.tar.gz"][1] = repack_tar(data_members, files, replacements)
    parts["control.tar.gz"][1] = repack_tar(ctrl_members, ctrl, {"control": control})
    output = repack_ar(parts, order)
    new_data = unpack_tar(read_ar(output)[0]["data.tar.gz"][1])[1]
    require(new_data.keys() == files.keys(), "FILE_SET_CHANGED")
    diffs = {name for name in files if new_data[name] != files[name]}
    require(diffs == CHANGED, "UNEXPECTED_CHANGED_FILES: " + repr(sorted(diffs)))
    require(new_data[PREFIX+"core.py"] == files[PREFIX+"core.py"], "CORE_CHANGED")
    new_ctrl = unpack_tar(read_ar(output)[0]["control.tar.gz"][1])[1]
    require(new_ctrl["postinst"] == ctrl["postinst"], "MAINTAINER_HOOK_CHANGED")
    require({k for k in new_ctrl if new_ctrl[k] != ctrl[k]} == {"control"},
            "CONTROL_FILE_SET_CHANGED")
    return output, {
        "status": "UNPUBLISHED_R803_RC1_OFFLINE_CANDIDATE",
        "source_version": OLD, "version": NEW, "source_sha256": SOURCE_SHA,
        "size": len(output), "sha256": digest(output),
        "core_sha256_unchanged": SOURCE_CORE_SHA,
        "only_changed_runtime_files": sorted(diffs), "receiver_touched": False,
        "opkg_executed": False, "stable_feed_changed": False,
        "hardware_video_audio_verified": False,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source-b64", required=True, type=Path,
                    help="Pinned RC2 Base64 payload from test branch")
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--output", type=Path,
                    default=Path("/tmp/iptosatpro-r803-playback-rc1.ipk"))
    args = ap.parse_args()
    try:
        source = base64.b64decode(args.source_b64.read_bytes(), validate=False)
        output, report = build(source)
        if args.build:
            require(not args.output.is_symlink() and not args.output.exists(),
                    "REFUSE_OVERWRITE_OR_SYMLINK")
            with args.output.open("xb") as fh:
                fh.write(output)
            require(digest(args.output.read_bytes()) == report["sha256"],
                    "WRITTEN_ARTIFACT_CHANGED")
            report["output"] = str(args.output)
        else:
            report["status"] = "R803_DRY_RUN_PASS_NO_OUTPUT"
        print(json.dumps(report, sort_keys=True, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status":"R803_BUILD_BLOCKED",
                          "reason": type(exc).__name__ + ": " + str(exc)[:180],
                          "receiver_touched":False,"stable_feed_changed":False},
                         indent=2))
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
