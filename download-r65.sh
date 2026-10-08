#!/bin/sh
set -eu

URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/main/payload/r65.b64"
OUT="/tmp/iptosatpro.ipk"
B64="/tmp/iptosatpro-r65.b64"
EXPECTED_SIZE="270986"
EXPECTED_SHA256="ad226ae2b511264a64d8778937daa900e88d28536fbe6ddb6841ede42d48045e"

rm -f "$OUT" "$B64"
echo "Downloading IPToSat Pro r65..."
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
echo "Version: 1.0.46-r65"
echo "Size: $SIZE bytes"
echo "SHA256: $EXPECTED_SHA256"
