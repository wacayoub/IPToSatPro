#!/usr/bin/env python3
"""Publish SHA-256 pinned R72.6 Digi 24 safe BETA, branch-only, download-only."""
import base64,hashlib,importlib.util,json,textwrap
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r726",R/"scripts/build-r726-safe-match.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
VERSION="1.0.46-r72.6-digi24-safe-beta"
SIZE=405038
SHA="9b7efbef03368c9a97b86c265574dbd9389401b7d5b014a50e427eaaf267859b"
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r726-digi24-safe-match/payload/r726-digi24-safe.b64"
TARGET="/tmp/iptosatpro-r726-digi24-safe-beta.ipk"

def main():
    assert json.loads((R/"update.json").read_text())["version"]=="1.0.46-r70-final"
    p=R/"r726-digi24-safe-beta.ipk"
    meta=b.build(p);blob=p.read_bytes()
    assert meta["size"]==SIZE and meta["sha256"]==SHA and meta["version"]==VERSION
    assert hashlib.sha256(blob).hexdigest()==SHA
    base64txt="\n".join(textwrap.wrap(base64.b64encode(blob).decode(),76))+"\n"
    assert base64.b64decode(base64txt)==blob
    (R/"payload/r726-digi24-safe.b64").write_text(base64txt,encoding="ascii")
    (R/"staging").mkdir(exist_ok=True)
    manifest={"version":VERSION,"size":SIZE,"sha256":SHA,"parts":[URL],
      "notes":"R72.6 guarded Digi 24 HD on no-signal SAT: exact RO: DIGI 24 HD/FHD, score>=65, confirmed tuner failure, no hard language/market/number identity reject, and no user rejected candidate; all other streams keep threshold 82; preserves Fast Zap, player, timeshift, Preview, mappings and R72.5 fuzzy stability.",
      "hardware_tested":False,"published_to_main":False}
    (R/"staging/r726-digi24-safe.update.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    sh=r'''#!/bin/sh
# R72.6 verified download only; no installation or receiver changes.
set -eu
URL="__URL__"
TARGET="__TARGET__"
TXT="/tmp/r726.$$-download.b64"
IPK="/tmp/r726.$$-download.ipk"
trap 'rm -f "$TXT" "$IPK"' EXIT HUP INT TERM
wget -O "$TXT" "$URL"
test -s "$TXT"
if command -v base64 >/dev/null 2>&1; then
    base64 -d "$TXT" > "$IPK"
else
    python3 - "$TXT" "$IPK" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: data=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(data)
PY
fi
test "$(wc -c < "$IPK" | tr -d ' ')" = "__SIZE__"
if command -v sha256sum >/dev/null 2>&1; then
    echo "__SHA__  $IPK" | sha256sum -c -
else
    python3 - "$IPK" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f:
    assert hashlib.sha256(f.read()).hexdigest()=="__SHA__"
PY
fi
mv "$IPK" "$TARGET"
echo "R72.6 DIGI 24 SAFE BETA VERIFIED: $TARGET"
echo "NOT INSTALLED; receiver settings and mappings unchanged."
'''
    for x,y in (("__URL__",URL),("__TARGET__",TARGET),("__SIZE__",str(SIZE)),("__SHA__",SHA)):
        sh=sh.replace(x,y)
    assert "opkg install" not in sh
    (R/"download-r726-digi24.sh").write_text(sh)
    print("R726_DIGI24_STAGE_OK",json.dumps(manifest,sort_keys=True))
if __name__=="__main__":main()
