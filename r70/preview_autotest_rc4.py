"""r70-rc4 Preview Auto-Test: bounded user-triggered candidate verification.

Operate exclusively inside Preview Browser after BLUE on the SAT column or
key 3. Never test all providers on background zap, never auto-save an ambiguous
REVIEW match and never change existing playback/failover callbacks.
"""
import functools


def attach_preview(preview_cls, namespace):
    if getattr(preview_cls, "_r70_autotest_attached", False):
        return preview_cls
    need = ("_blue_action", "_preview_selected", "_record_preview_failure",
            "_start_quality_analysis", "_poll", "_sat_selection_changed",
            "_cleanup", "_move_up", "_move_down")
    old = {name: getattr(preview_cls, name, None) for name in need}
    timer_type = namespace.get("eTimer")
    fingerprint = namespace.get("channel_fingerprint")
    if timer_type is None or not callable(fingerprint) or not all(callable(f) for f in old.values()):
        return preview_cls

    def stop(self):
        self._r70_autotest_running = False
        self._r70_autotest_queue = []
        try:
            self._r70_autotest_timer.stop()
        except Exception:
            pass

    def arm(self):
        timer = getattr(self, "_r70_autotest_timer", None)
        if timer is None:
            timer = timer_type()
            timer.callback.append(lambda: next_candidate(self))
            self._r70_autotest_timer = timer
        timer.start(120, True)

    def next_candidate(self):
        if not getattr(self, "_r70_autotest_running", False):
            return
        if getattr(self, "_closed_for_async", False) or self.sat_ref_string != self._r70_autotest_ref:
            stop(self)
            return
        rows = getattr(self, "channels", []) or []
        while self._r70_autotest_queue:
            wanted = self._r70_autotest_queue.pop(0)
            idx = next((i for i, c in enumerate(rows) if fingerprint(c) == wanted), -1)
            if idx < 0:
                continue
            self._r70_autotest_tried += 1
            self.selected_index = idx
            try:
                self._set_focus("right")
                self["source_list"].moveToIndex(idx)
            except Exception:
                pass
            try:
                self["detail"].setText(
                    "AUTO TEST %d/%d • decoding selected IPTV source • GREEN locks only after "
                    "verified picture + audio" %
                    (self._r70_autotest_tried, self._r70_autotest_total))
            except Exception:
                pass
            old["_preview_selected"](self)
            return
        stop(self)
        try:
            self["status"].setText("AUTO TEST • no candidate with verified video")
            self["detail"].setText(
                "All %d candidates failed or were rejected • YELLOW = All Sources; "
                "no mapping modified" % getattr(self, "_r70_autotest_tried", 0))
        except Exception:
            pass

    def begin(self):
        if getattr(self, "_closed_for_async", False):
            return
        stop(self)
        channels = list(getattr(self, "channels", []) or [])
        if not channels:
            try:
                self["detail"].setText(
                    "No candidates loaded yet • wait for P/B1/B2 or open YELLOW All Sources")
            except Exception:
                pass
            return
        ref = str(getattr(self, "sat_ref_string", "") or "")
        if not ref:
            return
        seen = set()
        queue = []
        # Current sorted ranking is provider/region-aware. Keep its order.
        # Hard rejected/user-rejected candidates are never automatically tried.
        for ch in channels:
            if not isinstance(ch, dict) or not ch.get("url"):
                continue
            try:
                decision = self._candidate_decision(ch)
                if decision not in ("MANUAL", "SAFE", "ALLOWED", "REVIEW"):
                    continue
                details = ch.get("_preview_details") or {}
                if details.get("reject_reason"):
                    continue
                fp = fingerprint(ch)
                if not fp or fp in seen:
                    continue
                seen.add(fp)
                queue.append(fp)
                if len(queue) >= 6:
                    break
            except Exception:
                continue
        if not queue:
            try:
                self["detail"].setText(
                    "No eligible source: every candidate is rejected or lacks a stream URL. "
                    "Use YELLOW All Sources to review the actual source.")
            except Exception:
                pass
            return
        self._r70_autotest_queue = queue
        self._r70_autotest_total = len(queue)
        self._r70_autotest_tried = 0
        self._r70_autotest_ref = ref
        self._r70_autotest_running = True
        arm(self)

    @functools.wraps(old["_blue_action"])
    def blue(self):
        if getattr(self, "focus", "left") == "left":
            return begin(self)
        stop(self)
        return old["_blue_action"](self)

    @functools.wraps(old["_record_preview_failure"])
    def fail(self, reason):
        result = old["_record_preview_failure"](self, reason)
        if (getattr(self, "_r70_autotest_running", False)
                and getattr(self, "_r70_autotest_ref", "") == self.sat_ref_string):
            arm(self)
        return result

    @functools.wraps(old["_start_quality_analysis"])
    def verified(self):
        result = old["_start_quality_analysis"](self)
        if (getattr(self, "_r70_autotest_running", False)
                and getattr(self, "current_result", "") == "PLAYING"
                and self.sat_ref_string == self._r70_autotest_ref):
            try:
                if getattr(self, "_preview_audio", {}).get(
                        (self._sat_key(), getattr(self, "active_fp", "")), {}).get(
                        "state", "") == "MISMATCH":
                    # Do not lock a wrong language/feed.
                    arm(self)
                    return result
            except Exception:
                pass
            attempt = self._r70_autotest_tried
            stop(self)
            try:
                self["status"].setText(
                    "AUTO TEST • VIDEO VERIFIED • candidate %d • GREEN = USE / LOCK" % attempt)
                self["detail"].setText(
                    "Video confirmed on candidate %d. Compare picture and audio, "
                    "then press GREEN to keep this exact SAT ↔ IPTV mapping." % attempt)
            except Exception:
                pass
        return result

    @functools.wraps(old["_poll"])
    def poll(self):
        result = old["_poll"](self)
        if (getattr(self, "_r70_autotest_running", False)
                and getattr(self, "finished", False)
                and getattr(self, "current_result", "") == "VERIFY"):
            # The player may actually be playing despite missing decoder
            # telemetry. Never switch away from a potentially good video.
            stop(self)
            try:
                self["status"].setText(
                    "AUTO TEST • PLAYER OPENED • verify video/audio manually")
                self["detail"].setText(
                    "Decoder telemetry unavailable: check picture + audio. "
                    "Press GREEN if correct or BLUE to choose another source.")
            except Exception:
                pass
        return result

    @functools.wraps(old["_sat_selection_changed"])
    def sat_changed(self):
        if (getattr(self, "_r70_autotest_running", False)
                and self.sat_ref_string != getattr(self, "_r70_autotest_ref", None)):
            stop(self)
        return old["_sat_selection_changed"](self)

    @functools.wraps(old["_move_up"])
    def moved_up(self):
        stop(self)
        return old["_move_up"](self)

    @functools.wraps(old["_move_down"])
    def moved_down(self):
        stop(self)
        return old["_move_down"](self)

    @functools.wraps(old["_cleanup"])
    def cleanup(self):
        stop(self)
        return old["_cleanup"](self)

    preview_cls._r70_autotest_start = begin
    preview_cls._r70_autotest_stop = stop
    preview_cls._blue_action = blue
    preview_cls._record_preview_failure = fail
    preview_cls._start_quality_analysis = verified
    preview_cls._poll = poll
    preview_cls._sat_selection_changed = sat_changed
    preview_cls._move_up = moved_up
    preview_cls._move_down = moved_down
    preview_cls._cleanup = cleanup
    preview_cls._r70_autotest_attached = True
    return preview_cls
