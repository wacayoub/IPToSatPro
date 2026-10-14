#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.9 release candidate safety gate.

Offline and read-only. Builds a temporary IPK, compares exact contents with
the R75 baseline, and checks the checksum-pinned staged beta. No receiver
commands, update manifests, repositories or mapping files are modified.
Passing this test does NOT mean the Vu+ hardware has been validated.
"""
import argparse
import base64
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "feature/r769-preview-manual-parity"
BETA_VERSION = "1.0.46-r76.9-preview-manual-parity-beta"


def load_builder():
    path = ROOT / "scripts" / "build-r76-metrix-preview.py"
    spec = importlib.util.spec_from_file_location("iptosat_r769_builder_gate", path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    return builder


def verify():
    builder = load_builder()
    manifest = json.loads((ROOT / "staging/r76-metrix-preview.update.json").read_text(encoding="utf-8"))
    published = json.loads((ROOT / "update.json").read_text(encoding="utf-8"))
    expected_url = ("https://raw.githubusercontent.com/wacayoub/IPToSatPro/"
                    + BRANCH + "/payload/r76-metrix-preview.b64")
    assert manifest["version"] == BETA_VERSION
    assert manifest["parts"] == [expected_url], "unrecognized or mutable payload origin"
    assert manifest.get("beta") is True
    assert manifest.get("receiver_tested") is False
    assert manifest.get("production_published") is False
    assert manifest.get("installation_requires_explicit_flag") is True
    assert published["version"] == "1.0.46-r70-final", "production was silently modified"
    assert builder.VERSION == BETA_VERSION

    staged = base64.b64decode((ROOT / "payload/r76-metrix-preview.b64").read_bytes())
    expected_digest = manifest["sha256"]
    assert len(staged) == manifest["size"], "staged IPK size mismatch"
    assert hashlib.sha256(staged).hexdigest() == expected_digest, "staged IPK digest mismatch"

    with tempfile.TemporaryDirectory(prefix="iptosat-final-audit-") as tmp:
        tmp = Path(tmp)
        baseline_path = tmp / "baseline-r75.ipk"
        candidate_path = tmp / "r769.ipk"
        base_info = builder.base.build(baseline_path)
        candidate_info = builder.build(candidate_path)
        candidate = candidate_path.read_bytes()
        baseline = builder.pack.members_from(
            builder.pack.unpack_ar(baseline_path.read_bytes())["data.tar.gz"])
        result = builder.pack.members_from(
            builder.pack.unpack_ar(candidate)["data.tar.gz"])

        assert base_info["production_published"] is False
        assert candidate_info["version"] == BETA_VERSION
        assert candidate_info["receiver_tested"] is False
        assert candidate_info["production_published"] is False
        assert hashlib.sha256(candidate).hexdigest() == expected_digest, (
            "rebuilt IPK differs from staged candidate")
        assert candidate == staged, "staged IPK differs byte-for-byte from rebuilt candidate"

        expected_changed = {builder.PLUGIN, builder.UPDATER, builder.THEME, builder.base.CORE}
        observed_changed = {p for p in baseline if baseline[p] != result.get(p)}
        added = set(result) - set(baseline)
        assert observed_changed == expected_changed, (
            "Unexpected core code or data mutation: " + repr(observed_changed))
        assert added == {builder.NOTE, builder.HOME_THEMES}, (
            "unexpected extra files in packaged plugin: " + repr(added))
        protected_paths = {
            builder.base.MONITOR,
            builder.P + "player.py",
            builder.P + "metadata_shadow.py",
        }
        assert builder.base.MONITOR in baseline, "monitor source missing from baseline"
        for path in protected_paths:
            # Some packaging generations embed player code in another module
            # instead of shipping a standalone player.py. Absence on BOTH
            # sides is protected; additions/removals already fail above.
            assert result.get(path) == baseline.get(path), (
                "protected playback/monitor asset changed: " + path)
        assert all("mapping" not in p.lower() and "override" not in p.lower()
                   for p in observed_changed | added), "mapping/override asset changed"
        for name, payload in result.items():
            if name.endswith(".py"):
                compile(payload, name, "exec")

        plugin = result[builder.PLUGIN].decode("utf-8")
        core = result[builder.base.CORE].decode("utf-8")
        assert 'PLUGIN_VERSION = "' + BETA_VERSION + '"' in plugin
        for required in (
            "R769_PREVIEW_MANUAL_PARITY",
            "fast_rank_matches_all_servers(",
            "PreviewManualMappingList",
            "_r769_preview_sat_context",
            "candidate_budget = 192 if self._r71_worker_deep else 48",
            "candidate_per_server = 64 if self._r71_worker_deep else 16",
        ):
            assert required in plugin, "release regression: missing " + required
        assert "R768" in core.upper(), "regional ranking policy missing from core"

        installer = (ROOT / "download-r76-beta.sh").read_text(encoding="utf-8")
        assert 'if [ "$#" -eq 0 ]; then MODE="--check"' in installer
        for required in (
            "--check|--install|--rollback",
            "BACKUPROOT",
            "PLUGIN_BACKUP_FAILED",
            "MAPPING_BACKUP_FAILED",
            "SHA256 / size mismatch",
            "NO_SETTINGS_OR_MAPPINGS_CHANGED",
            "CONFIG_AND_MAPPINGS_PRESERVED",
        ):
            assert required in installer, "installer safeguard missing: " + required
        subprocess.run(["sh", "-n", str(ROOT / "download-r76-beta.sh")], check=True)

    return {
        "candidate": BETA_VERSION,
        "candidate_sha256": expected_digest,
        "candidate_bytes": len(staged),
        "build_matches_staging": True,
        "published_version_untouched": published["version"],
        "changed_existing_assets": sorted(expected_changed),
        "protected_playback_monitor_unchanged": True,
        "installer_check_only_default": True,
        "software_release_gate": "PASS",
        "on_receiver_validated": False,
        "production_ready": False,
        "blocking_requirement": "Vu+ Zero 4K real video/audio/zap/mapping/rollback smoke test",
    }


if __name__ == "__main__":
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--require-hardware-proof", action="store_true",
                      help="fail closed: no live receiver attestation is available")
    ns = args.parse_args()
    try:
        report = verify()
        print("IPTOSAT_R769_RELEASE_AUDIT " + json.dumps(report, sort_keys=True))
    except Exception as exc:
        print("IPTOSAT_R769_RELEASE_GATE_FAILED: " + repr(exc), file=sys.stderr)
        sys.exit(1)
    if ns.require_hardware_proof:
        print("BLOCKED: do not call beta package a final verified Vu+ release", file=sys.stderr)
        sys.exit(3)
