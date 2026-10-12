#!/usr/bin/env python3
"""R74.12: cap NORMAL Preview ranked IPTV candidates at 24 (8 per role).

The old 192 candidates/64 per-role one-shot scan can take ~20s on Vu+ Zero 4K.
Only the Preview worker quota changes. Bulk auto-scan still uses topn=192 and
per_server=64. Existing SAFE auto-map and provider/language/resolution
priorities remain as in the installed plugin; manual locks and TOD AAC fix
are unchanged. Use Preview numeric 5 to search the full catalogue manually.
Requires previously applied r7411 Preview priority fix.
"""
import argparse
import os
import shutil
import stat
import tempfile
from pathlib import Path

TARGET=Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/plugin.py")
BACKUP="plugin.py.r7412-fast-shortlist-original.bak"
TAG="R7412_FAST_PREVIEW_SHORTLIST"
ORIGINAL='''        candidate_budget = 192
        candidate_per_server = 64'''
UPDATED='''        # R7412_FAST_PREVIEW_SHORTLIST: fast normal Preview, not bulk scan.
        # Detailed FULL catalogue lookup remains available via key 5 SEARCH.
        candidate_budget = 24
        candidate_per_server = 8'''


def patch(source):
    if TAG in source:
        return source,"already-installed"
    if "R7411_STAY_PREVIEW_PROVIDER_LANGUAGE_RESOLUTION" not in source:
        raise ValueError("Please install R7411 Preview ranking/stay-open first")
    if source.count(ORIGINAL)!=1:
        raise ValueError("Expected R74 Preview quota exactly once; aborting on source drift")
    updated=source.replace(ORIGINAL,UPDATED,1)
    compile(updated,"plugin.py","exec")
    return updated,"ready"


def atomic_replace(path,data,mode):
    fd,tmp=tempfile.mkstemp(prefix=".r7412-",suffix=".tmp",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,stat.S_IMODE(mode))
        os.replace(tmp,str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    action=parser.add_mutually_exclusive_group()
    action.add_argument("--check",action="store_true")
    action.add_argument("--apply",action="store_true")
    action.add_argument("--rollback",action="store_true")
    parser.add_argument("--target",type=Path,default=TARGET,help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    p=args.target
    bak=p.with_name(BACKUP)
    if not p.is_file():
        parser.error("Cannot locate installed plugin.py")
    current=p.read_bytes()
    mode=p.stat().st_mode
    try:
        source=current.decode("utf-8")
    except UnicodeDecodeError:
        parser.error("Not UTF-8")
    if args.rollback:
        if TAG not in source or not bak.is_file():
            parser.error("Recognized R7412 patch or backup not found")
        previous=bak.read_bytes()
        compile(previous,"plugin.py","exec")
        atomic_replace(p,previous,mode)
        print("ROLLBACK_OK: previous plugin.py restored; restart GUI")
        return 0
    try:
        changed,status=patch(source)
    except (ValueError,SyntaxError) as error:
        parser.error(str(error))
    if not args.apply:
        print("CHECK_OK:",status)
        print("Normal Preview: up to 24 nominees, 8/source role; full 5 SEARCH kept")
        print("R7411 priority, Preview stay-open, bulk AutoScan, live player, TOD AAC unchanged")
        return 0
    if status=="already-installed":
        print("ALREADY_INSTALLED")
        return 0
    if bak.exists():
        parser.error("Previous backup already exists; do not overwrite")
    shutil.copy2(str(p),str(bak))
    try:
        atomic_replace(p,changed.encode("utf-8"),mode)
    except Exception:
        atomic_replace(p,current,mode)
        raise
    print("PATCH_OK: saved backup="+str(bak))
    print("Restart Enigma2 GUI")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
