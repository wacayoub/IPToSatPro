#!/bin/sh
# IPToSatPro R73.8 opt-in beta: verified download, optional installation.
# Does not change main update.json or install automatically unless --install.
set -eu
BASE="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r738-auto-open-on-safe-match"
OUT="/tmp/iptosatpro-r738-safe-auto-play-beta.ipk"
WORK="/tmp/iptosatpro-r738-verify-$$"
mkdir -p "$WORK"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
wget -qO "$WORK/meta.json" "$BASE/staging/r738-safe-auto-play.update.json"
wget -qO "$WORK/package.b64" "$BASE/payload/r738-safe-auto-play.b64"
base64 -d "$WORK/package.b64" > "$WORK/package.ipk"
python3 - "$WORK/meta.json" "$WORK/package.ipk" <<'PY'
import json,hashlib,os,sys
meta=json.load(open(sys.argv[1]))
path=sys.argv[2]
size=os.path.getsize(path)
digest=hashlib.sha256(open(path,'rb').read()).hexdigest()
expected_version="1.0.46-r73.8-safe-auto-play-beta"
assert meta.get("version")==expected_version,"Unexpected version"
assert meta.get("beta") is True,"Production package not expected"
assert size==int(meta["size"]),"Package size verification FAILED"
assert digest==meta["sha256"],"SHA256 verification FAILED"
print("R73.8 VERIFIED: %s (%d bytes, SHA256 %s)"%(expected_version,size,digest))
PY
mv "$WORK/package.ipk" "$OUT"
echo "VERIFIED PACKAGE: $OUT"
if [ "${1:-}" = "--install" ]; then
  BACKUP="/tmp/iptosatpro-pre-r738-$(date +%Y%m%d%H%M%S).tar.gz"
  tar czf "$BACKUP" /etc/enigma2/SatIPTVBridge /etc/enigma2/settings 2>/dev/null || {
    echo "Backup could not be completed; installation cancelled."
    exit 2
  }
  echo "BACKUP: $BACKUP"
  opkg install --force-reinstall "$OUT"
  echo "R73.8 installed. Restart Enigma2 GUI once from OpenATV menus."
else
  echo "Download complete: NO installation performed."
  echo "To install intentionally: sh /tmp/download-r738-beta.sh --install"
fi
