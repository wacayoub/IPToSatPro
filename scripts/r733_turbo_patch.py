# -*- coding: utf-8 -*-
"""R73.3 Preview-only CPU optimizations and actual receiver latency breakdown.

Preserves:
- full one-pass indexed 192-result search with all provider roles;
- safety score on top per-role entries, REVIEW for unscored candidates;
- original live player, monitor, audio, EPG, FTA, mappings, timeshift.
"""

def one(src, before, after):
    count = src.count(before)
    if count != 1:
        raise AssertionError("R73.3 patch anchor drift %d: %s" % (count, repr(before[:90])))
    return src.replace(before,after,1)

def patch_core(src):
    src=one(src,
'''        cached = self._fast_cache_get(key)
        if cached is not None:
            return cached[:limit]
        target = normalize_preview_name(sat_name or "")''',
'''        cached = self._fast_cache_get(key)
        if cached is not None:
            self._r733_last_profile = {"cache":1, "index_ms":0,
                "score_ms":0, "total_ms":0, "scored":0, "candidate_count":len(cached)}
            return cached[:limit]
        target = normalize_preview_name(sat_name or "")''')
    src=one(src,
'''        role_map = {}
        seen = set()
        max_nominees''',
'''        role_map = {}
        seen = set()
        # Cache normalized metadata by title, not by URL. Large playlists
        # repeat the same names across many source URLs and server roles.
        title_cache = {}
        market_prefs = set(str(x).upper() for x in (context.get("market_preferences") or []))
        lang_prefs = set(str(x).upper() for x in (language_priorities or []))
        target_compact = "".join(target.split())
        max_nominees''')
    src=one(src,
'''            norm = str(ch.get("_preview_identity_norm") or normalize_preview_name(name))
            nums = tuple(ch.get("_preview_numbers") or _preview_numbers(name))
            # A genuine numbered channel''',
'''            cached_title = title_cache.get(name)
            if cached_title is None:
                nrm = str(ch.get("_preview_identity_norm") or normalize_preview_name(name))
                numbers = tuple(ch.get("_preview_numbers") or _preview_numbers(name))
                tok = set(nrm.split())
                brand = str(_iptv_provider_family(name or "") or "").upper()
                cached_title = (nrm, numbers, tok, brand, "".join(nrm.split()))
                title_cache[name] = cached_title
            norm, nums, tokens, candidate_brand, compact_name = cached_title
            # A genuine numbered channel''')
    src=one(src,
'''            tokens = set(norm.split())
            candidate_brands = tokens.intersection(distinctive_brands)''',
'''            candidate_brands = tokens.intersection(distinctive_brands)''')
    src=one(src,
'''            compact = int(bool(norm and "".join(norm.split()) == "".join(target.split())))''',
'''            compact = int(bool(norm and compact_name == target_compact))''')
    src=one(src,
'''            candidate_brand = str(_iptv_provider_family(name or "") or "").upper()
            if wanted_brand and candidate_brand and wanted_brand != candidate_brand:''',
'''            if wanted_brand and candidate_brand and wanted_brand != candidate_brand:''')
    src=one(src,
'''            prefs = [str(x).upper() for x in (context.get("market_preferences") or [])]
            market_rank = int(bool(market and market in prefs))
            lang = str(ch.get("language") or "").upper()
            lang_rank = int(bool(lang and lang in (language_priorities or [])))''',
'''            market_rank = int(bool(market and market in market_prefs))
            lang = str(ch.get("language") or "").upper()
            lang_rank = int(bool(lang and lang in lang_prefs))''')
    src=one(src,
'''        roles = ordered_roles
        score_ids = set()''',
'''        roles = ordered_roles
        index_ready = _clock.monotonic()
        score_ids = set()''')
    src=one(src,
'''        # 60 detailed scores total; make sure the best of every server gets
        # a chance to qualify SAFE instead of blindly scoring PRIMARY only.
        budget=60
        for i in range(20):''',
'''        # Scores are CPU intensive on the Vu+ Zero 4K. Score a SMALL fixed
        # top subset, allocated fairly across P/B1/B2. All other plausible
        # results remain visible and explicitly require manual preview.
        budget=18
        for i in range(18):''')
    src=one(src,
'''                info["_r732_index_only"] = True
                output.append((info,0.0,{"name":0.0,"manual":True,
                    "review_reason":"INDEX ONLY: press OK to verify actual picture and audio"}))
        self._fast_cache_put(key,output)
        return output''',
'''                info["_r732_index_only"] = True
                # Never mark an unscored candidate SAFE/ALLOWED.  The Preview
                # UI treats _manual_candidate as REVIEW until OK video/audio.
                info["_manual_candidate"] = True
                output.append((info,0.0,{"name":0.0,
                    "review_reason":"INDEX ONLY: press OK to verify actual picture and audio"}))
        finish = _clock.monotonic()
        self._r733_last_profile = {
            "cache":0,
            "index_ms":round((index_ready-t0)*1000),
            "score_ms":round((finish-index_ready)*1000),
            "total_ms":round((finish-t0)*1000),
            "scored":len(score_ids), "candidate_count":len(output)}
        self._fast_cache_put(key,output)
        return output''')
    return src

def patch_plugin(src):
    src=one(src,
'''                    per_server=candidate_per_server, topn=candidate_budget,
                    quality_mode=quality_mode)
                value = (raw, sat_name, ctx, ranked, "")''',
'''                    per_server=candidate_per_server, topn=candidate_budget,
                    quality_mode=quality_mode)
                perf_ctx = dict(ctx)
                perf_ctx["_r733_perf"] = dict(getattr(catalog,"_r733_last_profile",{}) or {})
                value = (raw, sat_name, perf_ctx, ranked, "")''')
    src=one(src,
'''        _startup_log("PREVIEW_RANK_BG", "candidate_count=%d elapsed=%dms error=%s" % (len(ranked), elapsed, error[:50]))
        if selected_raw != raw:''',
'''        perf = dict((ctx or {}).get("_r733_perf") or {})
        _startup_log("PREVIEW_RANK_BG",
            "candidate_count=%d elapsed=%dms index=%dms scoring=%dms scored=%d cache=%d error=%s" %
            (len(ranked), elapsed, int(perf.get("index_ms") or 0),
             int(perf.get("score_ms") or 0),int(perf.get("scored") or 0),
             int(perf.get("cache") or 0),error[:50]))
        if selected_raw != raw:''')
    return src
