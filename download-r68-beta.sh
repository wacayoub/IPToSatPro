#!/bin/sh
set -eu

URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/main/payload/r68-beta.b64"
OUT="/tmp/iptosatpro.ipk"
B64="/tmp/iptosatpro-r68-beta.b64"
EXPECTED_SIZE="276082"
EXPECTED_SHA256="d2d14f38180807e6060cbbb8927e56fe0d4aa03025ccfff061ea70f1d3f09844"

rm -f "$OUT" "$B64"
echo "Downloading IPToSat Pro r68-beta..."
wget -q -O "$B64" "$URL"
test -s "$B64"

if command -v base64 >/dev/null 2>&1; then
    base64 -d "$B64" > "$OUT"
else
    python3 - "$B64" "$OUT" <<'PY'
import base64, sys
src, dst = sys.argv[1], sys.argv[2]
with open(src, "rb") as f:
    data = base64.b64decode(f.read())
with open(dst, "wb") as f:
    f.write(data)
PY
fi

SIZE=$(wc -c < "$OUT" | tr -d ' ')
if [ "$SIZE" != "$EXPECTED_SIZE" ]; then
    echo "ERROR: bad IPK size: $SIZE (expected $EXPECTED_SIZE)"
    rm -f "$OUT"
    exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
    SHA=$(sha256sum "$OUT" | awk '{print $1}')
    if [ "$SHA" != "$EXPECTED_SHA256" ]; then
        echo "ERROR: SHA256 mismatch: $SHA"
        rm -f "$OUT"
        exit 1
    fi
fi

rm -f "$B64"
echo "OK: $OUT"
echo "Version: 1.0.46-r68-beta"
echo "Size: $SIZE bytes"
echo "SHA256: $EXPECTED_SHA256"
