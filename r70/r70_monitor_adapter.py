"""Opt-in, non-invasive r70 monitor adapter for the existing Enigma2 engine.

The r69 playback plan, failover timers, locked fast path and media stack are
not replaced. Missing APIs safely disable individual observations.
"""
import functools
import os
import time

try:
    from .r70_safety_core import PlaybackGuard, CandidateHistory, RecoveryPolicy, _token
except ImportError:
    try:
        from Plugins.Extensions.SatIPTVBridge.r70_safety_core import (
            PlaybackGuard, CandidateHistory, RecoveryPolicy, _token
        )
    except ImportError:
        from r70_safety_core import PlaybackGuard, CandidateHistory, RecoveryPolicy, _token

try:
    from .core import channel_fingerprint as _native_fingerprint
except ImportError:
    try:
        from Plugins.Extensions.SatIPTVBridge.core import channel_fingerprint as _native_fingerprint
    except ImportError:
        _native_fingerprint = None

_STATE_DIR = "/etc/enigma2/SatIPTVBridge"


def _identity(candidate):
    if isinstance(candidate, dict):
        # Use exact stream identifiers where available. IDs are always hashed
        # before they enter the persisted history.
        return (candidate.get("url") or candidate.get("stream_url") or
                candidate.get("id") or candidate.get("name") or "")
    return str(candidate or "")


def _source(candidate):
    if isinstance(candidate, dict):
        return (candidate.get("source_id") or candidate.get("server") or
                candidate.get("provider") or "")
    return ""


def _ensure(monitor):
    if getattr(monitor, "_r70_playback", None) is None:
        monitor._r70_playback = PlaybackGuard()
        monitor._r70_history = CandidateHistory(os.path.join(_STATE_DIR, "r70-history.json"))
        monitor._r70_policy = RecoveryPolicy()
        monitor._r70_generation = 0
        monitor._r70_observed = set()
        monitor._r70_last_warning = ""
    return monitor._r70_playback


def _later(monitor):
    """Batch writes via eTimer, never do JSON I/O on every zap."""
    if getattr(monitor, "_r70_flush_scheduled", False):
        return
    try:
        from enigma import eTimer
        timer = getattr(monitor, "_r70_flush_timer", None)
        if timer is None:
            timer = eTimer()
            def flush():
                monitor._r70_flush_scheduled = False
                try:
                    monitor._r70_history.flush()
                except (OSError, ValueError):
                    pass
            timer.callback.append(flush)
            monitor._r70_flush_timer = timer
        monitor._r70_flush_scheduled = True
        timer.start(15000, True)
    except Exception:
        # Never trade zap stability for optional diagnostics.
        monitor._r70_flush_scheduled = False


def _watch_for_no_video(monitor, generation):
    try:
        from enigma import eTimer
        timer = getattr(monitor, "_r70_watch_timer", None)
        if timer is None:
            timer = eTimer()
            def inspect():
                try:
                    g = getattr(monitor, "_r70_watch_generation", -1)
                    guard = getattr(monitor, "_r70_playback", None)
                    if guard and guard.no_frame_due(g, wait_s=2.5):
                        # Advisory only: do not force a decoder restart or block GUI.
                        monitor._r70_last_warning = "NO_DECODED_VIDEO_OBSERVATION"
                except Exception:
                    pass
            timer.callback.append(inspect)
            monitor._r70_watch_timer = timer
        monitor._r70_watch_generation = generation
        timer.start(2700, True)
    except Exception:
        pass


def attach_monitor(monitor_class):
    """Attach bounded telemetry without modifying the established player plan."""
    if getattr(monitor_class, "_r70_adapter_attached", False):
        return monitor_class
    play_match = getattr(monitor_class, "_play_match", None)
    late = getattr(monitor_class, "_post_success_quality_update", None)
    fail = getattr(monitor_class, "_handle_iptv_failure", None)
    if not all(callable(x) for x in (play_match, late, fail)):
        # Refuse a partial monkeypatch on incompatible OpenATV/monitor layout.
        return monitor_class

    @functools.wraps(play_match)
    def wrapped_play(self, *args, **kwargs):
        # Purely passive tracking of the active attempt.
        guard = _ensure(self)
        candidate = kwargs.get("candidate") or kwargs.get("match")
        if candidate is None and args:
            candidate = args[0]
        if candidate is None:
            candidate = getattr(self, "pending_match", None) or getattr(self, "last_match", None)
        service = (getattr(self, "sat_ref_string", None) or
                   getattr(self, "sat_ref", None) or _identity(candidate))
        try:
            self._r70_candidate_id = _identity(candidate)
            self._r70_source_id = _source(candidate)
            self._r70_generation = guard.begin(self._r70_candidate_id, service)
            self._r70_last_warning = ""
            _watch_for_no_video(self, self._r70_generation)
        except Exception:
            pass
        return play_match(self, *args, **kwargs)

    @functools.wraps(late)
    def wrapped_late(self, candidate, width, height, *args, **kwargs):
        result = late(self, candidate, width, height, *args, **kwargs)
        # r69 returns False even AFTER decoder verification when it has
        # accepted a real below-target quality (e.g. FHD for requested UHD).
        # Its verified signature is written only after the active service,
        # channel fingerprint and stale decoder guards pass. Match the exact
        # playback attempt before counting evidence or clearing no-video.
        confirmed = bool(result)
        try:
            if _native_fingerprint is not None:
                sig = getattr(self, "_late_quality_signature", None)
                expected = (
                    _native_fingerprint(candidate),
                    str(getattr(self, "current_play_mode", "")),
                    float(getattr(self, "current_candidate_started_at", 0) or 0),
                    (int(width), int(height)),
                    str(kwargs.get("hdr", args[0] if args else "") or ""),
                )
                confirmed = bool(confirmed or (sig == expected))
        except Exception:
            pass
        if confirmed:
            try:
                guard = _ensure(self)
                gen = self._r70_generation
                if _token(_identity(candidate)) == _token(self._r70_candidate_id):
                    guard.connected(gen)
                    if guard.decoded_frame(gen, int(width), int(height)):
                        key = (gen, _token(_identity(candidate)))
                        if key not in self._r70_observed:
                            self._r70_observed.add(key)
                            if len(self._r70_observed) > 32:
                                self._r70_observed = {key}
                            first_ms = guard.snapshot().get("time_to_first_frame_ms")
                            self._r70_history.record(
                                self._r70_candidate_id, True,
                                str(getattr(self, "current_play_mode", "")),
                                first_ms, self._r70_source_id
                            )
                            _later(self)
            except Exception:
                pass
        return result

    @functools.wraps(fail)
    def wrapped_fail(self, *args, **kwargs):
        try:
            guard = _ensure(self)
            guard.mark_failure(self._r70_generation, "player_failed")
            cid = getattr(self, "_r70_candidate_id", "")
            if cid:
                self._r70_history.record(
                    cid, False, source_id=getattr(self, "_r70_source_id", "")
                )
                _later(self)
        except Exception:
            pass
        return fail(self, *args, **kwargs)

    monitor_class._play_match = wrapped_play
    monitor_class._post_success_quality_update = wrapped_late
    monitor_class._handle_iptv_failure = wrapped_fail
    monitor_class._r70_adapter_attached = True
    return monitor_class
