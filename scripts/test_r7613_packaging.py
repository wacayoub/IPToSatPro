#!/usr/bin/env python3
"""R76.13 release candidate protections, source parity and safe hook."""
import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def mod(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/"scripts"/path)
 v=importlib.util.module_from_spec(s);s.loader.exec_module(v);return v
old=mod("old7613source","build-r7612-preview-profile.py")
new=mod("new7613build","build-r7613-preview-cpu.py")


class PackagedPreviewCPU(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.t=tempfile.TemporaryDirectory()
  oldipk=Path(cls.t.name)/"old.ipk"
  newipk=Path(cls.t.name)/"new.ipk"
  cls.oldmeta=old.build(oldipk)
  cls.newmeta=new.build(newipk)
  cls.before=new.pack.members_from(new.pack.unpack_ar(oldipk.read_bytes())["data.tar.gz"])
  cls.after=new.pack.members_from(new.pack.unpack_ar(newipk.read_bytes())["data.tar.gz"])
  cls.before_ctrl=new.pack.members_from(new.pack.unpack_ar(oldipk.read_bytes())["control.tar.gz"])
  cls.after_ctrl=new.pack.members_from(new.pack.unpack_ar(newipk.read_bytes())["control.tar.gz"])
 @classmethod
 def tearDownClass(cls):
  cls.t.cleanup()

 def test_versions_and_production_safety(self):
  self.assertEqual(self.oldmeta["sha256"],
    "773bbbba6c32be3b1f61a21c773593f6ff5d04382beeffc341e38961d5b3a911")
  self.assertEqual(self.newmeta["version"],"1.0.46-r76.13-preview-cpu-fast-beta")
  self.assertFalse(self.newmeta["production_published"])
  self.assertFalse(self.newmeta["receiver_tested"])

 def test_exact_changed_files_and_protected_assets(self):
  self.assertEqual(set(self.newmeta["changed"]),{new.CORE,new.PLUGIN,new.UPDATER})
  for path,raw in self.before.items():
   if path in self.newmeta["changed"]:continue
   self.assertEqual(self.after[path],raw,path)
  self.assertIn("R7612_NORMAL_PREVIEW_PHASE_TIMINGS",self.after[new.CORE].decode())
  self.assertIn("R7613_PREVIEW_SCORING_POSTINGS",self.after[new.CORE].decode())
  self.assertIn("PREVIEW_STAGE",self.after[new.PLUGIN].decode())

 def test_postinst_passive_and_no_hidden_scripts(self):
  self.assertEqual(self.before_ctrl["postinst"],self.after_ctrl["postinst"])
  self.assertEqual(self.after_ctrl["postinst"],old.SAFE_POSTINST)
  self.assertFalse(any(t in self.after_ctrl for t in ("preinst","postrm","prerm")))
  self.assertNotIn("import_spec",self.after_ctrl["postinst"].decode())

 def test_no_changes_outside_exact_methods(self):
  a=ast.parse(self.before[new.CORE].decode());b=ast.parse(self.after[new.CORE].decode())
  def signatures(t):
   out=[]
   for n in ast.walk(t):
    if isinstance(n,ast.FunctionDef):
     out.append((n.name,ast.dump(n,include_attributes=False)))
   return out
  before=signatures(a);after=signatures(b)
  self.assertEqual([n for n,_ in before],[n for n,_ in after])
  changes=[name for (name,o),(name2,p) in zip(before,after) if o!=p]
  self.assertEqual(changes.count("_fast_candidate_pool"),1)
  self.assertEqual(changes.count("_preview_nomination_pool"),1)
  self.assertEqual(changes.count("match_score_details"),1)


if __name__=="__main__":
 unittest.main()
