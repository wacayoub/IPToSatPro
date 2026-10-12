# -*- coding: utf-8 -*-
"""R74 unified Preview: native active-bouquet SAT roster, legible compact UI,
bounded source ranking, existing automatic playback and diagnostics.

All changes are scoped to the Preview plugin and catalog ranking. No edits to
monitor.py, stream player, timeshift, service database, settings or user locks.
"""

def one(src, old, new):
    count=src.count(old)
    if count != 1:
        raise AssertionError("R74 source drift %d: %r" % (count, old[:130]))
    return src.replace(old,new,1)

BOUQUET_HELPERS = '''
def _r74_active_bouquet_root():
    """Native Enigma2 CURRENT service-list root, never a userbouquet file guess."""
    try:
        from Screens.InfoBar import InfoBar
        ui=getattr(InfoBar,"instance",None)
        service_list=getattr(ui,"servicelist",None)
        root=service_list.getRoot() if service_list is not None else None
        raw=root.toString() if root is not None else ""
        return (root,service_list) if "FROM BOUQUET" in raw.upper() else (None,None)
    except Exception:
        return (None,None)


def _r74_active_bouquet_rows(session):
    """Read only current bouquet in its ORIGINAL order using Enigma2 service center.

    This O(number of current bouquet rows) path avoids lamedb full-orbit scans.
    The left SAT panel deliberately ignores IPTV/radio/directory rows.
    """
    root,service_list=_r74_active_bouquet_root()
    if root is None:
        return [],""
    try:
        from enigma import eServiceCenter
        listing=eServiceCenter.getInstance().list(root)
        if listing is None:
            return [],""
        try:
            items=listing.getContent("SN",True)
        except Exception:
            items=None
        if items is None:
            items=[]
            for _ in range(600):
                item=listing.getNext()
                if item is None or not item.valid():
                    break
                items.append((item.toString(),""))
        result=[]
        seen=set()
        for entry in items:
            try:
                if isinstance(entry,(list,tuple)):
                    raw=entry[0].toString() if hasattr(entry[0],"toString") else str(entry[0] or "")
                    label=str(entry[1] or "") if len(entry)>1 else ""
                else:
                    raw=entry.toString() if hasattr(entry,"toString") else str(entry or "")
                    label=""
                if not raw or raw in seen:
                    continue
                ref=eServiceReference(raw)
                if not _is_tv_dvb_service(ref,raw):
                    continue
                seen.add(raw)
                if not label:
                    label=ServiceReference(ref).getServiceName() or ""
                result.append({"ref":raw,"name":clean_display_name(label) or "SAT TV",
                               "crypted":None,"orbital_position":_sat_orbital_position(raw)})
            except Exception:
                continue
        title=""
        try:
            bouquets=service_list.getBouquetList() or []
            wanted=root.toString()
            for item in bouquets:
                if not isinstance(item,(list,tuple)) or len(item)<2:
                    continue
                b_ref=item[1]
                if getattr(b_ref,"toString",lambda:"")()==wanted:
                    title=clean_display_name(item[0]);break
        except Exception:
            pass
        return result,title or "Bouquet actuel"
    except Exception as err:
        _startup_log("R74_BOUQUET_ERROR",str(err)[:130])
        return [],""


'''


