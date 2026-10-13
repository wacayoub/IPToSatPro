"""R7418 tests: actual built R74 core/monitor, bounded and cancellable fuzzy stage."""
import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]


def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/file)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod


builder=load("builder7418","build-r74-unified.py")
aac=load("aac7418","r74_tod_bein_audio_hotfix.py")
fta=load("fta7418","r7417_fta_signal_native_guard.py")
patcher=load("bounded7418","r7418_bounded_cancel_fuzzy.py")


class BoundedFuzzyRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        ipk=Path(cls.temp.name)/"r74.ipk"
        builder.build(ipk)
        pack=builder.b.b.base.pack
        files=pack.members_from(pack.unpack_ar(ipk.read_bytes())["data.tar.gz"])
        cls.core=files[builder.CORE].decode()
        mon=files[builder.MONITOR].decode()
        cls.monitor=fta.patch(aac.patch(mon)[0])[0]
        cls.newcore,cls.corestatus=patcher.patch_core(cls.core)
        cls.newmon,cls.monstatus=patcher.patch_monitor(cls.monitor)
        ct=ast.parse(cls.newcore)
        mt=ast.parse(cls.newmon)
        catalog=next(x for x in ct.body if isinstance(x,ast.ClassDef) and x.name=="Catalog")
        monitor=next(x for x in mt.body if isinstance(x,ast.ClassDef) and x.name=="SatFallbackMonitor")
        cls.catalog_methods={n.name:n for n in catalog.body if isinstance(n,ast.FunctionDef)}
        cls.monitor_methods={n.name:n for n in monitor.body if isinstance(n,ast.FunctionDef)}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def isolate(cls,method,env,monitor=False):
        tree=cls.monitor_methods if monitor else cls.catalog_methods
        node=tree[method]
        mod=ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[]))
        scope=dict(env)
        exec(compile(mod,"r7418-reconstructed.py","exec"),scope)
        return scope[method]

    @staticmethod
    def synthetic(n=900):
        roles=("PRIMARY","BACKUP1","BACKUP2")
        records=[]
        for i in range(n):
            records.append({
                "id":str(i),"name":"Global News %d"%i,
                "norm":"global news %d"%i,
                "server_role":roles[i%3],
                "server_priority":i%3+1,
            })
        records[-1]=dict(records[-1],name="Almajd News",
                         norm="almajd news")
        return records

    def test_generated_package_install_and_idempotence(self):
        self.assertEqual((self.corestatus,self.monstatus),("ready","ready"))
        self.assertEqual(patcher.patch_core(self.newcore)[1],"already-installed")
        self.assertEqual(patcher.patch_monitor(self.newmon)[1],"already-installed")
        self.assertIn("R7417_FTA_SIGNAL_NATIVE_GUARD",self.newmon)
        self.assertIn(aac.TAG,self.newmon)
        self.assertIn("NATIVE_PAT_GUARD_MS",self.newmon)

    def test_96_of_900_and_tail_exact_candidate_rescued(self):
        records=self.synthetic()
        class Catalog:
            def _candidate_pool(self,sat_name):return records
        fn=self.isolate("_r7418_nominate_fuzzy",
                        {"normalize_name":lambda n:n.lower().strip()})
        found=fn(Catalog(),"Almajd News",96)
        self.assertEqual(len(found),96)
        self.assertIn(records[-1],found)
        roles={r:sum(x["server_role"]==r for x in found) for r in ("PRIMARY","BACKUP1","BACKUP2")}
        self.assertEqual(roles,{"PRIMARY":32,"BACKUP1":32,"BACKUP2":32})
        self.assertEqual(len(records),900)

    def _test_catalog(self):
        records=self.synthetic()
        called=[]
        normalize=lambda n:(n or "").lower().strip()
        nominees=self.isolate("_r7418_nominate_fuzzy",{"normalize_name":normalize})
        def score(name,ch,lang,ctx,quality):
            called.append(ch["id"])
            match = 101.0 if ch.get("name") == name else 0.0
            return match,{"name":match,"equivalence":0.0,"variant":0.0}
        def verdict(score,details,threshold):
            return "SAFE" if score>=threshold else "REVIEW"
        class Catalog:
            def __init__(self):
                self._r727_fuzzy_cache={}
            def _candidate_pool(self,sat_name):return records
            def _fast_cache_key(self,*parts):return repr(parts)
            def _context_rank_bands(self,ch,det,ctx):return (0,0,0)
            def _r7418_nominate_fuzzy(self,*a):
                return nominees(self,*a)
        env={"match_score_details":score,
             "match_decision":verdict,
             "quality_fit_key":lambda *a:(0,0),
             "_stream_penalty":lambda ch:0,
             "_enrich_channel":lambda ch:ch}
        function=self.isolate("rank_matches",env)
        return Catalog(),function,called,records

    def test_budgeted_original_score_and_rank_decides_safe(self):
        cat,fn,called,records=self._test_catalog()
        ranked=fn(cat,"Almajd News",context={},topn=32,
                  candidate_budget=96,should_abort=lambda:False)
        self.assertEqual(len(called),96)
        self.assertEqual(ranked[0][0]["name"],"Almajd News")
        self.assertEqual(ranked[0][1],101.0)
        self.assertEqual(len(ranked),32)

    def test_manual_no_budget_preserves_full_900(self):
        cat,fn,called,records=self._test_catalog()
        results=fn(cat,"Almajd News",topn=5)
        self.assertEqual(len(called),900)
        self.assertEqual(results[0][0]["name"],"Almajd News")

    def test_abort_every_eight_scores_and_does_not_cache_partial(self):
        cat,fn,called,records=self._test_catalog()
        ranked=fn(cat,"Almajd News",candidate_budget=96,
                  should_abort=lambda:len(called)>=16)
        self.assertEqual(ranked,[])
        self.assertLessEqual(len(called),16)
        self.assertFalse(cat._r727_fuzzy_cache)

    def test_fuzzy_budget_changes_cache_key_only_in_budgeted_lane(self):
        cat,fn,called,records=self._test_catalog()
        fn(cat,"Almajd News",candidate_budget=96)
        self.assertEqual(len(called),96)
        fn(cat,"Almajd News")
        self.assertEqual(len(called),996)
        fn(cat,"Almajd News",candidate_budget=96)
        self.assertEqual(len(called),996)

    def test_monitor_worker_has_explicit_cancel_probe(self):
        s=ast.get_source_segment(self.newmon,self.monitor_methods["_queue_background_smartmatch"])
        self.assertIn("candidate_budget=96",s)
        self.assertIn("generation != int(self.smartmatch_generation)",s)
        self.assertIn("sat_ref != str(self.current_sat_ref_string or",s)
        self.assertIn("catalog is not self.catalog",s)
        self.assertIn('stage == "fast"',s)
        self.assertIn('"fuzzy"',s)

    def test_full_preview_and_native_fta_logic_unmodified(self):
        self.assertIn('def fast_preview_mega_matches(',self.newcore)
        self.assertIn('def fast_rank_matches_all_servers(',self.newcore)
        self.assertIn('def _r7417_native_keep_reason(',self.newmon)
        self.assertIn("AUDIO_SAFE_PLAYER",self.newmon)

    def test_dual_file_installer_and_rollback_byte_identical(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            (d/"core.py").write_text(self.core)
            (d/"monitor.py").write_text(self.monitor)
            self.assertEqual(patcher.main(["--check","--root",tmp]),0)
            self.assertEqual(patcher.main(["--apply","--root",tmp]),0)
            self.assertEqual((d/"core.py").read_text(),self.newcore)
            self.assertEqual((d/"monitor.py").read_text(),self.newmon)
            self.assertTrue((d/patcher.CORE_BACKUP).is_file())
            self.assertTrue((d/patcher.MON_BACKUP).is_file())
            self.assertEqual(patcher.main(["--rollback","--root",tmp]),0)
            self.assertEqual((d/"core.py").read_text(),self.core)
            self.assertEqual((d/"monitor.py").read_text(),self.monitor)


if __name__=="__main__":
    unittest.main()
