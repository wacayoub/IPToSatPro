#!/usr/bin/env python3
"""Publish downloadable opt-in UI beta on isolated branch, never main/update.json."""
import base64, hashlib, importlib.util, json, textwrap
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("ui_builder",ROOT/"scripts/build-r71-ui-beta.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
VERSION="1.0.46-r71-ui-beta"
SIZE=278240
SHA="f61fda976653ef3b17c717f8798cd96277437ec9984402b75bed5c4389634b56"
BRANCH="feature/r71-stability"
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/"+BRANCH+"/payload/r71-ui-beta.b64"

def main():
    assert json.loads((ROOT/"update.json").read_text())["version"]=="1.0.46-r70-final"
    assert (ROOT/"latest-version.txt").read_text().strip()=="1.0.46-r70-final"
    path=ROOT/"r71-ui-beta.ipk"
    info=b.build(path);raw=path.read_bytes()
    assert info["version"]==VERSION and info["size"]==SIZE and info["sha256"]==SHA
    assert hashlib.sha256(raw).hexdigest()==SHA
    text="\n".join(textwrap.wrap(base64.b64encode(raw).decode(),76))+"\n"
    assert base64.b64decode(text)==raw
    (ROOT/"payload/r71-ui-beta.b64").write_text(text,encoding="ascii")
    manifest={"version":VERSION,"size":SIZE,"sha256":SHA,
         "notes":"R71 UI BETA Home GREEN direct Preview; Preview All Sources P/B1/B2 automatic 48 candidates and YELLOW deeper 72, manual source screen on 4; unchanged R71 matching and R70 player/locked zap/audio/timeshift. Receiver UI not field-verified.",
         "parts":[URL],"production_published":False,"receiver_tested":False}
    (ROOT/"staging/r71-ui-beta.update.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    script=r'''#!/bin/sh
# R71 UI beta - download and SHA verify only. NO INSTALLATION.
set -eu
RAW="__RAW__"
TARGET="/tmp/iptosatpro-r71-ui-beta.ipk"
B64="/tmp/iptosat-r71ui.$$-temp.b64"
PKG="/tmp/iptosat-r71ui.$$-temp.ipk"
trap 'rm -f "$B64" "$PKG"' EXIT HUP INT TERM
wget -qO "$B64" "$RAW"
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
    echo "__SHA__  $PKG" | sha256sum -c -
else
    python3 - "$PKG" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f: assert hashlib.sha256(f.read()).hexdigest()=="__SHA__"
PY
fi
mv "$PKG" "$TARGET"
echo "R71 UI BETA VERIFIED DOWNLOAD: $TARGET"
echo "NOT INSTALLED: existing R70/R71 unchanged."
'''
    script=script.replace("__RAW__",URL).replace("__SIZE__",str(SIZE)).replace("__SHA__",SHA)
    assert "__RAW__" not in script and "__SIZE__" not in script and "__SHA__" not in script
    assert "opkg install" not in script
    (ROOT/"download-r71-ui-beta.sh").write_text(script)
    print("R71_UI_STAGED",json.dumps(manifest,sort_keys=True))
if __name__=="__main__":main()
