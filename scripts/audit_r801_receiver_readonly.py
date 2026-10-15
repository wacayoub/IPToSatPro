#!/usr/bin/env python3
"""IPToSatPro R80 receiver acceptance, LOCAL READ-ONLY, privacy-safe.

Collects only numeric PREVIEW_STAGE timings and count of PREVIEW_RANK_BG
errors since R80 install's backup marker. Never prints service/channel names,
IPTV URLs, server data, tokens, account information or mapping contents.
No writes, service actions, catalog refresh or installs.
"""
import datetime as dt
import json
import re
import statistics
from pathlib import Path

ROOT=Path("/home/root/iptosatpro-r76-backups")
LOG=Path("/etc/enigma2/SatIPTVBridge/bridge.log")
PLUGIN=Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/plugin.py")
PREFIX=Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/core.py")
BACKUP_DIR=re.compile(r"^\d{8}T\d{6}$")
STAMP=re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\s*\|")
STAGE=re.compile(r"\|\s*PREVIEW_STAGE\s*\|\s*(.*)$")
RANK=re.compile(r"\|\s*PREVIEW_RANK_BG\s*\|\s*(.*)$")
INT_KEY=re.compile(r"\b(total|nominate|score|rescue|sort|scored|cache)=(\d+)(?:ms)?\b")


def install_timestamp(root=ROOT):
    try:
        pointer=root/"last-backup-path"
        if pointer.is_symlink() or not pointer.is_file():
            return None
        path=Path(pointer.read_text(encoding="utf8").strip())
        if path.parent!=root or path.is_symlink() or not path.is_dir():
            return None
        name=path.name
        if not BACKUP_DIR.fullmatch(name):
            return None
        return f"{name[:4]}-{name[4:6]}-{name[6:8]} {name[9:11]}:{name[11:13]}:{name[13:15]}"
    except (OSError,UnicodeError,ValueError):
        return None


def summarize(lines,since):
    values=[]
    ranks=0
    errors=0
    for line in lines:
        stamp=STAMP.match(line)
        if not stamp or not since or stamp.group(1)<since:
            continue
        phase=STAGE.search(line)
        if phase:
            metrics={k:int(v) for k,v in INT_KEY.findall(phase.group(1))}
            if {"total","nominate","score","scored","cache"} <= metrics.keys():
                values.append(metrics)
        rank=RANK.search(line)
        if rank:
            ranks+=1
            if "error=" in rank.group(1) and re.search(r"error=\S+",rank.group(1)):
                errors+=1
    nominate=sorted(x["nominate"] for x in values)
    scoring=sorted(x["score"] for x in values)
    total=sorted(x["total"] for x in values)
    # A cache hit is useful but cannot demonstrate first-open speed.
    cold=[x for x in values if x.get("cache",0)==0]
    cold_nominate=sorted(x["nominate"] for x in cold)
    cold_score=sorted(x["score"] for x in cold)
    cold_rescue=sorted(x.get("rescue",0) for x in cold)
    cold_sort=sorted(x.get("sort",0) for x in cold)
    cold_total=sorted(x["total"] for x in cold)
    n=len(nominate)
    def p95(v):
        return v[max(0,int((len(v)*95+99)//100)-1)] if v else None
    measured={
        "samples":n,
        "nominated_ms_median":statistics.median(nominate) if n else None,
        "nominated_ms_p95":p95(nominate),
        "nominated_ms_max":max(nominate) if n else None,
        "scoring_ms_median":statistics.median(scoring) if n else None,
        "total_ms_median":statistics.median(total) if n else None,
        "cache_hits":sum(x.get("cache",0) for x in values),
        "cold_samples":len(cold),
        "cold_nomination_ms_p95":p95(cold_nominate),
        "cold_score_ms_p95":p95(cold_score),
        "cold_score_ms_max":max(cold_score) if cold else None,
        "cold_rescue_ms_p95":p95(cold_rescue),
        "cold_sort_ms_p95":p95(cold_sort),
        "cold_total_ms_p95":p95(cold_total),
        "cold_total_ms_max":max(cold_total) if cold else None,
        "ranking_completed":ranks,
        "ranking_errors":errors,
    }
    if not since:
        state="INSTALL_BASELINE_UNKNOWN"
    elif n < 10:
        state="INSUFFICIENT_SAMPLES"
    elif errors:
        state="RUNTIME_ERRORS"
    elif len(cold)<10:
        state="INSUFFICIENT_COLD_SAMPLES"
    elif measured["cold_nomination_ms_p95"]>3000 or max(cold_nominate)>5000:
        state="NOMINATION_SPEED_GATE_FAIL"
    elif measured["cold_score_ms_p95"]>500:
        state="SCORING_SPEED_GATE_FAIL"
    elif measured["cold_rescue_ms_p95"]>200:
        state="RESCUE_SPEED_GATE_FAIL"
    elif measured["cold_sort_ms_p95"]>200:
        state="SORT_SPEED_GATE_FAIL"
    elif measured["cold_total_ms_p95"]>1000:
        state="COLD_TOTAL_SPEED_GATE_FAIL"
    else:
        state="PREVIEW_SPEED_GATE_PASS"
    return measured,state


def report(log=LOG,root=ROOT,plugin=PLUGIN,core=PREFIX):
    since=install_timestamp(root)
    try:
        version=plugin.read_text(encoding="utf8")
        installed='PLUGIN_VERSION = "1.0.46-r80.1-preview-hotpath-beta"' in version
        core_present=(core.is_file() and "R7615_NOMINATION_INDEX_ONLY" in core.read_text(encoding="utf8") and
                      "R80_PREVIEW_PURE_HOTPATH_V1" in core.read_text(encoding="utf8"))
    except (OSError,UnicodeError,ValueError):
        installed=False;core_present=False
    try:
        with log.open("rb") as f:
            f.seek(0,2);size=f.tell()
            f.seek(max(0,size-4*1024*1024))
            raw=f.read(4*1024*1024)
        lines=raw.decode("utf8","replace").splitlines()
        if size>4*1024*1024:
            lines=lines[1:]
        values,state=summarize(lines,since)
    except (OSError,UnicodeError,ValueError):
        values,state=summarize([],since)
        state="LOG_UNREADABLE"
    if not (installed and core_present):
        state="R801_NOT_INSTALLED_OR_INCOMPLETE"
    return {
        "audit":"IPToSatPro R80.1 Preview hotpath beta post-install acceptance READ ONLY",
        "r801_installed_on_disk":installed,
        "r801_hotpath_engine_present":core_present,
        "since_local":since,
        "finding":state,
        "metrics":values,
        "release_final_authorized":False,
        "mapping_files_read":False,
        "receiver_modified":False,
        "note":"Collect >=10 COLD samples across >=10 DIFFERENT SAT channels after GUI restart; logs cannot prove unique channels. Cold P95 limits: score<=500ms, rescue<=200ms, sort<=200ms, total<=1000ms. User AV/mapping validation required; no automatic final approval.",
    }


if __name__=="__main__":
    print(json.dumps(report(),sort_keys=True))
