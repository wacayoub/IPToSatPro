#!/bin/sh
# VERIFIED DOWNLOAD ONLY. No installation, GUI restart, mappings changes.
set -eu
RAW="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r71-1-neo-home/payload/r711-neo-home-beta.b64"
TARGET="/tmp/iptosatpro-r711-neo-home-beta.ipk"
TMPB64="/tmp/iptosat-r711.$$-download.b64"
TMPIPK="/tmp/iptosat-r711.$$-download.ipk"
trap 'rm -f "$TMPB64" "$TMPIPK"' EXIT HUP INT TERM
wget -qO "$TMPB64" "$RAW"
test -s "$TMPB64"
if command -v base64 >/dev/null 2>&1; then
  base64 -d "$TMPB64" > "$TMPIPK"
else
  python3 - "$TMPB64" "$TMPIPK" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: raw=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(raw)
PY
fi
test "$(wc -c < "$TMPIPK" | tr -d ' ')" = "279792"
if command -v sha256sum >/dev/null 2>&1; then
  echo "e6108f374ac7aa5a5ac8f06bb0c707e94c1932754f75ee62b25091609bef68ff  $TMPIPK" | sha256sum -c - >/dev/null
else
  python3 - "$TMPIPK" <<'PY'
import sys,hashlib
with open(sys.argv[1],"rb") as f:
    assert hashlib.sha256(f.read()).hexdigest()=="e6108f374ac7aa5a5ac8f06bb0c707e94c1932754f75ee62b25091609bef68ff"
PY
fi
mv -f "$TMPIPK" "$TARGET"
echo "R71.1 NEO HOME BETA VERIFIED: $TARGET"
echo "NOT INSTALLED: receiver plugin, settings, mappings and player unchanged."
