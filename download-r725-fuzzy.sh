#!/bin/sh
# R72.5 checksum download only. Does NOT install, zap, restart, or mutate mappings.
set -eu
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r725-fuzzy-no-signal-stability/payload/r725-fuzzy-stability.b64"
TARGET="/tmp/iptosatpro-r725-fuzzy-beta.ipk"
ENC="/tmp/r725.$$-download.b64"
PKG="/tmp/r725.$$-download.ipk"
trap 'rm -f "$ENC" "$PKG"' EXIT HUP INT TERM
wget -O "$ENC" "$URL"
test -s "$ENC"
if command -v base64 >/dev/null 2>&1; then
    base64 -d "$ENC" > "$PKG"
else
    python3 - "$ENC" "$PKG" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: data=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(data)
PY
fi
test "$(wc -c < "$PKG" | tr -d ' ')" = "404226"
if command -v sha256sum >/dev/null 2>&1; then
    echo "f4b1c1ab8a23ced1856e95b2481b70e6fbb245af3cd5b36fb0d63a3d3a5983f5  $PKG" | sha256sum -c -
else
    python3 - "$PKG" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f: assert hashlib.sha256(f.read()).hexdigest()=="f4b1c1ab8a23ced1856e95b2481b70e6fbb245af3cd5b36fb0d63a3d3a5983f5"
PY
fi
mv "$PKG" "$TARGET"
echo "R72.5 FUZZY STABILITY VERIFIED: $TARGET"
echo "NOT INSTALLED. Existing receiver and user mappings unchanged."
