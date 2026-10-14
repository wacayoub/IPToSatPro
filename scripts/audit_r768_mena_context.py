#!/usr/bin/env python3
"""Inspect real packaged R76 regional signals and scores, read-only."""
import ast, importlib.util, tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("builder768",root/"scripts/build-r76-metrix-preview.py")
builder=importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
with tempfile.TemporaryDirectory() as tmp:
    ipk=Path(tmp)/"audit.ipk"
    builder.build(ipk)
    parts=builder.pack.members_from(builder.pack.unpack_ar(ipk.read_bytes())["data.tar.gz"])
    plugin=parts[builder.PLUGIN].decode("utf8")
    core=parts[builder.base.CORE].decode("utf8")
    py=Path(tmp)/"actual_core.py";py.write_text(core)
    modspec=importlib.util.spec_from_file_location("real_core768",py)
    c=importlib.util.module_from_spec(modspec);modspec.loader.exec_module(c)
    for label,src in (("PLUGIN",plugin),("CORE",core)):
        tree=ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node,ast.FunctionDef) and node.name in (
                "_match_context_for_sat_ref","_match_context_for_current",
                "infer_sat_context","_r74_sat_original_languages",
                "_effective_sat_provider_family",
                "market_from_text","match_score_details",
                "fast_preview_mega_matches"):
                body=ast.get_source_segment(src,node)
                lines=body.splitlines()
                print("R768_FUNC",label,node.name,"TOTAL",len(lines))
                if node.name in ("_match_context_for_sat_ref","infer_sat_context",
                                 "_effective_sat_provider_family","market_from_text"):
                    for ix,line in enumerate(lines[:190]):print("%03d"% (ix+1),line)
                else:
                    marks=[i for i,line in enumerate(lines)
                           if any(term in line.lower() for term in
                                  ("market_pref","market_rank","cand_market","sat_market",
                                   "language_pri","language_set","context","provider_family",
                                   "country_relation","prefix_warning","review_reason",
                                   "market_source","role","reject_reason","match_score_details"))]
                    chosen=set()
                    for i in marks:
                        for k in range(max(0,i-1),min(len(lines),i+3)):chosen.add(k)
                    for ix in sorted(chosen)[:165]:print("%03d"%(ix+1),lines[ix])
    sat="Discovery HD"
    names=("AR OSN DISCOVERY CHANNEL HD","FR: DISCOVERY HEVC",
           "UK: DISCOVERY","DE: DISCOVERY HD","DE: DISCOVERY HEVC HD",
           "FR: DISCOVERY CHANNEL HD","FR: DISNEY CHANNEL HD")
    contexts=(
      {"confidence":"LOW","language_priorities":[],"market_preferences":[]},
      {"confidence":"HIGH","language_priorities":[],"market_preferences":["AR"]},
      {"confidence":"HIGH","language_priorities":["AR"],"audio_language_set":["AR"],
       "audio_language_target":"AR","market_preferences":["AR"],"provider_family":"OSN"},
    )
    for context in contexts:
        print("R768_CONTEXT",context)
        for name in names:
            ch={"name":name,"server_role":"BACKUP2","server_priority":1,
                "market":c.market_from_text(name),"market_source":"name",
                "url":"http://127.0.0.1/offline.ts"}
            try:
                score,d=c.match_score_details(sat,ch,[],context,preview=True)
                print("R768_SCORE",repr(name),score,c.match_decision(score,d,82.0),
                      {k:d.get(k) for k in ("name","market","context","provider_identity",
                         "country_prefix_warning","review_reason","reject_reason",
                         "sat_market","iptv_market","prefix_evidence") if d.get(k)})
            except Exception as err:print("R768_ERROR",repr(name),str(err)[:250])
