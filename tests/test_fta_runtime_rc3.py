"""Offline integration tests for r70-rc3 FTA gate and Preview TV expansion."""
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "r70"))
from fta_runtime_adapter import attach_monitor, attach_plugin

def cfg(enabled=True):
    val = lambda x: SimpleNamespace(value=x)
    return SimpleNamespace(fta_no_signal=val(enabled), fallback_no_signal=val(True),
                           enabled=val(True))

class NoSignalMonitorTests(unittest.TestCase):
    def monitor(self, access=False, tuner="FAILED", policy=True, old_gate=False):
        class Fake:
            def __init__(self):
                self.cfg=cfg(policy)
                self.current_sat_started_at=time.time()-3
                self.current_sat_ref_string="sat-1"
                self.tuner_state=tuner
                self.video_event_seen=False
                self._fallback_crypto_gate=None
                self._r70_fta_event_ref=""
                self.direct_mapping_source=""
                self.timer=SimpleNamespace(start=lambda *args: None)
                self._fallback_calls=0
                self.log=[]
                self.session=SimpleNamespace(nav=SimpleNamespace(
                    getCurrentlyPlayingServiceReference=lambda:
                        SimpleNamespace(toString=lambda: "sat-1")
                ))
            def _ref_valid(self,ref):return True
            def _same_sat_still_playing(self):return True
            def _manual_lock_saved_access(self):return access
            def _static_crypted_state_fast(self):return access
            def _is_crypted(self):return access
            def _sat_tuner_state(self):return self.tuner_state
            def _read_pts(self):return None
            def _log(self,key,msg):self.log.append(key)
            def _instant_mapped_enabled(self):return True
            def _encrypted_fallback_allowed_once(self):return old_gate
            def _on_tune_failed(self,event=None):return "deferred"
            def _fallback_if_matched(self):
                self._fallback_calls+=1
                return "IPTV"
        return attach_monitor(Fake)()

    def test_default_behavior_unmodified(self):
        f=self.monitor(policy=False)
        self.assertTrue(f._instant_mapped_enabled())
        self.assertFalse(f._encrypted_fallback_allowed_once())

    def test_explicit_clear_tune_failure_allows(self):
        f=self.monitor(access=False,tuner="FAILED")
        self.assertFalse(f._instant_mapped_enabled())
        self.assertTrue(f._encrypted_fallback_allowed_once())
        self.assertEqual(f._fallback_if_matched(),"IPTV")
        self.assertEqual(f._fallback_calls,1)

    def test_healthy_clear_locked_keeps_sat_even_with_override(self):
        f=self.monitor(access=False,tuner="LOCKED")
        self.assertFalse(f._instant_mapped_enabled())
        self.assertFalse(f._encrypted_fallback_allowed_once())
        self.assertIsNone(f._fallback_if_matched())
        self.assertEqual(f._fallback_calls,0)

    def test_clear_manual_mapping_cannot_override_healthy_sat(self):
        f=self.monitor(access=False,tuner='LOCKED',old_gate=True)
        self.assertFalse(f._instant_mapped_enabled())
        self.assertFalse(f._encrypted_fallback_allowed_once())
        self.assertIsNone(f._fallback_if_matched())
        self.assertEqual(f._fallback_calls,0)

    def test_encrypted_existing_fast_path(self):
        f=self.monitor(access=True,tuner="LOCKED",old_gate=True)
        self.assertTrue(f._instant_mapped_enabled())
        self.assertTrue(f._encrypted_fallback_allowed_once())
        self.assertEqual(f._fallback_if_matched(),"IPTV")

    def test_unknown_access_no_auto_reclassification(self):
        f=self.monitor(access=None,tuner="FAILED")
        self.assertTrue(f._instant_mapped_enabled())
        self.assertFalse(f._encrypted_fallback_allowed_once())

    def test_native_tune_failed_ref_remembered_deferred(self):
        f=self.monitor(access=False,tuner="?")
        self.assertEqual(f._on_tune_failed("evTuneFailed"),"deferred")
        self.assertEqual(f._r70_fta_event_ref,"sat-1")
        self.assertTrue(f._encrypted_fallback_allowed_once())
        f.tuner_state="LOCKED"
        self.assertIsNone(f._fallback_if_matched())
        self.assertEqual(f._fallback_calls,0)

    def test_video_event_cancels_even_after_tune_failure(self):
        f=self.monitor(access=False,tuner="FAILED")
        f.video_event_seen=True
        self.assertFalse(f._encrypted_fallback_allowed_once())
        self.assertIsNone(f._fallback_if_matched())

    def test_access_cache_avoids_repeated_lamedb_lookup(self):
        f=self.monitor(access=False,tuner="FAILED")
        counts=[0]
        def static():
            counts[0]+=1
            return False
        f._static_crypted_state_fast=static
        self.assertFalse(f._instant_mapped_enabled())
        self.assertTrue(f._encrypted_fallback_allowed_once())
        self.assertEqual(f._fallback_if_matched(),"IPTV")
        self.assertEqual(counts[0],1)
        f.current_sat_started_at-=5  # next SAT service/decision cycle
        self.assertFalse(f._instant_mapped_enabled())
        self.assertEqual(counts[0],2)

    def test_no_callbacks_replaced_on_double_attach(self):
        f=self.monitor()
        wrapped=type(f)._fallback_if_matched
        attach_monitor(type(f))
        self.assertIs(type(f)._fallback_if_matched,wrapped)


