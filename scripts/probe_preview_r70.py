#!/usr/bin/env python3
"""Audit actual Preview Browser code inside SHA-pinned r69 payload; no receiver/streams."""
from pathlib import Path
import ast,base64,io,subprocess,tarfile,tempfile,re
R=Path(__file__).resolve().parents[1]
raw=base64.b64decode((R/"payload/r69-beta.b64").read_bytes())
with tempfile.TemporaryDirectory() as td:
 p=Path(td)/"base.ipk";p.write_bytes(raw)
 gz=subprocess.check_output(["ar","p",str(p),"data.tar.gz"])
with tarfile.open(fileobj=io.BytesIO(gz),mode="r:gz") as t:
 s=t.extractfile("./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/plugin.py").read().decode()
lines=s.splitlines()
tree=ast.parse(s)
for cls in tree.body:
 if isinstance(cls,ast.ClassDef) and ("Preview" in cls.name or "Alternatives" in cls.name):
  print("CLASS",cls.name,"at",cls.lineno,"through",cls.end_lineno)
  for n in cls.body:
   if isinstance(n,ast.FunctionDef):
    print(" METHOD",n.name, "line", n.lineno, "span", n.end_lineno-n.lineno+1,
          "params",",".join(x.arg for x in n.args.args))
for n in tree.body:
 if isinstance(n,ast.FunctionDef) and any(k in n.name.lower() for k in ("rank","candidate","source","preview","alternatives")):
  print("GLOBAL",n.name,n.lineno,n.end_lineno-n.lineno+1)
want=("_render_sat_list","_render_source_list","_render","_on_sat_changed","_on_source_changed",
      "_load_sources","_refresh_mapping_caches","_update_selected_picon",
      "_page_up","_page_down","_open_preview","_all_sources","_sat_changed")
for cls in tree.body:
 if isinstance(cls,ast.ClassDef) and ("Preview" in cls.name or "Alternatives" in cls.name):
  for n in cls.body:
   if isinstance(n,ast.FunctionDef) and (n.name in want or n.name=="__init__"):
    print("SOURCE",cls.name,n.name)
    bound=85 if n.name!="__init__" else 95
    for line in range(n.lineno,min(n.end_lineno,n.lineno+bound-1)+1):
     print("%d: %s"%(line,lines[line-1][:210]))
