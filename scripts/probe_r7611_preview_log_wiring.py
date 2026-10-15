#!/usr/bin/env python3
"""Inspect EXACT R76.11 packaged Preview logger wiring, offline, no receiver access."""
import ast
import importlib.util
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r7611_log_builder",ROOT/"scripts/build-r7611-preview-cold.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
with tempfile.TemporaryDirectory() as d:
    p=Path(d)/"candidate.ipk"
    b.build(p)
    files=b.pack.members_from(b.pack.unpack_ar(p.read_bytes())["data.tar.gz"])
    for path in (b.PLUGIN,b.CORE,b.P+"monitor.py"):
        code=files[path].decode("utf8")
        lines=code.splitlines()
        tree=ast.parse(code)
        print("R7611_WIRING_MODULE",path,"lines",len(lines))
        for idx,line in enumerate(lines):
            if any(x in line for x in (
                    "PREVIEW_RANK_BG","MATCH_BG_DONE","_poll_expanded_candidates",
                    "_expand_selected_sat_candidates","_r71_worker_deep",
                    "bridge.log","_bridge_log(", "log_event(")):
                print("R7611_WIRING_HIT",path,idx+1,line.strip()[:210])
        for klass in tree.body:
            if not isinstance(klass,ast.ClassDef) or klass.name not in (
                    "SatIPTVBridgePreview","Catalog"):
                continue
            for fn in klass.body:
                if not isinstance(fn,ast.FunctionDef) or fn.name not in (
                    "_poll_expanded_candidates","_expand_selected_sat_candidates",
                    "fast_rank_matches_all_servers"):
                    continue
                if klass.name=="Catalog":continue
                print("R7611_WIRING_METHOD",klass.name,fn.name,
                      fn.lineno,fn.end_lineno)
                chunk=lines[fn.lineno-1:fn.end_lineno]
                for i,line in enumerate(chunk):
                    print("R7611_WIRING_SOURCE",fn.lineno+i,line[:230])
