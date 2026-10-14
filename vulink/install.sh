#!/bin/sh
# VuLink Pro V3 beta: safe, isolated plugin deployment on OpenATV/Enigma2.
set -eu
BRANCH="feature/vulink-v3-github-relay"
RAW="https://raw.githubusercontent.com/wacayoub/IPToSatPro/$BRANCH/vulink"
TARGET="/usr/lib/enigma2/python/Plugins/Extensions/VuLink"
BACKUPS="/home/root/vulink-backups"
MODE="--check"
if [ "$#" -gt 0 ]; then MODE="$1"; fi

case "$MODE" in --check|--install|--rollback) ;; *)
  echo "Usage: sh install.sh [--check|--install|--rollback]"
  exit 2 ;;
esac
[ "$(id -u)" = "0" ] || { echo "ROOT_REQUIRED"; exit 2; }

if [ "$MODE" = "--rollback" ]; then
  [ -f "$BACKUPS/last-path" ] || { echo "NO_BACKUP"; exit 3; }
  SAVED="$(cat "$BACKUPS/last-path")"
  case "$SAVED" in "$BACKUPS"/*) ;; *) echo "UNSAFE_BACKUP_PATH"; exit 3 ;; esac
  [ -d "$SAVED" ] || { echo "BACKUP_MISSING"; exit 3; }
  if [ -d "$SAVED/plugin" ]; then
    rm -rf "$TARGET"
    cp -a "$SAVED/plugin" "$TARGET"
    echo "RESTORED_PREVIOUS_VULINK"
  elif [ -f "$SAVED/was-not-installed" ]; then
    rm -rf "$TARGET"
    echo "REMOVED_FIRST_VULINK_INSTALL"
  else
    echo "BACKUP_NOT_VALID"
    exit 3
  fi
  echo "Restart Enigma2 GUI from OpenATV menu."
  exit 0
fi

command -v wget >/dev/null || { echo "WGET_MISSING"; exit 3; }
command -v python3 >/dev/null || { echo "PYTHON3_MISSING"; exit 3; }

WORK="$(mktemp -d /tmp/vulink-install.XXXXXX)"
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
for filename in bridge.py plugin.py v2.py v3.py v3_setup.py qrpng.py __init__.py; do
  wget -q -O "$WORK/$filename" "$RAW/$filename" || {
    echo "DOWNLOAD_FAILED: $filename"; exit 3; }
done

python3 - "$WORK" <<'PY'
import pathlib, sys, hashlib
base=pathlib.Path(sys.argv[1])
expected={
 "bridge.py":"8346dffe7f98b9187241829388b92d34c71700b6",
 "plugin.py":"37bc1a8b25e05518125b70d02b945386ceed9245",
 "v2.py":"9699cf9ccddce5867f298aeab411420b61db2825",
 "v3.py":"affe154479bd26d85f60338d98c8ddf77da9f082",
 "v3_setup.py":"53863789fdbb846f2150515c5452c9430eb4912f",
 "qrpng.py":"1c59db4cd9ae80ca6e4ef26a3f7fd106cccf7119",
 "__init__.py":"37aa9c748e07ee20a2fad065d72973e7da656835"
}
for name,wanted in expected.items():
    data=(base/name).read_bytes()
    git_sha=hashlib.sha1(b"blob "+str(len(data)).encode("ascii")+bytes([0])+data).hexdigest()
    if git_sha != wanted:
        raise SystemExit("INTEGRITY_FAILED: "+name)
print("VULINK_V3_CONTENT_PIN_VERIFIED")
for name in ("bridge.py","plugin.py","v2.py","v3.py","v3_setup.py","qrpng.py","__init__.py"):
    text=(base/name).read_text(encoding="utf-8")
    compile(text,str(base/name),"exec")
    print("VALID_PYTHON",name,len(text))
body=(base/"bridge.py").read_text(encoding="utf-8")
assert 'VERSION = "0.1.0"' in body
assert 'class ProPairingServer(PairingServer)' in (base/"v2.py").read_text(encoding="utf-8")
assert 'class RelayAgent:' in (base/"v3.py").read_text(encoding="utf-8")
assert 'class PairingServer:' in body
print("VULINK_PACKAGE_CHECK_PASS")
PY

if [ "$MODE" = "--check" ]; then
  echo "CHECK_ONLY • no receiver files changed"
  exit 0
fi

mkdir -p "$BACKUPS"
chmod 700 "$BACKUPS"
STAMP="$(date +%Y%m%d-%H%M%S)-$$"
SAVED="$BACKUPS/$STAMP"
mkdir "$SAVED"
if [ -d "$TARGET" ]; then
  cp -a "$TARGET" "$SAVED/plugin" || { echo "BACKUP_FAILED"; exit 4; }
else
  : > "$SAVED/was-not-installed"
fi

mkdir -p "$TARGET"
for filename in bridge.py plugin.py v2.py v3.py v3_setup.py qrpng.py __init__.py; do
  cp "$WORK/$filename" "$TARGET/$filename"
  chmod 644 "$TARGET/$filename"
done
printf '%s\n' "$SAVED" > "$BACKUPS/last-path"
chmod 600 "$BACKUPS/last-path"
echo "INSTALLED VuLink Pro V3 3.0.0-rc1 (GitHub private relay)"
echo "No IPTV mappings, credentials or player code modified."
echo "Phone actions require GREEN approval on Vu+ screen; YELLOW denies."
echo "QR generated offline (built in), or address+code as fallback."
echo "SETUP_ONCE: python3 /usr/lib/enigma2/python/Plugins/Extensions/VuLink/v3_setup.py"
echo "Restart Enigma2 GUI; open Plugins > VuLink Pro V3 - ChatGPT Connect."
echo "Rollback: sh /tmp/install-vulink-v2.sh --rollback"
