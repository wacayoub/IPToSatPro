#!/usr/bin/env python3
"""IPToSatPro R74.18: bounded/cancellable automatic fuzzy search, safely reversible.

R74 core ranks up to 900 candidates with expensive full scores after fast
SmartMatch finds no safe channel; some Vu+ Zero 4K searches take 19-61 seconds.
For automatic fallback ONLY, cheaply shortlist up to 96 candidates balanced
across server roles; score them with the ORIGINAL normal match_score_details.
Check generation/identity every 8 items to stop an obsolete search after zap.
The manual/deep search and ordinary core.rank_matches calls stay unchanged.

This patches core.py AND monitor.py as one guarded transaction, with independent
backups. No changes to Preview, beIN AAC, SAT tuner, EPG, decoder or mappings.
"""
import argparse
import os
import shutil
import stat
import tempfile
from pathlib import Path

ROOT=Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge")
CORE=ROOT/"core.py"
MONITOR=ROOT/"monitor.py"
CORE_BACKUP="core.py.r7418-fuzzy-original.bak"
MON_BACKUP="monitor.py.r7418-fuzzy-original.bak"
CORE_TAG="R7418_BOUNDED_FUZZY"
MON_TAG="R7418_BG_CANCEL_FUZZY"

CORE_SIGNATURE='''    def rank_matches(self, sat_name, language_priorities=None, context=None, topn=5, quality_mode="best"):'''
CORE_SIGNATURE_REPLACEMENT='''    def rank_matches(self, sat_name, language_priorities=None, context=None, topn=5, quality_mode="best", candidate_budget=None, should_abort=None):'''
CORE_KEY='''(int(topn),))'''
CORE_KEY_NEW='''(int(topn), int(candidate_budget or 0)))'''
CORE_SCORING='''        ranked = []
        for ch in self._candidate_pool(sat_name):
            enriched = _enrich_channel(ch)
            score, details = match_score_details(sat_name, enriched, language_priorities, context, quality_mode)
            ranked.append((enriched, score, details))'''
CORE_SCORING_NEW='''        # R7418_BOUNDED_FUZZY: the live fallback worker passes a CPU budget,
        # other callers (including manual search) retain the original full pool.
        pool = (self._r7418_nominate_fuzzy(sat_name, candidate_budget)
                if candidate_budget is not None else self._candidate_pool(sat_name))
        ranked = []
        for ix, ch in enumerate(pool):
            # Heavy SequenceMatcher scoring releases no GIL: stop a stale
            # worker as soon as the user zaps to another DVB service.
            if should_abort is not None and ix % 8 == 0 and should_abort():
                return []
            enriched = _enrich_channel(ch)
            score, details = match_score_details(sat_name, enriched, language_priorities, context, quality_mode)
            ranked.append((enriched, score, details))
        if should_abort is not None and should_abort():
            return []'''

