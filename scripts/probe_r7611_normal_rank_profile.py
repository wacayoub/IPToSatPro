#!/usr/bin/env python3
"""Read-only offline R76.11 actual Catalog ranking time-path source audit.

Rebuilds the byte-equivalent staged IPK and prints selected Catalog methods,
then bounded AST metadata about loops and profiling. No receiver data.
"""
import ast,importlib.util,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r7611",R/"scripts/build-r7611-preview-cold.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/"r7611.ipk";meta=b.build(p)
 members=b.pack.members_from(b.pack.unpack_ar(p.read_bytes())["data.tar.gz"])
 src=members[b.CORE].decode("utf8"); lines=src.splitlines(); tree=ast.parse(src)
 cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="Catalog")
 for name in ("fast_rank_matches_all_servers","_preview_nomination_pool",
              "_fast_candidate_pool","_ensure_preview_decorated_index",
              "fast_preview_mega_matches"):
  fn=next((m for m in cls.body if isinstance(m,ast.FunctionDef) and m.name==name),None)
  if fn is None:
   print("PERF_PATH_MISSING",name);continue
  print("PERF_PATH_METHOD",name,"lines",fn.lineno,fn.end_lineno,"count",fn.end_lineno-fn.lineno)
  body=lines[fn.lineno-1:fn.end_lineno]
  for lineno in range(fn.lineno,fn.end_lineno+1):
   line=lines[lineno-1].strip()
   if name in ("fast_rank_matches_all_servers","_preview_nomination_pool"):
    print("PERF_PATH_SOURCE",name,lineno,line[:240])
   elif any(x in line for x in ("_r733_last_profile","_ensure_preview_decorated_index", "for ", "scor", "time.", "index","token", "limit", "budget")):
    print("PERF_PATH_SOURCE",name,lineno,line[:220])
 for f in cls.body:
  if isinstance(f,ast.FunctionDef) and ("profile" in f.name or "rank" in f.name):
   txt=ast.get_source_segment(src,f)
   if "_r733_last_profile" in txt:
    print("PERF_PATH_PROFILE_WRITER",f.name,f.lineno,f.end_lineno)