def _patch_filters(src):
    """Fast non-destructive view filters: source role, SAFE and market/lang/quality.

    Full all-server candidate cache is never discarded and manual locks never
    change; CH+/- remains page navigation over the filtered view.
    """
    src=one(src,'''        self._r74_bouquet_name = "Bouquet actuel"
        self.input_sat_ref''',
'''        self._r74_bouquet_name = "Bouquet actuel"
        self._r74_role_filter = "ALL"
        self._r74_safe_only = False
        self._r74_meta_filter = "ALL"
        self._r74_filtered_rows = None
        self.input_sat_ref''')

    src=one(src,''' "7": self._r74_switch_roster,''',
''' "7": self._r74_switch_roster, "8": self._r74_cycle_server,
            "9": self._r74_toggle_safe, "3": self._r74_cycle_metadata,''')

    methods='''    def _r74_filters_active(self):
        return (self._r74_role_filter!="ALL" or self._r74_safe_only
                or self._r74_meta_filter!="ALL")

    def _r74_apply_filters(self):
        """Filter in memory; no scoring, network, extra catalogue scans or locks."""
        all_rows=list(self._r732_auto_rows or [])
        wanted=self._r74_role_filter
        rule=self._r74_meta_filter
        result=[]
        for ch in all_rows:
            role=str(ch.get("server_role") or "SERVER").upper()
            if wanted!="ALL" and wanted!=role:
                continue
            if self._r74_safe_only and self._candidate_decision(ch) not in ("SAFE","ALLOWED","MANUAL"):
                continue
            if rule in ("FR","EN","AR"):
                lang=str(ch.get("language") or "").upper()
                market=str(ch.get("market") or "").upper()
                if lang!=rule and market!=rule:
                    continue
            if rule in ("HD+","FHD+","UHD"):
                quality=str(ch.get("quality") or "").upper()
                try: width=int(ch.get("actual_width") or 0)
                except Exception: width=0
                if rule=="HD+" and not any(x in quality for x in ("HD","FHD","4K","UHD")) and width<1280:
                    continue
                if rule=="FHD+" and not any(x in quality for x in ("FHD","1080","4K","UHD")) and width<1800:
                    continue
                if rule=="UHD" and not any(x in quality for x in ("4K","UHD","2160")) and width<3000:
                    continue
            result.append(dict(ch))
        self._r74_filtered_rows=result if self._r74_filters_active() else None
        self._r732_auto_page=0
        self.selected_index=0
        self.channels=result[:48]
        self._render_source_list(keep_index=False)
        self._set_focus(self.focus)
        self["status"].setText("IPTV %d/%d • server %s • %s • %s"%(len(result),len(all_rows),
            self._r74_role_filter,"SAFE" if self._r74_safe_only else "ALL",
            self._r74_meta_filter))
        _startup_log("R74_FILTER","role=%s safe=%d meta=%s rows=%d full=%d"%
            (self._r74_role_filter,int(self._r74_safe_only),self._r74_meta_filter,len(result),len(all_rows)))

    def _r74_cycle_server(self):
        values=("ALL","PRIMARY","BACKUP1","BACKUP2")
        self._r74_role_filter=values[(values.index(self._r74_role_filter)+1)%len(values)]
        self._r74_apply_filters()

    def _r74_toggle_safe(self):
        self._r74_safe_only=not self._r74_safe_only
        self._r74_apply_filters()

    def _r74_cycle_metadata(self):
        values=("ALL","FR","AR","EN","HD+","FHD+","UHD")
        self._r74_meta_filter=values[(values.index(self._r74_meta_filter)+1)%len(values)]
        self._r74_apply_filters()

'''
    src=one(src,'    def _r74_switch_roster(self):',methods+'    def _r74_switch_roster(self):')

    src=one(src,'''        total = len(self._r732_auto_rows)
        pagecount = (total+47)//48
        self._r732_auto_page = max(0, min(pagecount-1, self._r732_auto_page+(1 if direction>0 else -1)))
        start = self._r732_auto_page*48
        self.channels = [dict(ch) for ch in self._r732_auto_rows[start:start+48]]''',
'''        all_rows = self._r74_filtered_rows if self._r74_filters_active() else self._r732_auto_rows
        total = len(all_rows or [])
        if not total:
            return
        pagecount = (total+47)//48
        self._r732_auto_page = max(0, min(pagecount-1, self._r732_auto_page+(1 if direction>0 else -1)))
        start = self._r732_auto_page*48
        self.channels = [dict(ch) for ch in all_rows[start:start+48]]''')
    src=one(src,'''        self._set_focus(self.focus)

        # Second phase: populate the fuller bounded candidate set after the instant list is on''',
'''        self._set_focus(self.focus)
        if self._r74_filters_active():
            self._r74_apply_filters()

        # Second phase: populate the fuller bounded candidate set after the instant list is on''')
    src=one(src,'''        _startup_log("PREVIEW_UI_CANDIDATES",''',
'''        if self._r74_filters_active():
            self._r74_apply_filters()
        _startup_log("PREVIEW_UI_CANDIDATES",''')
    src=one(src,'''        self["focus_hint"].setText("FOCUS: %s" % ("SOURCES" if self.focus == "right" else "SAT"))''',
'''        if self._r74_filters_active():
            self["right_head"].setText("IPTV FILTRE • %s • %s • %s" % (
                self._r74_role_filter,"SAFE" if self._r74_safe_only else "ALL",
                self._r74_meta_filter))
        self["focus_hint"].setText("FOCUS: %s" % ("SOURCES" if self.focus == "right" else "SAT"))''')
    return src

