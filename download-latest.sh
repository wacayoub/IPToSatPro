#!/bin/sh
# Download only. Does not install or restart Enigma2.
set -eu
RAW="https://raw.githubusercontent.com/wacayoub/IPToSatPro/main/payload/r80-final.b64"
TARGET="/tmp/iptosatpro.ipk"
TMPB64="/tmp/iptosatpro-r80-final.$$-download.b64"
TMPIPK="/tmp/iptosatpro-r80-final.$$-download.ipk"
trap 'rm -f "$TMPB64" "$TMPIPK"' EXIT HUP INT TERM
wget -q -O "$TMPB64" "$RAW"
test -s "$TMPB64"
if command -v base64 >/dev/null 2>&1; then
  base64 -d "$TMPB64" > "$TMPIPK"
else
  python3 - "$TMPB64" "$TMPIPK" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f:
    raw=base64.b64decode(f.read(), validate=False)
with open(sys.argv[2],"wb") as f:
    f.write(raw)
PY
fi
test "$(wc -c < "$TMPIPK" | tr -d ' ')" = "461198"
if command -v sha256sum >/dev/null 2>&1; then
  echo "5c7e48ba51e5ed1689c5930df72309c7c495cc702f5cff6b91142ddc2985606a  $TMPIPK" | sha256sum -c - >/dev/null
else
  python3 - "$TMPIPK" <<'PY'
import sys,hashlib
with open(sys.argv[1],"rb") as f:
    assert hashlib.sha256(f.read()).hexdigest()=="5c7e48ba51e5ed1689c5930df72309c7c495cc702f5cff6b91142ddc2985606a", "SHA256 mismatch"
PY
fi
mv -f "$TMPIPK" "$TARGET"
echo "Verified official online package: $TARGET"
echo "No installation performed. Existing plugin remains unchanged."
