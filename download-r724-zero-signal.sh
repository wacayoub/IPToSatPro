#!/bin/sh
# SHA-verified R72.4 beta download only. Does NOT install/change settings/mappings.
set -eu
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r724-zero-signal-fallback/payload/r724-zero-signal.b64"
TARGET="/tmp/iptosatpro-r724-zero-signal-beta.ipk"
ENC="/tmp/iptosat-r724.$$-download.b64"
IPK="/tmp/iptosat-r724.$$-download.ipk"
trap 'rm -f "$ENC" "$IPK"' EXIT HUP INT TERM
wget -O "$ENC" "$URL"
test -s "$ENC"
if command -v base64 >/dev/null 2>&1; then
    base64 -d "$ENC" > "$IPK"
else
    python3 - "$ENC" "$IPK" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: data=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(data)
PY
fi
test "$(wc -c < "$IPK" | tr -d ' ')" = "403344"
if command -v sha256sum >/dev/null 2>&1; then
    echo "fe779fc4a2c95bea7166c4ce168e18b76416959d9e51b247fdbc809d1b737194  $IPK" | sha256sum -c -
else
    python3 - "$IPK" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f:
    assert hashlib.sha256(f.read()).hexdigest()=="fe779fc4a2c95bea7166c4ce168e18b76416959d9e51b247fdbc809d1b737194", "SHA mismatch"
PY
fi
mv "$IPK" "$TARGET"
echo "R72.4 NO SIGNAL BETA VERIFIED: $TARGET"
echo "NOT INSTALLED. SAT and IPTV mappings unchanged."
