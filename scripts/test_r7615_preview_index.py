#!/usr/bin/env python3
"""R76.15 nomination-only regression: retain original candidates and order.

Tests full extracted Catalog._preview_nomination_pool with realistic indexed
provider rows; also tests _fast_candidate_pool with stale posting index.
Uses synthetic channels, never real IPTV credentials, no receiver changes.
"""
import ast,importlib.util,tempfile,textwrap,unittest,re
from pathlib import Path
R=Path(__file__).resolve().parents[1]
def mod(name,path):
 s=importlib.util.spec_from_file_location(name,R/"scripts"/path)
 m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
base=mod("r7614_nomination","build-r7614-preview-cache.py")
patch=mod("r7615_nomination","r7615_preview_index_patch.py")

def method(src,name,globals_):
 t=ast.parse(src)
 c=next(x for x in t.body if isinstance(x,ast.ClassDef) and x.name=="Catalog")
 f=next(x for x in c.body if isinstance(x,ast.FunctionDef) and x.name==name)
 d=textwrap.dedent(ast.get_source_segment(src,f))
 ns=dict(globals_)
 exec(compile(d,name+".py","exec"),ns)
 return ns[name]

def lex(name):
 return tuple(re.findall(r"[a-z0-9]+",(name or "").lower()))

def nums(name):
 return tuple(x for x in lex(name) if x.isdigit())

def prefixes(name):
 return set(x[:4] for x in lex(name) if len(x)>=4 and x not in {"live","channel"})

def fp(ch):
 return ch["name"]

GLOBALS={
 "normalize_name":lambda name:" ".join(lex(name)),
 "clean_display_name":lambda x:x,
 "_strip_accents":lambda x:x,
 "_preview_identity_norm":lambda name:" ".join(lex(name)),
 "extract_numbers":nums,
 "quality_info":lambda x:("AUTO",0),
 "_preview_lexical_tokens":lex,
 "_preview_numbers":nums,
 "effective_quality_info":lambda ch:("AUTO",0,"name"),
 "_preview_decorated_source_name":lambda x:x,
 "normalize_preview_name":lambda x:" ".join(lex(x)),
 "CHANNEL_EQUIVALENCE_RULES":[],
 "_equivalence_rule":lambda sat,ch,ctx:None,
 "_preview_compact_key":lambda x:"".join(lex(x)),
 "_preview_abbreviation_key":lambda x:"",
 "_effective_sat_provider_family":lambda sat,ctx:ctx.get("provider_family",""),
 "_preview_provider_stripped_norm":lambda name,fam:" ".join(
    x for x in lex(name) if x not in {fam.lower()}),
 "_preview_prefixes":prefixes,
 "_iptv_provider_family":lambda name:"OSN" if "osn" in lex(name) else "",
 "_GENERIC_IDENTITY_TOKENS":{"live","channel"},
 "_identity_anchor_tokens":lambda name:tuple(lex(name)),
}

class FakeCatalog:
 def __init__(self,channels,ready=True,missing_index=False):
  self.channels=channels;self._preview_coverage_ready=ready
  self._preview_provider_ready=ready
  self._exact={};self._token_index={};self._preview_prefix_index={}
  self._preview_number_index={};self._preview_compact_exact={}
  self._preview_abbrev_index={};self._preview_provider_index={}
  for ch in channels:
   self._exact.setdefault(ch["norm"],[]).append(ch)
   for t in set(ch["norm"].split()):
    self._token_index.setdefault(t,[]).append(ch)
   for p in prefixes(ch["name"]):
    if not missing_index:
     self._preview_prefix_index.setdefault(p,[]).append(ch)
   for n in nums(ch["name"]):
    self._preview_number_index.setdefault(n,[]).append(ch)
   self._preview_compact_exact.setdefault("".join(lex(ch["name"])),[]).append(ch)
   self._preview_provider_index.setdefault("OSN",[]).append(ch)
 def _fast_candidate_pool(self,sat_name,per_server=80,**kw):
  return []
 def _ensure_preview_coverage_indexes(self,allow_scan=False):
  return self._preview_compact_exact,self._preview_abbrev_index,self._preview_prefix_index,self._preview_number_index
 def _ensure_preview_provider_index(self,allow_scan=False):
  return self._preview_provider_index