CORE_METHOD='''    def _r7418_nominate_fuzzy(self, sat_name, candidate_budget):
        """Fast name-aware nomination; normal full scoring is unchanged.

        Cheap normalized-token sort over the existing 900-row maximum candidate
        pool. No video/player operations, HTTP requests or database writes.
        Diverse PRIMARY/BACKUP representation. No score accepted on heuristics:
        only the original match_score_details + match_decision may approve.
        """
        budget = max(16, min(256, int(candidate_budget or 96)))
        pool = self._candidate_pool(sat_name)
        if len(pool) <= budget:
            return pool
        target = normalize_name(sat_name or "")
        wanted = set(target.split())
        generic = {"tv","hd","fhd","sd","uhd","4k","2k","8k","h265","hevc",
                   "channel","channels","the","news","sports","sport",
                   "en","ar","fr","it","es","de","uk","us"}
        strong = wanted - generic
        numbers = set(x for x in wanted if x.isdigit())
        ranked = []
        for pos,ch in enumerate(pool):
            norm = str(ch.get("norm") or normalize_name(ch.get("name") or ""))
            tokens = set(norm.split())
            overlap = wanted.intersection(tokens)
            shared_strong = strong.intersection(tokens)
            candidate_numbers = set(x for x in tokens if x.isdigit())
            number_fit = (1 if numbers and numbers == candidate_numbers else
                          0 if not numbers or not candidate_numbers else -1)
            # Real identity evidence beats provider preference; score/match
            # threshold after selection still decides if IPTV is SAFE.
            priority = (
                int(bool(norm and norm == target)),
                int(bool(norm and norm.replace(" ","") == target.replace(" ",""))),
                len(shared_strong),
                number_fit,
                len(overlap),
                -abs(len(tokens)-len(wanted)),
                -pos)
            ranked.append((priority,ch))
        ranked.sort(key=lambda item:item[0],reverse=True)
        roles = set(str(ch.get("server_role") or "SERVER") for _,ch in ranked)
        quota = max(1,budget//max(1,len(roles)))
        seen = set()
        counts = {}
        chosen = []
        # First protect each server role against an overflowing other source.
        for _,ch in ranked:
            role = str(ch.get("server_role") or "SERVER")
            if counts.get(role,0)>=quota:
                continue
            ident=id(ch)
            if ident in seen:
                continue
            seen.add(ident)
            counts[role]=counts.get(role,0)+1
            chosen.append(ch)
            if len(chosen)>=budget:
                return chosen
        # Fill unused role quotas with globally strongest remaining nominees.
        for _,ch in ranked:
            if len(chosen)>=budget:
                break
            if id(ch) in seen:
                continue
            seen.add(id(ch))
            chosen.append(ch)
        return chosen

'''

MONITOR_OLD='''                    rows = catalog.rank_matches(name, languages, context=context, topn=32, quality_mode=qmode) or []'''
MONITOR_NEW='''                    # R7418_BG_CANCEL_FUZZY: 96/900 maximum detailed
                    # scores and cooperative cancellation on DVB zap/change.
                    # Manual Preview/deep search is NOT budgeted.
                    rows = catalog.rank_matches(
                        name, languages, context=context, topn=32,
                        quality_mode=qmode, candidate_budget=96,
                        should_abort=lambda: (
                            generation != int(self.smartmatch_generation)
                            or sat_ref != str(self.current_sat_ref_string or "")
                            or catalog is not self.catalog)) or []'''
MONITOR_LOG='''        self._log("MATCH_BG_START", "sat='%s' match='%s' stage=%s" % (self.current_sat_name, name, stage))'''
MONITOR_LOG_NEW='''        self._log("MATCH_BG_START", "sat='%s' match='%s' stage=%s budget=%s" % (
            self.current_sat_name, name, stage, "96" if stage=="fuzzy" else "fast-index"))'''


def once(src,old,new,where):
    found=src.count(old)
    if found!=1:
        raise ValueError("R7418 %s incompatible anchor count=%d"%(where,found))
    return src.replace(old,new,1)


def patch_core(src):
    if CORE_TAG in src:
        return src,"already-installed"
    src=once(src,CORE_SIGNATURE,CORE_METHOD+CORE_SIGNATURE_REPLACEMENT,
             "core rank_matches signature")
    # Patch exactly this one method, not the other fast rankers.
    begin=src.index(CORE_SIGNATURE_REPLACEMENT)
    end=src.find("\n    def ",begin+len(CORE_SIGNATURE_REPLACEMENT))
    if end<0:
        end=len(src)
    method=src[begin:end]
    method=once(method,CORE_KEY,CORE_KEY_NEW,"core fuzzy cache key")
    method=once(method,CORE_SCORING,CORE_SCORING_NEW,"core fuzzy score loop")
    src=src[:begin]+method+src[end:]
    compile(src,"core.py","exec")
    return src,"ready"


