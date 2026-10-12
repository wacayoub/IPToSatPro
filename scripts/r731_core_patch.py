# -*- coding: utf-8 -*-
"""R73.1 targeted Preview improvements. Applied to exact pinned packaged sources.

The automatic live fallback matcher, stream player, audio engine and timeshift
are NOT modified. Explicit user search is local and opt-in.
"""

def replace_once(source, old, new):
    count=source.count(old)
    if count != 1:
        raise AssertionError("R73.1 patch anchor drift count=%s: %s" % (count,repr(old[:100])))
    return source.replace(old,new,1)


def patch_core_r731(src):
    # Never convert an unverified country guess into a definitive wrong channel.
    # Preview only: leave the user a human-verifiable REVIEW candidate; live
    # SmartMatch hard safety rules remain as before.
    src=replace_once(src, '''                else:
                    details["context"] = -58.0
                    details["reject_reason"] = "IPTV feed market %s is secondary to strong SAT market %s" % (cand_market, desired_markets[0])''',
    '''                else:
                    if preview and sat_norm == ip_norm and not explicit_feed_lang:
                        details["context"] = -14.0
                        details["review_reason"] = "Preview: exact identity; secondary IPTV country hint %s requires manual verification" % cand_market
                    else:
                        details["context"] = -58.0
                        details["reject_reason"] = "IPTV feed market %s is secondary to strong SAT market %s" % (cand_market, desired_markets[0])''')
    src=replace_once(src, '''                else:
                    details["context"] = -64.0
                    details["market"] = -12.0
                    details["reject_reason"] = "IPTV feed market %s conflicts with strong SAT market %s" % (cand_market, desired_markets[0])''',
    '''                else:
                    if preview and sat_norm == ip_norm and not explicit_feed_lang:
                        details["context"] = -14.0
                        details["market"] = -8.0
                        details["review_reason"] = "Preview: exact identity; conflicting IPTV country hint %s needs video/audio test" % cand_market
                    else:
                        details["context"] = -64.0
                        details["market"] = -12.0
                        details["reject_reason"] = "IPTV feed market %s conflicts with strong SAT market %s" % (cand_market, desired_markets[0])''')
    return src


