#!/bin/sh
# SHA256-verified opt-in download only; no opkg install, no automatic restart.
set -eu
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r736-autolock-all-safe/payload/r736-automatic-safe-mapping.b64"
TARGET="/tmp/iptosatpro-r736-automatic-safe-mapping-beta.ipk"
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
test "$(wc -c < "$IPK" | tr -d ' ')" = "415216"
if command -v sha256sum >/dev/null 2>&1; then
  echo "9f0335e257ef0e6861efb710b3b41c2970381c3ec595c6c47940d63031c6bbca  $IPK" | sha256sum -c -
else
  python3 - "$IPK" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f: assert hashlib.sha256(f.read()).hexdigest()=="9f0335e257ef0e6861efb710b3b41c2970381c3ec595c6c47940d63031c6bbca"
PY
fi
mv "$IPK" "$TARGET"
echo "R73.6 VERIFIED BETA DOWNLOADED: $TARGET"
echo "NOT INSTALLED. Existing version, mappings and settings remain unchanged."
