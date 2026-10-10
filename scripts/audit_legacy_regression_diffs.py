"""Inspect only regression candidate methods across archived builds (AUDIT ONLY)."""
from pathlib import Path
import base64, subprocess, tempfile, tarfile, io, ast, difflib

ROOT=Path(__file__).resolve().parents[1]
sources={}
for v in ("r65","r66-beta","r67-beta","r68-beta","r69-beta"):
    p=ROOT/"payload"/(v+".b64")
    with tempfile.TemporaryDirectory() as td:
        file=Path(td)/"test.ipk"
        file.write_bytes(base64.b64decode(p.read_bytes()))
        data=subprocess.check_output(["ar","p",str(file),"data.tar.gz"])
    with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as t:
        sources[v]={}
        for part in ("core.py","plugin.py","monitor.py"):
            sources[v][part]=t.extractfile("./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"+part).read().decode()

def selected(s,key):
    tree=ast.parse(s)
    cls,name=key.split(".",1) if "." in key else ("",key)
    nodes=tree.body
    if cls:
        candidates=[n for n in nodes if isinstance(n,ast.ClassDef) and n.name==cls]
        if not candidates:return []
        nodes=candidates[0].body
    f=next((n for n in nodes if isinstance(n,ast.FunctionDef) and n.name==name),None)
    return s.splitlines()[f.lineno-1:f.end_lineno] if f else []
sections=[
("r65","r66-beta","plugin.py","_preview_sat_service_rows"),
("r66-beta","r67-beta","plugin.py","SatIPTVBridgePreview._load_selected_sat_candidates"),
("r66-beta","r67-beta","plugin.py","SatIPTVBridgePreview._ensure_full_sat_rows"),
("r67-beta","r68-beta","monitor.py","SatFallbackMonitor._build_candidate_plan"),
("r67-beta","r68-beta","monitor.py","SatFallbackMonitor._handle_iptv_failure"),
("r65","r66-beta","monitor.py","SatFallbackMonitor._on_start"),
]
for left,right,file,fn in sections:
    a=selected(sources[left][file],fn)
    b=selected(sources[right][file],fn)
    print("===== %s > %s %s %s (lines %d -> %d) ====="%
          (left,right,file,fn,len(a),len(b)))
    diff=list(difflib.unified_diff(a,b,fromfile=left,tofile=right,n=3))
    print("\n".join(diff[:105]))
    if len(diff)>105:print("... truncated %d diff lines"%(len(diff)-105))
