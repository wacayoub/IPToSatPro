"""r70-rc7: bounded automatic candidate choice, no Preview Browser required.

Manual mappings remain authoritative while their exact stream/replicas work.
Only after ALL player modes and exact replicas fail do we search other
same-SAT-channel sources. A separate strict exact-name REVIEW lane also helps
unmapped SAT channels with unmeasured sources (e.g. TREK).

Never edit saved mappings. Never equate beIN SPORTS 1 with a generic TOD EVENT 7.
No network scan, no background playback of several accounts, no GUI blocking.
"""
import functools
import threading
import time


def _enabled(obj):
    try:
        return bool(obj.cfg.auto_recover_failed_mapping.value)
    except AttributeError:
        return False
    except Exception:
        return False


def _review_exact(monitor, row, fingerprint, normalize, decision_fn):
    try:
        ch, score, details = row
        details = details or {}
        if details.get("reject_reason") or not isinstance(ch, dict):
            return False
        if decision_fn(score, details, float(monitor.cfg.match_threshold.value)) != "REVIEW":
            return False
        if float(score) < 45:
            return False
        satname = monitor.current_match_name or monitor.current_sat_name
        expected = normalize(satname)
        candidate = normalize(ch.get("name", ""))
        if len(expected) < 4 or candidate != expected:
            return False
        identity = sum(float(details.get(k, 0) or 0)
                       for k in ("name", "equivalence", "variant"))
        if identity < 98:
            return False
        # Never force a feed with known wrong market or sound language.
        if float(details.get("market", 0) or 0) < -0.1:
            return False
        if float(details.get("language", 0) or 0) < -0.1:
            return False
        if float(details.get("context", 0) or 0) < -10:
            return False
        if not ch.get("url") or not fingerprint(ch):
            return False
        return True
    except Exception:
        return False


