#!/usr/bin/env python3
"""Compare two RC5 IPKs by actual content, ignoring archive timestamps.

The local GitHub Actions build and receiver-style HTTPS bootstrap can have
different .tar.gz bytes due to metadata timestamps; this check rejects any
file, symlink, ownership, permission, or payload-content mismatch.
No extraction or installation is performed.
"""
import hashlib
import io
import subprocess
import sys
import tarfile
from pathlib import Path


def members(ipk):
    raw = Path(ipk).read_bytes()
    if not raw.startswith(b"!<arch>\\n"):
        raise AssertionError("Not an ar package: " + str(ipk))
    manifest = {}
    for kind in ("control", "data"):
        packed = subprocess.check_output(
            ["ar", "p", str(ipk), kind + ".tar.gz"]
        )
        with tarfile.open(fileobj=io.BytesIO(packed), mode="r:gz") as archive:
            for item in archive:
                key = (kind, item.name)
                if key in manifest:
                    raise AssertionError("Duplicate member: " + repr(key))
                if item.isfile():
                    digest = hashlib.sha256(archive.extractfile(item).read()).hexdigest()
                else:
                    digest = None
                manifest[key] = (
                    item.type, item.mode, item.uid, item.gid,
                    item.linkname, item.size, digest
                )
    debian = subprocess.check_output(["ar", "p", str(ipk), "debian-binary"])
    if debian != b"2.0\\n":
        raise AssertionError("Unexpected Debian package version")
    if ("control", "./control") not in manifest:
        raise AssertionError("Missing control file")
    return manifest


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: check_rc5_package_equivalence.py local.ipk remote.ipk")
    local = members(sys.argv[1])
    remote = members(sys.argv[2])
    if local != remote:
        changed = sorted(key for key in set(local) | set(remote)
                         if local.get(key) != remote.get(key))
        raise AssertionError("Receiver bootstrap package differs from CI build: "
                             + repr(changed[:30]))
    print("PASS: receiver HTTPS bootstrap and CI build have identical package")
    print("      file hashes, paths, types, modes, ownership and symlink targets")
    print("      (archive timestamps ignored; no installation performed)")


if __name__ == "__main__":
    main()
