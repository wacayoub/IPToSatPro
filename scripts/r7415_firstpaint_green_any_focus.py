#!/usr/bin/env python3
"""IPToSatPro R74.15: instant candidates from empty initial cache + GREEN from SAT focus.

R7414 can miss the instant seed because Preview always creates an incomplete
cache entry (sometimes empty) at construction; _sat_selection_changed() goes
directly to _load_selected_sat_candidates and bypasses the R7414 seed.
Additionally, Preview starts with focus LEFT and _lock() rejects GREEN until
some other action moves focus right. Neither should require OK/playing.

This guarded, reversible change only touches plugin.py. No player, stream relay,
audio, EPG, tuner, auto-mapper, manual-lock database or timeshift edits.
"""
import argparse
import os
import shutil
import stat
import tempfile
from pathlib import Path

TARGET=Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/plugin.py")
BACKUP="plugin.py.r7415-firstpaint-green-original.bak"
TAG="R7415_FIRSTPAINT_GREEN_ANY_FOCUS"

HELPER_OLD='''        sources = groups.get(key, ()) if key else ()
        result = []
        seen = set()'''
HELPER_NEW='''        sources = groups.get(key, ()) if key else ()
        # R7415: exact decoration may differ (EN/AR, country, IPTV prefix).
        # Use the already-indexed tiny identity pool if the exact bucket is empty.
        # Do not run fuzzy scoring or enumerate the whole IPTV catalogue.
        if not sources and catalog is not None:
            import re
            wanted = set((key or "").split())
            wanted_nums = set(x for x in wanted if x.isdigit())
            stops = {"tv", "channel", "en", "ar", "fr", "de", "it", "es",
                     "hd", "fhd", "uhd", "4k", "sd"}
            wanted_tags = wanted - wanted_nums - stops
            pool = catalog._fast_candidate_pool(
                sat_name, per_server=8, total_cap=48)
            filtered = []
            for src in pool[:48]:
                label = normalize_name(src.get("name") or "")
                tags = set(label.split())
                nums = set(x for x in tags if x.isdigit())
                if wanted_nums and nums and wanted_nums != nums:
                    continue
                overlap = len(wanted_tags.intersection(tags))
                if overlap < min(2, len(wanted_tags)) or not overlap:
                    continue
                filtered.append(src)
            sources = filtered
        result = []
        seen = set()'''

LOAD_ORIGINAL='''        self._r732_auto_rows = [dict(x or {}) for x in list(cached[2] or [])]
        self._r732_auto_page = 0
        self.channels = [dict(x) for x in self._r732_auto_rows[:48]]'''
LOAD_UPDATED='''        # R7415_FIRSTPAINT_GREEN_ANY_FOCUS: the initial cache may be EMPTY but
        # incomplete, so load a bounded indexed seed here BEFORE waiting for
        # the 4-second full background worker. No Auto Mapping of these seeds.
        seeded = False
        if not complete and not (cached[2] or []):
            try:
                cat = MONITOR.catalog if MONITOR is not None else None
                first = _r7414_fast_exact_seed(self.sat_name, cat)
            except Exception:
                first = []
            if first:
                cached = (cached[0], dict(cached[1] or {}), first, False)
                self._candidate_cache[key] = cached
                seeded = True
                _startup_log("PREVIEW_INSTANT_SEED",
                             "source=EMPTY_CACHE count=%d sat=%r" %
                             (len(first),str(self.sat_name)[:70]))
        self._r732_auto_rows = [dict(x or {}) for x in list(cached[2] or [])]
        self._r732_auto_page = 0
        self.channels = [dict(x) for x in self._r732_auto_rows[:48]]
        if seeded:
            # First paint BEFORE slower EPG/context updates. Main render still
            # occurs normally later in this method; no extra scan is launched.
            try:
                self._render_source_list(keep_index=False)
                self._update_header()
            except Exception:
                pass'''

