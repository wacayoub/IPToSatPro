#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.9: full Manual Mapping ranking in background Preview, first paint retained."""
TAG="R769_PREVIEW_MANUAL_PARITY"
HELPER='''def _r769_preview_sat_context(raw, session):
    """Reuse live metadata only when the current SAT ref exactly matches."""
    sat_name, _ref, context = _match_context_for_sat_ref(raw)
    ctx = dict(context or {})
    provider = str(ctx.get("provider") or "").strip().upper()
    if provider not in ("", "-", "UNKNOWN"):
        return sat_name, ctx
    try:
        live_name, live_ref, live_ctx = _match_context_for_current(session)
        if live_ref and sat_service_key(live_ref) == sat_service_key(raw):
            for key, value in dict(live_ctx or {}).items():
                if value not in (None, "", [], {}):
                    ctx[key] = value
            return clean_display_name(live_name or sat_name) or sat_name, ctx
    except Exception:
        pass
    return sat_name, ctx


'''
OLD_CONTEXT='''        try:
            sat_name, _ref, ctx = _match_context_for_sat_ref(raw)
            catalog = MONITOR.catalog if MONITOR is not None else None'''
NEW_CONTEXT='''        try:
            sat_name, ctx = _r769_preview_sat_context(raw, self.session)
            catalog = MONITOR.catalog if MONITOR is not None else None'''
OLD_WORKER='''        # R7412_FAST_PREVIEW_SHORTLIST: cheap normal Preview; full deep on YELLOW.
        # Bulk AutoScan is a separate function and retains its own 192 budget.
        candidate_budget = 192 if self._r71_worker_deep else 24
        candidate_per_server = 64 if self._r71_worker_deep else 8
        def worker():
            try:
                ranked = catalog.fast_preview_mega_matches(
                    sat_name, priorities, context=dict(ctx),
                    per_server=candidate_per_server, topn=candidate_budget,
                    quality_mode=quality_mode)'''
NEW_WORKER='''        # R769_PREVIEW_MANUAL_PARITY: keep quick unranked first paint.
        # Normal background uses 48/16 Manual Mapping. DEEP stays 192/64.
        candidate_budget = 192 if self._r71_worker_deep else 48
        candidate_per_server = 64 if self._r71_worker_deep else 16
        def worker():
            try:
                if self._r71_worker_deep:
                    ranked = catalog.fast_preview_mega_matches(
                        sat_name, priorities, context=dict(ctx),
                        per_server=candidate_per_server, topn=candidate_budget,
                        quality_mode=quality_mode)
                else:
                    ranked = catalog.fast_rank_matches_all_servers(
                        sat_name, priorities, context=dict(ctx),
                        per_server=candidate_per_server, topn=candidate_budget,
                        quality_mode=quality_mode)'''

# Mirror Manual Mapping's *actual* display ordering, not Preview's secondary
# identity/reliability ranking.  Sorting does not probe streams or play video.
MANUAL_SORT_METHOD = '''    def _sort_candidates_with_cached_evidence(self, channels, context=None):
        """The same SAFE/identity/provider/quality/score ordering as Manual Mapping."""
        rows = [dict(ch) for ch in list(channels or []) if isinstance(ch, dict)]
        ctx = dict(context or self.context or {})
        manual = self._manual_overrides.get(self._sat_key()) if isinstance(self._manual_overrides, dict) else None
        manual_fp = str(manual.get("channel_id") or "") if isinstance(manual, dict) else ""
        def key(ch):
            details = ch.get("_preview_details") if isinstance(ch.get("_preview_details"), dict) else {}
            try: score = float(ch.get("_preview_score"))
            except (ValueError, TypeError): score = -9999.0
            fp = channel_fingerprint(ch)
            if fp in self._user_rejected_ids:
                decision = "USER REJECT"
            elif (manual_fp and manual_fp == fp) or details.get("manual") or ch.get("_r735_verified_manual_lock"):
                decision = "MANUAL"
            else:
                decision = self._candidate_decision(ch)
            tier = {"MANUAL":5,"SAFE":4,"ALLOWED":3,"REVIEW":2,"REJECT":0,"USER REJECT":0}.get(decision,0)
            try:
                identity = float(details.get("name",0)) + float(details.get("equivalence",0)) + float(details.get("variant",0))
            except (ValueError,TypeError): identity = 0.0
            identity_band = 3 if identity >= 99 else (2 if identity >= 90 else (1 if identity >= 78 else 0))
            try: qfit = quality_fit_key(ch,self.sat_name,ctx)
            except Exception: qfit = (0,0,0,0)
            provider_band = 1 if details.get("provider_identity") else 0
            try: priority = -int(ch.get("server_priority",999))
            except (ValueError,TypeError): priority = -999
            return (tier,identity_band,provider_band,qfit,score,priority)
        rows.sort(key=key,reverse=True)
        return rows
'''

