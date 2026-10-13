#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R75 Neo Dark Classic: restore the R73 color palette, KEEP R75 geometry.

ONLY replaces color literals in preview_theme_r74.py. All XML screen/widget
positions, sizes, font sizes, actions, SAT/IPTV lists and Picon boxes are
bit-for-bit unchanged. Never patches monitor, core, player, mappings or EPG.

--check read-only, --apply atomic + single backup, --rollback restores prior skin.
"""
import argparse
import ast
import os
import stat
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

TARGET=Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/preview_theme_r74.py")
BACKUP="preview_theme_r74.py.r75-neo-classic-original.bak"
OLD="R74 compact, legible Neo Dark FHD skin"
TAG="R75_NEO_DARK_CLASSIC_PALETTE"
MAP={
    "#08131E":"#090F18", # outer screen
    "#31D5B4":"#27C7AC", # turquoise accent
    "#112433":"#111C29", # title surface
    "#102130":"#101C29", # meta/status surface
    "#142431":"#121F2D", # SAT/IPTV panel surface
    "#66A5DC":"#347BA5", # blue accent
    "#1A3443":"#192C3A", # picon backdrop
    "#94ADBD":"#819AAD",
    "#F8DCA3":"#F9D981",
    "#B5CCDE":"#B0C4D4",
    "#E3F0F9":"#D5E9F5",
    "#4ED9B4":"#55D9BA",
    "#A4C8E8":"#9DC9E6",
    "#5FEAC6":"#69E1C3",
    "#91CBFA":"#89CFFF",
    "#F0F6FA":"#ECF4F8",
    "#C3D7E5":"#A8BED0",
    "#A7BDD0":"#E7F1FA",
    "#A23E4C":"#8A343E",
    "#16855E":"#257955",
    "#A1802D":"#A78129",
    "#246F9F":"#286B9A",
    "#554581":"#473E69",
}
WIDGETS={
 "title","focus_hint","sat_picon","picon_fallback","sat_current",
 "context_info","epg","status","subtitles","left_head","right_head",
 "sat_list","source_list","verify","detail","key_red","key_green",
 "key_yellow","key_blue","key_menu"
}


def skin(src):
    tree=ast.parse(src)
    for statement in tree.body:
        if isinstance(statement,ast.Assign) and any(
                isinstance(t,ast.Name) and t.id=="PREVIEW_R74_FHD"
                for t in statement.targets):
            return ET.fromstring(ast.literal_eval(statement.value))
    raise ValueError("R74 Preview skin constant not found")


def preserve_layout(before,after):
    first=skin(before); second=skin(after)
    left=list(first.iter()); right=list(second.iter())
    if len(left)!=len(right):
        raise ValueError("R75 layout changed: element count mismatch")
    for idx,(old,new) in enumerate(zip(left,right)):
        if old.tag!=new.tag or (old.text or "").strip()!=(new.text or "").strip():
            raise ValueError("R75 layout changed at element %d" % idx)
        x={k:v for k,v in old.attrib.items()
           if k not in ("foregroundColor","backgroundColor")}
        y={k:v for k,v in new.attrib.items()
           if k not in ("foregroundColor","backgroundColor")}
        if x!=y:
            raise ValueError("R75 layout changed at element %d: %s" %
                             (idx,old.attrib.get("name") or old.tag))
    if first.attrib.get("size")!="1700,790" or second.attrib.get("size")!="1700,790":
        raise ValueError("Expected FHD 1700x790 unchanged")
    old_names=[el.attrib["name"] for el in left if el.tag=="widget"]
    new_names=[el.attrib["name"] for el in right if el.tag=="widget"]
    if set(old_names)!=WIDGETS or new_names!=old_names or len(old_names)!=20:
        raise ValueError("R75 widget order/count changed")
    return len(left),len(old_names)


def patch(src):
    if TAG in src:
        preserve_layout(src,src)
        return src,"already-installed"
    if OLD not in src:
        raise ValueError("Unexpected theme source; no modification")
    if src.count("PREVIEW_R74_FHD = ")!=1:
        raise ValueError("R74 Preview skin constant ambiguous")
    converted=src
    for current,classic in MAP.items():
        if current not in converted:
            raise ValueError("Theme palette drift; missing %s" % current)
        converted=converted.replace(current,classic)
    converted=converted.replace(OLD,
          "R75_NEO_DARK_CLASSIC_PALETTE: R73 colors with EXACT R75 layout",1)
    compile(converted,"preview_theme_r74.py","exec")
    preserve_layout(src,converted)
    return converted,"ready"


def atomic(path,data,mode):
    fd,temp=tempfile.mkstemp(prefix=".r75-skin-",suffix=".tmp",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(temp,stat.S_IMODE(mode))
        os.replace(temp,str(path))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument("--check",action="store_true")
    group.add_argument("--apply",action="store_true")
    group.add_argument("--rollback",action="store_true")
    parser.add_argument("--target",type=Path,default=TARGET,help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    path=args.target
    bak=path.with_name(BACKUP)
    if not path.is_file():
        parser.error("preview_theme_r74.py not installed")
    raw=path.read_bytes()
    try:src=raw.decode("utf-8")
    except UnicodeError:parser.error("Theme file is not UTF-8")
    mode=path.stat().st_mode
    if args.rollback:
        if TAG not in src or not bak.is_file():
            parser.error("Classic theme or backup is absent")
        saved=bak.read_bytes()
        compile(saved,path.name,"exec")
        preserve_layout(src,saved.decode("utf-8"))
        atomic(path,saved,mode)
        print("ROLLBACK_OK: previous R75 palette restored; restart GUI")
        return 0
    try:new,state=patch(src)
    except (SyntaxError,ValueError) as error:parser.error(str(error))
    if not args.apply:
        count,widget_count=preserve_layout(src,new)
        print("CHECK_OK:",state,"widgets=%d"%widget_count,"XML_nodes=%d"%count)
        print("R73 NEO DARK classic palette only; R75 positions/fonts/layout untouched")
        return 0
    if state=="already-installed":
        print("ALREADY_INSTALLED")
        return 0
    if bak.exists():
        parser.error("Existing R75 theme backup would be overwritten; refusing")
    # Refuse to replace installed skin if an unexpected variant exists.
    bak.write_bytes(raw)
    os.chmod(bak,0o600)
    try:atomic(path,new.encode("utf-8"),mode)
    except Exception:
        atomic(path,raw,mode)
        raise
    print("PALETTE_APPLIED: previous Neo Dark R73 colors; R75 layout identical")
    print("BACKUP:",bak)
    print("Restart Enigma2 GUI once")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
