#!/bin/sh
# R72.6 verified download only; no installation or receiver changes.
set -eu
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r726-digi24-safe-match/payload/r726-digi24-safe.b64"
TARGET="/tmp/iptosatpro-r726-digi24-safe-beta.ipk"
TXT="/tmp/r726.$$-download.b64"
IPK="/tmp/r726.$$-download.ipk"
trap 'rm -f "$TXT" "$IPK"' EXIT HUP INT TERM
wget -O "$TXT" "$URL"
test -s "$TXT"
if command -v base64 >/dev/null 2>&1; then
    base64 -d "$TXT" > "$IPK"
else
    python3 - "$TXT" "$IPK" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: data=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(data)
PY
fi
test "$(wc -c < "$IPK" | tr -d ' ')" = "405038"
if command -v sha256sum >/dev/null 2>&1; then
    echo "9b7efbef03368c9a97b86c265574dbd9389401b7d5b014a50e427eaaf267859b  $IPK" | sha256sum -c -
else
    python3 - "$IPK" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f:
    assert hashlib.sha256(f.read()).hexdigest()=="9b7efbef03368c9a97b86c265574dbd9389401b7d5b014a50e427eaaf267859b"
PY
fi
mv "$IPK" "$TARGET"
echo "R72.6 DIGI 24 SAFE BETA VERIFIED: $TARGET"
echo "NOT INSTALLED; receiver settings and mappings unchanged."
