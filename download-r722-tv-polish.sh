#!/bin/sh
# Verified download only: NO receiver changes and no installation.
set -eu
RAW="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r72-2-tv-polish/payload/r722-tv-polish.b64"
TARGET="/tmp/iptosatpro-r722-tv-polish-beta.ipk"
TXT="/tmp/iptosat-r722.$$-download.b64"
PKG="/tmp/iptosat-r722.$$-download.ipk"
trap 'rm -f "$TXT" "$PKG"' EXIT HUP INT TERM
wget -O "$TXT" "$RAW"
test -s "$TXT"
if command -v base64 >/dev/null 2>&1; then
    base64 -d "$TXT" > "$PKG"
else
    python3 - "$TXT" "$PKG" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: dat=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(dat)
PY
fi
test "$(wc -c < "$PKG" | tr -d ' ')" = "359174"
if command -v sha256sum >/dev/null 2>&1; then
    echo "fdfa391b6ead34b27977be9e9592b60be7a50247bbe45a2a2645e3a5488bdfb1  $PKG" | sha256sum -c -
else
    python3 - "$PKG" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f: assert hashlib.sha256(f.read()).hexdigest()=="fdfa391b6ead34b27977be9e9592b60be7a50247bbe45a2a2645e3a5488bdfb1"
PY
fi
mv "$PKG" "$TARGET"
echo "R72.2 TV POLISH VERIFIED: $TARGET"
echo "NOT INSTALLED; receiver plugin and manual mappings unchanged."
