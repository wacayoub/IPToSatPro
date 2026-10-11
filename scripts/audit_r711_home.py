#!/usr/bin/env python3
"""Inspect source of released R71 UI Home skin and data binding, no modifications."""
import ast,base64,importlib.util,re
from pathlib import Path
R=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('b',R/'scripts/build-r71-ui-beta.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
raw=base64.b64decode((R/'payload/r71-ui-beta.b64').read_bytes())
data=b.base.members_from(b.base.unpack_ar(raw)['data.tar.gz'])
s=data[b.PATH].decode();lines=s.splitlines()
tree=ast.parse(s)
for node in tree.body:
    if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('DASHBOARD_FHD','PREVIEW_FHD') for t in node.targets):
        var=next(t.id for t in node.targets if isinstance(t,ast.Name))
        try:render=ast.literal_eval(node.value)
        except Exception as e:render='AST ERROR '+str(e)
        print('===== SKIN',var,'LENGTH',len(render),'LINES',render.count('\n')+1)
        for i,line in enumerate(render.splitlines(),1):print('SKIN',var,i,line)
for first,last in [(1350,1410),(1460,1540),(3495,3557),(3590,3700),(3720,3788),(3790,3835),(2180,2284)]:
    print('===== CODE',first,last)
    for i in range(first,last+1):
        if i<=len(lines):print('CODE',i,lines[i-1])
print('R711_INSPECTION_DONE')
