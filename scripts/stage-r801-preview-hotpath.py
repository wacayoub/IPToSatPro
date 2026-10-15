#!/usr/bin/env python3
"""Stage R80.1 experimental beta on its feature branch, never main/update.json.

Builds a deterministic IPK; validates SHA and size before base64 staging.
Does not access or install on any Enigma2 receiver.
"""
import base64
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("r801_builder",
    ROOT / "scripts" / "build-r801-preview-hotpath.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)

BRANCH = "feature/r80-preview-hotpath-20261015"
PAYLOAD = ROOT / "payload/r801-preview-hotpath.b64"
MANIFEST = ROOT / "staging/r801-preview-hotpath.update.json"
URL = ("https://raw.githubusercontent.com/wacayoub/IPToSatPro/"
       + BRANCH + "/payload/r801-preview-hotpath.b64")


def stage():
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "r801.ipk"
        info = builder.build(target)
        raw = target.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == info["sha256"] and len(raw) == info["size"]
        PAYLOAD.parent.mkdir(exist_ok=True, parents=True)
        MANIFEST.parent.mkdir(exist_ok=True, parents=True)
        PAYLOAD.write_bytes(base64.encodebytes(raw))
        manifest = {
            "version": info["version"],
            "source_receiver_version": info["source_receiver_version"],
            "source_sha256": info["source_sha256"],
            "sha256": digest,
            "size": len(raw),
            "parts": [URL],
            "notes": ("Preview-only R80.1 pure-ratio and second-sort memoization "
                      "on top of frozen R80 RC1/R76.15 engine. "
                      "Experimental, NOT validated on Vu+ hardware."),
            "beta": True,
            "production_published": False,
            "receiver_tested": False,
            "cold_target_met": False,
            "installation_requires_explicit_flag": True,
        }
        MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                            encoding="utf8")
        assert base64.b64decode(PAYLOAD.read_bytes()) == raw
        assert manifest["version"] == builder.VERSION
        print("R801_STAGED_NONPRODUCTION", json.dumps(manifest, sort_keys=True))
        return manifest


if __name__ == "__main__":
    stage()
