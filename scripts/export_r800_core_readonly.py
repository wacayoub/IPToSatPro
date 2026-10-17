#!/usr/bin/env python3
"""Read-only export of the installed R80.0 Index Focus core.py.

Packages ONLY core.py and a non-sensitive code hash manifest.
Never reads configuration, mappings, IPTV URLs, tokens or logs.
Never installs, restarts, updates or connects to a network.
"""
import argparse
import hashlib
import io
import json
import re
import sys
import tarfile
from pathlib import Path

DEFAULT_DIR = Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge")
DEFAULT_OUTPUT = Path("/tmp/IPToSatPro_R80_0_Index_Focus_CORE_ONLY.tar.gz")
EXPECTED_VERSION = "1.0.46-r80.0-rc1-index-focus"
PREVIOUS_CORE_SHA = "795b3bb206ec9ca4a285db7a85f497af1037248837d5a299442cea10e608ee1b"

def sha256(data):
    return hashlib.sha256(data).hexdigest()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plugin-dir", type=Path, default=DEFAULT_DIR)
    p.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    opts = p.parse_args()
    plugin = opts.plugin_dir / "plugin.py"
    core = opts.plugin_dir / "core.py"
    if not plugin.is_file() or not core.is_file():
        raise RuntimeError("MISSING_PLUGIN_OR_CORE; nothing exported")
    raw_plugin = plugin.read_bytes()
    m = re.search(rb"""(?m)^\s*PLUGIN_VERSION\s*=\s*["']([^"'\r\n]+)["']""", raw_plugin)
    version = m.group(1).decode("ascii", "replace") if m else "UNKNOWN"
    if version != EXPECTED_VERSION:
        raise RuntimeError("WRONG_INSTALLED_VERSION: %s; nothing exported" % version)
    data = core.read_bytes()
    if not (50000 < len(data) <= 2 * 1024 * 1024):
        raise RuntimeError("INVALID_CORE_SIZE; nothing exported")
    checksums = {}
    for name in ("plugin.py", "updater.py"):
        path = opts.plugin_dir / name
        checksums[name] = ({"sha256": sha256(path.read_bytes()), "bytes": path.stat().st_size}
                           if path.is_file() else {"present": False})
    manifest = {
        "schema": "iptosat-r800-exact-core-export-v1",
        "installed_version": version,
        "core_sha256": sha256(data),
        "core_bytes": len(data),
        "matches_previous_receiver_audit": sha256(data) == PREVIOUS_CORE_SHA,
        "other_code_only_checksums": checksums,
        "included_files": ["core.py", "manifest.json"],
        "excluded": ["settings", "mappings", "stream URLs", "passwords", "logs"],
    }
    opts.output.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(opts.output, "w:gz") as archive:
        for name, blob in (
            ("core.py", data),
            ("manifest.json", (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf8")),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(blob)
            info.mode = 0o600
            info.mtime = 0
            archive.addfile(info, io.BytesIO(blob))
    print(json.dumps({
        "result": "CORE_EXPORT_READY",
        "file": str(opts.output),
        "archive_sha256": sha256(opts.output.read_bytes()),
        "core_sha256": manifest["core_sha256"],
        "core_bytes": len(data),
        "matches_previous_audit": manifest["matches_previous_receiver_audit"],
        "privacy": "Core source and hashes only; no mappings/settings/logs exported",
    }, indent=2))

if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError) as exc:
        print("EXPORT_BLOCKED: " + str(exc), file=sys.stderr)
        sys.exit(2)
