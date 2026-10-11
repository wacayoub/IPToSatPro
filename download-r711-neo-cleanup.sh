#!/bin/sh
# Download and SHA verify R71.1 UI cleanup BETA. Does NOT install anything.
set -eu
RAW="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r711-neo-cleanup/payload/r711-neo-cleanup.b64"
TARGET="/tmp/iptosatpro-r711-neo-cleanup-beta.ipk"
TMPB64="/tmp/iptosat-r711-cleanup.$$-download.b64"
TMPIPK="/tmp/iptosat-r711-cleanup.$$-download.ipk"
trap 'rm -f "$TMPB64" "$TMPIPK"' EXIT HUP INT TERM
wget -qO "$TMPB64" "$RAW"
test -s "$TMPB64"
if command -v base64 >/dev/null 2>&1; then
    base64 -d "$TMPB64" > "$TMPIPK"
else
    python3 - "$TMPB64" "$TMPIPK" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: d=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(d)
PY
fi
test "$(wc -c < "$TMPIPK" | tr -d ' ')" = "308552"
if command -v sha256sum >/dev/null 2>&1; then
    echo "ae70b0e84827a5bb0edc8b79abf5ebaf1e98e4ccb64fe10c1f8b5b05cb66cedd  $TMPIPK" | sha256sum -c - >/dev/null
else
    python3 - "$TMPIPK" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f:
    assert hashlib.sha256(f.read()).hexdigest()=="ae70b0e84827a5bb0edc8b79abf5ebaf1e98e4ccb64fe10c1f8b5b05cb66cedd", "SHA256 mismatch"
PY
fi
mv -f "$TMPIPK" "$TARGET"
echo "R71.1 NEO CLEANUP BETA VERIFIED: $TARGET"
echo "NOT INSTALLED: receiver plugin, settings, mappings, player unchanged."
