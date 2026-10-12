#!/usr/bin/env python3
"""Read-only AST dump of actual R73.3 package: Preview first-open, decoder video evidence."""
import ast,importlib.util,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("build733",ROOT/"scripts/build-r73-preview.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp)/"r733.ipk";b.build(p)
    items=b.base.pack.members_from(b.base.pack.unpack_ar(p.read_bytes())["data.tar.gz"])
    src=items[b.PLUGIN].decode()
    tree=ast.parse(src);lines=src.splitlines()
    wanted = {
        "_start","_sat_selection_changed","_load_selected_sat_candidates",
        "_expand_selected_sat_candidates","_poll_expanded_candidates",
        "_preview_selected","_preview_finished","_preview_finished_callback",
        "_quality_record_text","_quality_checklist_text","_health_record",
        "_preview_success","_preview_done","_poll","_preview_player_active",
        "_preview_quality_verified","_dimensions","_read_video_dimensions",
        "_refresh_mapping_caches","_render_source_list","_update_header",
        "_preview_target_quality","_set_focus","_source_selection_changed",
        "_merge_locked_candidate","_startup_log"}
    for n in ast.walk(tree):
        if isinstance(n,ast.ClassDef) and ("Preview" in n.name or "Browser" in n.name):
            print("CLASS",n.name,"line",n.lineno)
        if isinstance(n,ast.FunctionDef) and n.name in wanted:
            print("\n===== %s lines %d-%d ====="%(n.name,n.lineno,n.end_lineno))
            for i in range(n.lineno-1,min(n.end_lineno,n.lineno+165)):
                print("%d %s"%(i+1,lines[i]))
            if n.end_lineno-n.lineno>165:
                print("TRUNCATED",n.end_lineno)
    for pattern in ("NON MESUREE","measured_resolution","measured_width","video_width",
                    "video_height","last_dims","PREVIEW_RANK_BG","_preview_target_quality",
                    "_preview_results","_preview_candidate_cache_get"):
        found=[(i+1,line) for i,line in enumerate(lines) if pattern in line]
        print("PATTERN",pattern,"COUNT",len(found))
        for ln,t in found[:26]: print("MATCH",ln,t[:230])
