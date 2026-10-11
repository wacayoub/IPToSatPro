#!/usr/bin/env python3
"""Read-only R71 UI catalog: print method map and relevant screen/context snippets."""
import ast
import re
from pathlib import Path
from importlib import util

path=Path(__file__).with_name("build-r71-beta.py")
s=util.spec_from_file_location("r71ui_base",path)
m=util.module_from_spec(s);s.loader.exec_module(m)
before=m.members_from(m.unpack_ar(m.get_r70())["data.tar.gz"])
tokens=re.compile(r"preview|browser|dashboard|home|source|all.source|candidate|onselect|on_show|show_", re.I)
for filename, raw in sorted(before.items()):
    if not filename.startswith(m.PREFIX) or not filename.endswith(".py"):continue
    src=raw.decode("utf-8")
    tree=ast.parse(src)
    lines=src.splitlines()
    matches=[]
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef,ast.AsyncFunctionDef)):
            if tokens.search(node.name):matches.append(("func",node.name,node.lineno,node.end_lineno))
        elif isinstance(node,ast.ClassDef):
            if tokens.search(node.name):matches.append(("class",node.name,node.lineno,node.end_lineno))
            for child in node.body:
                if isinstance(child,(ast.FunctionDef,ast.AsyncFunctionDef)) and tokens.search(child.name):
                    matches.append(("method",node.name+"."+child.name,child.lineno,child.end_lineno))
    if matches:print("=== MODULE",filename.removeprefix(m.PREFIX),"TOTAL_LINES",len(lines))
    for kind,name,start,end in matches:print("ENTRY",kind,name,start,end)
    for i,line in enumerate(lines,1):
        if ("all source" in line.lower() or "all_source" in line.lower() or "all sources" in line.lower() or "preview browser" in line.lower()):
            print("LITERAL",filename.removeprefix(m.PREFIX),i,line[:220])
for name, regions in [
    ("plugin.py",[(3513,3570),(3610,3695),(3775,3827),(4818,4990),(5929,5995),(6050,6110),(6252,6362),(7106,7120),(8185,8270)]),
    ("core.py",[(3314,3473)]),
]:
    lines=before[m.PREFIX+name].decode("utf-8").splitlines()
    for start,end in regions:
        print("=== SOURCE",name,start,end)
        for number in range(start,min(end,len(lines))+1):
            print("CODE",name,number,lines[number-1])
print("R71_UI_CATALOG_OK")