def patch_plugin(src):
    src=one(src,'def _preview_sat_service_rows(session, current_sat_ref_string):',
        BOUQUET_HELPERS+'def _preview_sat_service_rows(session, current_sat_ref_string):')

    src=one(src,'''            from .preview_theme_r73 import PREVIEW_R73_FHD
            self.skin = _theme_skin(PREVIEW_R73_FHD)''',
        '''            from .preview_theme_r74 import PREVIEW_R74_FHD
            self.skin = _theme_skin(PREVIEW_R74_FHD)''')
    src=one(src,'''        self.input_sat_ref = str(sat_ref_string or "")''',
        '''        self._r74_roster_mode = "BOUQUET" if _r74_active_bouquet_root()[0] is not None else "SATELLITE"
        self._r74_bouquet_name = "Bouquet actuel"
        self.input_sat_ref = str(sat_ref_string or "")''')
    src=one(src,'''        self["title"] = Label("PREVIEW BROWSER PRO  |  NEO DARK R73")''',
        '''        self["title"] = Label("PREVIEW BROWSER PRO  |  NEO DARK R74")''')
    src=one(src,'''        self["verify"] = Label("AUTO maps SAFE candidates by identity • OK displays real video fullscreen • GREEN corrects manually")''',
        '''        self["verify"] = Label("AUTO SELECT / PLAY • OK: test vidéo 8 s • GREEN: correction manuelle")''')
    src=one(src,'''        self["detail"] = Label("LEFT: SAT channels • RIGHT: IPTV sources • OK = FULLSCREEN video test (8 s) • AUTO = metadata only")''',
        '''        self["detail"] = Label("7: Bouquet / Satellite   •   6: filtre FTA satellite   •   CH+/-: pages")''')
    src=one(src,'''        self["sat_list"] = PreviewBrowserList([], width=488, item_height=42, font_size=19)''',
        '''        self["sat_list"] = PreviewBrowserList([], width=492, item_height=43, font_size=19)''')
    src=one(src,'''        self["source_list"] = PreviewBrowserList([], width=1066, item_height=42, font_size=18)''',
        '''        self["source_list"] = PreviewBrowserList([], width=1054, item_height=43, font_size=18)''')
    src=one(src,'''        self["key_menu"] = Label("5 SEARCH  |  6 FTA")''',
        '''        self["key_menu"] = Label("7 BOUQUET / SAT")''')
    src=one(src,''' "5": self._r731_search_dialog, "6": self._r731_toggle_fta,''',
        ''' "5": self._r731_search_dialog, "6": self._r731_toggle_fta, "7": self._r74_switch_roster,''')
    src=one(src,'''        try: self.sat_roster_timer.start(8500, True)''',
        '''        try: self.sat_roster_timer.start(55 if self._r74_roster_mode == "BOUQUET" else 750, True)''')

    # The previously rigid lamedb-only path is now the fallback for satellite mode.
    src=one(src,'''    def _ensure_full_sat_rows(self):
        if self._sat_rows_loaded:
            return True
        current_raw = str(self.sat_ref_string or self.input_sat_ref or "")''',
'''    def _ensure_full_sat_rows(self):
        if self._sat_rows_loaded:
            return True
        if self._r74_roster_mode == "BOUQUET":
            started=time.monotonic()
            rows,bouquet_name=_r74_active_bouquet_rows(self.session)
            if rows:
                self._r74_bouquet_name=bouquet_name
                current_raw=str(self.sat_ref_string or self.input_sat_ref or "")
                idx=next((i for i,row in enumerate(rows)
                          if _dvb_service_key(row.get("ref"))==_dvb_service_key(current_raw)),0)
                self._suppress_sat_change=True
                try:
                    self.sat_rows=rows
                    self.sat_index=idx
                    self._sat_list_dirty=True
                    self._render_sat_list(keep_index=False)
                    try: self["sat_list"].moveToIndex(idx)
                    except Exception: pass
                finally:
                    self._suppress_sat_change=False
                self._sat_rows_loaded=True
                _startup_log("R74_BOUQUET_ROSTER","bouquet=%r tv=%d elapsed=%dms"%
                    (bouquet_name,len(rows),int((time.monotonic()-started)*1000)))
                self["detail"].setText("Bouquet actif • ordre natif • 7 = satellite • 5 = recherche IPTV")
                return True
            self._r74_roster_mode="SATELLITE"
            _startup_log("R74_BOUQUET_FALLBACK","No current native DVB TV bouquet: satellite mode")
        current_raw = str(self.sat_ref_string or self.input_sat_ref or "")''')

    src=one(src,'''    def _r731_toggle_fta(self):''',
'''    def _r74_switch_roster(self):
        """7 switches CURRENT native bouquet vs CURRENT orbital satellite."""
        previous=self._r74_roster_mode
        self._r74_roster_mode="SATELLITE" if previous=="BOUQUET" else "BOUQUET"
        self._sat_rows_loaded=False
        self._sat_list_dirty=True
        self._sat_list_rendered=None
        self._sat_list_source_id=None
        if self._ensure_full_sat_rows():
            self._set_focus("left")
            self._sat_selection_changed()
        self["status"].setText("SAT CHANNELS • %s • %d TV • mode switch 7"%
            (self._r74_roster_mode,len(self.sat_rows)))
        _startup_log("R74_ROSTER_MODE","mode=%s tv=%d"%(self._r74_roster_mode,len(self.sat_rows)))

    def _r731_toggle_fta(self):''')

    # Current native Bouquet includes all DVB TV services, not only crypted.
    src=one(src,'''        self["left_head"].setText(("▶ " if self.focus == "left" else "  ") + left_text)''',
'''        if self._r74_roster_mode=="BOUQUET":
            left_text="BOUQUET • %s • %d TV" % (self._r74_bouquet_name[:21], len(self.sat_rows))
        else:
            left_text="SATELLITE • " + left_text.replace("SAT ","",1)
        self["left_head"].setText(("▶ " if self.focus == "left" else "  ") + left_text[:56])''')

    src=one(src,'''        self["right_head"].setText(("▶ " if self.focus == "right" else "  ") +
             ("SEARCH %d/%d • P+B1+B2" % (len(self.channels),len(self._r731_search_rows))
              if self._r731_search_active else
              "CANDIDATES • %d TOTAL • 48/PAGE • P+B1+B2" % max(len(self.channels),len(self._r732_auto_rows))))''',
'''        self["right_head"].setText(("▶ " if self.focus == "right" else "  ") +
             ("RECHERCHE IPTV • %d" % len(self._r731_search_rows)
              if self._r731_search_active else
              "IPTV • %d candidats • P / B1 / B2 • CH+/- pages" % max(len(self.channels),len(self._r732_auto_rows))))''')

    # Avoid long single-line candidate tags spilling into neighbouring widgets.
    src=one(src,'''            text = "[%s] %s • %s • %s • %s" % (
                _short_role(role), name, quality, server[:16], tag)
            rows.append(self["source_list"].row(text, state))''',
'''            score=ch.get("_preview_score")
            score_text=("%.0f"%float(score)) if score not in (None,"") else "?"
            decision=self._candidate_decision(ch)
            observed=self._health_record(ch)
            measured=bool(observed.get("width") and observed.get("height"))
            state_text="REAL" if measured else "CAT"
            label="%s • %s" % (decision, score_text)
            text="[%s] %s • %s %s • %s • %s" % (
                _short_role(role), name[:32], state_text, quality[:13],
                server[:14], label)
            rows.append(self["source_list"].row(text[:112], state))''')

    # Keep the entire playback and scoring engines as-is; on-screen headings
    # reflect whether a channel has just been mapped or physically decoded.
    src=one(src,'''        self["sat_current"].setText("SAT CURRENT: %s" % clean_display_name(self.sat_name))''',
'''        self["sat_current"].setText("%s   •   %s" % (
            "BOUQUET ACTUEL" if self._r74_roster_mode=="BOUQUET" else "SATELLITE ACTUEL",
            clean_display_name(self.sat_name)[:74]))''')
    src=one(src,'''        self["context_info"].setText("Provider: %s   •   Satellite: %s   •   Access: %s   •   Mapping: %s   •   Result: %s" % (
            provider, sat_display, access, self._mapping_text(), self.current_result))''',
'''        self["context_info"].setText("Provider: %s   •   Sat: %s   •   DVB: %s   •   Mapping: %s   •   Video: %s" % (
            provider[:32], sat_display[:24], access, self._mapping_text()[:34], self.current_result[:25]))''')

    src=_patch_filters(src)
    compile(src,"plugin.py","exec")
    return src

def patch_core(src):
    # Higher coverage still bounded (no 168 full rescores on Vu+ CPU).
    src=one(src,'''        budget=36
        for i in range(36):''',
'''        budget=48
        for i in range(48):''')
    compile(src,"core.py","exec")
    return src
