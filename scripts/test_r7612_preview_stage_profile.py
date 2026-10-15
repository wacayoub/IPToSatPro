#!/usr/bin/env python3
"""R76.12 Phase Profiler: semantic/packaging and nonmutation regression tests."""
import ast
import importlib.util
import json
import tempfile
import types
import unittest
from pathlib import Path

R=Path(__file__).resolve().parents[1]
def importfile(name,file):
 spec=importlib.util.spec_from_file_location(name,R/"scripts"/file)
 b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b);return b
base=importfile("baseline7611","build-r7611-preview-cold.py")
prof=importfile("profiler7612","build-r7612-preview-profile.py")


def getmethod(src,name,cls="Catalog"):
 tree=ast.parse(src)
 c=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
 return next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name==name)


class ProfilingSafety(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory()
  p=Path(cls.tmp.name)
  b=p/"old.ipk";n=p/"new.ipk"
  cls.oldmeta=base.build(b)
  cls.newmeta=prof.build(n)
  cls.before=base.pack.members_from(base.pack.unpack_ar(b.read_bytes())["data.tar.gz"])
  cls.after=base.pack.members_from(base.pack.unpack_ar(n.read_bytes())["data.tar.gz"])
  cls.ctrl=base.pack.members_from(base.pack.unpack_ar(n.read_bytes())["control.tar.gz"])
  cls.oldcore=cls.before[prof.CORE].decode("utf8")
  cls.newcore=cls.after[prof.CORE].decode("utf8")
  cls.oldplugin=cls.before[prof.PLUGIN].decode("utf8")
  cls.newplugin=cls.after[prof.PLUGIN].decode("utf8")
 @classmethod
 def tearDownClass(cls):
  cls.tmp.cleanup()

 def test_baseline_identity(self):
  self.assertEqual(self.oldmeta["sha256"],
    "3c3f7b0e623808681884aef4f7975965b2eccdbc224cc4ba0b4393830a7d24d5")
  self.assertEqual(self.newmeta["version"],prof.VERSION)
  self.assertFalse(self.newmeta["production_published"])
  self.assertFalse(self.newmeta["receiver_tested"])

 def test_only_one_catalog_method_changed(self):
  def fmap(src,cls):
   tree=ast.parse(src);klass=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
   return {n.name:ast.dump(n,include_attributes=False) for n in klass.body if isinstance(n,ast.FunctionDef)}
  old=fmap(self.oldcore,"Catalog");new=fmap(self.newcore,"Catalog")
  self.assertEqual(old.keys(),new.keys())
  self.assertEqual({k for k in old if old[k]!=new[k]},{"fast_rank_matches_all_servers"})
  self.assertIn("R7612_NORMAL_PREVIEW_PHASE_TIMINGS",self.newcore)
  m=ast.get_source_segment(self.newcore,getmethod(self.newcore,"fast_rank_matches_all_servers"))
  for term in ("_preview_nomination_pool","match_score_details","_fast_cache_put",
               "nomination_cap","rescue_cap","_context_rank_bands"):
   self.assertIn(term,m)

 def test_only_preview_poll_and_version_in_plugin(self):
  old=ast.parse(self.oldplugin);new=ast.parse(self.newplugin)
  def get_methods(t):
   c=next(n for n in t.body if isinstance(n,ast.ClassDef) and n.name=="SatIPTVBridgePreview")
   return {n.name:ast.dump(n,include_attributes=False) for n in c.body if isinstance(n,ast.FunctionDef)}
  o=get_methods(old);n=get_methods(new)
  self.assertEqual(o.keys(),n.keys())
  self.assertEqual({k for k in o if o[k]!=n[k]},{"_poll_expanded_candidates"})
  self.assertIn('PREVIEW_STAGE',self.newplugin)
  self.assertIn('"rescue_ms"',self.newcore)
  self.assertIn('"sort_ms"',self.newcore)

 def test_protected_assets_byte_identical(self):
  protected=[p for p in self.before if ("player.py" in p or "monitor.py" in p
         or "theme" in p.lower() or "mapping" in p.lower()
         or "override" in p.lower() or "satiptvbridge/cache_migrator" in p.lower())]
  for p in protected:
   self.assertEqual(self.after[p],self.before[p],p)
  self.assertEqual(set(self.newmeta["changed"]),{prof.CORE,prof.PLUGIN,prof.UPDATER})

 def test_postinst_is_passive_and_safe(self):
  post=self.ctrl["postinst"].decode("utf8")
  for token in ("rm ","mv ","chmod ","chown ","python3 ","wget ","curl ","opkg ","import_spec"):
   self.assertNotIn(token,post)
  self.assertNotIn("r62",post)
  self.assertIn("exit 0",post)
  self.assertTrue(self.ctrl["control"].decode().find(prof.VERSION)>0)

 def test_function_returns_identical_ranked_items(self):
  def get_callable(src):
   f=getmethod(src,"fast_rank_matches_all_servers")
   source="def "+ast.get_source_segment(src,f).split("def ",1)[1]
   import textwrap
   script=textwrap.dedent(ast.get_source_segment(src,f))
   funcs={
    "_enrich_channel":lambda ch:dict(ch),
    "match_score_details":lambda sat,ch,langs,context,quality,preview:
       (float(ch.get("score",91)),{"name":99.0,
          "equivalence":0,"variant":0,"provider_identity":False}),
    "match_decision":lambda score,det,threshold:"SAFE",
    "extract_numbers":lambda name:(),
    "_identity_anchor_tokens":lambda name:(),
    "channel_fingerprint":lambda ch:str(ch.get("name")),
    "quality_fit_key":lambda ch,sat,ctx:(0,0),
    "_stream_penalty":lambda ch:0,
   }
   exec(compile(script,"ranking_function.py","exec"),funcs)
   return funcs["fast_rank_matches_all_servers"]
  class Fake:
   _token_index={}
   def __init__(self):
    self.cache=None
   def _fast_cache_key(self,*args):
    return "same_key"
   def _fast_cache_get(self,key):
    return self.cache
   def _fast_cache_put(self,key,rows):
    self.cache=rows
   def _preview_nomination_pool(self,*args,**kwargs):
    return [{"name":"BBC Earth","server_role":"P","score":95},
            {"name":"BBC Earth HD","server_role":"B1","score":94}]
   def server_roles(self):
    return ["P","B1"]
   def _context_rank_bands(self,ch,det,ctx):
    return (0,0,0)
  v11=get_callable(self.oldcore);v12=get_callable(self.newcore)
  o=v11(Fake(),"BBC Earth",context={},per_server=2,topn=2)
  fake=Fake()
  n=v12(fake,"BBC Earth",context={},per_server=2,topn=2)
  self.assertEqual(o,n)
  p=fake._r733_last_profile
  self.assertEqual(p["cache"],0)
  self.assertEqual(p["scored"],2)
  self.assertTrue(all(isinstance(p[k],int) for k in ("index_ms","score_ms",
       "rescue_ms","sort_ms","total_ms")))
  self.assertEqual(v12(fake,"BBC Earth",context={},per_server=2,topn=2),o)
  self.assertEqual(fake._r733_last_profile["cache"],1)


if __name__=="__main__":
 unittest.main()
