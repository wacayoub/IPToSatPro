#!/bin/sh
# SHA256-verified opt-in download only; no opkg install, no automatic restart.
set -eu
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r731-preview-core-recovery/payload/r731-preview-recovery.b64"
TARGET="/tmp/iptosatpro-r731-preview-recovery-beta.ipk"
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
test "$(wc -c < "$IPK" | tr -d ' ')" = "409874"
if command -v sha256sum >/dev/null 2>&1; then
  echo "2ed09630f46066e7376a47858edd4f425d2df0ef56227a66a067bccd0d91e85d  $IPK" | sha256sum -c -
else
  python3 - "$IPK" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f: assert hashlib.sha256(f.read()).hexdigest()=="2ed09630f46066e7376a47858edd4f425d2df0ef56227a66a067bccd0d91e85d"
PY
fi
mv "$IPK" "$TARGET"
echo "R73.1 VERIFIED BETA DOWNLOADED: $TARGET"
echo "NOT INSTALLED. Existing version, mappings and settings remain unchanged."
