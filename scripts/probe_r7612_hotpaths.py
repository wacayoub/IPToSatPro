#!/usr/bin/env python3
"""Offline R76.12 exact assembled-IPK source profiling, read-only.

Outputs only source code at hot paths, never accesses any receiver data.
"""
import ast,importlib.util,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r7612",R/"scripts/build-r7612-preview-profile.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/"r7612.ipk";b.build(p)
 members=b.pack.members_from(b.pack.unpack_ar(p.read_bytes())["data.tar.gz"])
 core=members[b.CORE].decode();tree=ast.parse(core);lines=core.splitlines()
 names=("match_score_details","_enrich_channel","_fast_candidate_pool","_ensure_preview_coverage_indexes","_ensure_preview_provider_index",
        "_identity_anchor_tokens","normalize_name","_context_rank_bands","_preview_nomination_pool",
        "fast_rank_matches_all_servers","_preview_prefixes","_preview_numbers",
        "_preview_provider_stripped_norm","_preview_identity_norm")
 for name in names:
  node=None
  for n in ast.walk(tree):
   if isinstance(n,ast.FunctionDef) and n.name==name:
    node=n;break
  if node is None:
   print("HOTPATH_MISSING",name)
   continue
  depth=node.end_lineno-node.lineno+1
  print("HOTPATH_FUNC",name,node.lineno,node.end_lineno,"length",depth)
  if name in ("match_score_details","_enrich_channel","_fast_candidate_pool",
              "_ensure_preview_coverage_indexes","_ensure_preview_provider_index",
              "_context_rank_bands","_preview_prefixes","_preview_numbers",
              "_preview_provider_stripped_norm","_preview_identity_norm"):
   for ln in range(node.lineno,node.end_lineno+1):
    print("HOTPATH_SRC",name,ln,lines[ln-1][:240])
  else:
   for ln in range(node.lineno,node.end_lineno+1):
    line=lines[ln-1].strip()
    if any(t in line for t in ("for ","def ","if ","_index","return ","self._","_preview_")):
     print("HOTPATH_ANCHOR",name,ln,line[:220])
