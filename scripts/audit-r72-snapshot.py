#!/usr/bin/env python3
"""Read-only inspection of exact published R71.1 cleanup plugin & monitor snapshot."""
import ast,base64,importlib.util
from pathlib import Path
r=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location('r711cleanup',r/'scripts/build-r711-cleanup-beta.py')
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
contents=b.archive.members_from(b.archive.unpack_ar(base64.b64decode((r/'payload/r711-neo-cleanup.b64').read_bytes()))['data.tar.gz'])
for filename in ('plugin.py','monitor.py','core.py'):
    p=b.P+filename
    raw=contents[p].decode()
    tree=ast.parse(raw)
    lines=raw.splitlines()
    print('===FILE',filename,'TOTAL',len(lines))
    for node in tree.body:
        if isinstance(node,ast.ClassDef):
            if filename=='plugin.py' and node.name=='SatIPTVBridgeDashboard':
                for c in node.body:
                    if isinstance(c,ast.FunctionDef) and c.name in ('__init__','_refresh_monitor','_safe_refresh_monitor','_snapshot'):
                        print('===METHOD',filename,node.name,c.name,c.lineno,c.end_lineno)
                        for k in range(c.lineno,c.end_lineno+1):print('CODE',filename,k,lines[k-1])
            if filename=='monitor.py' and node.name=='SatFallbackMonitor':
                for c in node.body:
                    if isinstance(c,ast.FunctionDef) and ('status_snapshot'==c.name or c.name in ('_probe_live_video','_capture_playback_status')):
                        print('===METHOD',filename,node.name,c.name,c.lineno,c.end_lineno)
                        for k in range(c.lineno,c.end_lineno+1):print('CODE',filename,k,lines[k-1])
    if filename=='plugin.py':
        for i,l in enumerate(lines,1):
            if 'DASHBOARD_FHD = ' in l or 'def _theme_skin' in l or 'def presentation_name' in l:
                print('===MARK',filename,i,l[:170])
    if filename=='monitor.py':
        for i,l in enumerate(lines,1):
            if 'def status_snapshot' in l or 'first_frame_ms' in l and ('return ' in l or '"first_frame_ms"' in l):
                print('===MARK',filename,i,l[:190])
print('R72_READ_ONLY_INSPECTION_OK')
