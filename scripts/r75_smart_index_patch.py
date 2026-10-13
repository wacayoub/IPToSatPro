#!/usr/bin/env python3
"""R75 SMART indexed shortlist reuse + no-match cross-zap debounce.

Original R74.18 96-score shortlist is preserved (not a low-score auto lock).
R75 memoizes index nominee arrays (no extra deep scorer runs), caps 48 keys
and invalidates by Catalog identity + 90 seconds. Repeated NO_MATCH on same
SAT ref/catalogue is remembered briefly across channel re-entry; new catalog
or manual lock selection still takes precedence in native monitor paths.

R75 updater uses STAGED beta feed on branch instead of main production R70.
"""
import re

CORE_TAG="R75_SMART_INDEX_MEMO"
MONITOR_TAG="R75_SMART_NEGATIVE_CACHE"
UPDATER_URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r75-smart-index-optimized/staging/r75-smart-index.update.json"

INDEX_WRAPPER='''    # R75_SMART_INDEX_MEMO
    def _r7418_nominate_fuzzy(self, sat_name, candidate_budget):
        """Reuse a small, per-catalog identity shortlist across repeat SAT zaps.

        Nomination depends on IPTV names/roles, not on current SAT CA/EPG, so
        original match_score_details still evaluates every nominee against
        actual current SAT context. Only indexes and shortlist are cached.
        """
        import time as _r75time
        cap=max(16,min(256,int(candidate_budget or 96)))
        key=(normalize_name(sat_name or ""),cap,id(self.channels),
             len(self.channels))
        now=_r75time.monotonic()
        cache=getattr(self,"_r75_fuzzy_index_cache",None)
        if not isinstance(cache,dict):
            cache={}
            self._r75_fuzzy_index_cache=cache
        cached=cache.get(key)
        if cached is not None and now-float(cached[0])<90.0:
            return list(cached[1])
        shortlist=self._r7418_nominate_fuzzy_uncached(sat_name,cap)
        cache[key]=(now,tuple(shortlist))
        while len(cache)>48:
            cache.pop(next(iter(cache)))
        return shortlist

    def _r7418_nominate_fuzzy_uncached(self, sat_name, candidate_budget):'''

MONITOR_FIRST='''        stage = "fuzzy" if str(stage) == "fuzzy" else "fast"'''
MONITOR_FIRST_REPLACE='''        stage = "fuzzy" if str(stage) == "fuzzy" else "fast"
        # R75_SMART_NEGATIVE_CACHE: avoid expensive retry on rapid back-and-
        # forth zap for the same NO_MATCH SAT / catalog generation / identity.
        # Never block a manual mapping: that is resolved before this method.
        if stage=="fast":
            import time as _r75_clock
            lookup=(sat_ref,id(catalog),name,qmode)
            recorded=getattr(self,"_r75_negative_match_cache",{}).get(lookup)
            if recorded is not None and _r75_clock.monotonic()-recorded<90.0:
                self.play_result="NO MATCH"
                self._set_state("NO_MATCH",
                     "IPTV not identified (short-lived negative cache)",
                     "no repeated full fuzzy scoring")
                self._log("MATCH_NEGATIVE_CACHE",
                          "sat='%s' max_age=90s no repeated CPU work" %
                          self.current_sat_name)
                return'''

MONITOR_NEGATIVE='''            self._r725_no_match_until = time.monotonic() + 45.0'''
MONITOR_NEGATIVE_REPLACE='''            self._r725_no_match_until = time.monotonic() + 45.0
            # R75 negative result bound to SAT identity AND catalog object.
            # New IPTV list swaps the Catalog and invalidates this key.
            # A manual GREEN mapping is resolved ahead of SmartMatch.
            import time as _r75_clock
            cache=getattr(self,"_r75_negative_match_cache",None)
            if not isinstance(cache,dict):
                cache={}
                self._r75_negative_match_cache=cache
            cache[(sat_ref,id(self.catalog),name,qmode)]=_r75_clock.monotonic()
            while len(cache)>64:
                cache.pop(next(iter(cache)))'''


def once(src,old,new,label):
    count=src.count(old)
    if count!=1:
        raise ValueError("R75 incompatible %s anchor count=%d"%(label,count))
    return src.replace(old,new,1)


def patch_core(src):
    if CORE_TAG in src:
        return src
    return_code='''    def _r7418_nominate_fuzzy(self, sat_name, candidate_budget):'''
    src=once(src,return_code,INDEX_WRAPPER,"r7418 shortlist wrapper")
    compile(src,"core.py","exec")
    return src


def patch_monitor(src):
    if MONITOR_TAG in src:
        return src
    src=once(src,MONITOR_FIRST,MONITOR_FIRST_REPLACE,"smartmatch stage")
    src=once(src,MONITOR_NEGATIVE,MONITOR_NEGATIVE_REPLACE,"negative fuzzy stage")
    compile(src,"monitor.py","exec")
    return src


def patch_updater(src):
    old='MANIFEST_URL = "https://raw.githubusercontent.com/wacayoub/IPToSatPro/main/update.json"'
    new='MANIFEST_URL = "'+UPDATER_URL+'"'
    src=once(src,old,new,"beta updater staged feed")
    compile(src,"updater.py","exec")
    return src
