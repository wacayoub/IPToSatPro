#!/usr/bin/env python3
"""Audit call graph of the *packaged* R76.10 Catalog ranking methods."""
import ast
import importlib.util
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r7610probe",ROOT/"scripts/build-r7610-normal48.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp)/"candidate.ipk"
    b.build(p)
    members=b.pack.members_from(b.pack.unpack_ar(p.read_bytes())["data.tar.gz"])
    core=members[b.CORE].decode()
    tree=ast.parse(core)
    catalog=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="Catalog")
    for name in ("fast_rank_matches_all_servers","_preview_nomination_pool","fast_preview_mega_matches","_fast_candidate_pool"):
        method=next((x for x in catalog.body if isinstance(x,ast.FunctionDef) and x.name==name),None)
        if method is None:
            print("R7610_PROBE MISSING",name)
            continue
        body=ast.get_source_segment(core,method)
        calls=sorted(set(
            ast.unparse(x.func) for x in ast.walk(method) if isinstance(x,ast.Call)
            and ("rank" in ast.unparse(x.func) or "preview" in ast.unparse(x.func)
                 or "candidate" in ast.unparse(x.func))
        ))
        print("R7610_PROBE",name,"lines",method.lineno,method.end_lineno,"calls",calls)
        print("R7610_SOURCE",name,body[:12000])
