#!/usr/bin/env python3
"""SHA-256 checked R72 beta staging, isolated from production online update."""
import base64,hashlib,importlib.util,json,textwrap
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r72",ROOT/"scripts/build-r72-live-monitor.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
VERSION="1.0.46-r72-live-monitor-beta"
SIZE=314512
SHA="6bb68ed906637c19e8e22a33a66165db53044a759258d19e39ec1898dee2c8d0"
RAW="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r72-sat-iptv-live-monitor/payload/r72-live-monitor.b64"
TARGET="/tmp/iptosatpro-r72-live-monitor-beta.ipk"

def stage():
    assert json.loads((ROOT/"update.json").read_text())["version"]=="1.0.46-r70-final"
    assert (ROOT/"latest-version.txt").read_text().strip()=="1.0.46-r70-final"
    p=ROOT/"r72-live-monitor-beta.ipk"
    metadata=b.build(p);blob=p.read_bytes()
    assert metadata["size"]==SIZE and metadata["sha256"]==SHA and metadata["version"]==VERSION
    assert hashlib.sha256(blob).hexdigest()==SHA
    encoded="\n".join(textwrap.wrap(base64.b64encode(blob).decode("ascii"),76))+"\n"
    assert base64.b64decode(encoded)==blob
    (ROOT/"payload/r72-live-monitor.b64").write_text(encoded,encoding="ascii")
    (ROOT/"staging").mkdir(exist_ok=True)
    manifest={
      "version":VERSION,"size":SIZE,"sha256":SHA,"parts":[RAW],
      "description":"R72 BETA two separate SAT/IPTV current channel cards; SAT SNR, providers, source role, manual mapping lock vs confirmed first video, decoded resolution vs claimed, real first-image speed, SAT audio language and IPTV catalog language; audio/video codec explicitly N/A until supported. Preview/fast zap/player unchanged.",
      "field_tested":False,"published_to_main":False,
    }
    (ROOT/"staging/r72-live-monitor.update.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    sh=r'''#!/bin/sh
# Verified download ONLY. No opkg, restart, playback, mappings or user settings changes.
set -eu
RAW="__URL__"
TARGET="__TARGET__"
B64="/tmp/iptosat-r72.$$-download.b64"
PKG="/tmp/iptosat-r72.$$-download.ipk"
trap 'rm -f "$B64" "$PKG"' EXIT HUP INT TERM
wget -qO "$B64" "$RAW"
test -s "$B64"
if command -v base64 >/dev/null 2>&1; then
    base64 -d "$B64" > "$PKG"
else
    python3 - "$B64" "$PKG" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: payload=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(payload)
PY
fi
test "$(wc -c < "$PKG" | tr -d ' ')" = "__SIZE__"
if command -v sha256sum >/dev/null 2>&1; then
    echo "__SHA__  $PKG" | sha256sum -c - >/dev/null
else
    python3 - "$PKG" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f:
    assert hashlib.sha256(f.read()).hexdigest()=="__SHA__", "SHA-256 verification failed"
PY
fi
mv -f "$PKG" "$TARGET"
echo "R72 BETA VERIFIED DOWNLOAD: $TARGET"
echo "NOT INSTALLED. Running receiver version and mappings unchanged."
'''
    for frm,to in [("__URL__",RAW),("__TARGET__",TARGET),("__SIZE__",str(SIZE)),("__SHA__",SHA)]:
        sh=sh.replace(frm,to)
    assert "opkg " not in sh and "__SHA__" not in sh
    (ROOT/"download-r72-live-monitor.sh").write_text(sh)
    print("R72_STAGED_AND_PINNED",json.dumps(manifest,sort_keys=True))

if __name__=="__main__":stage()
