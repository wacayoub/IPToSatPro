# -*- coding: utf-8 -*-
"""R73.4 Preview-only: foreground full candidates, late reliable resolution.

No automatic live mapping, player, satellite tuner, audio/monitor or timeshift changes.
"""

def replace_once(src, before, after):
    count=src.count(before)
    if count != 1:
        raise AssertionError("R73.4 anchor changed: count=%s %r"%(count,before[:95]))
    return src.replace(before,after,1)

def patch_plugin(src):
    # Native lamedb/CAID roster can synchronously scan thousands of DVB rows.
    # Prioritize complete indexed candidate list on entering Preview, then do
    # the expensive SAT-list expansion. Never show a partial progressive IPTV list.
    src=replace_once(src,
        'try: self.sat_roster_timer.start(750, True)',
        'try: self.sat_roster_timer.start(8500, True)')
    src=replace_once(src,
        '''        self._render_source_list(keep_index=True)
        self._update_header()
        if self._r71_deep_requested and self._r71_deep_target_ref == raw and not self._r71_worker_deep:''',
        '''        self._render_source_list(keep_index=True)
        self._update_header()
        # Candidate list is fully available before the potentially blocking
        # lamedb/native encryption roster pass starts.
        if not self._sat_rows_loaded:
            try:
                self.sat_roster_timer.stop()
                self.sat_roster_timer.start(350, True)
            except Exception:
                pass
        _startup_log("PREVIEW_UI_CANDIDATES",
            "candidate_count=%d full=%d rank_elapsed=%dms" %
            (len(self.channels), len(self._r732_auto_rows), elapsed))
        if self._r71_deep_requested and self._r71_deep_target_ref == raw and not self._r71_worker_deep:''')
    src=replace_once(src,
        '''        self._render_source_list(keep_index=False)
        self._update_header()
        if self.channels:''',
        '''        self._render_source_list(keep_index=False)
        self._update_header()
        if complete and self.channels and not self._sat_rows_loaded:
            try:
                self.sat_roster_timer.stop()
                self.sat_roster_timer.start(350, True)
            except Exception:
                pass
        if self.channels:''')
    # VERIFY is not a playing-success verdict. But a decoder can produce
    # trustworthy requested-service dimensions without exposing PTS.  Keep
    # sampling and recording resolution, independently of the PLAYING gate.
    src=replace_once(src,
        '''        self["status"].setText("PLAYING • measuring resolution / FPS / codec / bitrate / Dolby / IQ...")''',
        '''        state = "PLAYING" if self.preview_ok else "VERIFY"
        self["status"].setText("%s • checking decoder resolution / FPS / codec / bitrate / audio..." % state)''')
    src=replace_once(src,
        '''        if not self.preview_ok or not self.active_fp or self.active_sat_ref != self.sat_ref_string:
            return
        now = time.time(); elapsed = max(0.001, now - self.quality_started_at)
        final = elapsed >= self.QUALITY_SAMPLE_WINDOW_S
        info = self._video_info_now()''',
        '''        if not (self.preview_ok or self.current_result == "VERIFY") or not self.active_fp or self.active_sat_ref != self.sat_ref_string:
            return
        # Do not persist dimensions from another channel or a stale decoder.
        if not self._preview_player_active():
            return
        now = time.time(); elapsed = max(0.001, now - self.quality_started_at)
        final = elapsed >= self.QUALITY_SAMPLE_WINDOW_S
        info = self._video_info_now()''')
    src=replace_once(src,
        '''        if w <= 0 or h <= 0:
            w, h = self._dimensions()
        fps = float(info.get("fps") or 0); codec = str(info.get("codec") or "?")''',
        '''        if w <= 0 or h <= 0:
            w, h = self._dimensions()
        # If OpenATV/ServiceApp reports video dimensions late, keep polling
        # automatically for up to eight seconds. Do not zap the stream again.
        # Presence of dimensions is telemetry, NOT proof of moving video.
        final = bool((elapsed >= self.QUALITY_SAMPLE_WINDOW_S and w > 0 and h > 0) or elapsed >= 8.0)
        fps = float(info.get("fps") or 0); codec = str(info.get("codec") or "?")''')
    src=replace_once(src,
        '''        phase = "MEASURED" if final else "MEASURING"
        self["status"].setText(("PLAYING • %s • %s • %s • %s • %s • %s • %s • %s" % (phase, mode, codec, ratetxt, iqtxt, dolbytxt, opentxt, self._audio_status_text(self.channel)))[:250])''',
        '''        phase = "MEASURED" if final and w > 0 and h > 0 else "MEASURING"
        state = "PLAYING" if self.preview_ok else "VERIFY"
        self["status"].setText(("%s • %s • %s • %s • %s • %s • %s • %s • %s" % (state, phase, mode, codec, ratetxt, iqtxt, dolbytxt, opentxt, self._audio_status_text(self.channel)))[:250])''')
    src=replace_once(src,
        '''        if self.sat_ref_string == self.active_sat_ref:
            self._render_source_list(keep_index=True)
        self._update_verify_strip()
        if not final:''',
        '''        if w > 0 and h > 0:
            _startup_log("PREVIEW_RESOLUTION",
                "state=%s width=%d height=%d elapsed=%dms saved=%s" %
                ("PLAYING" if self.preview_ok else "VERIFY",
                 w, h, int(elapsed*1000),
                 "health" if MONITOR is not None else "channel-only"))
        if self.sat_ref_string == self.active_sat_ref:
            self._render_source_list(keep_index=True)
        self._update_verify_strip()
        if not final:''')
    src=replace_once(src,
        '''                self["detail"].setText("Decoder statistics unavailable • if picture/audio are correct, press GREEN to LOCK directly")
                self._render_source_list(keep_index=True)
                self._update_header()
                return''',
        '''                self["detail"].setText("Decoder PTS unavailable • continuing resolution measurement without zap • verify picture/audio before locking")
                self._render_source_list(keep_index=True)
                self._update_header()
                self._start_quality_analysis()
                return''')
    return src
