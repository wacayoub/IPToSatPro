#!/usr/bin/env python3
"""Read-only forensic audit of matching jobs and tune-failure cycle in deployed R72.4."""
import ast,base64,hashlib,importlib.util,re
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("pkg",R/"scripts/build-r724-zero-signal.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
blob=base64.b64decode((R/"payload/r724-zero-signal.b64").read_bytes())
files=b.pack.members_from(b.pack.unpack_ar(blob)["data.tar.gz"])
pattern=re.compile(r"MATCH_BG_(START|DONE)|_match_background|match_bg|fuzzy|_start_background|_on_tune_failed|_deferred_tune_failed|TUNE_FAIL_DEFER|_background_match|_fallback_if_matched",re.I)
for path,data in files.items():
  if not path.endswith(".py") or not any(x in path for x in ("monitor.py","core.py","plugin.py")):continue
  src=data.decode("utf-8")
  tree=ast.parse(src); lines=src.splitlines()
  relevant=[]
  for node in ast.walk(tree):
    if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
      body="\n".join(lines[node.lineno-1:node.end_lineno])
      if pattern.search(body) or pattern.search(node.name):
        relevant.append((node.lineno,node.end_lineno,node.name))
  print("=== SOURCE",path,"function hits",len(relevant),"total_lines",len(lines))
  for start,end,name in sorted(relevant):
    print("=== METHOD",name,"start",start,"end",end)
    if end-start>240:
      print("=== LARGE: print only focused anchor neighborhoods")
      indices=set()
      for i in range(start-1,end):
        if pattern.search(lines[i]):
          indices.update(range(max(start-1,i-10),min(end,i+16)))
    else:
      indices=set(range(start-1,end))
    for i in sorted(indices):
      v=lines[i]
      if re.search(r"https?://|password|apikey|api_key|token=|username",v,re.I):continue
      print("CODE",i+1,v[:200])
print("R725_FORENSIC_AUDIT_COMPLETE")
