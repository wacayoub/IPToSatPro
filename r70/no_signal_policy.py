"""Pure policy for optional FTA no-signal IPTV fallback (r70-rc3 PREPARATION ONLY).

This module performs no Enigma2 calls, timer scheduling, playback or disk I/O.
Only true no-signal can qualify, never a scrambled/decrypt failure or a
still-locked tuner displaying a black image. Default flag is OFF.
"""

CONFIRMED_NO_LOCK = frozenset((
    "FAILED", "TUNE_FAILED", "LOST_LOCK", "NO_LOCK",
    "NO_SIGNAL", "UNLOCKED",
))
TRANSIENT = frozenset(("TUNING", "ACQUIRING", "SEARCHING", "LOCKING"))


def decide_fta_fallback(
    *,
    enabled=False,
    clear_no_signal_opt_in=False,
    sat_fallback_enabled=True,
    is_dvb=True,
    current_service_unchanged=True,
    satellite_access=None,
    tuner_state="?",
    verified_decoder_video=False,
    video_pts_present=False,
    video_resolution_present=False,
    time_since_sat_start_s=0.0,
    explicit_tune_failure=False,
):
    """Return (allow, reason) with safe fail-closed default.

    satellite_access: False = confirmed FTA, True = encrypted, None = unknown.
    Only FTA is handled here; existing encrypted engine remains authoritative.
    Explicit evTuneFailed may mean no PAT on a LOCKED tuner; it is never enough
    by itself unless the tuner is confirmed not locked and no video exists.
    """
    if not enabled or not clear_no_signal_opt_in:
        return False, "FEATURE_DISABLED"
    if not sat_fallback_enabled or not is_dvb or not current_service_unchanged:
        return False, "INVALID_FALLBACK_CONTEXT"
    if satellite_access is not False:
        return False, "NOT_CONFIRMED_FTA"
    state = str(tuner_state or "?").upper()
    if state == "LOCKED":
        return False, "SAT_LOCKED"
    if state in TRANSIENT:
        return False, "TUNER_TRANSITION"
    if verified_decoder_video or video_pts_present or video_resolution_present:
        return False, "SAT_VIDEO_PRESENT"
    try:
        elapsed = float(time_since_sat_start_s)
    except (TypeError, ValueError):
        return False, "INVALID_TIME"
    if elapsed < 0 or elapsed > 300:
        return False, "INVALID_TIME"
    if state in CONFIRMED_NO_LOCK:
        if elapsed < 0.65:
            return False, "TUNER_GRACE_PERIOD"
        return True, "FTA_NO_SIGNAL_CONFIRMED"
    # Unknown frontend information alone cannot prove no signal. An explicit
    # native tuner failure PLUS a grace period can serve as corroboration.
    if state in ("?", "UNKNOWN", "") and explicit_tune_failure:
        if elapsed < 1.2:
            return False, "TUNER_GRACE_PERIOD"
        return True, "FTA_TUNE_FAILURE_CONFIRMED"
    return False, "NO_RELIABLE_SIGNAL_EVIDENCE"


def should_bypass_instant_manual_lock(
    *, feature_enabled=False, confirmed_fta=False
):
    """Only clear SAT services require a full no-signal gate before IPTV.

    Existing encrypted manual locks retain r69/r70 45ms instant route.
    """
    return bool(feature_enabled and confirmed_fta)
