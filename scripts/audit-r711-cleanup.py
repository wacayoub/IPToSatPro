#!/usr/bin/env python3
import ast,base64,importlib.util,re
from pathlib import Path
r=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r711base",r/"scripts/build-r711-neo-home.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
raw=base64.b64decode((r/"payload/r711-neo-home-beta.b64").read_bytes())
files=b.archive.members_from(b.archive.unpack_ar(raw)["data.tar.gz"])
src=files[b.PLUGIN].decode()
lines=src.splitlines()
tree=ast.parse(src)
for node in tree.body:
 if isinstance(node,ast.FunctionDef) and any(x in node.name for x in ("theme_skin","picon_path","open_plugin")):
  print("FUNC",node.name,node.lineno,node.end_lineno)
  for i in range(node.lineno,min(node.end_lineno,node.lineno+90)+1):print("CODE",i,lines[i-1])
 if isinstance(node,ast.ClassDef) and node.name in ("SatIPTVBridgeDashboard","SatIPTVBridgeSettings","SatIPTVBridgeSafeDiagnostics"):
  print("CLASS",node.name,node.lineno,node.end_lineno)
  for method in node.body:
   if isinstance(method,ast.FunctionDef):
    print("METHOD",method.name,method.lineno,method.end_lineno)
    if method.name in ("__init__","open_settings","_layout_ready","keyMenu","_create_list","createSetup","_save","_refresh_monitor"):
     for i in range(method.lineno,min(method.end_lineno,method.lineno+85)+1):print("CODE",i,lines[i-1])
for term in ("class ChoiceBox","def open_settings","def _theme_skin","PLUGIN_PATH","SKIN","showDetails"):
 for i,x in enumerate(lines):
  if term in x:print("HIT",term,i+1,x[:200])
print("INSPECT_CLEANUP_DONE")
