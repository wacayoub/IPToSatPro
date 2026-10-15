#!/usr/bin/env python3
"""Offline code forensic: trace R76.11 Preview normal/DEEP trigger and cache paths.

Builds the exact hash-pinned beta IPK; prints only excerpts of Python source,
never accesses a receiver or IPTV subscription data. Read-only analysis.
"""
import ast
import importlib.util
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("preview_pkg",ROOT/"scripts/build-r7611-preview-cold.py")
b=importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
TARGETS={
    "SatIPTVBridgePreview":(
        "__init__","_selected_sat_row","_load_selected_sat_candidates",
        "_expand_selected_sat_candidates","_poll_expanded_candidates",
        "_r7413_keep_preview_visible","_r74_filters_active",
        "open","onSelectionChanged","_sat_selection_changed",
        "_r71_deep_search","_r71_deep_selected"),
}
with tempfile.TemporaryDirectory() as d:
    path=Path(d)/"check.ipk"
    meta=b.build(path)
    assert meta["version"]=="1.0.46-r76.11-preview-coldstart-fast-beta"
    fs=b.pack.members_from(b.pack.unpack_ar(path.read_bytes())["data.tar.gz"])
    s=fs[b.PLUGIN].decode("utf8")
    lines=s.splitlines()
    tree=ast.parse(s)
    methods=[]
    for cls in tree.body:
        if not isinstance(cls,ast.ClassDef) or cls.name!="SatIPTVBridgePreview":
            continue
        for f in cls.body:
            if not isinstance(f,ast.FunctionDef):
                continue
            if f.name in TARGETS[cls.name] or any(z in f.name for z in (
                "selected_sat","_preview","_r71","_on_sat","_deep","_expand")):
                methods.append(f)
    print("TRIGGER_METHOD_INDEX",",".join("%s:%s" % (f.name,f.lineno) for f in methods))
    for f in methods:
        if f.name in ("__init__","_expand_selected_sat_candidates","_poll_expanded_candidates"):
            # Excerpts from these large methods only, except exact early exits.
            for lineno in range(f.lineno,f.end_lineno+1):
                line=lines[lineno-1]
                if any(t in line for t in (
                    "candidate_expand_timer","candidate_poll_timer",
                    "PREVIEW_RANK_BG","_preview_candidate_cache_get",
                    "_load_selected_sat_candidates","_expand_selected_sat_candidates",
                    "_closed_for_async","def worker","th.start(",
                    "self._expand_worker","self._expand_result","return",
                    "onSelectionChanged","_preview_candidate_cache_put",
                    "_r71_deep_requested","_r71_deep_target_ref",
                    "_startup_log","_r7413_keep_preview_visible",
                )):
                    print("TRIGGER_SOURCE",f.name,lineno,line.strip()[:230])
        elif f.name in ("_selected_sat_row","_load_selected_sat_candidates",
                        "_r71_deep_search","_r71_deep_selected",
                        "_sat_selection_changed","onSelectionChanged",
                        "_r7413_keep_preview_visible"):
            length=f.end_lineno-f.lineno
            print("TRIGGER_METHOD",f.name,"lines",length)
            for lineno in range(f.lineno,min(f.end_lineno+1,f.lineno+125)):
                print("TRIGGER_SOURCE",f.name,lineno,lines[lineno-1].strip()[:230])
    # The exact top-level cache methods and Preview entry points.
    for node in tree.body:
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and (
            "preview_candidate_cache" in node.name or
            node.name=="_startup_log"):
            print("TRIGGER_HELPER",node.name,node.lineno,node.end_lineno)
            for lineno in range(node.lineno,min(node.end_lineno+1,node.lineno+90)):
                print("TRIGGER_SOURCE",node.name,lineno,lines[lineno-1].strip()[:230])
