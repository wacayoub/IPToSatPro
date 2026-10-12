"""R7417 native DVB FTA signal protection tests on actual R74 built monitor.

Simulate FTA LOCKED, signal failure, genuine native video, encrypted FTA-looking
CA transitions, cached no-signal, untrusted saved manual IPTV mapping, and
safe rollback. No receiver/streams/files modified by test.
"""
import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]


def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/filename)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder=load("r74build7417","build-r74-unified.py")
patcher=load("r7417patch","r7417_fta_signal_native_guard.py")
aac=load("r74aac7417","r74_tod_bein_audio_hotfix.py")


class MonitorFTARegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        path=Path(cls.temp.name)/"r74.ipk"
        builder.build(path)
        pack=builder.b.b.base.pack
        payload=pack.members_from(pack.unpack_ar(path.read_bytes())["data.tar.gz"])
        cls.original=payload[builder.MONITOR].decode()
        cls.audio_fixed=aac.patch(cls.original)[0]
        cls.updated,cls.status=patcher.patch(cls.audio_fixed)
        cls.tree=ast.parse(cls.updated)
        cls.methods={n.name:n for n in ast.walk(cls.tree) if isinstance(n,ast.FunctionDef)}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def isolate(cls,name,env):
        node=cls.methods[name]
        tree=ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[]))
        namespace=dict(env)
        exec(compile(tree,"r7417_fake_monitor.py","exec"),namespace)
        return namespace[name]

    def fake(self,frontend="LOCKED",memo="LOCKED",live=False,static=False,
             picture=False,fallback=False,manual="MANUAL_LOCK"):
        reasons=[]
        class Fake:
            current_sat_ref_string="1:0:1:AAAA:BBBB:CCCC:DDDD:0:0:0:"
            current_sat_started_at=10.25
            current_sat_name="TEST DVB"
            fallback_active=fallback
            switch_in_progress=False
            native_pat_guard_pending=True
            tuner_state=memo
            video_event_seen=picture
            direct_mapping_source=manual
            play_result=""
            cfg=SimpleNamespace(enabled=SimpleNamespace(value=True),
                                fallback_no_signal=SimpleNamespace(value=True),
                                only_crypted=SimpleNamespace(value=True))
            _fallback_crypto_gate=None
            def _same_sat_still_playing(self):return True
            def _sat_tuner_state(self):return frontend
            def _r746_native_picture(self):return picture
            def _is_crypted(self):return live
            def _static_crypted_state_fast(self):return static
            def _log(self,*args):reasons.append(args)
        obj=Fake()
        obj._r7417_native_keep_reason=self.isolate("_r7417_native_keep_reason",{})
        obj._r7417_keep_sat=self.isolate("_r7417_keep_sat",{})
        # Test functions are unbound methods; bind to instance.
        import types
        obj._r7417_native_keep_reason=types.MethodType(obj._r7417_native_keep_reason,obj)
        obj._r7417_keep_sat=types.MethodType(obj._r7417_keep_sat,obj)
        return obj,reasons

    def test_built_r74_audio_patch_plus_native_guard(self):
        self.assertEqual(self.status,"ready")
        self.assertEqual(patcher.patch(self.updated)[1],"already-installed")
        self.assertIn(aac.TAG,self.updated)
        self.assertIn(patcher.TAG,self.updated)
        self.assertIn("native PAT",self.updated)
        self.assertIn("_r745_cached_probe",self.updated)

    def test_fta_signal_locked_keeps_dvb_even_without_video_pts(self):
        obj,logs=self.fake()
        self.assertEqual(obj._r7417_native_keep_reason(),"FTA_LOCKED")
        self.assertTrue(obj._r7417_keep_sat("TEST"))
        self.assertEqual(obj.play_result,"KEEP SAT")
        self.assertFalse(obj.native_pat_guard_pending)
        self.assertEqual(logs[0][0],"FTA_SIGNAL_KEEP_SAT")

    def test_live_native_picture_wins_even_if_crypted(self):
        for static,live in ((True,True),(True,False),(None,None)):
            obj,logs=self.fake(live=live,static=static,picture=True)
            self.assertEqual(obj._r7417_native_keep_reason(),"NATIVE_PICTURE")
            self.assertTrue(obj._r7417_keep_sat("VIDEO"))

    def test_locked_provisionally_clear_but_positive_caids_allows_fallback(self):
        obj,_=self.fake(static=True,live=False,picture=False)
        self.assertEqual(obj._r7417_native_keep_reason(),"")
        self.assertFalse(obj._r7417_keep_sat("NO PICTURE"))

    def test_actual_encrypted_without_sat_video_allows_fallback(self):
        obj,_=self.fake(live=True,static=True,picture=False)
        self.assertEqual(obj._r7417_native_keep_reason(),"")

    def test_fta_no_signal_eligible_ip_fallback(self):
        for observed,memo in (
            ("TUNE_FAILED","TUNE_FAILED"),("NO_SIGNAL","NO_SIGNAL"),
            ("TUNING","TUNING"),("LOCKED","TUNE_FAILED")):
            obj,_=self.fake(frontend=observed,memo=memo,static=False,live=False)
            self.assertFalse(obj._r7417_keep_sat("NO SIGNAL"),(observed,memo))

    def test_ambiguous_early_crypt_state_no_premature_fta_block(self):
        obj,_=self.fake(live=None,static=None,picture=False)
        self.assertEqual(obj._r7417_native_keep_reason(),"")

    def test_explicit_old_manual_mapping_not_allowed_to_steal_fta(self):
        obj,_=self.fake(live=False,static=False,manual="MANUAL_LOCK")
        self.assertTrue(obj._r7417_keep_sat("MANUAL_PREVENTED"))

    def test_background_start_and_pat_guard_protected(self):
        for method in ("_fallback_with_native_pat_guard",
                       "_native_pat_guard_fire",
                       "_fallback_if_matched",
                       "_play_match",
                       "_r744_access_check"):
            src=ast.get_source_segment(self.updated,self.methods[method])
            self.assertIn("_r7417_keep_sat(",src,method)
        self.assertIn('_r7417_keep_sat("PLAYER_SWITCH")',
                      ast.get_source_segment(self.updated,self.methods["_play_match"]))

    def test_central_guard_prevents_any_fallback_side_effects(self):
        obj,logs=self.fake()
        obj._fallback_if_matched=lambda:logs.append(("SIDE_EFFECT","match"))
        obj._r743_crypto_pending=lambda:logs.append(("SIDE_EFFECT","crypto"))
        obj._fallback_crypto_gate=True
        obj._native_pat_guard_remaining_ms=lambda:0
        obj._set_state=lambda *args:logs.append(("SIDE_EFFECT","setstate"))
        obj._arm_native_pat_poll=lambda *args:logs.append(("SIDE_EFFECT","pat"))
        fn=self.isolate("_fallback_with_native_pat_guard",{})
        fn(obj)
        self.assertEqual(obj.play_result,"KEEP SAT")
        self.assertFalse(any(row[0]=="SIDE_EFFECT" for row in logs))

    def test_player_handover_guard(self):
        obj,logs=self.fake()
        fn=self.isolate("_play_match",{})
        fn(obj,{"name":"WRONG LIVE IPTV","url":"http://example.invalid"},100,retry=False)
        self.assertEqual(obj.play_result,"KEEP SAT")
        self.assertFalse(any(log[0]=="IPTV_OK" for log in logs))

    def test_guard_inert_while_already_fallback_active(self):
        obj,_=self.fake(fallback=True)
        self.assertFalse(obj._r7417_keep_sat("ALREADY_IPTV"))

    def test_check_apply_rollback_preserves_audio_fix(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/"monitor.py"
            target.write_text(self.audio_fixed)
            self.assertEqual(patcher.main(["--check","--target",str(target)]),0)
            self.assertEqual(patcher.main(["--apply","--target",str(target)]),0)
            self.assertEqual(target.read_text(),self.updated)
            self.assertEqual(patcher.main(["--rollback","--target",str(target)]),0)
            self.assertEqual(target.read_text(),self.audio_fixed)


if __name__=="__main__":
    unittest.main()
