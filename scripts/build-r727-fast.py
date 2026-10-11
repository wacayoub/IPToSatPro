#!/usr/bin/env python3
"""R72.7 SmartMatch fuzzy reuse for fast repeat zaps, SHA pinned to R72.6.

Core's full fuzzy rank_matches() currently recomputes ALL score/details on
EVERY zap, whereas fast_rank_matches() has an LRU. Keep exactly the same fuzzy
ranking and quality/security decisions but memoize its result briefly per
channel, language, market, source context and quality target. Invalidate
immediately upon observed video resolution change. This avoids repeat 9.8s
fuzzy work on Digi 24 / uncached ambiguous services without tampering with
the player, monitor events, user locks, timeshift, or Fast Zap timing.
"""
import ast,base64,hashlib,importlib.util,json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r726",R/"scripts/build-r726-safe-match.py")
base=importlib.util.module_from_spec(sp);sp.loader.exec_module(base)
pack=base.pack; P=base.P; CORE=P+"core.py"; MONITOR=base.MONITOR;PLUGIN=base.PLUGIN;UPDATER=base.UPDATER
B64=R/"payload/r726-digi24-safe.b64"
SIZE=405038
SHA="9b7efbef03368c9a97b86c265574dbd9389401b7d5b014a50e427eaaf267859b"
OLD="1.0.46-r72.6-digi24-safe-beta"
NEW="1.0.46-r72.7-fuzzy-cache-beta"
CHANGELOG=P+"CHANGELOG-r727-FAST-ZAP-CACHE.txt"

def once(s,a,b):
    n=s.count(a)
    if n!=1:raise AssertionError("r727 exact core anchor drift hits=%d: %s"%(n,a[:140]))
    return s.replace(a,b,1)

def patch_core(raw):
    s=raw.decode()
    old='''    def rank_matches(self, sat_name, language_priorities=None, context=None, topn=5, quality_mode="best"):
        ranked = []
        for ch in self._candidate_pool(sat_name):'''
    new='''    def rank_matches(self, sat_name, language_priorities=None, context=None, topn=5, quality_mode="best"):
        # R72.7: bounded short-lived memoization of the expensive fuzzy lane.
        # Includes SAT name, audio languages, market/provider context, quality
        # target, and topn. It never changes the actual matcher or score.
        # Catalog instances own their cache, and observed video quality updates
        # below invalidate it immediately. A 90-second cap prevents stale
        # market/stream evidence from persisting indefinitely.
        import time as _r727_time
        key = self._fast_cache_key("fuzzy_r727", sat_name,
                                   language_priorities, context, quality_mode,
                                   (int(topn),))
        cache = getattr(self, "_r727_fuzzy_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._r727_fuzzy_cache = cache
        now = _r727_time.monotonic()
        cached = cache.get(key)
        if cached is not None:
            if (now - float(cached[0])) < 90.0:
                return list(cached[1])
            cache.pop(key, None)
        ranked = []
        for ch in self._candidate_pool(sat_name):'''
    s=once(s,old,new)
    oldreturn='''        ranked.sort(key=_rank_key, reverse=True)
        return ranked[:max(1, int(topn))]

'''
    newreturn='''        ranked.sort(key=_rank_key, reverse=True)
        out = ranked[:max(1, int(topn))]
        # Max 16 fuzzy identities held in RAM. Threaded worker does not share
        # its result with another catalog object or persist it to disk.
        cache[key] = (now, tuple(out))
        while len(cache) > 16:
            cache.pop(next(iter(cache)))
        return out

'''
    s=once(s,oldreturn,newreturn)
    original='''        label, rank, source = effective_quality_info(ch)
        ch["quality"] = label; ch["quality_rank"] = rank; ch["quality_source"] = source
        return ch'''
    changed='''        label, rank, source = effective_quality_info(ch)
        ch["quality"] = label; ch["quality_rank"] = rank; ch["quality_source"] = source
        # Newly confirmed decoder dimensions change quality ranking for both
        # SAT auto-matches and future zaps. Never reuse pre-observation scores.
        cache = getattr(self, "_r727_fuzzy_cache", None)
        if isinstance(cache, dict):
            cache.clear()
        return ch'''
    s=once(s,original,changed)
    before=ast.parse(raw)
    after=ast.parse(s)
    def methods(tree):
        out={}
        for node in ast.walk(tree):
            if isinstance(node,ast.FunctionDef) and node.name in ("rank_matches","set_observed_quality"):
                out[node.name]=ast.dump(node,include_attributes=False)
        return out
    a,b=methods(before),methods(after)
    assert set(a)==set(b)=={"rank_matches","set_observed_quality"}
    assert all(a[x]!=b[x] for x in a)
    compile(s,CORE,"exec")
    return s.encode()

def build(output=None):
    raw=base64.b64decode(B64.read_bytes())
    assert len(raw)==SIZE and hashlib.sha256(raw).hexdigest()==SHA
    parts=pack.unpack_ar(raw)
    before=pack.members_from(parts["data.tar.gz"])
    ctrls=pack.members_from(parts["control.tar.gz"])
    changes={CORE:patch_core(before[CORE])}
    for p,var in ((PLUGIN,"PLUGIN_VERSION"),(UPDATER,"CURRENT_VERSION")):
        src=before[p].decode(); token='%s = "%s"'%(var,OLD)
        assert src.count(token)==1
        changes[p]=src.replace(token,'%s = "%s"'%(var,NEW),1).encode()
    ctrl=ctrls["control"].decode()
    assert ctrl.count("Version: "+OLD)==1
    control=ctrl.replace("Version: "+OLD,"Version: "+NEW,1).encode()
    adds={CHANGELOG:(
      "R72.7: bounded fuzzy matching result cache for repeat zaps (16 entries/90s), "
      "identity key includes SAT channel/language/context/quality. Immediate "
      "invalidation on newly measured decoded resolution. Ranking score, hard "
      "REJECT, R72.6 Digi24 no-signal rules, Preview and streamer player fully "
      "preserved. First-ever uncached fuzzy search and poor upstream servers may "
      "still take longer than 2s. Receiver hardware not yet tested.\n").encode()}
    parts["data.tar.gz"]=pack.make_tar(parts["data.tar.gz"],changes,adds)
    parts["control.tar.gz"]=pack.make_tar(parts["control.tar.gz"],{"control":control})
    dest=Path(output) if output else R/"r727-fuzzy-cache-beta.ipk"
    if dest.exists():dest.unlink()
    binary=pack.assemble(parts,dest)
    after=pack.members_from(pack.unpack_ar(binary)["data.tar.gz"])
    ca=pack.members_from(pack.unpack_ar(binary)["control.tar.gz"])
    assert set(after)==set(before)|set(adds)
    for p,blob in before.items():assert after[p]==changes.get(p,blob),p
    for p,blob in ctrls.items():assert ca[p]==(control if p=="control" else blob),p
    for path,blob in after.items():
        if path.endswith(".py"):compile(blob,path,"exec")
    meta={"version":NEW,"size":len(binary),"sha256":hashlib.sha256(binary).hexdigest(),
       "modified":sorted(changes),"protected_unchanged":len(before)-len(changes),
       "receiver_tested":False,"main_published":False,"scoring_unchanged":True,"player_changed":False}
    print("R727_FAST_FUZZY_CACHE_BUILD_OK",json.dumps(meta,sort_keys=True))
    return meta
if __name__=="__main__":build(sys.argv[1] if len(sys.argv)>1 else None)
