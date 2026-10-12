# -*- coding: utf-8 -*-
"""R73.2 true one-shot indexed candidate search. LIVE playback untouched."""

def one(source,old,new):
    count=source.count(old)
    if count!=1:
        raise AssertionError("R73.2 expected exactly one anchor, got %d: %s"%(count,repr(old[:110])))
    return source.replace(old,new,1)

def patch_core(src):
    method='''    def fast_preview_mega_matches(self, sat_name, language_priorities=None,
                                  context=None, per_server=64, topn=192,
                                  quality_mode="best"):
        """One pass: indexed candidates, bounded scoring, all rows ready together.

        The path does not alter automatic/live SmartMatch or user mappings.  It
        exposes unscored overflow rows as REVIEW/manual candidates, never as
        automatically validated matches.
        """
        import time as _clock
        t0 = _clock.monotonic()
        context = dict(context or {})
        roles_cap = max(1, int(per_server))
        limit = max(1, int(topn))
        key = self._fast_cache_key("mega-r732", sat_name, language_priorities,
                                   context, quality_mode, (roles_cap, limit))
        cached = self._fast_cache_get(key)
        if cached is not None:
            return cached[:limit]
        target = normalize_preview_name(sat_name or "")
        if not target:
            return []
        target_norm = normalize_name(sat_name or "")
        wanted_nums = tuple(_preview_numbers(sat_name or ""))
        wanted_tokens = set(target.split())
        wanted_fam = str(_effective_sat_provider_family(sat_name, context) or "")
        role_map = {}
        seen = set()
        max_nominees = 760
        checked = 0

        def candidate_key(ch):
            name = ch.get("name") or ""
            norm = str(ch.get("_preview_identity_norm") or normalize_preview_name(name))
            nums = tuple(ch.get("_preview_numbers") or _preview_numbers(name))
            # A genuine numbered channel is never equated with a different
            # number simply because the provider/family spelling is similar.
            if wanted_nums and nums and wanted_nums != nums:
                return None
            tokens = set(norm.split())
            overlap = len(wanted_tokens.intersection(tokens))
            exact = int(bool(norm and norm == target))
            compact = int(bool(norm and "".join(norm.split()) == "".join(target.split())))
            if not (exact or compact or overlap):
                return None
            ch_fam = str(ch.get("provider_family") or "")
            fam = int(bool(wanted_fam and ch_fam and wanted_fam.upper() == ch_fam.upper()))
            market = str(ch.get("market") or "").upper()
            prefs = [str(x).upper() for x in (context.get("market_preferences") or [])]
            market_rank = int(bool(market and market in prefs))
            lang = str(ch.get("language") or "").upper()
            lang_rank = int(bool(lang and lang in (language_priorities or [])))
            return (exact, compact, fam, overlap, market_rank, lang_rank,
                    -abs(len(tokens)-len(wanted_tokens)), -int(ch.get("server_priority") or 0))

        def add(ch):
            nonlocal checked
            if checked >= max_nominees or not isinstance(ch, dict):
                return
            ident = id(ch)
            if ident in seen:
                return
            seen.add(ident)
            checked += 1
            rank = candidate_key(ch)
            if rank is not None:
                role = str(ch.get("server_role") or "SERVER")
                role_map.setdefault(role, []).append((rank,ch))

        # All sources: exact normalized and decorated aliases first.
        for ch in self._exact.get(target_norm, ()):
            add(ch)
        try:
            for ch in self._ensure_preview_decorated_index().get(target, ()):
                add(ch)
        except Exception:
            pass
        # Only in-memory, pre-built inverted indexes. Avoid r71's expensive
        # provider-wide lexical normalization (notably huge beIN buckets).
        for ch in self._fast_candidate_pool(sat_name,per_server=roles_cap,
                                           total_cap=max(192, min(360,limit*2))):
            add(ch)
        anchors = [x for x in _identity_anchor_tokens(sat_name) if x in self._token_index]
        anchors.sort(key=lambda x:len(self._token_index.get(x, ())))
        for token in anchors[:3]:
            if checked >= max_nominees:
                break
            for ch in self._token_index.get(token, ())[:max(128, min(420,limit*2))]:
                add(ch)
                if checked >= max_nominees: break
        try:
            compact_idx, abbrev_idx, prefix_idx, number_idx = self._ensure_preview_coverage_indexes(allow_scan=False)
            for idx,key_name in ((compact_idx,_preview_compact_key(sat_name)),
                                 (abbrev_idx,_preview_abbreviation_key(sat_name))):
                if key_name:
                    for ch in idx.get(key_name, ())[:min(128,limit)]: add(ch)
            for pref in list(_preview_prefixes(sat_name))[:3]:
                for ch in prefix_idx.get(pref, ())[:min(120,limit)]: add(ch)
            for number in wanted_nums[:2]:
                for ch in number_idx.get(number, ())[:min(160,limit)]: add(ch)
        except Exception:
            pass
        try:
            famidx = self._ensure_preview_provider_index(allow_scan=False)
            if wanted_fam and len(role_map) < 2:
                for ch in famidx.get(wanted_fam, ())[:min(180,limit)]:
                    add(ch)
        except Exception:
            pass

        # Quotas are across IPTV SERVER ROLE, not provider-country guesses.
        # Sort candidates cheaply first; detailed fuzzy score is only computed
        # on the first 16 per role, at most 60 globally.
        all_ranked = []
        for role, values in role_map.items():
            values.sort(key=lambda x:x[0],reverse=True)
            all_ranked.extend((rank,role,ch) for rank,ch in values[:roles_cap])
        all_ranked.sort(key=lambda x:x[0], reverse=True)
        chosen = []
        counts = {}
        for rank,role,ch in all_ranked:
            if counts.get(role,0) >= roles_cap: continue
            counts[role] = counts.get(role,0)+1
            chosen.append((rank,role,ch))
            if len(chosen)>=limit: break
        roles = list(dict.fromkeys(role for _rank,role,_ch in chosen))
        score_ids = set()
        by_role={}
        for _rank,role,ch in chosen:
            by_role.setdefault(role,[]).append(ch)
        # 60 detailed scores total; make sure the best of every server gets
        # a chance to qualify SAFE instead of blindly scoring PRIMARY only.
        budget=60
        for i in range(20):
            for role in roles:
                options=by_role.get(role, ())
                if i<len(options) and len(score_ids)<budget:
                    score_ids.add(id(options[i]))
        output=[]
        for _rank,role,ch in chosen:
            if id(ch) in score_ids:
                enriched = _enrich_channel(ch)
                score, details = match_score_details(
                    sat_name,enriched,language_priorities,context,quality_mode,preview=True)
                output.append((enriched,score,details))
            else:
                # No scored SAFE or auto-map claim from index-only guesses.
                info = dict(ch)
                info["_r732_index_only"] = True
                output.append((info,0.0,{"name":0.0,"manual":True,
                    "review_reason":"INDEX ONLY: press OK to verify actual picture and audio"}))
        self._fast_cache_put(key,output)
        return output

'''
    return one(src,'    def fast_rank_matches_all_servers(self, sat_name, language_priorities=None, context=None, per_server=12, topn=48, quality_mode="best"):',method+'    def fast_rank_matches_all_servers(self, sat_name, language_priorities=None, context=None, per_server=12, topn=48, quality_mode="best"):')

