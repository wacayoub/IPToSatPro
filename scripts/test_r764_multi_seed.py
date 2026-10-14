#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.4 executable cold-cache tests, on actual packaged plugin methods."""
import ast
import importlib.util
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/file)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj
builder=load("r764_package","build-r76-metrix-preview.py")


class FirstPaintTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory()
        pkg=Path(cls.temporary.name)/"r764.ipk"
        cls.build_info=builder.build(pkg)
        packed=builder.pack.members_from(builder.pack.unpack_ar(pkg.read_bytes())["data.tar.gz"])
        cls.src=packed[builder.PLUGIN].decode()
        tree=ast.parse(cls.src)
        helper=next(n for n in tree.body if isinstance(n,ast.FunctionDef)
                    and n.name=="_r763_preview_instant_index")
        cl=next(n for n in tree.body if isinstance(n,ast.ClassDef)
                and n.name=="SatIPTVBridgePreview")
        method=next(n for n in cl.body if isinstance(n,ast.FunctionDef)
                    and n.name=="_load_selected_sat_candidates")
        target=next(n for n in method.body if isinstance(n,ast.If)
                    and ast.unparse(n.test).startswith("not complete and len("))
        cls.helper_code=compile(ast.Module(body=[helper],type_ignores=[]),"r764_helper.py","exec")
        cls.gate_code=compile(ast.Module(body=[target],type_ignores=[]),"r764_gate.py","exec")

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def sandbox(self):
        marker="r764_dummy"
        core=types.ModuleType(marker+".core")
        core.normalize_name=lambda name: str(name).lower().strip()
        sys.modules[marker]=types.ModuleType(marker)
        sys.modules[marker].__path__=[]
        sys.modules[marker+".core"]=core
        ns={"__package__":marker, "_r7414_fast_exact_seed":lambda name,cat:[]}
        exec(self.helper_code,ns)
        return marker,ns

    def test_one_cached_source_is_enriched_before_rank(self):
        marker,ns=self.sandbox()
        try:
            groups={}
            for i in range(13000):
                groups["unrelated service xyz%05d"%i]=[]
            roles=("PRIMARY","BACKUP1","BACKUP2")
            for role in roles:
                for i in range(12):
                    groups["osn movies family %s variant%02d"%(role,i)]=[
                        {"name":"OSN Movies Family HD","url":"http://%s/stream/%02d"%(role,i),
                         "server_role":role}]
            groups["osn movies action"]=[
                {"name":"OSN Movies Action","url":"http://wrong/action",
                 "server_role":"PRIMARY"}]
            cat=types.SimpleNamespace(_exact=groups)
            old={"url":"http://manual/locked","name":"OSN Movies Family",
                 "_manual_candidate":True}
            obj=types.SimpleNamespace(
                sat_name="OSNtv Movies Family",
                _candidate_cache={}
            )
            key="sat-key"
            ctx={"origin":"SAT"}
            cached=(obj.sat_name,ctx,[old],False)
            logs=[]
            runtime=dict(ns,
                self=obj,key=key,cached=cached,complete=False,seeded=False,
                MONITOR=types.SimpleNamespace(catalog=cat),
                channel_fingerprint=lambda ch: ch.get("url") or "",
                _startup_log=lambda *args: logs.append(args))
            started=time.perf_counter()
            exec(self.gate_code,runtime)
            elapsed_ms=(time.perf_counter()-started)*1000
            combined=obj._candidate_cache[key][2]
            self.assertEqual(len(combined),24)
            self.assertEqual(combined[0]["url"],old["url"])
            self.assertEqual(len(set(ch["url"] for ch in combined)),24)
            self.assertNotIn("http://wrong/action",
                             {ch["url"] for ch in combined})
            self.assertEqual({ch.get("server_role") for ch in combined[1:]},set(roles))
            self.assertTrue(all(ch.get("_manual_candidate")
                         for ch in combined[1:]))
            self.assertTrue(all(ch.get("_preview_score")==0.0
                         for ch in combined[1:]))
            self.assertFalse(obj._candidate_cache[key][3])
            self.assertTrue(runtime["seeded"])
            self.assertTrue(any("ENRICHED" in str(log) for log in logs))
            # CI desktop threshold only, NOT a Vu+ performance guarantee.
            self.assertLess(elapsed_ms,600)
        finally:
            sys.modules.pop(marker+".core",None);sys.modules.pop(marker,None)

    def test_no_fake_candidates_if_no_real_index_match(self):
        marker,ns=self.sandbox()
        try:
            cat=types.SimpleNamespace(_exact={
                "osn movies action":[{"name":"OSN Movies Action",
                 "url":"http://wrong","server_role":"PRIMARY"}],
                "beIN Sport 2":[{"name":"beIN Sport 2",
                 "url":"http://2","server_role":"PRIMARY"}]})
            got=ns["_r763_preview_instant_index"]("OSNtv Movies Family",cat,24)
            self.assertEqual(got,[])
        finally:
            sys.modules.pop(marker+".core",None);sys.modules.pop(marker,None)

    def test_completed_cache_does_not_rerank(self):
        marker,ns=self.sandbox()
        try:
            obj=types.SimpleNamespace(sat_name="OSNtv Movies Family",_candidate_cache={})
            previous=[{"url":"http://verified","name":"OSN Movies Family"}]
            cached=(obj.sat_name,{},previous,True)
            runtime=dict(ns,self=obj,key="sat",cached=cached,complete=True,seeded=False,
               MONITOR=types.SimpleNamespace(catalog=types.SimpleNamespace(_exact={})),
               _startup_log=lambda *args:None,
               channel_fingerprint=lambda ch:ch.get("url") or "")
            exec(self.gate_code,runtime)
            self.assertFalse(runtime["seeded"])
            self.assertFalse(obj._candidate_cache)
        finally:
            sys.modules.pop(marker+".core",None);sys.modules.pop(marker,None)

    def test_safety_no_changes_to_automap_player_or_mappings(self):
        self.assertIn("R764_MULTI_CANDIDATE_FIRST_PAINT",self.src)
        self.assertIn("if not complete and len(cached[2] or []) < 24:",self.src)
        self.assertIn("PREVIEW_RANK_BG",self.src)
        self.assertIn("candidate_budget = 192 if self._r71_worker_deep else 24",self.src)
        self.assertIn("self.candidate_expand_timer.start(20, True)",self.src)
        self.assertEqual(self.build_info["changes"],sorted([builder.PLUGIN,builder.THEME,builder.UPDATER]))
        self.assertFalse(self.build_info["receiver_tested"])


if __name__=="__main__":
    unittest.main()
