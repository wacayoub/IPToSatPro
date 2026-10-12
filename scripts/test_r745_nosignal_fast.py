#!/usr/bin/env python3
"""R74.5 fast No Signal behavioral tests against the built receiver IPK."""
import ast,importlib.util,tempfile,unittest,time
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r745build",ROOT/"scripts/build-r74-unified.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class FakeTimer:
    def __init__(self):self.callback=[];self.started=[]
    def start(self,ms,once=True):self.started.append(ms)
    def stop(self):pass

class NoSignalFastTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        output=Path(cls.tmp.name)/"r745.ipk"
        cls.meta=b.build(output)
        members=b.b.b.base.pack.members_from(b.b.b.base.pack.unpack_ar(output.read_bytes())["data.tar.gz"])
        cls.source=members[b.MONITOR].decode()
        tree=ast.parse(cls.source)
        classes=[n for n in tree.body if isinstance(n,ast.ClassDef) and
                 any(isinstance(m,ast.FunctionDef) and m.name=="_r745_cached_probe" for m in n.body)]
        assert len(classes)==1
        cls.methods={n.name:n for n in classes[0].body if isinstance(n,ast.FunctionDef)}
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def setUp(self):
        self.ref="1:0:19:24CD:43C:1:C00000:0:0:0:"
        self.nextref="1:0:19:2715:43C:1:C00000:0:0:0:"
        self.other_tp_ref="1:0:19:24CD:55C:1:D00000:0:0:0:"
        self.frontend="TUNING"
        self.pmt=0
        self.logs=[]
        self.play_calls=[]
        self.m=SimpleNamespace(
            current_sat_ref_string=self.ref,
            current_sat_started_at=time.time()-0.04,
            current_sat_name="NICKELODEON",
            fallback_active=False,switch_in_progress=False,
            video_event_seen=False,failure_cooldown_sat="",
            failure_cooldown_until=0,
            cfg=SimpleNamespace(enabled=SimpleNamespace(value=True),
                only_crypted=SimpleNamespace(value=True),
                fallback_no_signal=SimpleNamespace(value=True)),
        )
        self.m._r746_black_active=lambda:False
        self.m._r746_stable_black=lambda:False
        self.m._r746_native_picture=lambda:bool(self.m.video_event_seen)
        self.m._same_sat_still_playing=lambda:self.m.current_sat_ref_string in (self.ref,self.nextref,self.other_tp_ref)
        self.m._sat_tuner_state=lambda:self.frontend
        self.m._sat_pmt_pid=lambda:self.pmt
        self.m._fallback_with_native_pat_guard=lambda:self.play_calls.append("PENDING_IPTV")
        self.m._log=lambda *a:self.logs.append(a)
        env={"time":time,"eTimer":FakeTimer}
        for name in (
            "_r745_tp_key","_r745_confirm_no_signal","_r745_cached_failure_active",
            "_r745_discard_bad_tp","_r745_no_signal_once",
            "_r745_arm_cached_nosignal","_r745_cached_probe"):
            node=self.methods[name]
            exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),
                         "actual-r745-ipk-"+name,"exec"),env)
            setattr(self.m,name,lambda *args,_fn=env[name]:_fn(self.m,*args))

    def _proof(self):
        self.m._r745_confirm_no_signal()

    def _fast_two_probes(self):
        self.m._r745_arm_cached_nosignal()
        self.assertEqual(self.m._r745_probe_timer.started,[180])
        self.m._r745_cached_probe()
        self.assertEqual(self.m._r745_probe_timer.started,[180,250])
        self.m._r745_cached_probe()

    def test_confirmed_native_failure_cached_in_ram(self):
        self._proof()
        self.assertEqual(len(self.m._r745_bad_transponders),1)
        self.assertIn("NO_SIGNAL_PROVEN",str(self.logs))

    def test_previous_failed_tp_next_visit_starts_fallback_after_430ms(self):
        self._proof()
        self.m.current_sat_started_at=time.time()
        self._fast_two_probes()
        self.assertEqual(self.play_calls,["PENDING_IPTV"])
        self.assertTrue(self.m._r745_cached_failure_active())
        self.assertIn("NO_SIGNAL_FAST_TRY",str(self.logs))

    def test_same_transport_works_for_other_channel(self):
        self._proof()
        self.m.current_sat_ref_string=self.nextref
        self.m.current_sat_started_at=time.time()
        self._fast_two_probes()
        self.assertEqual(self.play_calls,["PENDING_IPTV"])

    def test_other_transponder_cannot_reuse_false_no_signal(self):
        self._proof()
        self.m.current_sat_ref_string=self.other_tp_ref
        self.m.current_sat_started_at=time.time()
        self.m._r745_arm_cached_nosignal()
        self.assertFalse(hasattr(self.m,"_r745_probe_timer"))
        self.assertEqual(self.play_calls,[])

    def test_first_ever_no_signal_cannot_use_unproven_shortcut(self):
        self.m._r745_arm_cached_nosignal()
        self.assertFalse(hasattr(self.m,"_r745_probe_timer"))

    def test_expired_proof_cannot_start_iptv(self):
        self._proof()
        key=self.m._r745_tp_key()
        self.m._r745_bad_transponders[key]=time.time()-121
        self.m._r745_arm_cached_nosignal()
        self.assertEqual(self.play_calls,[])
        self.assertNotIn(key,self.m._r745_bad_transponders)

    def test_native_lock_alone_does_not_clear_cached_no_signal(self):
        self._proof()
        self.m._r745_arm_cached_nosignal()
        self.frontend="LOCKED"
        self.m._r745_cached_probe()
        self.assertEqual(self.play_calls,[])
        self.assertTrue(self.m._r745_bad_transponders)
        self.assertIn("DVB_LOCK_NO_VIDEO",str(self.logs))

    def test_pmt_ready_alone_does_not_clear_cache(self):
        self._proof()
        self.m._r745_arm_cached_nosignal()
        self.pmt=260
        self.m._r745_cached_probe()
        self.assertEqual(self.play_calls,[])
        self.assertTrue(self.m._r745_bad_transponders)

    def test_no_frontend_state_never_guesses_no_signal_from_zero_snr(self):
        self._proof()
        self.m._r745_arm_cached_nosignal()
        self.frontend="?"
        self.m._r745_cached_probe()
        self.assertEqual(self.play_calls,[])

    def test_video_present_does_not_switch(self):
        self._proof()
        self.m._r745_arm_cached_nosignal()
        self.m.video_event_seen=True
        self.m._r745_cached_probe()
        self.assertEqual(self.play_calls,[])
        self.assertFalse(self.m._r745_bad_transponders)

    def test_stale_timer_is_ignored_after_user_zap(self):
        self._proof()
        self.m._r745_arm_cached_nosignal()
        self.m.current_sat_ref_string=self.other_tp_ref
        self.m.current_sat_started_at=time.time()
        self.m._r745_cached_probe()
        self.assertEqual(self.play_calls,[])

    def test_repeat_native_tune_failed_event_does_not_retry_every_five_seconds(self):
        self.assertTrue(self.m._r745_no_signal_once("NATIVE_TUNE_FAILED"))
        self.assertFalse(self.m._r745_no_signal_once("NATIVE_TUNE_FAILED"))
        self.assertEqual(self.play_calls,["PENDING_IPTV"])
        self.assertIn("NO_SIGNAL_DEDUP",str(self.logs))

    def test_locked_video_prevents_fallback_even_when_cached(self):
        self.m.video_event_seen=True
        self.assertFalse(self.m._r745_no_signal_once("PROVEN_TP_CACHE"))
        self.assertEqual(self.play_calls,[])

    def test_native_pat_pmt_crash_guard_is_preserved(self):
        self.assertIn("NATIVE_PAT_GUARD_MS = 1250",self.source)
        self.assertIn('RECOVERED_DURING_PMTPAT_GUARD',self.source)
        self.assertIn('NO_SIGNAL_CACHE_ALLOW',self.source)
        self.assertTrue(self.meta["monitor_cached_no_signal"])
        self.assertFalse(self.meta["receiver_tested"])

if __name__=="__main__":unittest.main()
