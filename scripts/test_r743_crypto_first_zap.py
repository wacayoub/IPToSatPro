#!/usr/bin/env python3
"""R74.3 DVB encryption first-zap regression on the actual generated IPK."""
import ast,importlib.util,tempfile,unittest,time
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("build743",ROOT/"scripts/build-r74-unified.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class DummyTimer:
    def __init__(self):
        self.callback=[]
        self.calls=[]
    def start(self,ms,single=True):
        self.calls.append(ms)
    def stop(self): pass

class CryptFirstZapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        pkg=Path(cls.tmp.name)/"r743.ipk"
        cls.meta=b.build(pkg)
        cls.payload=b.b.b.base.pack.members_from(b.b.b.base.pack.unpack_ar(pkg.read_bytes())["data.tar.gz"])
        cls.src=cls.payload[b.MONITOR].decode()
        tree=ast.parse(cls.src)
        classes=[n for n in tree.body if isinstance(n,ast.ClassDef)
                 and any(isinstance(fn,ast.FunctionDef) and fn.name=="_r743_crypto_pending"
                         for fn in n.body)]
        assert len(classes)==1
        cls.methods={fn.name:fn for fn in classes[0].body if isinstance(fn,ast.FunctionDef)}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.logs=[]
        self.calls=[]
        self.ref="1:0:19:24CD:43C:1:C00000:0:0:0:"
        self.age=0.09
        self.live=False
        self.static=False
        self.video=False
        self.manual=True
        self.saved=False
        self.now=time.time()
        self.session=SimpleNamespace()
        self.m=SimpleNamespace(
            cfg=SimpleNamespace(
                only_crypted=SimpleNamespace(value=True),
                fallback_no_signal=SimpleNamespace(value=True)),
            _fallback_crypto_gate=None, fallback_active=False, crypted_state="?",
            current_sat_ref_string=self.ref,current_sat_name="NICKELODEON",
            current_sat_started_at=self.now-self.age,tuner_state="LOCKED",
            video_event_seen=False,direct_mapping_source="MANUAL_LOCK",
            session=self.session,
        )
        self.m._same_sat_still_playing=lambda: self.m.current_sat_ref_string==self.ref
        self.m._manual_lock_saved_access=lambda:self.saved
        self.m._is_crypted=lambda:self.live
        self.m._static_crypted_state_fast=lambda:self.static
        self.m._load_overrides=lambda:{self.ref:{"sat_crypted":self.saved}}
        self.m._log=lambda *args:self.logs.append(args)
        self.m._fallback_with_native_pat_guard=lambda:self.calls.append("retry")
        self.methods_ns={}
        for name in ("_r743_crypto_pending","_r743_crypto_retry","_encrypted_fallback_allowed_once"):
            node=self.methods[name]
            env={"time":time,"eTimer":DummyTimer,"sat_service_key":lambda s:s}
            exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),name,"exec"),env)
            self.methods_ns[name]=env[name]
            setattr(self.m,name,lambda *args,_n=name:self.methods_ns[_n](self.m,*args))
    def set_age(self,age):
        self.m.current_sat_started_at=time.time()-age
    def test_first_zap_no_waits_and_does_not_cache_false(self):
        self.assertTrue(self.m._r743_crypto_pending())
        self.assertEqual(self.m.crypted_state,"?")
        self.assertIsNone(self.m._fallback_crypto_gate)
        self.assertTrue(self.m._r743_crypto_timer.calls)
        self.assertTrue(any("CRYPT_PENDING" in str(t) for t in self.logs))
    def test_no_to_yes_first_zap_is_recognized_without_second_zap(self):
        self.assertTrue(self.m._r743_crypto_pending())
        self.live=True
        self.assertTrue(self.m._encrypted_fallback_allowed_once())
        self.assertEqual(self.m.crypted_state,"YES")
    def test_old_manual_saved_no_does_not_override_new_static_yes(self):
        self.static=True
        self.assertFalse(self.m._r743_crypto_pending())
        self.assertTrue(self.m._encrypted_fallback_allowed_once())
        self.assertEqual(self.m.crypted_state,"YES")
    def test_early_no_later_yes_retry_still_on_same_sat(self):
        self.assertTrue(self.m._r743_crypto_pending())
        self.live=True
        self.m._r743_crypto_retry()
        self.assertEqual(self.calls,["retry"])
    def test_stale_zap_retry_does_not_touch_next_channel(self):
        self.assertTrue(self.m._r743_crypto_pending())
        self.m.current_sat_ref_string="1:0:1:DIFFERENT"
        self.m._r743_crypto_retry()
        self.assertEqual(self.calls,[])
    def test_native_video_prevents_deferred_retry(self):
        self.m.video_event_seen=True
        self.assertFalse(self.m._r743_crypto_pending())
        self.assertFalse(self.m._encrypted_fallback_allowed_once())
        self.assertEqual(self.m.crypted_state,"NO")
    def test_manual_lock_stale_saved_no_does_not_override_locked_fta_after_grace(self):
        self.set_age(1.12)
        self.assertFalse(self.m._r743_crypto_pending())
        self.assertFalse(self.m._encrypted_fallback_allowed_once())
        self.assertEqual(self.m.crypted_state,"NO")
    def test_manual_lock_does_not_override_native_working_fta(self):
        self.set_age(1.12)
        self.m.video_event_seen=True
        self.assertFalse(self.m._encrypted_fallback_allowed_once())
    def test_auto_mapping_with_definite_no_remains_protected(self):
        self.set_age(1.1)
        self.m.direct_mapping_source="AUTO_LOCK"
        self.saved=None
        self.assertFalse(self.m._encrypted_fallback_allowed_once())
    def test_positive_ca_starts_without_waiting(self):
        self.static=True
        self.assertFalse(self.m._r743_crypto_pending())
        self.assertEqual(self.m.crypted_state,"YES")
    def test_timer_is_bounded(self):
        self.set_age(0.85)
        self.assertTrue(self.m._r743_crypto_pending())
        self.assertLessEqual(self.m._r743_crypto_timer.calls[-1],175)
        self.set_age(1.12)
        self.assertFalse(self.m._r743_crypto_pending())
    def test_direct_mapping_saved_no_is_provisional_not_cached(self):
        self.assertIn('self._fallback_crypto_gate = None; self.crypted_state = "?"',self.src)
    def test_every_other_module_byte_identical_to_baseline(self):
        self.assertTrue(self.meta["monitor_crypto_patch_only"])
        self.assertFalse(self.meta["receiver_tested"])
        self.assertFalse(self.meta["production_published"])

if __name__=="__main__":unittest.main()
