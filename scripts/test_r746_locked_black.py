#!/usr/bin/env python3
"""R74.6: actual-IPK regressions for DMAX/TLC locked DVB but black picture."""
import ast
import importlib.util
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r746build",ROOT/"scripts/build-r74-unified.py")
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)

class Timer:
    def __init__(self):
        self.callback=[]
        self.starts=[]
    def start(self,ms,once=True):
        self.starts.append(ms)
    def stop(self):
        pass

class LockedBlackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        dest=Path(cls.tmp.name)/"r746.ipk"
        cls.meta=builder.build(dest)
        contents=builder.b.b.base.pack.members_from(builder.b.b.base.pack.unpack_ar(dest.read_bytes())["data.tar.gz"])
        cls.src=contents[builder.MONITOR].decode()
        tree=ast.parse(cls.src)
        classes=[x for x in tree.body if isinstance(x,ast.ClassDef)
             and any(isinstance(n,ast.FunctionDef) and n.name=="_r746_stable_black" for n in x.body)]
        assert len(classes)==1
        cls.methods={n.name:n for n in classes[0].body if isinstance(n,ast.FunctionDef)}
    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.ref="1:0:19:152E:455:1:C00000:0:0:0:"  # DMAX HD Austria
        self.logs=[]
        self.fallback=[]
        self.pts=None
        self.state="LOCKED"
        self.pmt=250
        self.m=SimpleNamespace(
            current_sat_ref_string=self.ref,
            current_sat_started_at=time.time()-2.08,
            current_sat_name="DMAX HD Austria",
            tuner_state="LOCKED",
            video_event_seen=False,
            fallback_active=False,
            switch_in_progress=False,
            crypted_state="?",
            _fallback_crypto_gate=None,
            _r746_first_pts=None,
            cfg=SimpleNamespace(enabled=SimpleNamespace(value=True),
                fallback_no_signal=SimpleNamespace(value=True),
                only_crypted=SimpleNamespace(value=True)),
        )
        self.m._same_sat_still_playing=lambda:self.m.current_sat_ref_string==self.ref
        self.m._sat_tuner_state=lambda:self.state
        self.m._sat_pmt_pid=lambda:self.pmt
        self.m._is_crypted=lambda:False
        self.m._static_crypted_state_fast=lambda:False
        self.m._read_pts=lambda:self.pts
        self.m._log=lambda *args:self.logs.append(args)
        self.m._fallback_with_native_pat_guard=lambda:self.fallback.append("IPTV_REQUEST")
        env={"time":time,"eTimer":Timer}
        for name in ("_r746_token","_r746_native_picture","_r746_take_sample",
                     "_r746_arm_video_sample","_r746_black_active","_r746_stable_black",
                     "_r744_access_check"):
            node=self.methods[name]
            exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),name,"exec"),env)
            setattr(self.m,name,lambda *args,_fn=env[name]:_fn(self.m,*args))

    def _sample(self):
        self.m._r746_sample_token=self.m._r746_token()
        self.m._r746_take_sample()
        self.m._r744_access_ref=self.m._r746_token()

    def test_dmax_locked_without_video_automatically_requests_iptv_at_two_seconds(self):
        self._sample()
        self.m._r744_access_check()
        self.assertEqual(self.fallback,["IPTV_REQUEST"])
        self.assertTrue(self.m._r746_black_active())
        self.assertIn("DVB_BLACK_FALLBACK",str(self.logs))

    def test_tlc_locked_no_video_also_requests_iptv_with_no_prior_tp_cache(self):
        self.m.current_sat_name="TLC HD Austria"
        self._sample()
        self.m._r744_access_check()
        self.assertEqual(self.fallback,["IPTV_REQUEST"])

    def test_working_fta_video_event_stays_sat(self):
        self._sample()
        self.m.video_event_seen=True
        self.m._r744_access_check()
        self.assertEqual(self.fallback,[])
        self.assertEqual(self.m.crypted_state,"NO")

    def test_new_decoder_pts_after_sample_keeps_sat(self):
        self._sample()
        self.pts=90000
        self.m._r744_access_check()
        self.assertEqual(self.fallback,[])
        self.assertEqual(self.m.crypted_state,"NO")

    def test_moving_pts_with_two_samples_keeps_sat(self):
        self.pts=90000
        self._sample()
        self.pts=135000
        self.m._r744_access_check()
        self.assertEqual(self.fallback,[])

    def test_nonmoving_decoder_pts_is_black_without_video_event(self):
        self.pts=90000
        self._sample()
        self.m._r744_access_check()
        self.assertEqual(self.fallback,["IPTV_REQUEST"])

    def test_no_fallback_at_900ms_before_safe_black_grace(self):
        self.m.current_sat_started_at=time.time()-0.9
        self._sample()
        self.assertFalse(self.m._r746_stable_black())

    def test_stale_video_sample_from_previous_zap_is_ignored(self):
        self._sample()
        self.m.current_sat_started_at=time.time()-2.1
        self.assertFalse(self.m._r746_stable_black())

    def test_sample_timer_does_not_block_frontend(self):
        self.m._r746_arm_video_sample()
        self.assertEqual(self.m._r746_sample_timer.starts,[850])

    def test_2s_fta_to_crypto_logic_remains(self):
        self._sample()
        self.m._is_crypted=lambda:True
        self.m._r744_access_check()
        self.assertEqual(self.fallback,["IPTV_REQUEST"])
        self.assertIn("CRYPT_AFTER_2S",str(self.logs))

    def test_runtime_has_black_protection_at_crypt_gate_and_pmtsafety(self):
        self.assertIn("DVB_BLACK_ALLOW",self.src)
        self.assertIn("DVB_LOCK_NO_VIDEO",self.src)
        self.assertIn("DVB_VIDEO_SAMPLE",self.src)
        self.assertIn("DVB_BLACK_CANCEL",self.src)
        self.assertIn("NATIVE_PAT_GUARD_MS = 1250",self.src)
        self.assertTrue(self.meta["monitor_black_decision"])
        self.assertFalse(self.meta["receiver_tested"])

if __name__=="__main__":
    unittest.main()
