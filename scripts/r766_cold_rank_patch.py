#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.6 safe cold-rank optimization (normal Preview only).

1. Do not rebuild decorated identity index by scanning every IPTV channel on
   the first Preview 24-candidate search. Deep/YELLOW retains existing rebuild.
   The already-built index is used whenever available.
2. Memoize SAT/stream country relation and reversed-title equivalence per
   stream *name* within a ranking request, across P/B1/B2 URL duplicates.
   Only performance changes: return values, scores, ordering and Auto Lock
   decisions are unchanged.
No player, mapping, DVB, EPG, scanner or persistent data code is modified.
"""
TAG="R766_COLD_RANK_FAST"

OLD_DECORATED='''        try:
            for ch in self._ensure_preview_decorated_index().get(target, ()):
                add(ch)
        except Exception:
            pass'''
NEW_DECORATED='''        # R766_COLD_RANK_FAST: never do an O(all IPTV services) decorated
        # rebuild during normal top24 Preview. The token index, exact names and
        # provider pools still run. Deep/YELLOW keeps the full fallback.
        try:
            decorated = getattr(self, "_preview_decorated_exact", None)
            ready = isinstance(decorated,dict) and bool(getattr(self,"_preview_decorated_ready",False))
            if not ready:
                decorated = (self._ensure_preview_decorated_index()
                             if limit > 24 else {})
            for ch in decorated.get(target, ()):
                add(ch)
        except Exception:
            pass'''
OLD_TITLECACHE='''        title_cache = {}
        market_prefs = set(str(x).upper() for x in (context.get("market_preferences") or []))'''
NEW_TITLECACHE='''        title_cache = {}
        # R766 same SAT / same IPTV service title -> same country/reversal
        # relationship, regardless of PRIMARY/BACKUP stream URL.
        relation_cache = {}
        market_prefs = set(str(x).upper() for x in (context.get("market_preferences") or []))'''
OLD_RELATION='''            country_relation,_sat_code,_ip_code=_r748_country_relation(sat_name,name)
            reordered=_r749_reordered_identity(sat_name,name)'''
NEW_RELATION='''            relation = relation_cache.get(name)
            if relation is None:
                country_relation,_sat_code,_ip_code=_r748_country_relation(sat_name,name)
                reordered=_r749_reordered_identity(sat_name,name)
                relation = (country_relation,reordered)
                relation_cache[name] = relation
            country_relation,reordered = relation'''

def once(s,old,new,name):
    n=s.count(old)
    if n!=1:raise AssertionError("R766 "+name+" source changed "+str(n))
    return s.replace(old,new,1)

def patch_core(src):
    if TAG in src:return src
    src=once(src,OLD_DECORATED,NEW_DECORATED,"decorated-index")
    src=once(src,OLD_TITLECACHE,NEW_TITLECACHE,"relations-cache")
    src=once(src,OLD_RELATION,NEW_RELATION,"country-reorder-relations")
    compile(src,"core.py","exec")
    return src

if __name__=="__main__":
    print("R766_CORE_PATCH_READY")
