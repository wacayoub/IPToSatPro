#!/bin/sh
   # IPToSatPro R80.1 EXPERIMENTAL PREVIEW BETA / Vu+ OpenATV: verified, explicit receiver deployment.
# Defaults to --check (download + SHA256 ONLY, no receiver modifications).
# --install backs up persistent receiver plugin/configuration before opkg.
# --rollback restores previous plugin CODE (mapping files remain untouched).
set -eu
umask 077
VERSION="1.0.46-r80.1-preview-hotpath-beta"
BASE="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r80-preview-hotpath-20261015"
PLUGIN="/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge"
CONFIG="/etc/enigma2/SatIPTVBridge"
BACKUPROOT="/home/root/iptosatpro-r76-backups"
PACKAGE="/tmp/iptosatpro-r801-preview-hotpath-beta.ipk"
if [ "$#" -eq 0 ]; then MODE="--check"; else MODE="$1"; fi
case "$MODE" in --check|--install|--rollback) ;; *)
  echo "Usage: sh download-r801-preview-hotpath.sh [--check|--install|--rollback]"
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
  if [ ! -d "$SAVED" ] || [ -L "$SAVED" ] || [ ! -s "$SAVED/plugin-code.tar.gz" ]; then
    echo "BACKUP_MISSING: refusing rollback"; exit 3
  fi
  tar tzf "$SAVED/plugin-code.tar.gz" >/dev/null || {
    echo "BACKUP_CORRUPT"; exit 3
  }
  tar xzf "$SAVED/plugin-code.tar.gz" -C /
  echo "PREVIOUS_PLUGIN_CODE_RESTORED: $SAVED"
  echo "CONFIG_AND_MAPPINGS_PRESERVED: no settings restored by default"
  echo "NOTE: opkg metadata may still report R80 after restoring previous plugin code."
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
wget -qO "$WORK/manifest.json" "$BASE/staging/r801-preview-hotpath.update.json" || {
  echo "DOWNLOAD_FAILED: manifest"; exit 4
}
wget -qO "$WORK/payload.b64" "$BASE/payload/r801-preview-hotpath.b64" || {
  echo "DOWNLOAD_FAILED: payload"; exit 4
}
python3 - "$WORK/manifest.json" "$WORK/payload.b64" "$WORK/result.ipk" <<'PY'
import base64,hashlib,json,sys
with open(sys.argv[1],encoding="utf-8") as f:m=json.load(f)
with open(sys.argv[2],"rb") as f:encoded=f.read()
ver="1.0.46-r80.1-preview-hotpath-beta"
url=("https://raw.githubusercontent.com/wacayoub/IPToSatPro/"
     "feature/r80-preview-hotpath-20261015/payload/r801-preview-hotpath.b64")
if m.get("version")!=ver or m.get("beta") is not True:
    raise SystemExit("Wrong R80.1 Preview hot-path beta manifest or version")
if m.get("parts")!=[url]:
    raise SystemExit("Unrecognized manifest payload")
if m.get("production_published") is not False:
    raise SystemExit("Expected non-production R80.1 beta package")
raw=base64.b64decode(encoded,validate=False)
sha=hashlib.sha256(raw).hexdigest()
expected_sha="210fe7de203353b71f02829f4f2b31acc582dfc663ce7bc8971425e0ecd2f173"
expected_size=461044
if (sha!=expected_sha or m.get("sha256")!=expected_sha or
        len(raw)!=expected_size or m.get("size")!=expected_size):
    raise SystemExit("PINNED_SHA256_SIZE_MISMATCH: receiver unchanged")
if (m.get("receiver_tested") is not False or
        m.get("installation_requires_explicit_flag") is not True):
    raise SystemExit("INVALID_BETA_SAFETY_FLAGS: receiver unchanged")
with open(sys.argv[3],"wb") as f:f.write(raw)
print("R801 VERIFIED",ver,"bytes",len(raw),"SHA256",sha)
PY
mv "$WORK/result.ipk" "$PACKAGE"
if [ "$MODE" = "--check" ]; then
  echo "DOWNLOAD_ONLY: verified at $PACKAGE"
  echo "NO_SETTINGS_OR_MAPPINGS_CHANGED"
  echo "Install explicitly with: sh /tmp/download-r801-preview-hotpath.sh --install"
  exit 0
