#!/bin/sh
# R74 unified Preview beta - download/verify ONLY by default.
# Explicit --install backs up local mapping/settings and installs the signed-checksum IPK.
set -eu
BASE='https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r74-unified-preview-actual-bouquet'
WORK="/tmp/iptosat-r74-$$"
OUT="/tmp/iptosatpro-r74-unified-beta.ipk"
mkdir -p "$WORK"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
wget -qO "$WORK/manifest.json" "$BASE/staging/r74-unified-preview.update.json"
wget -qO "$WORK/payload.b64" "$BASE/payload/r74-unified-preview.b64"
base64 -d "$WORK/payload.b64" > "$WORK/result.ipk"
python3 - "$WORK/manifest.json" "$WORK/result.ipk" <<'PY'
import hashlib,json,os,sys
m=json.load(open(sys.argv[1]))
data=open(sys.argv[2],"rb").read()
assert m["version"]=="1.0.46-r74.2-preview-close-hotfix-beta","Unexpected version"
assert m.get("beta") is True,"Not a beta manifest"
assert len(data)==int(m["size"]),"Invalid IPK size"
assert hashlib.sha256(data).hexdigest()==m["sha256"],"INVALID IPK SHA256"
print("R74 VERIFIED %s bytes=%d SHA256=%s"%(m["version"],len(data),m["sha256"]))
PY
mv "$WORK/result.ipk" "$OUT"
echo "PACKAGE $OUT"
if [ "${1:-}" = "--install" ]; then
  SAVE="/tmp/iptosatpro-pre-r74-$(date +%Y%m%d-%H%M%S).tar.gz"
  tar czf "$SAVE" /etc/enigma2/SatIPTVBridge /etc/enigma2/settings 2>/dev/null || {
    echo 'Backup unavailable: no installation performed.'
    exit 2
  }
  echo "BACKUP $SAVE"
  opkg install --force-reinstall "$OUT"
  echo 'R74 beta installed. Restart only Enigma2 GUI via OpenATV menu.'
else
  echo 'Download verified. NO receiver changes were made.'
  echo 'To install: sh /tmp/download-r74-beta.sh --install'
fi
