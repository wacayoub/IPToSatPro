#!/usr/bin/env python3
"""R80 nomination-only matching parity and verified avoided work."""
import ast,importlib.util,tempfile,unittest
from pathlib import Path
import test_r7615_preview_index as prior

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r80_focus_patch",ROOT/"scripts/r80_index_focus_patch.py")
patch=importlib.util.module_from_spec(spec);spec.loader.exec_module(patch)
sp=importlib.util.spec_from_file_location("r80_base7615",ROOT/"scripts/build-r7615-preview-index.py")
base=importlib.util.module_from_spec(sp);sp.loader.exec_module(base)

class R80IndexGuardParity(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  with tempfile.TemporaryDirectory() as td:
   f=Path(td)/"old.ipk"
   meta=base.build(f)
   assert meta["version"]=="1.0.46-r76.15-preview-index-fast-beta"
   files=base.pack.members_from(base.pack.unpack_ar(f.read_bytes())["data.tar.gz"])
   cls.old=files[base.CORE].decode("utf8")
  cls.new=patch.patch_core(cls.old)

 def test_only_nomination_method_modified(self):
  def dict_methods(src):
   t=ast.parse(src);c=next(n for n in t.body if isinstance(n,ast.ClassDef) and n.name=="Catalog")
   return {n.name:ast.dump(n,include_attributes=False) for n in c.body if isinstance(n,ast.FunctionDef)}
  old=dict_methods(self.old);new=dict_methods(self.new)
  self.assertEqual(old.keys(),new.keys())
  self.assertEqual({n for n in old if old[n]!=new[n]},{"_preview_nomination_pool"})
  self.assertEqual(patch.patch_core(self.new),self.new)

 def test_candidate_parity_unordered_and_numbered_1600_rows(self):
  rows=[]
  for i in range(1600):
   name=("OSN CINEMA %d"%i if i%5==0 else
         "OSN DOCUMENTARY %d"%i if i%7==0 else
         "BEIN SPORT %d"%i if i%11==0 else
         "OSN HISTORY "+str(i))
   rows.append({"name":name,"norm":" ".join(prior.lex(name)),
      "server_role":("P","B1","B2")[i%3],"provider_family":"OSN",
      "group":"OSN","_preview_numbers":prior.nums(name)})
  before=prior.method(self.old,"_preview_nomination_pool",prior.GLOBALS)
  after=prior.method(self.new,"_preview_nomination_pool",prior.GLOBALS)
  for sat in ("CINEMA","CINEMA 1","OSN CINEMA","SPORT","BEIN SPORT 1",
              "DOCUMENTARY 7","HISTORY 0","NO MATCH"):
   for ready in (False,True):
    c1=prior.FakeCatalog(rows,ready=ready)
    c2=prior.FakeCatalog(rows,ready=ready)
    a=before(c1,sat,context={"provider_family":"OSN","market":"AR"},
             per_server=20,cap=120)
    b=after(c2,sat,context={"provider_family":"OSN","market":"AR"},
            per_server=20,cap=120)
    self.assertEqual([(x["name"],x["server_role"]) for x in a],
                     [(x["name"],x["server_role"]) for x in b],
                     (sat,ready))

 def test_unnumbered_sat_avoids_repeated_candidate_number_parses(self):
  rows=[]
  for i in range(500):
   name="OSN CINEMA" if i%15==0 else "OSN DOCUMENTARY "+str(i)
   rows.append({"name":name,"norm":" ".join(prior.lex(name)),
    "server_role":("P","B1","B2")[i%3],"provider_family":"OSN",
    "group":"OSN","_preview_numbers":()})
  recorded=[]
  for src in (self.old,self.new):
   counts=[0]
   g=dict(prior.GLOBALS)
   def counted(x):
    counts[0]+=1
    return prior.nums(x)
   g["_preview_numbers"]=counted
   fn=prior.method(src,"_preview_nomination_pool",g)
   chosen=fn(prior.FakeCatalog(rows),"CINEMA",
          context={"provider_family":"OSN","market":"AR"},
          per_server=16,cap=100)
   recorded.append(([(x["name"],x["server_role"]) for x in chosen],counts[0]))
  self.assertEqual(recorded[0][0],recorded[1][0])
  self.assertGreater(recorded[0][1],recorded[1][1]+20)

if __name__=="__main__":unittest.main()
