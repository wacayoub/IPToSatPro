#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPToSatPro R76.11 Preview event forensic, LOCAL READ ONLY.

Unlike early audit versions, recognizes ANY 'PREVIEW_*' code, INCLUDING
truncated codes emitted by _startup_log(code[:18], ...), notably
PREVIEW_SEED_EXPAN, PREVIEW_INSTANT_SE and PREVIEW_UI_CANDIDA.
Only prints event names, counts, and timestamps. NEVER prints SAT names,
IPTV URLs, passwords, server names, or raw log messages. No file changes.
"""
import collections
import datetime
import json
import re
from pathlib import Path

LOG = Path("/etc/enigma2/SatIPTVBridge/bridge.log")
ROOT = Path("/home/root/iptosatpro-r76-backups")
MAX_READ = 5*1024*1024
EV = re.compile(r"\|\s*(PREVIEW_[A-Z0-9_]+)\s*\|")
TS = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)")
KNOWN_PREFIXES = {
    "PREVIEW_SEED_EXPAN": "seed_loaded_rank_requested",
    "PREVIEW_INSTANT_SE": "instant_candidates_found",
    "PREVIEW_EXPAND_WAI": "existing_rank_worker_busy",
    "PREVIEW_RANK_BG": "rank_result_published",
    "PREVIEW_AUTO_MAP": "automap_evaluated",
    "PREVIEW_STAY_OPEN": "ui_stays_open",
    "PREVIEW_UI_CANDIDA": "ranked_candidates_rendered",
    "PREVIEW_INLINE": "preview_playback_panel",
}
BACKUP_RE = re.compile(r"^\d{8}T\d{6}$")


def install_marker(root=ROOT):
    try:
        p = root/"last-backup-path"
        if p.is_symlink() or not p.is_file():
            return None
        target=Path(p.read_text(encoding="utf8").strip())
        if target.parent!=root or not target.is_dir() or target.is_symlink():
            return None
        n=target.name
        if not BACKUP_RE.fullmatch(n):
            return None
        return f"{n[:4]}-{n[4:6]}-{n[6:8]} {n[9:11]}:{n[11:13]}:{n[13:]}"
    except (OSError,ValueError,UnicodeError):
        return None


def aggregate(lines,since):
    overall=collections.Counter()
    after=collections.Counter()
    phase_times={}
    last_any=last_preview=None
    other_new=0
    preview_post=0
    for line in lines:
        time_match=TS.match(line)
        stamp=time_match.group(1) if time_match else None
        if stamp:
            last_any=max(last_any or stamp,stamp)
        event=EV.search(line)
        if event:
            name=event.group(1)
            if stamp:
                last_preview=max(last_preview or stamp,stamp)
            overall[name]+=1
            if stamp and since and stamp>=since:
                after[name]+=1
                preview_post+=1
                phase_times[name]=max(phase_times.get(name,stamp),stamp)
        elif stamp and since and stamp>=since:
            other_new+=1
    if not since:
        status="no_install_marker"
    elif after.get("PREVIEW_RANK_BG",0):
        status="rank_results_observed"
    elif preview_post:
        status="preview_activity_without_rank_result"
    elif last_any and last_any>=since:
        status="other_activity_no_preview_event"
    else:
        status="no_post_install_log_activity"
    return {
        "finding":status,
        "events_all":dict(sorted(overall.items())),
        "events_after_install":dict(sorted(after.items())),
        "last_seen_event_by_code":dict(sorted(phase_times.items())),
        "preview_events_after_install":preview_post,
        "non_preview_log_entries_after_install":other_new,
        "last_log_timestamp":last_any,
        "last_preview_timestamp":last_preview,
        "event_names_may_be_truncated_to_18_chars":True,
        "event_phase_legend":{k:v for k,v in KNOWN_PREFIXES.items() if k in overall},
        "note":"Code PREVIEW_SEED_EXPAN means a background job was scheduled, not that it completed. PREVIEW_RANK_BG is written after the GUI polls the finished job.",
    }


def report(log=LOG,root=ROOT):
    base=install_marker(root)
    if not log.is_file() or log.is_symlink():
        return {"audit":"R76.11 Preview event-codes read-only",
                "status":"log_missing","receiver_modified":False}
    try:
        with log.open("rb") as f:
            f.seek(0,2)
            total=f.tell()
            f.seek(max(0,total-MAX_READ))
            sample=f.read(MAX_READ)
        lines=sample.decode("utf8","replace").splitlines()
        if total>MAX_READ:
            lines=lines[1:]
        result=aggregate(lines,base)
        result.update({
            "audit":"R76.11 Preview event-codes read-only",
            "since_install":base,
            "read_bytes":len(sample),
            "total_log_bytes":total,
            "truncated_log_tail":total>MAX_READ,
            "receiver_modified":False,
        })
        return result
    except (OSError,UnicodeError,ValueError):
        return {"audit":"R76.11 Preview event-codes read-only",
                "status":"log_unreadable","receiver_modified":False}


if __name__=="__main__":
    print(json.dumps(report(),ensure_ascii=True,sort_keys=True))
