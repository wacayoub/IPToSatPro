#!/usr/bin/env python3
"""R80 release engineering: read exact R76.15 packaged nomination/index code.

This diagnostic runs on GitHub Actions; it never accesses the user's receiver,
IPTV files, personal credentials, channels or configuration.
"""
import ast, importlib.util, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r7615_build",ROOT/"scripts/build-r7615-preview-index.py")
builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
with tempfile.TemporaryDirectory() as d:
    dst=Path(d)/"baseline.ipk";m=builder.build(dst)
    assert m["sha256"]=="c3991af773c6700c1aac0652f5027b27b4e1a91ff0820bf25e801e8d8488c468"
    arc=builder.pack.unpack_ar(dst.read_bytes())
    src=builder.pack.members_from(arc["data.tar.gz"])[builder.CORE].decode()
    lines=src.splitlines()
    t=ast.parse(src)
    cls=next(x for x in t.body if isinstance(x,ast.ClassDef) and x.name=="Catalog")
    for n in cls.body:
        if isinstance(n,ast.FunctionDef) and (
            n.name in ("_preview_nomination_pool","_fast_candidate_pool",
                       "_ensure_preview_coverage_indexes","_ensure_preview_provider_index",
                       "_fast_cache_get","_fast_cache_put") or
            ("preview" in n.name and ("index" in n.name or "cover" in n.name))):
            print("R80_METHOD",n.name,n.lineno,n.end_lineno)
            for lineno in range(n.lineno,n.end_lineno+1):
                print("R80_CODE",n.name,lineno,lines[lineno-1][:220])
