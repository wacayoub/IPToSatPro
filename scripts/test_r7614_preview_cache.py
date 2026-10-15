#!/usr/bin/env python3
"""R76.14 source parity and bounded immutable Preview parsing cache checks."""
import ast,functools,importlib.util,re,tempfile,time,unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,ROOT/"scripts"/path)
 b=importlib.util.module_from_spec(s);s.loader.exec_module(b);return b
base=load("r7613_for_parity","build-r7613-preview-cpu.py")
opt=load("r7614_cached","r7614_preview_cache_patch.py")

class R7614ParseCacheSafety(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  with tempfile.TemporaryDirectory() as td:
   ipk=Path(td)/"old.ipk"
   meta=base.build(ipk)
   assert meta["version"]=="1.0.46-r76.13-preview-cpu-fast-beta"
   old=base.pack.members_from(base.pack.unpack_ar(ipk.read_bytes())["data.tar.gz"])
   cls.old=old[base.CORE].decode("utf8")
   cls.new=opt.patch_core(cls.old)

 def test_exact_only_bounded_decorators(self):
  before=ast.parse(self.old);after=ast.parse(self.new)
  def fnames(tree):
   return {(f.name,f.lineno):f for f in ast.walk(tree) if isinstance(f,ast.FunctionDef)}
  f1={f.name:f for f in ast.walk(before) if isinstance(f,ast.FunctionDef)}
  f2={f.name:f for f in ast.walk(after) if isinstance(f,ast.FunctionDef)}
  self.assertEqual(f1.keys(),f2.keys())
  for name in f1:
   a=f1[name];b=f2[name]
   for old,new in ((ast.dump(x,include_attributes=False),ast.dump(y,include_attributes=False))
                   for x,y in zip(a.body,b.body)):
    self.assertEqual(old,new,name)
   self.assertEqual(len(a.body),len(b.body))
   self.assertEqual(len(b.decorator_list)-len(a.decorator_list),
                    1 if name in opt.PURE_FUNCTIONS else 0,name)
  self.assertEqual(opt.patch_core(self.new),self.new)

 def test_country_parser_returns_identical_values_and_bounded_cache(self):
  def build(src,decorated=False):
   t=ast.parse(src)
   f=next(x for x in ast.walk(t) if isinstance(x,ast.FunctionDef) and x.name=="_r748_explicit_country")
   # Isolate exactly the underlying code, allow only the LRU decorator in new source.
   execmod=ast.Module(body=[f],type_ignores=[])
   ast.fix_missing_locations(execmod)
   env={
    "re":re,
    "_strip_accents":lambda s:s,
    "clean_display_name":lambda s:s,
    "_R748_COUNTRY_LABELS":{"AT":{"AUSTRIA"},"DE":{"GERMANY","DEUTSCHLAND"},
     "FR":{"FRANCE"},"UK":{"UNITED KINGDOM"},"AR":{"ARABIC"},"ES":{"SPAIN"}},
    "_r7614_cached":functools.lru_cache,
   }
   exec(compile(execmod,"pure_helper.py","exec"),env)
   return env["_r748_explicit_country"]
  before=build(self.old)
  after=build(self.new,True)
  cases=["AT: TLC HD","DE: DISCOVERY HD","France 2","BBC Arabic",
         "TLC AUSTRIA","SAT 1","BBC FOOD","UK: BBC EARTH",
         "AR: BEIN SPORTS 1","FILMBOX ONE","ES: HISTORIA",
         "SPORT 1 HD","NATIONAL GEOGRAPHIC","CINEMA 1"]
  for name in cases:
   self.assertEqual(before(name),after(name),name)
  after.cache_clear()
  # Prove repeated parsing of a SAT service is memoized, not repeated.
  for i in range(250):
   self.assertEqual(before(cases[i%len(cases)]),after(cases[i%len(cases)]))
  info=after.cache_info()
  self.assertGreater(info.hits,180)
  self.assertLessEqual(info.currsize,opt.CACHE_MAX)

 def test_one_cached_function_never_returns_mutable(self):
  # Country parser returns tuple of strings; lexical/number helpers return tuples,
  # others return strings. Do not memoize dict/list/set/scorer output.
  self.assertNotIn("match_score_details",opt.PURE_FUNCTIONS)
  self.assertNotIn("_preview_coverage_keys",opt.PURE_FUNCTIONS)
  self.assertNotIn("_enrich_channel",opt.PURE_FUNCTIONS)
  self.assertNotIn("_preview_prefixes",opt.PURE_FUNCTIONS)
  self.assertLessEqual(opt.CACHE_MAX,2048)


if __name__=="__main__":
 unittest.main()
