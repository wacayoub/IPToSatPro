#!/usr/bin/env python3
"""Stage opt-in R72.3 Neo Classic Premium without touching production updater."""
import base64,hashlib,importlib.util,json,textwrap
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r723",ROOT/"scripts/build-r723-classic-fusion.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
VERSION="1.0.46-r72.3-classic-premium-beta"
SIZE=402536
SHA="b76e9fb551cef1d0422d6303f3d74e38b94cadae6fda6b6f90d6eecf7739afa3"
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r723-neo-classic-fusion/payload/r723-neo-classic-premium.b64"

def stage():
    assert json.loads((ROOT/"update.json").read_text())["version"]=="1.0.46-r70-final"
    assert (ROOT/"latest-version.txt").read_text().strip()=="1.0.46-r70-final"
    pkg=ROOT/"r723-neo-classic-fusion-beta.ipk"
    metadata=b.build(pkg)
    content=pkg.read_bytes()
    assert metadata["size"]==SIZE and metadata["sha256"]==SHA and metadata["version"]==VERSION
    assert hashlib.sha256(content).hexdigest()==SHA
    b64="\n".join(textwrap.wrap(base64.b64encode(content).decode("ascii"),76))+"\n"
    assert base64.b64decode(b64)==content
    (ROOT/"payload/r723-neo-classic-premium.b64").write_text(b64,encoding="ascii")
    (ROOT/"staging").mkdir(exist_ok=True)
    manifest={"version":VERSION,"size":SIZE,"sha256":SHA,
      "notes":"R72.3 Classic Premium: restore original R71.1 Neo Dark dashboard as DEFAULT with updated native SAT/IPTV icons, measured video resolution, catalog audio, IPTV provider and measured first-frame speed. Current R72 Live Monitor remains selectable in MENU > Appearance > Home layout. No player, matching, sources, audio, timeshift or mapping changes. Receiver field validation pending.",
      "parts":[URL],"field_tested":False,"published_to_main":False}
    (ROOT/"staging/r723-neo-classic-premium.update.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    shell=r'''#!/bin/sh
# Download and SHA verify ONLY. Does not install or alter receiver configuration.
set -eu
RAW="__URL__"
TARGET="/tmp/iptosatpro-r723-neo-classic-beta.ipk"
TMPB64="/tmp/r723.$$-download.b64"
TMPIPK="/tmp/r723.$$-download.ipk"
trap 'rm -f "$TMPB64" "$TMPIPK"' EXIT HUP INT TERM
wget -O "$TMPB64" "$RAW"
test -s "$TMPB64"
if command -v base64 >/dev/null 2>&1; then
    base64 -d "$TMPB64" > "$TMPIPK"
else
    python3 - "$TMPB64" "$TMPIPK" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: content=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(content)
PY
fi
test "$(wc -c < "$TMPIPK" | tr -d ' ')" = "__SIZE__"
if command -v sha256sum >/dev/null 2>&1; then
    echo "__SHA__  $TMPIPK" | sha256sum -c -
else
    python3 - "$TMPIPK" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f:
    assert hashlib.sha256(f.read()).hexdigest()=="__SHA__"
PY
fi
mv "$TMPIPK" "$TARGET"
echo "R72.3 NEO CLASSIC PREMIUM VERIFIED: $TARGET"
echo "NOT INSTALLED, existing receiver settings and mappings unchanged."
'''
    shell=shell.replace("__URL__",URL).replace("__SIZE__",str(SIZE)).replace("__SHA__",SHA)
    assert "__SHA__" not in shell and "opkg install" not in shell
    (ROOT/"download-r723-classic-premium.sh").write_text(shell)
    print("R723_STAGING_VERIFIED",json.dumps(manifest,sort_keys=True))

if __name__=="__main__":stage()
