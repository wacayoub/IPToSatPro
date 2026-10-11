#!/usr/bin/env python3
"""R72.5 verify released monitor funcs prevent Digi24 infinite fuzzy restarts."""
import ast,base64,hashlib,importlib.util,threading,time,tempfile,types,unittest
from pathlib import Path
sp=importlib.util.spec_from_file_location("r725",Path(__file__).with_name("build-r725-fuzzy.py"))
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)

class Config:
    def __init__(self,v):self.value=v
class Timer:
    def __init__(self):self.calls=[]
    def start(self,ms,single):self.calls.append((ms,single))
class Catalog:
    def __init__(self,gate=None,fast_rows=None,fuzzy_rows=None):
        self.gate=gate or threading.Event()
        self.fast_calls=0
        self.fuzzy_calls=0
        self.fast_rows=fast_rows or []
        self.fuzzy_rows=fuzzy_rows or []
    def fast_rank_matches(self,*a,**kw):
        self.fast_calls+=1
        return list(self.fast_rows)
    def rank_matches(self,*a,**kw):
        self.fuzzy_calls+=1
        self.gate.wait(4)
        return list(self.fuzzy_rows)

class FakeMonitor:
    def __init__(self,catalog=None):
        self.current_sat_ref_string="1:0:1:DIGI24:11:1:170000:0:0:0:"
        self.current_sat_name="Digi 24"
        self.current_match_name="Digi 24"
        self.current_sat_started_at=1697042020
        self.catalog=catalog or Catalog()
        self.sat_context={"market":"RO"}
        self.smartmatch_generation=0
        self.smartmatch_pending=None
        self.smartmatch_result=None
        self.smartmatch_timer=Timer()
        self.smartmatch_thread=None
        self.cfg=types.SimpleNamespace(enabled=Config(True),match_threshold=Config(60))
        self.counters={"no_match":0,"matches":0}
        self.fallback_active=False
        self.events=[]
        self.state=""
        self.play_result=""
        self.target_quality="HD"
    def _user_languages(self):return ["RO"]
    def _set_state(self,s,*a):self.state=s
    def _log(self,e,msg):self.events.append((e,msg))
    def _same_sat_still_playing(self):return True
    def _build_candidate_plan(self,ranked,pinned=None):return []
    def _queue_background_smartmatch(self,*args,**kwargs):
        return queue(self,*args,**kwargs)
    def _activate_candidate(self,*args,**kwargs):raise AssertionError("No safe candidate allowed")
    def _play_match(self,*args,**kwargs):raise AssertionError("No safe candidate allowed")

class StabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.tmp.name)/"r725.ipk"
        cls.meta=b.build(cls.path)
        cls.now=b.pack.members_from(b.pack.unpack_ar(cls.path.read_bytes())["data.tar.gz"])
        cls.before=b.pack.members_from(b.pack.unpack_ar(base64.b64decode(b.BASE.read_bytes()))["data.tar.gz"])
        tree=ast.parse(cls.now[b.MONITOR])
        klass=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="SatFallbackMonitor")
        fns=[m for m in klass.body if isinstance(m,ast.FunctionDef) and m.name in
             ("_queue_background_smartmatch","_smartmatch_poll")]
        method_module=ast.Module(body=fns,type_ignores=[])
        ast.fix_missing_locations(method_module)
        namespace={"threading":threading,"time":time,"int":int,"str":str,"float":float}
        exec(compile(method_module,"r725_shipped_monitor.py","exec"),namespace)
        global queue,poll
        queue=namespace["_queue_background_smartmatch"]
        poll=namespace["_smartmatch_poll"]
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_duplicate_sat_tune_failed_reuses_fuzzy_job_and_emits_final_no_match(self):
        gate=threading.Event()
        cat=Catalog(gate)
        d=FakeMonitor(cat)
        queue(d,"Digi 24","best",stage="fuzzy")
        t=d.smartmatch_thread
        self.assertTrue(t.is_alive())
        self.assertEqual(d.smartmatch_generation,1)
        for _ in range(8):
            queue(d,"Digi 24","best",stage="fast")
            queue(d,"Digi 24","best",stage="fuzzy")
        self.assertEqual(d.smartmatch_generation,1)
        self.assertEqual(d.smartmatch_thread,t)
        self.assertEqual(d.catalog.fuzzy_calls,1)
        self.assertEqual(d.catalog.fast_calls,0)
        self.assertGreaterEqual(sum(ev=="MATCH_BG_REUSE" for ev,_ in d.events),10)
        gate.set();t.join(timeout=2)
        self.assertFalse(t.is_alive())
        poll(d)
        self.assertEqual(d.state,"NO_MATCH")
        self.assertEqual(d.counters["no_match"],1)
        self.assertTrue(any(x[0]=="MATCH_BG_DONE" and "stage=fuzzy" in x[1] for x in d.events))
        gen=d.smartmatch_generation
        queue(d,"Digi 24","best",stage="fast")
        self.assertEqual(d.smartmatch_generation,gen)
        self.assertTrue(any(x[0]=="MATCH_NO_MATCH_REUSE" for x in d.events))

    def test_fast_to_fuzzy_escalates_exactly_once_when_fast_has_zero_candidates(self):
        gate=threading.Event()
        cat=Catalog(gate)
        d=FakeMonitor(cat)
        queue(d,"Digi 24","best",stage="fast")
        d.smartmatch_thread.join(timeout=2)
        self.assertEqual(cat.fast_calls,1)
        poll(d)
        self.assertEqual(d.smartmatch_pending[4],"fuzzy")
        self.assertEqual(cat.fuzzy_calls,1)
        fuzzy_thread=d.smartmatch_thread
        for _ in range(5):
            queue(d,"Digi 24","best",stage="fast")
        self.assertEqual(d.smartmatch_thread,fuzzy_thread)
        self.assertEqual(cat.fuzzy_calls,1)
        gate.set();fuzzy_thread.join(timeout=2);poll(d)
        self.assertEqual(d.state,"NO_MATCH")
        self.assertEqual(d.counters["no_match"],1)
        self.assertEqual(sum(e=="MATCH_BG_DONE" for e,_ in d.events),2)

    def test_new_zap_catalog_refresh_and_expired_negative_can_retry(self):
        cat=Catalog(threading.Event())
        cat.gate.set()
        d=FakeMonitor(cat)
        queue(d,"Digi 24","best",stage="fuzzy")
        d.smartmatch_thread.join(timeout=2)
        poll(d)
        self.assertEqual(d.state,"NO_MATCH")
        generation=d.smartmatch_generation
        queue(d,"Digi 24","best",stage="fast")
        self.assertEqual(d.smartmatch_generation,generation)
        d.current_sat_started_at += 200
        queue(d,"Digi 24","best",stage="fast")
        self.assertEqual(d.smartmatch_generation,generation+1)
        d.smartmatch_thread.join(timeout=2);poll(d)
        d.catalog=Catalog(threading.Event());d.catalog.gate.set()
        queue(d,"Digi 24","best",stage="fast")
        self.assertEqual(d.smartmatch_generation,generation+3)
        d.smartmatch_thread.join(timeout=2)

    def test_source_matcher_player_native_pat_untouched(self):
        assert set(self.now)==set(self.before)|{b.CHANGELOG}
        for path,data in self.before.items():
            if path not in (b.MONITOR,b.PLUGIN,b.UPDATER):
                with self.subTest(name=path):self.assertEqual(data,self.now[path])
        def methods(raw):
            tree=ast.parse(raw)
            klass=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="SatFallbackMonitor")
            return {x.name:ast.dump(x,include_attributes=False) for x in klass.body if isinstance(x,ast.FunctionDef)}
        before,after=methods(self.before[b.MONITOR]),methods(self.now[b.MONITOR])
        self.assertEqual(set(before),set(after))
        self.assertEqual({name for name in before if before[name]!=after[name]},
                         {"_queue_background_smartmatch","_smartmatch_poll"})
        for key in ("_on_tune_failed","_deferred_tune_failed_fallback",
                    "_fallback_with_native_pat_guard","_fallback_if_matched",
                    "_on_start","_play_match"):
            self.assertEqual(before[key],after[key],key)
        self.assertFalse(self.meta["player_changed"])
        self.assertFalse(self.meta["scoring_changed"])

    def test_checksum_reproducibility_and_nonproduction(self):
        dest=Path(self.tmp.name)/"again.ipk"
        result=b.build(dest)
        self.assertEqual(self.path.read_bytes(),dest.read_bytes())
        self.assertEqual(hashlib.sha256(dest.read_bytes()).hexdigest(),result["sha256"])
        self.assertFalse(self.meta["field_tested"])
        self.assertFalse(self.meta["production_published"])

if __name__=="__main__":unittest.main()
