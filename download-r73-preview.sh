#!/bin/sh
# SHA256-verified opt-in download only; no opkg install, no automatic restart.
set -eu
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r73-preview-browser-pro/payload/r73-preview-browser.b64"
TARGET="/tmp/iptosatpro-r73-preview-browser-beta.ipk"
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
test "$(wc -c < "$IPK" | tr -d ' ')" = "407996"
if command -v sha256sum >/dev/null 2>&1; then
  echo "969d26dbfeb045f990d42b4d294c0513f03a8f757d9b10c758f06ad4f32758d7  $IPK" | sha256sum -c -
else
  python3 - "$IPK" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f: assert hashlib.sha256(f.read()).hexdigest()=="969d26dbfeb045f990d42b4d294c0513f03a8f757d9b10c758f06ad4f32758d7"
PY
fi
mv "$IPK" "$TARGET"
echo "R73 VERIFIED BETA DOWNLOADED: $TARGET"
echo "NOT INSTALLED. Existing version, mappings and settings remain unchanged."
