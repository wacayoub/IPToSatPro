#!/usr/bin/env python3
"""Read-only comparison of installed R80.0 Index Focus against frozen R80 RC1.
Does not install, extract to disk, modify settings, or read mapping content.
"""
import base64
import hashlib
import io
import json
import re
import tarfile
from pathlib import Path
from urllib.request import urlopen

ROOT = Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge")
BASE_URL = ("https://raw.githubusercontent.com/wacayoub/IPToSatPro/"
            "release/r80-final-candidate-20261015/payload/r80-final-rc1.b64")
BASE_SHA256 = "ca4077a83869d7b7b52510bb4816b2c57c5320cc84d249fc004c5b47c9f055ce"
BASE_SIZE = 460514
PACKAGE_ROOT = "usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"
FIELDS = ("core.py", "plugin.py", "updater.py")

def sha(data):
    return hashlib.sha256(data).hexdigest()

def version(source, name):
    m = re.search(r'^' + re.escape(name) + r'\s*=\s*["\x27]([^"\x27]+)', source, re.M)
    return m.group(1) if m else "UNKNOWN"

def members_ar(data):
    if not data.startswith(b"!<arch>\n"):
        raise ValueError("IPK is not an ar archive")
    pos = 8
    found = {}
    while pos < len(data):
        if pos + 60 > len(data):
            raise ValueError("Truncated ar header")
        head = data[pos:pos+60]
        if head[58:] != bytes((96, 10)):
            raise ValueError("Invalid ar header")
        size = int(head[48:58].decode("ascii").strip())
        name = head[:16].decode("ascii").strip().rstrip("/")
        pos += 60
        if pos + size > len(data):
            raise ValueError("Truncated ar member")
        found[name] = data[pos:pos + size]
        pos += size + size % 2
    return found

def reference_code(ipk):
    archive = members_ar(ipk)
    data = archive.get("data.tar.gz")
    if not data:
        raise ValueError("Missing data.tar.gz")
    found = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        for member in tf:
            if not member.isfile():
                continue
            path = member.name.lstrip("./")
            if not path.startswith(PACKAGE_ROOT):
                continue
            suffix = path[len(PACKAGE_ROOT):]
            if suffix in FIELDS:
                f = tf.extractfile(member)
                if f is not None:
                    found[suffix] = f.read()
    if set(found) != set(FIELDS):
        raise ValueError("Baseline package missing required Python modules")
    return found

def main():
    report = {"audit": "R80_INDEX_FOCUS_BASE_AUDIT_V1", "receiver_modified": False,
              "mapping_files_read": False}
    try:
        local = {name: (ROOT / name).read_bytes() for name in FIELDS}
        report["plugin_version"] = version(local["plugin.py"].decode("utf8"), "PLUGIN_VERSION")
        report["updater_version"] = version(local["updater.py"].decode("utf8"), "CURRENT_VERSION")
        report["versions_agree"] = report["plugin_version"] == report["updater_version"]
        report["local_core_sha256"] = sha(local["core.py"])
        report["local_core_bytes"] = len(local["core.py"])
        report["r7615_markers_present"] = all(m.encode() in local["core.py"] for m in (
            "R7615_NOMINATION_INDEX_ONLY", "R7614_PREVIEW_PARSE_CACHE_IMMUTABLE",
            "R7612_NORMAL_PREVIEW_PHASE_TIMINGS"))
        with urlopen(BASE_URL, timeout=25) as r:
            payload = r.read(1024 * 1024)
        ipk = base64.b64decode(payload, validate=True)
        if len(ipk) != BASE_SIZE or sha(ipk) != BASE_SHA256:
            raise ValueError("PINNED_BASELINE_HASH_MISMATCH")
        ref = reference_code(ipk)
        report["baseline_verified"] = True
        report["baseline_core_sha256"] = sha(ref["core.py"])
        report["core_byte_identical_to_frozen_r7615_rc1"] = (
            local["core.py"] == ref["core.py"])
        report["updater_byte_identical_to_reference"] = (
            local["updater.py"] == ref["updater.py"])
        report["plugin_byte_identical_to_reference"] = (
            local["plugin.py"] == ref["plugin.py"])
        if not report["versions_agree"] or not report["r7615_markers_present"]:
            report["next"] = "STOP_INCONSISTENT_RECEIVER"
        elif report["core_byte_identical_to_frozen_r7615_rc1"]:
            report["next"] = "CORE_COMPATIBLE_BUT_INSTALLER_STILL_BLOCKED"
        else:
            report["next"] = "CORE_DIFFERS_REQUIRES_SOURCE_PARITY_AUDIT_NO_INSTALL"
    except Exception as exc:
        report["next"] = "AUDIT_INCOMPLETE_NO_INSTALL"
        report["error"] = type(exc).__name__ + ": " + str(exc)
    print(json.dumps(report, sort_keys=True, indent=2))

if __name__ == "__main__":
    main()
