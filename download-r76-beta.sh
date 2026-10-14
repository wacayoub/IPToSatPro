#!/bin/sh
# IPToSatPro R76 BETA / Vu+ OpenATV: verified, explicit receiver deployment.
# Defaults to --check (download + SHA256 ONLY, no receiver modifications).
# --install backs up persistent receiver plugin/configuration before opkg.
# --rollback restores previous plugin CODE (mapping files remain untouched).
set -eu
umask 077
VERSION="1.0.46-r76.9-preview-manual-parity-beta"
BASE="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r769-preview-manual-parity"
PLUGIN="/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge"
CONFIG="/etc/enigma2/SatIPTVBridge"
BACKUPROOT="/home/root/iptosatpro-r76-backups"
PACKAGE="/tmp/iptosatpro-r76-metrix-preview-b-beta.ipk"
if [ "$#" -eq 0 ]; then MODE="--check"; else MODE="$1"; fi
case "$MODE" in --check|--install|--rollback) ;; *)
  echo "Usage: sh download-r76-beta.sh [--check|--install|--rollback]"
  exit 2 ;;
esac
if [ "$(id -u)" != "0" ]; then
  echo "ROOT_REQUIRED: please use the Vu+ root shell"; exit 2
fi
if [ "$MODE" = "--rollback" ]; then
  if [ ! -f "$BACKUPROOT/last-backup-path" ]; then
    echo "NO_BACKUP: refusing rollback"; exit 3
  fi
  SAVED="$(cat "$BACKUPROOT/last-backup-path")"
  case "$SAVED" in
    "$BACKUPROOT"/*) ;;
    *) echo "BACKUP_PATH_UNTRUSTED"; exit 3 ;;
  esac
  if [ ! -s "$SAVED/plugin-code.tar.gz" ]; then
    echo "BACKUP_MISSING: refusing rollback"; exit 3
  fi
  tar tzf "$SAVED/plugin-code.tar.gz" >/dev/null || {
    echo "BACKUP_CORRUPT"; exit 3
  }
  tar xzf "$SAVED/plugin-code.tar.gz" -C /
  echo "PREVIOUS_PLUGIN_CODE_RESTORED: $SAVED"
  echo "CONFIG_AND_MAPPINGS_PRESERVED: no settings restored by default"
  echo "NOTE: opkg package-version metadata may still report R76."
  echo "Restart Enigma2 GUI using the OpenATV menu."
  exit 0
fi
if [ ! -d "$PLUGIN" ]; then
  echo "PLUGIN_NOT_INSTALLED: refusing beta installation"; exit 3
fi
if ! command -v opkg >/dev/null 2>&1; then
  echo "OPKG_NOT_FOUND: this is not the expected OpenATV receiver"; exit 3
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "PYTHON3_NOT_FOUND"; exit 3
fi
WORK="/tmp/iptosat-r76-$$"
mkdir -p "$WORK"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
wget -qO "$WORK/manifest.json" "$BASE/staging/r76-metrix-preview.update.json" || {
  echo "DOWNLOAD_FAILED: manifest"; exit 4
}
wget -qO "$WORK/payload.b64" "$BASE/payload/r76-metrix-preview.b64" || {
  echo "DOWNLOAD_FAILED: payload"; exit 4
}
python3 - "$WORK/manifest.json" "$WORK/payload.b64" "$WORK/result.ipk" <<'PY'
import base64,hashlib,json,sys
with open(sys.argv[1],encoding="utf-8") as f:m=json.load(f)
with open(sys.argv[2],"rb") as f:encoded=f.read()
ver="1.0.46-r76.9-preview-manual-parity-beta"
url=("https://raw.githubusercontent.com/wacayoub/IPToSatPro/"
     "feature/r769-preview-manual-parity/payload/r76-metrix-preview.b64")
if m.get("version")!=ver or m.get("beta") is not True:
    raise SystemExit("Wrong R76 beta manifest or version")
if m.get("parts")!=[url]:
    raise SystemExit("Unrecognized manifest payload")
if m.get("production_published") is not False:
    raise SystemExit("Expected non-production package")
raw=base64.b64decode(encoded,validate=False)
sha=hashlib.sha256(raw).hexdigest()
if sha!=m.get("sha256") or len(raw)!=m.get("size"):
    raise SystemExit("SHA256 / size mismatch; receiver unchanged")
with open(sys.argv[3],"wb") as f:f.write(raw)
print("R76 VERIFIED",ver,"bytes",len(raw),"SHA256",sha)
PY
mv "$WORK/result.ipk" "$PACKAGE"
if [ "$MODE" = "--check" ]; then
  echo "DOWNLOAD_ONLY: verified at $PACKAGE"
  echo "NO_SETTINGS_OR_MAPPINGS_CHANGED"
  echo "Install explicitly with: sh /tmp/download-r76-beta.sh --install"
  exit 0
fi
# Avoid overwriting the only known-good R75 backup with broken R76.0 code.
# The user must first restore the verified R75 snapshot using --rollback.
if grep -q 'PLUGIN_VERSION = "1.0.46-r76.0-metrix-preview-b-beta"' "$PLUGIN/plugin.py"; then
  echo "OLD_R76_CRASH_VERSION: run sh /tmp/download-r76-beta.sh --rollback before --install"
  echo "Your saved R75 backup remains available. No installation attempted."
  exit 6
fi
# Create persistent code and mapping snapshot before package replacement.
mkdir -p "$BACKUPROOT"
chmod 700 "$BACKUPROOT"
STAMP="$(date +%Y%m%dT%H%M%S)"
SAVED="$BACKUPROOT/$STAMP"
if [ -e "$SAVED" ]; then
  echo "BACKUP_COLLISION: aborting";exit 4
fi
mkdir -m 700 "$SAVED"
if ! tar czf "$SAVED/plugin-code.tar.gz" "$PLUGIN" 2>/dev/null; then
  echo "PLUGIN_BACKUP_FAILED: no install"; exit 4
fi
chmod 600 "$SAVED/plugin-code.tar.gz"
set --
if [ -f /etc/enigma2/settings ]; then set -- "$@" /etc/enigma2/settings; fi
for FILE in overrides.json manual_aliases.json resolved_mappings.json rejected_sources.json player_overrides.json import_spec.json refresh_state.json r723_home_layout r76_home_layout; do
  if [ -f "$CONFIG/$FILE" ]; then set -- "$@" "$CONFIG/$FILE"; fi
done
if [ "$#" -gt 0 ]; then
  if ! tar czf "$SAVED/settings-and-maps.tar.gz" "$@" 2>/dev/null; then
    echo "MAPPING_BACKUP_FAILED: no install"; exit 4
  fi
  chmod 600 "$SAVED/settings-and-maps.tar.gz"
fi
python3 - "$SAVED" "$CONFIG" <<'PY'
import hashlib,json,os,sys
saved,config=sys.argv[1:]
names=("overrides.json","manual_aliases.json","resolved_mappings.json",
       "rejected_sources.json","player_overrides.json")
checks={}
for name in names:
    path=os.path.join(config,name)
    if os.path.isfile(path):
        with open(path,"rb") as f:checks[name]=hashlib.sha256(f.read()).hexdigest()
with open(os.path.join(saved,"mapping-hashes.json"),"w") as f:json.dump(checks,f,indent=2)
os.chmod(os.path.join(saved,"mapping-hashes.json"),0o600)
print("BACKUP_MAPPINGS",len(checks))
PY
printf '%s\n' "$SAVED" > "$BACKUPROOT/last-backup-path"
chmod 600 "$BACKUPROOT/last-backup-path"
echo "PERSISTENT_BACKUP $SAVED"
if ! opkg install --force-reinstall "$PACKAGE"; then
  echo "INSTALL_FAILED: attempting immediate previous plugin-code restoration"
  tar xzf "$SAVED/plugin-code.tar.gz" -C / || true
  echo "Check the Enigma2 GUI before use; mappings not modified."
  exit 5
fi
echo "R76_BETA_INSTALL_OK: $VERSION"
echo "Restart ONLY Enigma2 GUI using the OpenATV menu."
echo "Rollback code only: sh /tmp/download-r76-beta.sh --rollback"
