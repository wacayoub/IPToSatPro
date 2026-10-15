#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.11 Preview event triage, read only, no channel or server data exported.

An existing shared candidate cache may short-circuit ranking and produce
no PREVIEW_RANK_BG despite a working Preview screen. Deep/YELLOW requests
bypass that normal-cache shortcut in the R76.11 packaged code.
"""
import datetime
import json
import re
from pathlib import Path

LOG=Path("/etc/enigma2/SatIPTVBridge/bridge.log")
MARK=Path("/home/root/iptosatpro-r76-backups/last-backup-path")
PLUG=Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/plugin.py")
CORE=Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/core.py")
MAX=4*1024*1024
EVENTS=("PREVIEW_RANK_BG","PREVIEW_EXPAND_WAIT","PREVIEW_AUTO_MAP",
        "PREVIEW_UI_CANDIDATES","PREVIEW_STAY_OPEN")
REGEX=re.compile(r"\|\s*([A-Z][A-Z0-9_]+)\s*\|")
STAMP=re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)")
DUR=re.compile(r"(?:^|\s)elapsed=(\d+)ms(?:\s|$)")
SAFE_MARK=re.compile(r"^\d{8}T\d{6}$")


def since_install(marker=MARK):
    try:
        if not marker.is_file() or marker.is_symlink():
            return None
        folder=Path(marker.read_text(encoding="utf8").strip())
        if not SAFE_MARK.fullmatch(folder.name):
            return None
        if folder.parent != marker.parent:
            # The selected backup must be a direct child of the marker directory.
            return None
        d=folder.name
        return f"{d[:4]}-{d[4:6]}-{d[6:8]} {d[9:11]}:{d[11:13]}:{d[13:15]}"
    except (OSError,UnicodeError):
        return None


def summarize(lines,since=None):
    all_counts=dict.fromkeys(EVENTS,0)
    newer=dict.fromkeys(EVENTS,0)
    last_preview=None
    last_log=None
    duration_count=0
    timestamped=0
    total_after=0
    for line in lines:
        stamp=STAMP.match(line)
        if stamp:
            timestamped+=1
            ts=stamp.group(1)
            last_log=max(last_log or ts,ts)
        else:
            ts=None
        marker=REGEX.search(line)
        if marker is None:
            continue
        event=marker.group(1)
        if event in all_counts:
            all_counts[event]+=1
            if ts:
                last_preview=max(last_preview or ts,ts)
            if ts is not None and (since is None or ts>=since):
                newer[event]+=1
                if event=="PREVIEW_RANK_BG" and DUR.search(line):
                    duration_count+=1
        if ts is not None and (since is None or ts>=since):
            total_after+=1
    rank=newer["PREVIEW_RANK_BG"]
    others=sum(v for k,v in newer.items() if k!="PREVIEW_RANK_BG")
    if since is None:
        interpretation="install_baseline_unknown"
    elif rank:
        interpretation="preview_rank_emitted"
    elif others:
        interpretation="preview_events_without_rank"
    elif last_log is None or last_log<since:
        interpretation="no_logged_activity_after_install"
    elif total_after:
        interpretation="other_events_after_install_but_no_preview_events"
    else:
        interpretation="no_timestamped_event_after_install"
    return {
        "event_counts_all":{k:v for k,v in all_counts.items() if v},
        "preview_events_after_install":{k:v for k,v in newer.items() if v},
        "preview_rank_durations_after_install":duration_count,
        "last_preview_event":last_preview,
        "last_log_event":last_log,
        "timestamped_lines_in_tail":timestamped,
        "all_event_lines_after_install":total_after,
        "interpretation":interpretation,
    }


def static_wiring(plugin=PLUG,core=CORE):
    try:
        src=plugin.read_text(encoding="utf8")
        c=core.read_text(encoding="utf8")
        return {
            "r7611_installed": all(x in src for x in (
                'PLUGIN_VERSION = "1.0.46-r76.11-preview-coldstart-fast-beta"',
                'self.candidate_poll_timer.callback.append(self._poll_expanded_candidates)',
                '_startup_log("PREVIEW_RANK_BG",',
                "if shared is not None and bool(shared[3])",
                "self._r71_deep_requested and self._r71_deep_target_ref == raw",
            )) and "R7611_NORMAL_PREVIEW_NO_COLD_DECORATED_SCAN" in c,
            "normal_shared_cache_can_skip_rank_logging":(
                "if shared is not None and bool(shared[3])" in src and
                "_preview_candidate_cache_get(raw)" in src),
            "deep_request_can_bypass_shared_cache":(
                "not (self._r71_deep_requested and self._r71_deep_target_ref == raw)" in src),
            "worker_completion_log_present":'_startup_log("PREVIEW_RANK_BG",' in src,
        }
    except (OSError,UnicodeError):
        return {"status":"plugin_source_unavailable"}


def report(log=LOG,marker=MARK,plugin=PLUG,core=CORE):
    since=since_install(marker)
    if since is None:
        return {"audit":"IPToSatPro R76.11 Preview trace read-only",
                "no_changes":True,"status":"backup_timestamp_missing"}
    if not log.is_file() or log.is_symlink():
        return {"audit":"IPToSatPro R76.11 Preview trace read-only",
                "no_changes":True,"status":"log_unavailable"}
    try:
        with log.open("rb") as fh:
            fh.seek(0,2)
            n=fh.tell()
            fh.seek(max(0,n-MAX))
            body=fh.read(MAX)
        lines=body.decode("utf8","replace").splitlines()
        if n>MAX:lines=lines[1:]
        result=summarize(lines,since)
        result.update({
            "audit":"IPToSatPro R76.11 Preview trace read-only",
            "since_install":since,
            "log_bytes":n,
            "log_tail_truncated":n>MAX,
            "static_wiring":static_wiring(plugin,core),
            "no_changes":True,
            "guidance":"For performance samples: open Preview on a new SAT channel, or press YELLOW for deep alternatives, then rerun. Check that PREVIEW_RANK_BG increases; do not infer speed from missing samples.",
        })
        return result
    except (OSError,UnicodeError,ValueError):
        return {"audit":"IPToSatPro R76.11 Preview trace read-only",
                "no_changes":True,"status":"log_unreadable"}


if __name__=="__main__":
    print(json.dumps(report(),ensure_ascii=True,sort_keys=True))
