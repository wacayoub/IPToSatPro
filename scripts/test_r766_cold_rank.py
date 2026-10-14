#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.6 actual packaged-core runtime equivalence, cold first Preview.

Build and compare R76.5 and R76.6 core ranking with identical mock channel
catalogues to prove no rank/score/role changes. Validate old and new number
of duplicate identity checks, decorated index rebuild, YELLOW deep fallback.
Synthetic tests do not certify Vu+ 4K receiver timings.
"""
import ast
import importlib.util
import tempfile
import time
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r766_builder",ROOT/"scripts"/"build-r76-metrix-preview.py")
builder=importlib.util.module_from_spec(sp);sp.loader.exec_module(builder)

def extract(source,method="fast_preview_mega_matches"):
    tree=ast.parse(source)
    cls=next(c for c in tree.body if isinstance(c,ast.ClassDef) and c.name=="Catalog")
    fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==method)
    return compile(ast.Module(body=[fn],type_ignores=[]),"core_mock.py","exec")

class SimCatalog:
    def __init__(self,rows):
        self.rows=rows
        self._exact={"osn movies family":rows[:]}
        self._token_index={"family":rows[:]}
        self._preview_decorated_ready=False
        self._preview_decorated_exact=None
        self.scans=0
        self.cache={}
        self._r733_last_profile={}
    def _fast_cache_key(self,*args):return tuple(str(a) for a in args)
    def _fast_cache_get(self,key):return self.cache.get(key)
    def _fast_cache_put(self,key,value):self.cache[key]=list(value)
    def server_roles(self):return ["PRIMARY","BACKUP1","BACKUP2"]
    def _ensure_preview_decorated_index(self):
        self.scans+=1
        return {}
    def _fast_candidate_pool(self,*args,**kwargs):return self.rows[:]
    def _ensure_preview_coverage_indexes(self,allow_scan=False):
        return {},{},{},{}
    def _ensure_preview_provider_index(self,allow_scan=False):return {}

class R766Acceptance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        output=Path(cls.tmp.name)/"r766.ipk"
        cls.meta=builder.build(output)
        content=builder.pack.members_from(builder.pack.unpack_ar(output.read_bytes())["data.tar.gz"])
        cls.optimized=content[builder.base.CORE].decode()
        old=Path(cls.tmp.name)/"r75.ipk"
        builder.base.build(old)
        orig=builder.pack.members_from(builder.pack.unpack_ar(old.read_bytes())["data.tar.gz"])
        cls.previous=builder.r765.patch_core(orig[builder.base.CORE].decode())
        cls.code_prev=extract(cls.previous)
        cls.code_new=extract(cls.optimized)
        cls.parts=content
        cls.baseline=orig

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def run_rank(self,code,deep=False):
        counters={"country":0,"reorder":0}
        def country(*a):
            counters["country"]+=1
            return "MATCH","AR","AR"
        def reorder(*a):
            counters["reorder"]+=1
            return False
        globals_={
            "_clock":time,
            "normalize_preview_name":lambda s:str(s or "").lower(),
            "normalize_name":lambda s:str(s or "").lower(),
            "_preview_numbers":lambda x:(),
            "_effective_sat_provider_family":lambda *a:"OSN",
            "_iptv_provider_family":lambda *a:"OSN",
            "_r748_country_relation":country,
            "_r749_reordered_identity":reorder,
            "_identity_anchor_tokens":lambda *a:["family"],
            "_preview_compact_key":lambda *a:"osnmoviesfamily",
            "_preview_abbreviation_key":lambda *a:"",
            "_preview_prefixes":lambda *a:(),
            "_enrich_channel":lambda ch:dict(ch),
            "match_score_details":lambda sat,ch,*args,**kwargs:(92.0,{"name":1.0,"country":"MATCH"}),
        }
        exec(code,globals_)
        rows=[]
        for role in ("PRIMARY","BACKUP1","BACKUP2"):
            for i in range(5):
                rows.append({"name":"OSN Movies Family","url":"https://%s/live/%s"%(role,i),
                   "server_role":role,"provider_family":"OSN","language":"AR",
                   "market":"AR","server_priority":i})
        catalog=SimCatalog(rows)
        func=globals_["fast_preview_mega_matches"]
        ranked=func(catalog,"OSN Movies Family",["AR"],
                    context={"market_preferences":["AR"],"provider_family":"OSN"},
                    per_server=64 if deep else 8,topn=192 if deep else 24,quality_mode="best")
        return ranked,counters,catalog

    def test_normal_has_identical_ranking_and_scores(self):
        before,counts_old,catalog_old=self.run_rank(self.code_prev)
        after,counts_new,catalog_new=self.run_rank(self.code_new)
        self.assertEqual(before,after)
        self.assertEqual(len(after),15)
        self.assertEqual({r[0]["server_role"] for r in after},
                         {"PRIMARY","BACKUP1","BACKUP2"})
        self.assertEqual(catalog_old.scans,1)
        self.assertEqual(catalog_new.scans,0)
        self.assertGreaterEqual(counts_old["country"],15)
        self.assertEqual(counts_new["country"],1)
        self.assertEqual(counts_new["reorder"],1)
        self.assertEqual(catalog_old._r733_last_profile["scored"],
                         catalog_new._r733_last_profile["scored"])

    def test_deep_keeps_decorated_index_fallback(self):
        before,_,catalog_old=self.run_rank(self.code_prev,deep=True)
        after,_,catalog_new=self.run_rank(self.code_new,deep=True)
        self.assertEqual(before,after)
        self.assertEqual(catalog_new.scans,1)
        self.assertEqual(catalog_old.scans,1)

    def test_exact_safe_changes_in_catalog_method_only(self):
        before=ast.parse(self.previous)
        after=ast.parse(self.optimized)
        def find(t):
            return {(c.name,n.name):ast.dump(n,include_attributes=False)
                    for c in t.body if isinstance(c,ast.ClassDef)
                    for n in c.body if isinstance(n,ast.FunctionDef)}
        b,a=find(before),find(after)
        self.assertEqual(set(b),set(a))
        changed={k for k in b if b[k]!=a[k]}
        self.assertEqual(changed,{("Catalog","fast_preview_mega_matches")})
        for name in self.baseline:
            if name not in (builder.PLUGIN,builder.UPDATER,builder.THEME,builder.base.CORE):
                self.assertEqual(self.parts[name],self.baseline[name])
        self.assertIn("R766_COLD_RANK_FAST",self.optimized)
        self.assertIn("relation_cache = {}",self.optimized)
        self.assertFalse(self.meta["receiver_tested"])
        self.assertFalse(self.meta["production_published"])

if __name__=="__main__":
    unittest.main()
