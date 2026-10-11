#!/bin/sh
# Download and SHA verify ONLY. Does not install or alter receiver configuration.
set -eu
RAW="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r723-neo-classic-fusion/payload/r723-neo-classic-premium.b64"
TARGET="/tmp/iptosatpro-r723-neo-classic-beta.ipk"
TMPB64="/tmp/r723.$$-download.b64"
TMPIPK="/tmp/r723.$$-download.ipk"
trap 'rm -f "$TMPB64" "$TMPIPK"' EXIT HUP INT TERM
wget -O "$TMPB64" "$RAW"
test -s "$TMPB64"
if command -v base64 >/dev/null 2>&1; then
    base64 -d "$TMPB64" > "$TMPIPK"
else
    python3 - "$TMPB64" "$TMPIPK" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: content=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(content)
PY
fi
test "$(wc -c < "$TMPIPK" | tr -d ' ')" = "402536"
if command -v sha256sum >/dev/null 2>&1; then
    echo "b76e9fb551cef1d0422d6303f3d74e38b94cadae6fda6b6f90d6eecf7739afa3  $TMPIPK" | sha256sum -c -
else
    python3 - "$TMPIPK" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f:
    assert hashlib.sha256(f.read()).hexdigest()=="b76e9fb551cef1d0422d6303f3d74e38b94cadae6fda6b6f90d6eecf7739afa3"
PY
fi
mv "$TMPIPK" "$TARGET"
echo "R72.3 NEO CLASSIC PREMIUM VERIFIED: $TARGET"
echo "NOT INSTALLED, existing receiver settings and mappings unchanged."
