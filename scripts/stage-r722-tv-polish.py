#!/usr/bin/env python3
"""Publish R72.2 TV polish SHA-pinned BETA on feature branch only."""
import base64,hashlib,importlib.util,json,textwrap
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r722",ROOT/"scripts/build-r722-tv-polish.py")
r722=importlib.util.module_from_spec(sp);sp.loader.exec_module(r722)
VERSION="1.0.46-r72.2-tv-polish-beta"
SIZE=359174
SHA="fdfa391b6ead34b27977be9e9592b60be7a50247bbe45a2a2645e3a5488bdfb1"
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r72-2-tv-polish/payload/r722-tv-polish.b64"

def stage():
    assert json.loads((ROOT/"update.json").read_text())["version"]=="1.0.46-r70-final"
    assert (ROOT/"latest-version.txt").read_text().strip()=="1.0.46-r70-final"
    p=ROOT/"r722-tv-polish-beta.ipk"
    info=r722.build(p);raw=p.read_bytes()
    assert info["version"]==VERSION and info["bytes"]==SIZE and info["sha256"]==SHA
    assert hashlib.sha256(raw).hexdigest()==SHA
    encoded="\n".join(textwrap.wrap(base64.b64encode(raw).decode(),76))+"\n"
    assert base64.b64decode(encoded)==raw
    (ROOT/"payload/r722-tv-polish.b64").write_text(encoded,encoding="ascii")
    (ROOT/"staging").mkdir(exist_ok=True)
    manifest={"version":VERSION,"size":SIZE,"sha256":SHA,
      "notes":"SAT->IPTV R72.2 screen polish from real Vu+ photo. Short native title; 2-line full IPTV channel name; zero SNR meter never looks full; SAT badge not asserted when no SAT lock; more legible metrics and MENU footer. Fast Zap, IPTV player, mapping and preview unchanged.",
      "parts":[URL],"receiver_tested":False,"production_published":False}
    (ROOT/"staging/r722-tv-polish.update.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    sh=r'''#!/bin/sh
# Verified download only: NO receiver changes and no installation.
set -eu
RAW="__RAW__"
TARGET="/tmp/iptosatpro-r722-tv-polish-beta.ipk"
TXT="/tmp/iptosat-r722.$$-download.b64"
PKG="/tmp/iptosat-r722.$$-download.ipk"
trap 'rm -f "$TXT" "$PKG"' EXIT HUP INT TERM
wget -O "$TXT" "$RAW"
test -s "$TXT"
if command -v base64 >/dev/null 2>&1; then
    base64 -d "$TXT" > "$PKG"
else
    python3 - "$TXT" "$PKG" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: dat=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(dat)
PY
fi
test "$(wc -c < "$PKG" | tr -d ' ')" = "__SIZE__"
if command -v sha256sum >/dev/null 2>&1; then
    echo "__SHA__  $PKG" | sha256sum -c -
else
    python3 - "$PKG" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f: assert hashlib.sha256(f.read()).hexdigest()=="__SHA__"
PY
fi
mv "$PKG" "$TARGET"
echo "R72.2 TV POLISH VERIFIED: $TARGET"
echo "NOT INSTALLED; receiver plugin and manual mappings unchanged."
'''
    sh=sh.replace("__RAW__",URL).replace("__SIZE__",str(SIZE)).replace("__SHA__",SHA)
    assert "opkg install" not in sh and "__SHA__" not in sh
    (ROOT/"download-r722-tv-polish.sh").write_text(sh)
    print("R722_BETA_STAGE_OK",json.dumps(manifest,sort_keys=True))

if __name__=="__main__":stage()
