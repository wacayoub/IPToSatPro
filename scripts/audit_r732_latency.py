#!/usr/bin/env python3
"""Read-only R73.1 Preview latency audit using exact verified package build."""
import ast, importlib.util,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r731",ROOT/"scripts/build-r73-preview.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/"beta.ipk";b.build(p)
    data=b.base.pack.members_from(b.base.pack.unpack_ar(p.read_bytes())["data.tar.gz"])
    for filename,method_names in {
        "plugin.py":("_sat_selection_changed","_load_selected_sat_candidates","_load_sat_fast_candidates",
             "_run_sat_match","_render_source_list","_sort_candidates_with_cached_evidence",
             "_preview_channel_rows","_candidate_decision","_render_sat_list","_measured_best_fps","_measured_fastest_and_overall","_refresh_epg_now_next","_refresh_mapping_caches","_source_tag","_update_header","_fast_rank_sat","_r731_start_search","_r731_poll_search","_expand_selected_sat_candidates",
             "_poll_expanded_candidates","_all_sources","_preview_sat_service_rows"),
        "core.py":("_preview_nomination_pool","fast_preview_instant_matches",
            "_fast_candidate_pool","_ensure_manual_indexes","_ensure_preview_decorated_index","_ensure_preview_coverage_indexes","_ensure_preview_provider_index","manual_search")
    }.items():
        source=data[b.P+filename].decode();lines=source.splitlines()
        t=ast.parse(source)
        for node in ast.walk(t):
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in method_names:
                print("\n===== %s::%s (%d-%d) =====" %(filename,node.name,node.lineno,node.end_lineno))
                snippet=lines[node.lineno-1:node.end_lineno]
                if len(snippet)>185:
                    print("\n".join("%d %s"%(j+node.lineno,line) for j,line in enumerate(snippet[:130])))
                    print("... [truncated %d lines] ..."%len(snippet))
                    print("\n".join("%d %s"%(node.end_lineno-40+j,line) for j,line in enumerate(snippet[-41:])))
                else:
                    print("\n".join("%d %s"%(j+node.lineno,line) for j,line in enumerate(snippet)))
