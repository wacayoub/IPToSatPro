"""r70-rc3: explicit opt-in FTA *no signal* rescue; never change encrypted rules.

No synchronous service switch, no tuner manipulation, no network scan.
Native OpenATV PAT safety and existing playback engine remain authoritative.
"""
import functools
import time

try:
    from .no_signal_policy import decide_fta_fallback, should_bypass_instant_manual_lock
except ImportError:
    from no_signal_policy import decide_fta_fallback, should_bypass_instant_manual_lock


def _enabled(monitor):
    try:
        return bool(monitor.cfg.fta_no_signal.value)
    except (AttributeError, TypeError):
        return False


def _access(monitor):
    """Per-SAT-service access cache; avoids repeating lamedb/overrides I/O on zap."""
    key = (getattr(monitor, "current_sat_ref_string", ""),
           getattr(monitor, "current_sat_started_at", 0),
           getattr(monitor, "direct_mapping_source", ""))
    cached = getattr(monitor, "_r70_fta_access_cached", None)
    if cached and cached[0] == key:
        return cached[1]
    access = None
    # Strong positive live CA evidence is the cheapest encrypted fast path.
    try:
        if monitor._is_crypted() is True:
            access = True
    except Exception:
        pass
    if access is not True:
        static = None
        saved = None
        try: static = monitor._static_crypted_state_fast()
        except Exception: pass
        if static is True:
            access = True
        else:
            try: saved = monitor._manual_lock_saved_access()
            except Exception: pass
            if saved is True:
                access = True
            elif saved is False or static is False:
                access = False
    monitor._r70_fta_access_cached = (key, access)
    return access


def _policy(monitor, explicit=False):
    try:
        if not monitor._same_sat_still_playing():
            return False, "SERVICE_CHANGED"
        tuner = str(monitor._sat_tuner_state() or "?").upper()
        old_state = str(getattr(monitor, "tuner_state", "?") or "?").upper()
        # The native deferred evTuneFailed marks TUNE_FAILED; prioritize
        # the *live* LOCKED state if the tuner recovered during the PAT timer.
        if tuner in ("LOCKED", "TUNING", "ACQUIRING", "SEARCHING"):
            state = tuner
        elif tuner in ("?", "UNKNOWN", "") and old_state in ("TUNE_FAILED", "FAILED", "LOST_LOCK"):
            state = old_state
        else:
            state = tuner
        video = bool(getattr(monitor, "video_event_seen", False))
        pts = monitor._read_pts() is not None
        # Decoder dimension nodes can remain stale on the Vu+ after the last
        # service: use video event or PTS as reliable evidence, not just W/H.
        elapsed = time.time() - float(getattr(monitor, "current_sat_started_at", 0) or 0)
        known_event = bool(explicit or
                           (getattr(monitor, "_r70_fta_event_ref", "") ==
                            getattr(monitor, "current_sat_ref_string", "") and
                            elapsed < 90))
        return decide_fta_fallback(
            enabled=_enabled(monitor),
            clear_no_signal_opt_in=_enabled(monitor),
            sat_fallback_enabled=bool(monitor.cfg.fallback_no_signal.value),
            is_dvb=True,
            current_service_unchanged=True,
            satellite_access=_access(monitor),
            tuner_state=state,
            verified_decoder_video=video,
            video_pts_present=pts,
            video_resolution_present=False,
            time_since_sat_start_s=elapsed,
            explicit_tune_failure=known_event,
        )
    except Exception:
        return False, "FTA_GUARD_EXCEPTION"


def attach_monitor(monitor_cls):
    if getattr(monitor_cls, "_r70_fta_hooked", False):
        return monitor_cls
    old_fast = getattr(monitor_cls, "_instant_mapped_enabled", None)
    old_gate = getattr(monitor_cls, "_encrypted_fallback_allowed_once", None)
    old_tune = getattr(monitor_cls, "_on_tune_failed", None)
    old_fallback = getattr(monitor_cls, "_fallback_if_matched", None)
    if not all(callable(x) for x in (old_fast, old_gate, old_tune, old_fallback)):
        return monitor_cls

    @functools.wraps(old_fast)
    def fast(self):
        if _enabled(self):
            access = _access(self)
            if should_bypass_instant_manual_lock(
                    feature_enabled=True, confirmed_fta=(access is False)):
                return False
        return old_fast(self)

    @functools.wraps(old_tune)
    def tune_failed(self, event=None):
        if _enabled(self):
            try:
                ref = self.session.nav.getCurrentlyPlayingServiceReference()
                raw = ref.toString() if self._ref_valid(ref) else ""
                if raw:
                    self._r70_fta_event_ref = raw
            except Exception:
                pass
        return old_tune(self, event)

    @functools.wraps(old_gate)
    def crypto_gate(self):
        # Existing r69 encryption gate MUST win. It retains fast crypted
        # handling and the manual-lock stale CAID exception.
        if old_gate(self):
            return True
        if not _enabled(self):
            return False
        allowed, reason = _policy(self)
        if allowed:
            try:
                self._log("FTA_NO_SIGNAL_ALLOW", "confirmed FTA no-lock; SAT PAT guard stays active")
            except Exception:
                pass
            return True
        # A tune-fail callback may arrive <650ms after SAT start. Revisit
        # once, from the existing Enigma2 timer (not the DVB callback).
        if reason == "TUNER_GRACE_PERIOD" and not getattr(self, "_r70_fta_wait_armed", False):
            try:
                self._r70_fta_wait_armed = True
                self.timer.start(850, True)
            except Exception:
                pass
        return False

    @functools.wraps(old_fallback)
    def final_match(self):
        # Reconfirm FTA tuner lock after OpenATV PAT/PMT safety wait.
        # If signal recovered, leave SAT alone even after the prior failure.
        if _enabled(self) and _access(self) is False:
            allowed, reason = _policy(self)
            if not allowed:
                try: self._log("FTA_NO_SIGNAL_CANCEL", "reason=%s" % reason)
                except Exception: pass
                return
        return old_fallback(self)

    monitor_cls._instant_mapped_enabled = fast
    monitor_cls._on_tune_failed = tune_failed
    monitor_cls._encrypted_fallback_allowed_once = crypto_gate
    monitor_cls._fallback_if_matched = final_match
    monitor_cls._r70_fta_hooked = True
    return monitor_cls


