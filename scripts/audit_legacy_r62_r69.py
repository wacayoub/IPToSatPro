#!/usr/bin/env python3
"""Read-only forensic comparison of archived r62-r69 published IPKs.

No source modifications, no installation, no stream URLs, no network access.
For each historic archive, extract core.py/plugin.py/monitor.py from embedded
package and compare function bodies + rank decisions on real user examples.
"""
import ast, base64, hashlib, inspect, io, subprocess, tarfile, tempfile, json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VERSIONS=["r62","r63","r64","r65","r66-beta","r67-beta","r68-beta","r69-beta"]
TARGETS = {
"core.py": [
"normalize_name","market_from_text","_channel_market",
"infer_sat_context","match_score_details","match_decision",
"_enrich_channel","Catalog.fast_rank_matches_all_servers",
"Catalog.fast_rank_matches","Catalog.rank_matches_all_servers",
],
"plugin.py": [
"_preview_sat_service_rows","_preview_candidate_cache_get",
"_preview_candidate_cache_put", "_preview_candidate_cache_drop",
"SatIPTVBridgePreview._load_selected_sat_candidates",
"SatIPTVBridgePreview._poll_expanded_candidates",
"SatIPTVBridgePreview._merge_locked_candidate",
"SatIPTVBridgePreview._ensure_full_sat_rows",
],
"monitor.py":[
"SatFallbackMonitor._build_candidate_plan",
"SatFallbackMonitor._schedule_next_candidate",
"SatFallbackMonitor._encrypted_fallback_allowed_once",
"SatFallbackMonitor._handle_iptv_failure",
"SatFallbackMonitor._on_start",
"SatFallbackMonitor._start_iptv",
],
}
def func_map(tree):
    m={}
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            m[n.name]=n
        if isinstance(n,ast.ClassDef):
            for fn in n.body:
                if isinstance(fn,(ast.FunctionDef,ast.AsyncFunctionDef)):
                    m[n.name+"."+fn.name]=fn
    return m

def package_sources(version):
    p=ROOT/"payload"/(version+".b64")
    if not p.exists():
        return {"ERROR":"payload missing"}
    try:
        data=base64.b64decode(p.read_bytes())
        with tempfile.TemporaryDirectory(prefix="legacy-audit-") as td:
            file=Path(td)/"package.ipk";file.write_bytes(data)
            tar_data=subprocess.check_output(["ar","p",str(file),"data.tar.gz"],
                                             stderr=subprocess.DEVNULL)
            ctrl_data=subprocess.check_output(["ar","p",str(file),"control.tar.gz"],
                                              stderr=subprocess.DEVNULL)
        with tarfile.open(fileobj=io.BytesIO(ctrl_data),mode="r:gz") as t:
            control=t.extractfile("./control").read().decode()
        with tarfile.open(fileobj=io.BytesIO(tar_data),mode="r:gz") as t:
            files={}
            for name in ("core.py","plugin.py","monitor.py"):
                target="./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"+name
                try: files[name]=t.extractfile(target).read().decode("utf8")
                except (KeyError, AttributeError): files[name]=None
        return {"version":next((x.strip() for x in control.splitlines()
                                if x.startswith("Version:")),"UNKNOWN"),
                "files":files, "bytes":len(data)}
    except Exception as exc:
        return {"ERROR":type(exc).__name__+":"+str(exc)[:100]}

def hashes(s, target):
    if not s:return {}
    tree=ast.parse(s)
    out={}
    for k in target:
        n=func_map(tree).get(k)
        if n is None:continue
        out[k]=hashlib.sha256(ast.dump(n,include_attributes=False).encode()).hexdigest()[:12]
    return out

results={}
for v in VERSIONS:
    pkg=package_sources(v)
    if "ERROR" in pkg:
        print("ARCHIVE",v,pkg["ERROR"]);continue
    files=pkg["files"]
    entry={
        "version":pkg["version"],"bytes":pkg["bytes"],
        "sha":{n:hashlib.sha256(s.encode()).hexdigest()[:12] if s else "-"
               for n,s in files.items()},
        "fns":{n:hashes(files[n],TARGETS[n]) for n in TARGETS},
    }
    try:
        scope={"__name__":"forensic_"+v.replace("-","_")}
        exec(compile(files["core.py"],v+"/core.py","exec"),scope)
        sat_args=["AR","FR","EN"]
        cases=[]
        for sat,ip,market in [
            ("TREK","FR TREK FHD","FR"),
            ("TREK","VIP: TREK HD","FR"),
            ("Tipik","BE: Tipik 4K","BE"),
            ("Tipik","BE TIPIK FHD","BE"),
            ("beIN SPORTS 1","TOD EVENT SPORTS 7 FHD","AR"),
            ("beIN SPORTS 6","AR BEIN SPORTS 6 FHD","AR"),
        ]:
            normalized=scope.get("normalize_name")
            if not all(k in scope for k in
                       ("infer_sat_context","match_score_details","match_decision")):
                cases.append({"case":sat+"->"+ip,"result":"API NOT AVAILABLE"});continue
            ctx=scope["infer_sat_context"](
                sat,"Unknown",orbital_position=130,
                user_languages=sat_args)
            ch={"name":ip,"group":"FRANCE" if market=="FR" else
                "BELGIUM" if market=="BE" else "SPORTS",
                "url":"fake://offline","market":market}
            score,details=scope["match_score_details"](
                sat,ch,sat_args,ctx,"best")
            dec=scope["match_decision"](score,details,82.0)
            cases.append({"pair":sat+" => "+ip,"score":round(score,1),
                          "decision":dec,"sat_market":ctx.get("market"),
                          "norm":normalized(ip) if normalized else "?",
                          "reason":details.get("reject_reason") or details.get("review_reason") or ""})
        entry["cases"]=cases
    except Exception as exc:
        entry["cases_error"]=type(exc).__name__+":"+str(exc)[:140]
    results[v]=entry
    print("ARCHIVE",v,entry["version"],"size",entry["bytes"],"SHA",entry["sha"])
    for row in entry.get("cases",[]):
        print("CASE",v,json.dumps(row,ensure_ascii=False))
    if "cases_error" in entry:
        print("CASE_ERROR",v,entry["cases_error"])
baseline=results.get("r69-beta",{})
print("=== METHODS DIVERGING FROM r69 ===")
for name in TARGETS:
    print("FILE",name)
    for target in TARGETS[name]:
        baseline_hash=baseline.get("fns",{}).get(name,{}).get(target)
        if baseline_hash is None:continue
        series=" ".join(v+"="+results.get(v,{}).get("fns",{}).get(name,{}).get(target,"MISSING")
                        for v in VERSIONS)
        if len({results.get(v,{}).get("fns",{}).get(name,{}).get(target,"MISSING") for v in VERSIONS})>1:
            print("EVOLUTION",target,series)
report=ROOT/"audit"/"LEGACY_COMPARISON_R62_R69.json"
report.parent.mkdir(exist_ok=True)
report.write_text(json.dumps(results,ensure_ascii=False,indent=2)+"\n")
print("REPORT",report)