def patch_plugin_r731(src):
    # Opt-in FTA browsing and search are local to Preview; no global FTA fence changes.
    src=replace_once(src,'        self._r71_deep_requested = False\n        self._r71_worker_deep = False',
    '''        self._r71_deep_requested = False
        self._r71_worker_deep = False
        self._r731_show_fta = False
        self._r731_search_rows = []
        self._r731_search_page = 0
        self._r731_search_query = ""
        self._r731_search_ref = ""
        self._r731_search_active = False
        self._r731_search_result = None
        self._r731_search_worker = None
        self._r731_search_timer = eTimer()
        self._r731_search_timer.callback.append(self._r731_poll_search)''')
    src=replace_once(src,'        self.onClose.append(self._cleanup)',
    '''        self.onClose.append(self._cleanup)
        self.onClose.append(self._r731_cleanup)''')
    src=replace_once(src,'        self["key_menu"] = Label("MENU REJECT  |  1 ADD  |  4 ALL")',
    '''        self["key_menu"] = Label("5 SEARCH  |  6 FTA")''')
    src=replace_once(src, '"2": self._open_auto_scan, "4": self._open_legacy_all_sources,',
    '"2": self._open_auto_scan, "4": self._open_legacy_all_sources, "5": self._r731_search_dialog, "6": self._r731_toggle_fta,')
    src=replace_once(src,'''            rows = _preview_sat_service_rows(self.session, current_raw)
        except Exception:
            rows = []
        if current_crypted is True''',
    '''            rows = _preview_sat_service_rows(self.session, current_raw)
            if self._r731_show_fta:
                # Complete DVB lamedb cache, only positively-known clear services.
                # Unknown CA state is never silently classified as FTA.
                orbital = _sat_orbital_position(current_raw)
                existing = set(_dvb_service_key(row.get("ref")) for row in rows)
                for candidate in _lamedb_tv_service_rows():
                    if candidate.get("crypted") is not False:
                        continue
                    if orbital is not None and candidate.get("orbital_position") != orbital:
                        continue
                    key = _dvb_service_key(candidate.get("ref"))
                    if key and key not in existing:
                        rows.append(dict(candidate))
                        existing.add(key)
        except Exception:
            rows = []
        if current_crypted is True''')
    src=replace_once(src,'            self["detail"].setText("SAT list loaded • CRYPTED TV only • RIGHT returns to candidates")',
    '''            self["detail"].setText("SAT list loaded • %s • RIGHT for IPTV candidates" %
                                   ("CRYPTED + confirmed FTA" if self._r731_show_fta else "CRYPTED only"))''')
    src=replace_once(src,'''        self["left_head"].setText(("▶ " if self.focus == "left" else "  ") + left_text)
        self["right_head"]''',
    '''        if self._r731_show_fta:
            left_text = "SAT %s • CRYPTED + FTA • %d TV" % (same_sat, len(self.sat_rows))
        self["left_head"].setText(("▶ " if self.focus == "left" else "  ") + left_text)
        self["right_head"]''')
    src=replace_once(src,'''        self.sat_ref_string = raw
        try: self.candidate_expand_timer.stop()''',
    '''        self.sat_ref_string = raw
        if self._r731_search_ref and self._r731_search_ref != raw:
            self._r731_search_active = False
            self._r731_search_rows = []
            self._r731_search_query = ""
            self._r731_search_ref = ""
        try: self.candidate_expand_timer.stop()''')
    # KEY CH+/- page through all indexed literal results in bounded 48-row lists.
    src=replace_once(src,'''        if self.focus != "right":
            return self._page_sat(step)
        if not self.channels:''',
    '''        if self.focus != "right":
            return self._page_sat(step)
        if self._r731_search_active:
            return self._r731_page_search(step)
        if not self.channels:''')
    # A single completed background worker is allowed: no competing searches,
    # no full list rendering on the GUI and no API/web calls inside the worker.
    src=replace_once(src,'''    def _sat_key(self, raw=None):
        return sat_service_key(str(raw if raw is not None else self.sat_ref_string or ""))''',
    '''    def _r731_cleanup(self):
        try: self._r731_search_timer.stop()
        except Exception: pass

    def _r731_toggle_fta(self):
        """6 toggles positively classified FTA services, no fallback bypass."""
        self._r731_show_fta = not self._r731_show_fta
        self._sat_rows_loaded = False
        self._sat_list_dirty = True
        if self._ensure_full_sat_rows():
            self._set_focus("left")
        self["status"].setText("SAT filter: %s • no changes to live FTA fallback" %
                               ("CRYPTED + FTA" if self._r731_show_fta else "CRYPTED ONLY"))

    def _r731_search_dialog(self):
        """Explicit indexed full-catalogue search, independent of score cutoffs."""
        if self._r731_search_worker is not None and self._r731_search_worker.is_alive():
            self["status"].setText("SEARCH RUNNING • previous catalogue query still working")
            return
        try:
            from Screens.VirtualKeyBoard import VirtualKeyBoard
            self.session.openWithCallback(self._r731_start_search, VirtualKeyBoard,
                title="IPTV SEARCH • name/brand • all configured servers", text=self.sat_name or "")
        except Exception as e:
            self["status"].setText("Keyboard unavailable: %s" % str(e)[:90])

    def _r731_start_search(self, value=None):
        query = clean_display_name(value or "").strip()
        if len(query) < 2:
            return
        if self._r731_search_worker is not None and self._r731_search_worker.is_alive():
            return
        catalog = MONITOR.catalog if MONITOR is not None else None
        if catalog is None or not getattr(catalog, "channels", None):
            self["status"].setText("No IPTV catalogue loaded")
            return
        sat_ref = str(self.sat_ref_string or "")
        ctx = dict(self.context or {})
        self._r731_search_ref = sat_ref
        self._r731_search_query = query
        self._r731_search_rows = []
        self._r731_search_page = 0
        self._r731_search_active = False
        self._r731_search_result = None
        # Scores are intentionally not used as search exclusion rules.
        def worker():
            try:
                limit = max(320, len(catalog.channels))
                found = catalog.manual_search(query, topn=limit, context=ctx)
                self._r731_search_result = (sat_ref, query, found, "")
            except Exception as exc:
                self._r731_search_result = (sat_ref, query, [], str(exc)[:150])
        thread = threading.Thread(target=worker, name="IPToSatR731ManualIndex")
        thread.daemon = True
        self._r731_search_worker = thread
        thread.start()
        self["status"].setText("INDEXED SEARCH • %s • all IPTV sources • background" % query[:48])
        try: self._r731_search_timer.start(100, True)
        except Exception: pass

    def _r731_poll_search(self):
        if self._closed_for_async:
            return
        worker = self._r731_search_worker
        if worker is not None and worker.is_alive():
            try: self._r731_search_timer.start(120, True)
            except Exception: pass
            return
        result = self._r731_search_result
        self._r731_search_worker = None
        self._r731_search_result = None
        if not result:
            return
        ref, query, found, error = result
        if ref != str(self.sat_ref_string or "") or query != self._r731_search_query:
            return
        if error:
            self["status"].setText("SEARCH ERROR • %s" % error[:105])
            return
        rows = _preview_channel_rows(found)
        for ch in rows:
            ch["_manual_candidate"] = True
        self._r731_search_rows = rows
        self._r731_search_active = bool(rows)
        self._r731_search_page = 0
        if not rows:
            self["status"].setText("NO LITERAL RESULTS • %s • press 5 to search another name" % query[:44])
            return
        self._r731_show_search_page()

    def _r731_show_search_page(self):
        if not self._r731_search_active:
            return
        page_size = 48
        total = len(self._r731_search_rows)
        count = (total + page_size - 1) // page_size
        page = max(0, min(self._r731_search_page, count - 1))
        self._r731_search_page = page
        self.channels = [dict(row) for row in self._r731_search_rows[page*page_size:(page+1)*page_size]]
        self.selected_index = 0
        self._render_source_list(keep_index=False)
        self._set_focus("right")
        self["status"].setText("SEARCH %s • %d candidates • page %d/%d • CH+/- next page" %
                               (self._r731_search_query[:31],total,page+1,count))

    def _r731_page_search(self, direction):
        if not self._r731_search_active:
            return
        count = (len(self._r731_search_rows) + 47) // 48
        self._r731_search_page = max(0,min(count-1,self._r731_search_page+(1 if direction>0 else -1)))
        self._r731_show_search_page()

    def _sat_key(self, raw=None):
        return sat_service_key(str(raw if raw is not None else self.sat_ref_string or ""))''')
    # Correct misleading header from fixed MAX 48 after deep expansion.
    src=replace_once(src,'''        self["right_head"].setText(("▶ " if self.focus == "right" else "  ") + "CANDIDATES • %d BEST • MAX %d • P+B1+B2" % (len(self.channels), self.MAX_BROWSER_CANDIDATES))''',
    '''        self["right_head"].setText(("▶ " if self.focus == "right" else "  ") +
             ("SEARCH %d/%d • P+B1+B2" % (len(self.channels),len(self._r731_search_rows))
              if self._r731_search_active else
              "CANDIDATES • %d • P+B1+B2 • 5 SEARCH" % len(self.channels)))''')
    return src
