#!/usr/bin/env python3
"""Read-only inspection of the real packaged Enigma2 Preview screen. No secrets."""
import ast,base64,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("base",ROOT/"scripts/build-r727-fast.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
arc=b.pack.members_from(b.pack.unpack_ar(base64.b64decode((ROOT/"payload/r727-fuzzy-cache.b64").read_bytes()))["data.tar.gz"])
src=arc[b.P+"plugin.py"].decode()
lines=src.splitlines()
tree=ast.parse(src)
print("SOURCE lines",len(lines))
for node in tree.body:
    if isinstance(node,ast.Assign) and any(isinstance(x,ast.Name) and x.id == "PREVIEW_FHD" for x in node.targets):
        print("PREVIEW_SKIN",ast.unparse(node)[:25000])
    if isinstance(node,ast.ClassDef) and node.name in ("SatIPTVBridgePreview","PreviewBrowserList"):
        print("CLASS",node.name,node.lineno,node.end_lineno)
for start,end in [(5028,5168),(5168,5355),(6487,6550),(6749,6805),(6939,7065),(7410,7470)]:
    print("SECTION",start,end)
    for n in range(start,min(end+1,len(lines)+1)):
        print("%04d %s"%(n,lines[n-1]))
