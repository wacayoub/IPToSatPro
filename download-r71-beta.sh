#!/bin/sh
# DOWNLOAD ONLY: no installation, no restart, no settings/mappings touched.
set -eu
RAW="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r71-stability/payload/r71-beta.b64"
TARGET="/tmp/iptosatpro-r71-beta.ipk"
B64="/tmp/iptosatpro-r71.$$-download.b64"
PKG="/tmp/iptosatpro-r71.$$-download.ipk"
trap 'rm -f "$B64" "$PKG"' EXIT HUP INT TERM
wget -q -O "$B64" "$RAW"
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
test "$(wc -c < "$PKG" | tr -d ' ')" = "277614"
if command -v sha256sum >/dev/null 2>&1; then
    echo "2fe47964933906522680114f7d3ac23aee928caf4dd7e02554a8cd183d2980f3  $PKG" | sha256sum -c - >/dev/null
else
    python3 - "$PKG" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f:
    assert hashlib.sha256(f.read()).hexdigest()=="2fe47964933906522680114f7d3ac23aee928caf4dd7e02554a8cd183d2980f3", "SHA256 mismatch"
PY
fi
mv -f "$PKG" "$TARGET"
echo "R71 BETA VERIFIED DOWNLOAD: $TARGET"
echo "NOT INSTALLED. R70 running plugin and all receiver settings unchanged."