class SettingsPreviewTests(unittest.TestCase):
    def namespace(self):
        class Value:
            def __init__(self,default=False):
                self.value=default
                self.default=default
        class Settings:
            HELP={}
            def __init__(self,section="all"):
                self.section=section
                self.list=[]
                self.controls={"config":SimpleNamespace(setList=lambda rows:None)}
            def __getitem__(self,k):return self.controls[k]
            def _build_list(self):
                self.list=[("Fallback when SAT has no signal",None)]
                return "base"
        class Preview:
            def __init__(self):
                self.controls={"detail":SimpleNamespace(setText=lambda s:None)}
            def __getitem__(self,k):return self.controls[k]
            def _ensure_full_sat_rows(self):return True
        originals=[{"ref":"1", "name":"Encrypted","crypted":True}]
        available=[
            {"ref":"1","name":"Encrypted","crypted":True,"orbital_position":7},
            {"ref":"2","name":"Clear","crypted":None,"orbital_position":7},
            {"ref":"3","name":"Other sat","crypted":None,"orbital_position":13},
            {"ref":"4","name":"Unknown access","crypted":None,"orbital_position":7},
        ]
        ns={
            "ConfigYesNo":Value,
            "cfg":SimpleNamespace(),
            "SatIPTVBridgeSettings":Settings,
            "SatIPTVBridgePreview":Preview,
            "getConfigListEntry":lambda title,config:(title,config),
            "_preview_sat_service_rows":lambda sess,ref:originals,
            "_lamedb_tv_service_rows":lambda:available,
            "_lamedb_access_states":lambda:{"2":False},
            "_sat_orbital_position":lambda ref:7,
            "_dvb_service_key":lambda ref:ref,
        }
        return ns

    def test_opt_in_settings_default_false_and_preview_all(self):
        ns=self.namespace()
        self.assertTrue(attach_plugin(ns))
        self.assertFalse(ns["cfg"].fta_no_signal.value)
        x=ns["SatIPTVBridgeSettings"]()
        x._build_list()
        self.assertEqual(len(x.list),2)
        self.assertEqual(len(ns["_preview_sat_service_rows"](None,"sat")),1)
        ns["cfg"].fta_no_signal.value=True
        rows=ns["_preview_sat_service_rows"](None,"sat")
        self.assertEqual({x["ref"] for x in rows},{"1","2","4"})
        self.assertEqual(next(r for r in rows if r["ref"]=="2")["crypted"],False)
        self.assertIsNone(next(r for r in rows if r["ref"]=="4")["crypted"])

if __name__=="__main__":
    unittest.main()
