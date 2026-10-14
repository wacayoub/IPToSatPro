#!/usr/bin/env python3
"""Read-only investigation of actual packaged R76 Preview UI ranking/candidates."""
import ast,importlib.util,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r76",root/"scripts"/"build-r76-metrix-preview.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
with tempfile.TemporaryDirectory() as td:
    dest=Path(td)/"r76.ipk";b.build(dest)
    parts=b.pack.members_from(b.pack.unpack_ar(dest.read_bytes())["data.tar.gz"])
    src=parts[b.PLUGIN].decode()
tree=ast.parse(src);cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="SatIPTVBridgePreview")
functions=[n for n in cls.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
print("PREVIEW_METHODS")
for n in functions:
    if any(q in n.name.lower() for q in ["rank","candidate","source","sat","search","render","row","expand","worker","format","cache","display","populate"]):
        print(f"{n.lineno}-{n.end_lineno}: {n.name}")
for n in functions:
    if n.name in ("_load_selected_sat_candidates","_expand_selected_sat_candidates","_render_sources","_render_source_list","_render_candidate_list","_expand_worker_run","_r71_rank_worker","_r71_worker","_r71_rank_candidates","_preview_selected","_build_source_rows","_poll_expanded_candidates","_source_tag","_measured_fastest_and_overall","_measured_best_fps","_sort_candidates_with_cached_evidence","_cached_candidate_evidence","_candidate_decision"):
        print("METHOD_START",n.name,"\n"+ast.get_source_segment(src,n)[:20000]+"\nMETHOD_END")
print("GLOBAL_METHODS")
for n in tree.body:
    if isinstance(n,ast.FunctionDef) and any(q in n.name.lower() for q in ["candidate","source","preview","score","rank"]):
        print(f"{n.lineno}-{n.end_lineno}: {n.name}")
