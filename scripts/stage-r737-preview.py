#!/usr/bin/env python3
"""Stage opt-in R73.7 visible fullscreen Preview beta on its isolated feature branch only.

SHA-verified, no production updater change, never auto-install on receiver.
"""
import base64,hashlib,importlib.util,json,textwrap
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r73",ROOT/"scripts/build-r73-preview.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
VERSION="1.0.46-r73.7-visible-video-preview-beta"
SIZE=415986
SHA="d5ebcfad771207ca572ff32613ff01c5f83432c45d6e4e2d99bd05cedd9f5d62"
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r737-video-visible-preview/payload/r737-visible-video-preview.b64"
TARGET="/tmp/iptosatpro-r737-visible-video-preview-beta.ipk"

def stage():
    assert json.loads((ROOT/"update.json").read_text())["version"]=="1.0.46-r70-final"
    assert (ROOT/"latest-version.txt").read_text().strip()=="1.0.46-r70-final"
    pkg=ROOT/"r737-visible-video-preview-beta.ipk"
    result=b.build(pkg)
    blob=pkg.read_bytes()
    assert result["size"]==SIZE and result["sha256"]==SHA and result["version"]==VERSION
    assert hashlib.sha256(blob).hexdigest()==SHA
    encoded="\n".join(textwrap.wrap(base64.b64encode(blob).decode("ascii"),76))+"\n"
    assert base64.b64decode(encoded)==blob
    (ROOT/"payload/r737-visible-video-preview.b64").write_text(encoded,encoding="ascii")
    manifest={"version":VERSION,"size":SIZE,"sha256":SHA,"parts":[URL],
      "notes":"R73.7 video visibility: after OK, temporarily hide opaque Neo Dark Preview to expose selected IPTV picture fullscreen for 8 seconds, then restore candidate list via independent timer. Log PREVIEW_VIDEO_WINDOW and decoder state. This is not proof that the stream carries video; AUTO mapping remains metadata-based; r73.6 AutoScan and manual corrections preserved. Player, timeshift and mappings unchanged. Playback/monitor/timeshift preserved. Not tested on receiver.",
      "hardware_tested":False,"production_published":False}
    (ROOT/"staging").mkdir(exist_ok=True)
    (ROOT/"staging/r737-visible-video-preview.update.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    sh=r'''#!/bin/sh
# SHA256-verified opt-in download only; no opkg install, no automatic restart.
set -eu
URL="__URL__"
TARGET="__TARGET__"
ENC="/tmp/iptosat-r73.$$-download.b64"
IPK="/tmp/iptosat-r73.$$-download.ipk"
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
echo "R73.7 VERIFIED BETA DOWNLOADED: $TARGET"
echo "NOT INSTALLED. Existing version, mappings and settings remain unchanged."
'''
    sh=sh.replace("__URL__",URL).replace("__TARGET__",TARGET).replace("__SIZE__",str(SIZE)).replace("__SHA__",SHA)
    assert not any(line.lstrip().startswith("opkg ") for line in sh.splitlines()) and "__SHA__" not in sh
    (ROOT/"download-r737-preview.sh").write_text(sh)
    print("R737_VERIFIED_STAGE_OK",json.dumps(manifest,sort_keys=True))

if __name__=="__main__":
    stage()
