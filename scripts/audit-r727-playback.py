#!/usr/bin/env python3
"""Audit R72.6 shipped monitor/player playback critical path, without URLs or credentials."""
import ast,base64,hashlib,importlib.util,re
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r726",R/"scripts/build-r726-safe-match.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
raw=base64.b64decode((R/"payload/r726-digi24-safe.b64").read_bytes())
assert hashlib.sha256(raw).hexdigest()=="9b7efbef03368c9a97b86c265574dbd9389401b7d5b014a50e427eaaf267859b"
files=b.pack.members_from(b.pack.unpack_ar(raw)["data.tar.gz"])
words=re.compile(r"IPTV_(?:OK|FAIL)|PLAYER_|first_frame|latency|timeout|attempt|playService|retry|watchdog|player|_play_match|_fallback_if_matched|_on_start|_on_tune_failed|MATCH_BG_START|_queue_background_smartmatch",re.I)
for path,blob in files.items():
 if not path.endswith(".py") or not any(n in path.lower() for n in ("monitor","player","core","plugin","adapter")):continue
 s=blob.decode(errors="replace"); lines=s.splitlines();tree=ast.parse(s)
 print("===FILE",path,"LINES",len(lines))
 methods=[]
 for n in ast.walk(tree):
  if isinstance(n,ast.FunctionDef):
   body="\n".join(lines[n.lineno-1:n.end_lineno])
   if words.search(n.name) or len(words.findall(body))>=3:methods.append(n)
 print("===METHOD_INDEX",[(n.name,n.lineno,n.end_lineno) for n in methods[:160]])
 for n in methods:
  if path.endswith("monitor.py") and (n.name.startswith(("_play","_fallback","_on_start","_on_tune","_start","_player","_iptv","_check","_try","_handle","_retry","_smartmatch")) or n.name in ("_queue_background_smartmatch","_build_candidate_plan")):
   print("===METHOD",n.name,n.lineno,n.end_lineno)
   for i in range(n.lineno-1,n.end_lineno):
    row=lines[i]
    if re.search(r"https?://|password|token=|username|api_key|Authorization",row,re.I):continue
    print("L",i+1,row[:195])
  elif path.endswith("player.py") and n.end_lineno-n.lineno<180:
   print("===METHOD",n.name,n.lineno,n.end_lineno)
   for i in range(n.lineno-1,n.end_lineno):
    row=lines[i]
    if re.search(r"https?://|password|token=|username|api_key|Authorization",row,re.I):continue
    print("L",i+1,row[:195])
 print("===CONSTANTS")
 for i,row in enumerate(lines):
  if words.search(row) and (any(k in row for k in ("timeout","retry","MAX_","PLAYER_","FFMPEG","start("))):
   if not re.search(r"https?://|password|token=|username|api_key|Authorization",row,re.I):print("L",i+1,row[:195])
print("R727_PLAYBACK_AUDIT_DONE")
