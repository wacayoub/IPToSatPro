#!/usr/bin/env python3
"""R74.4 regression tests on REAL generated IPK, including 2-second FTA->YES."""
import ast,importlib.util,time,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r744build",ROOT/"scripts/build-r74-unified.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class FakeTimer:
    def __init__(self):self.callback=[];self.started=[]
    def start(self,ms,once=True):self.started.append(ms)
    def stop(self):pass

class R744FastSignalPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        pkg=Path(cls.tmp.name)/"r744.ipk"
        cls.meta=b.build(pkg)
        members=b.b.b.base.pack.members_from(b.b.b.base.pack.unpack_ar(pkg.read_bytes())["data.tar.gz"])
        cls.source=members[b.MONITOR].decode()
        tree=ast.parse(cls.source)
        classes=[x for x in tree.body if isinstance(x,ast.ClassDef) and
                 any(isinstance(c,ast.FunctionDef) and c.name=="_r744_access_check" for c in x.body)]
        assert len(classes)==1
        cls.methods={x.name:x for x in classes[0].body if isinstance(x,ast.FunctionDef)}
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def setUp(self):
        self.ref="1:0:19:24CD:43C:1:C00000:0:0:0:"
        self.logs=[];self.played=[];self.live=False;self.static=False
        self.m=SimpleNamespace(
            current_sat_ref_string=self.ref,current_sat_started_at=time.time()-0.1,
            current_sat_name="NICKELODEON", tuner_state="LOCKED",
            video_event_seen=False,fallback_active=False,switch_in_progress=False,
            direct_mapping_source="MANUAL_LOCK",crypted_state="?",
            _fallback_crypto_gate=None,_r744_fta_status_key=None,
            cfg=SimpleNamespace(enabled=SimpleNamespace(value=True),
                only_crypted=SimpleNamespace(value=True),
                fallback_no_signal=SimpleNamespace(value=True)),
        )
        self.m._r745_cached_failure_active=lambda:False
        self.m._same_sat_still_playing=lambda:self.m.current_sat_ref_string==self.ref
        self.m._sat_tuner_state=lambda:self.m.tuner_state
        self.m._is_crypted=lambda:self.live
        self.m._static_crypted_state_fast=lambda:self.static
        self.m._manual_lock_saved_access=lambda:False
        self.m._log=lambda *a:self.logs.append(a)
        self.m._set_state=lambda *a:None
        self.m._native_pat_guard_remaining_ms=lambda:0
        self.m._fallback_if_matched=lambda:self.played.append("IPTV")
        self.m._r743_crypto_pending=lambda:False
        methods=("_r744_arm_access_followup","_r744_access_check",
                 "_fallback_with_native_pat_guard","_encrypted_fallback_allowed_once")
        gl={"time":time,"eTimer":FakeTimer}
        for name in methods:
            node=self.methods[name]
            exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),
                         "r744-real-ipk-"+name,"exec"),gl)
            setattr(self.m,name,lambda *args,_fn=gl[name]:_fn(self.m,*args))
    def aged(self,s=2.1):
        self.m.current_sat_started_at=time.time()-s

    def test_two_second_timer_is_armed_without_waiting_for_sat(self):
        self.m._r744_arm_access_followup()
        self.assertEqual(self.m._r744_access_timer.started,[2000])
        self.assertIn("CRYPT_2S_ARM",str(self.logs))

    def test_locked_fta_keeps_sat_initially_and_after_two_seconds(self):
        self.m._r744_arm_access_followup()
        self.m._fallback_with_native_pat_guard()
        self.assertEqual(self.played,[])
        self.assertEqual(self.m.crypted_state,"?")
        self.aged(2.1)
        self.m._r744_access_ref=(self.ref,self.m.current_sat_started_at)
        self.m._r744_access_check()
        self.assertEqual(self.played,[])
        self.assertEqual(self.m.crypted_state,"NO")
        self.assertIn("SIGNAL_FTA_KEEP_SAT",str(self.logs))

    def test_first_fta_later_encrypted_triggers_iptv_with_no_second_zap(self):
        self.m._r744_arm_access_followup()
        self.m._fallback_with_native_pat_guard()
        self.assertEqual(self.played,[])
        self.live=True
        self.aged(2.01)
        self.m._r744_access_ref=(self.ref,self.m.current_sat_started_at)
        self.m._r744_access_check()
        self.assertEqual(self.played,["IPTV"])
        self.assertEqual(self.m.crypted_state,"YES")
        self.assertIn("CRYPT_AFTER_2S",str(self.logs))

    def test_signal_and_crypted_opens_without_wait(self):
        self.live=True
        self.m._fallback_with_native_pat_guard()
        self.assertEqual(self.played,["IPTV"])
        self.assertIn("FAST_SIGNAL_CRYPTED",str(self.logs))

    def test_static_positive_caids_open_while_live_false(self):
        self.static=True
        self.m._fallback_with_native_pat_guard()
        self.assertEqual(self.played,["IPTV"])

    def test_no_signal_fta_bypasses_crypto_wait(self):
        self.m.tuner_state="TUNE_FAILED"
        self.m._r743_crypto_pending=lambda:(_ for _ in ()).throw(AssertionError("CRYPTO_WAIT_ON_NO_SIGNAL"))
        self.m._fallback_with_native_pat_guard()
        self.assertEqual(self.played,["IPTV"])
        self.assertIn("FAST_NO_SIGNAL",str(self.logs))

    def test_no_signal_encrypted_opens(self):
        self.m.tuner_state="NO_LOCK"
        self.live=True
        self.m._fallback_with_native_pat_guard()
        self.assertEqual(self.played,["IPTV"])

    def test_tuning_is_not_incorrectly_classed_as_no_signal(self):
        self.m.tuner_state="TUNING"
        self.m._r743_crypto_pending=lambda:True
        self.m._fallback_with_native_pat_guard()
        self.assertEqual(self.played,[])
        self.assertNotIn("FAST_NO_SIGNAL",str(self.logs))

    def test_fta_signal_keeps_sat_even_when_only_crypted_setting_off(self):
        self.m.cfg.only_crypted.value=False
        self.m._fallback_with_native_pat_guard()
        self.assertEqual(self.played,[])

    def test_second_zap_token_invalidates_first_zap_recheck(self):
        self.m._r744_arm_access_followup()
        self.m.current_sat_ref_string="1:0:1:OTHER"
        self.live=True
        self.m._r744_access_check()
        self.assertEqual(self.played,[])

    def test_active_iptv_prohibits_duplicate_switch(self):
        self.m._r744_arm_access_followup()
        self.m.fallback_active=True
        self.live=True
        self.m._r744_access_check()
        self.assertEqual(self.played,[])

    def test_ftacheck_unknown_keeps_sat(self):
        self.m._r744_arm_access_followup()
        self.live=None;self.static=None
        self.aged(2.1)
        self.m._r744_access_ref=(self.ref,self.m.current_sat_started_at)
        self.m._r744_access_check()
        self.assertEqual(self.played,[])
        self.assertIn("CRYPT_UNKNOWN_2S",str(self.logs))

    def test_confirmed_no_signal_on_recheck_opens_any_access(self):
        self.m._r744_arm_access_followup()
        self.m.tuner_state="NO_SIGNAL"
        self.m._r744_access_check()
        self.assertEqual(self.played,["IPTV"])

    def test_no_snr_zero_heuristic_or_fuzzy_score_required(self):
        self.assertIn('timer.start(2000,True)',self.source)
        self.assertIn('CRYPT_AFTER_2S',self.source)
        self.assertIn('SIGNAL_FTA_KEEP_SAT',self.source)
        self.assertIn('FAST_NO_SIGNAL',self.source)
        self.assertTrue(self.meta["monitor_fast_signal_policy"])
        self.assertFalse(self.meta["receiver_tested"])

if __name__=="__main__":unittest.main()
