#!/usr/bin/env python3
"""Offline safety tests for R76.11 receiver after-install audit."""
import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "after_install",ROOT/"scripts/audit_r7611_after_install_readonly.py")
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


class ReceiverAfterInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        base=Path(self.temp.name)
        self.plugin=base/"plugin";self.plugin.mkdir()
        self.config=base/"config";self.config.mkdir()
        self.backups=base/"backups";self.backups.mkdir()
        self.saved=self.backups/"20261014T222823";self.saved.mkdir()
        (self.backups/"last-backup-path").write_text(str(self.saved))
        (self.plugin/"plugin.py").write_text(
            'PLUGIN_VERSION = "'+audit.EXPECTED+'"\n')
        (self.plugin/"core.py").write_text(
            "# R7611_NORMAL_PREVIEW_NO_COLD_DECORATED_SCAN\n"
            "# R7610_NORMAL48_FAST_BUDGET\n")

    def tearDown(self):
        self.temp.cleanup()

    def add_backup_files(self, data):
        with tarfile.open(self.saved/"settings-and-maps.tar.gz","w:gz") as tf:
            for name,content in data.items():
                b=content.encode()
                info=tarfile.TarInfo(
                    "etc/enigma2/SatIPTVBridge/"+name)
                info.size=len(b)
                tf.addfile(info,io.BytesIO(b))

    def read(self):
        return audit.report(self.plugin,self.config,self.backups)

    def test_backup_detects_postinst_removed_import_spec_without_leak(self):
        self.add_backup_files({
            "overrides.json":'{"private_ip":"http://iptv.invalid/pass", "secret":"xxxx"}',
            "resolved_mappings.json":'{"target": "old"}',
            "import_spec.json":'{"server_password":"private"}',
        })
        (self.config/"overrides.json").write_text(
            '{"private_ip":"http://iptv.invalid/pass", "secret":"xxxx"}')
        (self.config/"resolved_mappings.json").write_text('{"target": "new"}')
        report=self.read()
        self.assertTrue(report["installed_version_and_fast_guards_match"])
        self.assertTrue(report["no_changes"])
        self.assertEqual(report["backup"]["saved_files"],3)
        self.assertEqual(report["backup"]["same"],["overrides.json"])
        self.assertEqual(report["backup"]["changed"],["resolved_mappings.json"])
        self.assertEqual(report["backup"]["missing_since_backup"],["import_spec.json"])
        for s in ("http://iptv.invalid","private","xxxx","server_password"):
            self.assertNotIn(s,json.dumps(report))
        self.assertTrue(report["backup"]["import_spec_was_backed_up"])
        self.assertFalse(report["backup"]["import_spec_present_now"])

    def test_log_measurements_start_after_first_install_only(self):
        lines=[
            "2026-10-14 20:27:34 | PREVIEW_RANK_BG | candidate_count=48 elapsed=56042ms index=56000ms",
            "2026-10-14 22:28:24 | PREVIEW_RANK_BG | candidate_count=48 elapsed=160ms",
            "2026-10-14 22:28:25 | PREVIEW_RANK_BG | candidate_count=22 elapsed=450ms",
            "2026-10-14 22:28:26 | IPTV_OK | duration=100ms SECRET",
        ]
        (self.config/"bridge.log").write_text("\n".join(lines)+"\n")
        result=self.read()["preview_after_install"]
        self.assertEqual(result["status"],"measured")
        self.assertEqual(result["count"],2)
        self.assertEqual(result["median_ms"],160)
        self.assertEqual(result["p95_ms"],450)
        self.assertEqual(result["max_ms"],450)
        self.assertEqual(result["sample_quality"],"limited")

    def test_untrusted_backup_folder_rejected(self):
        (self.backups/"last-backup-path").write_text("/etc")
        report=self.read()
        self.assertEqual(report["backup"]["status"],"not_found")
        self.assertEqual(report["preview_after_install"]["status"],
                         "install_time_unknown")

    def test_missing_plugin_is_not_declared_installed(self):
        (self.plugin/"core.py").unlink()
        self.assertFalse(self.read()["installed_version_and_fast_guards_match"])


if __name__=="__main__":
    unittest.main()
