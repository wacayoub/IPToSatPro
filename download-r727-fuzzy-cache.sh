#!/bin/sh
# SHA-verified download only: no opkg, restart, changes to user mapping.
set -eu
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r727-fast-playback-audit/payload/r727-fuzzy-cache.b64"
TARGET="/tmp/iptosatpro-r727-fuzzy-cache-beta.ipk"
ENC="/tmp/iptosat-r727.$$-download.b64"
IPK="/tmp/iptosat-r727.$$-download.ipk"
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
test "$(wc -c < "$IPK" | tr -d ' ')" = "405774"
if command -v sha256sum >/dev/null 2>&1; then
    echo "cd638f40b1bbfcbbc9007634a59683f159cb415a4668190269a5aa1ec4ab0d62  $IPK" | sha256sum -c -
else
    python3 - "$IPK" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f: assert hashlib.sha256(f.read()).hexdigest()=="cd638f40b1bbfcbbc9007634a59683f159cb415a4668190269a5aa1ec4ab0d62"
PY
fi
mv "$IPK" "$TARGET"
echo "R72.7 FUZZY CACHE VERIFIED: $TARGET"
echo "NOT INSTALLED. Plugin, user settings and mappings unchanged."
