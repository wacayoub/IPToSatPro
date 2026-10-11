#!/bin/sh
# Verified download ONLY. No opkg, restart, playback, mappings or user settings changes.
set -eu
RAW="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r72-sat-iptv-live-monitor/payload/r72-live-monitor.b64"
TARGET="/tmp/iptosatpro-r72-live-monitor-beta.ipk"
B64="/tmp/iptosat-r72.$$-download.b64"
PKG="/tmp/iptosat-r72.$$-download.ipk"
trap 'rm -f "$B64" "$PKG"' EXIT HUP INT TERM
wget -qO "$B64" "$RAW"
test -s "$B64"
if command -v base64 >/dev/null 2>&1; then
    base64 -d "$B64" > "$PKG"
else
    python3 - "$B64" "$PKG" <<'PY'
import base64,sys
with open(sys.argv[1],"rb") as f: payload=base64.b64decode(f.read())
with open(sys.argv[2],"wb") as f: f.write(payload)
PY
fi
test "$(wc -c < "$PKG" | tr -d ' ')" = "314512"
if command -v sha256sum >/dev/null 2>&1; then
    echo "6bb68ed906637c19e8e22a33a66165db53044a759258d19e39ec1898dee2c8d0  $PKG" | sha256sum -c - >/dev/null
else
    python3 - "$PKG" <<'PY'
import hashlib,sys
with open(sys.argv[1],"rb") as f:
    assert hashlib.sha256(f.read()).hexdigest()=="6bb68ed906637c19e8e22a33a66165db53044a759258d19e39ec1898dee2c8d0", "SHA-256 verification failed"
PY
fi
mv -f "$PKG" "$TARGET"
echo "R72 BETA VERIFIED DOWNLOAD: $TARGET"
echo "NOT INSTALLED. Running receiver version and mappings unchanged."
