#!/usr/bin/env python3
"""Stage R76.11 beta IPK on feature/release branch ONLY; never modify main."""
import base64
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "scripts" / "build-r7611-preview-cold.py"
spec = importlib.util.spec_from_file_location("r7611stagebuilder", path)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
BRANCH = "release/r769-finalization-20261014"
PAYLOAD = ROOT / "payload" / "r7611-preview-cold.b64"
MANIFEST = ROOT / "staging" / "r7611-preview-cold.update.json"
URL = ("https://raw.githubusercontent.com/wacayoub/IPToSatPro/" + BRANCH
       + "/payload/r7611-preview-cold.b64")


def stage():
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "r7611.ipk"
        result = builder.build(target)
        blob = target.read_bytes()
        assert hashlib.sha256(blob).hexdigest() == result["sha256"]
        assert len(blob) == result["size"]
        PAYLOAD.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        PAYLOAD.write_bytes(base64.encodebytes(blob))
        manifest = {
            "version": result["version"],
            "size": result["size"], "sha256": result["sha256"],
            "parts": [URL],
            "notes": ( "R76.11 beta skips cold decorated-index rebuild on the actual "
                       "normal Preview ranking route; DEEP 192/64 and manual "
                      "mapping, player, TV GUI and settings preserved. "
                      "Needs on-device performance/audio/video validation."),
            "beta": True, "receiver_tested": False,
            "production_published": False,
            "installation_requires_explicit_flag": True,
        }
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n",
                            encoding="utf8")
        assert base64.b64decode(PAYLOAD.read_bytes()) == blob
        print("R7611_STAGING_OK", json.dumps({
            "version": result["version"], "bytes": len(blob),
            "sha256": result["sha256"],
            "production_published": False,
        }, sort_keys=True))
        return result


if __name__ == "__main__":
    stage()
