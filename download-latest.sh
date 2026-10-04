#!/bin/sh
set -eu

URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/main/payload/r61.b64"
OUT="/tmp/iptosatpro.ipk"
B64="/tmp/iptosatpro-r61.b64"
EXPECTED_SIZE="260550"
EXPECTED_SHA256="430b3ab1b0bfbb4410253b0c1b0e65d3a968903b10d8a86853d05451f7ac266f"

rm -f "$OUT" "$B64"
echo "Downloading IPToSat Pro r61..."
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
echo "Version: 1.0.46-r61"
echo "Size: $SIZE bytes"
echo "SHA256: $EXPECTED_SHA256"
