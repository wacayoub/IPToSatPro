#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.12 *profiling-only* patch for NORMAL R76.11 Preview ranking.

No ranking candidates, scoring, decisions, limits, player, lock/mapping,
catalog/cache mechanics, or GUI layout are changed. Timings are numeric only.
"""
import ast

TAG = "R7612_NORMAL_PREVIEW_PHASE_TIMINGS"
VERSION = "1.0.46-r76.12-preview-phase-profile-beta"


def method_span(src,class_name,method_name):
    tree=ast.parse(src)
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==class_name)
    fns=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==method_name]
    assert len(fns)==1,(class_name,method_name,len(fns))
    return fns[0].lineno,fns[0].end_lineno


def replace_once(body,old,new):
    if body.count(old)!=1:
        raise AssertionError("R7612 changed anchor: "+repr(old[:100])+" count="+str(body.count(old)))
    return body.replace(old,new,1)


def patch_core(src):
    if TAG in src:
        return src
    start,end=method_span(src,"Catalog","fast_rank_matches_all_servers")
    lines=src.splitlines(keepends=True)
    body="".join(lines[start-1:end])
    old_method=ast.parse(body.lstrip()) if False else None
    body=replace_once(body,
        '        per_server = max(1, int(per_server)); limit = max(1, int(topn))',
        '''        # R7612_NORMAL_PREVIEW_PHASE_TIMINGS: no ranking behavior changes.
        _r7612_clock = __import__("time").monotonic
        _r7612_t0 = _r7612_clock()
        per_server = max(1, int(per_server)); limit = max(1, int(topn))''')
    body=replace_once(body,
        '''        if cached is not None:
            return cached[:limit]''',
        '''        if cached is not None:
            self._r733_last_profile = {"index_ms": 0, "score_ms": 0,
                "rescue_ms": 0, "sort_ms": 0, "scored": 0, "cache": 1,
                "total_ms": int((_r7612_clock()-_r7612_t0)*1000)}
            return cached[:limit]''')
    body=replace_once(body,
        '''            cap=nomination_cap)
        rows = []''',
        '''            cap=nomination_cap)
        _r7612_nomination_done = _r7612_clock()
        rows = []''')
    body=replace_once(body,
        '''        # The live fast pool intentionally starts from the rarest identity anchor.''',
        '''        _r7612_scoring_done = _r7612_clock()
        # The live fast pool intentionally starts from the rarest identity anchor.''')
    body=replace_once(body,
        '''        except Exception:
            pass

        def key(item):''',
        '''        except Exception:
            pass
        _r7612_rescue_done = _r7612_clock()

        def key(item):''')
    body=replace_once(body,
        '''        self._fast_cache_put(cache_key, out)
        return out''',
        '''        _r7612_sort_done = _r7612_clock()
        self._r733_last_profile = {
            "index_ms": int((_r7612_nomination_done-_r7612_t0)*1000),
            "score_ms": int((_r7612_scoring_done-_r7612_nomination_done)*1000),
            "rescue_ms": int((_r7612_rescue_done-_r7612_scoring_done)*1000),
            "sort_ms": int((_r7612_sort_done-_r7612_rescue_done)*1000),
            "total_ms": int((_r7612_sort_done-_r7612_t0)*1000),
            "scored": len(rows), "cache": 0,
        }
        self._fast_cache_put(cache_key, out)
        return out''')
    out="".join(lines[:start-1])+body+"".join(lines[end:])
    compile(out,"core.py","exec")
    return out


def patch_plugin(src):
    tag="R7612_PREVIEW_STAGE_NUMERIC_ONLY"
    if tag in src:
        return src
    old='''        _startup_log("PREVIEW_RANK_BG",
            "candidate_count=%d elapsed=%dms index=%dms scoring=%dms scored=%d cache=%d error=%s" %
            (len(ranked), elapsed, int(perf.get("index_ms") or 0),
             int(perf.get("score_ms") or 0),int(perf.get("scored") or 0),
             int(perf.get("cache") or 0),error[:50]))'''
    new=old+'''
        # R7612_PREVIEW_STAGE_NUMERIC_ONLY: no names, IPTV URLs or channel IDs.
        _startup_log("PREVIEW_STAGE",
            "total=%dms nominate=%dms score=%dms rescue=%dms sort=%dms cache=%d scored=%d" %
            (int(perf.get("total_ms") or 0), int(perf.get("index_ms") or 0),
             int(perf.get("score_ms") or 0), int(perf.get("rescue_ms") or 0),
             int(perf.get("sort_ms") or 0),int(perf.get("cache") or 0),
             int(perf.get("scored") or 0)))'''
    src=replace_once(src,old,new)
    compile(src,"plugin.py","exec")
    return src
