#!/usr/bin/env python3
"""Opt-in R72.5 beta downloadable from GitHub after exact package checksum CI."""
import base64,hashlib,importlib.util,json,textwrap
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r725",ROOT/"scripts/build-r725-fuzzy.py")
builder=importlib.util.module_from_spec(sp);sp.loader.exec_module(builder)
VERSION="1.0.46-r72.5-fuzzy-stability-beta"
SIZE=404226
SHA="f4b1c1ab8a23ced1856e95b2481b70e6fbb245af3cd5b36fb0d63a3d3a5983f5"
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r725-fuzzy-no-signal-stability/payload/r725-fuzzy-stability.b64"
TARGET="/tmp/iptosatpro-r725-fuzzy-beta.ipk"

def main():
    assert json.loads((ROOT/"update.json").read_text())["version"]=="1.0.46-r70-final"
    assert (ROOT/"latest-version.txt").read_text().strip()=="1.0.46-r70-final"
    p=ROOT/"r725-fuzzy-stability-beta.ipk"
    meta=builder.build(p)
    data=p.read_bytes()
    assert meta["version"]==VERSION and meta["size"]==SIZE and meta["sha256"]==SHA
    assert hashlib.sha256(data).hexdigest()==SHA
    encoded="\n".join(textwrap.wrap(base64.b64encode(data).decode("ascii"),76))+"\n"
    assert base64.b64decode(encoded)==data
    (ROOT/"payload/r725-fuzzy-stability.b64").write_text(encoded,encoding="ascii")
    (ROOT/"staging").mkdir(exist_ok=True)
    manifest={
        "version":VERSION,"size":SIZE,"sha256":SHA,
        "notes":"R72.5 repeats of SAT evTuneFailed do not cancel in-progress fuzzy SmartMatch for same satellite service/catalogue. Terminal MATCH_BG_DONE or NO_MATCH now reachable, with short same-zap no-match cooldown. Catalog updates and new zaps can retry. All audio/player/Fast Zap/scoring/manual mappings and Preview unchanged.",
        "parts":[URL],"field_tested":False,"production_published":False
    }
    (ROOT/"staging/r725-fuzzy-stability.update.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    shell=r'''#!/bin/sh
# R72.5 checksum download only. Does NOT install, zap, restart, or mutate mappings.
set -eu
URL="__URL__"
TARGET="__TARGET__"
ENC="/tmp/r725.$$-download.b64"
PKG="/tmp/r725.$$-download.ipk"
trap 'rm -f "$ENC" "$PKG"' EXIT HUP INT TERM
wget -O "$ENC" "$URL"
test -s "$ENC"
if command -v base64 >/dev/null 2>&1; then
    base64 -d "$ENC" > "$PKG"
else
    python3 - "$ENC" "$PKG" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: data=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(data)
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
echo "R72.5 FUZZY STABILITY VERIFIED: $TARGET"
echo "NOT INSTALLED. Existing receiver and user mappings unchanged."
'''
    shell=shell.replace("__URL__",URL).replace("__TARGET__",TARGET).replace("__SIZE__",str(SIZE)).replace("__SHA__",SHA)
    assert "opkg install" not in shell and "__SHA__" not in shell
    (ROOT/"download-r725-fuzzy.sh").write_text(shell)
    print("R725_FUZZY_STAGE_OK",json.dumps(manifest,sort_keys=True))

if __name__=="__main__":main()
