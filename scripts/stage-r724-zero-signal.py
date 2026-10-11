#!/usr/bin/env python3
"""Stage checked R72.4 confirmed SAT-no-lock fallback beta on feature branch ONLY."""
import base64,hashlib,importlib.util,json,textwrap
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r724",ROOT/"scripts/build-r724-zero-signal.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
VERSION="1.0.46-r72.4-zero-signal-beta"
SIZE=403344
SHA="fe779fc4a2c95bea7166c4ce168e18b76416959d9e51b247fdbc809d1b737194"
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r724-zero-signal-fallback/payload/r724-zero-signal.b64"
DEST="/tmp/iptosatpro-r724-zero-signal-beta.ipk"

def main():
    assert json.loads((ROOT/"update.json").read_text())["version"]=="1.0.46-r70-final"
    assert (ROOT/"latest-version.txt").read_text().strip()=="1.0.46-r70-final"
    target=ROOT/"r724-zero-signal-beta.ipk"
    meta=b.build(target)
    blob=target.read_bytes()
    assert meta["version"]==VERSION and meta["size"]==SIZE and meta["sha256"]==SHA
    assert hashlib.sha256(blob).hexdigest()==SHA
    encoded="\n".join(textwrap.wrap(base64.b64encode(blob).decode("ascii"),76))+"\n"
    assert base64.b64decode(encoded)==blob
    (ROOT/"payload/r724-zero-signal.b64").write_text(encoded,encoding="ascii")
    (ROOT/"staging").mkdir(exist_ok=True)
    manifest={
        "version":VERSION,"size":SIZE,"sha256":SHA,
        "notes":"R72.4 zero signal FTA and encrypted IPTV fallback after explicit no-lock/TUNE_FAILED with unchanged DVB PAT deferred safety, exact current SAT service, enabled no-signal fallback; other FTA/locked paths unchanged. New status log NO_SIGNAL_FTA_IPTV_ALLOWED. Existing smart matcher must still have a safe candidate. Receiver hardware test pending.",
        "parts":[URL],"field_tested":False,"production_published":False
    }
    (ROOT/"staging/r724-zero-signal.update.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    shell=r'''#!/bin/sh
# SHA-verified R72.4 beta download only. Does NOT install/change settings/mappings.
set -eu
URL="__URL__"
TARGET="__TARGET__"
ENC="/tmp/iptosat-r724.$$-download.b64"
IPK="/tmp/iptosat-r724.$$-download.ipk"
trap 'rm -f "$ENC" "$IPK"' EXIT HUP INT TERM
wget -O "$ENC" "$URL"
test -s "$ENC"
if command -v base64 >/dev/null 2>&1; then
    base64 -d "$ENC" > "$IPK"
else
    python3 - "$ENC" "$IPK" <<'PY'
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
    assert hashlib.sha256(f.read()).hexdigest()=="__SHA__", "SHA mismatch"
PY
fi
mv "$IPK" "$TARGET"
echo "R72.4 NO SIGNAL BETA VERIFIED: $TARGET"
echo "NOT INSTALLED. SAT and IPTV mappings unchanged."
'''
    for old,new in (("__URL__",URL),("__TARGET__",DEST),("__SIZE__",str(SIZE)),("__SHA__",SHA)):
        shell=shell.replace(old,new)
    assert "__SHA__" not in shell and "opkg install" not in shell
    (ROOT/"download-r724-zero-signal.sh").write_text(shell)
    print("R724_VERIFIED_STAGE_OK",json.dumps(manifest,sort_keys=True))
if __name__=="__main__":main()
