#!/usr/bin/env python3
"""Publish an OPT-IN staged R70 candidate to the feature branch, not main.

Writes versioned base64 IPK, non-production manifest and download-only
installer. Must run ONLY after protected-byte checks in GitHub CI.
Never installs on receiver or changes the updater's production update.json.
"""
import base64
import hashlib
import importlib.util
import json
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "r70_release_builder", Path(__file__).with_name("build-r70-final.py"))
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

version = "1.0.46-r70-final"
branch = "feature/iptosatpro-final-r70"
ipk = ROOT / "r70-final.ipk"
info = builder.build(ipk)
raw = ipk.read_bytes()
assert info["version"] == version
assert not info["logic_changed"]
assert info["sha256"] == hashlib.sha256(raw).hexdigest()
encoded = "\n".join(textwrap.wrap(base64.b64encode(raw).decode("ascii"), 76))+"\n"
assert base64.b64decode(encoded) == raw
dst = ROOT / "payload/r70-final.b64"
dst.write_text(encoded, encoding="ascii")
manifest = {
    "version": version,
    "size": info["size"],
    "sha256": info["sha256"],
    "notes": ("OPT-IN r70 final candidate; runtime unchanged from r69-beta, "
              "does not guarantee faster zapping or solve unverified receiver bugs. "
              "Existing manual mappings, audio, timeshift and player code preserved. "
              "NO experimental TOD functionality. Not installed/field validated."),
    "published_to_main": False,
    "parts": ["https://raw.githubusercontent.com/wacayoub/IPToSatPro/" +
              branch + "/payload/r70-final.b64"]
}
(ROOT / "staging").mkdir(exist_ok=True)
(ROOT / "staging/r70-final.update.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
script = r'''#!/bin/sh
# Download only. Does not install or restart Enigma2.
set -eu
RAW="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/iptosatpro-final-r70/payload/r70-final.b64"
TARGET="/tmp/iptosatpro-r70-final.ipk"
TMPB64="/tmp/iptosatpro-r70-final.$$-download.b64"
TMPIPK="/tmp/iptosatpro-r70-final.$$-download.ipk"
trap 'rm -f "$TMPB64" "$TMPIPK"' EXIT HUP INT TERM
wget -q -O "$TMPB64" "$RAW"
test -s "$TMPB64"
if command -v base64 >/dev/null 2>&1; then
  base64 -d "$TMPB64" > "$TMPIPK"
else
  python3 - "$TMPB64" "$TMPIPK" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f:
    raw=base64.b64decode(f.read(), validate=False)
with open(sys.argv[2],"wb") as f:
    f.write(raw)
PY
fi
test "$(wc -c < "$TMPIPK" | tr -d ' ')" = "__SIZE__"
if command -v sha256sum >/dev/null 2>&1; then
  echo "__HASH__  $TMPIPK" | sha256sum -c - >/dev/null
else
  python3 - "$TMPIPK" <<'PY'
import sys,hashlib
with open(sys.argv[1],"rb") as f:
    assert hashlib.sha256(f.read()).hexdigest()=="__HASH__", "SHA256 mismatch"
PY
fi
mv -f "$TMPIPK" "$TARGET"
echo "Verified candidate: $TARGET"
echo "No installation performed. Existing plugin remains unchanged."
'''
script = script.replace("__SIZE__", str(info["size"])).replace("__HASH__", info["sha256"])
(ROOT / "download-r70-final.sh").write_text(script, encoding="utf-8")
print("STAGED_R70", {"size": info["size"], "sha256": info["sha256"],
                    "payload": str(dst.relative_to(ROOT)), "production_manifest_untouched":True})