def patch_monitor(src):
    if MON_TAG in src:
        return src,"already-installed"
    src=once(src,MONITOR_OLD,MONITOR_NEW,"monitor fuzzy worker")
    src=once(src,MONITOR_LOG,MONITOR_LOG_NEW,"monitor background log")
    compile(src,"monitor.py","exec")
    return src,"ready"


def atomic_write(path,data,mode):
    fd,tmp=tempfile.mkstemp(prefix=".r7418-",suffix=".tmp",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as out:
            out.write(data);out.flush();os.fsync(out.fileno())
        os.chmod(tmp,stat.S_IMODE(mode))
        os.replace(tmp,str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    acts=p.add_mutually_exclusive_group()
    acts.add_argument("--check",action="store_true")
    acts.add_argument("--apply",action="store_true")
    acts.add_argument("--rollback",action="store_true")
    p.add_argument("--root",type=Path,default=ROOT,help=argparse.SUPPRESS)
    a=p.parse_args(argv)
    files=[(a.root/"core.py",a.root/CORE_BACKUP,patch_core,CORE_TAG),
           (a.root/"monitor.py",a.root/MON_BACKUP,patch_monitor,MON_TAG)]
    states=[]
    for path,backup,transform,tag in files:
        if not path.is_file():
            p.error(str(path.name)+" missing")
        raw=path.read_bytes()
        mode=path.stat().st_mode
        try:text=raw.decode("utf-8")
        except UnicodeError:p.error(str(path.name)+" not UTF-8")
        states.append((path,backup,transform,tag,raw,mode,text))
    if a.rollback:
        for path,backup,transform,tag,raw,mode,src in states:
            if tag not in src or not backup.is_file():
                p.error("Both installed R7418 files and backups required for rollback")
        saved=[(path,backup.read_bytes(),mode,raw) for
               path,backup,transform,tag,raw,mode,src in states]
        for path,data,mode,raw in saved:
            compile(data,str(path.name),"exec")
        written=[]
        try:
            for path,data,mode,raw in saved:
                atomic_write(path,data,mode);written.append((path,raw,mode))
        except Exception:
            for path,raw,mode in reversed(written):
                atomic_write(path,raw,mode)
            raise
        print("ROLLBACK_OK: core.py and monitor.py restored; restart GUI")
        return 0
    patches=[]
    for path,backup,transform,tag,raw,mode,src in states:
        try:updated,status=transform(src)
        except (ValueError,SyntaxError) as ex:p.error(str(ex))
        patches.append((path,backup,raw,mode,updated,status))
    statuses=[item[-1] for item in patches]
    if len(set(statuses))!=1:
        p.error("Inconsistent installation: core/monitor versions differ; refusing")
    if not a.apply:
        print("CHECK_OK:",statuses[0])
        print("Automatic fuzzy: at most 96 of 900 detailed scores, per-role names nominated")
        print("Obsolete scoring stops after SAT zap; full manual search unmodified")
        print("AAC, native FTA protection, maps, player and Preview unmodified")
        return 0
    if statuses[0]=="already-installed":
        print("ALREADY_INSTALLED")
        return 0
    if any(backup.exists() for path,backup,raw,mode,updated,status in patches):
        p.error("At least one R7418 backup already exists; refusing overwrite")
    for path,backup,raw,mode,updated,status in patches:
        shutil.copy2(str(path),str(backup))
    written=[]
    try:
        for path,backup,raw,mode,updated,status in patches:
            atomic_write(path,updated.encode("utf-8"),mode)
            written.append((path,raw,mode))
    except Exception:
        for path,raw,mode in reversed(written):
            atomic_write(path,raw,mode)
        raise
    print("PATCH_OK: core.py + monitor.py; backups:")
    for path,backup,raw,mode,updated,status in patches:
        print(" ",backup)
    print("Restart Enigma2 GUI; compare MATCH_BG_DONE fuzzy cost")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
