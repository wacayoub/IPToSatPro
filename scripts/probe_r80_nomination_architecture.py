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

    # Numeric-only/static source analysis of Preview ranking hot path. This
    # examines staged repository code, never a live receiver or private feeds.
    ranked=next((x for x in cls.body if isinstance(x,ast.FunctionDef)
                 and x.name=="fast_rank_matches_all_servers"),None)
    assert ranked is not None
    print("R80_RANK_METHOD",ranked.name,ranked.lineno,ranked.end_lineno)
    for lineno in range(ranked.lineno,ranked.end_lineno+1):
        print("R80_RANK_CODE",lineno,lines[lineno-1][:260])
    # Show score implementation call sites plus expensive loops without
    # emitting any runtime service names or URLs.
    for node in ast.walk(t):
        if isinstance(node,ast.FunctionDef) and node.name=="match_score_details":
            print("R80_SCORE_METHOD",node.lineno,node.end_lineno)
            for lineno in range(node.lineno,node.end_lineno+1):
                line=lines[lineno-1]
                if any(token in line for token in
                       ("SequenceMatcher","_preview_", "for ", "while ",
                        "country_relation","reordered","normalize","ratio(")):
                    print("R80_SCORE_HOT_CODE",lineno,line[:260])
