#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.4: merge fast index candidates even if R74 first seed/cache contains 1.

Previously the no-cached-sources test skipped the larger local index
whenever legacy Preview had one manually locked or R74.14 instant source.
This produced 1 instant source, then 24 after a 5-10s scorer.
R76.4 paints all available locally indexed plausible candidates before waiting
for the background score worker; all early candidates remain REVIEW/IDX.
"""
TAG="R764_MULTI_CANDIDATE_FIRST_PAINT"

OLD_GATE='''        seeded = False
        if not complete and not (cached[2] or []):'''
NEW_GATE='''        # R764_MULTI_CANDIDATE_FIRST_PAINT: a cached ONE-SOURCE seed is
        # *not* the complete immediate shortlist. Enrich it without scoring.
        seeded = False
        if not complete and len(cached[2] or []) < 24:'''

OLD_ASSIGN='''            if first:
                cached = (cached[0], dict(cached[1] or {}), first, False)
                self._candidate_cache[key] = cached
                seeded = True
                _startup_log("PREVIEW_INSTANT_SEED",
                             "source=EMPTY_CACHE count=%d sat=%r" %
                             (len(first),str(self.sat_name)[:70]))'''
NEW_ASSIGN='''            if first:
                # Keep original lock/source first (never replace or forget it).
                # Fingerprints avoid duplicates across PRIMARY/BACKUP and
                # different server URLs; no network or playback here.
                previous=[dict(x or {}) for x in (cached[2] or [])]
                combined=list(previous)
                known=set()
                for item in previous:
                    try: known.add(channel_fingerprint(item))
                    except Exception: pass
                for item in first:
                    try: fp=channel_fingerprint(item)
                    except Exception: continue
                    if not fp or fp in known:
                        continue
                    known.add(fp)
                    combined.append(dict(item))
                    if len(combined)>=24:
                        break
                if len(combined)>len(previous):
                    cached = (cached[0], dict(cached[1] or {}), combined, False)
                    self._candidate_cache[key] = cached
                    seeded = True
                    _startup_log("PREVIEW_INSTANT_SEED",
                        "source=ENRICHED count=%d before=%d sat=%r" %
                        (len(combined),len(previous),str(self.sat_name)[:70]))'''

OLD_TARGET='''    target=[t for t in tokens if t not in noise]
    if not target:'''
NEW_TARGET='''    # Common SAT broadcast affixes: OSNtv vs OSN, HBOtv vs HBO.
    # Keep all channel numbers and family/genre tokens to prevent mixups.
    normalized=[]
    for t in tokens:
        if t.endswith("tv") and len(t)>3:
            normalized.append(t[:-2])
        else:
            normalized.append(t)
    target=[t for t in normalized if t not in noise]
    if not target:'''

OLD_CANDIDATE='''        candidate=set(_r763_re.findall(r"[a-z0-9]+",key.lower()))-noise'''
NEW_CANDIDATE='''        if target[-1] not in key.lower():
            continue
        candidate=set(
            (t[:-2] if t.endswith("tv") and len(t)>3 else t)
            for t in _r763_re.findall(r"[a-z0-9]+",key.lower())
            if t not in noise)'''

OLD_OVERLAP="        overlap=len(set(target)&candidate)"
NEW_OVERLAP="        # Final identity token: Family does not match Action.\n        if target[-1] not in candidate:\n            continue\n        overlap=len(set(target)&candidate)"

OLD_BOUND='''        if i>=12000:
            break'''
NEW_BOUND='''        # Check the entire already-indexed name space. A late server may
        # begin after key #12000; bounded guard is for pathological catalogues.
        if i>=40000:
            break'''


def replace_one(s,a,b,part):
    n=s.count(a)
    if n!=1:
        raise AssertionError("R764 expected "+part+" once; got %s"%n)
    return s.replace(a,b,1)


def patch_plugin(src):
    if TAG in src:
        return src
    if "R763_FAST_INDEX_BEST_MEDAL" not in src:
        raise AssertionError("R764 requires real R76.3 indexed Preview")
    for name,old,new in (
       ("single seed gate",OLD_GATE,NEW_GATE),
       ("seed merge",OLD_ASSIGN,NEW_ASSIGN),
       ("SAT alias normalization",OLD_TARGET,NEW_TARGET),
       ("IPTV alias normalization",OLD_CANDIDATE,NEW_CANDIDATE),
       ("distinguishing identity",OLD_OVERLAP,NEW_OVERLAP),
       ("all indexed servers",OLD_BOUND,NEW_BOUND)):
        src=replace_one(src,old,new,name)
    compile(src,"plugin.py","exec")
    return src


if __name__=="__main__":
    print("R764_MULTI_SOURCE_FIRST_PAINT_PATCH_READY")
