#!/usr/bin/env python3
"""Inspect exact bundled R72.5 matching thresholds with no customer credentials."""
from pathlib import Path
import ast,base64,hashlib,importlib.util,re
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r725",root/"scripts/build-r725-fuzzy.py")
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
binary=base64.b64decode((root/"payload/r725-fuzzy-stability.b64").read_bytes())
assert hashlib.sha256(binary).hexdigest()=="f4b1c1ab8a23ced1856e95b2481b70e6fbb245af3cd5b36fb0d63a3d3a5983f5"
files=mod.pack.members_from(mod.pack.unpack_ar(binary)["data.tar.gz"])
for p,blob in files.items():
  if not p.endswith(".py") or not p.endswith(("monitor.py","core.py","plugin.py")):continue
  t=blob.decode()
  tree=ast.parse(t); lines=t.splitlines()
  print("FILE",p,"length",len(lines))
  for n in ast.walk(tree):
    if isinstance(n,ast.FunctionDef) and (
        "score" in n.name or "candidate" in n.name or "threshold" in n.name or "match" in n.name
      ):
      if n.end_lineno-n.lineno>190:
        chosen={i for i in range(n.lineno-1,n.end_lineno)
          if re.search(r"threshold|quality_mode|no_match|identity|market|score|candidate|ranked|lang|smartmatch",lines[i],re.I)}
        ctx=set()
        for i in chosen:
          ctx.update(range(max(n.lineno-1,i-4),min(n.end_lineno,i+6)))
      else:ctx=set(range(n.lineno-1,n.end_lineno))
      if ctx:
        print("METHOD",n.name,n.lineno,n.end_lineno)
        for i in sorted(ctx):
          line=lines[i]
          if re.search(r"https?://|password|username|api_key|token=|auth=",line,re.I):continue
          print("L",i+1,line[:190])
print("R726_MATCH_AUDIT_OK")
