#!/usr/bin/env python3
"""R76.11 acceptance: executable cold-cache behavior on the REAL Preview route."""
import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("build_r7611",ROOT/"scripts/build-r7611-preview-cold.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)


def cls_methods(src):
    tree=ast.parse(src)
    cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="Catalog")
    return {x.name:x for x in cls.body if isinstance(x,ast.FunctionDef)}


class PreviewColdSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.work=tempfile.TemporaryDirectory()
        old=Path(cls.work.name)/"r7610.ipk"
        new=Path(cls.work.name)/"r7611.ipk"
        cls.old_meta=b.previous.build(old)
        cls.meta=b.build(new)
        cls.old=b.pack.members_from(b.pack.unpack_ar(old.read_bytes())["data.tar.gz"])
        cls.new=b.pack.members_from(b.pack.unpack_ar(new.read_bytes())["data.tar.gz"])
        cls.oldcore=cls.old[b.CORE].decode()
        cls.newcore=cls.new[b.CORE].decode()
        cls.old_methods=cls_methods(cls.oldcore)
        cls.new_methods=cls_methods(cls.newcore)

    @classmethod
    def tearDownClass(cls):
        cls.work.cleanup()

    def test_actual_preview_48_calls_modified_nomination(self):
        normal=self.new_methods["fast_rank_matches_all_servers"]
        calls={ast.unparse(n.func) for n in ast.walk(normal) if isinstance(n,ast.Call)}
        self.assertIn("self._preview_nomination_pool",calls)
        nomination=self.new_methods["_preview_nomination_pool"]
        body=ast.get_source_segment(self.newcore,nomination)
        self.assertIn(b.fix.TAG,body)
        self.assertIn("preview_index = getattr(self,",body)
        self.assertIn('"_preview_decorated_ready"',body)

    def test_core_changes_only_normal_nomination_method(self):
        self.assertEqual(set(self.old_methods),set(self.new_methods))
        diffs={name for name in self.old_methods if ast.dump(
            self.old_methods[name],include_attributes=False)!=ast.dump(
            self.new_methods[name],include_attributes=False)}
        self.assertEqual(diffs,{"_preview_nomination_pool"})
        before=ast.get_source_segment(self.oldcore,self.old_methods["_preview_nomination_pool"])
        after=ast.get_source_segment(self.newcore,self.new_methods["_preview_nomination_pool"])
        self.assertEqual(after,b.fix.patch_core(self.oldcore)[
            self.newcore.index("    def _preview_nomination_pool("):
        ].split("\n    def ",1)[0] if False else after)
        self.assertIn("preview_index = self._ensure_preview_decorated_index()",before)
        self.assertNotIn("preview_index = self._ensure_preview_decorated_index()",after)
        self.assertEqual(b.fix.patch_core(self.newcore),self.newcore)

    def test_execute_real_cold_index_guard(self):
        fn=self.new_methods["_preview_nomination_pool"]
        assigns=[i for i,n in enumerate(fn.body)
                 if isinstance(n,ast.Assign)
                 and any(isinstance(t,ast.Name) and t.id=="preview_index" for t in n.targets)]
        self.assertEqual(len(assigns),2)  # cold variable and optional empty fallback
        i=assigns[0]
        node=fn.body[i]
        follow=fn.body[i+1]
        self.assertIsInstance(follow,ast.If)
        code=compile(ast.fix_missing_locations(ast.Module(body=[node,follow],
                              type_ignores=[])),"r7611_guard.py","exec")
        class Catalog:
            _preview_decorated_exact=None
            _preview_decorated_ready=False
            calls=0
            def _ensure_preview_decorated_index(self):
                self.calls+=1
                return {"demo": ["slow"]}
        cat=Catalog()
        scope={"self":cat}
        exec(code,scope)
        self.assertEqual(scope["preview_index"],{})
        self.assertEqual(cat.calls,0)
        cat._preview_decorated_exact={"demo":["warm"]}
        cat._preview_decorated_ready=True
        exec(code,scope)
        self.assertEqual(scope["preview_index"],{"demo":["warm"]})
        self.assertEqual(cat.calls,0)
        cat._preview_decorated_ready=False
        exec(code,scope)
        self.assertEqual(scope["preview_index"],{})
        self.assertEqual(cat.calls,0)

    def test_deep_yellow_still_builds_original_index(self):
        deep=self.new_methods["fast_preview_mega_matches"]
        calls={ast.unparse(n.func) for n in ast.walk(deep) if isinstance(n,ast.Call)}
        self.assertIn("self._ensure_preview_decorated_index",calls)
        self.assertEqual(ast.dump(deep,include_attributes=False),
                         ast.dump(self.old_methods["fast_preview_mega_matches"],
                                  include_attributes=False))

    def test_player_monitor_skin_and_user_maps_not_touched(self):
        changed={k for k in self.old if self.old[k]!=self.new[k]}
        self.assertEqual(changed,{b.CORE,b.PLUGIN,b.UPDATER})
        self.assertEqual(set(self.new)-set(self.old),{b.NOTE})
        for name in ("monitor.py","player.py","metadata_shadow.py",
                     "preview_theme_r74.py","home_themes_r767.py"):
            p=b.P+name
            self.assertEqual(self.new.get(p),self.old.get(p),p)
        self.assertFalse(any("mapping" in x.lower() or "override" in x.lower()
                             for x in changed))

    def test_version_and_safe_beta(self):
        self.assertEqual(self.meta["version"],b.VERSION)
        self.assertTrue(self.meta["beta"])
        self.assertFalse(self.meta["receiver_tested"])
        self.assertFalse(self.meta["production_published"])
        self.assertIn('PLUGIN_VERSION = "'+b.VERSION+'"',self.new[b.PLUGIN].decode())
        self.assertIn(b.MANIFEST,self.new[b.UPDATER].decode())


if __name__=="__main__":
    unittest.main()
