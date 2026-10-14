#!/usr/bin/env python3
import ast, tempfile, importlib.util
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r769_builder",root/"scripts/build-r76-metrix-preview.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
with tempfile.TemporaryDirectory() as td:
  ipk=Path(td)/"audit.ipk";b.build(ipk)
  files=b.pack.members_from(b.pack.unpack_ar(ipk.read_bytes())["data.tar.gz"])
  for file,payload in files.items():
    if not file.endswith(".py"):continue
    src=payload.decode()
    if "SatIPTVBridgeAlternatives" in src or "Manual Mapping" in src or "MANUAL MAPPING" in src:
      print("R769_FIND_FILE",file)
      lines=src.splitlines()
      for i,line in enumerate(lines):
        if any(q in line for q in ("SatIPTVBridgeAlternatives","Manual Mapping","MANUAL MAPPING","_rank_current_all_servers","_rank_sat_ref_all_servers")):
          print("R769_FIND",i+1," | ".join(lines[max(0,i-2):i+4])[:1500])
    if file.endswith("/plugin.py"):
      tree=ast.parse(src)
      print("R769_ALL_CLASSES",[n.name for n in tree.body if isinstance(n,ast.ClassDef)])
      for node in tree.body:
        if isinstance(node,(ast.Import,ast.ImportFrom)) and "altern" in ast.unparse(node).lower():
          print("R769_ALT_IMPORT",ast.unparse(node))
        if isinstance(node,ast.ClassDef) and any(term in node.name.lower() for term in ("dashboard","alternative","manual")):
          for method in node.body:
            if isinstance(method,ast.FunctionDef) and any(term in method.name.lower() for term in ("manual","alternative","search","candidate")):
              print("R769_ROOT_METHOD",node.name,method.name,(ast.get_source_segment(src,method) or "")[:15000])

      # R76.9 display comparison: exact methods from the rebuilt IPK, no user data.
      for cname, wanted in (("SatIPTVBridgeAlternatives", ("_render", "_display_sort_key", "_display_decision", "_real_resolution_text")),
                            ("SatIPTVBridgePreview", ("_render_source_list", "_sort_candidates_with_cached_evidence", "_source_tag", "_candidate_decision"))):
        target=next((n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cname),None)
        if target is None:continue
        for method in target.body:
          if isinstance(method,ast.FunctionDef) and method.name in wanted:
            print("R769_DISPLAY_SOURCE",cname,method.name,(ast.get_source_segment(src,method) or "")[:24000])

      # Inspect widget API before replacing Preview's source_list implementation.
      for cname, wanted in (
          ("SmartMatchAlternativesList", ("ALL",)),
          ("PreviewBrowserList", ("ALL",)),
          ("SatIPTVBridgePreview", ("__init__","_source_index_now","_source_selection_changed","_set_focus","_selected_channel","_render_source_list","_close")),
          ("SatIPTVBridgeAlternatives", ("__init__","_index","_selection_changed","_render","_display_sort_key"))):
        target=next((n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cname),None)
        if not target:continue
        for method in target.body:
          if isinstance(method,ast.FunctionDef) and ("ALL" in wanted or method.name in wanted):
            body=ast.get_source_segment(src,method) or ""
            print("R769_WIDGET_SOURCE",cname,method.name,body[:18000])
      print("R769_SKIN_MANUAL",next((n.value.value[:5000] for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="ALTERNATIVES_FHD" for t in n.targets) and isinstance(n.value,ast.Constant)),"-"))
