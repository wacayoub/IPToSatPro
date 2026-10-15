#!/usr/bin/env python3
"""R76.14 package regression: only exact 3 plugin files and passive metadata change."""
import ast,importlib.util,tempfile,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def get(name,fn):
 s=importlib.util.spec_from_file_location(name,R/"scripts"/fn)
 m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
old=get("build13","build-r7613-preview-cpu.py")
new=get("build14","build-r7614-preview-cache.py")


class CachePackageTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.t=tempfile.TemporaryDirectory()
  p=Path(cls.t.name)
  a=p/"old.ipk";b=p/"new.ipk"
  cls.oldmeta=old.build(a);cls.newmeta=new.build(b)
  cls.before=old.pack.members_from(old.pack.unpack_ar(a.read_bytes())["data.tar.gz"])
  cls.after=old.pack.members_from(old.pack.unpack_ar(b.read_bytes())["data.tar.gz"])
  cls.ctrl=old.pack.members_from(old.pack.unpack_ar(b.read_bytes())["control.tar.gz"])
 @classmethod
 def tearDownClass(cls):
  cls.t.cleanup()
 def test_base_package_and_scope(self):
  self.assertEqual(self.oldmeta["sha256"],"817f797b1a60f5b146071366e2dc06a1de6f4c711fc2fbfd5937360e88989c76")
  self.assertEqual(self.newmeta["version"],"1.0.46-r76.14-preview-parsecache-beta")
  self.assertFalse(self.newmeta["production_published"])
  self.assertFalse(self.newmeta["receiver_tested"])
  self.assertEqual(set(self.newmeta["changed"]),{new.CORE,new.PLUGIN,new.UPDATER})

 def test_player_mappings_and_catalog_modules_unchanged(self):
  for path,raw in self.before.items():
   if path not in (new.CORE,new.PLUGIN,new.UPDATER):
    self.assertEqual(self.after[path],raw,path)
  self.assertIn("R7614_PREVIEW_PARSE_CACHE_IMMUTABLE",self.after[new.CORE].decode())
  self.assertIn("R7613_PREVIEW_SCORING_POSTINGS",self.after[new.CORE].decode())
  self.assertIn("R7612_NORMAL_PREVIEW_PHASE_TIMINGS",self.after[new.CORE].decode())
  self.assertIn('PREVIEW_STAGE',self.after[new.PLUGIN].decode())

 def test_passive_opkg_postinst_does_not_touch_user_files(self):
  p=self.ctrl["postinst"].decode()
  self.assertIn("R76.14 Preview cache beta installed",p)
  for word in ("rm ","mv ","chmod ","chown ","python3 ","import_spec","cache_migrator","boot_cache"):
   self.assertNotIn(word,p)
  self.assertEqual(set(self.ctrl).intersection(("preinst","prerm","postrm")),set())

 def test_original_catalog_scoring_logic_identical(self):
  a=ast.parse(self.before[new.CORE].decode())
  b=ast.parse(self.after[new.CORE].decode())
  left=[(n.name,ast.dump(ast.Module(body=n.body,type_ignores=[]),include_attributes=False))
        for n in ast.walk(a) if isinstance(n,ast.FunctionDef)]
  right=[(n.name,ast.dump(ast.Module(body=n.body,type_ignores=[]),include_attributes=False))
        for n in ast.walk(b) if isinstance(n,ast.FunctionDef)]
  self.assertEqual(left,right)


if __name__=="__main__":
 unittest.main()
