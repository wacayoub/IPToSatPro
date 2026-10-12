#!/usr/bin/env python3
"""Read-only audit of actual R73.4 packaged scoring and lock-selection semantics."""
import ast,importlib.util,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("current",ROOT/"scripts/build-r73-preview.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
with tempfile.TemporaryDirectory() as t:
    p=Path(t)/"x.ipk";b.build(p)
    data=b.base.pack.members_from(b.base.pack.unpack_ar(p.read_bytes())["data.tar.gz"])
    for fname in ["core.py","plugin.py"]:
        src=data[b.P+fname].decode();lines=src.splitlines();tree=ast.parse(src)
        terms=("match_score_details","match_decision","fast_preview_mega_matches",
              "fast_rank_matches","_rank_sat_ref_instant","_candidate_decision",
              "_source_tag","_render_source_list","_sort_candidates_with_cached_evidence",
              "_merge_locked_candidate","_rank_candidates","_lock_selected",
              "_verified_lock","_green_action","_save_override","_sat_selection_changed",
              "_poll_expanded_candidates","_update_header","_auto_lock","_auto_scan",
              "_choose_candidate","_prepare_candidates","_compute_match",
              "_preview_channel_rows","_r732_page_auto")
        for node in ast.walk(tree):
            if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):continue
            if node.name not in terms:continue
            print("SECTION",fname,node.name,node.lineno,node.end_lineno)
            chunk=lines[node.lineno-1:node.end_lineno]
            if len(chunk)>320:
                chunk=chunk[:270]+["# ...TRUNCATED..."]+chunk[-35:]
            for i,ln in enumerate(chunk):
                print(" ",ln)
            print("END_SECTION",fname,node.name)
        for a,b in ([(3270,3435),(5990,6080),(6515,6680)] if fname=="plugin.py" else [(1180,1287),(1950,2095),(3930,4015)]):
            print("RANGE",fname,a,b)
            for ii in range(a-1,min(b,len(lines))): print("%d %s"%(ii+1,lines[ii]))
        for phrase in ("AUTO_LOCK","auto_lock","best_match","match_threshold",
                       "PREVIEW_RANK_BG","CANDIDATES •","SAFE","_manual_candidate",
                       "source_rank","locked_candidate","locked_source"):
            matches=[(i+1,s.strip()) for i,s in enumerate(lines) if phrase in s]
            print("HITS",fname,phrase,len(matches))
            for i,s in matches[:15]:print("HIT",i,s[:180])
