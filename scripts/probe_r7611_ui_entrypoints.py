#!/usr/bin/env python3
"""Locate PREVIEW_SAT_COST and Preview opening paths inside actual staged R76.11 IPK.

No receiver access. Read packaged source; print only limited source excerpts.
Does not execute plugin code or access IPTV credentials/mappings.
"""
import ast
import importlib.util
import tempfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r7611_actual_pkg",root/"scripts/build-r7611-preview-cold.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
with tempfile.TemporaryDirectory() as td:
    ipk=Path(td)/"R7611.ipk"
    info=b.build(ipk)
    assert info["version"]=="1.0.46-r76.11-preview-coldstart-fast-beta"
    files=b.pack.members_from(b.pack.unpack_ar(ipk.read_bytes())["data.tar.gz"])
    src=files[b.PLUGIN].decode("utf8")
    lines=src.splitlines()
    patterns=("PREVIEW_SAT_COST","session.open(SatIPTVBridgePreview",
              "session.openWithCallback(","SatIPTVBridgePreview(",
              "_load_selected_sat_candidates()","_sat_selection_changed()",
              "candidate_expand_timer.start(","sat_change_timer.start(",
              "onLayoutFinish.append(")
    indexes=[i for i,line in enumerate(lines) if any(p in line for p in patterns)]
    last_end=-1
    for i in indexes:
        start=max(0,i-5);end=min(len(lines),i+8)
        if start<=last_end:start=last_end+1
        if start>=end:continue
        print(f"PREVIEW_ENTRY_SECTION line={i+1} source={len(lines)}")
        for j in range(start,end):
            print(f"PREVIEW_ENTRY_SOURCE {j+1} {lines[j][:200]}")
        last_end=end-1
    tree=ast.parse(src)
    for node in tree.body:
        if isinstance(node,ast.ClassDef) and node.name in (
          "SatIPTVBridgeDashboard","SatIPTVBridgePreview"):
            print("PREVIEW_CLASS",node.name,node.lineno,node.end_lineno)
            for method in node.body:
                if isinstance(method,ast.FunctionDef) and (
                    method.name in ("__init__","onLayoutFinish") or
                    "preview" in method.name.lower() or
                    "sat_change" in method.name.lower()):
                    print("PREVIEW_CLASS_METHOD",node.name,method.name,
                          method.lineno,method.end_lineno)
