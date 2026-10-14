#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPToSatPro R76.11 on-receiver READ-ONLY install & mapping integrity check.

No VuLink, network request, opkg action, replay, restart or writes.
Reports only standard filenames, status and numbers. IPTV credentials,
server URLs and mapping contents are never returned.
"""
import argparse
import hashlib
import json
import math
import re
import tarfile
from pathlib import Path

PLUGIN=Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge")
CONFIG=Path("/etc/enigma2/SatIPTVBridge")
BACKUPS=Path("/home/root/iptosatpro-r76-backups")
EXPECTED="1.0.46-r76.11-preview-coldstart-fast-beta"
FILES=("overrides.json","resolved_mappings.json","manual_aliases.json",
       "rejected_sources.json","player_overrides.json",
       "import_spec.json","refresh_state.json","r76_home_layout")
STAMP_RE=re.compile(r"^(\d{8})T(\d{6})$")
LOG_STAMP=re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)")
DURATION=re.compile(r"(?:^|\s)elapsed=(\d+)ms(?:\s|$)")
PREVIEW=re.compile(r"\|\s*PREVIEW_RANK_BG\s*\|")


def backup_location(root):
    marker=root/"last-backup-path"
    try:
        if marker.is_symlink() or not marker.is_file():
            return None
        folder=Path(marker.read_text(encoding="utf8").strip())
        if folder.is_symlink() or not folder.is_dir() or folder.parent!=root:
            return None
        if not STAMP_RE.fullmatch(folder.name):
            return None
        return folder
    except (OSError, UnicodeError):
        return None


def backup_report(config, backup, installed=PLUGIN):
    if backup is None:
        return {"status":"not_found","saved_files":0,"changed":[],
                "missing_since_backup":[],"same":[]}
    archive=backup/"settings-and-maps.tar.gz"
    if archive.is_symlink() or not archive.is_file():
        return {"status":"backup_archive_missing"}
    try:
        with tarfile.open(archive,"r:gz") as tf:
            saved={}
            for member in tf.getmembers():
                norm=member.name.lstrip("./")
                for name in FILES:
                    if norm=="etc/enigma2/SatIPTVBridge/"+name and member.isfile():
                        stream=tf.extractfile(member)
                        if stream is not None:
                            saved[name]=hashlib.sha256(stream.read()).hexdigest()
            same=[];changed=[];missing=[]
            for name,digest in saved.items():
                actual=config/name
                if actual.is_symlink() or not actual.is_file():
                    missing.append(name)
                else:
                    with actual.open("rb") as f:
                        h=hashlib.sha256(f.read()).hexdigest()
                    (same if h==digest else changed).append(name)
        return {
            "status":"verified","saved_files":len(saved),
            "same":sorted(same),"changed":sorted(changed),
            "missing_since_backup":sorted(missing),
            "import_spec_was_backed_up":"import_spec.json" in saved,
            "import_spec_present_now":(config/"import_spec.json").is_file()
        }
    except (OSError,tarfile.TarError,ValueError,UnicodeError):
        return {"status":"backup_unreadable"}


def fresh_preview_report(logfile,backup_name):
    stamp=STAMP_RE.fullmatch(backup_name or "")
    if not stamp:
        return {"status":"install_time_unknown"}
    day,clock=stamp.groups()
    since=f"{day[:4]}-{day[4:6]}-{day[6:8]} {clock[:2]}:{clock[2:4]}:{clock[4:]}"
    if not logfile.is_file():
        return {"status":"log_unavailable","since_local":since}
    try:
        with logfile.open("rb") as f:
            f.seek(0,2);end=f.tell()
            f.seek(max(0,end-1024*1024))
            raw=f.read(1024*1024)
        lines=raw.decode("utf8","replace").splitlines()
        if end>1024*1024:
            lines=lines[1:]
        values=[]
        for line in lines:
            ts=LOG_STAMP.match(line)
            if not ts or ts.group(1)<since or not PREVIEW.search(line):
                continue
            x=DURATION.search(line)
            if x:
                values.append(int(x.group(1)))
        values.sort()
        if not values:
            return {"status":"no_new_preview_samples","since_local":since,"count":0}
        n=len(values)
        return {"status":"measured","since_local":since,"count":n,
                "median_ms":values[(n-1)//2],
                "p95_ms":values[min(n-1,math.ceil(n*.95)-1)],
                "max_ms":values[-1],
                "sample_quality":"limited" if n<10 else "usable",
                "note":"Preview ranking time, NOT time-to-picture or audio quality"}
    except (OSError,UnicodeError):
        return {"status":"log_unreadable","since_local":since}


def report(plugin=PLUGIN,config=CONFIG,backup_root=BACKUPS):
    path=plugin/"plugin.py"
    core=plugin/"core.py"
    try:
        p=path.read_text(encoding="utf8")
        c=core.read_text(encoding="utf8")
        good=(
            'PLUGIN_VERSION = "'+EXPECTED+'"' in p and
            "R7611_NORMAL_PREVIEW_NO_COLD_DECORATED_SCAN" in c and
            "R7610_NORMAL48_FAST_BUDGET" in c)
    except (OSError,UnicodeError):
        good=False
    backup=backup_location(backup_root)
    maps=backup_report(config,backup)
    performance=fresh_preview_report(
        config/"bridge.log",backup.name if backup else "")
    return {
        "audit":"IPToSatPro R76.11 receiver after-install read-only",
        "installed_version_and_fast_guards_match":good,
        "backup":maps,
        "preview_after_install":performance,
        "postinst_inherited_r62_hook":True,
        "note":"Postinst may remove import_spec.json; inspect backup before any restoration",
        "hardware_video_audio_tested":None,
        "no_changes":True
    }


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json",action="store_true")
    args=parser.parse_args()
    print(json.dumps(report(),ensure_ascii=True,
                     indent=None if args.json else 2,sort_keys=True))
if __name__=="__main__":
    main()
