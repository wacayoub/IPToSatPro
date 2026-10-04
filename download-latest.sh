#!/bin/sh
set -eu

BASE="https://raw.githubusercontent.com/wacayoub/IPToSatPro/main/payload"
OUT="/tmp/iptosatpro.ipk"
B64="/tmp/iptosatpro-r51.b64"
EXPECTED_SIZE="257954"
EXPECTED_SHA256="ec9c1e5b71f5dbd7377d0220802890a693fa2c532cce14072a9a1e71145a513e"

rm -f "$OUT" "$B64" /tmp/r51.part*.b64

i=1
while [ "$i" -le 10 ]; do
    p=$(printf "%02d" "$i")
    url="$BASE/r51.part$p.b64"
    file="/tmp/r51.part$p.b64"
    echo "Downloading IPToSat Pro r51 part $p/10..."
    wget -q -O "$file" "$url"
    test -s "$file"
    cat "$file" >> "$B64"
    printf '\n' >> "$B64"
    i=$((i + 1))
done

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

rm -f "$B64" /tmp/r51.part*.b64
echo "OK: $OUT"
echo "Version: 1.0.46-r51"
echo "Size: $SIZE bytes"
echo "SHA256: $EXPECTED_SHA256"
