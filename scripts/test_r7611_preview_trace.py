#!/usr/bin/env python3
"""Read-only R76.11 Preview trace: private-safe synthetic regression tests."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parent/"audit_r7611_preview_trace_readonly.py"
spec=importlib.util.spec_from_file_location("preview_trace",SCRIPT)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

BASE="2026-10-14 22:28:23"
class PreviewCacheTraceTests(unittest.TestCase):
    def test_old_rank_and_new_iptv_only(self):
        out=m.summarize([
            "2026-10-14 20:26:58 | PREVIEW_RANK_BG | elapsed=56042ms sat=PRIVATE",
            "2026-10-15 04:13:50 | IPTV_OK | url=https://PRIVATE.invalid/pwd",
        ],BASE)
        self.assertEqual(out["interpretation"],"other_events_after_install_but_no_preview_events")
        self.assertEqual(out["event_counts_all"]["PREVIEW_RANK_BG"],1)
        self.assertEqual(out["preview_events_after_install"],{})
        self.assertEqual(out["last_preview_event"],"2026-10-14 20:26:58")
        self.assertNotIn("PRIVATE",json.dumps(out))

    def test_preview_but_no_rank_is_distinguished(self):
        x=m.summarize([
            "2026-10-15 04:00:00 | PREVIEW_EXPAND_WAIT | sat='private name'",
            "2026-10-15 04:00:01 | PREVIEW_UI_CANDIDATES | candidate_count=48",
            "2026-10-15 04:00:02 | PREVIEW_AUTO_MAP | selected='IPTV private'",
        ],BASE)
        self.assertEqual(x["interpretation"],"preview_events_without_rank")
        self.assertEqual(x["preview_events_after_install"]["PREVIEW_EXPAND_WAIT"],1)
        self.assertNotIn("private",json.dumps(x))

    def test_rank_and_unlogged_elapsed(self):
        x=m.summarize([
            "2026-10-15 04:10:10 | PREVIEW_RANK_BG | elapsed=87ms candidate_count=8",
            "2026-10-15 04:10:11 | PREVIEW_RANK_BG | candidate_count=22",
            "2026-10-15 04:10:12 | PREVIEW_STAY_OPEN | channel=private",
        ],BASE)
        self.assertEqual(x["interpretation"],"preview_rank_emitted")
        self.assertEqual(x["preview_rank_durations_after_install"],1)
        self.assertEqual(x["preview_events_after_install"]["PREVIEW_RANK_BG"],2)

    def test_real_package_has_cache_bypass_and_logging(self):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            p=base/"plugin.py"
            c=base/"core.py"
            p.write_text('PLUGIN_VERSION = "1.0.46-r76.11-preview-coldstart-fast-beta"\n'
                         'self.candidate_poll_timer.callback.append(self._poll_expanded_candidates)\n'
                         '_startup_log("PREVIEW_RANK_BG",\n'
                         'shared = _preview_candidate_cache_get(raw)\n'
                         'if shared is not None and bool(shared[3]) and not (self._r71_deep_requested and self._r71_deep_target_ref == raw):\n')
            c.write_text("# R7611_NORMAL_PREVIEW_NO_COLD_DECORATED_SCAN\n")
            x=m.static_wiring(p,c)
            self.assertTrue(x["r7611_installed"])
            self.assertTrue(x["normal_shared_cache_can_skip_rank_logging"])
            self.assertTrue(x["deep_request_can_bypass_shared_cache"])

    def test_read_only_report_with_portable_backup(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);back=root/"backups";back.mkdir()
            saved=back/"20261014T222823";saved.mkdir()
            marker=back/"last-backup-path";marker.write_text(str(saved))
            log=root/"bridge.log"
            log.write_text("2026-10-15 04:13:50 | IPTV_OK | token=secret\n")
            plugin=root/"plugin.py";plugin.write_text("# no code")
            core=root/"core.py";core.write_text("# no code")
            out=m.report(log,marker,plugin,core)
            self.assertTrue(out["no_changes"])
            self.assertEqual(out["interpretation"],"other_events_after_install_but_no_preview_events")
            self.assertEqual(out["log_tail_truncated"],False)
            self.assertNotIn("secret",json.dumps(out))
            self.assertEqual(out["since_install"],BASE)

    def test_marker_abuse_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);marker=folder/"last-backup-path"
            marker.write_text("/etc")
            self.assertIsNone(m.since_install(marker))
            marker.write_text(str(folder/"20261014T222823"))
            self.assertEqual(m.since_install(marker),BASE)


if __name__=="__main__":
    unittest.main()