def attach_auto_recovery(cls, namespace):
    if getattr(cls, "_r70_rc7_attached", False):
        return cls
    required = ("_schedule_next_candidate", "_build_candidate_plan",
                "_stop_probe_timers", "_stop_all_timers")
    original = {k: getattr(cls, k, None) for k in required}
    eTimer = namespace.get("eTimer")
    fingerprint = namespace.get("channel_fingerprint")
    normalize = namespace.get("normalize_name")
    decision_fn = namespace.get("match_decision")
    if (eTimer is None or not all(callable(original[k]) for k in required)
            or not all(callable(x) for x in (fingerprint, normalize, decision_fn))):
        return cls

    def cancel(self):
        self._r70_rc7_token = int(getattr(self, "_r70_rc7_token", 0)) + 1
        self._r70_rc7_pending = None
        self._r70_rc7_result = None
        try: self._r70_rc7_timer.stop()
        except Exception: pass

    def _review_plan(self, ranked, omit):
        rows = []
        used = set(omit or [])
        try: rejected = set(self._user_rejected_ids() or [])
        except Exception: rejected = set()
        for row in ranked or []:
            if len(row) != 3:
                continue
            ch, score, details = row
            fp = fingerprint(ch)
            if not fp or fp in used or fp in rejected:
                continue
            if self._health_blocked(ch) or not _review_exact(
                    self, row, fingerprint, normalize, decision_fn):
                continue
            used.add(fp)
            ds = dict(details or {})
            ds["decision"] = "REVIEW_EXACT_AUTO"
            ds["auto_rescue_temporary"] = True
            # Never mark auto-review as a manual lock or source of authority.
            rows.append((ch, float(score), ds, (1, 0, 1, 1, 1, 1),
                         int(ch.get("server_priority", 999))))
            if len(rows) >= 4:
                break
        return rows

    @functools.wraps(original["_build_candidate_plan"])
    def plan(self, ranked, pinned=None):
        base = list(original["_build_candidate_plan"](self, ranked, pinned) or [])
        if not _enabled(self) or pinned is not None or base:
            return base
        return _review_plan(self, ranked, set())[:4]

    def poll(self):
        pending = getattr(self, "_r70_rc7_pending", None)
        if not pending:
            return
        # Never apply a background result after another zap or IPTV selection.
        if (self.current_sat_ref_string != pending["sat_ref"] or
                int(getattr(self, "_r70_rc7_token", 0)) != pending["token"]):
            cancel(self)
            return
        try:
            current = self.session.nav.getCurrentlyPlayingServiceReference()
            current_raw = current.toString() if self._ref_valid(current) else ""
            expected = str(getattr(self, "expected_iptv_ref_string", "") or "")
            if current_raw and current_raw != expected and current_raw != pending["sat_ref"]:
                if not self._is_expected_bridge_iptv(current, current_raw):
                    cancel(self)
                    return
        except Exception:
            cancel(self)
            return
        result = getattr(self, "_r70_rc7_result", None)
        if result is None:
            if time.monotonic() - pending["started"] < 4.0:
                try: self._r70_rc7_timer.start(90, True)
                except Exception: cancel(self)
                return
            self._log("AUTO_RESCUE_TIMEOUT", "ranker slow; safe restore to original SAT")
            cancel(self)
            self._final_restore_sat("Auto-recovery timed out; keeping original SAT")
            return
        cancel(self)
        rows, error = result
        if error:
            self._log("AUTO_RESCUE_ERR", "index ranker failed: %s" % error)
        try:
            safe = list(self._build_candidate_plan(rows) or [])
            used = {fingerprint(x[0]) for x in self.candidate_plan}
            used.update(self.failed_candidate_ids or set())
            selected = [x for x in safe if fingerprint(x[0]) not in used]
            used.update(fingerprint(x[0]) for x in selected)
            selected += [x for x in _review_plan(self, rows, used)]
            selected = selected[:4]
        except Exception as err:
            selected = []
            self._log("AUTO_RESCUE_PLAN_ERR", err.__class__.__name__)
        if not selected:
            self._log("AUTO_RESCUE_EMPTY", "no safe exact identity across other IPTV servers")
            self._final_restore_sat("No other matching IPTV candidate verified")
            return
        self.candidate_plan.extend(selected)
        self._log("AUTO_RESCUE_PLAN", "sat='%s' extra=%d first='%s' mode=background" % (
            self.current_sat_name, len(selected), selected[0][0].get("name","")))
        # The failed pinned source was marked once when rescue began.
        # Reuse native candidate release timer and video verification.
        original["_schedule_next_candidate"](self, pending["reason"], mark_failure=False)

    @functools.wraps(original["_schedule_next_candidate"])
    def next_candidate(self, reason, mark_failure=True):
        if (not _enabled(self) or
                self.last_match_source != "MANUAL_LOCK" or
                self.candidate_index + 1 < len(self.candidate_plan) or
                getattr(self, "_r70_rc7_pending", None) or
                getattr(self, "_r70_rc7_attempted_ref", "") == self.current_sat_ref_string):
            return original["_schedule_next_candidate"](self, reason, mark_failure)

        try:
            # Only called after actual player failure. This must not cause
            # catalogue I/O or score computation on the GUI thread.
            catalog = self.catalog
            if catalog is None or not catalog.channels:
                return original["_schedule_next_candidate"](self, reason, mark_failure)
            sat_ref = str(self.current_sat_ref_string or "")
            if not sat_ref:
                return original["_schedule_next_candidate"](self, reason, mark_failure)
            current = self.pending_match or self.last_match
            if current and mark_failure:
                fp = fingerprint(current)
                if fp:
                    self.failed_candidate_ids.add(fp)
                self._record_health(current, False, reason=reason)
            self._r70_rc7_attempted_ref = sat_ref
            self._r70_rc7_token = int(getattr(self, "_r70_rc7_token", 0)) + 1
            token = self._r70_rc7_token
            info = dict(
                sat_ref=sat_ref, token=token, reason=str(reason),
                started=time.monotonic())
            name = str(self.current_match_name or self.current_sat_name or "")
            languages = list(self._user_languages() or [])
            context = dict(self.sat_context or {})
            quality = str(getattr(self.cfg.quality_mode, "value", "best"))
            self._r70_rc7_result = None
            self._r70_rc7_pending = info
            timer = getattr(self, "_r70_rc7_timer", None)
            if timer is None:
                timer = eTimer()
                timer.callback.append(lambda: poll(self))
                self._r70_rc7_timer = timer
            def work():
                try:
                    matches = catalog.fast_rank_matches_all_servers(
                        name, languages, context=context, topn=36,
                        per_server=12, quality_mode=quality) or []
                    error = ""
                except Exception as exc:
                    matches = []
                    error = exc.__class__.__name__
                # Only transfer result; Enigma2/UI calls stay on mainloop.
                if self._r70_rc7_token == token:
                    self._r70_rc7_result = (matches, error)
            th = threading.Thread(target=work, name="IPToSatAutoRescue")
            th.daemon = True
            self._r70_rc7_worker = th
            th.start()
            self._set_state("AUTO_RESCUE", "Pinned IPTV failed; finding same-channel alternatives",
                            "background ranking")
            self._log("AUTO_RESCUE_START", "sat='%s' pinned='%s' reason=%s" % (
                self.current_sat_name,
                (current or {}).get("name",""), str(reason)[:70]))
            timer.start(90, True)
            return True
        except Exception as exc:
            self._log("AUTO_RESCUE_SETUP_ERR", exc.__class__.__name__)
            cancel(self)
            return original["_schedule_next_candidate"](self, reason, mark_failure)

    @functools.wraps(original["_stop_probe_timers"])
    def stop_probe(self):
        cancel(self)
        # A fresh Enigma2 evStart means a new zap is eligible for one
        # recovery search, even when the user returns to the same SAT.
        self._r70_rc7_attempted_ref = ""
        return original["_stop_probe_timers"](self)

    @functools.wraps(original["_stop_all_timers"])
    def stop_all(self):
        cancel(self)
        return original["_stop_all_timers"](self)

    cls._schedule_next_candidate = next_candidate
    cls._build_candidate_plan = plan
    cls._stop_probe_timers = stop_probe
    cls._stop_all_timers = stop_all
    cls._r70_rc7_attached = True
    return cls


def attach_plugin(ns):
    """Expose user opt-out; enabled only for exhausted mappings and exact REVIEW."""
    cfg = ns.get("cfg")
    ConfigYesNo = ns.get("ConfigYesNo")
    if cfg is None or ConfigYesNo is None:
        return False
    if getattr(cfg, "auto_recover_failed_mapping", None) is None:
        cfg.auto_recover_failed_mapping = ConfigYesNo(default=True)
    settings = ns.get("SatIPTVBridgeSettings")
    entry = ns.get("getConfigListEntry")
    if settings is not None and callable(entry):
        old = settings._build_list
        @functools.wraps(old)
        def build(self):
            r = old(self)
            if getattr(self, "section", "") in ("quick", "all"):
                try:
                    title = "Auto-recover failed IPTV mapping (same channel)"
                    rows = list(self.list)
                    if not any(str(x[0]) == title for x in rows):
                        rows.append(entry(title, cfg.auto_recover_failed_mapping))
                        self.list = rows
                        self["config"].setList(rows)
                except Exception:
                    pass
            return r
        settings._build_list = build
    return True
