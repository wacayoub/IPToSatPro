#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.11 Preview performance logging diagnostic, READ-ONLY.

No IPTV names, URLs, server IDs, credentials or raw log lines are shown.
Distinguishes: no preview use, missing duration, no recent log activity,
possible log truncation/rotation, mismatched local clock assumptions.
A diagnostic DOES NOT prove native audio/video hardware performance.
"""
import json
import math
import re
from pathlib import Path

LOG=Path("/etc/enigma2/SatIPTVBridge/bridge.log")
BACKUP=Path("/home/root/iptosatpro-r76-backups/last-backup-path")
STAMP=re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)")
EVENT=re.compile(r"\|\s*([A-Z][A-Z0-9_]+)\s*\|")
ELAPSED=re.compile(r"(?:^|\s)elapsed=(\d+)ms(?:\s|$)")
DURATION=re.compile(r"(?:^|\s)(?:cost|elapsed)=(\d+)ms(?:\s|$)")
INDEX=re.compile(r"(?:^|\s)index=(\d+)ms(?:\s|$)")
SCORING=re.compile(r"(?:^|\s)scoring=(\d+)ms(?:\s|$)")
CANDIDATES=re.compile(r"(?:^|\s)candidate_count=(\d+)(?:\s|$)")
WHITELIST=("PREVIEW_RANK_BG","MATCH_BG_START","MATCH_BG_DONE",
           "IPTV_OK","IPTV_FAIL","NO_MATCH","AUDIO_SAFE_PLAYER")
MAX_BYTES=4*1024*1024


def snapshot_time(marker=BACKUP):
    try:
        if marker.is_symlink() or not marker.is_file():
            return None
        dirname=Path(marker.read_text(encoding="utf8").strip()).name
        if not re.fullmatch(r"\d{8}T\d{6}",dirname):
            return None
        return "%s-%s-%s %s:%s:%s" % (
            dirname[:4],dirname[4:6],dirname[6:8],
            dirname[9:11],dirname[11:13],dirname[13:15])
    except (OSError,ValueError,UnicodeError):
        return None


def metric(values):
    v=sorted(values)
    if not v:
        return {"samples":0,"p50_ms":None,"p95_ms":None,"max_ms":None}
    return {"samples":len(v),"p50_ms":v[(len(v)-1)//2],
            "p95_ms":v[min(len(v)-1,math.ceil(.95*len(v))-1)],
            "max_ms":v[-1]}


def inspect_lines(lines,since=None,truncated=False):
    total=len(lines)
    counts={x:0 for x in WHITELIST}
    recent={x:0 for x in WHITELIST}
    last_any=last_preview=None
    malformed=missing=recent_unstamped=0
    samples=[];index=[];scoring=[];max_candidates=0
    all_preview=0
    recent_lines=0
    for line in lines:
        ts=STAMP.match(line)
        name=EVENT.search(line)
        if ts:
            last_any=max(last_any or ts.group(1),ts.group(1))
        if not name:
            continue
        event=name.group(1)
        if event not in counts:
            continue
        counts[event]+=1
        if event=="PREVIEW_RANK_BG":
            all_preview+=1
            if ts:
                last_preview=ts.group(1)
        if since:
            if not ts:
                recent_unstamped+=1
                continue
            if ts.group(1)<since:
                continue
        recent[event]+=1
        recent_lines+=1
        if event=="PREVIEW_RANK_BG":
            duration=ELAPSED.search(line)
            if not duration:
                missing+=1
            else:
                samples.append(int(duration.group(1)))
            x=INDEX.search(line)
            if x:
                index.append(int(x.group(1)))
            x=SCORING.search(line)
            if x:
                scoring.append(int(x.group(1)))
            x=CANDIDATES.search(line)
            if x:
                max_candidates=max(max_candidates,int(x.group(1)))
    n_recent=recent["PREVIEW_RANK_BG"]
    if since is None:
        reason="unknown_install_timestamp"
    elif n_recent:
        reason="measured" if samples else "preview_logged_without_elapsed"
    elif last_any is None:
        reason="no_timestamped_log_events"
    elif last_any<since:
        reason="no_logs_after_install_in_sample"
    elif recent_lines:
        reason="other_activity_but_no_preview_rank"
    else:
        reason="postinstall_log_activity_unconfirmed"
    return {
        "audit":"IPToSatPro R76.11 Preview log forensics (read-only)",
        "since_install_local_timestamp":since,
        "last_timestamp_in_log":last_any,
        "last_preview_timestamp":last_preview,
        "log_tail_truncated":bool(truncated),
        "lines_in_recent_log_tail":total,
        "recognized_events_in_sample":{k:v for k,v in counts.items() if v},
        "recognized_events_after_install":{k:v for k,v in recent.items() if v},
        "preview_total_in_tail":all_preview,
        "preview_after_install":n_recent,
        "preview_after_install_missing_elapsed":missing,
        "preview_candidate_max_after_install":max_candidates or None,
        "duration":metric(samples),
        "index_ms":metric(index),
        "scoring_ms":metric(scoring),
        "possible_unstamped_events":recent_unstamped,
        "interpretation":reason,
        "warning":"Timestamp comparison assumes backup and bridge.log use same local clock; truncated logs cannot prove absence. Runtime tests and audio/video require TV verification.",
        "no_receiver_changes":True,
    }


def inspect(path=LOG,marker=BACKUP):
    since=snapshot_time(marker)
    if not path.is_file():
        return {"audit":"IPToSatPro R76.11 Preview log forensics (read-only)",
                "interpretation":"log_unavailable","no_receiver_changes":True}
    try:
        with path.open("rb") as f:
            f.seek(0,2);n=f.tell();f.seek(max(0,n-MAX_BYTES))
            data=f.read(MAX_BYTES)
        lines=data.decode("utf8","replace").splitlines()
        if n>MAX_BYTES:
            lines=lines[1:]
        result=inspect_lines(lines,since,n>MAX_BYTES)
        result["log_size_bytes"]=n
        return result
    except (OSError,UnicodeError,ValueError):
        return {"audit":"IPToSatPro R76.11 Preview log forensics (read-only)",
                "interpretation":"log_unreadable","no_receiver_changes":True}


if __name__=="__main__":
    print(json.dumps(inspect(),ensure_ascii=True,sort_keys=True))
