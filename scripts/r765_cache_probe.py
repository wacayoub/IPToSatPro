#!/usr/bin/env python3
"""Detailed no-network inspection of real R76 package candidate index/scoring/caching paths."""
import ast,importlib.util,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r765",root/"scripts/build-r76-metrix-preview.py")
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
with tempfile.TemporaryDirectory() as td:
    f=Path(td)/"ipk";build.build(f)
    parts=build.pack.members_from(build.pack.unpack_ar(f.read_bytes())["data.tar.gz"])
for file in (build.PLUGIN,build.base.CORE):
    s=parts[file].decode("utf-8");tree=ast.parse(s)
    print("=== FILE",file,len(s.splitlines()))
    for klass in tree.body:
        if not isinstance(klass,ast.ClassDef):continue
        for n in klass.body:
            if not isinstance(n,ast.FunctionDef):continue
            if n.name in ("_expand_selected_sat_candidates","_poll_expanded_candidates","_load_selected_sat_candidates",
                          "_r71_rank_worker","_r71_rank_candidates","fast_preview_mega_matches",
                          "_fast_candidate_pool","_fast_cache_key","_fast_cache_get",
                          "_fast_cache_put","_ensure_preview_coverage_indexes",
                          "_ensure_preview_decorated_index","_ensure_preview_provider_index"):
                print("=== METHOD",klass.name,n.name,n.lineno,n.end_lineno)
                lines=ast.get_source_segment(s,n).splitlines()
                for pos,line in enumerate(lines):
                    if n.name in ("_expand_selected_sat_candidates","_poll_expanded_candidates","_load_selected_sat_candidates",
                                  "_fast_cache_get","_fast_cache_key","_fast_cache_put"):
                        print("%3d %s"%(pos+1,line))
                    elif any(t in line for t in ("for ", "sort", "match_score_details", "cache", "return","time.",
                                   "normalize","index","_fast_candidate_pool","_ensure_preview",
                                   "_candidate_pool","_token_index","rank_matches")):
                        print("%3d %s"%(pos+1,line))
                print("===END")
