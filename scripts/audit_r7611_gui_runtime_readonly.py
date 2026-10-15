#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.11 GUI-process timeline vs installation, strictly read-only.

Uses /proc to determine whether the Enigma2 GUI process started BEFORE the
R76.11 installation backup. Does not read IPTV playlists, configuration
secrets, stream URLs, or processes' command-line arguments. Does not
restart Enigma2 or write to the receiver.
"""
import datetime
import json
import os
import re
import time
from pathlib import Path

PROC=Path("/proc")
PLUGIN=Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/plugin.py")
BACKUPS=Path("/home/root/iptosatpro-r76-backups")
LOG=Path("/etc/enigma2/SatIPTVBridge/bridge.log")
STAMP=re.compile(r"^(\d{8})T(\d{6})$")
LINE_TIME=re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)")
EVENT=re.compile(r"\|\s*([A-Z][A-Z0-9_]+)\s*\|")
MARKERS=("PREVIEW_RANK_BG","PREVIEW_AUTO_MAP","PREVIEW_STAY_OPEN",
         "PREVIEW_UI_CANDIDATES","PREVIEW_EXPAND_WAIT")


def baseline(root=BACKUPS):
    marker=root/"last-backup-path"
    try:
        if not marker.is_file() or marker.is_symlink():
            return None
        dest=Path(marker.read_text(encoding="utf8").strip())
        if dest.parent != root or not dest.is_dir() or dest.is_symlink():
            return None
        mat=STAMP.fullmatch(dest.name)
        if not mat:
            return None
        ymd,hms=mat.groups()
        local="%s-%s-%s %s:%s:%s" % (
            ymd[:4],ymd[4:6],ymd[6:8],hms[:2],hms[2:4],hms[4:6])
        return {"local":local,
                "epoch":datetime.datetime.strptime(local,"%Y-%m-%d %H:%M:%S").timestamp()}
    except (OSError,ValueError,UnicodeError,OverflowError):
        return None


def boot_epoch(proc=PROC):
    try:
        with (proc/"stat").open(encoding="ascii") as f:
            for line in f:
                if line.startswith("btime "):
                    return float(line.split()[1])
    except (OSError,ValueError,UnicodeError):
        pass
    try:
        return time.time()-float((proc/"uptime").read_text().split()[0])
    except (OSError,ValueError,UnicodeError):
        return None


def proc_start(stat_text,boot,hertz):
    """Linux proc stat field 22 is the 20th token AFTER the closing ')'."""
    if boot is None or not hertz:
        return None
    tail=stat_text.rsplit(")",1)
    if len(tail)!=2:
        return None
    cols=tail[1].split()
    if len(cols)<20:
        return None
    try:
        return float(boot)+int(cols[19])/float(hertz)
    except (ValueError,TypeError,OverflowError):
        return None


def gui_processes(proc=PROC,boot=None,hertz=None):
    if boot is None:
        boot=boot_epoch(proc)
    if hertz is None:
        try:
            hertz=os.sysconf("SC_CLK_TCK")
        except (ValueError,AttributeError,OSError):
            hertz=100
    matches=[]
    try:
        entries=list(proc.iterdir())
    except OSError:
        return matches
    for p in entries:
        if not p.name.isdigit():
            continue
        try:
            # "comm" contains only the executable name; do NOT access cmdline.
            comm=(p/"comm").read_text(encoding="utf8",errors="replace").strip()
            if not (comm=="enigma2" or comm.startswith("enigma2.")):
                continue
            start=proc_start((p/"stat").read_text(encoding="ascii"),boot,hertz)
            matches.append({"pid":int(p.name),"start_epoch":start,
                            "started_local":datetime.datetime.fromtimestamp(start).strftime(
                                "%Y-%m-%d %H:%M:%S") if start is not None else None})
        except (OSError,ValueError,OverflowError):
            continue
    return sorted(matches,key=lambda x:x["pid"])


def log_observation(path=LOG,since=None,cap=2*1024*1024):
    if not path.is_file() or path.is_symlink():
        return {"status":"log_unavailable"}
    try:
        with path.open("rb") as f:
            f.seek(0,2);size=f.tell()
            f.seek(max(0,size-cap));data=f.read(cap)
        lines=data.decode("utf8","replace").splitlines()
        if size>cap:lines=lines[1:]
        counts={k:0 for k in MARKERS}
        newest=None
        postinstall_events=0
        for line in lines:
            ts=LINE_TIME.match(line)
            if not ts:
                continue
            newest=max(newest or ts.group(1),ts.group(1))
            if since and ts.group(1)<since:
                continue
            postinstall_events+=1
            event=EVENT.search(line)
            if event and event.group(1) in counts:
                counts[event.group(1)]+=1
        return {"status":"ok","bytes":size,"tail_truncated":size>cap,
                "latest_log_local":newest,
                "timestamped_lines_after_install":postinstall_events,
                "preview_events_after_install":{k:v for k,v in counts.items() if v}}
    except (OSError,ValueError,UnicodeError):
        return {"status":"log_unreadable"}


def report(proc=PROC,plugin=PLUGIN,backups=BACKUPS,log=LOG):
    snap=baseline(backups)
    ps=gui_processes(proc)
    try:
        code=plugin.read_text(encoding="utf8",errors="replace")
        disk_r7611=('PLUGIN_VERSION = "1.0.46-r76.11-preview-coldstart-fast-beta"' in code)
    except OSError:
        disk_r7611=False
    epoch=snap["epoch"] if snap else None
    comparable=[p for p in ps if p["start_epoch"] is not None]
    # Avoid claiming restart from static version: GUI may hold older code in RAM.
    started_after=(
        all(p["start_epoch"]>=epoch for p in comparable)
        if epoch is not None and comparable and len(comparable)==len(ps) else None)
    logstats=log_observation(log,snap["local"] if snap else None)
    preview_count=sum(logstats.get("preview_events_after_install",{}).values())
    if epoch is None:
        finding="INSTALL_BASELINE_UNKNOWN"
    elif not ps:
        finding="ENIGMA2_GUI_PROCESS_NOT_FOUND"
    elif started_after is False:
        finding="ENIGMA2_GUI_PREDATES_R7611_INSTALL_RESTART_MAY_BE_NEEDED"
    elif started_after is True and preview_count:
        finding="GUI_STARTED_AFTER_INSTALL_AND_PREVIEW_EVENTS_PRESENT"
    elif started_after is True:
        finding="GUI_STARTED_AFTER_INSTALL_BUT_NO_PREVIEW_EVENTS_LOGGED"
    else:
        finding="GUI_START_TIME_UNKNOWN"
    return {"audit":"IPToSatPro R76.11 GUI-runtime timeline (read-only)",
            "installed_r7611_on_disk":disk_r7611,
            "install_backup_timestamp_local":snap["local"] if snap else None,
            "gui_processes":ps,
            "gui_started_after_install":started_after,
            "log_activity":logstats,
            "finding":finding,
            "note":"GUI process start is evidence of restart only, not proof that Preview opened or rank worker completed. Never assume EPGManager and IPToSatPro share GUI runtime state.",
            "no_receiver_changes":True}


if __name__=="__main__":
    print(json.dumps(report(),sort_keys=True,ensure_ascii=True))
