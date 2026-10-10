#!/bin/sh
# Diagnostic offline. Reads local IPTV index but NEVER prints URLs, tokens or account details.
# No scan, no package installation, no Enigma2 service changes, no HTTP requests.
python3 - <<'PY'
import importlib.util
import json
import os
import re
import time

root="/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge"
path=os.path.join(root,"core.py")
cache="/etc/enigma2/SatIPTVBridge/catalog.jsonl"
health="/etc/enigma2/SatIPTVBridge/stream_health.json"
print("=== R70 MAPPING DECISION EXPLAIN (read-only, sanitized) ===")
if not os.path.isfile(path):
    raise SystemExit("core.py not available")
spec=importlib.util.spec_from_file_location("bridge_audit_core",path)
core=importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)
if not os.path.isfile(cache):
    print("CATALOG_JSONL_MISSING; frozen in-memory/snapshot might still exist.")
    raise SystemExit(0)
stats=os.stat(cache)
print("CATALOG_JSONL_BYTES",stats.st_size)
try:
    with open(health,encoding="utf-8") as stream:
        states=json.load(stream)
    if not isinstance(states,dict):
        states={}
except Exception:
    states={}
print("STREAM_HEALTH_ENTRIES",len(states))
cases=(
    ("TREK","Unknown",130,"trek"),
    ("Tipik","Unknown",130,"tipik"),
)
ctxs={key:core.infer_sat_context(sat,provider,orbital_position=orbital,
       user_languages=["AR","FR","EN"])
      for sat,provider,orbital,key in cases}
for sat,provider,orbital,key in cases:
    ctx=ctxs[key]
    print("SAT",sat,"ORBITAL",orbital,
          "CONTEXT_MARKETS",",".join(ctx.get("market_preferences") or []),
          "CONFIDENCE",ctx.get("confidence") or "-")
items={k:[] for *_,k in cases}
read=0
started=time.monotonic()
exhausted=True
try:
    with open(cache,encoding="utf-8",errors="replace") as inp:
        for line in inp:
            read+=1
            if read>200000 or time.monotonic()-started>7:
                exhausted=False
                break
            # Fast prefilter on raw JSON to avoid parsing thousands of unrelated records.
            lowered=line.lower()
            if "trek" not in lowered and "tipik" not in lowered:
                continue
            try:
                row=json.loads(line)
                if not isinstance(row,dict):continue
                name=str(row.get("name") or "")
                if "trek" in name.lower():
                    key="trek"
                elif "tipik" in name.lower():
                    key="tipik"
                else:
                    continue
                if len(items[key])>=45:continue
                ch=core._enrich_channel(row)
                ctx=ctxs[key]
                sat="TREK" if key=="trek" else "Tipik"
                score,details=core.match_score_details(sat,ch,["AR","FR","EN"],ctx,"best")
                decision=core.match_decision(score,details,82.0)
                fp=core.channel_fingerprint(ch)
                record=states.get(fp) or {}
                lastfail=float(record.get("last_failure") or 0)
                lastsuccess=float(record.get("last_success") or 0)
                blocked=lastfail>lastsuccess and 0<=time.time()-lastfail<300
                items[key].append(dict(name=name[:75],norm=core.normalize_name(name),
                    score=round(float(score),1),decision=decision,
                    why=str(details.get("reject_reason") or details.get("review_reason") or "none")[:125],
                    blocked=blocked,market=ch.get("market") or "-",
                    market_source=ch.get("market_source") or "-",
                    quality=ch.get("quality") or "-",
                    role=str(ch.get("server_role") or "SERVER")[:20]))
            except Exception as e:
                continue
except Exception as err:
    print("SCAN_ERROR",type(err).__name__)
print("INDEX_ROWS_READ",read,"FULL_SCAN",exhausted)
def clean(s):
    # Remove control chars/escape sequences from IPTV labels; names only.
    return re.sub(r"[\x00-\x1f\x7f]"," ",str(s or ""))[:140]
for key in ("trek","tipik"):
    print("==",key.upper(),"CANDIDATES",len(items[key]),"==")
    for ch in sorted(items[key],key=lambda x:-x["score"])[:15]:
        print("NAME",clean(ch["name"]),"NORM",clean(ch["norm"]),
            "SCORE",ch["score"],"DECISION",ch["decision"],
            "MARKET",ch["market"],"SOURCE",ch["market_source"],
            "HEALTH_BLOCKED",ch["blocked"],"ROLE",ch["role"],
            "REASON",clean(ch["why"]))
print("No streams opened, no passwords/URLs output, no files changed.")
PY