fi
# Idempotent reinstall guard: code and version markers must all agree.
# This is deliberately after SHA verification, before any persistent backup
# or opkg operation. Never replace or rewrite user mappings on a second run.
# R801_ALREADY_INSTALLED_GUARD
if grep -Fq 'PLUGIN_VERSION = "1.0.46-r80.1-preview-hotpath-beta"' "$PLUGIN/plugin.py"; then
  if [ -f "$PLUGIN/core.py" ] && [ -f "$PLUGIN/updater.py" ] &&
     grep -Fq 'R7615_NOMINATION_INDEX_ONLY' "$PLUGIN/core.py" &&
     grep -Fq 'R80_PREVIEW_PURE_HOTPATH_V1' "$PLUGIN/core.py" &&
     grep -Fq 'R7614_PREVIEW_PARSE_CACHE_IMMUTABLE' "$PLUGIN/core.py" &&
     grep -Fq 'R7612_NORMAL_PREVIEW_PHASE_TIMINGS' "$PLUGIN/core.py" &&
     grep -Fq 'CURRENT_VERSION = "1.0.46-r80.1-preview-hotpath-beta"' "$PLUGIN/updater.py"; then
    echo "ALREADY_INSTALLED: $VERSION"
    echo "NO_OPKG_ACTION: installation is already complete."
    echo "NO_BACKUP_OR_MAPPINGS_CHANGED"
    exit 0
  fi
  echo "INSTALLED_R80_INCONSISTENT: refusing to overwrite; inspect installed files."
  echo "Receiver unchanged."
  exit 7
fi
# Avoid overwriting the only known-good R75 backup with broken R76.0 code.
# The user must first restore the verified R75 snapshot using --rollback.
if grep -q 'PLUGIN_VERSION = "1.0.46-r76.0-metrix-preview-b-beta"' "$PLUGIN/plugin.py"; then
  echo "OLD_R76_CRASH_VERSION: restore saved code before R80"
  echo "Existing backups remain available. No installation attempted."
  exit 6
fi
# R80.1 is derived from R80 RC1, whose matcher core is byte-identical
# to R76.15. Accept only either *coherent* starting version; never force an
# install over a partially migrated or unknown receiver installation.
# R801_COHERENT_BASE_GATE
BASE_FOUND=""
if [ -f "$PLUGIN/updater.py" ] && [ -f "$PLUGIN/core.py" ]; then
  if grep -Fq 'PLUGIN_VERSION = "1.0.46-r76.15-preview-index-fast-beta"' "$PLUGIN/plugin.py" &&
     grep -Fq 'CURRENT_VERSION = "1.0.46-r76.15-preview-index-fast-beta"' "$PLUGIN/updater.py"; then
    BASE_FOUND="R76.15"
  elif grep -Fq 'PLUGIN_VERSION = "1.0.46-r80-final-rc1"' "$PLUGIN/plugin.py" &&
       grep -Fq 'CURRENT_VERSION = "1.0.46-r80-final-rc1"' "$PLUGIN/updater.py"; then
    BASE_FOUND="R80 RC1"
  fi
fi
if [ -z "$BASE_FOUND" ]; then
  echo "BASE_VERSION_MISMATCH: coherent R76.15 or R80 RC1 required for R80.1 beta"
  echo "Receiver unchanged."
  exit 6
fi
for MARKER in R7615_NOMINATION_INDEX_ONLY R7614_PREVIEW_PARSE_CACHE_IMMUTABLE R7612_NORMAL_PREVIEW_PHASE_TIMINGS; do
  if ! grep -Fq "$MARKER" "$PLUGIN/core.py"; then
    echo "BASE_MARKER_MISSING: $MARKER ($BASE_FOUND)"
    echo "Receiver unchanged."
    exit 6
  fi
done
echo "BASE_COMPATIBLE: $BASE_FOUND"
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
echo "R801_BETA_INSTALL_OK: $VERSION"
echo "Restart ONLY Enigma2 GUI using the OpenATV menu."
echo "Rollback code only: sh /tmp/download-r801-preview-hotpath.sh --rollback"
