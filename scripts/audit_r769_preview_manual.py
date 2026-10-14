#!/usr/bin/env python3
"""Read-only audit of real R76 Preview Browser and Manual Mapping source paths."""
import ast, importlib.util, tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r769builder",root/"scripts/build-r76-metrix-preview.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp)/"r768.ipk";b.build(p)
    fs=b.pack.members_from(b.pack.unpack_ar(p.read_bytes())["data.tar.gz"])
    src=fs[b.PLUGIN].decode()
    tree=ast.parse(src)
    for cls in [x for x in tree.body if isinstance(x,ast.ClassDef)]:
        funcs=[x for x in cls.body if isinstance(x,ast.FunctionDef)]
        relevant=(any(q in cls.name.lower() for q in ("mapping","preview","alternate","source")) or
                  any(q in x.name for x in funcs for q in
                      ("_render_rows","_rank_candidates","_sort_candidates","_populate","_reload","_search_candidates")))
        if not relevant:continue
        print("R769_CLASS",cls.name)
        for m in funcs:
            if any(q in m.name.lower() for q in ("load","rank","render","sort","search","candidate","source","map","entry","list","refresh","poll")):
                print("R769_METHOD",cls.name,m.name,m.lineno,m.end_lineno)
                if ("mapping" in cls.name.lower() and any(t in m.name.lower() for t in ("refresh","search","load","render","rank","open"))) or (cls.name=="SatIPTVBridgePreview" and m.name in ("_expand_selected_sat_candidates","_poll_expanded_candidates","_sort_candidates_with_cached_evidence")):
                    body=ast.get_source_segment(src,m) or ""
                    if m.name in ("_expand_selected_sat_candidates","_poll_expanded_candidates","_sort_candidates_with_cached_evidence"):
                        print("R769_BODY",cls.name,m.name,body[:10000])
                    else:
                        print("R769_BODY",cls.name,m.name,body[:14000])
    for node in tree.body:
        if isinstance(node,ast.FunctionDef) and any(s in node.name for s in ("manual","rank","_r736_auto_map","_preview_channel_rows")):
            print("R769_GLOBAL",node.name,node.lineno,node.end_lineno,(ast.get_source_segment(src,node) or "")[:12500])

    print("R769_PACKAGE_SOURCE_NAMES",
          [p for p in fs if p.endswith(".py") and
           any(word in p.lower() for word in ("alternat","manual","mapping","plugin","source","rank"))])
    print("R769_ALTERNATIVES_IMPORT",
          [s for s in src.splitlines()[:320] if "alternativ" in s.lower() or "manual" in s.lower()])
    for path,data in fs.items():
        if not path.endswith(".py") or path==b.PLUGIN: continue
        try: other=ast.parse(data.decode("utf8"))
        except Exception: continue
        relevant=[c for c in ast.walk(other) if isinstance(c,ast.ClassDef)
                  and any(q in c.name.lower() for q in ("alternativ","mapping","manual"))]
        if not relevant:continue
        for cls in relevant:
            print("R769_PACKAGE_CLASS",path,cls.name)
            for method in cls.body:
                if not isinstance(method,ast.FunctionDef):continue
                print("R769_PACKAGE_METHOD",cls.name,method.name,method.lineno,method.end_lineno)
                if any(q in method.name.lower() for q in ("init","rank","refresh","search","render","candidate","sources","load")):
                    print("R769_PACKAGE_BODY",cls.name,method.name,(ast.get_source_segment(data.decode("utf8"),method) or "")[:15000])
