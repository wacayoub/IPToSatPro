"""rc5: on failed Auto-player only, try one alternate ServiceApp decoder.

This adapter never probes a second mode on successful playback, does not
change manual user-forced player modes, preserves TOD-sensitive audio routing,
and never changes locked SAT/IPTV mappings or candidate identity.
"""
import functools


def attach_recovery(monitor_class):
    if getattr(monitor_class, "_r70_rc5_alt_attached", False):
        return monitor_class
    old_plan = getattr(monitor_class, "_playback_plan", None)
    if not callable(old_plan):
        return monitor_class

    @functools.wraps(old_plan)
    def playback_plan(self):
        base = list(old_plan(self) or [])
        if len(base) != 1 or base[0] not in ("5002", "4097"):
            return base
        # 'dvb' is intentionally excluded. Native-TS retries are already
        # handled by the original player engine and must keep timeshift.
        try:
            if str(self.cfg.service_type.value) != "auto":
                return base
            if str(self._current_player_override()) != "auto":
                return base
            if not bool(self.cfg.retry_failed_stream.value):
                return base
            ch = self.pending_match or self.last_match or {}
            if self._audio_safe_serviceapp_required(ch):
                # TOD Event and known silent native video stay on their
                # established audio-safe route. Do not force a silent stream.
                return base
            if base[0] == "5002":
                other = "4097"
            elif bool(getattr(self, "serviceapp_5002_available", False)):
                other = "5002"
            else:
                return base
            return [base[0], other]
        except Exception:
            # Fail closed: leave the original player policy untouched.
            return base

    monitor_class._playback_plan = playback_plan
    monitor_class._r70_rc5_alt_attached = True
    return monitor_class
