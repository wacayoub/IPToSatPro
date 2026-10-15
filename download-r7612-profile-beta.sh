#!/bin/sh
 # IPToSatPro R76.12 PROFILER BETA / Vu+ OpenATV: verified, explicit receiver deployment.
# Defaults to --check (download + SHA256 ONLY, no receiver modifications).
# --install backs up persistent receiver plugin/configuration before opkg.
# --rollback restores previous plugin CODE (mapping files remain untouched).
set -eu
umask 077
VERSION="1.0.46-r76.12-preview-phase-profile-beta"
BASE="https://raw.githubusercontent.com/wacayoub/IPToSatPro/release/r769-finalization-20261014"
PLUGIN="/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge"
CONFIG="/etc/enigma2/SatIPTVBridge"
BACKUPROOT="/home/root/iptosatpro-r76-backups"
PACKAGE="/tmp/iptosatpro-r7612-phase-profile-beta.ipk"
if [ "$#" -eq 0 ]; then MODE="--check"; else MODE="$1"; fi
case "$MODE" in --check|--install|--rollback) ;; *)
  echo "Usage: sh download-r7612-profile-beta.sh [--check|--install|--rollback]"
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
wget -qO "$WORK/manifest.json" "$BASE/staging/r7612-phase-profile.update.json" || {
  echo "DOWNLOAD_FAILED: manifest"; exit 4
}
wget -qO "$WORK/payload.b64" "$BASE/payload/r7612-phase-profile.b64" || {
  echo "DOWNLOAD_FAILED: payload"; exit 4
}
python3 - "$WORK/manifest.json" "$WORK/payload.b64" "$WORK/result.ipk" <<'PY'
import base64,hashlib,json,sys
with open(sys.argv[1],encoding="utf-8") as f:m=json.load(f)
with open(sys.argv[2],"rb") as f:encoded=f.read()
ver="1.0.46-r76.12-preview-phase-profile-beta"
url=("https://raw.githubusercontent.com/wacayoub/IPToSatPro/"
     "release/r769-finalization-20261014/payload/r7612-phase-profile.b64")
if m.get("version")!=ver or m.get("beta") is not True:
    raise SystemExit("Wrong R7612 beta manifest or version")
if m.get("parts")!=[url]:
    raise SystemExit("Unrecognized manifest payload")
if m.get("production_published") is not False:
    raise SystemExit("Expected non-production R7612 package")
raw=base64.b64decode(encoded,validate=False)
sha=hashlib.sha256(raw).hexdigest()
expected_sha="773bbbba6c32be3b1f61a21c773593f6ff5d04382beeffc341e38961d5b3a911"
expected_size=458848
if (sha!=expected_sha or m.get("sha256")!=expected_sha or
        len(raw)!=expected_size or m.get("size")!=expected_size):
    raise SystemExit("PINNED_SHA256_SIZE_MISMATCH: receiver unchanged")
if (m.get("receiver_tested") is not False or
        m.get("installation_requires_explicit_flag") is not True):
    raise SystemExit("INVALID_BETA_SAFETY_FLAGS: receiver unchanged")
with open(sys.argv[3],"wb") as f:f.write(raw)
print("R7612 VERIFIED",ver,"bytes",len(raw),"SHA256",sha)
PY
mv "$WORK/result.ipk" "$PACKAGE"
if [ "$MODE" = "--check" ]; then
  echo "DOWNLOAD_ONLY: verified at $PACKAGE"
  echo "NO_SETTINGS_OR_MAPPINGS_CHANGED"
  echo "Install explicitly with: sh /tmp/download-r7612-profile-beta.sh --install"
  exit 0
fi
# Idempotent reinstall guard: code and version markers must all agree.
# This is deliberately after SHA verification, before any persistent backup
# or opkg operation. Never replace or rewrite user mappings on a second run.
# R7612_ALREADY_INSTALLED_GUARD
if grep -Fq 'PLUGIN_VERSION = "1.0.46-r76.12-preview-phase-profile-beta"' "$PLUGIN/plugin.py"; then
  if [ -f "$PLUGIN/core.py" ] && [ -f "$PLUGIN/updater.py" ] &&
     grep -Fq 'R7612_NORMAL_PREVIEW_PHASE_TIMINGS' "$PLUGIN/core.py" &&
     grep -Fq 'R7611_NORMAL_PREVIEW_NO_COLD_DECORATED_SCAN' "$PLUGIN/core.py" &&
     grep -Fq 'R7612_PREVIEW_STAGE_NUMERIC_ONLY' "$PLUGIN/plugin.py" &&
     grep -Fq 'CURRENT_VERSION = "1.0.46-r76.12-preview-phase-profile-beta"' "$PLUGIN/updater.py"; then
    echo "ALREADY_INSTALLED: $VERSION"
    echo "NO_OPKG_ACTION: installation is already complete."
    echo "NO_BACKUP_OR_MAPPINGS_CHANGED"
    exit 0
  fi
  echo "INSTALLED_R7612_INCONSISTENT: refusing to overwrite; inspect installed files."
  echo "Receiver unchanged."
  exit 7
fi
# Avoid overwriting the only known-good R75 backup with broken R76.0 code.
# The user must first restore the verified R75 snapshot using --rollback.
if grep -q 'PLUGIN_VERSION = "1.0.46-r76.0-metrix-preview-b-beta"' "$PLUGIN/plugin.py"; then
  echo "OLD_R76_CRASH_VERSION: restore saved code before R7612"
  echo "Your saved R75 backup remains available. No installation attempted."
  exit 6
fi
# R76.12 is a scoped non-production instrumentation update from exact R76.11.
# Refuse unknown/partial versions. No legacy-version workaround or silent downgrade.
if ! grep -Fq 'PLUGIN_VERSION = "1.0.46-r76.11-preview-coldstart-fast-beta"' "$PLUGIN/plugin.py" ||
   ! grep -Fq 'R7611_NORMAL_PREVIEW_NO_COLD_DECORATED_SCAN' "$PLUGIN/core.py"; then
  echo "BASE_VERSION_MISMATCH: installed R76.11 required before R76.12 profiling beta"
  echo "Receiver unchanged."
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
echo "R7612_BETA_INSTALL_OK: $VERSION"
echo "Restart ONLY Enigma2 GUI using the OpenATV menu."
echo "Rollback code only: sh /tmp/download-r7612-profile-beta.sh --rollback"
