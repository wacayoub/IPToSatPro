#!/usr/bin/env python3
"""R72.4 0%-SAT failover, original FTA protections, native callback and Fast Lock guard."""
import ast,base64,hashlib,importlib.util,tempfile,types,unittest
from pathlib import Path
sp=importlib.util.spec_from_file_location("r724",Path(__file__).with_name("build-r724-zero-signal.py"))
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)

class Settings:
    def __init__(self,enabled):self.value=enabled
class Dummy:
    def __init__(self,state,crypto=False,static=False,same=True,flag=True,only_crypted=True,
                 fallback=False,locked=False,cache=None):
        self.tuner_state=state
        self.cfg=types.SimpleNamespace(fallback_no_signal=Settings(flag),
          only_crypted=Settings(only_crypted))
        self.fallback_active=fallback
        self.current_sat_ref_string="1:0:19:ABCD:13:2:130000:0:0:0:"
        self.current_sat_name="beIN MOVIES TURK"
        self._fallback_crypto_gate=cache
        self.direct_mapping_source="MANUAL_LOCK" if locked else "AUTO"
        self.crypted_state="?"
        self.crypto=crypto;self.static=static;self.same=same
        self.entries=[]
    def _same_sat_still_playing(self):return self.same
    def _log(self,what,details):self.entries.append((what,details))
    def _manual_lock_saved_access(self):return None
    def _is_crypted(self):return self.crypto
    def _static_crypted_state_fast(self):return self.static
    def _load_overrides(self):return {}
    def _sat_tuner_state(self):return self.tuner_state

class SignalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.temp.name)/"test-r724.ipk"
        cls.meta=b.build(cls.path)
        cls.now=b.pack.members_from(b.pack.unpack_ar(cls.path.read_bytes())["data.tar.gz"])
        cls.baseline=b.pack.members_from(b.pack.unpack_ar(base64.b64decode(b.BASE.read_bytes()))["data.tar.gz"])
        code=cls.now[b.MONITOR].decode()
        cls.tree=ast.parse(code)
        original=next(x for x in cls.tree.body if isinstance(x,ast.ClassDef) and x.name=="SatFallbackMonitor")
        func=next(x for x in original.body if isinstance(x,ast.FunctionDef) and x.name=="_encrypted_fallback_allowed_once")
        # Isolate and execute the exact shipped code, no duplicated behavior.
        method=ast.Module(body=[func],type_ignores=[])
        ast.fix_missing_locations(method)
        ns={"sat_service_key":lambda r:r,"bool":bool}
        exec(compile(method,"r724_real_monitor.py","exec"),ns)
        cls.gate=ns[func.name]
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def check(self,state,expected,**kw):
        d=Dummy(state,**kw)
        self.assertIs(self.gate(d),expected,(state,kw,d.entries))
        return d

    def test_failed_tuner_allows_fta_and_encrypted(self):
        for state in ("TUNE_FAILED","FAILED","NO_SIGNAL","NO_LOCK","NOT_LOCKED","UNLOCKED"):
            with self.subTest(state=state):
                obj=self.check(state,True,crypto=False,static=False)
                self.assertEqual(obj.entries[0][0],"NO_SIGNAL_FTA_IPTV_ALLOWED")
                self.assertEqual(obj.crypted_state,"?")
                self.assertTrue(obj._fallback_crypto_gate)
        for name in ("beIN MOVIES TURK","CANAL+","Ushuaia","2M","AlAoula","NatGeo","MBC 1","Dubai Sports","Rotana","TF1"):
            obj=Dummy("TUNE_FAILED")
            obj.current_sat_name=name
            with self.subTest(name=name):
                self.assertTrue(self.gate(obj))
                self.assertIn(name,obj.entries[0][1])

    def test_healthy_and_unknown_sat_fences_remain_active(self):
        for state in ("LOCKED","TUNING","ACQUIRING","SEARCHING","?","UNKNOWN",""):
            with self.subTest(state=state):
                obj=self.check(state,False,crypto=False,static=False)
                self.assertFalse(any(x[0]=="NO_SIGNAL_FTA_IPTV_ALLOWED" for x in obj.entries))
        self.check("LOCKED",True,crypto=True,static=False)
        self.check("LOCKED",True,crypto=False,static=True)

    def test_no_signal_disabled_wrong_channel_or_active_fallback_blocked(self):
        self.check("TUNE_FAILED",False,flag=False,crypto=False,static=False)
        self.check("TUNE_FAILED",False,same=False,crypto=False,static=False)
        self.check("TUNE_FAILED",False,fallback=True,crypto=False,static=False)
        self.check("UNLOCKED",False,same=False,crypto=False,static=False)
        self.check("LOCKED",False,crypto=False,static=False,locked=False)
        # FTA on available tuner must stay on SAT even if SNR telemetry is 0.
        self.check("LOCKED",False,crypto=False,static=False)

    def test_cached_negative_crypto_does_not_block_proven_failed_tuner(self):
        obj=self.check("TUNE_FAILED",True,cache=False,static=False,crypto=False)
        self.assertTrue(obj._fallback_crypto_gate)
        obj=self.check("LOCKED",False,cache=False,static=False,crypto=True)
        self.assertEqual(obj.entries,[])

    def test_no_native_pat_event_or_playback_logic_changed(self):
        a=ast.parse(self.baseline[b.MONITOR])
        old=next(x for x in a.body if isinstance(x,ast.ClassDef) and x.name=="SatFallbackMonitor")
        now=next(x for x in self.tree.body if isinstance(x,ast.ClassDef) and x.name=="SatFallbackMonitor")
        before={x.name:ast.dump(x,include_attributes=False) for x in old.body if isinstance(x,ast.FunctionDef)}
        after={x.name:ast.dump(x,include_attributes=False) for x in now.body if isinstance(x,ast.FunctionDef)}
        self.assertEqual(set(before),set(after))
        self.assertEqual({name for name in before if before[name]!=after[name]},
                         {"_encrypted_fallback_allowed_once"})
        for method in ("_on_start","_on_tune_failed","_deferred_tune_failed_fallback",
                       "_native_pat_guard_remaining_ms","_fallback_with_native_pat_guard",
                       "_native_pat_guard_fire","_play_match","_fallback_if_matched"):
            self.assertEqual(before[method],after[method],method)
        self.assertEqual(set(self.now),set(self.baseline)|{b.CHANGELOG})
        for path,data in self.baseline.items():
            if path not in (b.PLUGIN,b.UPDATER,b.MONITOR):
                self.assertEqual(data,self.now[path],path)
        self.assertFalse(self.meta["player_changed"])

    def test_deterministic_reproducible_and_main_update_is_still_r70(self):
        other=Path(self.temp.name)/"again.ipk"
        info=b.build(other)
        self.assertEqual(other.read_bytes(),self.path.read_bytes())
        self.assertEqual(info["sha256"],hashlib.sha256(other.read_bytes()).hexdigest())
        import json
        self.assertEqual(json.loads((b.ROOT/"update.json").read_text())["version"],"1.0.46-r70-final")
        self.assertFalse(info["field_tested"])
        self.assertFalse(info["published_to_main"])

if __name__=="__main__":unittest.main()
