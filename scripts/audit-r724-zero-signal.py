#!/usr/bin/env python3
"""Inspect the released IPK's no-signal paths without revealing credentials."""
import ast,base64,hashlib,importlib.util,re
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("release",root/"scripts/build-r723-classic-fusion.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
raw=base64.b64decode((root/"payload/r723-neo-classic-premium.b64").read_bytes())
assert hashlib.sha256(raw).hexdigest()=="b76e9fb551cef1d0422d6303f3d74e38b94cadae6fda6b6f90d6eecf7739afa3"
files=b.pack.members_from(b.pack.unpack_ar(raw)["data.tar.gz"])
for path,data in files.items():
  if not path.endswith((".py",".sh")):continue
  if not any(word in path for word in ("monitor","plugin","core","service","adapter")):continue
  s=data.decode("utf-8",errors="replace")
  lines=s.splitlines()
  hits=[]
  patterns=[r"FTA_FALLBACK_BLOCK",r"SAT_TUNE_FAILED",r"TUNE_FAIL",r"sat_shadow_lock",r"no_signal",r"no_sat",r"fta_",r"_on_tune",r"tune_failed",r"signal.*0",r"fallback_block",r"signal_failure"]
  for i,line in enumerate(lines):
    if any(re.search(p,line,re.I) for p in patterns):hits.append(i)
  if not hits:continue
  print("=== FILE",path,"TOTAL",len(lines),"HITS",len(hits))
  # capture focused contexts; avoid spilling confidential stream URLs.
  selected=set()
  for idx in hits[:85]:
    for j in range(max(0,idx-10),min(len(lines),idx+18)):
      selected.add(j)
  for j in sorted(selected):
    text=lines[j]
    if any(term in text.lower() for term in ("http://","https://","password","username","token","api_key","auth=")):continue
    print("L",j+1,text[:230])
  print("=== END",path)
print("R724_AUDIT_COMPLETE")
