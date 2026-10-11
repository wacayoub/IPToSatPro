#!/usr/bin/env python3
"""Stage reproducible R72.7 fuzzy cache BETA, isolated from main online update."""
import base64,hashlib,importlib.util,json,textwrap
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r727",ROOT/"scripts/build-r727-fast.py")
builder=importlib.util.module_from_spec(sp);sp.loader.exec_module(builder)
VERSION="1.0.46-r72.7-fuzzy-cache-beta"
SIZE=405774
SHA="cd638f40b1bbfcbbc9007634a59683f159cb415a4668190269a5aa1ec4ab0d62"
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r727-fast-playback-audit/payload/r727-fuzzy-cache.b64"
TARGET="/tmp/iptosatpro-r727-fuzzy-cache-beta.ipk"

def stage():
    assert json.loads((ROOT/"update.json").read_text())["version"]=="1.0.46-r70-final"
    assert (ROOT/"latest-version.txt").read_text().strip()=="1.0.46-r70-final"
    pkg=ROOT/"r727-fuzzy-cache-beta.ipk"
    data=builder.build(pkg);blob=pkg.read_bytes()
    assert data["size"]==SIZE and data["sha256"]==SHA and data["version"]==VERSION
    assert hashlib.sha256(blob).hexdigest()==SHA
    encoded="\n".join(textwrap.wrap(base64.b64encode(blob).decode("ascii"),76))+"\n"
    assert base64.b64decode(encoded)==blob
    (ROOT/"payload/r727-fuzzy-cache.b64").write_text(encoded,encoding="ascii")
    (ROOT/"staging").mkdir(exist_ok=True)
    manifest={"version":VERSION,"size":SIZE,"sha256":SHA,"parts":[URL],
      "notes":"R72.7 performance BETA: cache exactly scored expensive fuzzy SmartMatch for 90 seconds, max 16 SAT identities, same user language/market/provider/quality context, invalidation on measured resolution updates. No changes to score, manual mappings, receiver playback, PAT, audio, Timeshift, direct Fast Zap. Cold searches and slow IPTV upstream still can exceed 2 seconds.",
      "hardware_tested":False,"production_published":False}
    (ROOT/"staging/r727-fuzzy-cache.update.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    sh=r'''#!/bin/sh
# SHA-verified download only: no opkg, restart, changes to user mapping.
set -eu
URL="__URL__"
TARGET="__TARGET__"
ENC="/tmp/iptosat-r727.$$-download.b64"
IPK="/tmp/iptosat-r727.$$-download.ipk"
trap 'rm -f "$ENC" "$IPK"' EXIT HUP INT TERM
wget -O "$ENC" "$URL"
test -s "$ENC"
if command -v base64 >/dev/null 2>&1; then
    base64 -d "$ENC" > "$IPK"
else
    python3 - "$ENC" "$IPK" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: raw=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(raw)
PY
fi
test "$(wc -c < "$IPK" | tr -d ' ')" = "__SIZE__"
if command -v sha256sum >/dev/null 2>&1; then
    echo "__SHA__  $IPK" | sha256sum -c -
else
    python3 - "$IPK" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f: assert hashlib.sha256(f.read()).hexdigest()=="__SHA__"
PY
fi
mv "$IPK" "$TARGET"
echo "R72.7 FUZZY CACHE VERIFIED: $TARGET"
echo "NOT INSTALLED. Plugin, user settings and mappings unchanged."
'''
    sh=sh.replace("__URL__",URL).replace("__TARGET__",TARGET).replace("__SIZE__",str(SIZE)).replace("__SHA__",SHA)
    assert "__SHA__" not in sh and "opkg install" not in sh
    (ROOT/"download-r727-fuzzy-cache.sh").write_text(sh)
    print("R727_VERIFIED_STAGE_OK",json.dumps(manifest,sort_keys=True))

if __name__=="__main__":stage()
