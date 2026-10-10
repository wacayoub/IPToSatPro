#!/usr/bin/env python3
"""Print security-critical FTA/tuner gating call sites from pinned r69 baseline."""
from pathlib import Path
import base64, io, ast, subprocess, tarfile, tempfile, re
root=Path(__file__).resolve().parents[1]
raw=base64.b64decode((root/'payload/r69-beta.b64').read_bytes())
with tempfile.TemporaryDirectory() as td:
 p=Path(td)/'base.ipk';p.write_bytes(raw)
 d=subprocess.check_output(['ar','p',str(p),'data.tar.gz'])
 with tarfile.open(fileobj=io.BytesIO(d),mode='r:gz') as t:
  for fname in ('monitor.py','plugin.py'):
   path='./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/'+fname
   s=t.extractfile(path).read().decode('utf8')
   lines=s.splitlines()
   tree=ast.parse(s)
   print('\n===== FILE',fname,'=====')
   for n in ast.walk(tree):
    if isinstance(n,ast.FunctionDef) and any(term in n.name.lower() for term in ('crypted','tune_failed','fallback_allowed','evaluate','sat_roster','sat_service_rows','load_sat_roster','settings')):
     if n.name.lower() in ('_evaluate','__init__'):
      pass
     else:
      print('METHOD',n.name,'LINES',n.lineno,n.end_lineno)
   targets=['_encrypted_fallback_allowed_once','_on_tune_failed','_deferred_tune_failed_fallback','_evaluate','_on_start','_load_sat_roster_deferred','_ensure_full_sat_rows','_sat_status']
   for n in ast.walk(tree):
    if isinstance(n,ast.FunctionDef) and n.name in targets:
     limit=210 if n.name in ('_evaluate','_on_start') else 115
     print('\nMETHOD-SOURCE',n.name,n.lineno,n.end_lineno)
     for i in range(n.lineno,min(n.end_lineno,n.lineno+limit-1)+1):
      print('%04d '%i+lines[i-1][:185])
   terms=('only_crypted','instant_mapped','is_crypted','tune_failed_fallback','_encrypted_fallback_allowed_once','_preview_sat_service_rows','sIsCrypted')
   print('\nSEARCH-ANCHORS',fname)
   indices=[i for i,l in enumerate(lines) if any(x in l for x in terms)]
   selected=sorted(set(j for i in indices for j in range(max(0,i-2),min(len(lines),i+3))))
   # Only list first 400 to avoid dumping all source in logs
   for i in selected[:400]:
    print('%04d '%(i+1)+lines[i][:185])
   print('ANCHOR TOTAL',len(indices),'window lines',len(selected))
