#!/usr/bin/env python3
"""R72.1 opt-in icon beta publication with pinned SHA, no opkg/no production update."""
import base64,hashlib,importlib.util,json,textwrap
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r721",ROOT/"scripts/build-r721-icons.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
VERSION="1.0.46-r72.1-premium-icons-beta"
SIZE=358772
SHA="5da1148476b471a000f9b2064f0b2e01d4db131f946783b24a70c098ebd97092"
B64_URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r72-1-premium-icons/payload/r721-premium-icons.b64"
TARGET="/tmp/iptosatpro-r721-premium-icons-beta.ipk"

def main():
    assert json.loads((ROOT/"update.json").read_text())["version"]=="1.0.46-r70-final"
    assert (ROOT/"latest-version.txt").read_text().strip()=="1.0.46-r70-final"
    p=ROOT/"r721-premium-icons-beta.ipk"
    info=b.build(p);raw=p.read_bytes()
    assert info["version"]==VERSION and info["size"]==SIZE and info["sha256"]==SHA
    assert hashlib.sha256(raw).hexdigest()==SHA
    encoded="\n".join(textwrap.wrap(base64.b64encode(raw).decode("ascii"),76))+"\n"
    assert base64.b64decode(encoded)==raw
    (ROOT/"payload/r721-premium-icons.b64").write_text(encoded,encoding="ascii")
    (ROOT/"staging").mkdir(exist_ok=True)
    manifest={"version":VERSION,"size":SIZE,"sha256":SHA,
        "notes":"R72.1 premium Enigma2 icons for SAT/IPTV, six metric cards and Preview/Update actions. Decoder-measured SAT and IPTV SD/HD/FHD/4K icons with '?' on unverified. Keeps playback, timeshift, source mapping, R72 live status byte-identical except native labels/background.",
        "parts":[B64_URL],"field_tested":False,"production_published":False}
    (ROOT/"staging/r721-premium-icons.update.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n")
    sh=r'''#!/bin/sh
# R72.1 premium icons: verified download only. NEVER installs/restarts/modifies mappings.
set -eu
RAW="__RAW__"
TARGET="__TARGET__"
B64="/tmp/iptosat-r721.$$-temp.b64"
IPK="/tmp/iptosat-r721.$$-temp.ipk"
trap 'rm -f "$B64" "$IPK"' EXIT HUP INT TERM
wget -O "$B64" "$RAW"
test -s "$B64"
if command -v base64 >/dev/null 2>&1; then
    base64 -d "$B64" > "$IPK"
else
    python3 - "$B64" "$IPK" <<'PY'
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
echo "VERIFIED R72.1 PREMIUM ICONS BETA: $TARGET"
echo "NOT INSTALLED. Existing receiver settings and stream mappings unchanged."
'''
    for a,z in (("__RAW__",B64_URL),("__TARGET__",TARGET),("__SIZE__",str(SIZE)),("__SHA__",SHA)):
        sh=sh.replace(a,z)
    assert "__SHA__" not in sh and "opkg install" not in sh
    (ROOT/"download-r721-premium-icons.sh").write_text(sh)
    print("R721_SAFE_STAGE_OK",json.dumps(manifest,sort_keys=True))

if __name__=="__main__":main()
