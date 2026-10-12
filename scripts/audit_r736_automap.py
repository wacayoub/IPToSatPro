#!/usr/bin/env python3
"""Inspect exactly shipped R73.5 beta AutoScan and Preview auto-mapping flows."""
import ast,importlib.util,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r735",root/"scripts/build-r73-preview.py")
build=importlib.util.module_from_spec(spec);spec.loader.exec_module(build)
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/"r735.ipk";build.build(p)
    memb=build.base.pack.members_from(build.base.pack.unpack_ar(p.read_bytes())["data.tar.gz"])
    for label in ("plugin.py","core.py"):
        lines=memb[build.P+label].decode().splitlines()
        tree=ast.parse("\n".join(lines))
        focus={
        "plugin.py":{
          "_pick_safe","_scan_one","_tick","_commit_auto_scan_overrides","_auto_scan_override_record",
          "_load_overrides","_load_user_rejections","_rank_sat_ref_all_servers",
          "_rank_sat_ref_instant","_merge_locked_candidate","_poll_expanded_candidates",
          "_load_selected_sat_candidates","_start","_start_scan","start_scan",
          "_source_selection_changed","_verified_lock","_do_verified_lock",
          "_green","_update_mapping","_mapping_text","_set_focus",
          "_candidate_decision","_preview_selected"},
        "core.py":{"fast_rank_matches_all_servers","fast_preview_mega_matches",
        "rank_matches_all_servers","match_score_details","match_decision"}
        }[label]
        for node in ast.walk(tree):
            if isinstance(node,ast.FunctionDef) and node.name in focus:
                print("=== %s::%s line %d-%d ==="%(label,node.name,node.lineno,node.end_lineno))
                part=lines[node.lineno-1:node.end_lineno]
                if len(part)>240:part=part[:195]+["  # TRUNCATED"]+part[-25:]
                for i,row in enumerate(part):print("%d %s"%(node.lineno+i,row))
        for pattern in ["_auto_scan_override_record(","_commit_auto_scan_overrides(","start_scan(","_scan_one(","onLayoutFinish.append","AUTO BEST","auto_best_lock","preview_candidate_cache","_store_overrides"]:
            hits=[(idx+1,s.strip()) for idx,s in enumerate(lines) if pattern in s]
            print("HITGROUP",label,pattern,len(hits))
            for pos,txt in hits[:15]:print("HIT",pos,txt[:180])
