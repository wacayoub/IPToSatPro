#!/usr/bin/env python3
"""Offline acceptance tests on fabricated logs; no receiver, no mapping data."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("receiver_audit801",R/"scripts/audit_r801_receiver_readonly.py")
a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
BASE="2026-10-15 22:00:00"

class R801ReceiverReadOnly(unittest.TestCase):
    def fake_logs(self,n,nominate=120,score=300,rank_error=False):
        lines=["2026-10-15 21:59:59 | PREVIEW_STAGE | total=80000ms nominate=70000ms score=9999ms cache=0 scored=100"]
        for i in range(n):
            stamp=f"2026-10-15 22:{i:02d}:01"
            lines.append(f"{stamp} | PREVIEW_STAGE | total={nominate+score}ms nominate={nominate}ms score={score}ms rescue=1ms sort=1ms cache=0 scored=80 channel=SECRET_IPTV")
            lines.append(f"{stamp} | PREVIEW_RANK_BG | candidate_count=48 elapsed={nominate+score}ms error={'fail' if rank_error else ''} channel=SECRET_IPTV")
        return lines
    def test_10_distinct_speed_gate_pass(self):
        m,state=a.summarize(self.fake_logs(10),BASE)
        self.assertEqual(state,"PREVIEW_SPEED_GATE_PASS")
        self.assertEqual(m["nominated_ms_p95"],120)
        self.assertEqual(m["ranking_completed"],10)
        self.assertNotIn("SECRET_IPTV",json.dumps(m))
    def test_any_slow_at_top_of_distribution_fails(self):
        v=self.fake_logs(10)
        v[1]=v[1].replace("nominate=120ms","nominate=8000ms")
        m,state=a.summarize(v,BASE)
        self.assertEqual(state,"NOMINATION_SPEED_GATE_FAIL")
        self.assertEqual(m["nominated_ms_max"],8000)
    def test_expensive_score_blocks_r80(self):
        m,state=a.summarize(self.fake_logs(10,score=2400),BASE)
        self.assertEqual(state,"SCORING_SPEED_GATE_FAIL")
        self.assertEqual(m["cold_score_ms_p95"],2400)
    def test_expensive_rescue_blocks_r80(self):
        slow=[x.replace("rescue=1ms","rescue=1700ms") for x in self.fake_logs(10)]
        m,state=a.summarize(slow,BASE)
        self.assertEqual(state,"RESCUE_SPEED_GATE_FAIL")
        self.assertEqual(m["cold_rescue_ms_p95"],1700)
    def test_expensive_sort_blocks_r80(self):
        slow=[x.replace("sort=1ms","sort=692ms") for x in self.fake_logs(10)]
        m,state=a.summarize(slow,BASE)
        self.assertEqual(state,"SORT_SPEED_GATE_FAIL")
        self.assertEqual(m["cold_sort_ms_p95"],692)
    def test_total_cold_gate_even_when_individual_phases_pass(self):
        m,state=a.summarize(self.fake_logs(10,nominate=850,score=400),BASE)
        self.assertEqual(state,"COLD_TOTAL_SPEED_GATE_FAIL")
        self.assertGreater(m["cold_total_ms_p95"],1000)
    def test_cached_events_cannot_falsely_approve(self):
        rows=[x.replace("cache=0","cache=1") for x in self.fake_logs(10)]
        m,state=a.summarize(rows,BASE)
        self.assertEqual(state,"INSUFFICIENT_COLD_SAMPLES")
        self.assertEqual(m["cold_samples"],0)
    def test_fewer_than_10_never_final(self):
        self.assertEqual(a.summarize(self.fake_logs(2),BASE)[1],"INSUFFICIENT_SAMPLES")
        self.assertEqual(a.summarize([],None)[1],"INSTALL_BASELINE_UNKNOWN")
    def test_errors_block_nomination_even_if_fast(self):
        m,state=a.summarize(self.fake_logs(10,rank_error=True),BASE)
        self.assertEqual(state,"RUNTIME_ERRORS")
        self.assertEqual(m["ranking_errors"],10)
    def test_snapshot_baseline_resolves_only_trusted_local_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"backups";root.mkdir()
            d=root/"20261015T220000";d.mkdir()
            (root/"last-backup-path").write_text(str(d))
            self.assertEqual(a.install_timestamp(root),BASE)
            (root/"last-backup-path").write_text("/tmp/foreign-dir")
            self.assertIsNone(a.install_timestamp(root))
    def test_old_version_cannot_pass_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"backups";root.mkdir()
            d=root/"20261015T220000";d.mkdir()
            (root/"last-backup-path").write_text(str(d))
            log=Path(tmp)/"bridge.log"
            log.write_text("\n".join(self.fake_logs(10))+"\n")
            plugin=Path(tmp)/"plugin.py";plugin.write_text('PLUGIN_VERSION = "1.0.46-r80-final-rc1"')
            core=Path(tmp)/"core.py";core.write_text("R7615_NOMINATION_INDEX_ONLY")
            out=a.report(log,root,plugin,core)
            self.assertEqual(out["finding"],"R801_NOT_INSTALLED_OR_INCOMPLETE")
            self.assertFalse(out["r801_installed_on_disk"])
    def test_readonly_privacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"backups";root.mkdir()
            d=root/"20261015T220000";d.mkdir()
            (root/"last-backup-path").write_text(str(d))
            log=Path(tmp)/"bridge.log"
            log.write_text("\n".join(self.fake_logs(10))+"\n")
            plugin=Path(tmp)/"plugin.py";plugin.write_text('PLUGIN_VERSION = "1.0.46-r80.1-preview-hotpath-beta"')
            core=Path(tmp)/"core.py";core.write_text("R7615_NOMINATION_INDEX_ONLY\nR80_PREVIEW_PURE_HOTPATH_V1")
            before=log.read_bytes()
            out=a.report(log,root,plugin,core)
            self.assertEqual(out["finding"],"PREVIEW_SPEED_GATE_PASS")
            self.assertFalse(out["receiver_modified"])
            self.assertFalse(out["mapping_files_read"])
            self.assertFalse(out["release_final_authorized"])
            self.assertEqual(log.read_bytes(),before)
            self.assertNotIn("SECRET_IPTV",json.dumps(out))

if __name__=="__main__":
    unittest.main()
