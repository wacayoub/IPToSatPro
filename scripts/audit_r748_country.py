#!/usr/bin/env python3
"""One-off inspect matching context and country names in the exact R74.7 IPK."""
import ast,importlib.util,re,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r747",root/"scripts/build-r74-unified.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
with tempfile.TemporaryDirectory() as td:
    dest=Path(td)/"audit.ipk";b.build(dest)
    fs=b.b.b.base.pack.members_from(b.b.b.base.pack.unpack_ar(dest.read_bytes())["data.tar.gz"])
    for label,key in (("core",b.CORE),("plugin",b.PLUGIN)):
        src=fs[key].decode();tree=ast.parse(src)
        functions=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)]
        matches=[]
        rx=re.compile(r"market|country|geo|locale|normalize|name_match|feed_conflict|variant|language|fast_preview_mega_matches|context|token|identity|score",re.I)
        for n in functions:
            if rx.search(n.name):
                matches.append((n.name,n.lineno,n.end_lineno))
        print("R748_FUNCTIONS",label,matches[:175])
        for n in functions:
            if n.name in ("fast_preview_mega_matches","infer_sat_context","_r736_choose_best_safe",
                    "_match_context_for_sat_ref","_match_context_for_current",
                    "match_decision","_candidate_decision"):
                body=ast.get_source_segment(src,n) or ""
                print("R748_FULL_FUNCTION",label,n.name,"BEGIN")
                print(body[:25000])
                print("R748_FULL_FUNCTION",label,n.name,"END")
        for token in ("Austria","Germany","country_variants","country_alias","market_preferences",
                      "provider_identity","country_conflict","wrong_market","variant_conflict","[AT]"):
            idx=[i for i,line in enumerate(src.splitlines()) if token.lower() in line.lower()]
            print("R748_TOKEN",label,token,len(idx))
            for i in idx[:5]:
                l=src.splitlines()
                print("R748_CTX",label,token,i+1," | ".join(l[max(0,i-3):min(len(l),i+4)])[:750])
