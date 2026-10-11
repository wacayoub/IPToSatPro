#!/bin/sh
# R72.1 premium icons: verified download only. NEVER installs/restarts/modifies mappings.
set -eu
RAW="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r72-1-premium-icons/payload/r721-premium-icons.b64"
TARGET="/tmp/iptosatpro-r721-premium-icons-beta.ipk"
B64="/tmp/iptosat-r721.$$-temp.b64"
IPK="/tmp/iptosat-r721.$$-temp.ipk"
trap 'rm -f "$B64" "$IPK"' EXIT HUP INT TERM
wget -O "$B64" "$RAW"
test -s "$B64"
if command -v base64 >/dev/null 2>&1; then
    base64 -d "$B64" > "$IPK"
else
    python3 - "$B64" "$IPK" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: raw=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(raw)
PY
fi
test "$(wc -c < "$IPK" | tr -d ' ')" = "358772"
if command -v sha256sum >/dev/null 2>&1; then
    echo "5da1148476b471a000f9b2064f0b2e01d4db131f946783b24a70c098ebd97092  $IPK" | sha256sum -c -
else
    python3 - "$IPK" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f: assert hashlib.sha256(f.read()).hexdigest()=="5da1148476b471a000f9b2064f0b2e01d4db131f946783b24a70c098ebd97092"
PY
fi
mv "$IPK" "$TARGET"
echo "VERIFIED R72.1 PREMIUM ICONS BETA: $TARGET"
echo "NOT INSTALLED. Existing receiver settings and stream mappings unchanged."
