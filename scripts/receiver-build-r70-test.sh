#!/bin/sh
# Receiver-only download and LOCAL BUILD of the r70 RC. NO INSTALL.
# OpenATV 8.0.1 / Vu+ Zero 4K. No online updater or main-branch changes.
set -eu

ROOT=/tmp/iptosat-r70-source
OUT=/tmp/iptosat-r70-rc3.ipk
BASE=https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r70-rc3-no-signal

command -v python3 >/dev/null 2>&1 || {
    echo "ERROR: Python3 is required; nothing changed."
    exit 1
}
command -v wget >/dev/null 2>&1 || {
    echo "ERROR: wget is required; nothing changed."
    exit 1
}

mkdir -p "$ROOT/scripts" "$ROOT/r70" "$ROOT/payload" "$ROOT/bin"

for item in \
    scripts/build-r70-candidate.py \
    scripts/portable_ar_r70.py \
    r70/r70_safety_core.py \
    r70/r70_monitor_adapter.py \
    r70/r70_lock_adapter.py \
    r70/r70_preview_patch.py \
    r70/r70_preview_async.py \
    r70/no_signal_policy.py \
    r70/fta_runtime_adapter.py \
    payload/r69-beta.b64
do
    echo "Fetching $item"
    wget -q -O "$ROOT/$item" "$BASE/$item" || {
        echo "ERROR: Could not download $item; r69 remains installed."
        exit 1
    }
    test -s "$ROOT/$item" || {
        echo "ERROR: Empty $item download; nothing installed."
        exit 1
    }
done

# Always use tested temporary Python ar shim: receiver firmware often ships
# BusyBox without 'ar r'. No package-manager changes and no extra opkg install.
cp "$ROOT/scripts/portable_ar_r70.py" "$ROOT/bin/ar"
chmod 700 "$ROOT/bin/ar"
export PATH="$ROOT/bin:$PATH"

cd "$ROOT"
echo "Building offline IPK against pinned published r69 SHA256..."
python3 scripts/build-r70-candidate.py || {
    echo "ERROR: Candidate build refused. Nothing installed."
    exit 1
}
test -s r70-candidate.ipk

# Basic archive/version/metadata integrity checks before copying.
python3 - <<'PY'
import io, os, subprocess, tarfile
from pathlib import Path
ipk=Path("r70-candidate.ipk")
assert ipk.read_bytes().startswith(b"!<arch>\n")
ctrl=subprocess.check_output(["ar", "p", str(ipk), "control.tar.gz"])
with tarfile.open(fileobj=io.BytesIO(ctrl),mode="r:gz") as t:
    c=t.extractfile("./control").read().decode("utf-8")
assert "Version: 1.0.46-r70-rc3\n" in c, c
print("Validated r70 RC package control. NOT INSTALLED.")
PY

cp r70-candidate.ipk "$OUT"
echo "SUCCESS: $OUT"
echo "Package bytes: $(wc -c < "$OUT" | tr -d ' ')"
if command -v sha256sum >/dev/null 2>&1; then sha256sum "$OUT"; fi
echo "No installation performed. Online Update and r69 unchanged."
echo "Optional manual test after backup: opkg install --force-reinstall $OUT"
