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
    compile(src,"plugin.py","exec")
    return src
if __name__=="__main__":
    print("R769_PREVIEW_MANUAL_PARITY_READY")