# Keep the existing two-panel Enigma2 Preview layout and its remote actions.
# Only change displayed contents: the Manual Mapping score/status/market/audio/
# REAL resolution/provider are shown in the right-side source list.
MANUAL_RESULTS_METHOD = '''    def _render_source_list(self, keep_index=True):
        idx = self._source_index_now() if keep_index else self.selected_index
        rows = []
        best_marked = False
        manual = self._manual_overrides.get(self._sat_key()) if isinstance(self._manual_overrides, dict) else None
        manual_fp = str(manual.get("channel_id") or "") if isinstance(manual,dict) else ""
        for n,ch in enumerate(self.channels,1):
            fp = channel_fingerprint(ch)
            details = ch.get("_preview_details") if isinstance(ch.get("_preview_details"),dict) else {}
            indexed = bool(ch.get("_r763_fast_index") or ch.get("_r7414_seed"))
            try: score = float(ch.get("_preview_score"))
            except (ValueError,TypeError): score = None
            if fp in self._user_rejected_ids:
                decision = "USER REJECT"
            elif (manual_fp and fp == manual_fp) or details.get("manual") or ch.get("_r735_verified_manual_lock"):
                decision = "MANUAL"
            else:
                decision = self._candidate_decision(ch)
            usable = decision in ("MANUAL","SAFE","ALLOWED")
            if decision == "MANUAL":
                flag = "LOCKED"
            elif indexed or score is None:
                flag = "INDEX"
            elif decision == "USER REJECT":
                flag = "USER REJECT"
            elif usable and not best_marked:
                flag = "BEST " + decision
            else:
                flag = decision
            if usable and score is not None:
                best_marked = True
            tag,state = self._source_tag(ch, best_available=(usable and score is not None and flag.startswith("BEST")))
            if tag == "AUDIO MISMATCH":
                flag = "AUDIO MISMATCH"
            elif tag in ("PLAYING","FAILED","CHECK PICTURE/AUDIO"):
                flag += " / " + tag
            elif tag.startswith("SAFE • LOCKED") and "LOCKED" not in flag:
                flag += " / LOCKED"
            role = ch.get("server_role") or "SERVER"
            short_role = _short_role(role)
            server = _friendly_server_name(role,ch.get("server_label") or ch.get("source") or "")
            # Preserve IPTV country prefixes (FR:/DE:/AR:) without name normalization.
            name = " ".join(str(ch.get("name") or "IPTV").split())
            if len(name)>39:name=name[:38]+"…"
            health = self._health_record(ch) or {}
            try:
                width = int(health.get("width") or ch.get("actual_width") or 0)
                height = int(health.get("height") or ch.get("actual_height") or 0)
            except (ValueError,TypeError):
                width=height=0
            if width>0 and height>0:
                resolution="REAL %dx%d"%(width,height)
            else:
                try: label=effective_quality_info(ch)[0] or "?"
                except Exception: label="?"
                resolution="DECLARED "+str(label).upper()[:6]
            if score is None:
                score_label="INDEX" if indexed else "--"
            else:
                score_label="%.1f"%score
            market=str(ch.get("market") or "-")
            language=str(ch.get("language") or "-")
            text="%d. [%s] %s %s • %s • %s/%s • %s • %s"%(n,short_role,
                 score_label,flag,name,market[:3],language[:3],resolution,server[:17])
            rows.append(self["source_list"].row(text[:120],state))
        if not rows:
            rows=[self["source_list"].row("NO MATCH • YELLOW: search all IPTV sources","NO_SOURCE")]
        try:self["source_list"].setList(rows)
        except Exception:
            try:self["source_list"].l.setList(rows)
            except Exception:pass
        if self.channels:
            idx=max(0,min(int(idx),len(self.channels)-1))
            try:self["source_list"].moveToIndex(idx)
            except Exception:pass
            self.selected_index=idx
'''

def replace_class_method(src, class_name, method_name, replacement):
    import ast
    tree=ast.parse(src)
    cls=next((x for x in tree.body if isinstance(x,ast.ClassDef) and x.name==class_name),None)
    if cls is None:raise AssertionError("R769 class missing: "+class_name)
    methods=[x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name==method_name]
    if len(methods)!=1:raise AssertionError("R769 method missing/duplicate: "+method_name)
    method=methods[0]
    lines=src.splitlines(keepends=True)
    return "".join(lines[:method.lineno-1])+replacement+"".join(lines[method.end_lineno:])

def once(src,old,new,label):
    n=src.count(old)
    if n!=1:
        raise AssertionError("R769 "+label+" anchor count "+str(n))
    return src.replace(old,new,1)
def patch_plugin(src):
    if TAG in src:
        return src
    src=once(src,"def _rank_sat_ref_all_servers(",HELPER+"def _rank_sat_ref_all_servers(","scoped SAT context helper")
    src=once(src,OLD_CONTEXT,NEW_CONTEXT,"Preview context")
    src=once(src,OLD_WORKER,NEW_WORKER,"Preview 48/16 worker")
    src=replace_class_method(src,"SatIPTVBridgePreview","_sort_candidates_with_cached_evidence",MANUAL_SORT_METHOD)
    src=replace_class_method(src,"SatIPTVBridgePreview","_render_source_list",MANUAL_RESULTS_METHOD)
    compile(src,"plugin.py","exec")
    return src
if __name__=="__main__":
    print("R769_PREVIEW_MANUAL_PARITY_READY")
