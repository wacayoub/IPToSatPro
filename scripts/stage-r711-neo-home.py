#!/usr/bin/env python3
"""Checksum pinned staging of R71.1 Neo Home on experimental branch ONLY."""
import base64,hashlib,importlib.util,json,textwrap
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("r711_builder",ROOT/"scripts/build-r711-neo-home.py")
b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
VERSION="1.0.46-r71.1-neo-home-beta"
SIZE=279792
SHA="e6108f374ac7aa5a5ac8f06bb0c707e94c1932754f75ee62b25091609bef68ff"
RAW="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r71-1-neo-home/payload/r711-neo-home-beta.b64"

def main():
    assert json.loads((ROOT/"update.json").read_text())["version"]=="1.0.46-r70-final"
    assert (ROOT/"latest-version.txt").read_text().strip()=="1.0.46-r70-final"
    path=ROOT/"r71.1-neo-home-beta.ipk"
    meta=b.build(path)
    raw=path.read_bytes()
    assert meta["version"]==VERSION and meta["size"]==SIZE and meta["sha256"]==SHA
    assert hashlib.sha256(raw).hexdigest()==SHA
    enc="\n".join(textwrap.wrap(base64.b64encode(raw).decode("ascii"),76))+"\n"
    assert base64.b64decode(enc)==raw
    (ROOT/"payload/r711-neo-home-beta.b64").write_text(enc,encoding="ascii")
    (ROOT/"staging").mkdir(exist_ok=True)
    manifest={"version":VERSION,"size":SIZE,"sha256":SHA,
              "notes":"R71.1 Neo Home FHD 1660x900: live SAT SNR bar, real IPTV catalog/status, stream identity/quality and persisted manual-lock status. GREEN Preview All, YELLOW Online Update, BLUE Logs, MENU Settings. Fast Zap/Preview/audio/timeshift unchanged. Rendering on receiver NOT verified.",
              "parts":[RAW],"published_to_main":False,"receiver_tested":False}
    (ROOT/"staging/r711-neo-home.update.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    shell=r'''#!/bin/sh
# VERIFIED DOWNLOAD ONLY. No installation, GUI restart, mappings changes.
set -eu
RAW="__RAW__"
TARGET="/tmp/iptosatpro-r711-neo-home-beta.ipk"
TMPB64="/tmp/iptosat-r711.$$-download.b64"
TMPIPK="/tmp/iptosat-r711.$$-download.ipk"
trap 'rm -f "$TMPB64" "$TMPIPK"' EXIT HUP INT TERM
wget -qO "$TMPB64" "$RAW"
test -s "$TMPB64"
if command -v base64 >/dev/null 2>&1; then
  base64 -d "$TMPB64" > "$TMPIPK"
else
  python3 - "$TMPB64" "$TMPIPK" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: raw=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(raw)
PY
fi
test "$(wc -c < "$TMPIPK" | tr -d ' ')" = "__SIZE__"
if command -v sha256sum >/dev/null 2>&1; then
  echo "__SHA__  $TMPIPK" | sha256sum -c - >/dev/null
else
  python3 - "$TMPIPK" <<'PY'
import sys,hashlib
with open(sys.argv[1],"rb") as f:
    assert hashlib.sha256(f.read()).hexdigest()=="__SHA__"
PY
fi
mv -f "$TMPIPK" "$TARGET"
echo "R71.1 NEO HOME BETA VERIFIED: $TARGET"
echo "NOT INSTALLED: receiver plugin, settings, mappings and player unchanged."
'''
    shell=shell.replace("__RAW__",RAW).replace("__SIZE__",str(SIZE)).replace("__SHA__",SHA)
    assert "__RAW__" not in shell and "__SIZE__" not in shell and "__SHA__" not in shell
    assert "opkg install" not in shell and "init 4" not in shell
    (ROOT/"download-r711-neo-home.sh").write_text(shell)
    print("R711_HOME_STAGED",json.dumps(manifest,sort_keys=True))
if __name__=="__main__":
    main()
