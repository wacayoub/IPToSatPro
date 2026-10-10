"""Preview Browser UI-only r70 upgrade, pinned to the exact r69 plugin source.

No changes to player, manual lock, SAT tune, timeshift, picons, or core ranking.
Every edit is an exact, single-match assertion to prevent unsafe patch drift.
"""

def improve(source):
    if "# R70_PREVIEW_AUDITED_UPGRADE" in source:
        raise AssertionError("r70 preview already upgraded")
    def once(old, new):
        nonlocal source
        count = source.count(old)
        if count != 1:
            raise AssertionError("Preview patch anchor mismatch (%d): %s" % (count, old[:100]))
        source = source.replace(old, new, 1)

    # Preserve an already-complete candidate cache.  Opening preview with a
    # 10/36-row seed previously downgraded shared COMPLETE -> INCOMPLETE, forcing
    # the 5-8s full ranking on EVERY reopen.
    once(
        '''    items = _PREVIEW_CANDIDATE_GLOBAL_CACHE.setdefault("items", {})
    order = _PREVIEW_CANDIDATE_GLOBAL_CACHE.setdefault("order", [])
    items[key] = (clean_display_name(sat_name or ""), dict(context or {}), [dict(x or {}) for x in list(channels or [])], bool(complete))''',
        '''    items = _PREVIEW_CANDIDATE_GLOBAL_CACHE.setdefault("items", {})
    order = _PREVIEW_CANDIDATE_GLOBAL_CACHE.setdefault("order", [])
    existing = items.get(key)
    if existing is not None and bool(existing[3]) and not complete:
        # A partial seed must never erase an already-complete matching result.
        # The catalogue token was checked above; no stale provider change.
        return
    items[key] = (clean_display_name(sat_name or ""), dict(context or {}), [dict(x or {}) for x in list(channels or [])], bool(complete))'''
    )
    once(
        '''            incoming_complete = False
            self._candidate_cache[key] = (self.sat_name, dict(self.context), incoming, incoming_complete)
            _preview_candidate_cache_put(self.input_sat_ref, self.sat_name, self.context, incoming, complete=incoming_complete)
            self._source_pos_by_sat[key] = incoming_selected''',
        '''            incoming_complete = False
            shared = _preview_candidate_cache_get(self.input_sat_ref)
            requested_fp = channel_fingerprint(incoming[incoming_selected]) if incoming else ""
            if shared is not None and bool(shared[3]):
                full = [dict(x or {}) for x in shared[2]]
                matching = next((pos for pos, ch in enumerate(full)
                                 if channel_fingerprint(ch) == requested_fp), None)
                if matching is not None:
                    self._candidate_cache[key] = (
                        shared[0], dict(shared[1] or {}), full, True)
                    self._source_pos_by_sat[key] = matching
                else:
                    self._candidate_cache[key] = (
                        self.sat_name, dict(self.context), incoming, False)
                    self._source_pos_by_sat[key] = incoming_selected
            else:
                self._candidate_cache[key] = (
                    self.sat_name, dict(self.context), incoming, False)
                self._source_pos_by_sat[key] = incoming_selected
            _preview_candidate_cache_put(
                self.input_sat_ref, self.sat_name, self.context,
                incoming, complete=incoming_complete)'''
    )

    # Stop repainting up to 36 large strings/labels every 300ms while retaining
    # 300ms live decoder/status samples.  Final sample always repaints.
    once(
        '''        if self.sat_ref_string == self.active_sat_ref:
            self._render_source_list(keep_index=True)
        self._update_verify_strip()
        if not final:''',
        '''        if self.sat_ref_string == self.active_sat_ref:
            last_paint = float(getattr(self, "_r70_last_quality_paint", 0) or 0)
            if final or time.monotonic() - last_paint >= 1.0:
                self._r70_last_quality_paint = time.monotonic()
                self._render_source_list(keep_index=True)
        self._update_verify_strip()
        if not final:'''
    )

    # Fast handover from expired worker: avoid a second 680ms dead time after
    # each stale SAT selection.  Existing single-worker invariant retained.
    once(
        '''            try: self.candidate_expand_timer.start(680, True)
            except Exception: pass
            return''',
        '''            try: self.candidate_expand_timer.start(230, True)
            except Exception: pass
            return'''
    )

    # Preserve candidate fingerprint after background reorder; old keep_index=True
    # selected an unrelated row at the old screen index.
    once(
        '''        self._render_source_list(keep_index=True)
        self._update_header()
        self["status"].setText("%d BEST candidates • BG READY • P/B1/B2 • YELLOW = ALL SOURCES" % len(self.channels))''',
        '''        self._render_source_list(keep_index=False)
        self._update_header()
        self["status"].setText("%d BEST candidates • BG READY • P/B1/B2 • YELLOW = ALL SOURCES" % len(self.channels))'''
    )

    # Maintain readable two-column FHD layout while showing more rows.
    once(
        '''        self["title"] = Label("PREVIEW BROWSER PRO • IMAGE • DOLBY • OPEN SPEED")''',
        '''        self["title"] = Label("PREVIEW BROWSER PRO • SAT ↔ IPTV • QUALITÉ RÉELLE")'''
    )
    once(
        '''        self["sat_list"] = PreviewBrowserList([], width=488, item_height=42, font_size=19)
        self["source_list"] = PreviewBrowserList([], width=1066, item_height=42, font_size=18)''',
        '''        self["sat_list"] = PreviewBrowserList([], width=488, item_height=39, font_size=18)
        self["source_list"] = PreviewBrowserList([], width=1066, item_height=39, font_size=18)'''
    )
    once(
        '''            self.l.setFont(0, gFont("Regular", 22))
            self.l.setItemHeight(52)''',
        '''            self.l.setFont(0, gFont("Regular", 20))
            self.l.setItemHeight(46)'''
    )

    # All Sources loads only instant rank synchronously; full rank will
    # follow on the pre-existing deferred timer handled by r70 async adapter.
    once(
        '''    sat_name2, sat_ref, ctx, ranked = _rank_sat_ref_all_servers(sat_ref_string, topn=48, per_server=16)
    if sat_name:''',
        '''    sat_name2, sat_ref, ctx, ranked = _rank_sat_ref_instant(sat_ref_string, topn=10, per_server=3)
    if sat_name:'''
    )
    once(
        '''            sat_name2, sat_ref, ctx, ranked=_rank_sat_ref_all_servers(raw, topn=self.MAX_VISIBLE_CANDIDATES, per_server=16)
            if requested_name:''',
        '''            sat_name2, sat_ref, ctx, ranked=_rank_sat_ref_instant(raw, topn=10, per_server=3)
            if requested_name:'''
    )
    once(
        '''            self._render()
        except Exception as err:
            try:self["detail"].setText("ALL SOURCES unavailable • %s"%str(err)[:180])''',
        '''            self._render()
            # Deferred full ranking, never block modal transition.
            try: self._load_timer.start(80, True)
            except Exception: pass
        except Exception as err:
            try:self["detail"].setText("ALL SOURCES unavailable • %s"%str(err)[:180])'''
    )

    # All Sources / bouquet previously rendered many thousands of rows at once.
    # Windowed pages keep entire ranked set available with 8 and 9 shortcuts.
    once(
        '''        self._shown_fps = []
        self._initial_selection = True
        self._zap_from_ref=self.sat_ref_string; self._zap_refresh_tries=0''',
        '''        self._shown_fps = []
        self._initial_selection = True
        self._r70_page_offset = 0
        self._r70_page_target = None
        self._r70_ranked_identity = None
        self._zap_from_ref=self.sat_ref_string; self._zap_refresh_tries=0'''
    )
    once(
        '''"0":self.choose_filters,"menu":self.toggle_source_status,"chplus":self.zap_next_channel''',
        '''"0":self.choose_filters,"8":self._r70_prev_page,"9":self._r70_next_page,"menu":self.toggle_source_status,"chplus":self.zap_next_channel'''
    )
    once(
        '''    def _render(self):
        # Restore by IPTV fingerprint, never by a stale index from a re-ranked list.''',
        '''    def _r70_prev_page(self):
        if not (self.browse_mode or self.search_query):
            return
        if self._r70_page_offset <= 0:
            return
        self._r70_page_offset = max(0, self._r70_page_offset - 48)
        self._r70_page_target = 0
        self._pending_selected_fp = ""
        self._shown_fps = []
        self._render()

    def _r70_next_page(self):
        if not (self.browse_mode or self.search_query):
            return
        if self._r70_page_offset + 48 >= len(self.ranked or []):
            return
        self._r70_page_offset += 48
        self._r70_page_target = 0
        self._pending_selected_fp = ""
        self._shown_fps = []
        self._render()

    def _render(self):
        # Reset a prior bouquet page after switching to a new search, SAT or source.
        if self._r70_ranked_identity is not None and id(self.ranked) != self._r70_ranked_identity:
            self._r70_page_offset = 0
        # Restore by IPTV fingerprint, never by a stale index from a re-ranked list.'''
    )
    once(
        '''        rendered=[]
        shown_fps=[]
        best_marked=False
        display_rows = self.ranked if (self.browse_mode or self.search_query) else self.ranked[:self.MAX_VISIBLE_CANDIDATES]
        for idx,(ch,score,details) in enumerate(display_rows,1):''',
        '''        self._r70_ranked_identity = id(self.ranked)
        rendered=[]
        shown_fps=[]
        best_marked=False
        paged = bool(self.browse_mode or self.search_query)
        limit = 48 if paged else self.MAX_VISIBLE_CANDIDATES
        if paged:
            self._r70_page_offset = max(
                0, min(int(getattr(self, "_r70_page_offset", 0) or 0),
                       (max(0, len(self.ranked) - 1) // limit) * limit))
        else:
            self._r70_page_offset = 0
        offset = self._r70_page_offset
        display_rows = self.ranked[offset:offset+limit]
        for idx,(ch,score,details) in enumerate(display_rows,offset+1):'''
    )
    once(
        '''        try:
            self["list"].setList(rendered)
        except Exception:
            try: self["list"].rows = rendered''',
        '''        if getattr(self, "_r70_page_target", None) is not None:
            target = min(int(self._r70_page_target), max(0, len(shown_fps) - 1))
            self._r70_page_target = None
        try:
            self["list"].setList(rendered)
        except Exception:
            try: self["list"].rows = rendered'''
    )
    once(
        '''        for row in self.ranked:
            d=self._display_decision(row)
            if d == "USER REJECT": d="REJECT"
            if d not in counts: d="REJECT"
            counts[d]+=1
        if self.browse_mode:
            count_text="%d CHANNELS • %s"%(len(self.ranked), scope)''',
        '''        if not self.browse_mode:
            for row in self.ranked:
                d=self._display_decision(row)
                if d == "USER REJECT": d="REJECT"
                if d not in counts: d="REJECT"
                counts[d]+=1
        if self.browse_mode:
            count_text="%d CHANNELS • %s"%(len(self.ranked), scope)
            count_text += " • %d-%d/%d • 8/9 PAGE" % (
                offset + 1 if self.ranked else 0,
                min(offset + limit, len(self.ranked)), len(self.ranked))'''
    )
    once(
        '''        idx=max(0,min(self._index(),len(self.ranked)-1))
        return self.ranked[idx]''',
        '''        idx=max(0,min(self._index()+int(getattr(self,"_r70_page_offset",0)),len(self.ranked)-1))
        return self.ranked[idx]'''
    )
    once(
        '''        idx = max(0, self._index())
        radius = 8''',
        '''        idx = max(0, self._index() + int(getattr(self, "_r70_page_offset", 0)))
        radius = 8'''
    )
    once(
        '''        if self.browse_mode and len(self.ranked or []) > 260:
            try:
                suffix = (" • " + message) if message else ""
                self["detail"].setText((getattr(self, "_mode_text", "SOURCE BOUQUET BROWSE") + suffix)[:260])
            except Exception:
                pass
            return
        self._render()''',
        '''        # Bounded r70 page draw makes even huge bouquet selection cheap;
        # always refresh the highlighted row after a manual lock/reject.
        self._render()'''
    )

    return source + "\n# R70_PREVIEW_AUDITED_UPGRADE: cache, deferred rank, pages, quality redraw\n"
