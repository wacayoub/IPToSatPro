#!/usr/bin/env python3
"""R76 diagnostic: inspect exact packaged Python AST at exec dynamic sites and UI init."""
import ast,importlib.util,inspect,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("b",ROOT/"scripts/build-r76-metrix-preview.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
with tempfile.TemporaryDirectory() as td:
    out=Path(td)/"r76.ipk"; print("BUILD",b.build(out)["version"])
    files=b.pack.members_from(b.pack.unpack_ar(out.read_bytes())["data.tar.gz"])
    for name,raw in files.items():
        if name.endswith("neo_theme.py"):
            skin_code=raw.decode()
            print("NEO_THEME",name,"len",len(skin_code))
            print(skin_code[:10000])
    text=files[b.PLUGIN].decode()
    lines=text.splitlines()
    tree=ast.parse(text)
    print("PLUGIN total_lines",len(lines))
    for node in ast.walk(tree):
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=="exec":
            print("EXEC_CALL lineno",node.lineno,"source",ast.get_source_segment(text,node)[:350])
        if isinstance(node,ast.FunctionDef) and node.name=="_theme_skin":
            print("THEME_SKIN lineno",node.lineno,"source",ast.get_source_segment(text,node)[:800])
    for cl in tree.body:
        if isinstance(cl,ast.ClassDef) and cl.name in ("SatIPTVBridgeDashboard","SatIPTVBridgePreview"):
            print("CLASS",cl.name)
            for method in cl.body:
                if isinstance(method,ast.FunctionDef) and method.name in ("__init__","_r7413_keep_preview_visible"):
                    for node in ast.walk(method):
                        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=="exec":
                            print("METHOD_EXEC",method.name,ast.get_source_segment(text,node)[:250])
                    if method.name=="__init__":
                        for i in range(method.lineno,method.end_lineno):
                            s=lines[i-1]
                            if "R76" in s or "_r76_" in s or "self.skin" in s or "R723" in s or "Label(" in s and "r76" in s:
                                print("UI",i,s[:170])
    print("METRIX_XML_TYPE",type(next(n for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=="R76_METRIX_FHD" for t in n.targets)).value).__name__)
