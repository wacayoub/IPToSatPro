#!/bin/sh
# R75 Smart Index beta: safe checksum-verified online install.
# Download-only by default. Installation ONLY on explicit --install.
# Does not auto-reboot GUI or write mapping files.
set -eu
umask 077
BASE='https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r75-smart-index-optimized'
WORK="/tmp/iptosat-r75-$$"
OUT="/tmp/iptosatpro-r75-smart-index.ipk"
mkdir -p "$WORK"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
wget -qO "$WORK/manifest.json" "$BASE/staging/r75-smart-index.update.json"
wget -qO "$WORK/payload.b64" "$BASE/payload/r75-smart-index.b64"
test -s "$WORK/manifest.json"
test -s "$WORK/payload.b64"
if command -v base64 >/dev/null 2>&1; then
  base64 -d "$WORK/payload.b64" > "$WORK/result.ipk"
else
  python3 - "$WORK/payload.b64" "$WORK/result.ipk" <<'PY'
import base64,sys
with open(sys.argv[1],'rb') as f: raw=base64.b64decode(f.read(),validate=False)
with open(sys.argv[2],'wb') as f: f.write(raw)
PY
fi
python3 - "$WORK/manifest.json" "$WORK/result.ipk" <<'PY'
import hashlib,json,sys
with open(sys.argv[1],'r',encoding='utf-8') as f: m=json.load(f)
with open(sys.argv[2],'rb') as f: raw=f.read()
version="1.0.46-r75.0-smart-index-beta"
if m.get("version")!=version or m.get("beta") is not True:
    raise SystemExit("Manifest is not the requested R75 beta")
if len(raw)!=int(m.get("size") or -1):
    raise SystemExit("R75 IPK size mismatch")
if hashlib.sha256(raw).hexdigest()!=m.get("sha256"):
    raise SystemExit("R75 IPK SHA256 mismatch")
parts=m.get("parts") or []
if len(parts)!=1 or "/payload/r75-smart-index.b64" not in str(parts[0]):
    raise SystemExit("Unexpected R75 payload path")
print("R75 VERIFIED",version,"bytes="+str(len(raw)),
      "SHA256="+m["sha256"])
PY
mv "$WORK/result.ipk" "$OUT"
echo "VERIFIED_PACKAGE $OUT"
if [ "${1:-}" = "--install" ]; then
  # Backup persistent receiver state BEFORE touching opkg. No credential leaks.
  BACKUP="/tmp/iptosatpro-pre-r75-$(date +%Y%m%d-%H%M%S).tar.gz"
  # Save previous receiver plugin CODE and critical persistent mappings.
  # Large IPTV catalog.jsonl/snapshot files are intentionally NOT duplicated.
  set -- /usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge
  if [ -f /etc/enigma2/settings ]; then
    set -- "$@" /etc/enigma2/settings
  fi
  for FILE in overrides.json manual_aliases.json resolved_mappings.json rejected_sources.json player_overrides.json import_spec.json refresh_state.json; do
    if [ -f "/etc/enigma2/SatIPTVBridge/$FILE" ]; then
      set -- "$@" "/etc/enigma2/SatIPTVBridge/$FILE"
    fi
  done
  tar czf "$BACKUP" "$@" 2>/dev/null || {
    echo 'BACKUP_FAILED: no installation performed'
    exit 2
  }
  echo "RECEIVER_STATE_BACKUP $BACKUP"
  opkg install --force-reinstall "$OUT"
  echo "R75 INSTALL_OK. Restart ONLY Enigma2 GUI using OpenATV menu."
else
  echo "DOWNLOAD_ONLY: no receiver changes."
  echo "Install explicitly with: sh /tmp/download-r75.sh --install"
fi