def patch_plugin(src):
    # The only Preview ranking pass returns 192 catalogued results at once.
    # No instant/expanded/re-expanded panels or Enigma2 work in worker thread.
    src=one(src,'        self._r731_search_active = False\n        self._r731_search_result = None\n        self._r731_search_worker = None\n        self._r731_search_timer = eTimer()',
        '        self._r731_search_active = False\n        self._r732_auto_rows = []\n        self._r732_auto_page = 0\n        self._r731_search_result = None\n        self._r731_search_worker = None\n        self._r731_search_timer = eTimer()')
    src=one(src,'        try: self.sat_change_timer.start(110, True)\n        except Exception: self._load_selected_sat_candidates()',
        '''        # No first-paint 10-candidate pass; one indexed 192-candidate job.
        try: self.candidate_expand_timer.start(20, True)
        except Exception: self._expand_selected_sat_candidates()''')
    src=one(src,'        candidate_budget = 144 if self._r71_worker_deep else self.MAX_BROWSER_CANDIDATES\n        candidate_per_server = 42 if self._r71_worker_deep else self.FAST_PER_SERVER',
        '''        candidate_budget = 192
        candidate_per_server = 64''')
    src=one(src,'''                ranked = catalog.fast_rank_matches_all_servers(
                    sat_name, priorities, context=dict(ctx),
                    per_server=candidate_per_server, topn=candidate_budget,
                    quality_mode=quality_mode)''',
        '''                ranked = catalog.fast_preview_mega_matches(
                    sat_name, priorities, context=dict(ctx),
                    per_server=candidate_per_server, topn=candidate_budget,
                    quality_mode=quality_mode)''')
    src=one(src,'channels = self._sort_candidates_with_cached_evidence(channels, context=ctx)[:(144 if self._r71_worker_deep else self.MAX_BROWSER_CANDIDATES)]',
        'channels = self._sort_candidates_with_cached_evidence(channels, context=ctx)[:192]')
    src=one(src,'        self.channels = [dict(x or {}) for x in rec[2]]\n        if old_fp:',
        '''        self._r732_auto_rows = [dict(x or {}) for x in rec[2]]
        self._r732_auto_page = 0
        self.channels = [dict(x) for x in self._r732_auto_rows[:48]]
        if old_fp:''')
    # Same behaviour on shared-cache hit.
    src=one(src,'        self.channels = [dict(x or {}) for x in list(cached[2] or [])]\n        try: complete = bool(cached[3])',
        '''        self._r732_auto_rows = [dict(x or {}) for x in list(cached[2] or [])]
        self._r732_auto_page = 0
        self.channels = [dict(x) for x in self._r732_auto_rows[:48]]
        try: complete = bool(cached[3])''')
    # Avoid re-searching when 192 results were just computed.
    src=one(src,'        if not complete:\n            try: self.candidate_expand_timer.start(190 if not self.channels else 520, True)',
        '        if not complete and not self._r732_auto_rows:\n            try: self.candidate_expand_timer.start(20, True)')
    src=one(src,'        if self._r731_search_active:\n            return self._r731_page_search(step)\n        if not self.channels:',
        '''        if self._r731_search_active:
            return self._r731_page_search(step)
        if len(self._r732_auto_rows)>48:
            return self._r732_page_auto(step)
        if not self.channels:''')
    # No expensive rescoring on YELLOW; 5 still gives full-catalogue search.
    src=one(src,'        self._r71_deep_requested = True\n        self._r71_deep_target_ref = raw',
        '''        if self._r732_auto_rows:
            self["status"].setText("ALL INDEXED CANDIDATES READY: %d • CH+/- page • 5 full search" % len(self._r732_auto_rows))
            self._set_focus("right")
            return
        self._r71_deep_requested = True
        self._r71_deep_target_ref = raw''')
    # Do not leave previous SAT candidates on screen while a new job is pending.
    src=one(src,'        self.channels = []\n        self.selected_index = 0\n        self._user_rejected_ids = set()',
        '''        self.channels = []
        self._r732_auto_rows = []
        self._r732_auto_page = 0
        self.selected_index = 0
        self._user_rejected_ids = set()''')
    src=one(src,'        self["status"].setText("FAST MATCH • exact/index candidates")',
        '        self["status"].setText("MEGA SEARCH • calculating candidates once • no progressive load")')
    # For a background worker from previous SAT, immediately schedule the new
    # selection as soon as its obsolete result finishes, not after a 680ms wait.
    src=one(src,'            try: self.candidate_expand_timer.start(680, True)',
        '            try: self.candidate_expand_timer.start(20, True)')
    # Slot is a class method, page the already computed result only.
    helper='''    def _r732_page_auto(self, direction):
        if not self._r732_auto_rows:
            return
        total = len(self._r732_auto_rows)
        pagecount = (total+47)//48
        self._r732_auto_page = max(0, min(pagecount-1, self._r732_auto_page+(1 if direction>0 else -1)))
        start = self._r732_auto_page*48
        self.channels = [dict(ch) for ch in self._r732_auto_rows[start:start+48]]
        self.selected_index = 0
        self._render_source_list(keep_index=False)
        self._set_focus("right")
        self["status"].setText("ALL CANDIDATES READY • %d total • page %d/%d • CH+/-" %
                                (total,self._r732_auto_page+1,pagecount))

'''
    src=one(src,'    def _r731_page_search(self, direction):',helper+'    def _r731_page_search(self, direction):')
    # Header shows total even though only one page is rendered at a time.
    src=one(src,'"CANDIDATES • %d • P+B1+B2 • 5 SEARCH" % len(self.channels)',
            '"CANDIDATES • %d TOTAL • 48/PAGE • P+B1+B2" % max(len(self.channels),len(self._r732_auto_rows))')
    # Preserve score rank for actual verified entries and reflect one-shot results.
    src=one(src,'        self["status"].setText("%d candidates • ALL SERVERS%s • READY • YELLOW = MORE" %',
            '        self["status"].setText("%d INDEXED CANDIDATES • ALL AT ONCE%s • READY • CH+/- PAGES" %')
    return src
