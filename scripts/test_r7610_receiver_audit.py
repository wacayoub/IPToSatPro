#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.10 read-only receiver audit regression tests on the real assembled IPK."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(label, path):
    spec = importlib.util.spec_from_file_location(label, ROOT / "scripts" / path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


audit = module("local_r7610_receiver_audit", "r7610_receiver_audit.py")
builder = module("local_r7610_builder", "build-r7610-normal48.py")


class LocalReceiverAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work = tempfile.TemporaryDirectory()
        cls.base = Path(cls.work.name)
        cls.plugin = cls.base / "installed_plugin"
        cls.plugin.mkdir()
        cls.config = cls.base / "config"
        cls.config.mkdir()
        cls.backups = cls.base / "backup"
        cls.backups.mkdir()
        cls.proc = cls.base / "proc"
        cls.proc.mkdir()
        cls.package = cls.base / "candidate.ipk"
        cls.meta = builder.build(cls.package)
        files = builder.pack.members_from(
            builder.pack.unpack_ar(cls.package.read_bytes())["data.tar.gz"])
        for name in ("plugin.py", "core.py", "monitor.py",
                     "updater.py", "preview_theme_r74.py", "home_themes_r767.py"):
            path = builder.P + name
            assert path in files, path
            (cls.plugin / name).write_bytes(files[path])

    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def scan(self):
        return audit.check_receiver(self.plugin, self.config, self.backups,
                                    self.config / "bridge.log", self.proc)

    def test_actual_ipk_is_recognized_and_all_skins_valid(self):
        report = self.scan()
        self.assertEqual(report["version"], audit.VERSION)
        self.assertTrue(report["static_pass"], report["checks"])
        self.assertEqual(report["hardware_av_pass"], None)
        self.assertTrue(report["no_changes"])
        self.assertEqual(report["log"]["status"], "log_unavailable")

    def test_normal48_guard_presence_is_enforced(self):
        result = self.scan()
        self.assertTrue(result["checks"]["normal48_bounded_candidate_pool"])
        path = self.plugin / "core.py"
        original = path.read_bytes()
        try:
            path.write_bytes(original.replace(b"R7610_NORMAL48_FAST_BUDGET",
                                             b"R7610_NORMAL48_GUARD_MISSING"))
            result = self.scan()
            self.assertFalse(result["checks"]["normal48_bounded_candidate_pool"])
            self.assertFalse(result["static_pass"])
            self.assertTrue(result["no_changes"])
        finally:
            path.write_bytes(original)

    def test_stale_version_is_rejected_without_modification(self):
        path = self.plugin / "plugin.py"
        original = path.read_bytes()
        try:
            path.write_bytes(original.replace(audit.VERSION.encode(), b"1.0.46-r76.7-stale"))
            report = self.scan()
            self.assertFalse(report["static_pass"])
            self.assertFalse(report["checks"]["exact_r7610_installed"])
            self.assertFalse(report["checks"]["updater_version_matches"] is False)
        finally:
            path.write_bytes(original)

    def test_log_summary_only_numbers_and_no_stream_identifiers(self):
        sensitive = "http://secret-provider.invalid/user/password"
        raw = [
            "2026-10-14 20:01:01 | PREVIEW_RANK_BG | "
            "candidate_count=8 elapsed=110ms index=25ms scoring=80ms url=" + sensitive + " SAT=DISCOVERY",
            "2026-10-14 20:01:02 | PREVIEW_RANK_BG | "
            "candidate_count=16 elapsed=800ms index=370ms scoring=410ms Name=PRIVATE_BOUQUET",
            "2026-10-14 20:01:03 | MATCH_BG_DONE | cost=34ms channel=PERSONAL",
            "2026-10-14 20:01:04 | IPTV_OK | url=" + sensitive,
            "2026-10-14 20:01:05 | IPTV_FAIL | url=" + sensitive,
        ]
        log = self.config / "bridge.log"
        log.write_text("\n".join(raw) + "\n", encoding="utf8")
        try:
            result = self.scan()
            summary = json.dumps(result)
            self.assertEqual(result["log"]["event_counts"]["PREVIEW_RANK_BG"], 2)
            self.assertEqual(result["log"]["latency_ms"]["PREVIEW_RANK_BG"]["p95"], 800)
            self.assertEqual(result["log"]["latency_ms"]["PREVIEW_RANK_BG"]["p50"], 110)
            self.assertEqual(result["log"]["preview_candidate_count_max"], 16)
            self.assertEqual(result["log"]["latency_ms"]["MATCH_BG_DONE"]["p50"], 34)
            self.assertEqual(result["log"]["preview_breakdown_ms"]["index_max"], 370)
            self.assertEqual(result["log"]["preview_breakdown_ms"]["scoring_max"], 410)
            self.assertEqual(result["log"]["preview_breakdown_ms"]["breakdown_samples"], 2)
            for secret in (sensitive, "PRIVATE_BOUQUET", "PERSONAL", "DISCOVERY"):
                self.assertNotIn(secret, summary)
            self.assertIsNone(result["hardware_av_pass"])
        finally:
            log.unlink()

    def test_legitimate_user_mapping_changes_are_nonblocking(self):
        folder = self.backups / "20261014T194000"
        folder.mkdir()
        data = self.config / "resolved_mappings.json"
        data.write_text('{"private": "do not print", "mapping": 1}')
        saved = {"resolved_mappings.json": hashlib.sha256(data.read_bytes()).hexdigest()}
        (folder / "mapping-hashes.json").write_text(json.dumps(saved))
        (self.backups / "last-backup-path").write_text(str(folder))
        try:
            self.assertEqual(self.scan()["mapping_backup"]["unchanged"], 1)
            data.write_text('{"private": "do not print", "mapping": 2}')
            report = self.scan()
            self.assertEqual(report["mapping_backup"]["changed_since_backup"], 1)
            self.assertTrue(report["static_pass"])
            self.assertNotIn("do not print", json.dumps(report))
        finally:
            data.unlink()
            (folder / "mapping-hashes.json").unlink()
            folder.rmdir()
            (self.backups / "last-backup-path").unlink()

    def test_unknown_or_missing_plugin_fails_closed(self):
        result = audit.check_receiver(self.base / "missing", self.config,
                                      self.backups, self.config / "missing_log", self.proc)
        self.assertFalse(result["static_pass"])
        self.assertEqual(result["checks"]["plugin_present"], False)

    def test_reject_malicious_backup_reference(self):
        path = self.backups / "last-backup-path"
        path.write_text("/etc")
        try:
            report = self.scan()
            self.assertEqual(report["mapping_backup"]["status"],
                             "invalid_backup_reference")
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()
