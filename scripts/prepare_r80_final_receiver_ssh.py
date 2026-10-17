#!/usr/bin/env python3
"""One-command SSH preparation for IPToSatPro R80 FINAL, without opkg.

Receiver: Vu+ Zero 4K, Python 3.14. Reads only the previously verified
R80.1 Index Focus IPK and writes a private source copy + unpublished
distribution bundle under /home/root. Does not restart Enigma2, inspect
mappings, install software, or publish to GitHub.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request

EXPECTED_SOURCE_SHA = "b6b1fe72ffbcbfaa398bd261c000f9361159a9e08f606a0af9d6da3d5ef04e5e"
EXPECTED_SOURCE_SIZE = 461250
EXPECTED_FINAL_VERSION = "1.0.46-r80.2-final"
EXPECTED_CORE_SHA = "74cd89b8c6a41b4537fd758cedb3a07b2bc0f9a5c215063e4c45b99e5d92cd2a"
SOURCE_TMP = Path("/tmp/iptosatpro-r801-indexfocus-hotpath-rc1-NOT_INSTALLED.ipk")
HOME = Path("/home/root/iptosatpro-r80-final")
SOURCE_SAVED = HOME / "R80_1_VALIDATED_SOURCE.ipk"
BUNDLE_DIR = HOME / "final-unpublished"
PINNED_COMMIT = "b611a5526aeaa65774a383cb6ad07587fea4ed64"
TOOL_NAMES = ("prepare_r80_final_offline.py", "prepare_r80_release_bundle_offline.py")
BASE_URL = ("https://raw.githubusercontent.com/wacayoub/IPToSatPro/" + PINNED_COMMIT + "/scripts/")


def fail(reason):
    print(json.dumps({"result": "R80_FINAL_SSH_PREPARATION_BLOCKED",
                      "reason": reason, "installed_code_modified": False,
                      "opkg_executed": False, "published": False}, indent=2))
    raise SystemExit(2)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as fd:
        while True:
            block = fd.read(128 * 1024)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def verified_source(path):
    return (path.is_file() and not path.is_symlink()
            and path.stat().st_size == EXPECTED_SOURCE_SIZE
            and digest(path) == EXPECTED_SOURCE_SHA)


def existing_bundle():
    if BUNDLE_DIR.is_symlink() or not BUNDLE_DIR.is_dir():
        return None
    manifest_path = BUNDLE_DIR / "r80-final.update.json"
    ipk_path = BUNDLE_DIR / "iptosatpro-r80-final.ipk"
    b64_path = BUNDLE_DIR / "r80-final.b64"
    sums_path = BUNDLE_DIR / "SHA256SUMS.txt"
    for p in (manifest_path, ipk_path, b64_path, sums_path):
        if not p.is_file() or p.is_symlink():
            return None
    try:
        manifest = json.loads(manifest_path.read_text("utf-8"))
        expected_sha = manifest["sha256"]
        if (manifest["version"] != EXPECTED_FINAL_VERSION or
                manifest["source_sha256"] != EXPECTED_SOURCE_SHA or
                manifest["production_published"] is not False or
                manifest["final_binary_receiver_tested"] is not False or
                manifest["size"] != ipk_path.stat().st_size or
                digest(ipk_path) != expected_sha):
            return None
        if base64.b64decode(b"".join(b64_path.read_bytes().split()),
                           validate=True) != ipk_path.read_bytes():
            return None
        if sums_path.read_text("utf-8").strip() != (expected_sha + "  " + ipk_path.name):
            return None
        return manifest
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        return None


def main():
    os.umask(0o077)
    if os.geteuid() != 0:
        fail("ROOT_SSH_SHELL_REQUIRED")
    source = None
    for candidate in (SOURCE_TMP, SOURCE_SAVED):
        if verified_source(candidate):
            source = candidate
            break
    if source is None:
        fail("VALIDATED_IPK_MISSING_OR_SHA_DIFFERS: expected 461250 bytes SHA256 "
             + EXPECTED_SOURCE_SHA + "; do not attempt to use an older R80 beta")
    if HOME.is_symlink():
        fail("RELEASE_DIRECTORY_IS_SYMLINK")
    HOME.mkdir(mode=0o700, exist_ok=True)
    HOME.chmod(0o700)
    if SOURCE_SAVED.is_symlink():
        fail("SAVED_SOURCE_IS_SYMLINK")
    if SOURCE_SAVED.exists() and not verified_source(SOURCE_SAVED):
        fail("SAVED_SOURCE_CONFLICT_REFUSING_OVERWRITE")
    if not SOURCE_SAVED.exists():
        with tempfile.NamedTemporaryFile(prefix=".ipk-", suffix=".part",
                                         dir=str(HOME), delete=False) as tmp:
            temp_path = Path(tmp.name)
            try:
                with source.open("rb") as original:
                    shutil.copyfileobj(original, tmp)
            except BaseException:
                temp_path.unlink(missing_ok=True)
                raise
        if not verified_source(temp_path):
            temp_path.unlink(missing_ok=True)
            fail("COPIED_SOURCE_SHA_MISMATCH")
        temp_path.chmod(0o600)
        os.replace(str(temp_path), str(SOURCE_SAVED))
    if BUNDLE_DIR.exists() or BUNDLE_DIR.is_symlink():
        manifest = existing_bundle()
        if manifest is None:
            fail("EXISTING_FINAL_OUTPUT_DIFFERS_REFUSE_OVERWRITE")
        print(json.dumps({
            "result": "R80_FINAL_BUNDLE_ALREADY_VERIFIED_UNPUBLISHED",
            "source_sha256": EXPECTED_SOURCE_SHA,
            "version": manifest["version"],
            "final_sha256": manifest["sha256"],
            "final_bytes": manifest["size"],
            "final_ipk": str(BUNDLE_DIR / "iptosatpro-r80-final.ipk"),
            "source_backup": str(SOURCE_SAVED),
            "installed_code_modified": False, "opkg_executed": False,
            "published": False
        }, indent=2))
        return 0

    with tempfile.TemporaryDirectory(prefix=".tools-", dir=str(HOME)) as tmpdir:
        tools = Path(tmpdir)
        for filename in TOOL_NAMES:
            url = BASE_URL + filename
            with urllib.request.urlopen(url, timeout=35) as response:
                data = response.read(60000)
                if not data or len(data) >= 60000:
                    fail("PINNED_BUILDER_DOWNLOAD_INVALID:" + filename)
            compile(data, filename, "exec")
            (tools / filename).write_bytes(data)
        output = tools / "candidate"
        result = subprocess.run(
            [sys.executable, str(tools / "prepare_r80_release_bundle_offline.py"),
             "--input", str(SOURCE_SAVED), "--out-dir", str(output), "--build"],
            cwd=str(tools), capture_output=True, text=True, timeout=150)
        if result.returncode:
            fail("FINAL_BUILDER_BLOCKED:" + (result.stdout + result.stderr)[-850:])
        manifest_file = output / "r80-final.update.json"
        manifest = json.loads(manifest_file.read_text("utf-8"))
        if (manifest.get("version") != EXPECTED_FINAL_VERSION or
                manifest.get("source_sha256") != EXPECTED_SOURCE_SHA or
                manifest.get("production_published") is not False):
            fail("FINAL_MANIFEST_VALIDATION_FAILED")
        output_ipk = output / "iptosatpro-r80-final.ipk"
        if output_ipk.stat().st_size != manifest["size"] or digest(output_ipk) != manifest["sha256"]:
            fail("FINAL_IPK_HASH_VALIDATION_FAILED")
        # The packager already verifies source/final core identity inside the IPK.
        report = json.loads(result.stdout)
        if (report.get("core_sha256_unchanged") != EXPECTED_CORE_SHA or
                report.get("code_unchanged") is not True):
            fail("ORIGINAL_CORE_NOT_PRESERVED")
        if existing_bundle() is not None or BUNDLE_DIR.exists():
            fail("OUTPUT_CREATED_CONCURRENTLY")
        output.rename(BUNDLE_DIR)

    print(json.dumps({
        "result": "R80_FINAL_BUNDLE_READY_UNPUBLISHED",
        "source_sha256": EXPECTED_SOURCE_SHA,
        "version": EXPECTED_FINAL_VERSION,
        "final_sha256": manifest["sha256"],
        "final_bytes": manifest["size"],
        "final_ipk": str(BUNDLE_DIR / "iptosatpro-r80-final.ipk"),
        "source_backup": str(SOURCE_SAVED),
        "code_unchanged": True,
        "installed_code_modified": False, "opkg_executed": False,
        "enigma2_restarted": False, "published": False
    }, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, UnicodeError, subprocess.TimeoutExpired) as exc:
        fail(type(exc).__name__ + ":" + str(exc)[:200])
