#!/usr/bin/env python3
"""Build an unpublished R80 FINAL distribution bundle from the exact tested IPK.

Offline, no receiver, opkg, credentials, network or GitHub publishing.
Requires the exact 461250-byte SHA-pinned working R80.1 Index Focus RC1.

The output directory is created only with --build, must not already exist,
and contains a final IPK, a Base64 payload for a later controlled GitHub
upload, a matching update manifest and a SHA256SUMS record.
"""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path

from prepare_r80_final_offline import FINAL, OLD, TESTED_SHA, digest, transform

RELEASE_BRANCH = "release/r80-indexfocus-final-20261017"
PART_NAME = "r80-final.b64"
IPK_NAME = "iptosatpro-r80-final.ipk"
MANIFEST_NAME = "r80-final.update.json"
PAYLOAD_URL = ("https://raw.githubusercontent.com/wacayoub/IPToSatPro/"
               + RELEASE_BRANCH + "/payload/" + PART_NAME)


def build_bundle(source):
    final, audit = transform(source)
    assert audit["source_sha256"] == TESTED_SHA
    assert audit["final_version"] == FINAL
    assert audit["unchanged_operational_payload"] is True
    assert audit["published"] is False

    encoded = base64.b64encode(final) + b"\n"
    decoded = base64.b64decode(encoded, validate=False)
    assert decoded == final
    manifest = {
        "version": FINAL,
        "size": len(final),
        "sha256": digest(final),
        "parts": [PAYLOAD_URL],
        "notes": ("R80 FINAL / Index Focus: exact functionally validated R80.1 "
                  "receiver engine. Metadata-only version promotion; Preview "
                  "cold P95 not measured. Manual install and verified backup required."),
        "beta": False,
        "source_hardware_functionally_validated": True,
        "final_binary_receiver_tested": False,
        "cold_preview_speed_certified": False,
        "production_published": False,
        "installation_requires_explicit_flag": True,
        "source_version": OLD,
        "source_sha256": TESTED_SHA,
    }
    assert manifest["parts"][0].endswith("/payload/" + PART_NAME)
    assert manifest["sha256"] == hashlib.sha256(decoded).hexdigest()
    artifacts = {
        IPK_NAME: final,
        PART_NAME: encoded,
        MANIFEST_NAME: (json.dumps(manifest, sort_keys=True, indent=2)
                        + "\n").encode("utf-8"),
        "SHA256SUMS.txt": (digest(final) + "  " + IPK_NAME + "\n").encode(),
    }
    return artifacts, audit, manifest


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", type=Path, required=True,
                    help="Exact, receiver-validated R80.1 RC1 IPK")
    ap.add_argument("--out-dir", type=Path, default=Path("r80-final-unpublished"))
    ap.add_argument("--build", action="store_true",
                    help="Write distribution bundle locally; never publish it")
    args = ap.parse_args()
    os.umask(0o077)
    try:
        source = args.input.read_bytes()
        output, audit, manifest = build_bundle(source)
        report = {
            "result": "R80_FINAL_OFFLINE_BUNDLE_VERIFIED_NOT_PUBLISHED",
            "source_sha256": TESTED_SHA,
            "final_sha256": manifest["sha256"],
            "final_version": FINAL,
            "final_bytes": manifest["size"],
            "core_sha256_unchanged": audit["core_sha256_unchanged"],
            "code_unchanged": audit["unchanged_operational_payload"],
            "production_published": False,
            "hardware_touched": False,
            "release_branch": RELEASE_BRANCH,
            "generated_files": list(output),
        }
        if args.build:
            if args.out_dir.is_symlink() or args.out_dir.exists():
                raise ValueError("OUTPUT_EXISTS_REFUSE_OVERWRITE")
            args.out_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
            for name, data in output.items():
                path = args.out_dir / name
                with path.open("xb") as fp:
                    fp.write(data)
                if path.read_bytes() != data:
                    raise ValueError("WRITTEN_FILE_MISMATCH:" + name)
            report["output_dir"] = str(args.out_dir)
        else:
            report["result"] = "R80_FINAL_OFFLINE_BUNDLE_DRY_RUN_PASS"
        print(json.dumps(report, sort_keys=True, indent=2))
        return 0
    except (OSError, ValueError, AssertionError, UnicodeError) as exc:
        print(json.dumps({"result":"R80_FINAL_BUNDLE_BLOCKED",
                          "reason":str(exc)[:240], "production_published":False}, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
