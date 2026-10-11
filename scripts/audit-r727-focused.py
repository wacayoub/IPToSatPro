#!/usr/bin/env python3
"""Focused exact shipped R72.6 matching and decoder timings audit."""
from pathlib import Path
import base64,hashlib,importlib.util,ast,re
R=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r726",R/"scripts/build-r726-safe-match.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
raw=base64.b64decode((R/"payload/r726-digi24-safe.b64").read_bytes())
parts=b.pack.members_from(b.pack.unpack_ar(raw)["data.tar.gz"])
for fname in ("core.py","monitor.py"):
 name=b.P+fname;src=parts[name].decode();lines=src.splitlines()
 tree=ast.parse(src)
 for n in ast.walk(tree):
  if not isinstance(n,ast.FunctionDef):continue
  if n.name not in {"rank_matches","fast_rank_matches","match_score_details",
    "_smartmatch_poll","_accept_verified_video","_verify_iptv","_schedule_next_candidate",
    "_record_health","_video_timeout_ms","_fallback_if_matched","_set_state"}:continue
  print("=== METHOD",fname,n.name,n.lineno,n.end_lineno)
  for i in range(n.lineno-1,n.end_lineno):
   line=lines[i]
   if re.search(r"https?://|password|username|api_key|token=",line,re.I):continue
   print("CODE",i+1,line[:230])
print("R727_DEEP_MATCH_AND_VIDEO_AUDIT_DONE")
