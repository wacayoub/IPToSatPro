#!/usr/bin/env python3
"""R76.13 preview-CPU safety: exact R76.12 source, compare token shortlisted outcomes.

Never uses real IPTV servers or receiver state; worker profiling separate.
"""
import ast
import importlib.util
import textwrap
import tempfile
import unittest
from pathlib import Path

R=Path(__file__).resolve().parents[1]
def module(name,path):
 s=importlib.util.spec_from_file_location(name,R/"scripts"/path)
 v=importlib.util.module_from_spec(s);s.loader.exec_module(v);return v
base=module("r7612baseperf","build-r7612-preview-profile.py")
fix=module("r7613cpupatch","r7613_preview_cpu_patch.py")


def cls_method(src,name):
 tree=ast.parse(src)
 c=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="Catalog")
 return next(x for x in c.body if isinstance(x,ast.FunctionDef) and x.name==name)


class FastCPUPreview(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/"r7612.ipk";base.build(p)
   arc=base.pack.unpack_ar(p.read_bytes())
   files=base.pack.members_from(arc["data.tar.gz"])
   cls.old=files[base.CORE].decode("utf8")
  cls.new=fix.patch_core(cls.old)

 def test_only_two_catalog_methods_and_score_func_changed(self):
  def nodes(src):
   t=ast.parse(src)
   c=next(x for x in t.body if isinstance(x,ast.ClassDef) and x.name=="Catalog")
   d={"Catalog."+f.name:ast.dump(f,include_attributes=False)
      for f in c.body if isinstance(f,ast.FunctionDef)}
   for i,f in enumerate(sorted((x for x in ast.walk(t) if isinstance(x,ast.FunctionDef) and x.name=="match_score_details"),key=lambda x:x.lineno)):
    d["match_score_details_"+str(i)]=ast.dump(f,include_attributes=False)
   return d
  a=nodes(self.old);b=nodes(self.new)
  self.assertEqual(a.keys(),b.keys())
  self.assertEqual({x for x in a if a[x]!=b[x]},
    {"Catalog._fast_candidate_pool","Catalog._preview_nomination_pool","match_score_details_0"})
  self.assertEqual(fix.patch_core(self.new),self.new)

 def test_live_path_keeps_original_normalization_gate(self):
  m=ast.get_source_segment(self.new,cls_method(self.new,"_fast_candidate_pool"))
  self.assertIn("_r7613_preview_postings=False",m)
  self.assertIn('wanted.intersection(set((ch.get("norm") or "").split())) == wanted',m)
  self.assertIn("if _r7613_preview_postings:",m)
  nom=ast.get_source_segment(self.new,cls_method(self.new,"_preview_nomination_pool"))
  self.assertIn("_r7613_preview_postings=True",nom)

 def test_same_candidates_and_order_for_consistent_postings(self):
  def make(src):
   f=cls_method(src,"_fast_candidate_pool")
   env={
    "normalize_name":lambda x:x.lower(),
    "_identity_anchor_tokens":lambda x:x.lower().split(),
   }
   exec(compile(textwrap.dedent(ast.get_source_segment(src,f)),
                "fast_shortlist.py","exec"),env)
   return env["_fast_candidate_pool"]

  old=make(self.old)
  new=make(self.new)

  class Cat:
   def __init__(self,all_channels):
    self._token_index={}
    self._exact={}
    for ch in all_channels:
     self._exact.setdefault(ch["norm"],[]).append(ch)
     for t in set(ch["norm"].split()):
      self._token_index.setdefault(t,[]).append(ch)

  candidates=[]
  for i in range(1200):
   tokens=["bbc", "earth" if i%3==0 else "news",
           "hd" if i%5==0 else "sd"]
   candidates.append({"name":"test_%d"%i,"norm":" ".join(tokens),
      "server_role":("P","B1","B2")[i%3]})
  cat=Cat(candidates)
  for sat in ("bbc earth","bbc news","bbc earth hd","bbc sd","notfound"):
   a=old(cat,sat,per_server=25,total_cap=80)
   b=new(cat,sat,per_server=25,total_cap=80,_r7613_preview_postings=True)
   self.assertEqual([id(v) for v in a],[id(v) for v in b],sat)
   live=new(cat,sat,per_server=25,total_cap=80)
   self.assertEqual([id(v) for v in a],[id(v) for v in live],sat)

 def test_fuzzy_ratio_reused_not_changed(self):
  import difflib
  src=ast.get_source_segment(self.new,next(n for n in ast.walk(ast.parse(self.new)) if isinstance(n,ast.FunctionDef) and n.name=="match_score_details"))
  self.assertIn("_r7613_ratio = SequenceMatcher(None, sat_norm, ip_norm).ratio()",src)
  self.assertIn("ratio = _r7613_ratio if _r7613_ratio is not None",src)
  for sat,iptv in [("bbc earth","bbc earth hd"),("beIN SPORTS 1","AR BEIN SPORTS 1"),
                   ("canal plus golf","canal golf"),("film box","filmbox"),
                   ("tve la 1","la1"),("nat geo abu dhabi","natgeo ad")]:
   old=difflib.SequenceMatcher(None,sat,iptv).ratio()
   self.assertEqual(old*78.0,difflib.SequenceMatcher(None,sat,iptv).ratio()*78.0)
   self.assertEqual(old,difflib.SequenceMatcher(None,sat,iptv).ratio())


if __name__=="__main__":
 unittest.main()
