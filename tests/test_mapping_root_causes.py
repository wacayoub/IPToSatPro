"""Root-cause regression tests for the rc7 mapping engine (AUDIT ONLY).

These tests guard the actual rc7 adapter but deliberately do not build or
publish a new receiver package. Native Vu+ tuner/decoder checks remain pending.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"r70"))
sys.path.insert(0,str(ROOT/"tests"))
import auto_recovery_rc7 as adapter
from test_auto_recovery_rc7 import Monitor, Timer, row, fingerprint, normalize, decision


class AuditedRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        adapter.attach_auto_recovery(Monitor, {
            "eTimer":Timer, "channel_fingerprint":fingerprint,
            "normalize_name":normalize, "match_decision":decision})

    def test_late_frame_cancels_auto_rescue(self):
        m=Monitor([row("replacement","beIN SPORTS 1",125,{"name":100})])
        m.playback_locked=False
        self.assertTrue(m._schedule_next_candidate("Decoder watchdog expired"))
        m._r70_rc7_worker.join(3)
        m.playback_locked=True
        m._r70_rc7_timer.fire()
        self.assertIsNone(m._r70_rc7_pending)
        self.assertEqual(m.restored,[])
        self.assertEqual(m.schedules,[])
        self.assertIn("AUTO_RESCUE_CANCEL_LATE_OK",m.logged)

    def test_delayed_frame_prevents_timeout_restore(self):
        m=Monitor([])
        m.playback_locked=False
        self.assertTrue(m._schedule_next_candidate("Decoder watchdog expired"))
        m._r70_rc7_worker.join(3)
        m._r70_rc7_pending["started"]-=10
        m.playback_locked=True
        m._r70_rc7_timer.fire()
        self.assertEqual(m.restored,[])
        self.assertNotIn("AUTO_RESCUE_TIMEOUT",m.logged)

    def test_only_dead_stream_without_alternatives_restores_sat(self):
        m=Monitor([])
        m.playback_locked=False
        m._schedule_next_candidate("EOF")
        m._r70_rc7_worker.join(3)
        m._r70_rc7_timer.fire()
        self.assertEqual(len(m.restored),1)

    def test_cancel_on_new_sat_identity(self):
        m=Monitor([row("replacement","beIN SPORTS 1",125,{"name":100})])
        m._schedule_next_candidate("EOF")
        m._r70_rc7_worker.join(3)
        m.current_sat_ref_string="SAT:OTHER"
        m._r70_rc7_timer.fire()
        self.assertFalse(m.schedules)
        self.assertFalse(m.restored)

    def test_core_client_api_contract_is_real(self):
        import base64, io, subprocess, tarfile, tempfile, ast
        raw=base64.b64decode((ROOT/"payload/r69-beta.b64").read_bytes())
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"base.ipk";p.write_bytes(raw)
            g=subprocess.check_output(["ar","p",str(p),"data.tar.gz"])
        with tarfile.open(fileobj=io.BytesIO(g),mode="r:gz") as t:
            mon=t.extractfile("./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/monitor.py").read().decode()
            core=t.extractfile("./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/core.py").read().decode()
            plugin=t.extractfile("./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/plugin.py").read().decode()
        moncls=next(x for x in ast.parse(mon).body if isinstance(x,ast.ClassDef) and x.name=="SatFallbackMonitor")
        names={x.name for x in moncls.body if isinstance(x,ast.FunctionDef)}
        for needed in ("_schedule_next_candidate","_build_candidate_plan","_stop_all_timers","_stop_probe_timers",
                       "_is_expected_bridge_iptv","_accept_verified_video"):
            self.assertIn(needed,names)
        self.assertIn("def fast_rank_matches_all_servers(",core)
        self.assertIn("def _load_selected_sat_candidates(",plugin)


class PreviewLockedSourceTests(unittest.TestCase):
    def namespace(self,found=True):
        class Config:
            def __init__(self,default=False):self.value=default
        class Settings:
            def _build_list(self):return None
        class Cat:
            def find_fingerprint(self, fp):
                return {"id":fp,"name":"AR BEIN SPORTS 6 FHD",
                        "url":"fake://source"} if found else None
        class Preview:
            def __init__(self):
                self._candidate_cache={}
                self.channels=[]
            def _selected_sat_row(self):
                return {"ref":"REF6","name":"beIN SPORTS 6"}
            def _load_selected_sat_candidates(self):
                self.channels=list(self._candidate_cache.get("REF6",("x",{},[],True))[2] or [])
                return len(self.channels)
        drops=[]
        ns={
            "cfg":SimpleNamespace(),
            "ConfigYesNo":Config,
            "SatIPTVBridgeSettings":Settings,
            "getConfigListEntry":lambda name,item:(name,item),
            "SatIPTVBridgePreview":Preview,
            "sat_service_key":lambda ref:ref,
            "_load_overrides":lambda:{"REF6":{"channel_id":"lock6"}},
            "channel_fingerprint":lambda c:c.get("id"),
            "_preview_candidate_cache_get":lambda ref:("beIN SPORTS 6",{},[],True),
            "_preview_candidate_cache_drop":lambda ref:drops.append(ref),
            "MONITOR":SimpleNamespace(catalog=Cat()),
        }
        return ns,Preview,drops

    def test_locked_sat_instant_preview_injects_real_catalogue_source(self):
        ns,Preview,drops=self.namespace()
        adapter.attach_plugin(ns)
        screen=Preview()
        self.assertEqual(screen._load_selected_sat_candidates(),1)
        self.assertEqual(screen.channels[0]["id"],"lock6")
        self.assertEqual(screen.channels[0]["_preview_score"],150)
        self.assertEqual(drops,[])

    def test_ghost_manual_lock_invalidates_empty_complete_cache(self):
        ns,Preview,drops=self.namespace(found=False)
        adapter.attach_plugin(ns)
        screen=Preview()
        self.assertEqual(screen._load_selected_sat_candidates(),0)
        self.assertFalse(screen._candidate_cache["REF6"][3])
        self.assertEqual(drops,["REF6"])

if __name__=="__main__":
    unittest.main()
