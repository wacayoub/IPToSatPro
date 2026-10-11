#!/bin/sh
# R71 UI beta - download and SHA verify only. NO INSTALLATION.
set -eu
RAW="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r71-stability/payload/r71-ui-beta.b64"
TARGET="/tmp/iptosatpro-r71-ui-beta.ipk"
B64="/tmp/iptosat-r71ui.$$-temp.b64"
PKG="/tmp/iptosat-r71ui.$$-temp.ipk"
trap 'rm -f "$B64" "$PKG"' EXIT HUP INT TERM
wget -qO "$B64" "$RAW"
test -s "$B64"
if command -v base64 >/dev/null 2>&1; then
  base64 -d "$B64" > "$PKG"
else
  python3 - "$B64" "$PKG" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: raw=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(raw)
PY
fi
test "$(wc -c < "$PKG" | tr -d ' ')" = "278240"
if command -v sha256sum >/dev/null 2>&1; then
    echo "f61fda976653ef3b17c717f8798cd96277437ec9984402b75bed5c4389634b56  $PKG" | sha256sum -c -
else
    python3 - "$PKG" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f: assert hashlib.sha256(f.read()).hexdigest()=="f61fda976653ef3b17c717f8798cd96277437ec9984402b75bed5c4389634b56"
PY
fi
mv "$PKG" "$TARGET"
echo "R71 UI BETA VERIFIED DOWNLOAD: $TARGET"
echo "NOT INSTALLED: existing R70/R71 unchanged."
