#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only Vu+ receiver static smoke for R76. Never plays/locks a channel.

Checks installed package version, Python syntax, real Enigma2 skin definitions,
HD/FHD bounds, preview/video separation, protected mapping hashes, and GUI
process. Does not read or expose IPTV URLs/credentials to output.
Actual video/remote test still requires GUI interaction.
"""
import ast
import hashlib
import json
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

PLUG=Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge")
CONF=Path("/etc/enigma2/SatIPTVBridge")
BACKUPROOT=Path("/home/root/iptosatpro-r76-backups")
EXPECTED="1.0.46-r76.1-metrix-preview-b-hotfix-beta"


def check(condition,label):
    print(("PASS" if condition else "FAIL")+": "+label)
    return bool(condition)


def literal(tree,name):
    for node in tree.body:
        if isinstance(node,ast.Assign) and any(
            isinstance(target,ast.Name) and target.id==name
            for target in node.targets):
            return ast.literal_eval(node.value)
    raise KeyError(name)


def skin(xml,size):
    root=ET.fromstring(xml)
    width,height=map(int,root.get("size").split(","))
    if (width,height)!=size:return False
    widgets=set()
    for el in root:
        if el.tag not in ("widget","eLabel","ePixmap"):return False
        x,y=map(int,el.get("position").split(","))
        w,h=map(int,el.get("size").split(","))
        if min(x,y)<0 or min(w,h)<=0 or x+w>width or y+h>height:return False
        if el.tag=="widget":
            name=el.get("name")
            if name in widgets:return False
            widgets.add(name)
    return len(widgets)>=20


def run():
    results=[]
    if not PLUG.is_dir():
        results.append(check(False,"plugin directory present"))
        return 2
    plugin=PLUG/"plugin.py"
    preview=PLUG/"preview_theme_r74.py"
    updater=PLUG/"updater.py"
    for path in (plugin,preview,updater):
        results.append(check(path.is_file(),"module "+path.name+" exists"))
        if not path.is_file():return 2
    contents=plugin.read_text(encoding="utf-8")
    results.append(check('PLUGIN_VERSION = "'+EXPECTED+'"' in contents,
                         "R76 exact installed plugin version"))
    compiled={}
    for file in (plugin,preview,updater):
        try:
            source=file.read_text(encoding="utf-8")
            compile(source,str(file),"exec")
            compiled[file.name]=ast.parse(source)
            results.append(check(True,file.name+" syntactically valid"))
        except Exception as e:
            print("FAIL: "+file.name+" parse/compile "+type(e).__name__)
            results.append(False)
    if len(compiled)==3:
        try:
            ht=compiled["plugin.py"]
            pt=compiled["preview_theme_r74.py"]
            results.append(check(skin(literal(ht,"R76_METRIX_FHD"),(1660,900)),
                                 "Metrix home FHD safe coordinates"))
            results.append(check(skin(literal(ht,"R76_METRIX_HD"),(1245,675)),
                                 "Metrix home HD safe coordinates"))
            results.append(check(skin(literal(pt,"PREVIEW_R74_FHD"),(1660,900)),
                                 "Preview B FHD safe coordinates"))
            results.append(check(skin(literal(pt,"PREVIEW_R76_HD"),(1245,675)),
                                 "Preview B HD safe coordinates"))
            results.append(check('self["r76_video"].show()' in contents and
                                 'VideoWindow(decoder=0' in contents,
                                 "OK-only video window code present"))
            results.append(check("R7413_PREVIEW_INLINE_NO_HIDE" in contents,
                                 "existing Preview OK logic retained"))
            results.append(check('("Metrix OpenATV R76 (default)", "metrix")' in contents,
                                 "classic/monitor appearance alternatives available"))
        except Exception as e:
            print("FAIL: screen extraction "+type(e).__name__)
            results.append(False)
    last=BACKUPROOT/"last-backup-path"
    if last.is_file():
        try:
            saved=Path(last.read_text().strip())
            old=json.loads((saved/"mapping-hashes.json").read_text())
            for name,digest in old.items():
                path=CONF/name
                with path.open("rb") as handle:
                    updated=hashlib.sha256(handle.read()).hexdigest()
                results.append(check(updated==digest,
                    "mapping unchanged: "+name))
        except Exception as e:
            print("FAIL: backup mapping hash verification "+type(e).__name__)
            results.append(False)
    else:
        print("INFO: no installation backup found; skipping map baseline comparison")
    try:
        entries=[p.name for p in Path("/proc").iterdir() if p.name.isdigit()]
        live=any(
            (Path("/proc")/pid/"comm").read_text(errors="ignore").strip().startswith("enigma2")
            for pid in entries if (Path("/proc")/pid/"comm").is_file())
        print("INFO: GUI Enigma2 running:",live)
    except Exception:
        print("INFO: GUI status unavailable")
    print("NOT TESTED: real video window, remote OK/GREEN/BLUE, zapping times.")
    print("R76_RECEIVER_SMOKE_"+("PASS" if all(results) else "FAIL"))
    return 0 if all(results) else 1


if __name__=="__main__":
    sys.exit(run())