def attach_plugin(namespace):
    """Expose an opt-in Settings control and full TV SAT roster in Preview."""
    if namespace.get("_r70_fta_plugin_hooked"):
        return True
    cfg = namespace.get("cfg")
    choice = namespace.get("ConfigYesNo")
    entry = namespace.get("getConfigListEntry")
    settings_cls = namespace.get("SatIPTVBridgeSettings")
    roster = namespace.get("_preview_sat_service_rows")
    tv_rows = namespace.get("_lamedb_tv_service_rows")
    if cfg is None or not callable(choice) or not callable(entry) or settings_cls is None:
        return False
    if not callable(roster) or not callable(tv_rows):
        return False

    if getattr(cfg, "fta_no_signal", None) is None:
        cfg.fta_no_signal = choice(default=False)

    original_build = settings_cls._build_list

    @functools.wraps(original_build)
    def build_settings(self):
        result = original_build(self)
        if self.section in ("quick", "all"):
            try:
                rows = list(self.list)
                label = "FTA rescue only when SAT has no signal"
                if not any(row[0] == label for row in rows):
                    i = next((i for i, row in enumerate(rows)
                              if row[0] == "Fallback when SAT has no signal"), -1)
                    rows.insert(max(0, i+1), entry(label, cfg.fta_no_signal))
                    self.list = rows
                    self["config"].setList(rows)
            except Exception:
                pass
        return result

    settings_cls._build_list = build_settings
    try:
        settings_cls.HELP["FTA rescue only when SAT has no signal"] = (
            "Off (default): encrypted-only. On: when the satellite has definitively "
            "no lock, allow IPTV for confirmed clear TV channels too. SAT with "
            "normal signal is never replaced; original PAT/tuner safety applies.")
    except Exception:
        pass

    @functools.wraps(roster)
    def all_tv_when_opted_in(session, current_sat_ref_string):
        original = roster(session, current_sat_ref_string)
        try:
            if not bool(cfg.fta_no_signal.value):
                return original
            orbital = namespace["_sat_orbital_position"](current_sat_ref_string)
            catalog = tv_rows()
            # The TV-only lamedb index already excludes radio/data. Include
            # confirmed FTA only; unknown crypted state is not assumed FTA.
            rows = [dict(row or {}) for row in original]
            ids = {namespace["_dvb_service_key"](row.get("ref")) for row in rows}
            access_states = namespace.get("_lamedb_access_states")
            static_access = access_states() if callable(access_states) else {}
            for entry_row in catalog:
                if orbital is not None and entry_row.get("orbital_position") != orbital:
                    continue
                key = namespace["_dvb_service_key"](entry_row.get("ref"))
                if not key or key in ids:
                    continue
                ids.add(key)
                row = dict(entry_row)
                if row.get("crypted") is not True and key in static_access:
                    # FTA from lamedb is provisional, never enough alone to
                    # authorize playback switching without the runtime gate.
                    row["crypted"] = bool(static_access[key])
                rows.append(row)
            rows.sort(key=lambda row: str(row.get("name") or "").casefold())
            return rows
        except Exception:
            return original

    namespace["_preview_sat_service_rows"] = all_tv_when_opted_in
    preview_cls = namespace.get("SatIPTVBridgePreview")
    if preview_cls is not None:
        old_ensure = preview_cls._ensure_full_sat_rows

        @functools.wraps(old_ensure)
        def full_sat(self):
            result = old_ensure(self)
            if result:
                try:
                    if cfg.fta_no_signal.value:
                        self["detail"].setText(
                            "SAT TV: cryptées + FTA • l'IPTV FTA intervient uniquement sans signal")
                except Exception:
                    pass
            return result
        preview_cls._ensure_full_sat_rows = full_sat
    namespace["_r70_fta_plugin_hooked"] = True
    return True
