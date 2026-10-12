#!/usr/bin/env python3
"""Inspect real R73.8 compiled sources to ground R74 patch anchors. No runtime changes."""
import ast, importlib.util, tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("r738",root/"scripts/build-r738-auto-open.py")
b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
with tempfile.TemporaryDirectory() as td:
    p=Path(td)/"source.ipk"
    b.build(p)
    fs=b.b.base.pack.members_from(b.b.base.pack.unpack_ar(p.read_bytes())["data.tar.gz"])
    plugin=fs[b.b.PLUGIN].decode()
    targets={
        "_preview_sat_service_rows","_preview_sat_stats","_preview_sat_rows_cache_key",
        "_preview_sat_disk_load","_preview_sat_disk_save","_preview_channel_rows",
        "_r731_toggle_fta","_r732_page_auto","_r73_page_focused","_render_sat_list","_update_header","_load_sat_roster",
        "_load_sat_rows","_load_sat_roster_deferred","_ensure_full_sat_rows","_sat_selection_changed","_context_for_row_fast","_sat_status","_selected_sat_row","_page_sat","_sat_key",
        "_set_focus","_render_source_list","_candidate_decision","_candidate_status",
        "_poll_expanded_candidates","_expand_selected_sat_candidates","_load_selected_sat_candidates",
        "_sat_roster_tick","_open_auto_scan","_green_action","_start","_display_sort_key",
        "_scan_one","_open_preview_sources_direct","_open_all_sources_direct","_r738_queue_auto_open","_r738_autoplay_current","_r736_choose_best_safe","_match_context_for_sat_ref","_rank_sat_ref_all_servers","_sat_audio_identity","_preview_sat_audio_identity",
    }
    print("IMPORTS BEGIN\n"+"\n".join(plugin.splitlines()[:105])+"\nIMPORTS END")
    for n in ast.walk(ast.parse(plugin)):
        if isinstance(n,ast.FunctionDef) and n.name in targets:
            src=ast.get_source_segment(plugin,n)
            print("\n<<<< "+n.name+" "+str(n.lineno)+" >>>>\n"+src[:15500]+"\n<<<< END "+n.name+" >>>>")
    for n in ast.walk(ast.parse(plugin)):
        if isinstance(n,ast.ClassDef) and n.name=="SatIPTVBridgePreview":
            init=next(x for x in n.body if isinstance(x,ast.FunctionDef) and x.name=="__init__")
            print("PREVIEW_INIT_BEGIN\\n"+(ast.get_source_segment(plugin,init) or "")[:18000]+"\\nPREVIEW_INIT_END")
            print("PREVIEW_METHODS",[(x.name,x.lineno) for x in n.body if isinstance(x,ast.FunctionDef)])

    core=fs[b.b.CORE].decode()
    for n in ast.walk(ast.parse(core)):
        if isinstance(n,ast.FunctionDef) and n.name=="infer_sat_context":
            excerpt=ast.get_source_segment(core,n) or ""
            print("INFER_SAT_CONTEXT_BEGIN\\n"+excerpt[:17500]+"\\nINFER_SAT_CONTEXT_END")

    # R74.2 crash audit: show all callbacks and exact closing handler
    for line_no,line in enumerate(plugin.splitlines(),1):
        if "openWithCallback(" in line or "_direct_preview_done" in line or "callback=" in line:
            print("OPEN_CALLBACK",line_no,repr(line[:200]))
    for n in ast.walk(ast.parse(plugin)):
        if isinstance(n,ast.FunctionDef) and n.name in ("_direct_preview_done","_open_preview_sources_direct","_restore","_close_no_save"):
            print("CRASH_HANDLER",n.name,ast.get_source_segment(plugin,n)[:12000])
