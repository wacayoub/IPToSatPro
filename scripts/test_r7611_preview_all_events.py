#!/usr/bin/env python3
"""No receiver access: validate R76.11 truncated Preview event analysis."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("preview_events",
    ROOT/"audit_r7611_preview_all_events_readonly.py")
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
BASE="2026-10-14 22:28:23"


class AllPreviewEventTests(unittest.TestCase):
    def test_old_events_with_new_no_preview(self):
        v=p.aggregate([
            "2026-10-14 20:27:26 | PREVIEW_AUTO_MAP   | channel=SECRET",
            "2026-10-14 20:27:26 | PREVIEW_RANK_BG    | elapsed=500ms",
            "2026-10-15 19:10:05 | IPTV_OK            | url=https://secret.invalid",
        ],BASE)
        self.assertEqual(v["finding"],"other_activity_no_preview_event")
        self.assertEqual(v["preview_events_after_install"],0)
        self.assertEqual(v["events_all"]["PREVIEW_RANK_BG"],1)
        self.assertNotIn("SECRET",json.dumps(v))
        self.assertNotIn("https://",json.dumps(v))

    def test_logger_truncates_codes_but_audit_finds_them(self):
        v=p.aggregate([
            "2026-10-15 19:11:00 | PREVIEW_INSTANT_SE | sat=SECRET",
            "2026-10-15 19:11:01 | PREVIEW_SEED_EXPAN | sat=SECRET",
            "2026-10-15 19:11:02 | PREVIEW_EXPAND_WAI | sat=SECRET",
            "2026-10-15 19:11:03 | PREVIEW_UI_CANDIDA | sat=SECRET",
        ],BASE)
        self.assertEqual(v["finding"],"preview_activity_without_rank_result")
        self.assertEqual(v["preview_events_after_install"],4)
        self.assertEqual(v["events_after_install"]["PREVIEW_SEED_EXPAN"],1)
        self.assertEqual(v["events_after_install"]["PREVIEW_UI_CANDIDA"],1)
        self.assertEqual(v["event_phase_legend"]["PREVIEW_SEED_EXPAN"],
                         "seed_loaded_rank_requested")
        self.assertNotIn("SECRET",json.dumps(v))

    def test_rank_completed(self):
        v=p.aggregate([
            "2026-10-15 19:11:05 | PREVIEW_RANK_BG    | elapsed=150ms index=15ms",
            "2026-10-15 19:11:08 | PREVIEW_AUTO_MAP   | sat=secret"
        ],BASE)
        self.assertEqual(v["finding"],"rank_results_observed")
        self.assertEqual(v["last_seen_event_by_code"]["PREVIEW_RANK_BG"],
                         "2026-10-15 19:11:05")

    def test_missing_timestamp_not_counted_after(self):
        v=p.aggregate(["bad timestamp | PREVIEW_RANK_BG | elapsed=100ms"],BASE)
        self.assertEqual(v["preview_events_after_install"],0)
        self.assertEqual(v["events_all"]["PREVIEW_RANK_BG"],1)

    def test_no_install_marker(self):
        self.assertEqual(p.aggregate([],None)["finding"],"no_install_marker")

    def test_report_uses_only_approved_local_log_and_no_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"backups";root.mkdir()
            snapshot=root/"20261014T222823";snapshot.mkdir()
            (root/"last-backup-path").write_text(str(snapshot))
            log=Path(td)/"bridge.log"
            log.write_text(
                "2026-10-15 19:13:00 | PREVIEW_SEED_EXPAN | private=secret\n")
            before=log.read_bytes()
            r=p.report(log,root)
            self.assertEqual(r["events_after_install"]["PREVIEW_SEED_EXPAN"],1)
            self.assertFalse(r["receiver_modified"])
            self.assertEqual(log.read_bytes(),before)
            self.assertNotIn("secret",json.dumps(r))


if __name__=="__main__":
    unittest.main()
