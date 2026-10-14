#!/usr/bin/env python3
"""Audit active Settings/Menu callbacks from the actual rebuilt R76.6 IPK."""
import ast,importlib.util,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("builder",root/"scripts/build-r76-metrix-preview.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
with tempfile.TemporaryDirectory() as tmp:
 f=Path(tmp)/"ipk";b.build(f)
 parts=b.pack.members_from(b.pack.unpack_ar(f.read_bytes())["data.tar.gz"])
s=parts[b.PLUGIN].decode()
t=ast.parse(s)
for c in t.body:
 if isinstance(c,ast.ClassDef) and ("Settings" in c.name or "Dashboard" in c.name):
  print("CLASS",c.name)
  for n in c.body:
   if not isinstance(n,ast.FunctionDef):continue
   if (c.name.endswith("Settings") and (n.name in ("__init__","_build","_create_setup","_layoutFinished","save","cancel","keySave","keyCancel") or "setup" in n.name.lower() or "mode" in n.name.lower())) or (c.name.endswith("Dashboard") and (n.name in ("open_settings","_r711_tools_choice","_r723_select_home_layout","_r723_set_home_layout","__init__"))):
    src=ast.get_source_segment(s,n)
    if n.name=="__init__" and "Dashboard" in c.name:
     lines=src.splitlines()
     print("METHOD",n.name," relevant lines only")
     print("\n".join(x for x in lines if any(k in x for k in ("self.skin","r76_home","r723_home","self._r76","_theme_skin","ActionMap","onLayoutFinish","init"))))
    else:
     print("METHOD",n.name,"line",n.lineno,n.end_lineno)
     print(src[:22000])
