#!/usr/bin/env python3
"""Stage SHA-pinned R71 beta on its ISOLATED branch only.

Never changes main/update.json/latest-version.txt, never runs opkg, never
touches real Enigma2, never embeds user credentials/mappings.
"""
import base64
import hashlib
import importlib.util
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "r71_build", ROOT / "scripts/build-r71-beta.py")
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)
EXPECTED_SIZE = 277614
EXPECTED_SHA = "2fe47964933906522680114f7d3ac23aee928caf4dd7e02554a8cd183d2980f3"
VERSION = "1.0.46-r71-beta"
BRANCH = "feature/r71-stability"
RAW = ("https://raw.githubusercontent.com/wacayoub/IPToSatPro/" +
       BRANCH + "/payload/r71-beta.b64")
TARGET = "/tmp/iptosatpro-r71-beta.ipk"


def stage():
    assert json.loads((ROOT / "update.json").read_text())["version"] == builder.OLD_VERSION
    assert (ROOT / "latest-version.txt").read_text().strip() == builder.OLD_VERSION
    package = ROOT / "r71-beta.ipk"
    meta = builder.build(package)
    raw = package.read_bytes()
    assert meta["version"] == VERSION and meta["size"] == EXPECTED_SIZE
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_SHA
    encoded = "\n".join(textwrap.wrap(base64.b64encode(raw).decode("ascii"), 76))+"\n"
    assert base64.b64decode(encoded) == raw
    (ROOT / "payload/r71-beta.b64").write_text(encoded, encoding="ascii")
    (ROOT / "staging").mkdir(exist_ok=True)
    manifest = {
        "version": VERSION,
        "size": EXPECTED_SIZE,
        "sha256": EXPECTED_SHA,
        "notes": ("R71 BETA isolated test candidate: exact-name FR/SAT audio group mismatch "
                  "matching only. All R70 player, locked fast path, audio, timeshift "
                  "and relay unchanged. 22 offline service scenarios tested in preview "
                  "and automatic mode. No receiver performance validation. NO TOD."),
        "published_to_main": False,
        "receiver_tested": False,
        "parts": [RAW]
    }
    (ROOT / "staging/r71-beta.update.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    installer = r'''#!/bin/sh
# DOWNLOAD ONLY: no installation, no restart, no settings/mappings touched.
set -eu
RAW="__RAW__"
TARGET="__TARGET__"
B64="/tmp/iptosatpro-r71.$$-download.b64"
PKG="/tmp/iptosatpro-r71.$$-download.ipk"
trap 'rm -f "$B64" "$PKG"' EXIT HUP INT TERM
wget -q -O "$B64" "$RAW"
test -s "$B64"
if command -v base64 >/dev/null 2>&1; then
    base64 -d "$B64" > "$PKG"
else
    python3 - "$B64" "$PKG" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: raw=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(raw)
PY
fi
test "$(wc -c < "$PKG" | tr -d ' ')" = "__SIZE__"
if command -v sha256sum >/dev/null 2>&1; then
    echo "__SHA__  $PKG" | sha256sum -c - >/dev/null
else
    python3 - "$PKG" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f:
    assert hashlib.sha256(f.read()).hexdigest()=="__SHA__", "SHA256 mismatch"
PY
fi
mv -f "$PKG" "$TARGET"
echo "R71 BETA VERIFIED DOWNLOAD: $TARGET"
echo "NOT INSTALLED. R70 running plugin and all receiver settings unchanged."
'''
    for key, value in {"__RAW__": RAW, "__TARGET__": TARGET,
                       "__SIZE__": str(EXPECTED_SIZE), "__SHA__": EXPECTED_SHA}.items():
        installer = installer.replace(key, value)
    if "__" in installer or "opkg " in installer or "init 4" in installer:
        raise AssertionError("unsafe download script")
    (ROOT / "download-r71-beta.sh").write_text(installer)
    print("R71_STAGED_ONLY", json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    stage()
