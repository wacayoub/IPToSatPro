#!/usr/bin/env python3
"""R76.11 zero-preview-sample forensic tests with no hardware/network access."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SRC=Path(__file__).resolve().parent/"audit_r7611_preview_logs_readonly.py"
s=importlib.util.spec_from_file_location("r7611_previewlog",SRC)
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
SINCE="2026-10-14 22:28:23"


class PreviewZeroSamples(unittest.TestCase):
    def test_postinstall_nonpreview_events_distinguished(self):
        lines=[
            "2026-10-14 20:27:34 | PREVIEW_RANK_BG | elapsed=56042ms candidate_count=48 name=SECRET_CHANNEL",
            "2026-10-14 22:32:04 | IPTV_OK | url=http://server.invalid/PASS",
            "2026-10-14 22:33:09 | MATCH_BG_DONE | cost=97ms private=SECRET_CHANNEL",
        ]
        report=m.inspect_lines(lines,SINCE)
        self.assertEqual(report["preview_total_in_tail"],1)
        self.assertEqual(report["preview_after_install"],0)
        self.assertEqual(report["interpretation"],"other_activity_but_no_preview_rank")
        self.assertEqual(report["recognized_events_after_install"]["IPTV_OK"],1)
        self.assertEqual(report["duration"]["samples"],0)
        self.assertEqual(report["last_preview_timestamp"],"2026-10-14 20:27:34")
        for secret in ("SECRET_CHANNEL","http://server.invalid","PASS"):
            self.assertNotIn(secret,json.dumps(report))

    def test_real_new_preview_aggregation_is_numeric_only(self):
        lines=[
            "2026-10-14 22:28:23 | PREVIEW_RANK_BG | elapsed=87ms index=40ms scoring=41ms candidate_count=4 name=PRIVATE",
            "2026-10-14 22:35:00 | PREVIEW_RANK_BG | elapsed=630ms index=75ms scoring=550ms candidate_count=48 url=secret",
            "2026-10-14 22:40:00 | PREVIEW_RANK_BG | elapsed=250ms index=70ms scoring=173ms candidate_count=7",
        ]
        report=m.inspect_lines(lines,SINCE,True)
        self.assertEqual(report["preview_after_install"],3)
        self.assertEqual(report["duration"]["p50_ms"],250)
        self.assertEqual(report["duration"]["p95_ms"],630)
        self.assertEqual(report["index_ms"]["max_ms"],75)
        self.assertEqual(report["preview_candidate_max_after_install"],48)
        self.assertEqual(report["interpretation"],"measured")
        self.assertTrue(report["log_tail_truncated"])
        self.assertNotIn("PRIVATE",json.dumps(report))

    def test_preview_logged_but_duration_missing(self):
        lines=["2026-10-14 22:31:00 | PREVIEW_RANK_BG | candidate_count=10"]
        report=m.inspect_lines(lines,SINCE)
        self.assertEqual(report["preview_after_install_missing_elapsed"],1)
        self.assertEqual(report["interpretation"],"preview_logged_without_elapsed")

    def test_absence_of_any_recent_entries_differs_from_zero_preview(self):
        r=m.inspect_lines([
            "2026-10-14 20:01:00 | PREVIEW_RANK_BG | elapsed=99ms"],SINCE)
        self.assertEqual(r["interpretation"],"no_logs_after_install_in_sample")
        self.assertEqual(r["last_timestamp_in_log"],"2026-10-14 20:01:00")

    def test_snapshot_marker_and_missing_log(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/"last-backup-path"
            p.write_text("/home/root/iptosatpro-r76-backups/20261014T222823")
            self.assertEqual(m.snapshot_time(p),SINCE)
            result=m.inspect(Path(t)/"not-created.log",p)
            self.assertEqual(result["interpretation"],"log_unavailable")
            p.write_text("/invalid/non-time-folder")
            self.assertIsNone(m.snapshot_time(p))


if __name__=="__main__":
    unittest.main()
