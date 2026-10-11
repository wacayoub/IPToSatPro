#!/usr/bin/env python3
"""Test the REAL packaged R72.7 fuzzy cache function and guarded player integrity."""
import ast,base64,hashlib,importlib.util,tempfile,time,unittest
from pathlib import Path
sp=importlib.util.spec_from_file_location("r727",Path(__file__).with_name("build-r727-fast.py"))
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)

def getmethod(source,name):
    tree=ast.parse(source)
    matches=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name]
    assert len(matches)==1,(name,len(matches))
    module=ast.Module(body=[matches[0]],type_ignores=[])
    ast.fix_missing_locations(module)
    return module

class FakeCatalog:
    def __init__(self):
        self.rows=[
            {"name":"Digi 24","server_priority":0,"fp":"1"},
            {"name":"Digi 24 HD","server_priority":1,"fp":"2"},
            {"name":"Other 123","server_priority":2,"fp":"3"},
        ]
        self.pools=0
        self.scores=0
    def _candidate_pool(self,name):
        self.pools+=1
        return self.rows
    def _fast_cache_key(self,mode,name,langs,ctx,quality,extra=()):
        ctx=ctx or {}
        return(mode,name,tuple(langs or ()),ctx.get("market",""),
               ctx.get("confidence",""),quality,tuple(extra))
    def _context_rank_bands(self,ch,det,ctx):
        return (0,0,0.0)
    def find_fingerprint(self,fp):
        return next((ch for ch in self.rows if ch["fp"]==fp),None)

class MatchingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.pkg=Path(cls.tmp.name)/"r727.ipk"
        cls.metadata=b.build(cls.pkg)
        cls.data=b.pack.members_from(b.pack.unpack_ar(cls.pkg.read_bytes())["data.tar.gz"])
        cls.old=b.pack.members_from(b.pack.unpack_ar(base64.b64decode(b.B64.read_bytes()))["data.tar.gz"])
        def enrich(ch):return dict(ch)
        def scorer(name,ch,langs,ctx,qual):
            cls.scoring+=1
            same=ch.get("name")=="Digi 24"
            return (97.0 if same else 76.0),{
              "name":100.0 if same else 80.0,
              "equivalence":0.0,"variant":0.0,
              "context":0.0,"reject_reason":"","review_reason":"",
            }
        ns={"_enrich_channel":enrich,"match_score_details":scorer,
            "quality_fit_key":lambda ch,name,ctx: (0,),
            "match_decision":lambda score,det,t:"SAFE" if score>=t else "REVIEW",
            "_stream_penalty":lambda ch:0,
            "effective_quality_info":lambda ch:("FHD",500,"observed")}
        cls.scoring=0
        exec(compile(getmethod(cls.data[b.CORE],"rank_matches"),"r727_core_rank.py","exec"),ns)
        exec(compile(getmethod(cls.data[b.CORE],"set_observed_quality"),"r727_core_quality.py","exec"),ns)
        cls.rank=staticmethod(ns["rank_matches"])
        cls.observed=staticmethod(ns["set_observed_quality"])
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):type(self).scoring=0

    def test_same_fuzzy_candidates_preserve_order_and_skip_expensive_second_scan(self):
        f=FakeCatalog()
        first=self.rank(f,"Digi 24",["RO"],{"market":"RO","confidence":"MEDIUM"},32,"best")
        self.assertEqual(f.pools,1)
        self.assertEqual(type(self).scoring,3)
        second=self.rank(f,"Digi 24",["RO"],{"market":"RO","confidence":"MEDIUM"},32,"best")
        self.assertEqual(first,second)
        self.assertEqual(f.pools,1)
        self.assertEqual(type(self).scoring,3)
        self.assertEqual(second[0][0]["name"],"Digi 24")
    def test_other_language_market_quality_key_does_not_reuse_wrong_match(self):
        f=FakeCatalog()
        self.rank(f,"Digi 24",["RO"],{"market":"RO","confidence":"MEDIUM"},32,"best")
        self.rank(f,"Digi 24",["FR"],{"market":"RO","confidence":"MEDIUM"},32,"best")
        self.rank(f,"Digi 24",["RO"],{"market":"NL","confidence":"MEDIUM"},32,"best")
        self.rank(f,"Digi 24",["RO"],{"market":"RO","confidence":"MEDIUM"},32,"quality")
        self.rank(f,"Digi 24",["RO"],{"market":"RO","confidence":"MEDIUM"},16,"best")
        self.assertEqual(f.pools,5)
    def test_timeout_and_bounded_max_entries(self):
        f=FakeCatalog()
        p={"market":"RO"}
        self.rank(f,"Digi 24",[],p,32,"best")
        self.assertEqual(f.pools,1)
        key=next(iter(f._r727_fuzzy_cache))
        oldtime,rows=f._r727_fuzzy_cache[key]
        f._r727_fuzzy_cache[key]=(time.monotonic()-91,rows)
        self.rank(f,"Digi 24",[],p,32,"best")
        self.assertEqual(f.pools,2)
        for i in range(34):
            self.rank(f,"Digi 24 "+str(i),[],p,32,"best")
        self.assertLessEqual(len(f._r727_fuzzy_cache),16)
    def test_confirmed_resolution_invalidates_fuzzy_ranking(self):
        f=FakeCatalog()
        self.rank(f,"Digi 24",[],{},32,"best")
        self.assertEqual(len(f._r727_fuzzy_cache),1)
        ch=self.observed(f,"1",1920,1080)
        self.assertEqual(ch["actual_width"],1920)
        self.assertEqual(ch["actual_height"],1080)
        self.assertEqual(len(f._r727_fuzzy_cache),0)
        self.rank(f,"Digi 24",[],{},32,"best")
        self.assertEqual(f.pools,2)
        self.assertIsNone(self.observed(f,"unknown",1280,720))
    def test_existing_fuzzy_matcher_and_player_bytes_untouched(self):
        self.assertEqual(set(self.data),set(self.old)|{b.CHANGELOG})
        for path,blob in self.old.items():
            if path not in (b.CORE,b.PLUGIN,b.UPDATER):
                self.assertEqual(blob,self.data[path],path)
        before=ast.parse(self.old[b.CORE]);after=ast.parse(self.data[b.CORE])
        def functions(tree):
            return {x.name:ast.dump(x,include_attributes=False) for x in ast.walk(tree) if isinstance(x,ast.FunctionDef)}
        a,d=functions(before),functions(after)
        self.assertEqual(set(a),set(d))
        self.assertEqual({x for x in a if a[x]!=d[x]},
                         {"rank_matches","set_observed_quality"})
        self.assertFalse(self.metadata["player_changed"])
        self.assertTrue(self.metadata["scoring_unchanged"])
    def test_package_reproducible_no_auto_update(self):
        p=Path(self.tmp.name)/"again.ipk"
        result=b.build(p)
        self.assertEqual(p.read_bytes(),self.pkg.read_bytes())
        self.assertEqual(result["sha256"],hashlib.sha256(p.read_bytes()).hexdigest())
        import json
        self.assertEqual(json.loads((b.R/"update.json").read_text())["version"],"1.0.46-r70-final")
        self.assertFalse(result["receiver_tested"])
if __name__=="__main__":unittest.main()
