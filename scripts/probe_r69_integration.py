#!/usr/bin/env python3
"""CI inspection of pinned r69 source APIs for the r70 integration review.
No credential, playlist, URL or live receiver data is loaded.
"""
from pathlib import Path
import ast, base64, io, subprocess, tarfile, tempfile
R=Path(__file__).resolve().parents[1]
raw=base64.b64decode((R/"payload/r69-beta.b64").read_bytes())
with tempfile.TemporaryDirectory(prefix="r69-probe-") as d:
    base=Path(d)/"r69.ipk";base.write_bytes(raw)
    tdata=subprocess.check_output(["ar","p",str(base),"data.tar.gz"])
with tarfile.open(fileobj=io.BytesIO(tdata),mode="r:gz") as tar:
    for filename in ("monitor.py","plugin.py","updater.py"):
        path="./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"+filename
        src=tar.extractfile(path).read().decode()
        lines=src.splitlines(); tree=ast.parse(src)
        print("\n====",filename,"lines",len(lines),"====")
        for cls in [n for n in tree.body if isinstance(n,ast.ClassDef)]:
            if cls.name in ("SatFallbackMonitor","SatIPTVBridgePreview","SatIPTVBridgeAlternatives"):
                print("CLASS",cls.name)
                for method in cls.body:
                    if isinstance(method,(ast.FunctionDef,ast.AsyncFunctionDef)):
                        if cls.name=="SatFallbackMonitor":
                            cond=(method.name in ("__init__","_play_match","_verify_iptv","_handle_iptv_failure","_post_success_quality_update","_on_start","_on_end","_stop","_on_video_size","_playback_plan")
                                  or "audio" in method.name.lower() or "lock" in method.name.lower() or "fail" in method.name.lower())
                        else:
                            cond=("manual" in method.name.lower() or "override" in method.name.lower()
                                  or "lock" in method.name.lower() or "save" in method.name.lower())
                        if cond:
                            print("METHOD",method.name,"line",method.lineno,"args", [a.arg for a in method.args.args], "body",method.end_lineno-method.lineno)
                            if method.name in ("_post_success_quality_update","_play_match","_handle_iptv_failure"):
                                for lineno in range(method.lineno,min(method.end_lineno,method.lineno+13)+1):
                                    print("  %s: %s" % (lineno, lines[lineno-1][:150]))
        if filename=="plugin.py":
            for n in tree.body:
                if isinstance(n,ast.FunctionDef) and n.name in ("_save_override","_remove_override","_load_overrides"):
                    print("==SOURCE",n.name)
                    for lineno in range(n.lineno, min(n.end_lineno, n.lineno+95)+1):
                        print("  %d: %s" %(lineno, lines[lineno-1][:165]))
        if filename=="monitor.py":
            for n in tree.body:
                if isinstance(n,ast.ClassDef) and n.name=="SatFallbackMonitor":
                    for m in n.body:
                        if isinstance(m,ast.FunctionDef) and m.name in ("_post_success_quality_update",):
                            print("==FULL_SOURCE",m.name)
                            for lineno in range(m.lineno, m.end_lineno+1):
                                print("  %d: %s" %(lineno, lines[lineno-1][:165]))
        if filename=="plugin.py":
            for n in tree.body:
                if isinstance(n,ast.FunctionDef) and any(w in n.name.lower() for w in ("override","manual","lock")):
                    print("GLOBAL",n.name,"line",n.lineno,"args",[a.arg for a in n.args.args])
        if filename=="monitor.py":
            for n in tree.body:
                if isinstance(n,ast.ImportFrom) and n.module and any(k in n.module.lower() for k in ("core","plugin")):
                    print("IMPORT",n.module,[a.name for a in n.names])
