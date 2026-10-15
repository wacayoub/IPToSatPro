#!/usr/bin/env python3
"""R80 RC1 scoped IPK protection: no score/UI/player/mapping or installer mutations."""
import ast,importlib.util,tempfile,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def module(name,path):
 s=importlib.util.spec_from_file_location(name,R/"scripts"/path)
 v=importlib.util.module_from_spec(s);s.loader.exec_module(v);return v
old=module("r7615_for_r80","build-r7615-preview-index.py")
new=module("r80candidate","build-r80-rc1-index-focus.py")

class TestOnlyPreviewIndexPackage(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory()
  t=Path(cls.tmp.name);p=t/"r80-rc1.ipk";q=t/"r7615.ipk"
  cls.pre=old.build(p);cls.post=new.build(q)
  cls.prev=old.pack.members_from(old.pack.unpack_ar(p.read_bytes())["data.tar.gz"])
  cls.next=old.pack.members_from(old.pack.unpack_ar(q.read_bytes())["data.tar.gz"])
  cls.post_ctrl=old.pack.members_from(old.pack.unpack_ar(q.read_bytes())["control.tar.gz"])
 @classmethod
 def tearDownClass(cls):
  cls.tmp.cleanup()
 def test_predecessor_exact_and_nonproduction(self):
  self.assertEqual(self.pre["sha256"],"c3991af773c6700c1aac0652f5027b27b4e1a91ff0820bf25e801e8d8488c468")
  self.assertEqual(self.post["version"],"1.0.46-r80.0-rc1-index-focus")
  self.assertFalse(self.post["production_published"])
  self.assertFalse(self.post["receiver_tested"])
 def test_all_nonmodified_ipk_files_byte_identical(self):
  self.assertEqual(set(self.post["changed"]),{new.CORE,new.PLUGIN,new.UPDATER})
  for path,raw in self.prev.items():
   if path not in (new.CORE,new.PLUGIN,new.UPDATER):
    self.assertEqual(self.next[path],raw,path)
 def test_only_exact_two_catalog_nomination_methods_modified(self):
  before=ast.parse(self.prev[new.CORE].decode())
  after=ast.parse(self.next[new.CORE].decode())
  def functions(asttree):
   c=next(n for n in asttree.body if isinstance(n,ast.ClassDef) and n.name=="Catalog")
   return {n.name:ast.dump(n,include_attributes=False)
           for n in c.body if isinstance(n,ast.FunctionDef)}
  b=functions(before);a=functions(after)
  self.assertEqual(b.keys(),a.keys())
  self.assertEqual({k for k in b if a[k]!=b[k]},
                   {"_preview_nomination_pool"})
  # Every scorer and other top-level helper remains untouched.
  def fbody(t,name):
   return [ast.dump(ast.Module(body=n.body,type_ignores=[]),include_attributes=False)
           for n in ast.walk(t) if isinstance(n,ast.FunctionDef) and n.name==name]
  self.assertEqual(fbody(before,"match_score_details"),fbody(after,"match_score_details"))
 def test_r7614_preview_gui_logs_remain(self):
  self.assertIn("R7614_PREVIEW_PARSE_CACHE_IMMUTABLE",self.next[new.CORE].decode())
  self.assertIn("R80_INDEX_LAZY_GUARDS",self.next[new.CORE].decode())
  self.assertIn("PREVIEW_STAGE",self.next[new.PLUGIN].decode())
 def test_postinst_is_passive_and_does_not_touch_user_assets(self):
  hook=self.post_ctrl["postinst"].decode()
  self.assertIn("R80 RC1 index focus installed",hook)
  for token in ("rm ","mv ","chmod ","chown ","python3 ","import_spec","cache_migrator"):
   self.assertNotIn(token,hook)
  self.assertFalse(set(self.post_ctrl).intersection({"preinst","prerm","postrm"}))

if __name__=="__main__":
 unittest.main()
