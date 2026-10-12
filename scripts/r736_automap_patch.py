# -*- coding: utf-8 -*-
"""R73.6 shared Preview+AutoScan SAFE selector and automatic mapping.

Preview maps its selected SAT automatically when a green SAFE/ALLOWED
candidate exists. Existing user MANUAL locks win.
No player, audio, timeshift, service list, credentials, or live matcher changes.
"""
def one(src,old,new):
    n=src.count(old)
    if n!=1:
        raise AssertionError("R73.6 drift %d: %s"%(n,repr(old[:105])))
    return src.replace(old,new,1)

def patch_plugin(src):
    selector='''def _r736_choose_best_safe(sat_ref, sat_name, ctx, ranked, rejected=None):
    """One selection policy for Preview and full Auto Scan.

    Never auto-save unscored index-only REVIEW candidates, hard rejected
    variants, wrong numbered service, or known explicit feed conflicts.
    A high numerical score without SAFE/ALLOWED is not an authorization.
    """
    rejected = rejected or {}
    items=[]
    has_review=False
    for pos,entry in enumerate(ranked or []):
        try:
            ch,score,details=entry
            fp=channel_fingerprint(ch or {})
            if not fp or fp in rejected:
                continue
            details=dict(details or {})
            decision=match_decision(score,details,float(cfg.match_threshold.value))
            if decision not in ("SAFE","ALLOWED"):
                if decision=="REVIEW":
                    has_review=True
                continue
            if (ch or {}).get("_manual_candidate") or (ch or {}).get("_r732_index_only"):
                has_review=True
                continue
            identity=float(details.get("name") or 0)+float(details.get("equivalence") or 0)+float(details.get("variant") or 0)
            if identity < 70:
                has_review=True
                continue
            try:
                qual=quality_fit_key(ch,sat_name,ctx or {})
            except Exception:
                qual=(0,0,0,0,0)
            try:
                h=(MONITOR.stream_health or {}).get(fp,{}) if MONITOR is not None else {}
                w=int(h.get("width") or ch.get("actual_width") or 0)
                hh=int(h.get("height") or ch.get("actual_height") or 0)
            except Exception:
                w=hh=0
            measured=int(w>0 and hh>0)
            try:priority=int(ch.get("server_priority") or 0)
            except Exception:priority=0
            tier=2 if decision=="SAFE" else 1
            iband=4 if identity >= 99 else 3 if identity >= 92 else 2 if identity >= 82 else 1
            order=(tier,iband,identity,float(score or 0),measured,qual,
                   w*hh,-priority,-pos)
            items.append((order,ch,float(score or 0),details,decision))
        except Exception:
            continue
    if not items:
        return None,0.0,{},has_review
    items.sort(key=lambda x:x[0],reverse=True)
    _key,ch,score,details,decision=items[0]
    details=dict(details)
    details["auto_lock_original_decision"]=decision
    details["allow_reason"]=details.get("allow_reason") or ("AUTO BEST • %s"%decision)
    details["universal_auto_lock"]=True
    return ch,score,details,has_review


def _r736_auto_map_single_sat(sat_ref, sat_name, ctx, ranked):
    """Persist best SAFE result once, without an extra IPTV scan or zapping.

    Re-read mappings at the commit boundary to protect manual edits made
    while asynchronous Preview matching was in flight.
    """
    key=sat_service_key(sat_ref)
    if not key or not ranked:
        return "NO_SAFE",None
    existing=_load_overrides().get(key)
    if isinstance(existing,dict) and existing.get("channel_id") and not existing.get("auto_best_lock"):
        return "MANUAL_PROTECTED",None
    rejected={}
    try:
        bucket=_load_user_rejections().get(key,{})
        rejected=bucket.get("items",{}) if isinstance(bucket,dict) else {}
    except Exception:
        rejected={}
    ch,score,details,_review=_r736_choose_best_safe(sat_ref,sat_name,ctx,ranked,rejected)
    if ch is None:
        return "REVIEW_ONLY",None
    fp=channel_fingerprint(ch)
    if isinstance(existing,dict) and existing.get("auto_best_lock") and existing.get("channel_id")==fp:
        return "ALREADY_AUTO",ch
    record=_auto_scan_override_record(sat_ref,ch,sat_name,ctx,score=score,details=details)
    added,removed=_commit_auto_scan_overrides({key:record},{key})
    if added:
        return "AUTO_REPLACED" if removed else "AUTO_CREATED",ch
    return "MANUAL_PROTECTED",None


'''
    src=one(src,'def _auto_scan_override_record(sat_ref_string, channel, sat_name="", context=None, score=None, details=None):',
        selector+'def _auto_scan_override_record(sat_ref_string, channel, sat_name="", context=None, score=None, details=None):')
    # Bulk AutoScan uses the same green candidates as Preview, not a separate
    # slow fuzzy ranking and independent nomination truncation.
    src=one(src,
'''            sat_name, _sat_ref, ctx, ranked = _rank_sat_ref_all_servers(raw, topn=48, per_server=16)''',
'''            sat_name, _sat_ref, ctx = _match_context_for_sat_ref(raw)
            catalog=MONITOR.catalog if MONITOR is not None else None
            if catalog is None:
                raise ValueError("IPTV catalogue unavailable")
            priorities=[x.strip().upper() for x in cfg.languages.value.split(",") if x.strip()]
            ctx=dict(ctx or {})
            ctx["match_threshold"]=float(cfg.match_threshold.value)
            ranked=catalog.fast_preview_mega_matches(
                sat_name,priorities,context=ctx,per_server=64,topn=192,
                quality_mode=cfg.quality_mode.value)''')
    start=src.index('    def _pick_safe(self, raw, sat_name, context, ranked):')
    end=src.index('    def _scan_one(self, row):',start)
    src=src[:start]+'''    def _pick_safe(self, raw, sat_name, context, ranked):
        bucket=(self.user_rejections or {}).get(sat_service_key(raw),{})
        rejected=bucket.get("items",{}) if isinstance(bucket,dict) else {}
        return _r736_choose_best_safe(raw,sat_name,context,ranked,rejected)

'''+src[end:]
    # Complete shared-cache hits must auto-map too. Otherwise auto-mapping
    # would only run when a fresh background ranking happens and skip most
    # revisits after AutoScan has prewarmed the Preview candidate cache.
    src=one(src,
'''        self._r732_auto_rows = [dict(x or {}) for x in list(cached[2] or [])]
        self._r732_auto_page = 0
        self.channels = [dict(x) for x in self._r732_auto_rows[:48]]
        try: complete = bool(cached[3])''',
'''        self._r732_auto_rows = [dict(x or {}) for x in list(cached[2] or [])]
        self._r732_auto_page = 0
        self.channels = [dict(x) for x in self._r732_auto_rows[:48]]
        try: complete = bool(cached[3])''')
    # No changes in live mapping until complete scanned candidates become
    # available.  Both direct cache and fresh-work paths use the shared helper.
    src=one(src,
'''        try: complete = bool(cached[3])
        except Exception: complete = False
        self._refresh_epg_now_next(raw)''',
'''        try: complete = bool(cached[3])
        except Exception: complete = False
        if complete and self._r732_auto_rows:
            try:
                ranked_cached=[(dict(ch),
                    float(ch.get("_preview_score") or 0),
                    dict(ch.get("_preview_details") or {}))
                    for ch in self._r732_auto_rows]
                auto_state,_pick=_r736_auto_map_single_sat(raw,self.sat_name,
                    self.context,ranked_cached)
                _startup_log("PREVIEW_AUTO_MAP",
                    "sat=%r state=%s source=CACHE"%(self.sat_name,auto_state))
                if auto_state in ("AUTO_CREATED","AUTO_REPLACED"):
                    self._manual_overrides=_load_overrides()
            except Exception as auto_error:
                _startup_log("PREVIEW_AUTO_MAP",
                    "sat=%r state=ERROR source=CACHE error=%s"%
                    (self.sat_name,str(auto_error)[:100]))
        self._refresh_epg_now_next(raw)''')
    # Persist on Preview GUI thread after full background ranking completes.
    # The CPU-only worker does not modify disk files.
    src=one(src,
'''        if error:
            return
        key = sat_service_key(raw)
        channels = _preview_channel_rows(ranked)''',
'''        if error:
            return
        try:
            automap_state,_chosen = _r736_auto_map_single_sat(raw,sat_name,ctx,ranked)
            _startup_log("PREVIEW_AUTO_MAP",
                "sat=%r state=%s ranked=%d selected=%r" %
                (sat_name,automap_state,len(ranked),
                 (_chosen or {}).get("name") or ""))
            if automap_state in ("AUTO_CREATED","AUTO_REPLACED"):
                self._manual_overrides=_load_overrides()
        except Exception as auto_err:
            _startup_log("PREVIEW_AUTO_MAP",
                "sat=%r state=ERROR error=%s"%(sat_name,str(auto_err)[:120]))
        key = sat_service_key(raw)
        channels = _preview_channel_rows(ranked)''')
    return src
