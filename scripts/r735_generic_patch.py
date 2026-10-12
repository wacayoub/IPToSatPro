# -*- coding: utf-8 -*-
"""R73.5 generic TV match safety and Preview rank selection.

No hardcoded channel-name exceptions. Existing manually confirmed mappings
must remain untouched; AUTO suggestions can be reranked and corrected.
"""
def one(src, old, new):
    n=src.count(old)
    if n!=1:
        raise AssertionError("R73.5 anchor expected once, got %d: %s"%(n,repr(old[:110])))
    return src.replace(old,new,1)

def patch_core(src):
    helper='''def _r735_numbered_live_subservice(name):
    """LIVE before a numbered service is a real service identity variant.

    Examples: V Sport LIVE 1 != V Sport 1; LIVE: V Sport 1 is just a
    transmission label, not a different channel. Never use this to infer
    that a candidate is verified from a high numerical score.
    """
    import re
    label=str(name or "")
    label=re.sub(r"(?i)^\\s*(?:[A-Z]{2}\\s*:\\s*)?LIVE\\s*[:\\-]\\s*","",label)
    return bool(re.search(r"(?i)(?:^|[^a-z0-9])live\\s*[-_]?\\s*\\d{1,3}(?!\\d)",label))

'''
    src=one(src,'def match_score_details(sat_name, channel, priorities=None, context=None, quality_mode="best", preview=False):',
        helper+'def match_score_details(sat_name, channel, priorities=None, context=None, quality_mode="best", preview=False):')
    src=one(src,'''    details["name"] = base

    if preview:''',
'''    details["name"] = base

    # Generic service variant gate. LIVE 1 and 1 are not interchangeable
    # even when a fuzzy identity score is 90+. REVIEW in human Preview,
    # REJECT for unattended matcher/AutoScan; explicit equivalence rules
    # remain the only permitted exception. A leading "LIVE:" is decorative.
    if not equivalence and _r735_numbered_live_subservice(sat_name) != _r735_numbered_live_subservice(ch.get("name", "")):
        details["variant"] = -42.0
        if preview:
            details["review_reason"] = "numbered LIVE service variant differs; check channel identity manually"
        else:
            details["reject_reason"] = "numbered LIVE service variant mismatch"

    if preview:''')
    return src