class NominationOnly(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  with tempfile.TemporaryDirectory() as td:
   ipk=Path(td)/"original.ipk"
   baseline=base.build(ipk)
   assert baseline["version"]=="1.0.46-r76.14-preview-parsecache-beta"
   files=base.pack.members_from(base.pack.unpack_ar(ipk.read_bytes())["data.tar.gz"])
   cls.old=files[base.CORE].decode("utf8")
  at=cls.old.find('if _r7613_preview_postings:')
  at=cls.old.find('for ch in provider_index.get(')
  print('R7615_PROVIDER_ANCHOR_ACTUAL',repr(cls.old[max(0,at-160):at+260]),flush=True)
  cls.new=patch.patch_core(cls.old)
 def test_only_nomination_and_fast_pool_changed(self):
  def fns(src):
   t=ast.parse(src)
   c=next(x for x in t.body if isinstance(x,ast.ClassDef) and x.name=="Catalog")
   return {n.name:ast.dump(n,include_attributes=False)
    for n in c.body if isinstance(n,ast.FunctionDef)}
  a=fns(self.old);b=fns(self.new)
  self.assertEqual(a.keys(),b.keys())
  self.assertEqual({x for x in a if a[x]!=b[x]},
    {"_fast_candidate_pool","_preview_nomination_pool"})
  self.assertEqual(patch.patch_core(self.new),self.new)
  self.assertNotIn("def match_score_details",self.new[self.new.index("R7615_NOMINATION_INDEX_ONLY"):])
 def test_provider_index_superset_same_candidates_order(self):
  channels=[]
  for i in range(800):
   name= "OSN CINEMA" if i%29==0 else "OSN DOCUMENTARY "+str(i)
   channels.append({"name":name,"norm":" ".join(lex(name)),
    "server_role":("P","B1","B2")[i%3],"provider_family":"OSN",
    "group":"OSN","_preview_numbers":nums(name)})
  before=method(self.old,"_preview_nomination_pool",GLOBALS)
  after=method(self.new,"_preview_nomination_pool",GLOBALS)
  for sat in ("CINEMA","CINEMA 1","DOCUMENTARY","OSN CINEMA","NO-MATCH"):
   for ready,missing in ((True,False),(False,True),(True,True)):
    b=FakeCatalog(channels,ready=ready,missing_index=missing)
    c=FakeCatalog(channels,ready=ready,missing_index=missing)
    # Method is bound to Cat instance without using any other real code.
    a=before(b,sat,context={"provider_family":"OSN","market":"AR"},
             per_server=16,cap=84)
    n=after(c,sat,context={"provider_family":"OSN","market":"AR"},
            per_server=16,cap=84)
    self.assertEqual([(x["name"],x["server_role"]) for x in a],
        [(x["name"],x["server_role"]) for x in n],
        (sat,ready,missing,len(a),len(n)))
  b=FakeCatalog(channels)
  a=before(b,"CINEMA",context={"provider_family":"OSN"},per_server=16,cap=84)
  self.assertGreater(len(a),10)
 def test_sparse_and_dense_anchor_preserve_valid_channels(self):
  oldfn=method(self.old,"_fast_candidate_pool",GLOBALS)
  newfn=method(self.new,"_fast_candidate_pool",GLOBALS)
  channels=[]
  for i in range(8000):
   name="osn cinema %d"%i if i%3==0 else "osn sports %d"%i
   channels.append({"name":name,"norm":name,"server_role":("P","B1","B2")[i%3]})
  cat=FakeCatalog(channels)
  for sat in ("osn cinema","osn sports","osn cinema 100","osn", "absent"):
   old=oldfn(cat,sat,per_server=30,total_cap=90)
   new=newfn(cat,sat,per_server=30,total_cap=90,
             _r7613_preview_postings=True)
   self.assertEqual([id(x) for x in old],[id(x) for x in new],sat)
   live=newfn(cat,sat,per_server=30,total_cap=90)
   self.assertEqual([id(x) for x in old],[id(x) for x in live],sat)

if __name__=="__main__":
 unittest.main()