GREEN_ORIGINAL='''        if self.focus != "right":
            self["detail"].setText("GREEN saves selected IPTV source without mandatory OK test • press RIGHT, select candidate")
            return
        selected = self._selected_channel()'''
GREEN_UPDATED='''        # R7415: GREEN is an explicit manual-lock command on the currently
        # highlighted IPTV candidate. Preview opens focused LEFT by default.
        # No need to press RIGHT/OK/play first if candidate rows exist.
        if self.focus != "right":
            if not self.channels:
                self["detail"].setText("No IPTV candidate selected yet • wait for candidates or use YELLOW")
                return
            try:
                self._set_focus("right")
            except Exception:
                self.focus = "right"
        selected = self._selected_channel()'''


def replace_exact(source,old,new,label):
    count=source.count(old)
    if count!=1:
        raise ValueError("Incompatible R74 source at %s (anchor count %d)"%(label,count))
    return source.replace(old,new,1)


def patch(source):
    if TAG in source:
        return source,"already-installed"
    for marker in ("R7411_STAY_PREVIEW_PROVIDER_LANGUAGE_RESOLUTION",
                   "R7412_FAST_PREVIEW_SHORTLIST",
                   "R7413_PREVIEW_INLINE_NO_HIDE",
                   "R7414_PREVIEW_FAST_SEED_MANUAL_LOCK"):
        if marker not in source:
            raise ValueError("Prerequisite hotfix missing: "+marker)
    updated=replace_exact(source,HELPER_OLD,HELPER_NEW,"indexed fallback")
    updated=replace_exact(updated,LOAD_ORIGINAL,LOAD_UPDATED,"empty initial cache")
    updated=replace_exact(updated,GREEN_ORIGINAL,GREEN_UPDATED,"GREEN left-focus gate")
    compile(updated,"plugin.py","exec")
    return updated,"ready"


def atomic_write(path,data,mode):
    fd,tmp=tempfile.mkstemp(prefix=".r7415-",suffix=".tmp",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        os.chmod(tmp,stat.S_IMODE(mode))
        os.replace(tmp,str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    group=ap.add_mutually_exclusive_group()
    group.add_argument("--check",action="store_true")
    group.add_argument("--apply",action="store_true")
    group.add_argument("--rollback",action="store_true")
    ap.add_argument("--target",type=Path,default=TARGET,help=argparse.SUPPRESS)
    opt=ap.parse_args(argv)
    path=opt.target
    bak=path.with_name(BACKUP)
    if not path.is_file():
        ap.error("plugin.py missing")
    raw=path.read_bytes()
    try:source=raw.decode("utf-8")
    except UnicodeError:ap.error("plugin.py is not UTF-8")
    mode=path.stat().st_mode

    if opt.rollback:
        if TAG not in source or not bak.is_file():
            ap.error("R7415 is not recognized or backup missing")
        original=bak.read_bytes()
        compile(original,"plugin.py","exec")
        atomic_write(path,original,mode)
        print("ROLLBACK_OK: R7414 restored; restart Enigma2 GUI")
        return 0

    try:updated,status=patch(source)
    except (ValueError,SyntaxError) as e:ap.error(str(e))
    if not opt.apply:
        print("CHECK_OK:",status)
        print("GREEN locks selected IPTV candidate from LEFT or RIGHT without OK/play")
        print("First paint from empty provisional cache; no full IPTV scan or player change")
        print("Protects TOD AAC, mappings, existing rank 24 and YELLOW deep search")
        return 0
    if status=="already-installed":
        print("ALREADY_INSTALLED")
        return 0
    if bak.exists():
        ap.error("Backup exists; refusing to overwrite")
    shutil.copy2(str(path),str(bak))
    try:atomic_write(path,updated.encode("utf-8"),mode)
    except Exception:
        atomic_write(path,raw,mode)
        raise
    print("PATCH_OK: backup="+str(bak))
    print("Restart Enigma2 GUI and try GREEN without OK")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
