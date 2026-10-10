"""r70-rc6: targeted TOD Event audio-safe player recovery.

Preview Browser already tests the same URL through both 5002 and 4097.
Automatic manual-lock playback previously forced 5002 alone for TOD Events:
a failed first decoder entered 12s cooldown without trying the alternative.

No changes to SAT, mappings, stream URL, timeshift, successful non-TOD streams,
decoder PID, audio tracks or native player selection.
"""
import functools
import re
import time


def tod_event(channel):
    try:
        fields = ("name", "group", "source", "server_label")
        name = " ".join(str((channel or {}).get(k) or "") for k in fields).casefold()
    except (TypeError, AttributeError):
        return False
    # Includes "TOD EVENT SPORTS 7 FHD" and "TOD EVENT 1 4K HDR".
    # Do not generalize to unrelated "EVENT" or another broadcaster's sports.
    return bool(re.search(r"\btod\b", name) and re.search(r"\bevents?\b", name))


def _candidate(monitor):
    try:
        obj = monitor.pending_match or monitor.last_match
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _verified_preference(monitor, channel, options):
    """One exact-fingerprint preference, never learned from TS-ready alone."""
    try:
        from .core import channel_fingerprint
    except ImportError:
        try:
            from Plugins.Extensions.SatIPTVBridge.core import channel_fingerprint
        except ImportError:
            return ""
    try:
        rec = dict((monitor.stream_health or {}).get(channel_fingerprint(channel)) or {})
        now = time.time()
        preferred = str(rec.get("preferred_mode") or "")
        verified_at = float(rec.get("preferred_mode_verified_at") or 0)
        failed_at = float(rec.get("last_failed_player_at") or 0)
        if (preferred in options and verified_at > 0 and
                0 <= now-verified_at <= 86400 and verified_at >= failed_at):
            return preferred
        # A recent 5002 failure may prioritize 4097 during the next visit
        # without assuming 4097 has been verified. The second mode remains.
        last_failed = str(rec.get("last_failed_player") or "")
        if last_failed == "5002" and "4097" in options and (
                0 <= now-failed_at <= 900):
            return "4097"
    except Exception:
        pass
    return ""


def attach_tod_audio(monitor_cls):
    if getattr(monitor_cls, "_r70_rc6_tod_hooked", False):
        return monitor_cls
    original_plan = getattr(monitor_cls, "_playback_plan", None)
    original_sensitive = getattr(monitor_cls, "_audio_sensitive_stream", None)
    if not callable(original_plan) or not callable(original_sensitive):
        return monitor_cls

    @functools.wraps(original_sensitive)
    def sensitive(channel):
        return tod_event(channel) or bool(original_sensitive(channel))

    @functools.wraps(original_plan)
    def plan(self):
        base = list(original_plan(self) or [])
        ch = _candidate(self)
        if not ch or not tod_event(ch):
            return base

        # Never override explicit player settings, manual per-SAT player
        # overrides, or disabled retry. The existing audio-safe player and
        # native-timeshift decisions remain the source of truth.
        try:
            if (str(self.cfg.service_type.value) != "auto" or
                    str(self._current_player_override()) != "auto" or
                    not bool(self.cfg.retry_failed_stream.value)):
                return base
        except Exception:
            return base

        if not base or base[0] == "dvb":
            return base
        if len(base) >= 2:
            # The existing runtime already has its own verified fallback.
            return base

        first = str(base[0])
        if first not in ("5002", "5001", "4097"):
            return base
        options = [first]
        if first == "5002":
            options.append("4097")
        elif first == "5001":
            options.append("4097")
        elif bool(getattr(self, "serviceapp_5002_available", False)):
            options.append("5002")
        if len(options) < 2:
            return base
        preferred = _verified_preference(self, ch, options)
        if preferred and preferred != options[0]:
            options = [preferred] + [mode for mode in options if mode != preferred]
        try:
            if tuple(options) != tuple(base):
                self._log("TOD_PLAYER_PLAN",
                          "mode=%s alternate=%s reason=TOD_EVENT_AUDIO_SAFE" %
                          (options[0], options[1]))
        except Exception:
            pass
        return options

    monitor_cls._audio_sensitive_stream = staticmethod(sensitive)
    monitor_cls._playback_plan = plan
    monitor_cls._r70_rc6_tod_hooked = True
    return monitor_cls
