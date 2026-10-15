#!/usr/bin/env python3
"""Inspect pure helper shapes used > 100 times per Preview rank (offline R76.13)."""
import ast,importlib.util,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("buildR7613",root/"scripts/build-r7613-preview-cpu.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
with tempfile.TemporaryDirectory() as td:
 p=Path(td)/"candidate.ipk";b.build(p)
 src=b.pack.members_from(b.pack.unpack_ar(p.read_bytes())["data.tar.gz"])[b.CORE].decode()
 lines=src.splitlines()
 t=ast.parse(src)
 needed={"_preview_lexical_tokens","normalize_preview_name","_preview_compact_key","_preview_abbreviation_key","_preview_coverage_keys","_r748_country_relation","_r749_reordered_identity","_equivalence_rule","_r735_numbered_live_subservice","_variant_tokens","_token_overlap","_dynamic_priorities","_preview_numbers","_preview_identity_norm","quality_info","hdr_info","_preview_provider_stripped_norm","_effective_sat_provider_family","_r748_explicit_country"}
 for n in ast.walk(t):
  if not isinstance(n,ast.FunctionDef) or n.name not in needed:continue
  print("CPU_HELPER",n.name,n.lineno,n.end_lineno,"lines",n.end_lineno-n.lineno)
  if n.end_lineno-n.lineno<75:
   for x in range(n.lineno,n.end_lineno+1):
    print("CPU_SOURCE",n.name,x,lines[x-1][:240])
  else:
   for x in range(n.lineno,min(n.lineno+16,n.end_lineno+1)):
    print("CPU_SOURCE",n.name,x,lines[x-1][:240])
