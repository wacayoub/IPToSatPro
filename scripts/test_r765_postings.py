#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.5 acceptance: benchmark true token postings and bounded core diff."""
import ast
import importlib.util
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod

builder=load("r765build","build-r76-metrix-preview.py")

class FastPostingR765(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work=tempfile.TemporaryDirectory()
        new=Path(cls.work.name)/"r765.ipk";old=Path(cls.work.name)/"r75.ipk"
        cls.meta=builder.build(new)
        builder.base.build(old)
        cls.new=builder.pack.members_from(builder.pack.unpack_ar(new.read_bytes())["data.tar.gz"])
        cls.old=builder.pack.members_from(builder.pack.unpack_ar(old.read_bytes())["data.tar.gz"])
        cls.plugin=cls.new[builder.PLUGIN].decode()
        cls.core=cls.new[builder.base.CORE].decode()

    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def test_exactly_four_changed_files_and_runtime_safety(self):
        differences={name for name in self.old if self.old[name]!=self.new[name]}
        self.assertEqual(differences,{builder.PLUGIN,builder.UPDATER,builder.THEME,builder.base.CORE})
        self.assertEqual(set(self.new)-set(self.old),{builder.NOTE})
        for name in self.old:
            if name in differences:continue
            self.assertEqual(self.new[name],self.old[name])
        self.assertEqual(self.new[builder.P+"player.py"],self.old[builder.P+"player.py"])
        self.assertEqual(self.new[builder.base.MONITOR],self.old[builder.base.MONITOR])
        self.assertFalse(self.meta["receiver_tested"])
        self.assertFalse(self.meta["production_published"])

    def test_core_only_preview_and_cache_put_changed(self):
        before=ast.parse(self.old[builder.base.CORE].decode())
        after=ast.parse(self.core)
        def defs(t):
            return {(c.name,n.name):ast.dump(n,include_attributes=False)
                for c in t.body if isinstance(c,ast.ClassDef)
                for n in c.body if isinstance(n,ast.FunctionDef)}
        b,a=defs(before),defs(after)
        self.assertEqual(set(b),set(a))
        modified={name for name in b if b[name]!=a[name]}
        self.assertEqual(modified,{("Catalog","fast_preview_mega_matches"),
                                   ("Catalog","_fast_cache_put")})
        self.assertIn("budget=18",self.core)
        self.assertIn("while len(order) > 96:",self.core)
        self.assertIn("if limit <= 24 and roles_cap <= 8 else",self.core)
        self.assertIn("max(760, roles_cap * max(3, len(self.server_roles())) * 2)",self.core)

    def test_postings_wins_over_full_40k_key_scan(self):
        tree=ast.parse(self.plugin)
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)
                and n.name=="_r763_preview_instant_index")
        code=compile(ast.Module(body=[fn],type_ignores=[]),"r765helper.py","exec")
        package="r765_virtualpkg"
        pkg=types.ModuleType(package);pkg.__path__=[]
        core=types.ModuleType(package+".core")
        core.normalize_name=lambda text:str(text).lower().strip()
        sys.modules[package]=pkg;sys.modules[package+".core"]=core
        try:
            env={"__package__":package,
                 "_r7414_fast_exact_seed":lambda name,cat:[]}
            exec(code,env)
            class TrapExact(dict):
                def items(self):
                    raise AssertionError("Unexpected expensive _exact key scan on GUI thread")
            groups=TrapExact({"noise %05d"%i:[] for i in range(45000)})
            postings={}
            rows=[]
            for role in ("PRIMARY","BACKUP1","BACKUP2"):
                for i in range(8):
                    rows.append({"name":"AR: OSN Movies Family HD",
                      "norm":"ar osntv movies family hd",
                      "url":"http://%s/stream/%d"%(role,i),"server_role":role})
            rows.append({"name":"OSN Movies Action","norm":"osn movies action",
                         "url":"http://wrong/action","server_role":"PRIMARY"})
            postings["family"]=rows
            postings["movies"]=rows
            cat=types.SimpleNamespace(_exact=groups,_token_index=postings)
            t0=time.perf_counter()
            result=env["_r763_preview_instant_index"]("OSNtv Movies Family",cat,24)
            elapsed=(time.perf_counter()-t0)*1000
            self.assertEqual(len(result),24)
            self.assertEqual({x["server_role"] for x in result},
                             {"PRIMARY","BACKUP1","BACKUP2"})
            self.assertNotIn("http://wrong/action",{x["url"] for x in result})
            self.assertTrue(all(x["_r763_fast_index"] and x["_manual_candidate"] and
                                x["_preview_score"]==0 for x in result))
            # CI only; receiver timer measured later.
            self.assertLess(elapsed,250)
            print("R765_FIRSTPAINT_SYNTHETIC_MS",round(elapsed,3))
        finally:
            sys.modules.pop(package,None);sys.modules.pop(package+".core",None)

    def test_missing_or_unrelated_token_index_no_full_catalog_scan(self):
        tree=ast.parse(self.plugin)
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)
                and n.name=="_r763_preview_instant_index")
        code=compile(ast.Module(body=[fn],type_ignores=[]),"r765helper.py","exec")
        pkg="r765_virtualpkg2";package=types.ModuleType(pkg);package.__path__=[]
        core=types.ModuleType(pkg+".core");core.normalize_name=lambda text:text.lower()
        sys.modules[pkg]=package;sys.modules[pkg+".core"]=core
        try:
            env={"__package__":pkg,"_r7414_fast_exact_seed":lambda name,catalog:[]}
            exec(code,env)
            class TrapExact(dict):
                def items(self):raise AssertionError("Scanned _exact despite existing postings")
            cat=types.SimpleNamespace(_exact=TrapExact({"unrelated": []}),
                                      _token_index={"politics":[{"name":"Other"}]})
            self.assertEqual(env["_r763_preview_instant_index"]("OSN Movies Family",cat),[])
        finally:
            sys.modules.pop(pkg,None);sys.modules.pop(pkg+".core",None)


if __name__=="__main__":
    unittest.main()
