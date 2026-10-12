# -*- coding: utf-8 -*-
"""R73.7 Preview OK must actually expose video below the opaque Enigma2 skin.

Hides only PreviewBrowser GUI for a bounded period; restores by independent
eTimer even if the remote is not handled while the screen is hidden.
Never changes player, monitoring, timeshift, sources, or mapping selection.
"""
def one(src,a,b):
    n=src.count(a)
    if n!=1: raise AssertionError("R73.7 UI patch anchor count=%d %r"%(n,a[:110]))
    return src.replace(a,b,1)

def patch_plugin(src):
    # Guarantee a timed return: Screen.hide() can hide its own ActionMap too.
    src=one(src,
'''        self.quality_timer = eTimer(); self.quality_timer.callback.append(self._quality_poll)
        self.sat_change_timer = eTimer();''',
'''        self.quality_timer = eTimer(); self.quality_timer.callback.append(self._quality_poll)
        self._r737_video_timer = eTimer()
        self._r737_video_timer.callback.append(self._r737_restore_video)
        self._r737_video_visible = False
        self.sat_change_timer = eTimer();''')
    src=one(src,
'''        self.onClose.append(self._r731_cleanup)

    def _start(self):''',
'''        self.onClose.append(self._r731_cleanup)
        self.onClose.append(self._r737_cleanup_video)

    def _start(self):''')
    functions='''    def _r737_show_video_fullscreen(self):
        """Temporarily reveal decoded IPTV picture behind the opaque skin.

        This is a visual exposure step, not a false claim of VIDEO VERIFIED.
        The timer always returns the UI to its usable state after 8 seconds.
        """
        if self._r737_video_visible:
            try: self._r737_video_timer.stop()
            except Exception: pass
        self._r737_video_visible = True
        self["detail"].setText("VIDEO FULLSCREEN • 8 s • returning to Preview automatically")
        try:
            self._r737_video_timer.start(8000, True)
        except Exception:
            self._r737_video_visible = False
            return
        try:
            self.hide()
            _startup_log("PREVIEW_VIDEO_WINDOW",
                "state=FULLSCREEN sat=%r iptv=%r mode=%s" %
                (self.sat_name, (self.channel or {}).get("name"), self.mode))
        except Exception as err:
            _startup_log("PREVIEW_VIDEO_WINDOW","state=HIDE_FAILED error=%s" % str(err)[:100])
            self._r737_restore_video()

    def _r737_restore_video(self):
        try: self._r737_video_timer.stop()
        except Exception: pass
        if not self._r737_video_visible:
            return
        self._r737_video_visible = False
        try: self.show()
        except Exception as err:
            _startup_log("PREVIEW_VIDEO_WINDOW","state=SHOW_FAILED error=%s" % str(err)[:100])
        try: w,h = self._dimensions()
        except Exception: w,h=0,0
        _startup_log("PREVIEW_VIDEO_WINDOW",
            "state=RETURN result=%s dimensions=%dx%d player_active=%s" %
            (self.current_result,int(w),int(h),bool(self._preview_player_active())))
        try:
            self._render_source_list(keep_index=True)
            self._update_header()
        except Exception: pass
        if self.current_result not in ("PLAYING","VERIFY","FAILED"):
            self["detail"].setText("OPENING • select another SAFE candidate if the previous stream remains black")

    def _r737_cleanup_video(self):
        self._r737_video_visible = False
        try: self._r737_video_timer.stop()
        except Exception: pass

'''
    src=one(src,'    def _preview_selected(self):',functions+'    def _preview_selected(self):')
    src=one(src,
'''        self._update_header()
        self._play_current_mode()

    def _play_current_mode(self):''',
'''        self._update_header()
        self._play_current_mode()
        # OK must make the actual IPTV picture visible, not just cover it
        # with Preview Browser's opaque Neo Dark background and list panes.
        if not self.finished:
            self._r737_show_video_fullscreen()

    def _play_current_mode(self):''')
    src=one(src,
'''            "OK tests the source; GREEN locks only after confirmation.",''',
'''            "OK = 8-second FULLSCREEN video test. AUTO mapping does not prove picture/audio.",''')
    src=one(src,
'''        self["detail"] = Label("LEFT: SAT channels • RIGHT: IPTV sources • OK previews only on source panel")''',
'''        self["detail"] = Label("LEFT: SAT channels • RIGHT: IPTV sources • OK = FULLSCREEN video test (8 s) • AUTO = metadata only")''')
    src=one(src,
'''        self["verify"] = Label("CHECK: select SAT → RIGHT → OK preview → visually confirm video before GREEN")''',
'''        self["verify"] = Label("AUTO maps SAFE candidates by identity • OK displays real video fullscreen • GREEN corrects manually")''')
    return src
