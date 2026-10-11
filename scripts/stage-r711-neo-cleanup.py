#!/usr/bin/env python3
"""Stage SHA-pinned R71.1 Neo Cleanup BETA on isolated branch only."""
import base64,hashlib,importlib.util,json,textwrap
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("cleanup",ROOT/"scripts/build-r711-cleanup-beta.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
VERSION="1.0.46-r71.1-neo-cleanup-beta"
SIZE=308552
SHA="ae70b0e84827a5bb0edc8b79abf5ebaf1e98e4ccb64fe10c1f8b5b05cb66cedd"
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r711-neo-cleanup/payload/r711-neo-cleanup.b64"

def main():
    assert json.loads((ROOT/"update.json").read_text())["version"]=="1.0.46-r70-final"
    assert (ROOT/"latest-version.txt").read_text().strip()=="1.0.46-r70-final"
    path=ROOT/"r711-neo-cleanup-beta.ipk"
    meta=b.build(path);raw=path.read_bytes()
    assert meta["version"]==VERSION and meta["bytes"]==SIZE and meta["sha256"]==SHA
    assert hashlib.sha256(raw).hexdigest()==SHA
    encoded="\n".join(textwrap.wrap(base64.b64encode(raw).decode("ascii"),76))+"\n"
    assert base64.b64decode(encoded)==raw
    (ROOT/"payload/r711-neo-cleanup.b64").write_text(encoded,encoding="ascii")
    (ROOT/"staging").mkdir(exist_ok=True)
    manifest={"version":VERSION,"size":SIZE,"sha256":SHA,
              "notes":"R71.1 Neo Cleanup: dashboard screenshot-like rounded PNG cards, real SAT SNR, IPTV source/catalog and candidate metrics, 4 separated badge tiles, GREEN Preview, YELLOW Online Update, BLUE Logs, MENU Settings/Tools. Deep classic Mapping, SmartMatch Test, Player Lock, Auto Scan, Diagnostics moved into Tools. No old features deleted. R70 lock/player/audio/timeshift + R71 Preview matcher untouched. NOT hardware-tested.",
              "parts":[URL],"published_to_main":False,"receiver_tested":False}
    (ROOT/"staging/r711-neo-cleanup.update.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    shell=r'''#!/bin/sh
# Download and SHA verify R71.1 UI cleanup BETA. Does NOT install anything.
set -eu
RAW="__RAW__"
TARGET="/tmp/iptosatpro-r711-neo-cleanup-beta.ipk"
TMPB64="/tmp/iptosat-r711-cleanup.$$-download.b64"
TMPIPK="/tmp/iptosat-r711-cleanup.$$-download.ipk"
trap 'rm -f "$TMPB64" "$TMPIPK"' EXIT HUP INT TERM
wget -qO "$TMPB64" "$RAW"
test -s "$TMPB64"
if command -v base64 >/dev/null 2>&1; then
    base64 -d "$TMPB64" > "$TMPIPK"
else
    python3 - "$TMPB64" "$TMPIPK" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: d=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(d)
PY
fi
test "$(wc -c < "$TMPIPK" | tr -d ' ')" = "__SIZE__"
if command -v sha256sum >/dev/null 2>&1; then
    echo "__SHA__  $TMPIPK" | sha256sum -c - >/dev/null
else
    python3 - "$TMPIPK" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f:
    assert hashlib.sha256(f.read()).hexdigest()=="__SHA__", "SHA256 mismatch"
PY
fi
mv -f "$TMPIPK" "$TARGET"
echo "R71.1 NEO CLEANUP BETA VERIFIED: $TARGET"
echo "NOT INSTALLED: receiver plugin, settings, mappings, player unchanged."
'''
    shell=shell.replace("__RAW__",URL).replace("__SIZE__",str(SIZE)).replace("__SHA__",SHA)
    assert "__RAW__" not in shell and "__SIZE__" not in shell and "__SHA__" not in shell
    assert "opkg install" not in shell and "init 4" not in shell
    (ROOT/"download-r711-neo-cleanup.sh").write_text(shell)
    print("R711_CLEANUP_STAGED",json.dumps(manifest,sort_keys=True))
if __name__=="__main__":main()
