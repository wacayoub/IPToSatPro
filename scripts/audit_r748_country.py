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

    base=fs[b.CORE].decode(); tree=ast.parse(base)
    for n in ast.walk(tree):
        if isinstance(n,ast.FunctionDef) and n.name in (
            "normalize_preview_name","normalize_name","market_from_text",
            "_preview_lexical_tokens","_preview_prefixes","_identity_anchor_tokens",
            "_cross_market_feed_rule","_context_rank_bands","_identity_is_safe"
        ):
            print("R748_MATCH_FUNCTION",n.name,"BEGIN")
            print((ast.get_source_segment(base,n) or "")[:21000])
            print("R748_MATCH_FUNCTION",n.name,"END")
    for idx,line in enumerate(base.splitlines()):
        if "MARKET_ALIASES =" in line or "LANGUAGE_ALIASES =" in line or "normalize_name(" in line and idx<180:
            print("R748_GLOBAL",idx+1,"BEGIN")
            print("\n".join(base.splitlines()[idx:idx+130])[:17000])
            print("R748_GLOBAL",idx+1,"END")
    n=next(x for x in ast.walk(tree) if isinstance(x,ast.FunctionDef) and x.name=="match_score_details")
    score=ast.get_source_segment(base,n) or ""
    print("R748_SCORE_FULL_BEGIN")
    print(score[:34000])
    print("R748_SCORE_FULL_END")

    if True:
        src=base
        functions=[n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef)]
        for n in functions:
            if n.name in ("_preview_numbers","extract_numbers","_identity_anchor_tokens","_enrich_channel","_preview_decorated_source_name"):
                print("R749_FUNC",n.name,"BEGIN")
                print((ast.get_source_segment(src,n) or "")[:10500])
                print("R749_FUNC",n.name,"END")
        from importlib.util import spec_from_file_location,module_from_spec
        location=Path(td)/"core_inspect.py"
        location.write_text(src)
        spc=spec_from_file_location("real_r749_core",location)
        core=module_from_spec(spc);spc.loader.exec_module(core)
        context={"confidence":"LOW","language_priorities":[],"market_preferences":[]}
        for sat,iptv in (("FilmBox One","ONE: FILMBOX"),
             ("FILMBOX ONE HD","ONE FILMBOX FHD"),
             ("FILMBOX 1 HD","ONE FILMBOX FHD"),
             ("FilmBox One","FILMBOX EXTRA"),
             ("FilmBox One","ONE FILMBOX 2")):
            item={"name":iptv,"group":"MOVIES","server_role":"BACKUP1","server_priority":1,"url":"http://invalid.local/video.ts"}
            for preview in (True,False):
                score,details=core.match_score_details(sat,item,[],context,preview=preview)
                print("R749_BEFORE",repr(sat),repr(iptv),preview,score,core.match_decision(score,details,82),details.get("reject_reason"),details.get("review_reason"),
                    core.normalize_preview_name(sat),core.normalize_preview_name(iptv),core._preview_numbers(sat),core._preview_numbers(iptv))
