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

    monitor=fs[b.b.P+"monitor.py"].decode()
    tree=ast.parse(monitor)
    monitor_lines=monitor.splitlines()
    targets=("FTA_FALLBACK_BLOCK","_static_crypted_state","crypted_state","FAST_MAP_FIRE","DVB_PAT_GUARD","_read_crypt","_encrypted_fallback_allowed_once","_on_sat_check","_check_sat","_is_crypted","_on_tune_failed")
    for token in targets:
        matching=[i for i,line in enumerate(monitor_lines) if token in line]
        print("CRYPT_AUDIT_TOKEN",token,len(matching))
        for i in matching[:5]:
            print("CRYPT_AUDIT_WINDOW",token,i+1)
            for j in range(max(0,i-15),min(len(monitor_lines),i+24)):
                print("SRC",j+1,monitor_lines[j])
    for n in ast.walk(tree):
        if isinstance(n,ast.FunctionDef) and any(tag in n.name.lower() for tag in ("crypt","fast_map","guard","tuner","sat_check","isfta","signal","dvb")):
            print("CRYPT_AUDIT_FUNCTION",n.name,n.lineno,n.end_lineno)

    for n in ast.walk(tree):
        if isinstance(n,ast.FunctionDef) and n.name in (
            "_static_crypted_state_fast","_encrypted_fallback_allowed_once",
            "_is_crypted","_start","_check","_sat_tuner_state",
            "_fast_map_fire","_manual_lock_saved_access","_native_pat_guard_remaining_ms",
            "_dvb_access_key","_on_tuned","_fallback_with_native_pat_guard"):
            snippet=ast.get_source_segment(monitor,n) or ""
            print("CRYPT_FULL_FUNCTION",n.name,"BEGIN")
            print(snippet[:18500])
            print("CRYPT_FULL_FUNCTION",n.name,"END")

    for n in ast.walk(tree):
        if isinstance(n,ast.FunctionDef) and n.name in ("_poll","_on_service_start","_on_service_started","_sat_tuner_state","_fallback_if_matched","_fallback_with_native_pat_guard","_on_tune_failed","_deferred_tune_failed","_on_tuned","_start_guard"):
            body=ast.get_source_segment(monitor,n) or ""
            print("R744_FUNCTION",n.name,"BEGIN")
            print(body[:17500])
            print("R744_FUNCTION",n.name,"END")
    for i,line in enumerate(monitor_lines):
        if "timer = eTimer()" in line or "_fallback_crypto_gate = None" in line or "current_sat_started_at = " in line:
            print("R744_INIT",i+1,monitor_lines[max(0,i-4):i+6])

    for token in ('SAT_START','SAT_TUNED','_fallback_crypto_gate = None','_fallback_with_native_pat_guard()','NO_SIGNAL_FTA_IPTV_ALLOWED','FAST_MAP_ARM','_on_start('):
        indexes=[i for i,line in enumerate(monitor_lines) if token in line]
        for i in indexes[:5]:
            print("R744_WINDOW",token,"INDEX",i+1)
            print("\\n".join("%d %s"%(j+1,monitor_lines[j]) for j in range(max(0,i-13),min(i+22,len(monitor_lines)))))

    interested=("TUNE_FAIL_DEFER_MS","TUNE_FAIL_DEFER","tune_fail_defer","TUNER_RECHECK_MS","_deferred_tune_failed",
      "_tune_fail_defer_fire","_native_pat_guard_fire","_native_pat_guard_remaining_ms",
      "SAT_NO_SIGNAL","FAST_NO_SIGNAL","_on_start","_poll","_arm_native_pat_poll")
    for word in interested:
        hits=[i for i,t in enumerate(monitor_lines) if word in t]
        print("R745_WORD",word,"hits",len(hits))
        for i in hits[:5]:
            print("R745_HIT",word,i+1,
                  " ".join(monitor_lines[max(0,i-4):min(len(monitor_lines),i+6)]))
    for n in ast.walk(tree):
        if isinstance(n,ast.FunctionDef) and (n.name in
            ("_tune_fail_defer_fire","_on_tune_failed","_fallback_with_native_pat_guard",
             "_native_pat_guard_fire","_arm_native_pat_poll","_poll","_start_guard",
             "_on_service_event","_on_start")):
            body=ast.get_source_segment(monitor,n) or ""
            print("R745_FUN",n.name,"BEGIN")
            print(body[:24000])
            print("R745_FUN",n.name,"END")

    for n in ast.walk(tree):
        if isinstance(n,ast.FunctionDef) and n.name in (
          "_deferred_tune_failed_fallback","_on_start","_check_tuner_and_signal",
          "_poll","_native_pat_guard_remaining_ms","_fast_map_fire","_poll_sat",
          "_on_service_event"):
            print("R745_FINAL_METHOD",n.name,"BEGIN")
            print((ast.get_source_segment(monitor,n) or "")[:21000])
            print("R745_FINAL_METHOD",n.name,"END")
    for word in ("_fallback_if_matched()","tune_fail_defer_timer","_static_crypto_cache","TUNER_MAX_RECHECKS","FAST_MAPPED_DELAY_MS","NATIVE_PAT_GUARD_MS"):
        hits=[i for i,x in enumerate(monitor_lines) if word in x]
        for i in hits[:6]:
            print("R745_ANCHOR",word,i+1)
            print("\\n".join("%d %s"%(j+1,monitor_lines[j]) for j in range(max(0,i-6),min(i+12,len(monitor_lines)))))
