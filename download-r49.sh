#!/bin/sh
set -eu

BASE="https://raw.githubusercontent.com/wacayoub/IPToSatPro/main/payload"
OUT="/tmp/iptosatpro.ipk"
B64="/tmp/iptosatpro-r49.b64"
EXPECTED_SIZE="255380"
EXPECTED_SHA256="985f81777a83cd4d98355b6f80b05fde1365a1c53840c81006b1416b4843f23c"

rm -f "$OUT" "$B64" /tmp/r49.part*.b64

i=1
while [ "$i" -le 9 ]; do
    p=$(printf "%02d" "$i")
    url="$BASE/r49.part$p.b64"
    file="/tmp/r49.part$p.b64"
    echo "Downloading r49 part $p/09..."
    wget -q -O "$file" "$url"
    cat "$file" >> "$B64"
    i=$((i + 1))
done

base64 -d "$B64" > "$OUT"

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

rm -f "$B64" /tmp/r49.part*.b64
echo "OK: $OUT"
echo "Size: $SIZE bytes"
echo "Install with:"
echo "opkg install --force-reinstall $OUT"