def patch_plugin(src):
    # The previous code mistakenly treats *every* mapping (including an
    # unattended AUTO BEST lock) as a user-verified MANUAL lock.
    src=one(src,
'''        if isinstance(manual, dict) and str(manual.get("channel_id") or "") == fp:
            return "MANUAL"''',
'''        if (isinstance(manual, dict) and str(manual.get("channel_id") or "") == fp
                and not bool(manual.get("auto_best_lock"))):
            return "MANUAL"''')

    # Reevaluate the old AUTO source with the CURRENT matching rules.
    # It stays discoverable without being promoted ahead of a safe exact
    # match just because it was the stale automatic lock.
    src=one(src,
'''    def _merge_locked_candidate(self, key, channels):
        channels = [dict(x or {}) for x in list(channels or [])]''',
'''    def _merge_locked_candidate(self, key, channels, sat_name=None, context=None):
        channels = [dict(x or {}) for x in list(channels or [])]''')
    src=one(src,
'''                item = dict(locked)
                item["_preview_score"] = float((manual or {}).get("auto_scan_score") or 0.0)
                item["_preview_details"] = {
                  "allow_reason": "auto scan lock" if (manual or {}).get("auto_best_lock") else "manual lock",
                  "manual": not bool((manual or {}).get("auto_best_lock")),
                  "auto_best_lock": bool((manual or {}).get("auto_best_lock")),
                }
                channels.insert(0, item)''',
'''                item = dict(locked)
                is_auto = bool((manual or {}).get("auto_best_lock"))
                item["_r735_verified_manual_lock"] = not is_auto
                item["_r735_old_auto_lock"] = is_auto
                if is_auto:
                    # The original AUTO score may be stale or based on a
                    # wrong variant. Treat it like other new nominations.
                    try:
                        languages=[x.strip().upper() for x in cfg.languages.value.split(",") if x.strip()]
                        score,details = match_score_details(sat_name or self.sat_name,
                            item,languages,dict(context or {}),cfg.quality_mode.value,preview=True)
                        item["_preview_score"] = float(score)
                        item["_preview_details"] = dict(details or {})
                    except Exception:
                        item["_preview_score"] = 0.0
                        item["_preview_details"] = {"review_reason":"old AUTO lock requires re-verification"}
                else:
                    item["_preview_score"] = float((manual or {}).get("auto_scan_score") or 0.0)
                    item["_preview_details"] = {"manual":True}
                channels.insert(0, item)''')
    src=one(src,
'''        channels = self._merge_locked_candidate(key, channels)
        channels = self._sort_candidates_with_cached_evidence(channels, context=ctx)[:192]''',
'''        channels = self._merge_locked_candidate(key, channels, sat_name, ctx)
        channels = self._sort_candidates_with_cached_evidence(channels, context=ctx)[:192]''')

    # Rank usable exact service identities BEFORE visually similar subservices.
    # The existing R73.3 indexed nomination remains the speed-critical phase.
    src=one(src,
'''        rows = [dict(x or {}) for x in list(channels or []) if isinstance(x, dict)]
        return rows''',
'''        rows = [dict(x or {}) for x in list(channels or []) if isinstance(x, dict)]
        import re
        def core_identity(label):
            val=re.sub(r"(?i)^\\s*(?:[a-z]{2,3}\\s*:\\s*)?LIVE\\s*[:\\-]\\s*", "",str(label or ""))
            val=re.sub(r"(?i)^\\s*[a-z]{2,3}\\s*:\\s*","",val)
            tokens=re.findall(r"[a-z0-9]+",val.lower())
            tech={"sd","hd","fhd","uhd","4k","8k","hevc","h264","h265",
                  "1080p","1080i","720p","2160p","3840p","mpeg4"}
            return tuple(t for t in tokens if t not in tech)
        target=core_identity(self.sat_name)
        target_compact="".join(target)
        def key(ch):
            if ch.get("_r735_verified_manual_lock"):
                return (5,1,1000.0,1,1000.0,1,1,0)
            decision=self._candidate_decision(ch)
            d_band={"MANUAL":5,"SAFE":4,"ALLOWED":3,"REVIEW":2,
                    "SOURCE":1,"REJECT":0,"USER REJECT":-1}.get(decision,0)
            parts=core_identity(ch.get("name") or "")
            # Exact service + source number beats LIVE/Event/child variants.
            exact=int(bool(target and (parts==target or "".join(parts)==target_compact)))
            details=ch.get("_preview_details") if isinstance(ch.get("_preview_details"),dict) else {}
            try: identity=float(details.get("name") or 0)+float(details.get("equivalence") or 0)+float(details.get("variant") or 0)
            except Exception: identity=0.0
            try: score=float(ch.get("_preview_score") or 0.0)
            except Exception: score=0.0
            provider=int(bool(details.get("provider_identity")))
            health=self._health_record(ch)
            w=int(health.get("width") or ch.get("actual_width") or 0)
            h=int(health.get("height") or ch.get("actual_height") or 0)
            measured=int(w>0 and h>0)
            # Measured resolution breaks ties; it cannot redeem a wrong
            # channel identity, rejected stream, or mismatched country.
            return (d_band,exact,identity,provider,score,measured,w*h,
                    -int(ch.get("server_priority") or 0))
        rows.sort(key=key,reverse=True)
        return rows''')

    # Full list is ready, but R73.4's async callback did not refresh right_head;
    # it consequently displayed 0 TOTAL while actual rows were visible.
    src=one(src,
'''        self._render_source_list(keep_index=True)
        self._update_header()
        # Candidate list is fully available before''',
'''        self._render_source_list(keep_index=True)
        self._update_header()
        self._set_focus(self.focus)
        # Candidate list is fully available before''')

    # Unattended AUTO SCAN MUST NOT choose REVIEW/REJECT even with a 90
    # fuzzy-name score; user can manually preview either when uncertain.
    src=one(src,
'''            if decision in ("REVIEW", "ALLOWED"):
                had_review = True
            # r49 user policy: identity comes first, not SAFE/REVIEW bookkeeping.''',
'''            if decision in ("REVIEW", "REJECT"):
                had_review = True
            if decision not in ("SAFE", "ALLOWED"):
                continue
            # Identity comes first WITHIN safety-approved candidates.''')
    src=one(src,
'''        r49 follows the user policy: every SAT channel with at least one IPTV nominee gets an
        AUTO BEST lock.  Engine SAFE/ALLOWED/REVIEW/REJECT remains useful as confidence
        metadata, but no longer prevents a best-effort lock.  Explicit per-channel USER REJECT
        rows are the only automatic exclusions, and existing manual locks remain protected by
        _scan_one/_commit_auto_scan_overrides.''',
'''        Never auto-lock a REVIEW/REJECT candidate regardless of its fuzzy
        name score. Existing manual locks and explicit per-channel rejects are
        protected. SAFE/ALLOWED candidates rank by genuine service identity
        and quality evidence only after the safety gate.''')
    # For a saved AUTO lock that is incorrect, leave it visible as existing
    # mapping until user explicitly confirms another candidate with GREEN.
    return src
