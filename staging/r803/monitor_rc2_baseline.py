# -*- coding: utf-8 -*-
from __future__ import absolute_import

import json
import os
import re
import time
import threading
from collections import deque
from urllib.parse import unquote, quote
from urllib.request import urlopen

from enigma import eServiceReference, eServiceCenter, eTimer, iPlayableService, iServiceInformation
try:
    from enigma import eEPGCache
except Exception:
    eEPGCache = None
from ServiceReference import ServiceReference

from . import metadata_shadow as sat_shadow

from .core import (
    Catalog,
    build_stream_ref,
    canonical_sat_name,
    channel_fingerprint,
    effective_quality_info,
    quality_info,
    effective_hdr_info,
    hdr_info,
    infer_sat_context,
    match_decision,
    match_score_details,
    normalize_name,
    quality_from_dimensions,
    redact_url,
    sat_required_quality,
    sat_service_key,
    explicit_language_tag,
    normalize_audio_languages,
    auto_lock_100_match,
)


class SatFallbackMonitor(object):
    """SAT -> IPTV state machine with provider/orbital/bouquet-aware SmartMatch, no-signal fallback and stream watchdog."""

    LOG_MAX_BYTES = 512 * 1024
    VERIFY_STEP_MS = 700
    RETRY_RELEASE_MS = 850
    START_GUARD_MS = 1800
    # Fast mode polls aggressively but does NOT fail a stream after two polls.
    # Beta9 used a hard 0.8s watchdog and could reject a perfectly valid Xtream
    # stream before the first decoded frame arrived on Vu+ / GStreamer / ServiceApp.
    FAST_VERIFY_STEP_MS = 60
    NORMAL_VERIFY_STEP_MS = 350
    FAST_VIDEO_TIMEOUT_MS = 1700
    # Fast-zap watchdog ceilings. These are failure deadlines, not fixed waits: a real first
    # frame is still accepted immediately by the 60ms verifier, with a hard 2s ceiling for
    # normal, FHD and UHD streams.
    FAST_FHD_VIDEO_TIMEOUT_MS = 2400
    FAST_UHD_VIDEO_TIMEOUT_MS = 3600
    NORMAL_VIDEO_TIMEOUT_MS = 5000
    # Resolution is verified after the first decoded frame, but we keep this grace bounded
    # so a good stream is not held for seconds waiting for a late size notification.
    FAST_RESOLUTION_TIMEOUT_MS = 850
    NORMAL_RESOLUTION_TIMEOUT_MS = 1600
    FAST_RETRY_RELEASE_MS = 80
    FAST_FHD_RETRY_RELEASE_MS = 120
    FAST_UHD_RETRY_RELEASE_MS = 180
    FAST_START_GUARD_MS = 900
    FAST_FHD_START_GUARD_MS = 1900
    FAST_UHD_START_GUARD_MS = 3000
    FAST_START_GUARD_POLL_MS = 35
    FAST_SAT_DELAY_MS = 320
    FAST_MAPPED_DELAY_MS = 20
    # r61 FAST LOCK: explicit manual locks are exact user choices. Warm the local TS hub
    # while the OpenATV PAT/PMT safety window is still running, then use a lower-latency
    # startup reserve. Network setup overlaps DVB safety instead of adding to it.
    FAST_LOCK_PREWARM_TIMEOUT_S = 1.45
    FAST_LOCK_NATIVE_TIMEOUT_MS = 1150
    FAST_LOCK_UHD_NATIVE_TIMEOUT_MS = 1450
    FAST_LOCK_SERVICEAPP_TIMEOUT_MS = 1950
    # OpenATV 7.6 native PMT crash guard. pmt.cpp arms a 1000ms no-PAT timer and
    # sendEventNoPatEntry() dereferences m_channel. Keep a DVB service alive slightly
    # beyond that timer only when PMT is still unknown; normal services stay fast.
    NATIVE_PAT_GUARD_MS = 1250
    # Poll PMT readiness during the safety window instead of sleeping until its end.  This
    # preserves the OpenATV 7.6 crash guard while releasing mapped channels as soon as DVB
    # has a valid PMT.  The old one-shot guard could waste nearly the full 1.25 s window.
    NATIVE_PAT_GUARD_POLL_MS = 30
    # OpenATV servicedvb.cpp emits evTuneFailed synchronously from eventNoPATEntry.
    # Never call playService() from inside that callback: pmt.cpp continues afterwards and
    # dereferences m_channel. Defer fallback to a later mainloop turn to avoid freeing it
    # re-entrantly (native sendEventNoPatEntry crash).
    TUNE_FAIL_DEFER_MS = 90
    NEIGHBOR_PREP_DELAY_MS = 420
    # Keep all persistence outside the first seconds after a successful zap. Re-arm on each
    # update so continuous zapping never triggers a large JSON write in the GUI hot path.
    DEFERRED_STATE_SAVE_MS = 20000
    TUNER_RECHECK_MS = 250
    TUNER_MAX_RECHECKS = 2
    FAILURE_COOLDOWN_S = 12
    HEALTH_COOLDOWN_S = 300
    HEALTH_MAX_ENTRIES = 1200
    # Never trust a receiver-observed IPTV resolution forever. Xtream providers can silently
    # replace a stream while keeping the same stream id/name. Old dimensions are ranking hints
    # only for a short period and are always re-verified on playback.
    QUALITY_OBSERVATION_TTL_S = 12 * 3600
    FRESH_SIZE_MIN_MS = 260
    FRESH_SIZE_SAME_AS_PREVIOUS_MS = 650
    # ServiceApp/ExtEplayer3 does not always emit evVideoSizeChanged and some images do not
    # expose the hardware PTS node for every HEVC path.  A stable decoder size that differs
    # from the outgoing SAT service is therefore accepted as independent first-frame evidence.
    RAW_SIZE_EVIDENCE_MIN_MS = 220
    RAW_SIZE_EVIDENCE_SAMPLES = 2
    RESOLUTION_FOLLOWUP_FIRST_MS = 180
    RESOLUTION_FOLLOWUP_STEP_MS = 150
    RESOLUTION_FOLLOWUP_MAX_ROUNDS = 7
    # r57 audio-safe fallback: native type-1 TS can decode video while exposing zero audio
    # tracks when the upstream IPTV service/program identity differs from the SAT identity.
    # Poll only after video is already verified; five zero-track samples trigger one direct
    # ServiceApp retry of the SAME source.
    AUDIO_GUARD_FIRST_MS = 300
    AUDIO_GUARD_STEP_MS = 260
    AUDIO_GUARD_MAX_ZERO_SAMPLES = 5
    MAX_CANDIDATE_PLAN = 8
    CACHE_LOAD_DELAY_MS = 1500
    CACHE_TICK_MS = 45
    CACHE_TICK_BUDGET_S = 0.008
    CACHE_MAX_LINES_PER_TICK = 320
    CACHE_SWAP_TICK_MS = 25
    CACHE_SWAP_TICK_BUDGET_S = 0.006
    CACHE_SWAP_MAX_LINES_PER_TICK = 240
    # Never unpickle a huge 50k-100k channel snapshot in Enigma2 GUI thread. Small snapshots
    # are still fast; large ones use sliced JSONL (kept current by 1.0.45 importer).
    CACHE_SNAPSHOT_GUI_MAX_BYTES = 6 * 1024 * 1024
    # r15 Frozen Catalog: a validated pre-indexed catalogue is loaded exactly once at boot.
    # It is deliberately allowed to be larger than the normal runtime swap fence because
    # repeatedly rebuilding JSONL or swapping PRIMARY -> FULL after boot caused temporary
    # missing-channel windows on the receiver. 96 MB is a hard safety ceiling.
    BOOT_PRIMARY_SNAPSHOT_GUI_MAX_BYTES = 96 * 1024 * 1024
    BOOT_PRIMARY_LOAD_DELAY_MS = 80
    BOOT_FULL_SWAP_DELAY_MS = 900
    # Boot attach: WHERE_SESSIONSTART can run after the receiver has already started the
    # configured TV service, so the monitor may miss that service's evStart.  Reconcile the
    # already-playing DVB service without zapping/restarting it once the fast catalogue is ready.
    STARTUP_RECONCILE_DELAY_MS = 1200
    STARTUP_RECONCILE_RETRY_MS = 700
    STARTUP_RECONCILE_MAX_RETRIES = 40

    def __init__(self, session, cfg, cache_path, log_path, autoload_catalog=True):
        self.session = session
        self.cfg = cfg
        self.cache_path = cache_path
        self.player_override_path = os.path.join(os.path.dirname(cache_path), "player_overrides.json")
        self.playback_locked = False
        self.log_path = log_path
        self.override_path = os.path.join(os.path.dirname(cache_path), "overrides.json")
        self.learned_path = os.path.join(os.path.dirname(cache_path), "resolved_mappings.json")
        self.alias_path = os.path.join(os.path.dirname(cache_path), "manual_aliases.json")
        self.rejected_path = os.path.join(os.path.dirname(cache_path), "rejected_sources.json")
        self.health_path = os.path.join(os.path.dirname(cache_path), "stream_health.json")
        # Beta6 never parses a large JSON catalogue in __init__.  The optimized JSONL cache
        # is loaded in short eTimer slices after the GUI is alive, keeping each slice bounded.
        self.catalog = Catalog([])
        self.cache_jsonl_path = cache_path[:-5] + ".jsonl" if cache_path.endswith(".json") else cache_path + ".jsonl"
        self.cache_meta_path = cache_path[:-5] + ".meta.json" if cache_path.endswith(".json") else cache_path + ".meta.json"
        self.cache_snapshot_path = cache_path[:-5] + ".snapshot" if cache_path.endswith(".json") else cache_path + ".snapshot"
        self.cache_snapshot_override = ""
        self.cache_meta = Catalog.read_meta(self.cache_meta_path)
        self.cache_expected = int(self.cache_meta.get("count") or 0)
        self.cache_loaded = 0
        self.cache_loading = False
        self.cache_file = None
        self.cache_started_at = 0.0
        self.cache_generation = 0
        self.cache_target = None
        self.cache_swap_mode = False
        self.boot_primary_active = False
        self.boot_full_swap_path = ""

        self.timer = eTimer(); self.timer.callback.append(self._evaluate)
        self.probe_timer = eTimer(); self.probe_timer.callback.append(self._evaluate_probe)
        self.verify_timer = eTimer(); self.verify_timer.callback.append(self._verify_iptv)
        self.retry_timer = eTimer(); self.retry_timer.callback.append(self._retry_fallback)
        self.start_guard_timer = eTimer(); self.start_guard_timer.callback.append(self._start_guard)
        self.cache_loader_timer = eTimer(); self.cache_loader_timer.callback.append(self._cache_loader_tick)
        self.health_flush_timer = eTimer(); self.health_flush_timer.callback.append(self._flush_health)
        self.learned_flush_timer = eTimer(); self.learned_flush_timer.callback.append(self._flush_learned_mappings)
        self.log_flush_timer = eTimer(); self.log_flush_timer.callback.append(self._flush_log_buffer)
        self.neighbor_prepare_timer = eTimer(); self.neighbor_prepare_timer.callback.append(self._prepare_neighbor_rankings)
        self.startup_reconcile_timer = eTimer(); self.startup_reconcile_timer.callback.append(self._startup_reconcile)
        self.native_pat_guard_timer = eTimer(); self.native_pat_guard_timer.callback.append(self._native_pat_guard_fire)
        self.tune_fail_defer_timer = eTimer(); self.tune_fail_defer_timer.callback.append(self._deferred_tune_failed_fallback)
        self.resolution_followup_timer = eTimer(); self.resolution_followup_timer.callback.append(self._resolution_followup_tick)
        self.audio_guard_timer = eTimer(); self.audio_guard_timer.callback.append(self._audio_guard_tick)
        # r59: keep expensive live matching away from the Enigma2 GUI/main loop.
        self.smartmatch_timer = eTimer(); self.smartmatch_timer.callback.append(self._smartmatch_poll)

        self._log_ring = deque(maxlen=240)
        self._log_pending = []
        self._log_permissions_ready = False
        self._prime_log_cache()
        self._override_cache = {}
        self._override_mtime = None
        self._learned_cache = {}
        self._learned_mtime = None
        self.learned_dirty = False
        self._alias_cache = {}
        self._alias_mtime = None
        self._rejected_cache = {}
        self._rejected_mtime = None
        self.stream_health = self._load_health()
        self.health_dirty = False
        self.server_mode_stats = self._build_server_mode_stats()
        # ServiceApp/ExtEplayer3 capability is resolved once at monitor startup.  Never probe
        # packages/files in the zap hot path.  Type 5002 is only attempted first when both the
        # ServiceApp integration and exteplayer3 binary are actually present.
        try:
            _serviceapp_installed = bool(
                os.path.isdir("/usr/lib/enigma2/python/Plugins/SystemPlugins/ServiceApp") or
                os.path.isdir("/usr/lib/enigma2/python/Plugins/Extensions/ServiceApp")
            )
            self.serviceapp_5002_available = bool(_serviceapp_installed and os.path.isfile("/usr/bin/exteplayer3"))
            self.serviceapp_5001_available = bool(_serviceapp_installed and os.path.isfile("/usr/bin/gstplayer_gst-1.0"))
        except Exception:
            self.serviceapp_5002_available = False
            self.serviceapp_5001_available = False

        self.current_sat_ref = None
        self.current_sat_name = ""
        self.current_match_name = ""
        self.current_sat_ref_string = ""
        self.sat_provider = "Unknown"
        self.sat_orbital = None
        self.sat_satellite = "Unknown"
        self.sat_context = {}
        self.sat_audio_languages = []
        self.sat_epg_text = ""
        self.sat_epg_events = []
        self.frontend_shadow_ref = ""
        self._lock_prewarm_url = ""
        self._lock_prewarm_at = 0.0
        self.sat_deep_context_ready = False

        self.probe_pts = None
        self.probe_round = 0
        self.video_event_seen = False

        self.fallback_active = False
        self.fallback_attempt = 0
        self.pending_match = None
        self.pending_score = 0.0
        self.pending_details = {}
        # Exact stream ownership marker.  A manual IPTV zap must never be mistaken for the
        # bridge stream merely because fallback_active was still True from the previous SAT.
        self.expected_iptv_ref_string = ""
        self.expected_iptv_url = ""
        self.previous_iptv_ref_string = ""
        self.previous_iptv_url = ""
        self.candidate_plan = []
        self.candidate_index = -1
        self.failed_candidate_ids = set()
        self.target_quality = "AUTO"
        self.target_quality_rank = 0
        self.target_quality_source = "unknown"
        self.target_hdr = ""
        self.sat_video_width = 0
        self.sat_video_height = 0
        # Session-only IPTV resolution. Do not expose/catalog-cache historical dimensions as
        # if they belonged to the stream currently on screen.
        self.current_iptv_width = 0
        self.current_iptv_height = 0
        self.current_iptv_quality = ""
        self.current_iptv_quality_verified = False
        self.pre_switch_video_width = 0
        self.pre_switch_video_height = 0
        self.iptv_size_sample = (0, 0)
        self.iptv_size_sample_count = 0
        self.resolution_followup_round = 0
        self.resolution_followup_fp = ""
        self.audio_guard_round = 0
        self.audio_guard_fp = ""
        self.forced_retry_mode = ""
        self.current_candidate_started_at = 0.0
        self.verify_pts = None
        self.verify_round = 0
        self.verify_started_at = 0.0
        self.verify_deadline = 0.0
        self.resolution_deadline = 0.0
        self.first_video_evidence_at = 0.0
        self.retry_pending = False
        self.retry_kind = ""
        self.switch_in_progress = False
        self.native_pat_guard_pending = False
        self.tune_fail_defer_pending = False
        self.tune_fail_defer_ref = ""
        self.tune_fail_defer_event = None
        self.current_sat_started_at = 0.0
        self.iptv_start_seen = False
        self.iptv_video_event_seen = False
        self.start_guard_deadline = 0.0
        self.bridge_ready_marker = ""
        self.bridge_ready_token = ""
        self.direct_mapping_cache = None
        self.direct_mapping_source = ""
        # Per-session O(1) hot cache for already resolved SAT -> IPTV mappings.  Persistent
        # JSON is still authoritative, but repeated CH+/CH- zaps no longer pay file mtime /
        # learned-score validation on every visit to the same service.
        self.direct_hot_cache = {}
        self.direct_hot_order = deque()
        self.current_play_mode = "-"
        self.player_status = {"4097": "UNKNOWN", "5001": "UNKNOWN", "5002": "UNKNOWN"}
        self.manual_preview_active = False
        # r50 manual-preview ownership. r49 used a bare bool; if a Preview screen was
        # hidden/closed through a nested transition without cleanup, AUTO monitoring stayed
        # paused forever. Track the exact preview ref + restore SAT ref and self-heal safely.
        self.manual_preview_ref = ""
        self.manual_preview_restore_ref = ""
        self.manual_preview_started_at = 0.0
        self.last_first_frame_ms = 0
        self.tuner_wait_round = 0
        self.failure_cooldown_until = 0.0
        self.failure_cooldown_sat = ""

        self.last_match = None
        self.last_score = 0.0
        self.last_details = {}
        self.last_ranked = []
        self.last_match_source = "-"
        self.last_error = ""
        self.prefetched_ranked = []
        self.prefetched_match_name = ""
        self.smartmatch_generation = 0
        self.smartmatch_pending = None
        self.smartmatch_result = None
        self.smartmatch_thread = None
        self.neighbor_meta_cache = {}
        self.neighbor_cache_order = deque()
        self.last_reason = "Waiting for SAT channel"
        self.last_action = ""
        self.last_action_time = ""
        self.state = "IDLE"
        self.crypted_state = "?"
        # One-shot encrypted/FTA gate cache for the current DVB service.  It is consulted
        # only when a SAT->IPTV fallback is actually about to happen; normal SAT zaps pay no cost.
        self._fallback_crypto_gate = None
        # Per-service static access cache.  Unlike the 1.0.40 global lamedb parser this
        # cache resolves only the currently requested DVB service and stops as soon as the
        # matching lamedb row is found.  It is consulted only on a real SAT->IPTV fallback.
        self._static_crypto_cache = {}
        self._static_crypto_signature = None
        self.tuner_state = "?"
        self.pts_before = "-"
        self.pts_after = "-"
        self.video_state = "-"
        self.playback_state = "SAT"
        self.play_result = "-"
        self.counters = {
            "sat_zaps": 0, "matches": 0, "fallbacks": 0, "success": 0,
            "failures": 0, "retries": 0, "no_match": 0, "no_signal": 0,
            "pinned": 0, "candidate_failovers": 0, "server_failovers": 0,
            "resolution_rejects": 0, "black_streams": 0,
        }
        self.startup_reconcile_pending = True
        self.startup_reconcile_attempts = 0
        self.startup_reconcile_last_ref = ""

        if self._on_event not in self.session.nav.event:
            self.session.nav.event.append(self._on_event)
        self._log("MONITOR_START", "catalog=fast-snapshot expected=%d snapshot=%s" % (self.cache_expected, "YES" if os.path.isfile(self.cache_snapshot_path) else "NO"))
        self._set_state("IDLE", "Monitor ready; fast IPTV snapshot will load after GUI startup")

    # ------------------------------------------------------------------
    # Public diagnostics
    # ------------------------------------------------------------------
    def _fast_zap_enabled(self):
        try: return bool(getattr(getattr(self.cfg, "fast_zap", None), "value", True))
        except Exception: return True

    def _instant_mapped_enabled(self):
        try: return bool(getattr(getattr(self.cfg, "instant_mapped", None), "value", True))
        except Exception: return True

    def _neighbor_prepare_enabled(self):
        # 1.0.45: disabled. The previous metadata-only "Smart FCC" still materialised the
        # complete bouquet list after successful IPTV zaps. On large bouquets that work ran
        # in an eTimer/GUI callback and could make CH+/CH- feel frozen. Direct/session caches
        # already make repeated channels fast without scanning neighbours.
        return False

    def _preserve_sat_frontend_enabled(self):
        try: return bool(getattr(getattr(self.cfg, "preserve_sat_frontend", None), "value", True))
        except Exception: return True

    def _no_4k_upscale_enabled(self):
        try: return bool(getattr(getattr(self.cfg, "no_4k_upscale", None), "value", True))
        except Exception: return True

    def _capture_sat_frontend_shadow(self):
        if not self._preserve_sat_frontend_enabled():
            sat_shadow.deactivate()
            return
        data = {}
        try:
            service = self.session.nav.getCurrentService()
            feinfo = service and service.frontendInfo()
            if feinfo:
                try:
                    all_data = feinfo.getAll(True) or {}
                    if isinstance(all_data, dict): data.update(all_data)
                except Exception:
                    pass
                # OpenATV's FrontendStatus source uses tuner_signal_quality /
                # tuner_signal_quality_db / tuner_locked.  Merge those names into the
                # shadow so SNR bars survive the transition to 4097/5002.
                try:
                    status = feinfo.getFrontendStatus() or {}
                    if isinstance(status, dict): data.update(status)
                except TypeError:
                    try:
                        status = {}
                        feinfo.getFrontendStatus(status)
                        if isinstance(status, dict): data.update(status)
                    except Exception:
                        pass
                except Exception:
                    pass
        except Exception:
            data = {}
        sat_shadow.capture(
            name=self.current_sat_name, provider=self.sat_provider, orbital=self.sat_orbital,
            satellite=self.sat_satellite, frontend=data, ref=self.current_sat_ref_string
        )
        self.frontend_shadow_ref = str(self.current_sat_ref_string or "")

    def _prewarm_locked_stream(self, channel):
        """Warm the exact MANUAL_LOCK TS upstream in a worker thread.

        The relay keeps the warmed hub for a short handover grace. When playService() later
        requests /ts, the same upstream socket/ring is reused. HLS/DASH and non-HTTP transports
        are excluded because ServiceApp should own them directly.
        """
        if not channel or self.direct_mapping_source != "MANUAL_LOCK":
            return
        try:
            raw = str(channel.get("url") or "").strip()
            if not raw.startswith(("http://", "https://")):
                return
            kind = self._stream_transport_kind(channel)
            if kind not in ("ts", "unknown"):
                return
            if kind == "unknown" and not channel.get("stream_id"):
                return
            now = time.time()
            if raw == self._lock_prewarm_url and (now - float(self._lock_prewarm_at or 0)) < 1.0:
                return
            self._lock_prewarm_url = raw
            self._lock_prewarm_at = now
            try:
                _qlabel, qrank, _qsource = effective_quality_info(channel)
                qrank = max(int(qrank or 0), int(self.target_quality_rank or 0))
            except Exception:
                qrank = int(self.target_quality_rank or 0)
            warm_url = "http://127.0.0.1:18081/warm?fast=1&q=%d&u=%s" % (
                int(qrank or 0), quote(raw, safe=""))
            def _run():
                try:
                    h = urlopen(warm_url, timeout=float(self.FAST_LOCK_PREWARM_TIMEOUT_S))
                    try:
                        h.read(256)
                    finally:
                        try: h.close()
                        except Exception: pass
                except Exception:
                    pass
            threading.Thread(target=_run, name="IPToSatLockWarm", daemon=True).start()
            self._log("FAST_LOCK_PREWARM", "sat='%s' iptv='%s'" % (self.current_sat_name, channel.get("name", "")))
        except Exception as err:
            self._log("FAST_LOCK_PREWARM_ERR", str(err))

    def _schedule_neighbor_prepare(self):
        if not self._neighbor_prepare_enabled() or not self.catalog.channels or not self.current_sat_ref_string:
            return
        try:
            self.neighbor_prepare_timer.stop()
            self.neighbor_prepare_timer.start(self.NEIGHBOR_PREP_DELAY_MS, True)
        except Exception:
            pass

    def _static_sat_identity(self, ref):
        provider = ""; orbital = None; sat_name = ""
        try:
            from enigma import eServiceCenter
            info = eServiceCenter.getInstance().info(ref)
            pkey = getattr(iServiceInformation, "sProvider", None)
            if info is not None and pkey is not None:
                try: provider = info.getInfoString(ref, pkey) or ""
                except TypeError: provider = info.getInfoString(pkey) or ""
        except Exception:
            pass
        try:
            raw = int(ref.getUnsignedData(4)); orbital = (raw >> 16) & 0xFFFF
            if orbital == 0xFFFF: orbital = None
        except Exception:
            orbital = None
        if orbital is not None:
            try:
                from Components.NimManager import nimmanager
                sat_name = str(nimmanager.getSatDescription(int(orbital)) or "")
            except Exception:
                sat_name = ""
        return provider, orbital, sat_name

    def _prepare_neighbor_rankings(self):
        """Ultra-light CH+/CH- preparation that never scores the IPTV catalogue.

        The old Soft-FCC implementation called fast_rank_matches() for both neighbours from an
        eTimer callback. eTimer callbacks run on Enigma2's GUI/main loop, so on a Vu+ Zero 4K
        those CPU-heavy ranking passes could make the remote appear frozen for several seconds
        *after* the IPTV picture had already opened. Keep only cheap DVB metadata for the next
        and previous service; actual SmartMatch is done once, only if that service really needs
        IPTV fallback. Known manual/learned mappings are already O(1) and need no pre-ranking.
        """
        if not self._neighbor_prepare_enabled() or not self.current_sat_ref_string:
            return
        try:
            from Screens.InfoBar import InfoBar
            infobar = getattr(InfoBar, "instance", None)
            sl = infobar and getattr(infobar, "servicelist", None)
            lb = sl and getattr(sl, "servicelist", None)
            refs = lb and lb.getList() or []
            valid_refs = [r for r in refs if self._ref_valid(r)]
            strings = [r.toString() for r in valid_refs]
            if self.current_sat_ref_string not in strings:
                return
            pos = strings.index(self.current_sat_ref_string)
            prepared = 0
            for off in (1, -1):
                if not strings:
                    break
                idx = (pos + off) % len(strings)
                ref = valid_refs[idx]
                try:
                    rstr = ref.toString(); stype = rstr.split(":", 1)[0]; path = ref.getPath() or ""
                except Exception:
                    continue
                if stype != "1" or path:
                    continue
                try: name = ServiceReference(ref).getServiceName() or ""
                except Exception: name = ""
                if not name:
                    continue
                provider, orbital, satellite = self._static_sat_identity(ref)
                self.neighbor_meta_cache[rstr] = (name, provider, orbital, satellite, time.time())
                if rstr in self.neighbor_cache_order:
                    try: self.neighbor_cache_order.remove(rstr)
                    except Exception: pass
                self.neighbor_cache_order.append(rstr)
                prepared += 1
            while len(self.neighbor_meta_cache) > 4 and self.neighbor_cache_order:
                key = self.neighbor_cache_order.popleft()
                self.neighbor_meta_cache.pop(key, None)
            if prepared:
                self._log("SOFT_FCC_META", "prepared=%d next/previous SAT metadata; IPTV scoring=0 network=0" % prepared)
        except Exception as err:
            self._log("SOFT_FCC_ERROR", str(err))

    def _invalidate_fast_runtime_caches(self):
        """Drop candidate objects tied to an older catalog snapshot."""
        self.neighbor_meta_cache.clear()
        self.neighbor_cache_order.clear()
        self.direct_mapping_cache = None
        self.direct_mapping_source = ""
        self.direct_hot_cache.clear()
        self.direct_hot_order.clear()

    def _direct_hot_key(self):
        try:
            return sat_service_key(self.current_sat_ref_string)
        except Exception:
            return str(self.current_sat_ref_string or "")

    def _direct_hot_get(self):
        """Return a validated-in-this-session direct mapping without disk/scoring work."""
        key = self._direct_hot_key()
        rec = self.direct_hot_cache.get(key) if key else None
        if not isinstance(rec, tuple) or len(rec) != 3:
            return None, ""
        fingerprint, source, match_name = rec
        if str(match_name or "") != str(self.current_match_name or self.current_sat_name or ""):
            self.direct_hot_cache.pop(key, None)
            return None, ""
        ch = self.catalog.find_fingerprint(fingerprint) if fingerprint else None
        if ch is None:
            self.direct_hot_cache.pop(key, None)
            return None, ""
        try:
            if key in self.direct_hot_order:
                self.direct_hot_order.remove(key)
            self.direct_hot_order.append(key)
        except Exception:
            pass
        return ch, str(source or "")

    def _direct_hot_put(self, channel, source):
        if not channel or source not in ("MANUAL_LOCK", "LEARNED", "SESSION_FAST"):
            return
        key = self._direct_hot_key()
        if not key:
            return
        try:
            self.direct_hot_cache[key] = (
                channel_fingerprint(channel), str(source),
                str(self.current_match_name or self.current_sat_name or "")
            )
            if key in self.direct_hot_order:
                self.direct_hot_order.remove(key)
            self.direct_hot_order.append(key)
            while len(self.direct_hot_order) > 128:
                old = self.direct_hot_order.popleft()
                self.direct_hot_cache.pop(old, None)
        except Exception:
            pass

    def _direct_hot_drop_current(self):
        key = self._direct_hot_key()
        if not key:
            return
        self.direct_hot_cache.pop(key, None)
        try:
            self.direct_hot_order.remove(key)
        except Exception:
            pass

    def _verify_step_ms(self):
        return self.FAST_VERIFY_STEP_MS if self._fast_zap_enabled() else self.NORMAL_VERIFY_STEP_MS

    def _video_timeout_ms(self):
        if not self._fast_zap_enabled():
            return self.NORMAL_VIDEO_TIMEOUT_MS
        timeout = int(self.FAST_VIDEO_TIMEOUT_MS)
        rank = int(self.target_quality_rank or 0)
        ch = self.pending_match or self.last_match
        try:
            if ch is not None:
                _label, crank, _source = effective_quality_info(ch)
                rank = max(rank, int(crank or 0))
        except Exception:
            pass
        if rank >= 600:
            timeout = max(timeout, int(self.FAST_UHD_VIDEO_TIMEOUT_MS))
        elif rank >= 500:
            timeout = max(timeout, int(self.FAST_FHD_VIDEO_TIMEOUT_MS))
        # Reuse measured first-frame latency when available.  This prevents a stream that has
        # already proven it needs ~2s from being killed by the generic 1.8s ceiling next time.
        try:
            if ch is not None:
                rec = self.stream_health.get(channel_fingerprint(ch)) or {}
                latency = int(rec.get("latency_ms") or 0)
                if latency > 0:
                    timeout = max(timeout, min(2000, int(latency * 1.35 + 300)))
        except Exception:
            pass
        # r61: explicit MANUAL_LOCK channels use the earlier fast-open philosophy. A good
        # first frame is still accepted instantly, but a failed native path is not allowed to
        # spend 3-4.2 s before rescue. Direct ServiceApp locks keep a just-under-2 s ceiling.
        if self._fast_zap_enabled() and self.last_match_source == "MANUAL_LOCK":
            if str(self.current_play_mode) == "dvb":
                limit = self.FAST_LOCK_UHD_NATIVE_TIMEOUT_MS if rank >= 600 else self.FAST_LOCK_NATIVE_TIMEOUT_MS
                return min(int(limit), timeout)
            return min(int(self.FAST_LOCK_SERVICEAPP_TIMEOUT_MS), timeout)
        # r46 stable ceilings remain for automatic/non-locked channels.
        if rank >= 600:
            return min(4200, timeout)
        if rank >= 500:
            return min(3000, timeout)
        return min(2200, timeout)

    def _resolution_timeout_ms(self):
        return self.FAST_RESOLUTION_TIMEOUT_MS if self._fast_zap_enabled() else self.NORMAL_RESOLUTION_TIMEOUT_MS

    def _arm_video_watchdog(self):
        now = time.time()
        self.verify_started_at = now
        self.verify_deadline = now + (self._video_timeout_ms() / 1000.0)
        self.resolution_deadline = 0.0
        self.first_video_evidence_at = 0.0
        self.verify_round = 0

    def _retry_release_ms(self):
        if not self._fast_zap_enabled():
            return self.RETRY_RELEASE_MS
        rank = int(self.target_quality_rank or 0)
        try:
            ch = self.pending_match or self.last_match
            if ch is not None:
                _label, crank, _source = effective_quality_info(ch)
                rank = max(rank, int(crank or 0))
        except Exception:
            pass
        # Give the Vu+ hardware decoder a little more release time only after a failed player.
        # Successful zaps never pay this delay.  UHD needs the largest buffer before 4097<->5002.
        if rank >= 600:
            return self.FAST_UHD_RETRY_RELEASE_MS
        if rank >= 500:
            return self.FAST_FHD_RETRY_RELEASE_MS
        return self.FAST_RETRY_RELEASE_MS

    def _start_guard_ms(self):
        if not self._fast_zap_enabled():
            return self.START_GUARD_MS
        rank = int(self.target_quality_rank or 0)
        try:
            ch = self.pending_match or self.last_match
            if ch is not None:
                _label, crank, _source = effective_quality_info(ch)
                rank = max(rank, int(crank or 0))
        except Exception:
            pass
        # This is only the maximum time allowed for the IPTV reference to become active.
        # The 50ms poll exits immediately on success, so larger UHD/FHD ceilings do not slow
        # channels that start normally.
        if rank >= 600:
            return self.FAST_UHD_START_GUARD_MS
        if rank >= 500:
            return self.FAST_FHD_START_GUARD_MS
        return self.FAST_START_GUARD_MS

    def start_startup_reconcile(self, delay_ms=None):
        """Attach the monitor to the service already playing after GUI boot.

        Enigma2 does not replay evStart to listeners registered after a service started.  We do
        not call playService() here: the current DVB reference is inspected in-place, which avoids
        a visible zap, tuner retune, CAM churn or an invalid-reference window during boot.
        """
        if not self.startup_reconcile_pending:
            return
        try:
            delay = self.STARTUP_RECONCILE_DELAY_MS if delay_ms is None else max(0, int(delay_ms))
            self.startup_reconcile_timer.start(delay, True)
        except Exception as err:
            self._log("BOOT_ATTACH_TIMER", str(err))

    def _startup_reconcile(self):
        if not self.startup_reconcile_pending:
            return
        if not bool(getattr(getattr(self.cfg, "enabled", None), "value", False)):
            self.startup_reconcile_pending = False
            return
        self.startup_reconcile_attempts += 1
        ref = self.session.nav.getCurrentlyPlayingServiceReference()
        if not self._ref_valid(ref):
            if self.startup_reconcile_attempts < self.STARTUP_RECONCILE_MAX_RETRIES:
                self.start_startup_reconcile(self.STARTUP_RECONCILE_RETRY_MS)
            else:
                self._log("BOOT_ATTACH_GIVEUP", "no current service after %d checks" % self.startup_reconcile_attempts)
            return
        try:
            ref_string = ref.toString()
            service_type = ref_string.split(":", 1)[0]
            service_path = ref.getPath() or ""
        except Exception:
            service_type = ""; service_path = ""; ref_string = ""
        self.startup_reconcile_last_ref = ref_string
        # If the box intentionally boots on an IPTV/file service, there is no SAT service to
        # bridge.  Do not interfere with it and do not create a synthetic zap.
        if service_type in ("4097", "5001", "5002", "5003") or service_path:
            self.startup_reconcile_pending = False
            self._log("BOOT_ATTACH_BYPASS", "startup service already IPTV/non-DVB")
            return
        # The catalogue starts asynchronously to protect GUI boot. Never reconcile against a
        # partially built initial JSONL index: exact candidates later in the file may not exist
        # yet. Keep the current service pending until EOF publishes the complete catalogue.
        if self.cache_loading and not self.cache_swap_mode:
            if self.startup_reconcile_attempts < self.STARTUP_RECONCILE_MAX_RETRIES:
                self.start_startup_reconcile(self.STARTUP_RECONCILE_RETRY_MS)
            return
        if not self.catalog.channels:
            if self.startup_reconcile_attempts < self.STARTUP_RECONCILE_MAX_RETRIES:
                self.start_startup_reconcile(self.STARTUP_RECONCILE_RETRY_MS)
            return
        # If a normal evStart already processed this same SAT service while the cache was ready,
        # there is nothing to replay.  This avoids double counters/timers on normal zaps.
        if self.current_sat_ref_string == ref_string and self.state not in (
            "IDLE", "READY", "NO_CATALOG", "CACHE_LOADING", "CACHE_FAST_LOAD",
            "CACHE_REFRESH", "CACHE_LEGACY", "CATALOG_LOADING"
        ):
            self.startup_reconcile_pending = False
            self._log("BOOT_ATTACH_ALREADY", "current SAT service already monitored")
            return
        self._log("BOOT_ATTACH", "reconciling already-playing SAT service without zap")
        self._on_start()
        # _on_start may return early only if the service changed under us.  In that case allow
        # one more reconciliation cycle; otherwise the standard SAT timer now owns the flow.
        current = self.session.nav.getCurrentlyPlayingServiceReference()
        try: current_string = current.toString() if self._ref_valid(current) else ""
        except Exception: current_string = ""
        if (self.current_sat_ref_string and self.current_sat_ref_string == current_string and
                not self.cache_loading and self.state not in ("CATALOG_LOADING", "CACHE_LOADING", "CACHE_FAST_LOAD", "CACHE_REFRESH")):
            self.startup_reconcile_pending = False
            self._log("BOOT_ATTACH_OK", "startup SAT service armed")
        elif self.startup_reconcile_attempts < self.STARTUP_RECONCILE_MAX_RETRIES:
            self.start_startup_reconcile(self.STARTUP_RECONCILE_RETRY_MS)

    def _wake_startup_reconcile(self, delay_ms=80):
        if self.startup_reconcile_pending:
            self.start_startup_reconcile(delay_ms)

    def start_boot_cache_loader(self, primary_snapshot_path="", full_snapshot_path="", delay_ms=None):
        """Load one frozen, pre-indexed local catalogue at boot and never swap it later.

        r15 priority is FULL merged snapshot first, then PRIMARY snapshot as a safe fallback.
        This function performs no network access and deliberately does not schedule the old
        PRIMARY -> FULL background swap that could temporarily make mappings disappear.
        """
        if self.catalog.channels or self.cache_loading:
            return False
        full = str(full_snapshot_path or self.cache_snapshot_path or "")
        primary = str(primary_snapshot_path or "")
        chosen = ""
        for path in (full, primary):
            if not path or not os.path.isfile(path):
                continue
            try:
                size = int(os.path.getsize(path) or 0)
            except Exception:
                size = 0
            if size <= self.BOOT_PRIMARY_SNAPSHOT_GUI_MAX_BYTES:
                chosen = path
                break
        if chosen:
            self.boot_primary_active = True  # enables the larger one-shot boot snapshot fence
            self.boot_full_swap_path = ""    # r15: NEVER schedule a second boot swap
            self.cache_swap_mode = True
            self.cache_target = None
            self.cache_snapshot_override = chosen
            try:
                delay = self.BOOT_PRIMARY_LOAD_DELAY_MS if delay_ms is None else max(0, int(delay_ms))
                self.cache_loader_timer.start(delay, True)
                self._log("BOOT_CACHE_FROZEN", "one-shot snapshot=%s" % ("FULL" if chosen == full else "PRIMARY"))
                return True
            except Exception as err:
                self.boot_primary_active = False
                self.cache_swap_mode = False
                self.cache_snapshot_override = ""
                self._log("BOOT_CACHE_TIMER_ERR", str(err))
        # No valid optimized snapshot: local JSONL may still be read as a compatibility
        # fallback, but no source/network refresh is ever started here.
        self.start_cache_loader(delay_ms=self.BOOT_PRIMARY_LOAD_DELAY_MS if delay_ms is None else delay_ms)
        return False

    def start_cache_loader(self, delay_ms=None):
        """Schedule fast snapshot load, falling back to incremental JSONL only if needed."""
        if self.catalog.channels or self.cache_loading:
            return
        if not os.path.isfile(self.cache_snapshot_path) and not os.path.isfile(self.cache_jsonl_path):
            if os.path.isfile(self.cache_path):
                self._set_state("CACHE_LEGACY", "Legacy cache found; refresh IPTV once to optimize it")
                self._log("CACHE_LEGACY", "fast snapshot/JSONL missing; manual refresh required")
            return
        try:
            self.cache_loader_timer.start(int(self.CACHE_LOAD_DELAY_MS if delay_ms is None else max(0, int(delay_ms))), True)
        except Exception as err:
            self._log("CACHE_TIMER_ERROR", str(err))

    def start_cache_swap(self, delay_ms=0, snapshot_path=None):
        """Atomically swap a newly imported pre-indexed snapshot; JSONL remains fallback."""
        if self.cache_loading:
            return False
        chosen = str(snapshot_path or self.cache_snapshot_path or "")
        if not os.path.isfile(chosen) and not os.path.isfile(self.cache_jsonl_path):
            return False
        self.cache_swap_mode = True
        self.cache_target = None
        self.cache_snapshot_override = chosen if os.path.isfile(chosen) else ""
        try:
            self.cache_loader_timer.start(max(0, int(delay_ms or 0)), True)
            self._log("CACHE_SWAP_SCHEDULE", "fast snapshot swap scheduled" if self.cache_snapshot_override else "JSONL fallback swap scheduled")
            return True
        except Exception as err:
            self.cache_swap_mode = False
            self.cache_snapshot_override = ""
            self._log("CACHE_SWAP_ERROR", str(err))
            return False

    def _cache_loader_open(self):
        if self.cache_file is not None:
            return True
        try:
            self.cache_meta = Catalog.read_meta(self.cache_meta_path)
            self.cache_expected = int(self.cache_meta.get("count") or 0)
            self.cache_file = open(self.cache_jsonl_path, "r", encoding="utf-8", errors="replace")
            self.cache_generation += 1
            target = Catalog([], meta=dict(self.cache_meta or {}))
            if self.cache_swap_mode:
                self.cache_target = target
            else:
                self.catalog = target
            self.cache_loaded = 0
            self.cache_loading = True
            self.cache_started_at = time.time()
            self._set_state("CACHE_REFRESH" if self.cache_swap_mode else "CACHE_LOADING", "Loading IPTV cache incrementally")
            self._log("CACHE_LOAD_START", "expected=%d swap=%s" % (self.cache_expected, "YES" if self.cache_swap_mode else "NO"))
            return True
        except Exception as err:
            self.cache_loading = False
            self.cache_file = None
            self._set_state("CACHE_ERROR", "Cannot open IPTV cache")
            self._log("CACHE_OPEN_ERROR", str(err))
            return False

    def _cache_loader_tick(self):
        if (not self.cache_swap_mode) and self.catalog.channels and not self.cache_loading:
            return
        snapshot_path = self.cache_snapshot_override or self.cache_snapshot_path
        snapshot_ok_in_gui = False
        if snapshot_path and os.path.isfile(snapshot_path):
            try:
                snapshot_size = int(os.path.getsize(snapshot_path) or 0)
            except Exception:
                snapshot_size = 0
            # If a CURRENT JSONL exists, never unpickle a huge snapshot in the GUI thread.
            # A legacy/stale JSONL must not silently replace a newer snapshot, so only defer
            # when its mtime is at least the snapshot mtime. Post-install migration and the
            # 1.0.45 importer guarantee this on normal systems.
            jsonl_current = False
            try:
                if os.path.isfile(self.cache_jsonl_path):
                    js = os.stat(self.cache_jsonl_path); ss = os.stat(snapshot_path)
                    jmt = int(getattr(js, "st_mtime_ns", int(js.st_mtime * 1000000000)))
                    smt = int(getattr(ss, "st_mtime_ns", int(ss.st_mtime * 1000000000)))
                    jsonl_current = jmt >= smt
            except Exception:
                jsonl_current = False
            # Hard safety fence: NEVER unpickle a large catalogue snapshot on Enigma2's
            # GUI/mainloop, even when JSONL is stale/missing. Upgrade postinst migrates old
            # snapshot-only caches outside the runtime hot path; future imports write JSONL.
            snapshot_limit = self.BOOT_PRIMARY_SNAPSHOT_GUI_MAX_BYTES if self.boot_primary_active else self.CACHE_SNAPSHOT_GUI_MAX_BYTES
            snapshot_ok_in_gui = bool(snapshot_size <= snapshot_limit)
            if not snapshot_ok_in_gui and self.cache_file is None:
                self._log("CACHE_SNAPSHOT_DEFER", "size=%dMB jsonl_current=%s -> sliced JSONL only" % (
                    max(1, snapshot_size // (1024*1024)), "YES" if jsonl_current else "NO"))
        if self.cache_file is None and snapshot_path and os.path.isfile(snapshot_path) and snapshot_ok_in_gui:
            started = time.perf_counter()
            try:
                self.cache_loading = True
                self._set_state("CACHE_FAST_LOAD", "Loading pre-indexed IPTV snapshot")
                catalog = Catalog.from_snapshot(snapshot_path, migrate=False)
                elapsed = time.perf_counter() - started
                self.catalog = catalog
                self._invalidate_fast_runtime_caches()
                self.cache_meta = dict(catalog.meta or {})
                self.cache_expected = len(catalog.channels)
                self.cache_loaded = len(catalog.channels)
                self.cache_loading = False
                swapped = self.cache_swap_mode
                self.cache_swap_mode = False
                self.cache_snapshot_override = ""
                self.cache_target = None
                self._apply_health_to_catalog()
                self._set_state("READY", "IPTV catalogue ready")
                self._log("CACHE_FAST_READY", "channels=%d elapsed=%.3fs swap=%s" % (len(catalog.channels), elapsed, "YES" if swapped else "NO"))
                was_boot_primary = bool(self.boot_primary_active)
                full_swap_path = str(self.boot_full_swap_path or "")
                self.boot_primary_active = False
                self.boot_full_swap_path = ""
                # Wake the already-playing SAT channel immediately. Do not wait for backups.
                self._wake_startup_reconcile(40)
                if was_boot_primary:
                    # r15 Frozen Catalog: intentionally no second boot-time catalogue load/swap.
                    # The in-memory catalogue stays stable until a scheduled or manual refresh
                    # completes atomically.
                    self._log("BOOT_CACHE_FROZEN_READY", "catalogue locked for this session")
                return
            except Exception as err:
                # If the small PRIMARY bootstrap is corrupt/stale, fall back to the old safe
                # initial JSONL load. Never expose a partially built catalogue to SmartMatch.
                if self.boot_primary_active:
                    self.boot_primary_active = False
                    self.boot_full_swap_path = ""
                    self.cache_swap_mode = False
                    self.cache_target = None
                self.cache_loading = False
                self.cache_snapshot_override = ""
                self._log("CACHE_SNAPSHOT_ERROR", "%s; falling back to sliced JSONL" % err)
                # Never rebuild a stale snapshot in the GUI thread. Quarantine the normal merged
                # snapshot so subsequent boots do not retry it; Refresh IPTV recreates a current
                # snapshot in the external import worker.
                if snapshot_path == self.cache_snapshot_path:
                    try:
                        stale_path = snapshot_path + ".stale"
                        try:
                            if os.path.exists(stale_path): os.remove(stale_path)
                        except Exception:
                            pass
                        os.replace(snapshot_path, stale_path)
                        self._log("CACHE_SNAPSHOT_QUARANTINE", os.path.basename(stale_path))
                    except Exception:
                        pass
                # Continue below with compatibility JSONL loading in short mainloop slices.
        if not os.path.isfile(self.cache_jsonl_path):
            self.cache_swap_mode = False
            self._set_state("CACHE_ERROR", "Large snapshot kept off GUI thread; JSONL cache is missing. Run Refresh IPTV once.")
            return
        if not self._cache_loader_open():
            return
        started = time.perf_counter()
        lines = 0
        eof = False
        generation = self.cache_generation
        cache_file = self.cache_file
        target_catalog = self.cache_target if self.cache_swap_mode else self.catalog
        if target_catalog is None:
            target_catalog = self.catalog
        try:
            max_lines = self.CACHE_SWAP_MAX_LINES_PER_TICK if self.cache_swap_mode else self.CACHE_MAX_LINES_PER_TICK
            budget = self.CACHE_SWAP_TICK_BUDGET_S if self.cache_swap_mode else self.CACHE_TICK_BUDGET_S
            while lines < max_lines and (time.perf_counter() - started) < budget:
                if generation != self.cache_generation: return
                raw = cache_file.readline()
                if not raw:
                    eof = True
                    break
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    item = json.loads(raw)
                    if isinstance(item, dict) and target_catalog.add_channel(item) is not None:
                        self.cache_loaded += 1
                except Exception:
                    pass
                lines += 1
        except Exception as err:
            self._log("CACHE_READ_ERROR", str(err))
            eof = True
        if generation != self.cache_generation:
            return
        if eof:
            try: cache_file.close()
            except Exception: pass
            self.cache_file = None
            self.cache_loading = False
            elapsed = time.time() - self.cache_started_at if self.cache_started_at else 0.0
            if self.cache_swap_mode and target_catalog is not None:
                self.catalog = target_catalog
                self._invalidate_fast_runtime_caches()
            self.cache_meta["count"] = len(self.catalog.channels)
            self.catalog.meta.update(self.cache_meta)
            self._apply_health_to_catalog()
            # Do NOT serialize/rebuild snapshots here: this callback runs on Enigma2's mainloop.
            # A manual/automatic Refresh IPTV uses the external import worker and writes the fast
            # snapshot without freezing live TV or the GUI.
            if self.catalog.channels and not os.path.isfile(self.cache_snapshot_path):
                self._log("CACHE_SNAPSHOT_DEFERRED", "channels=%d; Refresh IPTV will create optimized snapshot" % len(self.catalog.channels))
            swapped = self.cache_swap_mode
            self.cache_swap_mode = False
            self.cache_snapshot_override = ""
            self.cache_target = None
            self._set_state("READY", "IPTV catalogue ready")
            self._log("CACHE_READY", "channels=%d elapsed=%.2fs swap=%s" % (len(self.catalog.channels), elapsed, "YES" if swapped else "NO"))
            self._wake_startup_reconcile(60)
            return
        self._set_state("CACHE_REFRESH" if self.cache_swap_mode else "CACHE_LOADING", "IPTV cache %d/%s" % (self.cache_loaded, self.cache_expected or "?"))
        try: self.cache_loader_timer.start(self.CACHE_SWAP_TICK_MS if self.cache_swap_mode else self.CACHE_TICK_MS, True)
        except Exception as err: self._log("CACHE_TIMER_ERROR", str(err))

    def publish_catalog(self, catalog, source="import"):
        """Publish a fully built immutable catalogue. Assignment is atomic under CPython's GIL."""
        if catalog is None:
            return
        self.cache_generation += 1
        self.catalog = catalog
        self._invalidate_fast_runtime_caches()
        self.cache_meta = dict(catalog.meta or {})
        self.cache_expected = len(catalog.channels)
        self.cache_loaded = len(catalog.channels)
        self.cache_loading = False
        self._apply_health_to_catalog()
        try:
            if self.cache_file is not None: self.cache_file.close()
        except Exception:
            pass
        self.cache_file = None
        self._log("CATALOG_READY", "channels=%d source=%s" % (len(catalog.channels), source))
        self._wake_startup_reconcile(60)

    def shutdown(self):
        try:
            if self.learned_dirty:
                self._flush_learned_mappings()
        except Exception:
            pass
        try:
            if self.health_dirty:
                self._save_health()
                self.health_dirty = False
        except Exception:
            pass
        self._stop_all_timers()
        try:
            if self.cache_file is not None: self.cache_file.close()
        except Exception: pass
        self.cache_file = None
        try:
            if self._on_event in self.session.nav.event:
                self.session.nav.event.remove(self._on_event)
        except Exception:
            pass
        sat_shadow.deactivate()
        self._log("MONITOR_STOP", "monitor stopped")
        self._flush_log_buffer()


    def set_catalog(self, catalog, source="background"):
        self.publish_catalog(catalog, source=source)
        if self.state in ("IDLE", "NO_CATALOG", "DISABLED", "CACHE_LOADING", "CACHE_LEGACY"):
            self._set_state("READY", "IPTV catalogue ready; zap to a SAT channel")

    def reload_catalog(self):
        # Beta6 deliberately refuses synchronous large-cache reloads in the Enigma2 GUI thread.
        self.start_cache_loader(delay_ms=0)
        return len(self.catalog.channels)

    def clear_log(self):
        try:
            directory = os.path.dirname(self.log_path)
            if directory and not os.path.exists(directory): os.makedirs(directory)
            try: self.log_flush_timer.stop()
            except Exception: pass
            self._log_pending = []
            with open(self.log_path, "w", encoding="utf-8") as handle: handle.write("")
            self._log_ring.clear()
            try: os.chmod(self.log_path, 0o600)
            except Exception: pass
            self._log_permissions_ready = True
            self._log("LOG_CLEAR", "log cleared from diagnostics screen")
            return True
        except Exception as err:
            self.last_error = str(err)
            return False

    def recent_log(self, lines=8):
        try:
            count = max(1, int(lines))
            data = list(self._log_ring)[-count:]
            return "\n".join(data) if data else "No events yet. Zap to a SAT channel to start monitoring."
        except Exception:
            return "No events yet. Zap to a SAT channel to start monitoring."

    def status_snapshot(self):
        match_name = self.last_match.get("name", "") if self.last_match else ""
        match_lang = self.last_match.get("language", "") if self.last_match else ""
        match_market = self.last_match.get("market", "") if self.last_match else ""
        if self.current_iptv_quality_verified and self.current_iptv_quality:
            match_quality = self.current_iptv_quality
        elif self.last_match:
            match_quality = self.last_match.get("claimed_quality") or self.last_match.get("quality", "")
        else:
            match_quality = ""
        match_group = self.last_match.get("group", "") if self.last_match else ""
        ctx = self.sat_context or {}
        shadow_state = sat_shadow.snapshot()
        try:
            sat_snr = sat_shadow.snr_percent_text() if sat_shadow.snr_raw() is not None else "N/A"
        except Exception:
            sat_snr = "N/A"
        try:
            sat_snr_db = sat_shadow.snr_db_text() if shadow_state.get("snr_db") is not None else "N/A"
        except Exception:
            sat_snr_db = "N/A"
        try:
            sat_tuner_letter = sat_shadow.tuner_letter()
        except Exception:
            sat_tuner_letter = "-"
        return {
            "state": self.state, "reason": self.last_reason, "action": self.last_action, "time": self.last_action_time,
            "sat": self.current_sat_name or "-", "provider": self.sat_provider or "Unknown",
            "satellite": self.sat_satellite or "Unknown", "orbital": ctx.get("orbital_label", "Unknown"),
            "market": ctx.get("market", "-") or "-", "market_preferences": ctx.get("market_preferences", []),
            "language_priorities": ctx.get("language_priorities", []),
            "sat_audio_languages": list(ctx.get("audio_language_set") or normalize_audio_languages(self.sat_audio_languages)),
            "sat_audio_target": str(ctx.get("audio_language_target") or ""),
            "context_confidence": ctx.get("confidence", "LOW"),
            "context_reason": ctx.get("reason", "generic"),
            "crypted": self.crypted_state, "tuner": self.tuner_state,
            "sat_snr": sat_snr, "sat_snr_db": sat_snr_db, "sat_tuner_letter": sat_tuner_letter,
            "sat_shadow_lock": bool(shadow_state.get("lock")), "sat_shadow_active": bool(shadow_state.get("active")),
            "sat_tuner_mask": int(shadow_state.get("tuner_mask") or 0),
            "pts_before": self.pts_before, "pts_after": self.pts_after, "video": self.video_state,
            "iptv": match_name or "-", "language": match_lang or "-", "iptv_market": match_market or "-",
            "quality": match_quality or "-", "group": match_group or "-", "score": self.last_score,
            "score_details": dict(self.last_details or {}),
            "match_decision": match_decision(self.last_score, self.last_details, float(self.cfg.match_threshold.value)) if self.last_match else "-",
            "match_source": self.last_match_source,
            "playback": self.playback_state, "play_result": self.play_result, "play_mode": self.current_play_mode,
            "player_override": self._current_player_override(), "first_image_locked": bool(self.playback_locked),
            "player_4097": self.player_status.get("4097", "UNKNOWN"), "player_5002": self.player_status.get("5002", "UNKNOWN"),
            "first_frame_ms": int(self.last_first_frame_ms or 0),
            "attempt": self.fallback_attempt, "error": self.last_error or "-", "counters": dict(self.counters),
            "target_quality": self.target_quality or "AUTO", "target_quality_rank": self.target_quality_rank,
            "target_quality_source": self.target_quality_source,
            "sat_width": self.sat_video_width, "sat_height": self.sat_video_height,
            "iptv_width": int(self.current_iptv_width or 0),
            "iptv_height": int(self.current_iptv_height or 0),
            "quality_verified": bool(self.current_iptv_quality_verified),
            "server_role": (self.last_match or {}).get("server_role") or "-",
            "server_label": (self.last_match or {}).get("server_label") or "-",
            "server_priority": int((self.last_match or {}).get("server_priority") if (self.last_match or {}).get("server_priority") is not None else 999),
            "candidate_index": self.candidate_index, "candidate_count": len(self.candidate_plan),
            "cache_loading": self.cache_loading, "cache_loaded": self.cache_loaded, "cache_expected": self.cache_expected,
            "catalog_count": len(self.catalog.channels), "catalog_meta": dict(self.catalog.meta or self.cache_meta or {}),
        }

    # ------------------------------------------------------------------
    # Logging / helpers
    # ------------------------------------------------------------------
    def _set_state(self, state, reason="", action=""):
        self.state = state
        if reason: self.last_reason = reason
        if action: self.last_action = action
        self.last_action_time = time.strftime("%H:%M:%S")

    def _prime_log_cache(self):
        try:
            if not os.path.isfile(self.log_path):
                return
            with open(self.log_path, "rb") as handle:
                try:
                    handle.seek(-65536, os.SEEK_END)
                except Exception:
                    handle.seek(0)
                raw = handle.read().decode("utf-8", "replace")
            for line in raw.splitlines()[-180:]:
                if line.strip(): self._log_ring.append(line)
        except Exception:
            pass

    def _safe_log_text(self, text):
        text = str(text or "")
        text = re.sub(r"(?i)(password|passwd|pass|token|auth|key)=([^&\s]+)", r"\1=***", text)
        text = re.sub(r"(?i)(/live/[^/\s]+/)([^/\s]+)(/)", r"\1***\3", text)
        text = re.sub(r"(?i)(/movie/[^/\s]+/)([^/\s]+)(/)", r"\1***\3", text)
        text = re.sub(r"(?i)(/series/[^/\s]+/)([^/\s]+)(/)", r"\1***\3", text)
        return text.replace("\r", " ").replace("\n", " ")

    def _rotate_log_if_needed(self):
        try:
            if os.path.isfile(self.log_path) and os.path.getsize(self.log_path) > self.LOG_MAX_BYTES:
                old = self.log_path + ".1"
                try:
                    if os.path.exists(old): os.remove(old)
                except Exception: pass
                os.rename(self.log_path, old)
                try: os.chmod(old, 0o600)
                except Exception: pass
        except Exception: pass

    def _flush_log_buffer(self):
        pending = list(getattr(self, "_log_pending", []) or [])
        if not pending:
            return
        self._log_pending = []
        try:
            directory = os.path.dirname(self.log_path)
            if directory and not os.path.exists(directory): os.makedirs(directory)
            self._rotate_log_if_needed()
            with open(self.log_path, "a", encoding="utf-8") as handle:
                handle.write("\n".join(pending) + "\n")
            if not self._log_permissions_ready:
                try: os.chmod(self.log_path, 0o600)
                except Exception: pass
                self._log_permissions_ready = True
        except Exception:
            # Do not lose diagnostic lines on a transient flash/filesystem failure. Bound the
            # retry queue so logging can never become a memory problem.
            try: self._log_pending = (pending + list(self._log_pending or []))[-120:]
            except Exception: self._log_pending = []

    def _log(self, code, msg):
        """Non-blocking log path: RAM ring now, one batched flash write later."""
        try:
            line = "%s | %-18s | %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), str(code or "INFO")[:18], self._safe_log_text(msg))
            self._log_ring.append(line)
            self._log_pending.append(line)
            # Avoid open/stat/write/close for every nav event. One eTimer flush batches the
            # burst generated by a SAT->IPTV transition.
            try:
                active = bool(self.log_flush_timer.isActive())
            except Exception:
                active = False
            if not active:
                try: self.log_flush_timer.start(1200, True)
                except Exception: pass
            if len(self._log_pending) >= 32:
                try: self.log_flush_timer.start(80, True)
                except Exception: pass
        except Exception:
            pass

    def _stop_all_timers(self):
        for timer in (self.timer, self.probe_timer, self.verify_timer, self.retry_timer, self.start_guard_timer, self.cache_loader_timer, self.health_flush_timer, self.learned_flush_timer, self.log_flush_timer, self.neighbor_prepare_timer, self.startup_reconcile_timer, self.native_pat_guard_timer, self.tune_fail_defer_timer, self.resolution_followup_timer, self.audio_guard_timer):
            try: timer.stop()
            except Exception: pass

    def _stop_probe_timers(self):
        for timer in (self.timer, self.probe_timer, self.verify_timer, self.start_guard_timer, self.neighbor_prepare_timer, self.native_pat_guard_timer, self.tune_fail_defer_timer, self.resolution_followup_timer, self.audio_guard_timer, self.smartmatch_timer):
            try: timer.stop()
            except Exception: pass
        # A new zap invalidates old worker results immediately. Never join/wait in the GUI.
        self.smartmatch_generation += 1
        self.smartmatch_pending = None
        self.smartmatch_result = None

    def _cleanup_bridge_ready_marker(self):
        """Remove the per-attempt native-TS readiness marker without touching playback.

        r28: a successful attempt can be accepted on decoder PTS before the localhost
        relay marker is consumed.  Leaving that marker around is harmless to playback but
        creates stale /tmp state and makes later diagnostics confusing.  Keep cleanup
        idempotent and strictly scoped to the token owned by this monitor instance.
        """
        marker = str(getattr(self, "bridge_ready_marker", "") or "")
        self.bridge_ready_marker = ""
        self.bridge_ready_token = ""
        if not marker or not marker.startswith("/tmp/iptosat-tsbridge-ready-"):
            return
        try:
            if os.path.exists(marker):
                os.unlink(marker)
        except Exception:
            pass

    def _clear_expected_iptv(self):
        self._cleanup_bridge_ready_marker()
        self.expected_iptv_ref_string = ""
        self.expected_iptv_url = ""
        self.previous_iptv_ref_string = ""
        self.previous_iptv_url = ""

    @staticmethod
    def _url_from_stream_ref_string(ref_string):
        """Extract a decoded stream URL from an Enigma2 IPTV ref without touching services."""
        try:
            parts = str(ref_string or "").split(":", 11)
            if len(parts) > 10:
                return unquote(parts[10] or "").strip()
        except Exception:
            pass
        return ""

    @staticmethod
    def _same_stream_url(left, right):
        try:
            a = unquote(str(left or "")).strip()
            b = unquote(str(right or "")).strip()
            return bool(a and b and a == b)
        except Exception:
            return False

    def _is_expected_bridge_iptv(self, ref, ref_string="", service_path=""):
        """True only for the IPTV service requested by this bridge attempt.

        Enigma2/ServiceApp may canonicalise the service reference, so URL equality is accepted
        in addition to the exact reference string.  Crucially, *any* IPTV service is no longer
        sufficient: that old behaviour could hijack a user-initiated IPTV zap while an earlier
        SAT fallback was still active.
        """
        if not self.fallback_active:
            return False
        try:
            current_string = ref_string or (ref.toString() if self._ref_valid(ref) else "")
        except Exception:
            current_string = str(ref_string or "")
        if self.expected_iptv_ref_string and current_string == self.expected_iptv_ref_string:
            return True
        expected_url = str(self.expected_iptv_url or "").strip()
        if not expected_url:
            return False
        # URL alone is not sufficient during a 4097 -> 5002 retry: the previous player may
        # still expose the same URL for a few mainloop ticks. Require the requested player type
        # unless the complete service reference matched above.
        try: current_type = current_string.split(":", 1)[0]
        except Exception: current_type = ""
        expected_type = str(self.current_play_mode or "")
        if expected_type in ("4097", "5001", "5002", "5003") and current_type and current_type != expected_type:
            return False
        path = str(service_path or "").strip()
        if not path and self._ref_valid(ref):
            try: path = ref.getPath() or ""
            except Exception: path = ""
        if self._same_stream_url(path, expected_url):
            return True
        return self._same_stream_url(self._url_from_stream_ref_string(current_string), expected_url)

    def _is_previous_bridge_iptv(self, ref, ref_string="", service_path=""):
        try:
            current_string = ref_string or (ref.toString() if self._ref_valid(ref) else "")
        except Exception:
            current_string = str(ref_string or "")
        if self.previous_iptv_ref_string and current_string == self.previous_iptv_ref_string:
            return True
        old_url = str(self.previous_iptv_url or "").strip()
        if not old_url:
            return False
        path = str(service_path or "").strip()
        if not path and self._ref_valid(ref):
            try: path = ref.getPath() or ""
            except Exception: path = ""
        return self._same_stream_url(path, old_url) or self._same_stream_url(self._url_from_stream_ref_string(current_string), old_url)

    def _abandon_bridge_for_manual_iptv(self, ref_string="", service_path=""):
        """Cancel stale bridge state when the user intentionally selects another IPTV service."""
        self._stop_probe_timers()
        try: self.retry_timer.stop()
        except Exception: pass
        try: self.start_guard_timer.stop()
        except Exception: pass
        sat_shadow.deactivate()
        self.frontend_shadow_ref = ""
        self.switch_in_progress = False
        self.native_pat_guard_pending = False
        self.fallback_active = False
        self.retry_pending = False
        self.retry_kind = ""
        self.iptv_start_seen = False
        self.pending_match = None
        self.pending_score = 0.0
        self.pending_details = {}
        self.candidate_plan = []
        self.candidate_index = -1
        self.failed_candidate_ids = set()
        self._clear_expected_iptv()
        self.playback_state = "IPTV (manual)"
        self.play_result = "BYPASS"
        self._set_state("IPTV_BYPASS", "Manual IPTV service selected; SAT bridge state cancelled")
        self._log("IPTV_MANUAL_BYPASS", "ref=%s path=%s" % (
            str(ref_string or "")[:96], redact_url(service_path) if service_path else "player-ref"))

    def _format_pts(self, value):
        if value is None: return "N/A"
        try: return "0x%X" % int(value)
        except Exception: return str(value)

    def _user_languages(self):
        return [x.strip().upper() for x in self.cfg.languages.value.split(",") if x.strip()]

    def _ref_valid(self, ref):
        if ref is None:
            return False
        try:
            valid = getattr(ref, "valid", None)
            if callable(valid) and not valid():
                return False
        except Exception:
            return False
        try:
            return bool(ref.toString())
        except Exception:
            return False

    def _read_sat_audio_languages(self):
        """Read original DVB audio identity before switching to IPTV.

        Some OpenATV demuxers expose only ISO language codes, while others put useful
        text such as ``French AC3`` in the track description. Keep both; core.py
        normalizes them conservatively and ignores und/qaa/mis markers.
        """
        out = []
        try:
            service = self.session.nav.getCurrentService()
            tracks = service and service.audioTracks()
            count = tracks and tracks.getNumberOfTracks() or 0
            for idx in range(int(count or 0)):
                try:
                    info = tracks.getTrackInfo(idx)
                except Exception:
                    info = None
                values = []
                if info is not None:
                    for meth in ("getLanguage", "getDescription"):
                        try:
                            value = getattr(info, meth)() or ""
                            if value:
                                values.append(str(value))
                        except Exception:
                            pass
                for value in values:
                    value = value.strip()
                    if value and value.lower() not in ("und", "qaa", "mis", "mul", "zxx") and value not in out:
                        out.append(value)
        except Exception:
            pass
        return out

    def _read_current_epg_text(self):
        # EPG is only a weak fallback for ambiguous FR/ES platform labels. Never depend on it.
        try:
            service = self.session.nav.getCurrentService()
            info = service and service.info()
            event = info and info.getEvent(0)
            if not event:
                return ""
            bits = []
            for meth in ("getEventName", "getShortDescription", "getExtendedDescription"):
                try:
                    value = getattr(event, meth)() or ""
                    if value: bits.append(str(value))
                except Exception:
                    pass
            return " ".join(bits)[:1200]
        except Exception:
            return ""

    def _capture_sat_epg_events(self):
        """Capture current/next DVB event before switching away from SAT.

        4097/5002 streams normally lose the DVB EventInfo association.  Keep a tiny now/next
        snapshot so it can be mirrored to the temporary IPTV service reference without any
        network lookup or full EPG import.
        """
        events = []
        try:
            service = self.session.nav.getCurrentService()
            info = service and service.info()
            if not info:
                return events
            seen = set()
            for which in (0, 1):
                try:
                    event = info.getEvent(which)
                except Exception:
                    event = None
                if not event:
                    continue
                try:
                    begin = int(event.getBeginTime() or 0); duration = int(event.getDuration() or 0)
                except Exception:
                    continue
                if begin <= 0 or duration <= 0 or begin in seen:
                    continue
                seen.add(begin)
                def val(name):
                    try: return str(getattr(event, name)() or "")
                    except Exception: return ""
                events.append((begin, duration, val("getEventName"), val("getShortDescription"), val("getExtendedDescription"), 0))
        except Exception:
            pass
        return events[:2]

    def _ensure_sat_switch_metadata(self):
        """Capture only metadata needed to preserve the SAT InfoBar during a known mapping.

        4097/5002 hybrid refs already keep the original SID/TSID/ONID and the renderer shadow
        covers players that canonicalize the ref.  Do not query/copy EPG events here: that work
        is unnecessary on the direct-mapping hot path and can delay playService().
        """
        try:
            # Fast mapped path already refreshes the frontend shadow immediately before this
            # call.  Avoid asking the Vu+ frontend twice in the same hot path.
            if self.frontend_shadow_ref != str(self.current_sat_ref_string or ""):
                self._capture_sat_frontend_shadow()
        except Exception:
            pass

    def _ensure_sat_deep_context(self):
        """Collect richer SAT metadata once, immediately before a real fallback."""
        if self.sat_deep_context_ready:
            return
        try: self.sat_audio_languages = self._read_sat_audio_languages()
        except Exception: self.sat_audio_languages = []
        try: self.sat_epg_text = self._read_current_epg_text()
        except Exception: self.sat_epg_text = ""
        try:
            self.sat_epg_events = self._capture_sat_epg_events() if self._epg_bridge_enabled() else []
        except Exception:
            self.sat_epg_events = []
        try:
            self.sat_context = infer_sat_context(
                self.current_match_name or self.current_sat_name, self.sat_provider, self.sat_orbital, self.sat_satellite,
                self._user_languages(), audio_languages=self.sat_audio_languages, epg_text=self.sat_epg_text
            )
            self.sat_context["service_label"] = self.current_sat_name
        except Exception:
            pass
        try: self._capture_sat_frontend_shadow()
        except Exception: pass
        self.sat_deep_context_ready = True

    def _epg_bridge_enabled(self):
        try: return bool(getattr(getattr(self.cfg, "preserve_sat_epg", None), "value", True))
        except Exception: return True

    def _stream_keeps_sat_epg_identity(self, ip_ref):
        """True when stream ref carries the SAT SID/TSID/ONID identity.

        OpenATV EPG keys are based on SID/ONID/TSID, not the service player type.
        A 4097/5002 hybrid reference can therefore read the existing SAT EPG directly
        without copying events into a temporary stream key.
        """
        try:
            sat_parts = str(self.current_sat_ref_string or "").split(":")
            ip_parts = ip_ref.toString().split(":") if ip_ref is not None else []
            if len(sat_parts) < 6 or len(ip_parts) < 6:
                return False
            if ip_parts[0] not in ("4097", "5001", "5002", "5003"):
                return False
            return tuple(ip_parts[3:6]) == tuple(sat_parts[3:6]) and any(x not in ("", "0") for x in sat_parts[3:6])
        except Exception:
            return False

    def _mirror_sat_epg_to_stream(self, ip_ref):
        if not self._epg_bridge_enabled() or ip_ref is None:
            return False
        if self._stream_keeps_sat_epg_identity(ip_ref):
            # No import needed: OpenATV resolves EPG by SID/ONID/TSID. Reusing the SAT
            # identity gives now/next (and future events) directly from the existing cache.
            self._log("EPG_NATIVE_ID", "sat='%s' mode=%s direct SAT EPG key" % (self.current_sat_name, self.current_play_mode))
            return True
        if eEPGCache is None or not self.sat_epg_events:
            return False
        try:
            cache = eEPGCache.getInstance()
            if cache is None:
                return False
            service_key = ip_ref.toString()
            events = tuple(self.sat_epg_events)
            if hasattr(cache, "importEvents"):
                # OpenPLi/OpenATV variants differ on whether SWIG refs or strings are accepted.
                # Prefer the real eServiceReference and transparently fall back to its string.
                try:
                    cache.importEvents((ip_ref,), events)
                except Exception:
                    cache.importEvents((service_key,), events)
            elif hasattr(cache, "importEvent"):
                try:
                    cache.importEvent(ip_ref, events)
                except Exception:
                    cache.importEvent(service_key, events)
            else:
                return False
            self._log("EPG_BRIDGE", "mirrored=%d sat='%s' mode=%s" % (len(events), self.current_sat_name, self.current_play_mode))
            return True
        except Exception as err:
            self._log("EPG_BRIDGE_FAIL", str(err))
            return False

    def _read_sat_identity(self, ref):
        provider = ""
        orbital = None
        sat_name = ""
        try:
            service = self.session.nav.getCurrentService()
            info = service and service.info()
            if info:
                pkey = getattr(iServiceInformation, "sProvider", None)
                if pkey is not None and hasattr(info, "getInfoString"):
                    provider = info.getInfoString(pkey) or ""
                tkey = getattr(iServiceInformation, "sTransponderData", None)
                if tkey is not None and hasattr(info, "getInfoObject"):
                    tp = info.getInfoObject(tkey)
                    if isinstance(tp, dict) and tp.get("orbital_position") is not None:
                        orbital = int(tp.get("orbital_position"))
        except Exception:
            pass
        # With no tuner lock, current service info may not expose the provider. Query the
        # static DVB database as a fallback; this is important for provider-aware no-signal matching.
        if not provider and self._ref_valid(ref):
            try:
                from enigma import eServiceCenter
                static = eServiceCenter.getInstance().info(ref)
                pkey = getattr(iServiceInformation, "sProvider", None)
                if static is not None and pkey is not None and hasattr(static, "getInfoString"):
                    try: provider = static.getInfoString(ref, pkey) or ""
                    except TypeError: provider = static.getInfoString(pkey) or ""
            except Exception:
                pass
        if orbital is None:
            try:
                raw = int(ref.getUnsignedData(4))
                orbital = (raw >> 16) & 0xFFFF
                if orbital == 0xFFFF: orbital = None
            except Exception:
                pass
        if orbital is not None:
            try:
                from Components.NimManager import nimmanager
                sat_name = str(nimmanager.getSatDescription(int(orbital)) or "")
            except Exception:
                sat_name = ""
        return provider, orbital, sat_name

    def _load_health(self):
        try:
            if not os.path.isfile(self.health_path):
                return {}
            with open(self.health_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_health(self):
        try:
            directory = os.path.dirname(self.health_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
            items = list((self.stream_health or {}).items())
            if len(items) > self.HEALTH_MAX_ENTRIES:
                items.sort(key=lambda kv: max(float((kv[1] or {}).get("last_success") or 0), float((kv[1] or {}).get("last_failure") or 0)), reverse=True)
                self.stream_health = dict(items[:self.HEALTH_MAX_ENTRIES])
            tmp = self.health_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(self.stream_health, handle, ensure_ascii=False, separators=(",", ":"))
            try: os.chmod(tmp, 0o600)
            except Exception: pass
            os.replace(tmp, self.health_path)
            try: os.chmod(self.health_path, 0o600)
            except Exception: pass
        except Exception as err:
            self._log("HEALTH_SAVE_ERROR", str(err))

    def _build_server_mode_stats(self):
        stats = {}
        try:
            for rec in (self.stream_health or {}).values():
                if not isinstance(rec, dict):
                    continue
                sid = str(rec.get("server_id") or "")
                mode = str(rec.get("preferred_mode") or "")
                if not sid or mode not in ("4097", "5002"):
                    continue
                bucket = stats.setdefault(sid, {"4097": [0, 0.0], "5002": [0, 0.0]})
                weight = max(1, int(rec.get("successes") or 1))
                latency = float(rec.get("latency_ms") or 0)
                bucket[mode][0] += weight
                if latency > 0:
                    bucket[mode][1] += latency * weight
        except Exception:
            return {}
        return stats

    def _server_preferred_mode(self, channel):
        try:
            sid = str((channel or {}).get("server_id") or "")
            bucket = self.server_mode_stats.get(sid) or {}
            choices = []
            for mode in ("4097", "5002"):
                count, total_latency = bucket.get(mode, [0, 0.0])
                if count:
                    avg = (float(total_latency) / float(count)) if total_latency else 99999.0
                    choices.append((int(count), -avg, mode))
            if choices:
                choices.sort(reverse=True)
                return choices[0][2]
        except Exception:
            pass
        return ""

    def _update_server_mode_stats(self, channel, mode, latency_ms=0):
        if mode not in ("4097", "5002"):
            return
        sid = str((channel or {}).get("server_id") or "")
        if not sid:
            return
        bucket = self.server_mode_stats.setdefault(sid, {"4097": [0, 0.0], "5002": [0, 0.0]})
        bucket[mode][0] += 1
        if latency_ms:
            bucket[mode][1] += float(latency_ms)

    def _schedule_health_save(self, delay_ms=None):
        """Debounce health persistence well outside the zap/remote-control hot path."""
        self.health_dirty = True
        delay = self.DEFERRED_STATE_SAVE_MS if delay_ms is None else max(1000, int(delay_ms))
        try:
            # start() re-arms the one-shot timer, so repeated zaps batch into one write.
            self.health_flush_timer.start(delay, True)
        except Exception:
            # Keep RAM state and persist on shutdown rather than blocking the GUI synchronously.
            pass

    def _flush_health(self):
        if not self.health_dirty:
            return
        self.health_dirty = False
        self._save_health()

    def _apply_health_to_catalog(self):
        if not self.catalog or not self.catalog.channels or not self.stream_health:
            return
        now = time.time()
        for fingerprint, rec in list(self.stream_health.items()):
            if not isinstance(rec, dict):
                continue
            try:
                width = int(rec.get("width") or 0); height = int(rec.get("height") or 0)
                observed_at = float(rec.get("quality_observed_at") or rec.get("last_success") or 0)
            except Exception:
                width = height = 0; observed_at = 0.0
            # A provider can change the real stream behind an unchanged Xtream id. Stale
            # measurements must not permanently force candidate ordering or learned mapping.
            if observed_at > 0 and (now - observed_at) > self.QUALITY_OBSERVATION_TTL_S:
                continue
            if width > 0 and height > 0:
                self.catalog.set_observed_quality(fingerprint, width, height)
                try:
                    hdr = str(rec.get("hdr") or "")
                    if hdr:
                        ch = self.catalog.find_fingerprint(fingerprint)
                        if ch is not None:
                            ch["actual_hdr"] = hdr
                except Exception:
                    pass

    def _record_health(self, channel, success, reason="", width=0, height=0, mode="", latency_ms=0, evidence=""):
        """Separate a transport-ready marker from actual decoder evidence.

        TS marker confirms 188-byte MPEG-TS packets only. Do not learn that its
        player decoded video, even though the existing fast zap can proceed.
        """
        if not channel:
            return
        fingerprint = channel_fingerprint(channel)
        rec = dict(self.stream_health.get(fingerprint) or {})
        rec["name"] = channel.get("name", "")
        rec["server_id"] = channel.get("server_id", "")
        rec["server_label"] = channel.get("server_label", "")
        now = time.time()
        if success:
            rec["last_success"] = now
            rec["successes"] = int(rec.get("successes") or 0) + 1
            rec["last_failure_reason"] = ""
            provisional = (evidence == "validated-ts-data")
            rec["last_success_evidence"] = "ts-ready" if provisional else ("decoder-video" if evidence else "unclassified")
            if provisional:
                rec["last_ts_ready"] = now
                rec["ts_ready_count"] = int(rec.get("ts_ready_count") or 0) + 1
            elif mode in ("dvb", "4097", "5002") and evidence:
                rec["preferred_mode"] = mode
                rec["preferred_mode_verified_at"] = now
                rec["decoder_confirmed_at"] = now
                rec["decoder_confirmed_count"] = int(rec.get("decoder_confirmed_count") or 0) + 1
                if mode in ("4097", "5002"):
                    self._update_server_mode_stats(channel, mode, latency_ms)
            if latency_ms:
                try:
                    old = float(rec.get("latency_ms") or 0)
                    rec["latency_ms"] = int(latency_ms if old <= 0 else (old * 0.65 + float(latency_ms) * 0.35))
                except Exception:
                    rec["latency_ms"] = int(latency_ms)
            if width and height:
                rec["width"] = int(width); rec["height"] = int(height)
                rec["quality_observed_at"] = now
                label, rank = quality_from_dimensions(width, height)
                rec["quality"] = label; rec["quality_rank"] = rank
                # The ranked candidate may be a freshly enriched copy of an older snapshot
                # record. Keep the active object in sync as well as the catalogue index.
                try:
                    channel["actual_width"] = int(width); channel["actual_height"] = int(height)
                    channel["quality"] = label; channel["quality_rank"] = rank; channel["quality_source"] = "observed"
                except Exception:
                    pass
                try:
                    self.catalog.set_observed_quality(fingerprint, width, height)
                except Exception:
                    pass
        else:
            rec["last_failure"] = now
            rec["failures"] = int(rec.get("failures") or 0) + 1
            rec["last_failure_reason"] = str(reason or "")
        self.stream_health[fingerprint] = rec
        self._schedule_health_save()

    def _health_blocked(self, channel):
        try:
            fingerprint = channel_fingerprint(channel)
            if fingerprint in self.failed_candidate_ids:
                return True
            rec = self.stream_health.get(fingerprint) or {}
            lf = float(rec.get("last_failure") or 0); ls = float(rec.get("last_success") or 0)
            return bool(lf > ls and (time.time() - lf) < self.HEALTH_COOLDOWN_S)
        except Exception:
            return False

    def _load_overrides(self):
        try:
            mtime = os.path.getmtime(self.override_path) if os.path.isfile(self.override_path) else None
            if mtime == self._override_mtime:
                return self._override_cache
            if mtime is None:
                self._override_cache = {}; self._override_mtime = None; return self._override_cache
            with open(self.override_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self._override_cache = data if isinstance(data, dict) else {}
            self._override_mtime = mtime
            return self._override_cache
        except Exception:
            return self._override_cache

    def invalidate_overrides(self):
        self._override_mtime = None
        self.direct_mapping_cache = None; self.direct_mapping_source = ""
        self.direct_hot_cache.clear(); self.direct_hot_order.clear()

    def _load_user_rejections(self):
        try:
            mtime = os.path.getmtime(self.rejected_path) if os.path.isfile(self.rejected_path) else None
            if mtime == self._rejected_mtime:
                return self._rejected_cache
            if mtime is None:
                self._rejected_cache = {}; self._rejected_mtime = None; return self._rejected_cache
            with open(self.rejected_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self._rejected_cache = data if isinstance(data, dict) else {}
            self._rejected_mtime = mtime
            return self._rejected_cache
        except Exception:
            return self._rejected_cache

    def invalidate_user_rejections(self):
        self._rejected_mtime = None
        self.direct_mapping_cache = None; self.direct_mapping_source = ""
        self.direct_hot_cache.clear(); self.direct_hot_order.clear()

    def _user_rejected_ids(self):
        try:
            bucket = self._load_user_rejections().get(sat_service_key(self.current_sat_ref_string), {})
            items = bucket.get("items", {}) if isinstance(bucket, dict) else {}
            return set(items.keys()) if isinstance(items, dict) else set()
        except Exception:
            return set()

    def _r80_user_unmapped_guard(self, stage):
        """A user UNMAP is a per-SAT veto of *all* automatic IPTV playback.

        Reject older direct-hot, background SmartMatch and retry candidates
        until an explicit new GREEN lock replaces the marker. No global reset.
        """
        key = sat_service_key(self.current_sat_ref_string)
        rec = self._load_overrides().get(key)
        if not isinstance(rec, dict) or not rec.get("user_unmapped"):
            return False
        self.direct_mapping_cache = None
        self.direct_mapping_source = ""
        self._direct_hot_drop_current()
        self.candidate_plan = []
        self.pending_match = None
        self.retry_pending = False
        self.retry_kind = ""
        self.smartmatch_pending = None
        self.smartmatch_result = None
        self.smartmatch_generation += 1
        try: self.retry_timer.stop()
        except Exception: pass
        try: self.smartmatch_timer.stop()
        except Exception: pass
        self._set_state("USER_UNMAPPED", "User UNMAP blocks old IPTV candidates until GREEN re-lock")
        self._log("USER_UNMAPPED_BLOCK", "sat=%r stage=%s" % (key, stage))
        return True

    def _find_override(self):
        key = sat_service_key(self.current_sat_ref_string)
        item = self._load_overrides().get(key)
        if not isinstance(item, dict): return None
        wanted = item.get("channel_id", "")
        wanted_name = normalize_name(item.get("name", ""))
        if wanted:
            found = self.catalog.find_fingerprint(wanted)
            # A user REJECT is the final scoped veto.  Normally the UI removes a matching
            # manual lock when creating it, but keep this guard for stale/hand-edited files.
            if found is not None and wanted in self._user_rejected_ids():
                self._log("USER_REJECT_SKIP", "manual/override source blocked iptv='%s'" % found.get("name", ""))
                return None
            # A manual lock is an exact source decision. Never silently jump to another
            # server merely because the same channel name exists there after a refresh.
            return found
        # Backward compatibility for very old override files that did not store a fingerprint.
        if wanted_name:
            exact = self.catalog._exact.get(wanted_name, [])
            if exact: return exact[0]
        return None

    def _load_learned_mappings(self):
        try:
            if self.learned_dirty:
                return self._learned_cache
            mtime = os.path.getmtime(self.learned_path) if os.path.isfile(self.learned_path) else None
            if mtime == self._learned_mtime:
                return self._learned_cache
            if mtime is None:
                self._learned_cache = {}; self._learned_mtime = None; return self._learned_cache
            with open(self.learned_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self._learned_cache = data if isinstance(data, dict) else {}
            self._learned_mtime = mtime
            return self._learned_cache
        except Exception:
            return self._learned_cache

    def invalidate_learned_mappings(self):
        # The mapping UI changed persistent state explicitly; discard any pending automatic
        # auto-learn write so it cannot overwrite the user action a few seconds later.
        self.learned_dirty = False
        try: self.learned_flush_timer.stop()
        except Exception: pass
        self._learned_mtime = None
        self.direct_mapping_cache = None; self.direct_mapping_source = ""
        self.direct_hot_cache.clear(); self.direct_hot_order.clear()

    def _load_manual_aliases(self):
        try:
            mtime = os.path.getmtime(self.alias_path) if os.path.isfile(self.alias_path) else None
            if mtime == self._alias_mtime:
                return self._alias_cache
            if mtime is None:
                self._alias_cache = {}; self._alias_mtime = None; return self._alias_cache
            with open(self.alias_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self._alias_cache = data if isinstance(data, dict) else {}
            self._alias_mtime = mtime
            return self._alias_cache
        except Exception:
            return self._alias_cache

    def invalidate_manual_aliases(self):
        self._alias_mtime = None
        self.direct_hot_cache.clear(); self.direct_hot_order.clear()

    def _manual_alias_name(self):
        item = self._load_manual_aliases().get(sat_service_key(self.current_sat_ref_string))
        if not isinstance(item, dict):
            return ""
        return str(item.get("target_name") or item.get("name") or "").strip()

    def _sticky_mapping_enabled(self):
        # AUTO-LOCK/automatic persistent learning is intentionally removed. Manual overrides
        # remain persistent; successful automatic matches may be cached only in RAM.
        return False

    def _find_learned_mapping(self):
        if not self._sticky_mapping_enabled(): return None
        key = sat_service_key(self.current_sat_ref_string)
        item = self._load_learned_mappings().get(key)
        if not isinstance(item, dict): return None
        wanted = item.get("channel_id", "")
        if not wanted: return None
        found = self.catalog.find_fingerprint(wanted)
        if found is None:
            return None
        if wanted in self._user_rejected_ids():
            self._log("USER_REJECT_SKIP", "learned source blocked iptv='%s'" % found.get("name", ""))
            self._remove_learned_mapping()
            return None
        # Learned mappings created by older engines may contain a visually working but wrong
        # service (e.g. generic Sky Sport -> Sky Sport Tennis). Validate ONE candidate only;
        # this is O(1) and keeps the direct-zap benefit while self-healing stale bad mappings.
        try:
            qmode = getattr(getattr(self.cfg, "quality_mode", None), "value", "best")
            if item.get("auto_lock_100"):
                strict_ok, strict_reason, score, details = auto_lock_100_match(
                    self.current_match_name or self.current_sat_name, found, self.sat_context,
                    float(getattr(getattr(self.cfg, "match_threshold", None), "value", 82)), qmode
                )
                if not strict_ok:
                    self._log("AUTO100_VALIDATE_DROP", "sat='%s' iptv='%s' reason=%s" % (
                        self.current_sat_name, found.get("name", ""), strict_reason))
                    self._remove_learned_mapping()
                    return None
            else:
                score, details = match_score_details(
                    self.current_match_name or self.current_sat_name, found, self._user_languages(), self.sat_context, qmode
                )
            identity = float(details.get("name",0)) + float(details.get("equivalence",0)) + float(details.get("variant",0))
            threshold = float(getattr(getattr(self.cfg, "match_threshold", None), "value", 82))
            _qlabel, _qrank, _qsrc = effective_quality_info(found)
            _sat_label, _sat_rank, _sat_src = sat_required_quality(self.current_match_name or self.current_sat_name, 0, 0)
            quality_invalid = self._no_4k_upscale_enabled() and _sat_rank < 600 and _qrank >= 600
            decision = match_decision(score, details, threshold)
            # Learned mappings remain strict on identity, but a controlled ALLOWED rule must
            # survive validation exactly as it did when the mapping was learned.
            if decision not in ("SAFE", "ALLOWED") or identity < 88.0 or quality_invalid:
                self._log("MAPPING_VALIDATE_DROP", "sat='%s' iptv='%s' score=%.1f identity=%.1f decision=%s reason=%s" % (
                    self.current_sat_name, found.get("name",""), score, identity, decision, details.get("reject_reason") or ("4K-upscale-blocked" if quality_invalid else "low-confidence")))
                self._remove_learned_mapping()
                return None
        except Exception as err:
            self._log("MAPPING_VALIDATE_ERR", str(err))
            return None
        try:
            from .core import _enrich_channel
            return _enrich_channel(found)
        except Exception:
            return found

    def _schedule_learned_save(self, delay_ms=None):
        self.learned_dirty = True
        delay = self.DEFERRED_STATE_SAVE_MS if delay_ms is None else max(1000, int(delay_ms))
        try:
            self.learned_flush_timer.start(delay, True)
        except Exception:
            # Automatic sticky mappings are an optimisation only. Never freeze the GUI merely
            # to persist one; shutdown() will make one final best-effort write.
            pass

    def _flush_learned_mappings(self):
        if not self.learned_dirty:
            return
        try:
            directory = os.path.dirname(self.learned_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory)
            data = dict(self._learned_cache or {})
            tmp = self.learned_path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
            try: os.chmod(tmp, 0o600)
            except Exception: pass
            os.replace(tmp, self.learned_path)
            try: os.chmod(self.learned_path, 0o600)
            except Exception: pass
            self.learned_dirty = False
            try: self._learned_mtime = os.path.getmtime(self.learned_path)
            except Exception: self._learned_mtime = None
            self._log("MAPPING_BATCH_SAVE", "entries=%d" % len(data))
        except Exception as err:
            # Keep dirty RAM data for the next idle/shutdown attempt.
            self.learned_dirty = True
            self._log("MAPPING_LEARN_ERR", str(err))

    def _save_learned_mapping(self, channel):
        # A successful, identity-safe first picture becomes a persistent lock for this SAT
        # service. This avoids rescoring the same channel on every later zap/restart.
        if not channel or not self.current_sat_ref_string:
            return
        try:
            details = dict(self.last_details or {})
            identity = float(details.get("name",0)) + float(details.get("equivalence",0)) + float(details.get("variant",0))
            decision = match_decision(float(self.last_score or 0), details, float(getattr(getattr(self.cfg, "match_threshold", None), "value", 82)))
            if decision in ("SAFE", "ALLOWED") and identity >= 90.0:
                key = sat_service_key(self.current_sat_ref_string)
                fingerprint = channel_fingerprint(channel)
                if not key or not fingerprint or fingerprint in self._user_rejected_ids():
                    return
                data = dict(self._load_overrides() or {})
                # An explicit user lock/correction always wins, and an automatic lock is
                # immutable until the user resets it in the mappings screen.
                if key in data:
                    return
                qlabel, qrank, qsource = effective_quality_info(channel)
                rec = {
                    "channel_id": fingerprint,
                    "name": str(channel.get("name") or ""),
                    "source": str(channel.get("source") or ""),
                    "stream_id": str(channel.get("stream_id") or ""),
                    "server_id": str(channel.get("server_id") or ""),
                    "server_role": str(channel.get("server_role") or ""),
                    "server_label": str(channel.get("server_label") or ""),
                    "group": str(channel.get("group") or ""),
                    "sat_ref": self.current_sat_ref_string,
                    "sat_name": str(self.current_sat_name or ""),
                    "locked": True,
                    "auto_best_lock": True,
                    "quality_label": str(qlabel or "AUTO"),
                    "quality_rank": int(qrank or 0),
                    "quality_source": str(qsource or "unknown"),
                    "actual_width": int(channel.get("actual_width") or 0),
                    "actual_height": int(channel.get("actual_height") or 0),
                    "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                }
                data[key] = rec
                directory = os.path.dirname(self.override_path)
                if directory and not os.path.exists(directory):
                    os.makedirs(directory)
                tmp = self.override_path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as handle:
                    json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
                try: os.chmod(tmp, 0o600)
                except Exception: pass
                os.replace(tmp, self.override_path)
                try: os.chmod(self.override_path, 0o600)
                except Exception: pass
                self._override_cache = data
                try: self._override_mtime = os.path.getmtime(self.override_path)
                except Exception: self._override_mtime = None
                self._direct_hot_put(channel, "MANUAL_LOCK")
                self._log("AUTO_BEST_LOCK", "sat='%s' -> iptv='%s' image=%s%s%s evidence=%s" % (
                    self.current_sat_name, channel.get("name", ""),
                    (str(rec["actual_width"]) + "x" + str(rec["actual_height"]) + " ") if rec["actual_width"] and rec["actual_height"] else "",
                    qlabel or "AUTO", "", qsource or "unknown"))
        except Exception:
            pass

    def _remove_learned_mapping(self):
        key = sat_service_key(self.current_sat_ref_string)
        try:
            data = dict(self._load_learned_mappings() or {})
            if key not in data: return False
            del data[key]
            self._learned_cache = data
            self._schedule_learned_save()
            self._direct_hot_drop_current()
            return True
        except Exception:
            return False

    def _r802_strict_manual_pin(self, channel):
        """A user-corrected GREEN lock pins the chosen stream, not its HD alias.

        The persisted override controls this; old generic manual mappings keep
        their established backup behavior. No extra files or global cache writes.
        """
        if not channel:
            return False
        try:
            rec = self._load_overrides().get(sat_service_key(self.current_sat_ref_string))
            return bool(isinstance(rec, dict) and rec.get("forced_correct")
                        and str(rec.get("channel_id") or "") == channel_fingerprint(channel))
        except Exception:
            return False

    def _direct_candidate_plan(self, channel, source="LEARNED"):
        """Build a tiny same-channel replica plan across PRIMARY/BACKUP servers.

        A manual/learned mapping pins the *channel identity*, not a dead server URL.  Exact
        normalized replicas remain O(1); 1.0.10 also admits validated provider-label aliases
        (for example TVE LA 1 <-> LA1) through the bounded cached index so PRIMARY/BACKUP failover
        still works when different servers spell the same public channel differently.
        """
        if not channel:
            return []
        target_name = str(channel.get("name") or "")
        target_norm = normalize_name(target_name)
        direct_fp = channel_fingerprint(channel)
        exact_user_pin = bool(source == "MANUAL_LOCK" and self._r802_strict_manual_pin(channel))
        # Use the *labelled* variant for a manual correction, never a stale
        # receiver-observed quality inherited from a different stream. Missing
        # quality labels permit the exact fingerprint only (fail-closed).
        pin_variant = quality_info(target_name)[1] if exact_user_pin else 0
        try:
            replicas = list(self.catalog._exact.get(target_norm, [])) if target_norm else []
        except Exception:
            replicas = []
        if not any(channel_fingerprint(ch) == direct_fp for ch in replicas):
            replicas.append(channel)

        # 1.0.46 locked/session-fast contract: NEVER run SmartMatch/fuzzy alias scoring in
        # the direct zap path. Exact-normalized PRIMARY/B1/B2 replicas above are O(1). If a
        # session-auto match later loses all exact replicas, normal SmartMatch may recover; a
        # manual lock remains exact and never roams to another identity without user action.

        rejected = self._user_rejected_ids()
        rows = []
        blocked_direct = None
        seen = set()
        for ch in replicas:
            fp = channel_fingerprint(ch)
            if not fp or fp in seen or fp in rejected:
                continue
            seen.add(fp)
            if exact_user_pin and fp != direct_fp:
                # A corrected FHD lock must not silently become HD/SD, even
                # when their names share the same normalized IPTV identity.
                candidate_variant = quality_info(str(ch.get("name") or ""))[1]
                if pin_variant == 300 or candidate_variant != pin_variant:
                    continue
            # Previous health failure may predate the user's new GREEN choice.
            # Give the exact newly corrected pin one fresh attempt each SAT zap;
            # failures *within* this zap still prevent an immediate retry loop.
            if exact_user_pin and fp == direct_fp and fp not in self.failed_candidate_ids:
                blocked = False
            else:
                blocked = self._health_blocked(ch)
            if blocked:
                if fp == direct_fp:
                    blocked_direct = ch
                continue
            qlabel, qrank, _qsource = effective_quality_info(ch)
            if source != "MANUAL_LOCK" and self._no_4k_upscale_enabled() and int(self.target_quality_rank or 0) < 600 and int(qrank or 0) >= 600:
                continue
            priority = int(ch.get("server_priority", 999))
            # Same normalized target identity is already proven by the manual/learned mapping.
            # Keep score 150/148 for UI compatibility and use quality only as a tie-break after
            # server role, preserving PRIMARY -> BACKUP1 -> BACKUP2.
            qr = int(qrank or 0)
            tr = int(self.target_quality_rank or 0)
            if tr >= 700:
                qtier = 0 if qr >= 700 else (1 if qr == 300 else (2 if qr >= 600 else (3 if qr >= 500 else (4 if qr >= 400 else 6))))
            elif tr >= 600:
                qtier = 0 if qr == 600 else (1 if qr == 300 else (2 if qr == 500 else (3 if qr == 400 else 6)))
            elif tr >= 500:
                qtier = 0 if qr == 500 else (1 if qr == 300 else (2 if qr == 400 else (3 if qr > 500 else 6)))
            elif tr >= 400:
                # HD is a minimum target: same-identity FHD/1080 is preferred to HD/720.
                qtier = 0 if qr == 500 else (1 if qr == 400 else (2 if qr == 300 else (3 if qr > 500 else 6)))
            else:
                qtier = 0 if qr == 500 else (1 if qr == 400 else (2 if qr == 300 else (3 if qr > 500 else 4)))
            try:
                rec = self.stream_health.get(fp) or {}
                latency = int(rec.get("latency_ms") or 99999)
            except Exception:
                latency = 99999
            details = {
                "name":100.0, "market":0.0, "language":0.0, "quality":0.0,
                "variant":0.0, "context":0.0, "family":0.0, "equivalence":0.0,
                "penalty":0.0, "reject_reason":"", "allow_reason":"same mapped identity replica",
                "allowed_floor":None, "pinned": source == "MANUAL_LOCK",
                "learned": source == "LEARNED", "direct_source": source,
            }
            rows.append((ch, 150.0 if source == "MANUAL_LOCK" else 148.0, details,
                         (0,0,0,0,qtier,0), priority, latency, 0 if fp == direct_fp else 1))
        # For a manual lock, never erase the user's explicit choice merely because its recent
        # health record is bad and there is no replica.  The normal SAT cooldown still prevents
        # a tight retry loop.  Learned mappings, by contrast, are disposable speed hints.
        if not rows and source == "MANUAL_LOCK" and blocked_direct is not None and direct_fp not in rejected:
            details = {
                "name":100.0, "market":0.0, "language":0.0, "quality":0.0,
                "variant":0.0, "context":0.0, "family":0.0, "equivalence":0.0,
                "penalty":0.0, "reject_reason":"", "allow_reason":"manual lock last resort",
                "allowed_floor":None, "pinned":True, "learned":False, "direct_source":"MANUAL_LOCK",
            }
            rows.append((blocked_direct, 150.0, details, (0,0,0,0,0,0), int(blocked_direct.get("server_priority",999)), 99999, 0))
        if source == "MANUAL_LOCK" and exact_user_pin:
            # A new explicit correction outranks the old health/fast-cache
            # shortcut. Same-variant BACKUP1/BACKUP2 remain after the pin only.
            rows.sort(key=lambda row: (0 if channel_fingerprint(row[0]) == direct_fp else 1,
                                       int(row[4]), int(row[5])))
            self._log("MANUAL_EXACT_PIN", "sat=%r chosen=%r replicas=%d" % (
                self.current_sat_name, target_name, len(rows)))
        elif source == "MANUAL_LOCK":
            # r66-beta: retain saved manual primary unchanged. When recent receiver evidence
            # says primary failed and a backup has actually succeeded, keep the backup hot
            # on later zaps for 15 minutes. Then retry the original on a *future* zap only.
            # Never probe primary in parallel with a playing backup (single-login safe).
            rec = (self.stream_health or {}).get(direct_fp) or {}
            last_fail = float(rec.get("last_failure") or 0)
            last_success = float(rec.get("last_success") or 0)
            bad_primary = bool(last_fail > last_success and 0 <= time.time() - last_fail < 900)
            if bad_primary:
                def _backup_priority(row):
                    ch = row[0]
                    fp = channel_fingerprint(ch)
                    hr = (self.stream_health or {}).get(fp) or {}
                    known_good = (fp != direct_fp and int(hr.get("successes") or 0) > 0 and
                                  float(hr.get("last_success") or 0) >= float(hr.get("last_failure") or 0))
                    return (0 if known_good else 1, int(row[3][4]), int(row[4]), int(row[5]), int(row[6]))
                rows.sort(key=_backup_priority)
            else:
                # Normal proven-fast manual lock ordering remains byte-for-byte the same.
                rows.sort(key=lambda row: (int(row[6]), int(row[3][4]), int(row[4]), int(row[5])))
        else:
            # Learned mappings are disposable speed hints, not a mandate to stay on a lower
            # resolution PRIMARY.  Prefer the best compatible resolution, then server role.
            rows.sort(key=lambda row: (int(row[3][4]), int(row[4]), int(row[5]), int(row[6])))
        return [row[:5] for row in rows[:self.MAX_CANDIDATE_PLAN]]

    @staticmethod
    def _stream_transport_kind(channel):
        """Cheap, deterministic transport classification for the zap hot path.

        Only *confirmed by URL* MPEG-TS is sent through native Enigma2 type 1.  We deliberately
        do not probe the network here because a HEAD/GET probe costs zap time and some IPTV
        servers count it as an extra connection.  HLS/DASH/RTMP/RTSP and ambiguous URLs stay
        with ServiceApp/ExtEplayer3.
        """
        try:
            raw = unquote(str((channel or {}).get("url") or "")).strip().lower()
        except Exception:
            raw = ""
        if not raw:
            return "unknown"
        if raw.startswith(("rtmp://", "rtsp://", "srt://", "rist://", "udp://", "rtp://")):
            return "serviceapp"
        if ".m3u8" in raw or "output=m3u8" in raw or "format=m3u8" in raw:
            return "hls"
        if ".mpd" in raw or "output=dash" in raw or "format=dash" in raw:
            return "dash"
        if re.search(r"\.(?:ts|mpegts)(?:[?#&]|$)", raw):
            return "ts"
        if any(token in raw for token in ("output=ts", "extension=ts", "container=ts", "type=mpegts")):
            return "ts"
        return "unknown"

    @staticmethod
    def _audio_sensitive_stream(channel):
        """Return True for feeds known to be unsafe on SAT-identity native type-1 playback.

        TOD Event Sports 1-14 are multi-program/multi-audio sports feeds that play correctly
        as normal IPTV but can lose audio when forced through the native SAT-identity TS path.
        Keep this deliberately narrow; generic sports channels are not affected.
        """
        try:
            raw = " ".join(str((channel or {}).get(k) or "") for k in ("name", "group", "source", "server_label")).casefold()
        except Exception:
            raw = ""
        # R74_TOD_BEIN_DIRECT_AUDIO: source audio works in direct IPTV
        # but can disappear in SAT-identity native localhost /ts playback.
        # Original TOD EVENT check is preserved.
        try:
            item = channel if isinstance(channel, dict) else {}
            label = " ".join(str(item.get("name") or "").upper().replace(":", " ").split())
            names = ("BEIN SPORTS ", "BEIN SPORT ", "BEIN SPORTS4K ")
            ar_bein = any(label.startswith("AR " + stem) for stem in names)
            bein = ar_bein or any(label.startswith(stem) for stem in names)
            origin_fields = ("group", "source", "server_label", "source_name",
                             "server_name", "provider", "provider_name", "source_id")
            labels = [" ".join(str(item.get(k) or "").upper().replace(":", " ").replace("-", " ").split()) for k in origin_fields]
            tod_origin = any(v == "TOD" or v.startswith("TOD ") or v.endswith(" TOD") for v in labels)
        except Exception:
            bein = ar_bein = tod_origin = False
        return bool(("tod" in raw and "event" in raw and "sport" in raw)
                    or (bein and tod_origin) or ar_bein)

    def _audio_safe_serviceapp_required(self, channel):
        if self._audio_sensitive_stream(channel):
            return True
        try:
            rec = (self.stream_health or {}).get(channel_fingerprint(channel)) or {}
            return bool(rec.get("native_audio_missing"))
        except Exception:
            return False

    def _current_player_override(self):
        """Return per-SAT-channel playback lock without adding work to every decoder event."""
        try:
            key = sat_service_key(self.current_sat_ref_string)
            if not key or not os.path.isfile(self.player_override_path):
                return "auto"
            with open(self.player_override_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            rec = data.get(key) if isinstance(data, dict) else None
            mode = rec.get("mode") if isinstance(rec, dict) else rec
            mode = str(mode or "auto").lower()
            return mode if mode in ("auto", "dvb", "serviceapp") else "auto"
        except Exception:
            return "auto"

    def _safe_serviceapp_mode(self):
        """One deterministic ServiceApp choice; never bounce players after picture starts."""
        if bool(getattr(self, "serviceapp_5002_available", False)):
            return "5002"
        if bool(getattr(self, "serviceapp_5001_available", False)):
            return "5001"
        return "4097"

    def _playback_plan(self):
        configured = str(self.cfg.service_type.value)
        lock = self._current_player_override()
        if lock == "dvb":
            return ["dvb"]
        if lock == "serviceapp":
            return [self._safe_serviceapp_mode()]
        if configured == "auto":
            ch = self.pending_match or self.last_match or {}
            # r57 audio-safe routing.  A known/proven native-audio failure must not be sent
            # through type-1 again.  Direct ServiceApp keeps the IPTV program/audio identity
            # intact. Explicit per-channel player locks above still win.
            if self._audio_safe_serviceapp_required(ch):
                mode = self._safe_serviceapp_mode()
                self._log("AUDIO_SAFE_PLAYER", "iptv='%s' direct=%s reason=%s" % (
                    ch.get("name", ""), mode, "TOD_EVENT" if self._audio_sensitive_stream(ch) else "NATIVE_AUDIO_MISSING"))
                return [mode]
            # r68: exact fingerprint mode memory. Never use a mere TS-ready marker as
            # evidence of decoded video. Explicit player overrides and TOD audio safety
            # above take precedence. Do not probe any extra stream during channel zap.
            try:
                rec = (self.stream_health or {}).get(channel_fingerprint(ch)) or {}
                preferred = str(rec.get("preferred_mode") or "")
                verified_at = float(rec.get("preferred_mode_verified_at") or 0)
                last_failed_at = float(rec.get("last_failed_player_at") or 0)
                failed_mode = str(rec.get("last_failed_player") or "")
                if (verified_at > 0 and (time.time() - verified_at) < 86400 and
                        (preferred != failed_mode or verified_at > last_failed_at) and
                        preferred in ("dvb", "4097", "5002")):
                    # Native TS is compatible with .ts (and Xtream IDs) only.
                    transport = self._stream_transport_kind(ch)
                    if preferred == "dvb" and (transport not in ("ts", "unknown") or
                            str(getattr(self.cfg.native_timeshift, "value", "xtream")) == "off" or
                            not bool(getattr(self.cfg.openatv_playback, "value", True))):
                        preferred = ""
                    if preferred == "5002" and not self.serviceapp_5002_available:
                        preferred = ""
                    if preferred:
                        alternate = self._safe_serviceapp_mode() if preferred == "dvb" else "dvb"
                        self._log("PLAYER_VERIFIED_REUSE", "mode=%s evidence=decoder-video iptv='%s'" % (
                            preferred, ch.get("name", "")))
                        return [preferred, alternate] if alternate != preferred else [preferred]
                # A transport-only DVB hint is lower trust: use it only when the
                # exact same IPTV previously failed in ServiceApp, and only briefly.
                ts_at = float(rec.get("last_ts_ready") or 0)
                if (failed_mode in ("5002", "4097") and
                        ts_at > last_failed_at > 0 and (time.time() - ts_at) < 600 and
                        self._stream_transport_kind(ch) == "ts" and
                        str(getattr(self.cfg.native_timeshift, "value", "xtream")) != "off" and
                        bool(getattr(self.cfg.openatv_playback, "value", True))):
                    self._log("PLAYER_TS_HINT_REUSE", "mode=dvb evidence=transport-only iptv='%s'" % ch.get("name", ""))
                    return ["dvb", self._safe_serviceapp_mode()]
            except Exception as err:
                self._log("PLAYER_MEMORY_ERR", str(err))
            # r46 UHD policy: high-bitrate HEVC/4K streams are much more robust when the
            # provider URL goes straight to ServiceApp/ExtEplayer3 instead of traversing the
            # Python localhost TS relay. This also removes relay CPU/copy pressure. The user
            # can still select Native to prioritise native timeshift, or Auto to retain learned
            # r41 behaviour. Manual per-channel player overrides always win above this block.
            try:
                _q_label, _q_rank, _q_source = effective_quality_info(ch)
                _q_rank = max(int(_q_rank or 0), int(self.target_quality_rank or 0))
            except Exception:
                _q_rank = int(self.target_quality_rank or 0)
            try:
                _uhd_policy = str(getattr(self.cfg, "uhd_playback").value or "stable")
            except Exception:
                _uhd_policy = "stable"
            if _q_rank >= 600:
                _service_mode = self._safe_serviceapp_mode()
                if _uhd_policy == "stable":
                    self._log("UHD_PLAYER_POLICY", "quality=%s rank=%d policy=stable first=%s fallback=dvb" % (_q_label, _q_rank, _service_mode))
                    return [_service_mode, "dvb"]
                if _uhd_policy == "native":
                    self._log("UHD_PLAYER_POLICY", "quality=%s rank=%d policy=native first=dvb fallback=%s" % (_q_label, _q_rank, _service_mode))
                    return ["dvb", _service_mode]
            # r41: if this exact IPTV fingerprint has already produced a verified picture via
            # ServiceApp, reuse that proven player first on the next zap.  This removes the
            # repeated ~2 s native-relay failure seen on channels such as beIN SPORTS 2 while
            # leaving never-tested streams on the normal native-timeshift-first policy.
            try:
                rec = (self.stream_health or {}).get(channel_fingerprint(ch)) or {}
                preferred = str(rec.get("preferred_mode") or "")
                last_ok = float(rec.get("last_success") or 0)
                last_fail = float(rec.get("last_failure") or 0)
                if preferred in ("4097", "5002") and last_ok >= last_fail:
                    safe_mode = preferred if preferred != "5002" or bool(getattr(self, "serviceapp_5002_available", False)) else self._safe_serviceapp_mode()
                    self._log("PLAYER_FAST_REUSE", "iptv='%s' mode=%s learned=verified" % (ch.get("name", ""), safe_mode))
                    return [safe_mode, "dvb"] if safe_mode != "dvb" else ["dvb"]
            except Exception:
                pass

            # 1.0.46-r4 STABILIZATION rule:
            #   confirmed MPEG-TS -> native type 1 first for fastest zap + native Timeshift/REC.
            #   Only if that native attempt produces NO decoded video, allow one one-way rescue
            #   through ServiceApp/ExtEplayer3 (or 4097 when ServiceApp is unavailable).
            #   HLS/DASH/unknown stay on ServiceApp directly and never bounce players.
            # This is intentionally not adaptive learning: the selected path never changes after
            # a picture has appeared, so there is no visible post-picture restart.
            kind = self._stream_transport_kind(ch)
            try:
                native_pref = str(getattr(self.cfg, "native_timeshift").value or "xtream")
            except Exception:
                native_pref = "xtream"

            try:
                openatv_native = bool(getattr(self.cfg, "openatv_playback").value)
            except Exception:
                openatv_native = True
            use_native = (openatv_native and native_pref != "off" and kind == "ts")
            if native_pref == "xtream" and kind == "unknown":
                try:
                    raw = unquote(str(ch.get("url") or "")).strip().lower()
                except Exception:
                    raw = ""
                xtream_row = bool(ch.get("stream_id"))
                explicit_non_ts = (".m3u8" in raw or ".mpd" in raw or raw.startswith(("rtmp://", "rtsp://", "srt://", "rist://", "udp://", "rtp://")))
                if openatv_native and xtream_row and not explicit_non_ts:
                    use_native = True

            service_mode = self._safe_serviceapp_mode()
            if use_native:
                return ["dvb", service_mode]
            return [service_mode]
        if configured in ("4097", "5002", "dvb"):
            return [configured]
        return [self._safe_serviceapp_mode()]

    # ------------------------------------------------------------------
    # Manual Preview ownership / recovery (r50)
    # ------------------------------------------------------------------
    def begin_manual_preview(self, restore_ref=""):
        self.manual_preview_active = True
        self.manual_preview_ref = ""
        self.manual_preview_restore_ref = str(restore_ref or self.current_sat_ref_string or "")
        self.manual_preview_started_at = time.time()
        self._set_state("MANUAL_PREVIEW", "Preview Browser active; automatic bridge monitoring paused")
        self._log("MANUAL_PREVIEW_BEGIN", "restore=%s" % str(self.manual_preview_restore_ref or "-")[:90])

    def set_manual_preview_ref(self, ref_string):
        if not self.manual_preview_active:
            return
        self.manual_preview_ref = str(ref_string or "")
        self._log("MANUAL_PREVIEW_REF", "ref=%s" % str(self.manual_preview_ref or "-")[:110])

    def end_manual_preview(self, reason="preview-ended"):
        was_active = bool(self.manual_preview_active)
        self.manual_preview_active = False
        self.manual_preview_ref = ""
        self.manual_preview_restore_ref = ""
        self.manual_preview_started_at = 0.0
        if was_active:
            self._log("MANUAL_PREVIEW_END", str(reason or "preview-ended"))

    def recover_manual_preview(self, reason="stale-preview", restore_preview=False):
        """Clear a stale Preview pause and resume AUTO monitoring.

        If the exact temporary preview ref is still on screen, restore the saved SAT origin.
        Otherwise leave user-owned playback untouched and only re-evaluate a current DVB service.
        """
        if not self.manual_preview_active:
            return False
        expected = str(self.manual_preview_ref or "")
        restore = str(self.manual_preview_restore_ref or self.current_sat_ref_string or "")
        try:
            cur = self.session.nav.getCurrentlyPlayingServiceReference()
            cur_s = cur.toString() if self._ref_valid(cur) else ""
        except Exception:
            cur_s = ""
        self.end_manual_preview(reason=reason)
        self._set_state("PREVIEW_RECOVERY", "Manual preview ended; automatic bridge monitoring resumed")
        self._log("MANUAL_PREVIEW_RECOVER", "reason=%s current=%s expected=%s" % (str(reason), cur_s[:70], expected[:70]))
        if restore_preview and expected and cur_s == expected and restore:
            try:
                ref = eServiceReference(restore)
                try:
                    self.session.nav.playService(ref, adjust=False)
                except TypeError:
                    self.session.nav.playService(ref)
                return True
            except Exception as err:
                self._log("MANUAL_PREVIEW_RESTORE_ERR", str(err))
        # If the receiver is already on DVB, no new evStart may be emitted after clearing the
        # stale flag. Re-run the SAT start path now so AUTO bridge is immediately live again.
        try:
            if cur_s and cur_s.split(":", 1)[0] not in ("4097", "5001", "5002", "5003"):
                self._on_start()
        except Exception as err:
            self._log("MANUAL_PREVIEW_RECHECK_ERR", str(err))
        return True

    # ------------------------------------------------------------------
    # Enigma2 events
    # ------------------------------------------------------------------
    def _on_event(self, event):
        try:
            if getattr(self, "manual_preview_active", False):
                # r50 self-heal: once a concrete preview stream was registered, only that exact
                # ref owns the pause. If a DVB evStart arrives for another service, Preview no
                # longer owns playback even if a screen cleanup callback was skipped.
                if event == iPlayableService.evStart:
                    try:
                        cur = self.session.nav.getCurrentlyPlayingServiceReference()
                        cur_s = cur.toString() if self._ref_valid(cur) else ""
                    except Exception:
                        cur_s = ""
                    expected = str(getattr(self, "manual_preview_ref", "") or "")
                    if expected and cur_s and cur_s != expected and cur_s.split(":", 1)[0] not in ("4097", "5001", "5002", "5003"):
                        self.end_manual_preview(reason="dvb-start-left-preview")
                        self._log("MANUAL_PREVIEW_SELF_HEAL", "DVB evStart resumed AUTO monitor")
                        # Continue into normal evStart handling below.
                    else:
                        self._set_state("MANUAL_PREVIEW", "Temporary IPTV preview active; automatic bridge monitoring paused")
                        self.playback_state = "PREVIEW"
                        return
                else:
                    return
            if event == iPlayableService.evStart:
                self._on_start()
                # A normal SAT evStart after monitor registration makes boot reconciliation
                # unnecessary once the catalogue exists.  IPTV evStart is handled by _on_start.
                if self.catalog.channels and self.current_sat_ref_string and not self.cache_loading:
                    try:
                        cur = self.session.nav.getCurrentlyPlayingServiceReference()
                        cur_string = cur.toString() if self._ref_valid(cur) else ""
                    except Exception:
                        cur_string = ""
                    if cur_string == self.current_sat_ref_string and self.state not in ("CATALOG_LOADING", "CACHE_LOADING", "CACHE_FAST_LOAD", "CACHE_REFRESH"):
                        self.startup_reconcile_pending = False
            elif event == getattr(iPlayableService, "evUpdatedInfo", -10008):
                # Cheap boot hint only.  evUpdatedInfo often arrives after WHERE_SESSIONSTART
                # even when evStart was missed; the timer keeps the actual work serialized.
                if self.startup_reconcile_pending and self.catalog.channels:
                    self._wake_startup_reconcile(40)
                # PMT information becoming available is the exact condition that lets the
                # OpenATV 7.6 native crash guard release early.  Wake its timer on the next
                # mainloop turn instead of waiting for the next 30 ms polling tick; never call
                # playService() re-entrantly from the Enigma2 info callback itself.
                if self.native_pat_guard_pending and self._sat_pmt_pid() > 0:
                    try: self.native_pat_guard_timer.start(1, True)
                    except Exception: pass
            elif event == getattr(iPlayableService, "evVideoSizeChanged", -10001):
                if self.fallback_active:
                    # During playService() the outgoing DVB/previous IPTV service can still emit
                    # a final size notification. Never bless that event as the new stream's
                    # resolution. Only the active IPTV service (evStart/start-guard confirmed)
                    # can make dimensions authoritative.
                    if self.switch_in_progress or not self.iptv_start_seen:
                        self._log("SIZE_EVENT_STALE", "ignored size event during service handover")
                        return
                    self.iptv_video_event_seen = True
                    # A size event is the cleanest proof that width/height belong to this IPTV
                    # decoder. Wake verification immediately; if playback was already accepted
                    # on PTS alone, refresh the session display/quality cache without counting
                    # another success.
                    if self.play_result in ("SUCCESS", "SUCCESS • QUALITY FALLBACK"):
                        width, height = self._video_dimensions()
                        candidate = self.pending_match or self.last_match
                        hdr = self._video_hdr()
                        self._post_success_quality_update(candidate, width, height, hdr=hdr)
                    else:
                        try: self.verify_timer.start(20, True)
                        except Exception: pass
                else:
                    self.video_event_seen = True
            elif event == getattr(iPlayableService, "evTunedIn", -10002):
                if not self.fallback_active: self._log("SAT_TUNED", "channel='%s'" % self.current_sat_name)
            elif event == getattr(iPlayableService, "evEOF", -10007):
                # Ignore EOF released by the SAT/previous service while playService is changing
                # ownership. The IPTV watchdog handles a stream that never becomes active.
                if self.fallback_active and not self.retry_pending and not self.switch_in_progress and self.iptv_start_seen:
                    current = self.session.nav.getCurrentlyPlayingServiceReference()
                    try:
                        cpath = current and current.getPath() or ""
                        ctype = current.toString().split(":", 1)[0] if current is not None else ""
                    except Exception:
                        cpath = ""; ctype = ""
                    if cpath or ctype in ("4097", "5001", "5002", "5003"):
                        try: cstring = current.toString() if current is not None else ""
                        except Exception: cstring = ""
                        if self._is_expected_bridge_iptv(current, cstring, cpath):
                            self._log("IPTV_EOF", "mode=%s iptv='%s'" % (self.current_play_mode, self.pending_match.get("name", "") if self.pending_match else "-"))
                            self._handle_iptv_failure("IPTV stream reached EOF before/while playing")
                        else:
                            self._abandon_bridge_for_manual_iptv(cstring, cpath)
            elif event in (getattr(iPlayableService, "evTuneFailed", -10005), getattr(iPlayableService, "evNoResources", -10006)):
                self._on_tune_failed(event)
            elif event in (getattr(iPlayableService, "evEnd", -10003), getattr(iPlayableService, "evStopped", -10004)):
                self._on_end()
        except Exception as err:
            self.last_error = str(err); self._set_state("ERROR", "Monitor event exception", "event handler"); self._log("EVENT_ERROR", str(err))

    def _on_tune_failed(self, event=None):
        # Some images never reach a normal LOCKED/FAILED tuner_state when the satellite is not
        # receivable. Handle the explicit tune-failed event as a first-class no-signal path.
        if not bool(getattr(getattr(self.cfg, "fallback_no_signal", None), "value", True)):
            return
        ref = self.session.nav.getCurrentlyPlayingServiceReference()
        if not self._ref_valid(ref):
            self._log("TUNE_FAIL_NOREF", "ignored invalid current reference")
            return
        try:
            ref_string = ref.toString()
        except Exception:
            return
        identity_ready = bool(self.current_sat_ref_string and self.current_sat_ref_string == ref_string)
        if identity_ready:
            try: self.timer.stop()
            except Exception: pass
            self.tuner_state = "TUNE_FAILED"
            self.video_state = "SAT tune failed / no signal"
            self._set_state("SAT_NO_SIGNAL", "SAT tune failed; IPTV fallback queued safely", "defer native DVB callback")
            self._log("SAT_TUNE_FAILED", "channel='%s' provider='%s' orbital=%s" % (self.current_sat_name, self.sat_provider, self.sat_context.get("orbital_label", "?")))
        else:
            # Do NOT call _on_start() inside evTuneFailed/eventNoPATEntry. Keep the native
            # callback as close to O(1) as possible; identity/context capture happens after the
            # C++ callback has returned on tune_fail_defer_timer.
            self._log("TUNE_FAIL_CAPTURE_DEFER", "ref=%s" % ref_string[:90])
        # CRITICAL OpenATV 7.6 safety rule: eventNoPATEntry is translated to evTuneFailed
        # synchronously. sendEventNoPatEntry() continues after this Python callback and then
        # dereferences m_channel. Switching to IPTV here can free m_channel and crash Enigma2.
        # Queue the fallback on a later mainloop turn instead.
        self.tune_fail_defer_pending = True
        self.tune_fail_defer_ref = ref_string
        self.tune_fail_defer_event = event
        try:
            self.tune_fail_defer_timer.start(self.TUNE_FAIL_DEFER_MS, True)
            self._log("TUNE_FAIL_DEFER", "channel='%s' delay=%dms event=%s" % (self.current_sat_name, self.TUNE_FAIL_DEFER_MS, event))
        except Exception:
            # Do not fall back synchronously if the timer cannot be armed. Safety wins.
            self.tune_fail_defer_pending = False
            self._log("TUNE_FAIL_DEFER_ERROR", "timer unavailable; keeping SAT to protect native PMT handler")

    def _deferred_tune_failed_fallback(self):
        if not self.tune_fail_defer_pending:
            return
        self.tune_fail_defer_pending = False
        expected = self.tune_fail_defer_ref
        self.tune_fail_defer_ref = ""
        event = self.tune_fail_defer_event
        self.tune_fail_defer_event = None
        if not bool(getattr(getattr(self.cfg, "enabled", None), "value", False)):
            return
        if not bool(getattr(getattr(self.cfg, "fallback_no_signal", None), "value", True)):
            return
        try:
            current = self.session.nav.getCurrentlyPlayingServiceReference()
            current_string = current.toString() if self._ref_valid(current) else ""
        except Exception:
            current_string = ""
        if not expected or current_string != expected:
            self._log("TUNE_FAIL_DEFER_CANCEL", "service changed before deferred fallback")
            return
        if self.current_sat_ref_string != expected:
            # Safe now: the native evTuneFailed callback has returned. Capture the DVB service
            # identity/context using the normal start path, then cancel its generic SAT timer
            # because this explicit tune-failed event already proved no signal.
            self._on_start()
            if self.current_sat_ref_string != expected:
                self._log("TUNE_FAIL_DEFER_CANCEL", "could not capture deferred SAT identity")
                return
            try: self.timer.stop()
            except Exception: pass
        self.tuner_state = "TUNE_FAILED"
        self.video_state = "SAT tune failed / no signal"
        self.counters["no_signal"] += 1
        if self.cache_loading and not self.cache_swap_mode:
            self.startup_reconcile_pending = True
            self._set_state("CATALOG_LOADING", "SAT failed while IPTV catalogue is loading; retry armed")
            self._log("TUNE_FAIL_CACHE_WAIT", "channel='%s'" % self.current_sat_name)
            return
        if not self.catalog.channels:
            self.startup_reconcile_pending = True
            self._set_state("NO_CATALOG", "SAT tune failed and IPTV catalogue is empty")
            return
        self._r745_confirm_no_signal()
        self._log("TUNE_FAIL_DEFER_FIRE", "channel='%s' event=%s native callback returned" % (self.current_sat_name, event))
        self._r745_no_signal_once("NATIVE_TUNE_FAILED")

    def _on_end(self):
        self._stop_probe_timers()
        if self.retry_pending or self.switch_in_progress:
            self._log("STREAM_RELEASE", "service ended during direct IPTV switch/retry"); return
        if self.fallback_active:
            # r28 Timeshift stability: OpenATV can emit a transient evEnd/evStopped while
            # rewiring the native type-1 timeshift pipeline even though the accepted bridge
            # service is still the current service.  Do not turn a working paused/resumed
            # picture into a false STREAM_ENDED state.  A genuine zap is handled by the next
            # evStart; pre-success failures are still owned by the watchdog.
            if self.playback_locked:
                try:
                    cur = self.session.nav.getCurrentlyPlayingServiceReference()
                    cur_s = cur.toString() if self._ref_valid(cur) else ""
                    cur_p = cur.getPath() if self._ref_valid(cur) else ""
                except Exception:
                    cur = None; cur_s = ""; cur_p = ""
                if self._is_expected_bridge_iptv(cur, cur_s, cur_p):
                    self._log("TIMESHIFT_END_IGNORED", "accepted bridge still active; transient end/stopped event")
                    return
            self.play_result = "ENDED"; self.video_state = "IPTV stream ended"
            self._set_state("STREAM_ENDED", "IPTV stream ended or was stopped", "stream end")
            self._log("IPTV_END", "sat='%s' iptv='%s'" % (self.current_sat_name, self.last_match.get("name", "") if self.last_match else ""))

    def _on_start(self):
        self._stop_probe_timers()
        # A genuine new service start begins a new decision cycle.  The lock only protects
        # the already-visible IPTV picture from post-start retries.
        try:
            cur = self.session.nav.getCurrentlyPlayingServiceReference()
            cur_s = cur.toString() if self._ref_valid(cur) else ""
            if not self._is_expected_bridge_iptv(cur, cur_s, (cur.getPath() if self._ref_valid(cur) else "")):
                self.playback_locked = False
        except Exception:
            self.playback_locked = False
        if not self.retry_pending:
            try: self.retry_timer.stop()
            except Exception: pass

        ref = self.session.nav.getCurrentlyPlayingServiceReference()
        if not self._ref_valid(ref):
            self._set_state("NO_SERVICE", "No valid currently playing service"); return
        ref_string = ref.toString(); service_type = ref_string.split(":", 1)[0]
        try: service_path = ref.getPath() or ""
        except Exception: service_path = ""

        if service_type in ("4097", "5001", "5002", "5003") or service_path:
            if self.fallback_active:
                if not self._is_expected_bridge_iptv(ref, ref_string, service_path):
                    # The old state machine treated *any* IPTV evStart as the bridge result. If
                    # the user zapped to a normal IPTV bouquet while a SAT fallback was pending,
                    # its verification/retry timers could hijack that unrelated service.
                    self._abandon_bridge_for_manual_iptv(ref_string, service_path)
                    return
                self.switch_in_progress = False
                self.iptv_start_seen = True
                self.previous_iptv_ref_string = ""; self.previous_iptv_url = ""
                try: self.start_guard_timer.stop()
                except Exception: pass
                self.retry_pending = False; self.playback_state = "IPTV"; self.play_result = "STARTED / VERIFYING"
                self.verify_pts = self._read_pts(); self._arm_video_watchdog()
                self.pts_before = self._format_pts(self.verify_pts); self.pts_after = "-"; self.video_state = "Verifying IPTV video"
                self._set_state("VERIFY_IPTV", "IPTV service started; checking decoded video", "verify IPTV")
                self._log("IPTV_START", "attempt=%d mode=%s path=%s" % (self.fallback_attempt, self.current_play_mode, redact_url(service_path) if service_path else "player-ref"))
                self.verify_timer.start(self._verify_step_ms(), True)
            else:
                self._clear_expected_iptv()
                self.playback_state = "IPTV (manual)"; self._set_state("IPTV_BYPASS", "Current service is already IPTV; SAT monitor bypassed")
            return

        # We are on a real DVB service again: stock frontend/orbital converters should own the
        # InfoBar values until the next IPTV fallback.
        self.switch_in_progress = False
        self.native_pat_guard_pending = False
        try: self.native_pat_guard_timer.stop()
        except Exception: pass
        sat_shadow.deactivate()
        self.frontend_shadow_ref = ""

        # beta25.9 never uses a DVB service as a retry placeholder. Therefore any real DVB
        # evStart means the user/InfoBar has left IPTV and pending retry state must be cancelled.
        # Cancel the timer itself too: otherwise an old player/candidate retry can still wake on
        # the next channel (it would normally no-op, but it is needless mainloop churn/race risk).
        try: self.retry_timer.stop()
        except Exception: pass
        try: self.audio_guard_timer.stop()
        except Exception: pass
        self.audio_guard_round = 0; self.audio_guard_fp = ""; self.forced_retry_mode = ""

        if self.fallback_active or self.retry_pending:
            self._log("STATE_RESET", "new SAT zap resets previous fallback/retry state")
        self.fallback_active = False; self.retry_pending = False; self.retry_kind = ""; self.pending_match = None; self.pending_score = 0.0; self.pending_details = {}
        self._clear_expected_iptv()
        self.candidate_plan = []; self.candidate_index = -1; self.failed_candidate_ids = set()
        self.target_quality = "AUTO"; self.target_quality_rank = 0; self.target_quality_source = "unknown"; self.target_hdr = ""
        self.sat_video_width = 0; self.sat_video_height = 0
        self._reset_iptv_resolution_session()
        self.pre_switch_video_width = 0; self.pre_switch_video_height = 0
        self.resolution_followup_round = 0; self.resolution_followup_fp = ""
        self.sat_audio_languages = []; self.sat_epg_text = ""; self.sat_epg_events = []
        self.fallback_attempt = 0; self.current_sat_ref = ref; self.current_sat_ref_string = ref_string
        self._fallback_crypto_gate = None
        # Do not display the previous channel's successful latency after the current channel fails.
        self.last_first_frame_ms = 0
        self.current_sat_started_at = time.time()
        meta = self.neighbor_meta_cache.pop(ref_string, None)
        if meta and (time.time() - float(meta[4] or 0)) < 45.0:
            self.current_sat_name = str(meta[0] or "")
            self.sat_provider = str(meta[1] or "") or "Unknown"
            self.sat_orbital = meta[2]
            self.sat_satellite = str(meta[3] or "") or "Unknown"
            self._log("SOFT_FCC_META_HIT", "sat='%s' static metadata reused; scoring deferred" % self.current_sat_name)
        else:
            try: self.current_sat_name = ServiceReference(ref).getServiceName() or ""
            except Exception: self.current_sat_name = ""
            self.sat_provider, self.sat_orbital, self.sat_satellite = self._read_sat_identity(ref)
        self.current_match_name = canonical_sat_name(self.current_sat_name, self.sat_provider, self.sat_orbital)
        alias_name = self._manual_alias_name()
        if alias_name:
            self.current_match_name = alias_name
            self._log("ALIAS_HIT", "sat='%s' -> canonical='%s'" % (self.current_sat_name, self.current_match_name))
        # Keep the immediate nav-event path light. Audio tracks, EPG descriptions and full
        # frontend status are only needed if this SAT service actually requires IPTV fallback.
        self.sat_audio_languages = []
        self.sat_epg_text = ""
        self.sat_epg_events = []
        self.sat_deep_context_ready = False
        self.sat_context = infer_sat_context(
            self.current_match_name, self.sat_provider, self.sat_orbital, self.sat_satellite,
            self._user_languages(), audio_languages=[], epg_text=""
        )
        self.sat_context["service_label"] = self.current_sat_name
        if self.failure_cooldown_sat == ref_string and time.time() < self.failure_cooldown_until:
            self.video_event_seen = False; self.playback_state = "SAT"; self.play_result = "COOLDOWN"
            self._set_state("IPTV_FAIL_COOLDOWN", "Recent IPTV failure; keeping SAT briefly to avoid a retry loop", "cooldown")
            self._log("FAIL_COOLDOWN", "channel='%s' remaining=%.1fs" % (self.current_sat_name, max(0.0, self.failure_cooldown_until-time.time())))
            return
        self.video_event_seen = False; self.probe_pts = None; self.probe_round = 0; self.verify_pts = None; self.verify_round = 0
        self.verify_started_at = 0.0; self.verify_deadline = 0.0; self.resolution_deadline = 0.0; self.first_video_evidence_at = 0.0
        self.last_match = None; self.last_score = 0.0; self.last_details = {}; self.last_ranked = []; self.last_match_source = "-"; self.last_error = ""
        self.prefetched_ranked = []; self.prefetched_match_name = ""
        self.crypted_state = "?"; self.tuner_state = "?"; self.pts_before = "-"; self.pts_after = "-"; self.video_state = "Waiting for SAT check"
        self.playback_state = "SAT"; self.play_result = "-"; self.current_play_mode = "-"; self.iptv_start_seen = False; self.iptv_video_event_seen = False; self.start_guard_deadline = 0.0; self.tuner_wait_round = 0
        self.counters["sat_zaps"] += 1
        self._set_state("WAIT_SAT", "Waiting before SAT availability check", "SAT detected")
        self._log("SAT_START", "channel='%s' match='%s' provider='%s' sat='%s' market=%s audio=%s ref=%s" % (
            self.current_sat_name, self.current_match_name, self.sat_provider, self.sat_context.get("orbital_label", "?"),
            self.sat_context.get("market", "?"), "/".join(self.sat_audio_languages) or "-", self.current_sat_ref_string[:90]))

        if not self.cfg.enabled.value:
            self._set_state("DISABLED", "Automatic fallback is disabled"); self._log("SKIP_DISABLED", "channel='%s'" % self.current_sat_name); return
        self._r744_arm_access_followup()
        self._r746_arm_video_sample()
        # Never SmartMatch against a partially built initial JSONL catalogue. A partial index
        # can produce a false NO MATCH or select the wrong backup merely because later rows have
        # not been loaded yet. Cache swaps keep the old complete catalog live and are unaffected.
        if self.cache_loading and not self.cache_swap_mode:
            # Reconcile this exact service as soon as the complete catalogue becomes ready.
            # Without this, a zap during sliced boot loading could remain black until the user
            # zapped away and back because the partial catalogue intentionally cannot match.
            self.startup_reconcile_pending = True
            self.startup_reconcile_attempts = 0
            self._set_state("CATALOG_LOADING", "IPTV catalogue is still loading %d/%s" % (self.cache_loaded, self.cache_expected or "?"))
            self._log("SKIP_CACHE_LOADING", "channel='%s' loaded=%d; reconcile=armed" % (self.current_sat_name, self.cache_loaded))
            return
        if not self.catalog.channels:
            self.startup_reconcile_pending = True
            self._set_state("NO_CATALOG", "IPTV catalogue is empty; refresh IPTV source")
            self._log("SKIP_NO_CATALOG", "channel='%s' reconcile=armed" % self.current_sat_name)
            return
        # Resolve the O(1) sticky/manual mapping once per SAT service and reuse it through
        # the whole switch path. This avoids repeated JSON mtimes + learned validation on the
        # same zap and makes mapped services the fastest path.
        self.direct_mapping_cache = None
        self.direct_mapping_source = ""
        direct = None
        try:
            direct, hot_source = self._direct_hot_get()
            if direct is not None and hot_source in ("MANUAL_LOCK", "LEARNED", "SESSION_FAST"):
                self.direct_mapping_cache = direct
                self.direct_mapping_source = hot_source
                self._log("MAP_HOT_HIT", "sat='%s' source=%s disk=0 score=0" % (self.current_sat_name, hot_source))
            else:
                direct = self._find_override()
                if direct is not None:
                    self.direct_mapping_cache = direct; self.direct_mapping_source = "MANUAL_LOCK"
                else:
                    direct = self._find_learned_mapping()
                    if direct is not None:
                        self.direct_mapping_cache = direct; self.direct_mapping_source = "LEARNED"
                if direct is not None:
                    self._direct_hot_put(direct, self.direct_mapping_source)
        except Exception:
            direct = None
        if direct:
            self.prefetched_ranked = []; self.prefetched_match_name = ""
            self._log("PREFETCH_BYPASS", "mapping already resolved; SmartMatch CPU work skipped")
            if self.direct_mapping_source == "MANUAL_LOCK":
                warm = direct
                try:
                    hr = (self.stream_health or {}).get(channel_fingerprint(direct)) or {}
                    last_bad = float(hr.get("last_failure") or 0)
                    last_ok = float(hr.get("last_success") or 0)
                    if (last_bad > last_ok and 0 <= time.time() - last_bad < 900
                            and not self._r802_strict_manual_pin(direct)):
                        # Only use a replica with confirmed health; never send two
                        # concurrent logins during a source outage.
                        for candidate, _score, _details, _tier, _priority in self._direct_candidate_plan(direct, source="MANUAL_LOCK"):
                            if channel_fingerprint(candidate) == channel_fingerprint(direct):
                                continue
                            chk = (self.stream_health or {}).get(channel_fingerprint(candidate)) or {}
                            if int(chk.get("successes") or 0) > 0 and float(chk.get("last_success") or 0) >= float(chk.get("last_failure") or 0):
                                warm = candidate
                                break
                except Exception:
                    warm = direct
                self._prewarm_locked_stream(warm)
        else:
            # Beta13 ran a fuzzy SmartMatch synchronously on EVERY SAT zap, even when the
            # SAT channel was healthy. On a 37k catalogue that wasted CPU and made channel
            # changes feel heavy. Beta14 defers matching until SAT is actually proven black
            # or unavailable, then uses the bounded identity-first fast index.
            self.prefetched_ranked = []; self.prefetched_match_name = ""
            self._log("PREFETCH_DEFER", "SmartMatch deferred until SAT fallback is required")
        if direct and self._instant_mapped_enabled():
            wait_ms = self.FAST_MAPPED_DELAY_MS
            self._log("FAST_MAP_ARM", "saved mapping -> SAT guard %dms" % wait_ms)
        else:
            wait_ms = max(250, min(int(self.cfg.delay_ms.value), self.FAST_SAT_DELAY_MS) if self._fast_zap_enabled() else int(self.cfg.delay_ms.value))
        self.timer.start(wait_ms, True)
        self._r745_arm_cached_nosignal()

    # ------------------------------------------------------------------
    # Native OpenATV DVB PMT/PAT crash guard
    # ------------------------------------------------------------------
    def _sat_pmt_pid(self):
        """Return a positive PMT PID when Enigma2 has resolved the DVB service, else 0."""
        try:
            service = self.session.nav.getCurrentService()
            info = service and service.info()
            key = getattr(iServiceInformation, "sPMTPID", None)
            if info is None or key is None:
                return 0
            value = int(info.getInfo(key) or 0)
            return value if value > 0 else 0
        except Exception:
            return 0

    def _native_pat_guard_remaining_ms(self):
        """Only slow down DVB->IPTV when PMT is still unresolved on OpenATV."""
        if not self._same_sat_still_playing():
            return 0
        if self._sat_pmt_pid() > 0:
            return 0
        if self.current_sat_started_at <= 0:
            return 0
        elapsed = int(max(0.0, time.time() - self.current_sat_started_at) * 1000.0)
        return max(0, int(self.NATIVE_PAT_GUARD_MS - elapsed))

    def _arm_native_pat_poll(self, remaining):
        # Short eTimer polling stays on the Enigma2 mainloop and performs no network I/O.
        # If PMT appears at 80/150/300 ms we leave immediately instead of sleeping to 1250 ms.
        delay = min(max(20, int(self.NATIVE_PAT_GUARD_POLL_MS)), max(20, int(remaining or 0)))
        try:
            self.native_pat_guard_timer.start(delay, True)
        except Exception as err:
            # Never recurse if an image has a broken timer implementation.  Keeping the DVB
            # service is safer than bypassing the OpenATV no-PAT crash window.
            self._log("DVB_PAT_TIMER_ERR", str(err))

    def _dvb_access_key(self):
        """Return (sid, namespace, tsid, onid) for the current DVB service."""
        try:
            fields = str(self.current_sat_ref_string or "").split(":")
            if len(fields) < 7:
                return None
            return (
                int(fields[3] or "0", 16),
                int(fields[6] or "0", 16),
                int(fields[4] or "0", 16),
                int(fields[5] or "0", 16),
            )
        except Exception:
            return None

    @staticmethod
    def _line_has_nonzero_caid(text):
        try:
            for token in re.findall(r"(?:^|,)C:([0-9A-Fa-f]+)(?=,|$)", str(text or "")):
                try:
                    if int(token, 16) > 0:
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        return False

    def _static_crypted_state_fast(self):
        """Resolve ONLY the current DVB service from lamedb/lamedb5.

        This is intentionally not the old 1.0.40 catalogue-wide parser.  It streams the DVB
        database line-by-line, stops at the first exact service identity and caches the answer.
        Therefore a no-signal encrypted channel can still be recognised when live sIsCrypted is
        unavailable, without doing a full service scan on every zap.
        """
        key = self._dvb_access_key()
        if key is None:
            return None
        # Cheapest path first: some images expose sIsCrypted from static service info even
        # when the live PMT is unavailable. Avoid touching flash when this is authoritative.
        try:
            ref = self.current_sat_ref
            info = eServiceCenter.getInstance().info(ref) if self._ref_valid(ref) else None
            ikey = getattr(iServiceInformation, "sIsCrypted", None)
            if info is not None and ikey is not None:
                try: value = int(info.getInfo(ref, ikey))
                except TypeError: value = int(info.getInfo(ikey))
                if value > 0:
                    self._static_crypto_cache[key] = True
                    return True
            # Some OpenATV service-info implementations can expose static CAIDs even when the
            # live PMT is unavailable. This O(1) native lookup avoids touching lamedb at all.
            ckey = getattr(iServiceInformation, "sCAIDs", None)
            if info is not None and ckey is not None:
                try:
                    try: caids = info.getInfoObject(ref, ckey)
                    except TypeError: caids = info.getInfoObject(ckey)
                    if caids is not None:
                        if isinstance(caids, (list, tuple, set)):
                            values = list(caids)
                        else:
                            values = [caids]
                        for raw in values:
                            try:
                                value = int(raw, 16) if isinstance(raw, str) else int(raw)
                            except Exception:
                                continue
                            if value > 0:
                                self._static_crypto_cache[key] = True
                                return True
                except Exception:
                    pass
        except Exception:
            pass
        paths = [path for path in ("/etc/enigma2/lamedb5", "/etc/enigma2/lamedb") if os.path.isfile(path)]
        signature = []
        for path in paths:
            try:
                st = os.stat(path)
                signature.append((path, int(getattr(st, "st_mtime_ns", int(st.st_mtime * 1000000000))), int(st.st_size)))
            except Exception:
                signature.append((path, 0, 0))
        signature = tuple(signature)
        if signature != self._static_crypto_signature:
            self._static_crypto_signature = signature
            self._static_crypto_cache = {}
        if key in self._static_crypto_cache:
            return self._static_crypto_cache.get(key)

        sid, namespace, tsid, onid = key
        result = None
        started = time.time()
        for path in paths:
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as handle:
                    first = handle.readline()
                    is_v5 = "/5/" in str(first or "").lower()
                    if is_v5:
                        # v5 row: s:SID:NS:TSID:ONID:TYPE:...,C:CAID. While streaming toward
                        # the requested service, retain access bits for rows already seen. The
                        # first unavoidable lookup therefore amortizes later no-signal zaps.
                        for line in handle:
                            if not line.startswith("s:"):
                                continue
                            head = line.split(",", 1)[0].split(":")
                            if len(head) < 5:
                                continue
                            try:
                                row_key = (int(head[1],16), int(head[2],16), int(head[3],16), int(head[4],16))
                            except Exception:
                                continue
                            row_crypted = bool(self._line_has_nonzero_caid(line))
                            self._static_crypto_cache[row_key] = row_crypted
                            if row_key == key:
                                result = row_crypted
                                break
                    else:
                        # v3/v4: identity line, display-name line, provider/cache line. Consume
                        # complete records so each row crossed is cached for future O(1) checks.
                        in_services = False
                        while True:
                            line = handle.readline()
                            if not line:
                                break
                            text = line.strip()
                            if not in_services:
                                if text == "services":
                                    in_services = True
                                continue
                            if not text:
                                continue
                            if text == "end":
                                break
                            parts = text.split(":")
                            if len(parts) < 4:
                                continue
                            try:
                                row_key = (int(parts[0],16), int(parts[1],16), int(parts[2],16), int(parts[3],16))
                            except Exception:
                                continue
                            # Standard lamedb v3/v4 records are three lines: identity, name,
                            # provider/cache. Reading them here costs no more than the old target
                            # scan and prevents rescanning from byte zero for every new channel.
                            try:
                                handle.readline()  # display name
                                cache_line = handle.readline()
                            except Exception:
                                cache_line = ""
                            row_crypted = bool(self._line_has_nonzero_caid(cache_line))
                            self._static_crypto_cache[row_key] = row_crypted
                            if row_key == key:
                                result = row_crypted
                                break
                if result is not None:
                    break
            except Exception:
                continue

        self._static_crypto_cache[key] = result
        elapsed_ms = int((time.time() - started) * 1000.0)
        if elapsed_ms >= 25:
            self._log("CRYPT_DB_LOOKUP", "channel='%s' result=%s cost=%dms targeted=1" % (
                self.current_sat_name, "YES" if result is True else ("NO" if result is False else "?"), elapsed_ms))
        return result

    def _manual_lock_saved_access(self):
        """Return the persisted DVB access flag for a manual lock, when known."""
        if str(self.direct_mapping_source or "") != "MANUAL_LOCK":
            return None
        try:
            item = self._load_overrides().get(sat_service_key(self.current_sat_ref_string)) or {}
            if isinstance(item, dict) and "sat_crypted" in item:
                return bool(item.get("sat_crypted"))
        except Exception:
            pass
        return None

    def _r746_token(self):
        return (str(self.current_sat_ref_string or ""),
                float(self.current_sat_started_at or 0))

    def _r746_native_picture(self):
        """Only current DVB video event or new decoder PTS is trusted.
        A tuner LOCKED and even a valid PMT never counts as a picture.
        """
        if bool(getattr(self,"video_event_seen",False)):
            return True
        if getattr(self,"_r746_sample_token",None)!=self._r746_token():
            return False
        before=getattr(self,"_r746_first_pts",None)
        current=self._read_pts()
        if current is None or current<=0:
            return False
        if before is None:
            # Decoder PTS has just appeared since the early sample: avoid
            # hijacking a SAT channel that may be starting successfully.
            return True
        return bool(current != before)

    def _r746_take_sample(self):
        if not self.cfg.enabled.value or not self._same_sat_still_playing():
            return
        token=self._r746_token()
        if getattr(self,"_r746_sample_token",None)!=token:
            return
        if self.fallback_active or self.switch_in_progress:
            return
        self._r746_first_pts=self._read_pts()
        self._log("DVB_VIDEO_SAMPLE","sat='%s' pts=%s video_event=%d"%(
            self.current_sat_name,"YES" if self._r746_first_pts is not None else "NO",
            int(bool(self.video_event_seen))))

    def _r746_arm_video_sample(self):
        if not self.cfg.enabled.value or not self._same_sat_still_playing():
            return
        self._r746_sample_token=self._r746_token()
        self._r746_first_pts=None
        timer=getattr(self,"_r746_sample_timer",None)
        if timer is None:
            timer=eTimer()
            timer.callback.append(self._r746_take_sample)
            self._r746_sample_timer=timer
        timer.start(850,True)

    def _r746_black_active(self):
        return (getattr(self,"_r746_black_token",None)==self._r746_token()
                and self._same_sat_still_playing()
                and not self._r746_native_picture())

    def _r746_stable_black(self):
        """Requires 2s elapsed and a previous 850ms sample of SAME zap."""
        if not self.cfg.enabled.value or not self._same_sat_still_playing():
            return False
        if self.fallback_active or self.switch_in_progress:
            return False
        if time.time()-float(self.current_sat_started_at or 0)<1.90:
            return False
        if getattr(self,"_r746_sample_token",None)!=self._r746_token():
            return False
        if getattr(self,"_r746_first_pts",None) is None:
            current=self._read_pts()
            if current is not None and current>0:
                return False
        return not self._r746_native_picture()

    # R7417_FTA_SIGNAL_NATIVE_GUARD
    def _r7417_native_keep_reason(self):
        """Classify *current* DVB; never infer reception from SNR percentage.

        Priority: real native decoded picture > cached IPTV mapping.
        Otherwise LOCKED and live FTA with no positive static CAIDs stays SAT,
        even when the black-screen heuristic has not seen decoder PTS yet.
        Native evTuneFailed or no-signal frontend state remains eligible.
        """
        if (not self.current_sat_ref_string or self.fallback_active
                or self.switch_in_progress or not self._same_sat_still_playing()):
            return ""
        try:
            observed=str(self._sat_tuner_state() or "?").upper().strip()
        except Exception:
            observed="?"
        memo=str(self.tuner_state or "?").upper().strip()
        failures=("TUNE_FAILED","FAILED","NO_SIGNAL","NO_LOCK","NOT_LOCKED","UNLOCKED")
        # A native evTuneFailed event is stronger evidence than a stale
        # frontend LOCKED cached on another transponder.
        try:
            native_picture=bool(self._r746_native_picture())
        except Exception:
            native_picture=bool(getattr(self,"video_event_seen",False))
        if native_picture:
            return "NATIVE_PICTURE"
        if observed in failures or memo in failures:
            return ""
        if observed!="LOCKED":
            return ""
        try:
            live=self._is_crypted()
        except Exception:
            live=None
        if live is not False:
            return ""
        # Positive CAIDs mean a temporarily clear *encrypted* service; preserve
        # IPTV fallback if its video is still black. Unknown is NOT positive.
        try:
            static=self._static_crypted_state_fast()
        except Exception:
            static=None
        if static is True:
            return ""
        return "FTA_LOCKED"

    def _r7417_keep_sat(self, stage):
        reason=self._r7417_native_keep_reason()
        if not reason:
            return False
        self.native_pat_guard_pending=False
        self.play_result="KEEP SAT"
        try:
            self.video_state="Native DVB video" if reason=="NATIVE_PICTURE" else "Native FTA LOCKED"
        except Exception:
            pass
        token=(str(self.current_sat_ref_string or ""),
               float(self.current_sat_started_at or 0),str(reason))
        if getattr(self,"_r7417_logged",None)!=token:
            self._r7417_logged=token
            self._log("FTA_SIGNAL_KEEP_SAT",
                      "sat='%s' stage=%s reason=%s"%
                      (self.current_sat_name,stage,reason))
        return True

    def _r745_tp_key(self):
        try:
            fields=str(self.current_sat_ref_string or "").split(":")
            if len(fields)<7:
                return None
            # Enigma2 DVB ref: ... SID : TSID : ONID : NAMESPACE
            return tuple(int(fields[i],16) for i in (4,5,6))
        except Exception:
            return None

    def _r745_confirm_no_signal(self):
        """Remember native proof, never infer from SNR=0 or transient TUNING."""
        key=self._r745_tp_key()
        if key is None or not self._same_sat_still_playing():
            return
        cache=getattr(self,"_r745_bad_transponders",None)
        if cache is None:
            cache={}
            self._r745_bad_transponders=cache
        cache[key]=time.time()
        if len(cache)>64:
            for tp,t in sorted(cache.items(),key=lambda r:r[1])[:-48]:
                cache.pop(tp,None)
        self._log("NO_SIGNAL_PROVEN","sat='%s' source=NATIVE_TUNE_FAILED tp=%r"%(
            self.current_sat_name,key))

    def _r745_cached_failure_active(self):
        token=(str(self.current_sat_ref_string or ""),
               float(self.current_sat_started_at or 0))
        return bool(getattr(self,"_r745_cached_failure_token",None)==token)

    def _r745_discard_bad_tp(self,why):
        key=self._r745_tp_key()
        try:
            getattr(self,"_r745_bad_transponders",{}).pop(key,None)
        except Exception:
            pass
        self._r745_cached_failure_token=None
        self._log("NO_SIGNAL_CACHE_CLEAR","sat='%s' reason=%s"%(
            self.current_sat_name,why))

    def _r745_no_signal_once(self,reason):
        """Never replay a failed no-match every 5s for same SAT tune."""
        token=(str(self.current_sat_ref_string or ""),
               float(self.current_sat_started_at or 0))
        if not token[0] or not self._same_sat_still_playing():
            return False
        if not bool(getattr(self.cfg.fallback_no_signal,"value",True)):
            return False
        if self.fallback_active or self.switch_in_progress:
            return False
        if bool(getattr(self,"video_event_seen",False)):
            return False
        if getattr(self,"_r745_attempt_token",None)==token:
            self._log("NO_SIGNAL_DEDUP","sat='%s' reason=%s"%(self.current_sat_name,reason))
            return False
        self._r745_attempt_token=token
        self._log("NO_SIGNAL_FAST_TRY","sat='%s' reason=%s wait_ms=%d"%(
            self.current_sat_name,reason,
            int(max(0,time.time()-float(self.current_sat_started_at or 0))*1000)))
        self._fallback_with_native_pat_guard()
        return True

    def _r745_arm_cached_nosignal(self):
        """Reuse confirmed failure only for same TP and recent native proof."""
        key=self._r745_tp_key()
        cache=getattr(self,"_r745_bad_transponders",{})
        seen=float(cache.get(key) or 0) if key is not None else 0
        if not seen or time.time()-seen>120:
            if seen:
                cache.pop(key,None)
            return
        if not bool(getattr(self.cfg.fallback_no_signal,"value",True)):
            return
        if self.fallback_active or self.switch_in_progress or self.video_event_seen:
            return
        if getattr(self,"failure_cooldown_sat",None)==self.current_sat_ref_string and time.time()<float(getattr(self,"failure_cooldown_until",0) or 0):
            return
        self._r745_probe_token=(str(self.current_sat_ref_string),
                                float(self.current_sat_started_at or 0))
        self._r745_probe_round=0
        timer=getattr(self,"_r745_probe_timer",None)
        if timer is None:
            timer=eTimer()
            timer.callback.append(self._r745_cached_probe)
            self._r745_probe_timer=timer
        timer.start(180,True)
        self._log("NO_SIGNAL_CACHE_HIT","sat='%s' age=%dms first_probe=180ms"%(
            self.current_sat_name,int(max(0,time.time()-seen)*1000)))

    def _r745_cached_probe(self):
        token=(str(self.current_sat_ref_string or ""),
               float(self.current_sat_started_at or 0))
        if getattr(self,"_r745_probe_token",None)!=token or not self._same_sat_still_playing():
            return
        if not self.cfg.enabled.value or self.fallback_active or self.switch_in_progress:
            return
        if self.video_event_seen:
            self._r745_discard_bad_tp("NATIVE_VIDEO")
            return
        live=str(self._sat_tuner_state() or "?").upper()
        if self._r746_native_picture():
            self._r745_discard_bad_tp("NATIVE_VIDEO_CONFIRMED")
            return
        if live=="LOCKED" or self._sat_pmt_pid()>0:
            self._log("DVB_LOCK_NO_VIDEO","sat='%s' tuner=%s pmt=%d -> retain proof until 2s"%
                (self.current_sat_name,live,self._sat_pmt_pid()))
            return
        # '?' has no trusted frontend state. A transient no-SNR reading
        # alone cannot start IPTV.
        transient=("TUNING","ACQUIRING")
        failed=("TUNE_FAILED","FAILED","NO_SIGNAL","NO_LOCK","NOT_LOCKED","UNLOCKED")
        if live not in transient+failed:
            return
        self._r745_probe_round=int(getattr(self,"_r745_probe_round",0))+1
        if live in transient and self._r745_probe_round<2:
            self._r745_probe_timer.start(250,True)
            return
        # Only a RECENT CONFIRMED failed transponder allows a provisional fast
        # fallback while tuner still says TUNING. Do not rewrite DVB crypt flag.
        self._r745_cached_failure_token=token
        self._r745_no_signal_once("PROVEN_TP_CACHE")

    def _r744_arm_access_followup(self):
        """Schedule exactly one 2s recheck per current DVB service tune."""
        if not self.cfg.enabled.value:
            return
        ref=str(self.current_sat_ref_string or "")
        if not ref:
            return
        self._r744_access_ref=(ref,float(self.current_sat_started_at or 0))
        timer=getattr(self,"_r744_access_timer",None)
        if timer is None:
            timer=eTimer()
            timer.callback.append(self._r744_access_check)
            self._r744_access_timer=timer
        timer.start(2000,True)
        self._log("CRYPT_2S_ARM","sat='%s' first_zap=1 delay=2000ms"%self.current_sat_name)

    def _r744_access_check(self):
        """After 2s, a provisional FTA flag can become crypted=yes.

        Check only the service originally armed. Never switch an unrelated
        station, a live bridge playback, or a failed/closing preview player.
        """
        token=getattr(self,"_r744_access_ref",None)
        current=(str(self.current_sat_ref_string or ""),float(self.current_sat_started_at or 0))
        if not token or token!=current or not self._same_sat_still_playing():
            return
        if (getattr(self,"_r745_attempt_token",None)==current
                or self.fallback_active or self.switch_in_progress
                or not self.cfg.enabled.value):
            return
        tuner=str(self._sat_tuner_state() or self.tuner_state or "?").upper()
        self.tuner_state=tuner
        failures=("TUNE_FAILED","FAILED","NO_SIGNAL","NO_LOCK","NOT_LOCKED","UNLOCKED")
        if tuner in failures and bool(getattr(getattr(self.cfg,"fallback_no_signal",None),"value",True)):
            self._log("FAST_NO_SIGNAL","sat='%s' tuner=%s crypto=ANY"% (self.current_sat_name,tuner))
            self._fallback_crypto_gate=None
            self._fallback_with_native_pat_guard()
            return
        if self._r7417_keep_sat("ACCESS_RECHECK_2S"):
            return
        live=self._is_crypted()
        # Positive live/CAID evidence overrides provisional/saved negative.
        static=self._static_crypted_state_fast() if live is not True else None
        if live is True or static is True:
            self._fallback_crypto_gate=None
            self.crypted_state="YES"
            self._log("CRYPT_AFTER_2S","sat='%s' prior=NO/? now=YES live=%s caids=%s -> IPTV"%(
                self.current_sat_name,live,static))
            self._fallback_with_native_pat_guard()
            return
        if tuner=="LOCKED" and live is False and self._r746_stable_black():
            self._r746_black_token=current
            self._fallback_crypto_gate=None
            self.crypted_state="?"
            self._log("DVB_BLACK_FALLBACK","sat='%s' tuner=LOCKED first=FTA video=ABSENT after=2000ms"%(
                self.current_sat_name))
            self._fallback_with_native_pat_guard()
            return
        if tuner=="LOCKED" and live is False:
            self.crypted_state="NO"
            self._fallback_crypto_gate=False
            self._log("SIGNAL_FTA_KEEP_SAT","sat='%s' tuner=LOCKED crypted=NO after=2000ms"%
                self.current_sat_name)
            return
        self.crypted_state="?"
        self._log("CRYPT_UNKNOWN_2S","sat='%s' tuner=%s live=%s -> keep SAT until evidence"%
            (self.current_sat_name,tuner,live))

    def _r743_crypto_retry(self):
        """Mainloop-only deferred access recheck; never switch a stale SAT ref."""
        token=getattr(self,"_r743_crypto_ref",None)
        now=(str(self.current_sat_ref_string or ""),float(self.current_sat_started_at or 0))
        if token!=now or not self._same_sat_still_playing() or self.fallback_active:
            return
        if bool(getattr(self,"video_event_seen",False)):
            self._log("CRYPT_RECHECK_CANCEL","reason=NATIVE_VIDEO")
            return
        self._fallback_crypto_gate=None
        self._log("CRYPT_RECHECK","sat='%s' elapsed=%dms"%(self.current_sat_name,
            int(max(0,time.time()-float(self.current_sat_started_at or 0))*1000)))
        self._fallback_with_native_pat_guard()

    def _r743_crypto_pending(self):
        if self._r745_cached_failure_active() and self._same_sat_still_playing():
            return False
        """Avoid classifying early sIsCrypted==0 as confirmed FTA.

        The timer runs only for a requested fallback on the CURRENT DVB service;
        ordinary FTA/SAT zapping and catalog scanning remain unaffected.
        """
        try:
            if not bool(self.cfg.only_crypted.value):
                return False
        except Exception:
            return False
        if self.fallback_active or not self._same_sat_still_playing():
            return False
        if getattr(self,"video_event_seen",False):
            return False
        if self._fallback_crypto_gate is True or self._manual_lock_saved_access() is True:
            return False
        # Confirmed encrypted evidence can start IPTV immediately.
        if self._is_crypted() is True:
            self.crypted_state="YES"
            self._fallback_crypto_gate=True
            return False
        elapsed=int(max(0.0,time.time()-float(self.current_sat_started_at or 0))*1000)
        if elapsed>=880 or elapsed<0:
            return False
        # Positive static CAIDs beat a transient live NO. Negative entries are
        # just a hint and must be revalidated after the DVB PMT grace period.
        if self._static_crypted_state_fast() is True:
            self.crypted_state="YES"
            self._fallback_crypto_gate=True
            return False
        self.crypted_state="?"
        self._fallback_crypto_gate=None
        token=(str(self.current_sat_ref_string or ""),float(self.current_sat_started_at or 0))
        self._r743_crypto_ref=token
        timer=getattr(self,"_r743_crypto_timer",None)
        if timer is None:
            timer=eTimer()
            timer.callback.append(self._r743_crypto_retry)
            self._r743_crypto_timer=timer
        delay=max(65,min(175,880-elapsed))
        timer.start(delay,True)
        self.video_state="Waiting for stable DVB CA/PMT access status"
        self.play_result="CRYPT_PENDING"
        if getattr(self,"_r743_crypto_logged",None)!=token:
            self._r743_crypto_logged=token
            self._log("CRYPT_PENDING","sat='%s' live=NO/? db=no-positive elapsed=%dms recheck=%dms"%
                (self.current_sat_name,elapsed,delay))
        return True

    def _encrypted_fallback_allowed_once(self):
        """Central FTA fence used only when a real IPTV fallback is requested.

        Live sIsCrypted is authoritative only when it says encrypted.  On no-signal/black DVB
        services OpenATV can temporarily report 0 or ? before PMT/CA data exists, so 1.0.43 could
        wrongly block beIN and other encrypted services.  For False/unknown we resolve the exact
        DVB service from the cached lamedb row; no catalogue-wide scan is performed.
        """
        try:
            if not bool(self.cfg.only_crypted.value):
                return True
        except Exception:
            pass
        if self._r745_cached_failure_active() and self._same_sat_still_playing():
            live=str(self._sat_tuner_state() or "?").upper()
            if live=="LOCKED" or self._sat_pmt_pid()>0:
                if self._r746_black_active():
                    self._fallback_crypto_gate=True
                    self.crypted_state="?"
                    self._log("DVB_BLACK_ALLOW","sat='%s' recovered lock but no DVB picture"%self.current_sat_name)
                    return True
                return False
            self._fallback_crypto_gate=True
            self.crypted_state="?"
            self._log("NO_SIGNAL_CACHE_ALLOW","sat='%s' tuner=%s crypto=ANY"%
                (self.current_sat_name,live))
            return True

        # R72.4: A definite FAILED satellite tuner cannot deliver SAT video, regardless
        # of FTA / encrypted markers. A failed tune without PMT commonly reports NO/?
        # for CAIDs, which previously produced FTA_FALLBACK_BLOCK indefinitely.
        #
        # This exception is deliberately narrow: it runs only inside a real fallback
        # request, after the native evTuneFailed callback was deferred. It DOES NOT
        # consider SNR=0 on its own (some drivers display 0 even with working video).
        # Nor does it override healthy LOCKED, transitional TUNING/ACQUIRING, or
        # an unknown '?' state. Existing matching and video verification still decide.
        try:
            no_sat_fallback = bool(self.cfg.fallback_no_signal.value)
        except Exception:
            no_sat_fallback = False
        state = str(self.tuner_state or "").upper().strip()
        failed_states = ("TUNE_FAILED", "FAILED", "NO_SIGNAL", "NO_LOCK", "NOT_LOCKED", "UNLOCKED")
        if no_sat_fallback and state in failed_states and not self.fallback_active:
            try:
                same_ref = bool(self.current_sat_ref_string) and self._same_sat_still_playing()
            except Exception:
                same_ref = False
            if same_ref:
                self._fallback_crypto_gate = True
                # Do NOT rewrite the service as encrypted. An FTA SAT source can
                # legitimately use IPTV only when its tuner has actually failed.
                self.crypted_state = "?"
                self._log("NO_SIGNAL_FTA_IPTV_ALLOWED",
                          "channel='%s' tuner=%s mode=SAT_NO_LOCK" %
                          (self.current_sat_name, state))
                return True

        # A stored sat_crypted=False is a historic observation, NOT immutable
        # evidence. Refresh positive live/static CAIDs on every requested
        # fallback before consulting any negative cached result.
        if self._r746_black_active():
            self._fallback_crypto_gate=True
            self.crypted_state="?"
            self._log("DVB_BLACK_ALLOW","sat='%s' tuner=%s no decoded picture -> IPTV"%
                (self.current_sat_name,self.tuner_state))
            return True
        live_state = self._is_crypted()
        if live_state is True:
            self._fallback_crypto_gate = True
            self.crypted_state = "YES"
            return True
        if self._fallback_crypto_gate is True:
            return True

        saved_access = self._manual_lock_saved_access()
        if saved_access is True:
            self._fallback_crypto_gate = True
            self.crypted_state = "YES"
            return True

        static_state = self._static_crypted_state_fast()
        if static_state is True:
            self._fallback_crypto_gate = True
            self.crypted_state = "YES"
            if live_state is False:
                self._log("CRYPT_LIVE_STALE", "channel='%s' live=NO db=YES -> encrypted fallback allowed" % self.current_sat_name)
            return True
        # A user-verified manual IPTV lock is explicit playback intent. A saved
        # negative may have been captured at SAT start before PMT/CA arrived.
        # Only recover after grace, and never override confirmed DVB video.
        # Historical manual sat_crypted=False is NOT authority over fresh
        # positive CA evidence. Without such evidence, a LOCKED + clear
        # signal remains DVB regardless of the saved IPTV candidate.
        if saved_access is False:
            self._fallback_crypto_gate=False
            self.crypted_state="NO"
            return False
        if static_state is False:
            # r41: OpenATV/Vu+ can return a stale clear flag after leaving our IPTV bridge and
            # retuning the original DVB reference.  A MANUAL_LOCK is explicit user authority.
            # New r41 locks also persist sat_crypted=True/False; a confirmed clear lock remains
            # blocked, while legacy/unknown locks are allowed to reopen instead of getting stuck
            # on FTA_FALLBACK_BLOCK.  Automatic mappings never receive this exception.
            if self.direct_mapping_source == "MANUAL_LOCK":
                saved_access = None
                try:
                    rec = self._load_overrides().get(sat_service_key(self.current_sat_ref_string)) or {}
                    if isinstance(rec, dict) and "sat_crypted" in rec:
                        saved_access = bool(rec.get("sat_crypted"))
                except Exception:
                    saved_access = None
                if saved_access is not False:
                    tuner = str(self.tuner_state or self._sat_tuner_state() or "?").upper()
                    self._fallback_crypto_gate = True
                    self.crypted_state = "YES" if saved_access is True else "?"
                    self._log("CRYPT_MANUAL_STALE", "channel='%s' live=%s db=NO saved=%s tuner=%s -> manual fallback allowed" % (
                        self.current_sat_name, "NO" if live_state is False else "?",
                        "YES" if saved_access is True else "?", tuner))
                    return True
            self._fallback_crypto_gate = False
            self.crypted_state = "NO"
            return False

        # Explicit manual lock is the only deliberate override when the DVB database has no
        # usable CA information.  Respect r41's persisted sat_crypted=False when it exists;
        # legacy/unknown manual locks are still allowed so old beIN mappings keep working.
        if self.direct_mapping_source == "MANUAL_LOCK":
            saved_access = None
            try:
                rec = self._load_overrides().get(sat_service_key(self.current_sat_ref_string)) or {}
                if isinstance(rec, dict) and "sat_crypted" in rec:
                    saved_access = bool(rec.get("sat_crypted"))
            except Exception:
                saved_access = None
            if saved_access is False:
                self._fallback_crypto_gate = False
                self.crypted_state = "NO"
                return False
            self._fallback_crypto_gate = True
            self.crypted_state = "YES" if saved_access is True else "?"
            self._log("CRYPT_MANUAL_OVERRIDE", "channel='%s' access=%s manual-lock=1" % (
                self.current_sat_name, "YES" if saved_access is True else "unknown"))
            return True

        # If SAT is genuinely locked and Enigma2 reports clear, trust the live decoder.  This
        # keeps normal FTA channels on satellite even if lamedb is incomplete.
        tuner = str(self.tuner_state or self._sat_tuner_state() or "?").upper()
        if live_state is False and tuner == "LOCKED":
            self._fallback_crypto_gate = False
            self.crypted_state = "NO"
            return False

        self.crypted_state = "?"
        return False

    def _fallback_with_native_pat_guard(self):
        if self._r7417_keep_sat("FALLBACK_REQUEST"):
            return
        # During a first zap, PMT/CA access may still be initializing.
        # A bounded deferred recheck avoids caching a transient NO as true FTA.
        signal=str(self.tuner_state or "").upper().strip()
        no_signal=bool(getattr(getattr(self.cfg,"fallback_no_signal",None),"value",True))
        confirmed_fail=signal in ("TUNE_FAILED","FAILED","NO_SIGNAL","NO_LOCK","NOT_LOCKED","UNLOCKED")
        if self._r745_cached_failure_active() and self._same_sat_still_playing():
            self._log("FAST_NO_SIGNAL_CACHED","sat='%s' tuner=%s crypto=ANY"%(
                self.current_sat_name,signal))
        elif confirmed_fail and no_signal:
            self._log("FAST_NO_SIGNAL","sat='%s' tuner=%s crypto=ANY"% (self.current_sat_name,signal))
        elif self._is_crypted() is True:
            self._log("FAST_SIGNAL_CRYPTED","sat='%s' source=LIVE -> IPTV"%self.current_sat_name)
        elif (signal=="LOCKED" and self._is_crypted() is False
              and self._static_crypted_state_fast() is not True
              and not self._r746_black_active()):
            # The ONE excluded case: native signal confirmed, FTA access.
            # Treat early 0 as PROVISIONAL for two seconds so channels whose
            # CA arrives late can recover without a second zap.
            age=int(max(0.0,time.time()-float(self.current_sat_started_at or 0))*1000)
            self.crypted_state="?" if age<2000 else "NO"
            self._fallback_crypto_gate=None if age<2000 else False
            self.play_result="FTA_RECHECK_2S" if age<2000 else "KEEP SAT"
            if getattr(self,"_r744_fta_status_key",None)!=(self.current_sat_ref_string,self.crypted_state):
                self._r744_fta_status_key=(self.current_sat_ref_string,self.crypted_state)
                self._log("SIGNAL_FTA_PENDING" if age<2000 else "SIGNAL_FTA_KEEP_SAT",
                    "sat='%s' live=NO tuner=LOCKED elapsed=%dms"% (self.current_sat_name,age))
            return
        elif self._r743_crypto_pending():
            return
        if not self._encrypted_fallback_allowed_once():
            self.video_state = "SAT allowed (clear/unknown access)"
            self.play_result = "KEEP SAT"
            self._set_state("SAT_OK", "FTA/unconfirmed encrypted service: IPTV fallback blocked", "keep SAT")
            self._log("FTA_FALLBACK_BLOCK", "channel='%s' crypted=%s" % (self.current_sat_name, self.crypted_state))
            return
        remaining = self._native_pat_guard_remaining_ms()
        if remaining > 0:
            first_arm = not self.native_pat_guard_pending
            self.native_pat_guard_pending = True
            self._set_state("DVB_PAT_GUARD", "Waiting briefly for DVB PMT/PAT teardown safety", "native crash guard")
            if first_arm:
                self._log("DVB_PAT_GUARD", "channel='%s' remaining=%dms pmt=unresolved poll=%dms" % (
                    self.current_sat_name, remaining, self.NATIVE_PAT_GUARD_POLL_MS))
            self._arm_native_pat_poll(remaining)
            return
        self.native_pat_guard_pending = False
        self._fallback_if_matched()

    def _native_pat_guard_fire(self):
        if self._r7417_keep_sat("PAT_GUARD"):
            return
        if not self.native_pat_guard_pending:
            return
        if not self.cfg.enabled.value or not self._same_sat_still_playing():
            self.native_pat_guard_pending = False
            return
        remaining = self._native_pat_guard_remaining_ms()
        if remaining > 0:
            self._arm_native_pat_poll(remaining)
            return
        if self._r745_cached_failure_active():
            if self._r746_native_picture():
                self.native_pat_guard_pending=False
                self._r745_discard_bad_tp("NATIVE_VIDEO_RECOVERED")
                return
            if (str(self._sat_tuner_state() or "?").upper()=="LOCKED"
                    and not self._r746_black_active()):
                # LOCKED without video: R74.4 two-second observer arbitrates.
                self.native_pat_guard_pending=False
                self._log("DVB_LOCK_NO_VIDEO","sat='%s' still black during PMT guard"%self.current_sat_name)
                return
        if (getattr(self,"_r746_black_token",None)==self._r746_token()
                and self._r746_native_picture()):
            self._r746_black_token=None
            self.native_pat_guard_pending=False
            self._log("DVB_BLACK_CANCEL","native video recovered during guard")
            return
        self.native_pat_guard_pending = False
        pmt = self._sat_pmt_pid()
        self._log("DVB_PAT_GUARD_OK", "channel='%s' release=%s" % (
            self.current_sat_name, "PMT_READY" if pmt > 0 else "SAFE_WINDOW"))
        self._fallback_if_matched()

    # ------------------------------------------------------------------
    # SAT detection
    # ------------------------------------------------------------------
    def _read_pts(self):
        for path in ("/proc/stb/vmpeg/0/pts", "/proc/stb/vmpeg/0/pts_pcrscr"):
            try:
                with open(path, "r") as handle: value = handle.read().strip()
                if value: return int(value, 16)
            except Exception:
                continue
        # ServiceApp/ExtEplayer3 can keep the hardware /proc PTS node unavailable while the
        # service-level seek interface still exposes a moving 90kHz position.  Use it only as
        # a fallback so the native Vu+ PTS path remains the fastest/authoritative source.
        try:
            service = self.session.nav.getCurrentService()
            seek = service and service.seek()
            result = seek and seek.getPlayPosition()
            if isinstance(result, (tuple, list)) and len(result) >= 2:
                err = int(result[0] or 0); pos = int(result[1] or 0)
                if err == 0 and pos > 0:
                    return pos
        except Exception:
            pass
        return None

    def _video_dimensions(self):
        try:
            service = self.session.nav.getCurrentService(); info = service and service.info()
            if info:
                width = int(info.getInfo(iServiceInformation.sVideoWidth) or 0)
                height = int(info.getInfo(iServiceInformation.sVideoHeight) or 0)
                if width > 0 and height > 0:
                    return width, height
        except Exception:
            pass
        return 0, 0

    def _video_hdr(self):
        """Read decoded HDR transfer function when this OpenATV build exposes sGamma."""
        try:
            key = getattr(iServiceInformation, "sGamma", None)
            if key is None:
                return ""
            service = self.session.nav.getCurrentService(); info = service and service.info()
            if info is None:
                return ""
            value = int(info.getInfo(key))
            # 0 is an explicit SDR observation and must be retained so an old HDR cache can
            # be cleared when a provider changes the stream behind the same Xtream id.
            return {0: "SDR", 1: "HDR", 2: "HDR10", 3: "HLG"}.get(value, "")
        except Exception:
            return ""

    def _resolution_present(self):
        width, height = self._video_dimensions()
        return bool(width > 0 and height > 0)

    def _reset_iptv_resolution_session(self):
        self.current_iptv_width = 0
        self.current_iptv_height = 0
        self.current_iptv_quality = ""
        self.current_iptv_quality_verified = False
        self.iptv_size_sample = (0, 0)
        self.iptv_size_sample_count = 0
        self.raw_decode_size_sample = (0, 0)
        self.raw_decode_size_count = 0
        self.raw_decode_size_first_at = 0.0

    def _raw_size_decode_evidence(self, now, width, height):
        """Conservative no-event first-frame proof for ServiceApp/HEVC paths.

        Never accepts dimensions identical to the outgoing service because Vu+ drivers can keep
        those stale values for a while.  A new stable size, however, cannot come from that exact
        outgoing decoder state and is safe evidence that the IPTV decoder has produced video.
        """
        try:
            dims = (int(width or 0), int(height or 0))
        except Exception:
            dims = (0, 0)
        if dims[0] <= 0 or dims[1] <= 0:
            self.raw_decode_size_sample = (0, 0)
            self.raw_decode_size_count = 0
            self.raw_decode_size_first_at = 0.0
            return False
        if dims == self.raw_decode_size_sample:
            self.raw_decode_size_count += 1
        else:
            self.raw_decode_size_sample = dims
            self.raw_decode_size_count = 1
            self.raw_decode_size_first_at = float(now)
        previous = (int(self.pre_switch_video_width or 0), int(self.pre_switch_video_height or 0))
        if previous[0] > 0 and previous[1] > 0 and dims == previous:
            return False
        elapsed_ms = int(max(0.0, float(now) - float(self.current_candidate_started_at or now)) * 1000.0)
        return bool(elapsed_ms >= int(self.RAW_SIZE_EVIDENCE_MIN_MS) and
                    self.raw_decode_size_count >= int(self.RAW_SIZE_EVIDENCE_SAMPLES))

    def _fresh_iptv_dimensions(self, now=None):
        """Return only dimensions that plausibly belong to the *current* IPTV decoder.

        Vu+ drivers can expose the previous service's width/height for a few hundred ms after
        playService().  evVideoSizeChanged is authoritative.  Some player builds miss that
        event, so after real IPTV PTS movement we also accept two/three stable samples with a
        longer grace when the dimensions are identical to the pre-switch service.
        """
        now = time.time() if now is None else float(now)
        width, height = self._video_dimensions()
        if width <= 0 or height <= 0:
            self.iptv_size_sample = (0, 0)
            self.iptv_size_sample_count = 0
            return 0, 0, False
        if self.iptv_video_event_seen:
            return width, height, True
        if not self.first_video_evidence_at:
            return 0, 0, False
        dims = (int(width), int(height))
        if dims == self.iptv_size_sample:
            self.iptv_size_sample_count += 1
        else:
            self.iptv_size_sample = dims
            self.iptv_size_sample_count = 1
        elapsed_ms = int(max(0.0, now - self.first_video_evidence_at) * 1000.0)
        same_as_previous = bool(
            self.pre_switch_video_width > 0 and self.pre_switch_video_height > 0 and
            dims == (self.pre_switch_video_width, self.pre_switch_video_height)
        )
        min_ms = self.FRESH_SIZE_SAME_AS_PREVIOUS_MS if same_as_previous else self.FRESH_SIZE_MIN_MS
        min_samples = 3 if same_as_previous else 2
        if elapsed_ms >= min_ms and self.iptv_size_sample_count >= min_samples:
            return dims[0], dims[1], True
        return 0, 0, False

    def _update_resolution_observation(self, channel, width, height, hdr=""):
        """Update resolution only, without counting a second playback success."""
        if not channel or width <= 0 or height <= 0:
            return
        try:
            fingerprint = channel_fingerprint(channel)
            rec = dict(self.stream_health.get(fingerprint) or {})
            label, rank = quality_from_dimensions(width, height)
            rec["name"] = channel.get("name", "")
            rec["server_id"] = channel.get("server_id", "")
            rec["server_label"] = channel.get("server_label", "")
            rec["width"] = int(width); rec["height"] = int(height)
            rec["quality"] = label; rec["quality_rank"] = rank
            rec["quality_observed_at"] = time.time()
            if hdr:
                rec["hdr"] = str(hdr); rec["hdr_observed_at"] = time.time()
            self.stream_health[fingerprint] = rec
            channel["actual_width"] = int(width); channel["actual_height"] = int(height)
            channel["quality"] = label; channel["quality_rank"] = rank; channel["quality_source"] = "observed"
            if hdr:
                channel["actual_hdr"] = str(hdr)
            self.catalog.set_observed_quality(fingerprint, width, height)
            self._schedule_health_save()
        except Exception:
            pass

    def _commit_current_resolution(self, candidate, width, height):
        # Session/UI state only. Persist to Stream Health exactly once on normal playback
        # acceptance; a late evVideoSizeChanged updates history explicitly without counting
        # another success.
        if width <= 0 or height <= 0:
            return
        label, _rank = quality_from_dimensions(width, height)
        self.current_iptv_width = int(width)
        self.current_iptv_height = int(height)
        self.current_iptv_quality = label
        self.current_iptv_quality_verified = True

    def _post_success_quality_update(self, candidate, width, height, hdr=""):
        """Store current verified metadata once, without touching the fast playback path."""
        if not candidate or width <= 0 or height <= 0:
            return False
        if (not self.fallback_active or self.switch_in_progress or
                not self.iptv_start_seen or self.play_result not in
                ("SUCCESS", "SUCCESS • QUALITY FALLBACK")):
            return False
        active = self.pending_match or self.last_match
        if not active or channel_fingerprint(active) != channel_fingerprint(candidate):
            return False
        try:
            ref = self.session.nav.getCurrentlyPlayingServiceReference()
            path = ref.getPath() if ref is not None else ""
            if ref is None or not self._is_expected_bridge_iptv(ref, ref.toString(), path):
                return False
        except Exception:
            return False
        now = time.time()
        started = float(self.current_candidate_started_at or 0)
        dims = (int(width), int(height))
        previous = (int(self.pre_switch_video_width or 0), int(self.pre_switch_video_height or 0))
        if (previous[0] > 0 and previous[1] > 0 and dims == previous and
                started > 0 and 0 <= now - started < 1.3):
            # Old decoder metadata sometimes reaches the new service during handover.
            # Defer metadata only; never delay the picture or make a network request.
            try:
                self.resolution_followup_fp = channel_fingerprint(candidate)
                self.resolution_followup_timer.start(max(150, int((1.35 - (now - started)) * 1000)), True)
            except Exception:
                pass
            return False
        signature = (channel_fingerprint(candidate), str(self.current_play_mode),
                     started, dims, str(hdr or ""))
        if getattr(self, "_late_quality_signature", None) == signature:
            return True
        self._late_quality_signature = signature
        self._commit_current_resolution(candidate, width, height)
        self._update_resolution_observation(candidate, width, height, hdr=hdr)
        try:
            if str(self.current_play_mode) in ("dvb", "4097", "5002"):
                fp = channel_fingerprint(candidate)
                rec = dict((self.stream_health or {}).get(fp) or {})
                rec["preferred_mode"] = str(self.current_play_mode)
                rec["preferred_mode_verified_at"] = time.time()
                rec["decoder_confirmed_at"] = rec["preferred_mode_verified_at"]
                rec["decoder_confirmed_count"] = max(1, int(rec.get("decoder_confirmed_count") or 0))
                rec["last_success_evidence"] = "decoder-video"
                self.stream_health[fp] = rec
                self._schedule_health_save()
                self._log("PLAYER_LATE_VIDEO", "mode=%s size=%dx%d" % (self.current_play_mode, width, height))
        except Exception:
            pass
        _qlabel, qrank = quality_from_dimensions(width, height)
        below_target = bool(self.target_quality_rank > 0 and int(qrank or 0) < int(self.target_quality_rank))
        if below_target:
            self.video_state = "IPTV verified • quality fallback %dx%d" % (width, height)
            self.play_result = "SUCCESS • QUALITY FALLBACK"
            # This is still the verified best candidate for the channel. Keep its actual
            # resolution in the lock so later zaps do not repeat the same search.
            self._log("QUALITY_DEGRADED", "iptv='%s' actual=%dx%d target=%s hdr=%s" % (candidate.get("name", ""), width, height, self.target_quality, hdr or "SDR/unknown"))
            if self.last_match_source not in ("MANUAL_LOCK", "LEARNED"):
                self._save_learned_mapping(candidate)
            return False
        if self.last_match_source not in ("MANUAL_LOCK", "LEARNED"):
            self._save_learned_mapping(candidate)
        return True

    def _schedule_resolution_followup(self, candidate):
        if not candidate:
            return
        try:
            self.resolution_followup_round = 0
            self.resolution_followup_fp = channel_fingerprint(candidate)
            self.resolution_followup_timer.stop()
            self.resolution_followup_timer.start(self.RESOLUTION_FOLLOWUP_FIRST_MS, True)
        except Exception:
            pass

    def _resolution_followup_tick(self):
        if not self.fallback_active or self.play_result not in ("SUCCESS", "SUCCESS • QUALITY FALLBACK"):
            return
        candidate = self.pending_match or self.last_match
        if not candidate or channel_fingerprint(candidate) != self.resolution_followup_fp:
            return
        current = self.session.nav.getCurrentlyPlayingServiceReference()
        try:
            path = current and current.getPath() or ""
            ctype = current.toString().split(":", 1)[0] if current is not None else ""
        except Exception:
            path = ""; ctype = ""
        if current is None or (not path and ctype not in ("4097", "5001", "5002", "5003")):
            return
        try:
            current_string = current.toString()
            if not self._is_expected_bridge_iptv(current, current_string, path):
                return
        except Exception:
            return
        self.resolution_followup_round += 1
        width, height, fresh = self._fresh_iptv_dimensions(time.time())
        if fresh:
            hdr = self._video_hdr()
            self._post_success_quality_update(candidate, width, height, hdr=hdr)
            return
        if self.resolution_followup_round < self.RESOLUTION_FOLLOWUP_MAX_ROUNDS:
            try: self.resolution_followup_timer.start(self.RESOLUTION_FOLLOWUP_STEP_MS, True)
            except Exception: pass
        else:
            self._log("RESOLUTION_LATE", "iptv='%s' picture accepted but decoder size stayed unavailable" % candidate.get("name", ""))

    def _is_crypted(self):
        try:
            service = self.session.nav.getCurrentService(); info = service and service.info()
            if not info: return None
            value = info.getInfo(iServiceInformation.sIsCrypted)
            if value == 1: return True
            if value == 0: return False
        except Exception: pass
        return None

    def _sat_tuner_state(self):
        try:
            service = self.session.nav.getCurrentService(); feinfo = service and service.frontendInfo(); data = feinfo and feinfo.getAll(True)
            if not data: return "?"
            state = str(data.get("tuner_state", "") or "").upper(); return state or "?"
        except Exception: return "?"

    def _same_sat_still_playing(self):
        current = self.session.nav.getCurrentlyPlayingServiceReference()
        return bool(self._ref_valid(current) and self._ref_valid(self.current_sat_ref) and current.toString() == self.current_sat_ref_string)

    def _evaluate(self):
        if not self._same_sat_still_playing() or not self.cfg.enabled.value: return
        # A manually locked or previously verified mapping is already the user's resolved
        # destination.  FCC-inspired fast mode keeps only a tiny 45ms SAT guard and skips the
        # expensive tuner/PTS decision path entirely.  Disable in Settings if SAT should always
        # be re-tested first.
        if self._instant_mapped_enabled():
            direct = self.direct_mapping_cache
            if direct:
                # Refresh the SAT shadow immediately before the fast switch.  evStart can be
                # too early for SNR/tuner-number data on some Vu+ drivers; this second capture
                # costs no network I/O and keeps the InfoBar signal/tuner indicators stable.
                self.tuner_state = self._sat_tuner_state()
                saved_access = self._manual_lock_saved_access()
                if saved_access is True:
                    self._fallback_crypto_gate = True; self.crypted_state = "YES"
                elif saved_access is False:
                    # Negative saved on the first zap is provisional: never
                    # hard-cache FTA before live CA/PMT recheck has settled.
                    self._fallback_crypto_gate = None; self.crypted_state = "?"
                else:
                    crypted = self._is_crypted()
                    self.crypted_state = "YES" if crypted is True else ("NO" if crypted is False else "?")
                self._capture_sat_frontend_shadow()
                self.video_state = "Saved mapping direct fallback"
                self._log("FAST_MAP_FIRE", "sat='%s' tuner=%s -> cached IPTV; SAT PTS probe bypassed" % (self.current_sat_name, self.tuner_state))
                self._fallback_with_native_pat_guard()
                return
        self._set_state("CHECK_SAT", "Checking tuner, encryption and video PTS", "SAT check")
        crypted = self._is_crypted(); self.crypted_state = "YES" if crypted is True else ("NO" if crypted is False else "?")
        self.tuner_state = self._sat_tuner_state()
        self._capture_sat_frontend_shadow()
        self._log("SAT_CHECK", "channel='%s' crypted=%s tuner=%s provider='%s' orbital=%s" % (
            self.current_sat_name, self.crypted_state, self.tuner_state, self.sat_provider, self.sat_context.get("orbital_label", "?")))

        locked = self.tuner_state == "LOCKED"
        no_signal_fallback = bool(getattr(getattr(self.cfg, "fallback_no_signal", None), "value", True))
        # TUNING/ACQUIRING are transitional states, not proof of a missing satellite signal.
        # Give the tuner a short bounded grace period before invoking no-signal fallback.
        if not locked and self.tuner_state in ("TUNING", "ACQUIRING", "SEARCHING") and self.tuner_wait_round < self.TUNER_MAX_RECHECKS:
            self.tuner_wait_round += 1
            self.video_state = "Waiting for SAT tuner lock"
            self._set_state("WAIT_TUNER", "SAT tuner is %s (%d/%d)" % (self.tuner_state, self.tuner_wait_round, self.TUNER_MAX_RECHECKS), "recheck tuner")
            self._log("TUNER_WAIT", "channel='%s' tuner=%s round=%d" % (self.current_sat_name, self.tuner_state, self.tuner_wait_round))
            self.timer.start(self.TUNER_RECHECK_MS, True)
            return
        if not locked and self.tuner_state not in ("?", "UNKNOWN"):
            if no_signal_fallback:
                self.counters["no_signal"] += 1; self.video_state = "SAT no signal / no lock"; self.play_result = "FALLBACK"
                self._set_state("SAT_NO_SIGNAL", "No SAT lock; IPTV fallback allowed", "match IPTV")
                self._log("SAT_NO_SIGNAL", "channel='%s' tuner=%s -> fallback" % (self.current_sat_name, self.tuner_state))
                self._fallback_with_native_pat_guard(); return
            self.video_state = "No SAT tuner lock"; self.play_result = "KEEP SAT"
            self._set_state("NO_TUNER_LOCK", "SAT tuner is not LOCKED; no-signal fallback disabled", "keep SAT")
            self._log("KEEP_NO_LOCK", "channel='%s' tuner=%s" % (self.current_sat_name, self.tuner_state)); return

        # A few Vu+/OpenATV driver paths expose no frontend state at all when a satellite is
        # completely unavailable. Do not treat '?' as healthy: if there is no lock state, no
        # decoder PTS and no resolution, classify it as no-signal and use the static service
        # provider/orbital identity for SmartMatch.
        if not locked and self.tuner_state in ("?", "UNKNOWN") and no_signal_fallback:
            early_pts = self._read_pts()
            if early_pts is None and not self._resolution_present():
                self.counters["no_signal"] += 1; self.video_state = "SAT no frontend lock / no video"; self.play_result = "FALLBACK"
                self._set_state("SAT_NO_SIGNAL", "No tuner state/video; IPTV fallback allowed", "match IPTV")
                self._log("SAT_NO_SIGNAL_UNKNOWN", "channel='%s' provider='%s' orbital=%s" % (self.current_sat_name, self.sat_provider, self.sat_context.get("orbital_label", "?")))
                self._fallback_with_native_pat_guard(); return

        if self.cfg.only_crypted.value and crypted is False:
            self.video_state = "SAT allowed (clear channel)"; self.play_result = "KEEP SAT"
            self._set_state("SAT_OK", "Channel is clear and SAT is available", "keep SAT"); self._log("KEEP_SAT_CLEAR", "channel='%s'" % self.current_sat_name); return

        self.probe_pts = self._read_pts(); self.pts_before = self._format_pts(self.probe_pts); self.pts_after = "-"; self.probe_round = 0
        if self.probe_pts is not None:
            self.video_state = "Sampling SAT PTS"; self._set_state("PROBE_SAT", "Sampling decoder PTS", "PTS probe"); self.probe_timer.start(160, True); return
        if not self.cfg.strict_black_detection.value and (self.video_event_seen or self._resolution_present()):
            self.video_state = "Video event/resolution present"; self.play_result = "KEEP SAT"
            self._set_state("SAT_OK", "SAT video evidence detected without readable PTS", "keep SAT"); self._log("KEEP_SAT_VIDEO", "channel='%s' no_pts=1" % self.current_sat_name); return
        self.video_state = "No SAT video PTS"; self._log("SAT_BLACK", "channel='%s' reason=no_pts" % self.current_sat_name); self._fallback_with_native_pat_guard()

    def _evaluate_probe(self):
        if not self._same_sat_still_playing() or not self.cfg.enabled.value: return
        now_pts = self._read_pts(); self.pts_after = self._format_pts(now_pts)
        if self.probe_pts is not None and now_pts is not None and now_pts != 0 and now_pts != self.probe_pts:
            self.video_state = "SAT PTS advancing"; self.play_result = "KEEP SAT"; self._set_state("SAT_OK", "Decoded SAT video is moving", "keep SAT")
            self._log("KEEP_SAT_PTS", "channel='%s' pts=%s->%s" % (self.current_sat_name, self._format_pts(self.probe_pts), self._format_pts(now_pts))); return
        self.probe_round += 1
        if self.probe_round < 2 and now_pts is not None:
            self.probe_pts = now_pts; self.probe_timer.start(160, True); return
        self.video_state = "SAT PTS frozen"; self._log("SAT_BLACK", "channel='%s' pts_frozen=%s" % (self.current_sat_name, self._format_pts(now_pts))); self._fallback_with_native_pat_guard()

    # ------------------------------------------------------------------
    # SmartMatch / playback / watchdog
    # ------------------------------------------------------------------
    def _sat_service_type_quality(self):
        """Conservative quality hint from the DVB service type in the SAT service reference.

        This is valuable when an encrypted/no-signal service has no trustworthy decoder
        dimensions and its display name omits HD/UHD. OpenATV servicerefs encode STYPE as
        the third field: AVC/MPEG2 HD types identify at least HD, while HEVC 0x1F/0x20 is
        treated as UHD only when the service name itself did not already declare a tier.
        """
        try:
            parts = str(self.current_sat_ref_string or "").split(":")
            if len(parts) < 3:
                return "", 0, ""
            stype = int(parts[2], 16)
        except Exception:
            return "", 0, ""
        if stype == 0x20:
            return "4K/UHD", 600, "dvb-service-type-0x%02X" % stype
        # 0x1F means HEVC television but does not, by itself, prove 2160p/UHD.
        # Leave it unknown unless the SAT name or real decoder dimensions provide the tier.
        if stype == 0x1F:
            return "", 0, "dvb-service-type-hevc"
        if stype in (0x11, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E):
            return "HD", 400, "dvb-service-type-0x%02X" % stype
        return "", 0, ""

    def _prepare_target_quality(self):
        width, height = self._video_dimensions()
        # This method is entered only after SAT is black/no-signal/frozen. Decoder dimensions
        # can therefore belong to the previous IPTV/SAT service on Vu+. For no-signal and
        # explicit quality names, prefer the static SAT service label instead of stale W/H.
        bad_video = any(x in (self.video_state or "").lower() for x in ("no signal", "no sat video", "frozen", "tune failed", "no frontend"))
        if bad_video:
            width = height = 0
        self.sat_video_width = int(width or 0); self.sat_video_height = int(height or 0)
        label, rank, source = sat_required_quality(
            self.current_match_name or self.current_sat_name, self.sat_video_width, self.sat_video_height
        )
        # If the decoder is intentionally ignored because SAT is black/no-signal and the name
        # has no HD/UHD marker, use DVB STYPE as a static floor. This prevents e.g. a nameless
        # AVC-HD service from degrading to an SD IPTV candidate merely because W/H were stale.
        if bad_video and int(rank or 0) <= 300:
            st_label, st_rank, st_source = self._sat_service_type_quality()
            if int(st_rank or 0) > int(rank or 0):
                label, rank, source = st_label, st_rank, st_source
        self.target_quality = label
        self.target_quality_rank = int(rank or 0)
        self.target_quality_source = source
        self.target_hdr = hdr_info(self.current_match_name or self.current_sat_name)[0]
        # If the SAT decoder still exposes authoritative HDR metadata before the switch, use it
        # only as an additional target hint. Name-derived HDR remains available for black services.
        if not self.target_hdr and not bad_video:
            sat_hdr = self._video_hdr()
            if sat_hdr and sat_hdr != "SDR":
                self.target_hdr = sat_hdr
        self.sat_context["target_quality_rank"] = int(self.target_quality_rank or 0)
        self.sat_context["target_quality"] = self.target_quality
        self.sat_context["target_hdr"] = self.target_hdr
        return label, int(rank or 0), source

    def _build_candidate_plan(self, ranked, pinned=None):
        threshold = float(self.cfg.match_threshold.value)
        policy = str(getattr(getattr(self.cfg, "resolution_policy", None), "value", "source_strict"))
        strict_exact = policy == "strict_exact"
        target_rank = int(self.target_quality_rank or 0)
        plan = []
        seen = set()

        if pinned is not None:
            fp = channel_fingerprint(pinned)
            plan.append((pinned, 149.0, {
                "name":100.0, "market":25.0, "language":12.0, "quality":12.0,
                "variant":0.0, "context":0.0, "family":0.0, "equivalence":0.0,
                "penalty":0.0, "reject_reason":"", "allow_reason":"", "allowed_floor":None, "pinned":True,
            }, (0,0,0,0,0,0), -1))
            seen.add(fp)

        user_rejected = self._user_rejected_ids()
        for ch, score, details in ranked or []:
            fp = channel_fingerprint(ch)
            if fp in seen:
                continue
            if fp in user_rejected:
                self._log("USER_REJECT_SKIP", "sat='%s' iptv='%s' role=%s" % (self.current_sat_name, ch.get("name", ""), ch.get("server_role") or "SERVER"))
                continue
            decision = match_decision(score, details, threshold)
            if decision not in ("SAFE", "ALLOWED"):
                # R72.6: very narrow controlled Romanian broadcaster exception.
                # The real Digi 24 case: SAT "Digi 24" on a wrong/inferred
                # orbital-country (Telekom Srbija at 23.5E); IPTV explicitly
                # "RO: DIGI 24 HD". Score 71 is below the global 82, but the
                # service identity and explicit country prefix are exact.
                # Never bypass hard reject (number, feed/audio, variant), and
                # never apply without a DEFINITE failed tuner/no SAT lock.
                # Manual rejected IDs, health and all resolution guards remain.
                sat_label = str(self.current_match_name or self.current_sat_name or "").strip().upper()
                ip_label = str(ch.get("name") or "").strip().upper()
                no_sat_state = str(self.tuner_state or "").upper().strip()
                review_reason = str((details or {}).get("review_reason") or "").lower()
                deny_reason = str((details or {}).get("reject_reason") or "").strip()
                market = str(ch.get("market") or "").upper().strip()
                lang = str(ch.get("language") or "").upper().strip()
                try:
                    no_signal_enabled = bool(self.cfg.fallback_no_signal.value)
                except Exception:
                    no_signal_enabled = False
                ro_digi24 = (
                    sat_label in ("DIGI 24", "DIGI 24 HD")
                    and ip_label in ("RO: DIGI 24 HD", "RO: DIGI 24 FHD")
                    and market in ("", "RO")
                    and lang in ("", "RO")
                    and not deny_reason
                    and (not review_reason or ("market" in review_reason or "bouquet" in review_reason))
                    and 65.0 <= float(score) < float(threshold)
                    and no_signal_enabled
                    and no_sat_state in ("TUNE_FAILED", "FAILED", "NO_SIGNAL", "NO_LOCK", "NOT_LOCKED", "UNLOCKED")
                    and not self.fallback_active
                    and bool(self.current_sat_ref_string)
                    and self._same_sat_still_playing()
                )
                if ro_digi24:
                    decision = "ALLOWED"
                    self._log("DIGI24_RO_NO_SIGNAL_ALLOW",
                              "sat='Digi 24' iptv='%s' score=%.1f global_threshold=%.1f no_lock=1" %
                              (ch.get("name",""), float(score), float(threshold)))
                else:
                    # Ordinary REVIEW stays manual; hard REJECT never auto-plays.
                    continue
            if self._health_blocked(ch):
                self._log("HEALTH_SKIP", "iptv='%s' server=%s recent_failure=1" % (
                    ch.get("name",""), ch.get("server_role") or ch.get("server_label") or "-"))
                continue
            qlabel, qrank, qsource = effective_quality_info(ch)
            # User policy: never auto-upgrade a normal SAT service to a 4K IPTV variant.
            # This prevents TF1 -> TF1 4K and beIN SPORTS 3/4 -> generic beIN 4K.  Manual
            # LOCK remains an explicit override.  A stream named 4K but receiver-measured FHD
            # is treated as FHD because effective_quality_info() trusts observed dimensions.
            if self._no_4k_upscale_enabled() and target_rank < 600 and qrank >= 600:
                self._log("QUALITY_4K_GUARD", "skip iptv='%s' quality=%s target=%s" % (ch.get("name",""), qlabel, self.target_quality))
                continue
            # r68 UHD identity guard. A generically named AUTO/unknown-quality feed
            # is not an automatic substitute for a specifically labelled UHD SAT
            # service. Keep it discoverable in Preview/Manual Mapping instead.
            if (target_rank >= 600 and int(qrank or 0) <= 300 and
                    str(qsource or "").lower() not in ("observed", "receiver")):
                self._log("UHD_UNKNOWN_SKIP", "sat='%s' candidate='%s' quality=%s reason=unverified-generic" % (
                    self.current_sat_name, ch.get("name", ""), qlabel))
                continue
            if strict_exact and target_rank > 0 and qsource == "observed" and qrank < target_rank:
                self._log("QUALITY_SKIP_KNOWN", "iptv='%s' actual=%s target=%s" % (ch.get("name",""), qlabel, self.target_quality))
                continue
            priority = int(ch.get("server_priority", 999))
            # Target-aware quality ladder. For an explicit UHD SAT service an unmeasured exact
            # candidate remains probeable ahead of a KNOWN FHD/720p fallback, while a real UHD
            # candidate wins. This fixes exact-name HD rows outranking available 4K rows.
            if target_rank >= 700:
                qtier = 0 if qrank >= 700 else (1 if qrank == 300 else (2 if qrank >= 600 else (3 if qrank >= 500 else (4 if qrank >= 400 else 6))))
            elif target_rank >= 600:
                qtier = 0 if qrank == 600 else (1 if qrank == 300 else (2 if qrank >= 500 and qrank < 600 else (3 if qrank >= 400 and qrank < 500 else (5 if qrank >= 700 else 6))))
            elif target_rank >= 500:
                qtier = 0 if qrank == 500 else (1 if qrank == 300 else (2 if qrank > 500 else (3 if qrank >= 400 else 6)))
            elif target_rank >= 400:
                # For an HD SAT target, prefer the same channel in FHD/1080 over HD/720.
                # 4K is still filtered above by no_4k_upscale unless the user explicitly disables it.
                qtier = 0 if qrank == 500 else (1 if qrank == 400 else (2 if qrank == 300 else (3 if qrank > 500 else 6)))
            else:
                qtier = 0 if qrank >= 700 else (1 if qrank >= 600 else (2 if qrank >= 500 else (3 if qrank >= 400 else (4 if qrank == 300 else 5))))
            hdr_label, hdr_rank, _hdr_source = effective_hdr_info(ch)
            hdrtier = 0 if (not self.target_hdr or int(hdr_rank or 0) > 0) else 1
            identity = float(details.get("name",0)) + float(details.get("equivalence",0)) + float(details.get("variant",0))
            identity_band = 0 if identity >= 99 else (1 if identity >= 90 else 2)
            # Same-language/source-market candidates beat higher resolution in another language.
            market_score = float(details.get("market", 0)) + float(details.get("context", 0)) + float(details.get("family", 0))
            language_score = float(details.get("language", 0))
            market_tier = 0 if market_score >= 20 else (1 if market_score >= 0 else 2)
            language_tier = 0 if language_score >= 14 else (1 if language_score >= 6 else (2 if language_score >= 0 else 3))
            decision_tier = 0 if decision == "SAFE" else 1
            safe_details = dict(details or {})
            safe_details["decision"] = decision
            seen.add(fp)
            if str((self.sat_context or {}).get("confidence") or "LOW").upper() == "HIGH":
                tier_key = (decision_tier, identity_band, market_tier, language_tier, qtier, hdrtier)
            else:
                # Generic orbital hints are secondary evidence. For international/multi-audio UHD
                # channels, exact target quality is more useful than an arbitrary first country at 13E.
                tier_key = (decision_tier, identity_band, qtier, hdrtier, market_tier, language_tier)
            plan.append((ch, float(score), safe_details, tier_key, priority))

        def health_key(ch):
            """Prefer repeatedly proven streams without letting one lucky probe dominate."""
            try:
                rec = self.stream_health.get(channel_fingerprint(ch)) or {}
                successes = int(rec.get("decoder_confirmed_count") or rec.get("successes") or 0)
                failures = int(rec.get("failures") or 0)
                last_success = float(rec.get("last_success") or 0)
                last_failure = float(rec.get("last_failure") or 0)
                latency = int(rec.get("latency_ms") or 99999)
                if successes >= 2 and last_success >= last_failure:
                    state = 0      # proven good
                elif successes == 0 and failures == 0:
                    state = 1      # unknown: do not punish new streams
                elif last_success >= last_failure and last_success:
                    state = 1      # one recent success, still learning
                else:
                    state = 2      # historically/recently failing
                return state, latency
            except Exception:
                return 1, 99999

        # 1.0.6 failover contract: safety/identity/feed context first, then server role.
        # Among equally safe/compatible feeds we MUST try PRIMARY, then BACKUP1, then BACKUP2.
        # A clearly better market/language identity may still beat a wrong-feed PRIMARY, and
        # recently failed streams are already filtered by _health_blocked() before sorting.
        high_context = str((self.sat_context or {}).get("confidence") or "LOW").upper() == "HIGH"
        def plan_key(row):
            tier = row[3]
            if high_context:
                decision_tier, identity_band, market_tier, language_tier, qtier, hdrtier = tier
            else:
                decision_tier, identity_band, qtier, hdrtier, market_tier, language_tier = tier
            hstate, latency = health_key(row[0])
            # Final policy: once identity/feed/language are safe, an explicit SAT quality
            # target (UHD/FHD/HD) outranks server role. PRIMARY remains preferred among
            # equivalent-quality candidates; health/latency then break remaining ties.
            return (decision_tier, identity_band, market_tier, language_tier,
                    qtier, hdrtier, int(row[4]), hstate, latency, -float(row[1]))
        plan.sort(key=plan_key)
        return plan[:self.MAX_CANDIDATE_PLAN]

    def _activate_candidate(self, index, source="SMART"):
        if index < 0 or index >= len(self.candidate_plan):
            return False
        ch, score, details, _tier, _priority = self.candidate_plan[index]
        old_server = ""
        if self.last_match:
            old_server = self.last_match.get("server_id", "")
        new_server = ch.get("server_id", "")
        if index > 0:
            self.counters["candidate_failovers"] += 1
            if old_server and new_server and old_server != new_server:
                self.counters["server_failovers"] += 1
        self.candidate_index = index
        self.last_match = ch
        self.pending_match = ch
        self.pending_score = score
        self.pending_details = details or {}
        self.last_score = score
        self.last_details = details or {}
        direct_source = str((details or {}).get("direct_source") or "")
        self.last_match_source = direct_source if direct_source in ("MANUAL_LOCK", "LEARNED", "SESSION_FAST") else ("PINNED" if details.get("pinned") else source)
        self.fallback_attempt = 0
        qlabel, _qrank, qsource = effective_quality_info(ch)
        self._log("CANDIDATE_SELECT", "idx=%d/%d role=%s server='%s' iptv='%s' quality=%s(%s) score=%.1f" % (
            index + 1, len(self.candidate_plan),
            ch.get("server_role") or "SERVER",
            ch.get("server_label") or ch.get("source") or "-",
            ch.get("name",""), qlabel, qsource, score))
        return True

    def _queue_background_smartmatch(self, match_name, quality_mode, stage="fast"):
        """Resolve ambiguous live matches without freezing Enigma2 remote/navigation."""
        sat_ref = str(self.current_sat_ref_string or "")
        catalog = self.catalog
        name = str(match_name or "")
        qmode = str(quality_mode or "best")
        stage = "fuzzy" if str(stage) == "fuzzy" else "fast"
        # R75_SMART_NEGATIVE_CACHE: avoid expensive retry on rapid back-and-
        # forth zap for the same NO_MATCH SAT / catalog generation / identity.
        # Never block a manual mapping: that is resolved before this method.
        if stage=="fast":
            import time as _r75_clock
            lookup=(sat_ref,id(catalog),name,qmode)
            recorded=getattr(self,"_r75_negative_match_cache",{}).get(lookup)
            if recorded is not None and _r75_clock.monotonic()-recorded<90.0:
                self.play_result="NO MATCH"
                self._set_state("NO_MATCH",
                     "IPTV not identified (short-lived negative cache)",
                     "no repeated full fuzzy scoring")
                self._log("MATCH_NEGATIVE_CACHE",
                          "sat='%s' max_age=90s no repeated CPU work" %
                          self.current_sat_name)
                return

        # R72.5: Enigma2 may emit evTuneFailed again every ~5s on an unavailable
        # transponder. Reusing the SAME pending worker prevents an endless sequence
        # of generation invalidations, which previously caused fast=0, fuzzy=START,
        # fast=0, fuzzy=START, ... without any fuzzy= DONE or NO_MATCH.
        pending = self.smartmatch_pending
        if isinstance(pending, (tuple, list)) and len(pending) >= 5:
            same_job = (str(pending[1]) == sat_ref and str(pending[2]) == name
                        and str(pending[3]) == qmode)
            higher_stage_inflight = str(pending[4]) == "fuzzy" and stage == "fast"
            same_catalog = getattr(self, "_r725_pending_catalog_id", None) == id(catalog)
            if same_job and same_catalog and (str(pending[4]) == stage or higher_stage_inflight):
                self._log("MATCH_BG_REUSE",
                          "sat='%s' requested=%s already=%s (no restart)" %
                          (self.current_sat_name, stage, pending[4]))
                if self.smartmatch_result is not None:
                    try: self.smartmatch_timer.start(1, True)
                    except Exception: pass
                return

        # Once fuzzy actually finished with NO_MATCH, do not redo CPU-intensive
        # scoring every 5s on a DVB transponder that keeps emitting evTuneFailed.
        # Next genuine zap or new catalog instance invalidates this short cooldown.
        cooldown_key = (sat_ref, id(catalog), getattr(self, "current_sat_started_at", 0))
        if (stage == "fast" and getattr(self, "_r725_no_match_key", None) == cooldown_key
                and time.monotonic() < float(getattr(self, "_r725_no_match_until", 0) or 0)):
            self.play_result = "NO MATCH"
            self._set_state("NO_MATCH",
                            "No safe IPTV match; wait briefly or use Manual Mapping",
                            "do not repeat fuzzy scoring")
            self._log("MATCH_NO_MATCH_REUSE", "sat='%s' cached negative match; no new worker" %
                      self.current_sat_name)
            return

        self.smartmatch_generation += 1
        generation = int(self.smartmatch_generation)
        self._r725_pending_catalog_id = id(catalog)
        languages = list(self._user_languages() or [])
        context = dict(self.sat_context or {})
        self.smartmatch_pending = (generation, sat_ref, name, qmode, stage)
        self.smartmatch_result = None
        self._set_state("MATCHING_BG", "Finding IPTV match without blocking the receiver", "background SmartMatch")
        self._log("MATCH_BG_START", "sat='%s' match='%s' stage=%s budget=%s" % (
            self.current_sat_name, name, stage, "96" if stage=="fuzzy" else "fast-index"))

        def worker():
            started = time.time()
            rows = []; error = ""
            try:
                if stage == "fast":
                    rows = catalog.fast_rank_matches(name, languages, context=context, topn=32, quality_mode=qmode) or []
                else:
                    # R7418_BG_CANCEL_FUZZY: 96/900 maximum detailed
                    # scores and cooperative cancellation on DVB zap/change.
                    # Manual Preview/deep search is NOT budgeted.
                    rows = catalog.rank_matches(
                        name, languages, context=context, topn=32,
                        quality_mode=qmode, candidate_budget=96,
                        should_abort=lambda: (
                            generation != int(self.smartmatch_generation)
                            or sat_ref != str(self.current_sat_ref_string or "")
                            or catalog is not self.catalog)) or []
            except Exception as err:
                error = str(err)
            # Rapid zap cancellation: stale workers neither overwrite current results nor keep
            # a newer poll waiting on an old generation.
            if generation != int(self.smartmatch_generation) or sat_ref != str(self.current_sat_ref_string or ""):
                return
            self.smartmatch_result = (
                generation, sat_ref, name, qmode, stage, rows, error,
                int((time.time() - started) * 1000.0)
            )

        th = threading.Thread(target=worker, name="IPToSatSmartMatch-%s" % stage)
        th.daemon = True
        self.smartmatch_thread = th
        th.start()
        try: self.smartmatch_timer.start(35, True)
        except Exception: pass

    def _smartmatch_poll(self):
        pending = self.smartmatch_pending
        if not pending:
            return
        result = self.smartmatch_result
        if result is None:
            try: self.smartmatch_timer.start(35, True)
            except Exception: pass
            return
        self.smartmatch_result = None
        generation, sat_ref, name, qmode, stage, ranked, error, elapsed_ms = result
        if int(generation) != int(self.smartmatch_generation) or sat_ref != str(self.current_sat_ref_string or ""):
            if self.smartmatch_pending:
                try: self.smartmatch_timer.start(35, True)
                except Exception: pass
            return
        if not self._same_sat_still_playing() or not self.cfg.enabled.value:
            self.smartmatch_pending = None
            return
        if self._r80_user_unmapped_guard("SMARTMATCH_BG"):
            return
        if bool(getattr(self,"manual_preview_active",False)):
            self.smartmatch_pending = None
            return
        # User GREEN correction wins over an earlier background ranking result.
        saved = self._find_override()
        if saved is not None:
            self.smartmatch_pending = None
            self.direct_mapping_cache = saved
            self.direct_mapping_source = "MANUAL_LOCK"
            self._fallback_if_matched()
            return
        if error:
            self._log("MATCH_BG_ERR", "stage=%s %s" % (stage, error))
        plan = self._build_candidate_plan(ranked or [], pinned=None)
        self._log("MATCH_BG_DONE", "sat='%s' stage=%s cost=%dms rows=%d candidates=%d" % (
            self.current_sat_name, stage, int(elapsed_ms or 0), len(ranked or []), len(plan or [])))
        if not plan and stage == "fast":
            # Only pay the broad fuzzy cost if the bounded identity-first lane produced no
            # usable candidate. This is the main r59 CPU saving for rapid channel surfing.
            self._queue_background_smartmatch(name, qmode, stage="fuzzy")
            return
        self.smartmatch_pending = None
        self.last_ranked = ranked or []
        self.candidate_plan = plan
        if not self.candidate_plan:
            self.last_match = None
            self.last_score = ranked[0][1] if ranked else -999.0
            self.last_details = ranked[0][2] if ranked else {}
            self.counters["no_match"] += 1
            self.play_result = "NO MATCH"
            if stage == "fuzzy":
                self._r725_no_match_key = (
                    sat_ref, id(self.catalog), getattr(self, "current_sat_started_at", 0))
                self._r725_no_match_until = time.monotonic() + 45.0
            # R75 negative result bound to SAT identity AND catalog object.
            # New IPTV list swaps the Catalog and invalidates this key.
            # A manual GREEN mapping is resolved ahead of SmartMatch.
            import time as _r75_clock
            cache=getattr(self,"_r75_negative_match_cache",None)
            if not isinstance(cache,dict):
                cache={}
                self._r75_negative_match_cache=cache
            cache[(sat_ref,id(self.catalog),name,qmode)]=_r75_clock.monotonic()
            while len(cache)>64:
                cache.pop(next(iter(cache)))
            self._set_state("NO_MATCH", "No safe IPTV candidate satisfies context/resolution policy", "keep SAT black")
            top = ranked[0][0].get("name", "") if ranked else "-"
            self._log("NO_MATCH", "sat='%s' match='%s' target=%s best='%s' score=%.1f threshold=%s" % (
                self.current_sat_name, self.current_match_name, self.target_quality, top, self.last_score, self.cfg.match_threshold.value))
            return
        self.counters["matches"] += 1
        self._activate_candidate(0)
        self._log("MATCH_PLAN", "sat='%s' provider='%s' market=%s target=%s(%s) candidates=%d primary='%s' bg=%s" % (
            self.current_sat_name, self.sat_provider, self.sat_context.get("market", ""),
            self.target_quality, self.target_quality_source, len(self.candidate_plan),
            self.pending_match.get("server_label") or self.pending_match.get("source") or "-", stage))
        self._play_match(self.pending_match, self.pending_score, retry=False)

    def _fallback_if_matched(self):
        if self._r7417_keep_sat("MATCH_SWITCH"):
            return
        if self._r80_user_unmapped_guard("FALLBACK"):
            return
        # Known manual/learned mappings are the hot path. Preserve only the SAT metadata needed
        # by EPG/picon/frontend renderers, then open the exact stream without collecting audio
        # tracks/EPG text or running SmartMatch again.
        direct = self.direct_mapping_cache
        direct_source = self.direct_mapping_source
        # A user may re-lock beIN while a previous SAT fallback was still
        # armed. Refresh the exact manual pin before using a stale RAM plan.
        current_pin = self._load_overrides().get(sat_service_key(self.current_sat_ref_string))
        current_fp = (str(current_pin.get("channel_id") or "")
                      if isinstance(current_pin,dict) else "")
        if current_fp:
            old_fp = channel_fingerprint(direct) if direct is not None else ""
            if old_fp != current_fp or direct_source != "MANUAL_LOCK":
                self._direct_hot_drop_current()
                direct = self._find_override()
                direct_source = "MANUAL_LOCK" if direct is not None else ""
                self.direct_mapping_cache = direct
                self.direct_mapping_source = direct_source
        elif direct_source == "MANUAL_LOCK":
            self._direct_hot_drop_current()
            direct = None
            direct_source = ""
            self.direct_mapping_cache = None
            self.direct_mapping_source = ""
        if direct is not None and direct_source in ("MANUAL_LOCK", "LEARNED", "SESSION_FAST"):
            self._ensure_sat_switch_metadata()
            # Learned mappings are automatic cache entries, not user authority. Read only
            # the lightweight DVB audio-track descriptors before using them so a previously
            # learned AR/FR feed cannot bypass the new audio-identity gate. This avoids the
            # heavier EPG/deep-context traversal on the mapped hot path.
            if direct_source == "LEARNED" and not self.sat_deep_context_ready:
                try:
                    self.sat_audio_languages = self._read_sat_audio_languages()
                    if self.sat_audio_languages:
                        self.sat_context = infer_sat_context(
                            self.current_match_name or self.current_sat_name, self.sat_provider, self.sat_orbital, self.sat_satellite,
                            self._user_languages(), audio_languages=self.sat_audio_languages, epg_text=""
                        )
                        self.sat_context["service_label"] = self.current_sat_name
                except Exception as err:
                    self._log("LEARNED_AUDIO_CTX_ERR", str(err))
            self._prepare_target_quality()
            # Manual LOCK is an explicit user decision and always remains exact.  A learned
            # mapping is only a speed cache: if a recent receiver measurement already proves
            # it below the SAT target, drop the stale shortcut and run bounded SmartMatch now.
            direct_ok = True
            if direct_source == "LEARNED":
                # Learned mappings are disposable speed hints. If an old learned row is
                # explicitly tagged AR/FR/EN and conflicts with the current strong SAT
                # language context, invalidate it before playback so SmartMatch can use the
                # original DVB audio/provider identity. Manual locks remain user-authoritative.
                try:
                    declared_lang = explicit_language_tag(direct.get("name", ""))
                    top_lang = str(((self.sat_context or {}).get("language_priorities") or [""])[0] or "").upper()
                    strong_lang = str((self.sat_context or {}).get("confidence") or "").upper() == "HIGH"
                    if declared_lang and top_lang and declared_lang != top_lang and strong_lang and not (self.sat_context or {}).get("global_fallback"):
                        direct_ok = False
                        self._log("LEARNED_LANG_DROP", "sat='%s' learned='%s' feed=%s expected=%s -> rematch" % (
                            self.current_sat_name, direct.get("name", ""), declared_lang, top_lang))
                        self._remove_learned_mapping()
                        self.direct_mapping_cache = None; self.direct_mapping_source = ""
                except Exception:
                    pass
            if direct_ok and direct_source == "LEARNED" and self.target_quality_rank > 0:
                try:
                    _dlab, drank, dsrc = effective_quality_info(direct)
                    claimed_rank = int(direct.get("claimed_quality_rank") or 0)
                    below_target = int(drank or 0) < int(self.target_quality_rank or 0)
                    below_claim = claimed_rank >= 500 and int(drank or 0) < claimed_rank
                    if dsrc == "observed" and (below_target or below_claim):
                        direct_ok = False
                        self._log("LEARNED_QUALITY_DROP", "sat='%s' learned='%s' actual=%s target=%s claimed_rank=%d -> rematch" % (
                            self.current_sat_name, direct.get("name", ""), _dlab, self.target_quality, claimed_rank))
                        self._remove_learned_mapping()
                        self.direct_mapping_cache = None; self.direct_mapping_source = ""
                except Exception:
                    direct_ok = True
            if direct_ok:
                if direct_source == "MANUAL_LOCK":
                    self.counters["pinned"] += 1
                self.last_ranked = []
                self.candidate_plan = self._direct_candidate_plan(direct, source=direct_source)
                if self.candidate_plan:
                    self._activate_candidate(0, source=direct_source)
                    self.last_match_source = direct_source
                    self._log("MATCH_DIRECT", "source=%s sat='%s' mapped='%s' replicas=%d first_role=%s search=EXACT_REPLICA" % (
                        direct_source, self.current_sat_name, direct.get("name", ""), len(self.candidate_plan),
                        self.pending_match.get("server_role") if self.pending_match else "SERVER"))
                    self._play_match(self.pending_match, self.pending_score, retry=False)
                    return
                # A learned shortcut can become stale after a server refresh/stream rotation.
                # Drop only the disposable learned mapping and continue into SmartMatch *now*
                # instead of restoring SAT and requiring a second zap.
                if direct_source in ("LEARNED", "SESSION_FAST"):
                    if direct_source == "LEARNED":
                        self._remove_learned_mapping()
                    self._direct_hot_drop_current()
                    self.direct_mapping_cache = None; self.direct_mapping_source = ""
                    self._log("SESSION_REPLICA_MISS", "source=%s sat='%s' -> immediate SmartMatch" % (direct_source, self.current_sat_name))
                else:
                    # Manual lock with no available replica stays exact; do not silently roam to
                    # another channel identity.
                    self._log("MANUAL_REPLICA_MISS", "sat='%s' mapped='%s' no usable replica" % (self.current_sat_name, direct.get("name", "")))

        # r41 fast exact path: the lightweight SAT context captured at evStart already contains
        # service identity, provider, orbital/market and target service type.  For a very strong
        # exact identity we can build the safe candidate plan immediately and avoid collecting
        # SAT audio/EPG metadata first.  Ambiguous/fuzzy identities still fall through to the
        # original deep-context path below.
        quality_mode = getattr(getattr(self.cfg, "quality_mode", None), "value", "best")
        match_name = self.current_match_name or self.current_sat_name
        self._prepare_target_quality()
        try:
            quick_ranked = self.catalog.fast_rank_matches(
                match_name, self._user_languages(), context=self.sat_context, topn=32, quality_mode=quality_mode
            )
            quick_plan = self._build_candidate_plan(quick_ranked, pinned=None)
            if quick_plan:
                qch, qscore, qdetails = quick_plan[0][0], quick_plan[0][1], quick_plan[0][2]
                qidentity = float(qdetails.get("name", 0) or 0) + float(qdetails.get("equivalence", 0) or 0) + float(qdetails.get("variant", 0) or 0)
                qconfidence = str((self.sat_context or {}).get("confidence") or "LOW").upper()
                qlang = explicit_language_tag((qch or {}).get("name", ""))
                if qidentity >= 99.0 and (qconfidence == "HIGH" or not qlang):
                    self.last_ranked = quick_ranked or []
                    self.candidate_plan = quick_plan
                    self.counters["matches"] += 1
                    self._log("MATCH_QUICK_HIT", "sat='%s' candidates=%d identity=%.1f context=%s" % (
                        self.current_sat_name, len(self.candidate_plan), qidentity, qconfidence))
                    self._activate_candidate(0, source="SMART_FAST")
                    self._log("MATCH_PLAN", "sat='%s' provider='%s' market=%s target=%s(%s) candidates=%d primary='%s'" % (
                        self.current_sat_name, self.sat_provider, self.sat_context.get("market", ""),
                        self.target_quality, self.target_quality_source, len(self.candidate_plan),
                        self.pending_match.get("server_label") or self.pending_match.get("source") or "-"))
                    self._play_match(self.pending_match, self.pending_score, retry=False)
                    return
        except Exception as err:
            self._log("MATCH_QUICK_SKIP", str(err))

        # Ambiguous identities need richer SAT context, but catalogue scoring can be heavy.
        # Keep Enigma2 metadata reads on the GUI thread and move only pure-Python ranking off it.
        self._ensure_sat_deep_context()
        self._prepare_target_quality()
        self._queue_background_smartmatch(match_name, quality_mode)
        return

    def _play_service_force(self, ref):
        """Use normal playService for a different ref; forceRestart only for the exact same ref."""
        play = self.session.nav.playService
        same_ref = False
        try:
            current = self.session.nav.getCurrentlyPlayingServiceReference()
            same_ref = bool(self._ref_valid(current) and self._ref_valid(ref) and current.toString() == ref.toString())
        except Exception:
            same_ref = False
        if not same_ref:
            try: return play(ref, adjust=False)
            except TypeError: return play(ref)
        try: return play(ref, forceRestart=True, adjust=False)
        except TypeError:
            try: return play(ref, forceRestart=True)
            except TypeError: return play(ref)

    def _play_match(self, match, score, retry=False):
        if not retry and self._r7417_keep_sat("PLAYER_SWITCH"):
            return
        url = match.get("url", "")
        if not url or self.current_sat_ref is None:
            self.last_error = "Missing IPTV URL or SAT reference"; self.play_result = "PLAY ERROR"; self._set_state("ERROR", self.last_error, "play IPTV"); self._log("PLAY_ERROR", self.last_error); return
        try: self.audio_guard_timer.stop()
        except Exception: pass
        self.audio_guard_round = 0; self.audio_guard_fp = ""
        if not retry: self.fallback_attempt = 1
        else: self.fallback_attempt += 1; self.counters["retries"] += 1
        plan = self._playback_plan()
        forced_mode = str(self.forced_retry_mode or "") if retry else ""
        if forced_mode:
            mode = forced_mode
            self.forced_retry_mode = ""
        else:
            mode = plan[min(self.fallback_attempt - 1, len(plan) - 1)]
        self.current_play_mode = mode
        if mode in self.player_status:
            self.player_status[mode] = "TRYING"
        display_name = self.current_sat_name or match.get("name") or "IPTV"
        self.retry_pending = False; self.last_error = ""; self.iptv_start_seen = False
        self.playback_locked = False
        self.iptv_video_event_seen = False
        try:
            self.pre_switch_video_width, self.pre_switch_video_height = self._video_dimensions()
        except Exception:
            self.pre_switch_video_width = self.pre_switch_video_height = 0
        self._reset_iptv_resolution_session()
        self.current_candidate_started_at = time.time()
        self.start_guard_deadline = self.current_candidate_started_at + (self._start_guard_ms() / 1000.0)
        self.verify_started_at = 0.0; self.verify_deadline = 0.0; self.resolution_deadline = 0.0; self.first_video_evidence_at = 0.0
        try:
            # r9 Timeshift Bridge Lite:
            # Native MPEG-TS uses a localhost relay because that exact service shape (type 1 +
            # local HTTP TS) enables OpenATV native PAUSE/REW/FF timeshift.  r44 keeps the relay
            # packet-transparent but gives FHD/UHD a bounded startup/jitter reserve; player and
            # candidate failover remain owned by IPToSat Pro.
            play_url = url
            self.bridge_ready_marker = ""
            self.bridge_ready_token = ""
            if str(mode) == "dvb":
                # r11: unique readiness marker. The bridge creates it only after receiving
                # and validating real MPEG-TS packets from upstream. This gives us reliable
                # first-data evidence without changing bitrate, buffering or decoder timing.
                self.bridge_ready_token = "%d-%d" % (os.getpid(), int(time.time() * 1000.0))
                self.bridge_ready_marker = "/tmp/iptosat-tsbridge-ready-%s" % self.bridge_ready_token
                try:
                    if os.path.exists(self.bridge_ready_marker):
                        os.unlink(self.bridge_ready_marker)
                except Exception:
                    pass
                # r44 passes the expected/observed quality tier to the localhost relay so
                # FHD/UHD streams receive a larger jitter reserve while SD/HD keep fast start.
                try:
                    _qlabel, bridge_quality_rank, _qsource = effective_quality_info(match)
                    bridge_quality_rank = max(int(bridge_quality_rank or 0), int(self.target_quality_rank or 0))
                except Exception:
                    bridge_quality_rank = int(self.target_quality_rank or 0)
                fast_lock = bool(self.last_match_source == "MANUAL_LOCK")
                play_url = "http://127.0.0.1:18081/ts?id=%s&q=%d&fast=%d&u=%s" % (
                    quote(self.bridge_ready_token, safe=""), int(bridge_quality_rank or 0),
                    1 if fast_lock else 0, quote(str(url or ""), safe=""))
                if fast_lock:
                    self._log("FAST_LOCK_PLAY", "native relay low-latency profile iptv='%s'" % match.get("name", ""))
            audio_safe_identity = bool(self._audio_safe_serviceapp_required(match))
            preserve_identity = bool(self._epg_bridge_enabled() and str(mode) in ("4097", "5001", "5002", "5003") and not audio_safe_identity)
            ref_string = build_stream_ref(self.current_sat_ref_string, play_url, display_name, mode=mode, preserve_identity=preserve_identity)
            if audio_safe_identity and str(mode) in ("4097", "5001", "5002", "5003"):
                self._log("AUDIO_SAFE_IDENTITY", "mode=%s iptv='%s' canonical_stream_ref=YES sat_metadata=shadow" % (mode, match.get("name", "")))
            ip_ref = eServiceReference(ref_string)
            # Mark exactly which IPTV service this attempt owns before playService(). Preserve
            # the previous bridge stream too: direct retries intentionally keep the old IPTV
            # service as a release placeholder until the replacement takes over.
            self.previous_iptv_ref_string = str(self.expected_iptv_ref_string or "")
            self.previous_iptv_url = str(self.expected_iptv_url or "")
            self.expected_iptv_ref_string = ref_string
            self.expected_iptv_url = str(play_url or "").strip()
            if self._preserve_sat_frontend_enabled():
                sat_shadow.activate()
            if preserve_identity:
                self._log("SAT_IDENTITY_BRIDGE", "mode=%s sat='%s' metadata=DVB epg+picon=SAT" % (mode, self.current_sat_name))
            # Prefer direct SAT identity (all 4097/5002 modes). If an image/player rewrites
            # the ref to a canonical stream identity, the renderer/EventInfo shadow patches
            # still recover the original SAT picon and EPG without a retune.
            self._mirror_sat_epg_to_stream(ip_ref)
            self.fallback_active = True; self.switch_in_progress = True; self.playback_state = "IPTV requested"; self.play_result = "REQUESTED"; self.counters["fallbacks"] += 1
            self._set_state("SWITCH_IPTV", "Opening matched IPTV stream via %s" % mode, "fallback attempt %d" % self.fallback_attempt)
            self._log("IPTV_SWITCH", "attempt=%d mode=%s sat='%s' -> iptv='%s' quality=%s score=%.1f stream=%s" % (
                self.fallback_attempt, mode, self.current_sat_name, match.get("name", ""), match.get("quality", ""), score, redact_url(url)))
            result = self._play_service_force(ip_ref)
            if result not in (0, None):
                self.switch_in_progress = False
                self._clear_expected_iptv()
                self.play_result = "REQUEST REJECTED (%s)" % result; self.last_error = "Enigma2 playService returned %s" % result
                self._log("PLAY_REJECTED", "attempt=%d mode=%s result=%s" % (self.fallback_attempt, mode, result)); self._handle_iptv_failure(self.last_error)
            else:
                # Poll service activation early instead of waiting the whole start timeout.
                # The failure deadline is unchanged, so slow streams keep the same allowance.
                self.start_guard_timer.start(self.FAST_START_GUARD_POLL_MS if self._fast_zap_enabled() else 180, True)
        except Exception as err:
            self.switch_in_progress = False
            self._clear_expected_iptv()
            self.last_error = str(err); self.fallback_active = False; self.play_result = "EXCEPTION"; self._set_state("ERROR", "Could not start IPTV stream", "play exception")
            self._log("PLAY_EXCEPTION", "mode=%s %s" % (mode, err)); self._handle_iptv_failure(str(err))

    def _start_guard(self):
        if not self.fallback_active or self.retry_pending or self.iptv_start_seen:
            return
        current = self.session.nav.getCurrentlyPlayingServiceReference()
        try:
            path = current and current.getPath() or ""
        except Exception:
            path = ""
        ctype = current.toString().split(":", 1)[0] if current is not None else ""
        if current is not None and (path or ctype in ("4097", "5001", "5002", "5003")):
            if self._is_expected_bridge_iptv(current, service_path=path):
                # Some images miss evStart. Detect the *requested* stream in ~100ms slices and
                # begin first-frame verification immediately. Never accept an unrelated IPTV
                # service simply because its type is 4097/5002.
                self.switch_in_progress = False
                self.iptv_start_seen = True
                self.previous_iptv_ref_string = ""; self.previous_iptv_url = ""
                self.verify_pts = self._read_pts()
                self._arm_video_watchdog()
                self.pts_before = self._format_pts(self.verify_pts)
                self._set_state("VERIFY_IPTV", "IPTV service active; checking decoded video", "early start guard")
                self._log("START_GUARD_HIT", "mode=%s current_type=%s after=%dms" % (
                    self.current_play_mode, ctype, int(max(0.0, time.time() - self.current_candidate_started_at) * 1000.0)))
                self.verify_timer.start(self._verify_step_ms(), True)
                return
            # During a direct candidate/player retry the previous bridge IPTV may remain on
            # screen briefly while playService switches. Keep polling only for that known old
            # bridge ref. Any other IPTV ref is user/navigation ownership and cancels our state.
            try: cur_string = current.toString()
            except Exception: cur_string = ""
            if self.switch_in_progress and self._is_previous_bridge_iptv(current, cur_string, path):
                pass
            else:
                self._abandon_bridge_for_manual_iptv(cur_string, path)
                return
        if time.time() < float(self.start_guard_deadline or 0.0):
            self.start_guard_timer.start(self.FAST_START_GUARD_POLL_MS if self._fast_zap_enabled() else 180, True)
            return
        self._handle_iptv_failure("IPTV start event/service not active after %.1f s" % (self._start_guard_ms() / 1000.0))

    def _restore_sat_for_release(self):
        # beta25.9 native-crash fix: DO NOT bounce IPTV -> SAT -> IPTV between player
        # retries/candidates. OpenATV 7.6 can have a delayed no-PAT callback associated
        # with the short-lived DVB PMT handler. Keep the failed IPTV service as a harmless
        # release placeholder; the next playService() atomically replaces it. The original
        # SAT reference is restored only once when all candidates are exhausted.
        self._log("RETRY_DIRECT", "keeping IPTV service during release window; no DVB retune")
        return True

    def _final_restore_sat(self, reason):
        sat_shadow.deactivate()
        self.switch_in_progress = False
        self.native_pat_guard_pending = False
        try: self.native_pat_guard_timer.stop()
        except Exception: pass
        self.fallback_active = False
        self.retry_pending = False
        self.retry_kind = ""
        self._clear_expected_iptv()
        self.failure_cooldown_sat = self.current_sat_ref_string
        self.failure_cooldown_until = time.time() + self.FAILURE_COOLDOWN_S
        self.play_result = "NO VERIFIED IPTV"
        self._set_state("NO_VERIFIED_IPTV", reason, "keep original SAT")
        try:
            if self._ref_valid(self.current_sat_ref):
                self._play_service_force(self.current_sat_ref)
                self._log("RESTORE_SAT", "all IPTV candidates exhausted -> original SAT reference restored")
        except Exception as err:
            self._log("RESTORE_SAT_ERROR", str(err))

    def _schedule_next_candidate(self, reason, mark_failure=True):
        current = self.pending_match or self.last_match
        if current is not None:
            fp = channel_fingerprint(current)
            if mark_failure:
                self.failed_candidate_ids.add(fp)
                self._record_health(current, False, reason=reason)
        next_index = self.candidate_index + 1
        while next_index < len(self.candidate_plan):
            row = self.candidate_plan[next_index]
            ch = row[0]
            try:
                is_quality_fallback = bool((row[2] or {}).get("quality_fallback"))
            except Exception:
                is_quality_fallback = False
            # A quality_fallback is the stream that decoded successfully moments ago. Historical
            # health cooldown must never skip it after optional higher-quality probes fail.
            if is_quality_fallback or not self._health_blocked(ch):
                break
            next_index += 1
        if next_index >= len(self.candidate_plan):
            if self.last_match_source in ("LEARNED", "SESSION_FAST"):
                if self.last_match_source == "LEARNED":
                    self._remove_learned_mapping()
                self._log("SESSION_MAP_DROP", "source=%s all exact replicas failed; immediate SmartMatch in same zap" % self.last_match_source)
                self.direct_mapping_cache = None; self.direct_mapping_source = ""
                self._direct_hot_drop_current()
                try:
                    # We are still on the failed IPTV service here.  Keep the SAT identity/context
                    # captured before the switch; do not accidentally read IPTV audio/EPG as SAT.
                    quality_mode = getattr(getattr(self.cfg, "quality_mode", None), "value", "best")
                    match_name = self.current_match_name or self.current_sat_name
                    ranked = self.catalog.fast_rank_matches(
                        match_name, self._user_languages(), context=self.sat_context, topn=32, quality_mode=quality_mode
                    )
                    new_plan = self._build_candidate_plan(ranked, pinned=None)
                    if not new_plan:
                        ranked = self.catalog.rank_matches(
                            match_name, self._user_languages(), context=self.sat_context, topn=32, quality_mode=quality_mode
                        )
                        new_plan = self._build_candidate_plan(ranked, pinned=None)
                    if new_plan:
                        self.last_ranked = ranked or []
                        self.candidate_plan = new_plan
                        self._activate_candidate(0, source="SMART")
                        self.retry_pending = True
                        self.retry_kind = "candidate"
                        self.fallback_active = False
                        self.play_result = "REMATCH"
                        self._set_state("CANDIDATE_WAIT", "Session shortcut failed; trying fresh SmartMatch", "same zap rematch")
                        self._log("SESSION_REMATCH", "reason=%s candidates=%d next_role=%s next='%s'" % (
                            reason, len(new_plan), self.pending_match.get("server_role") or "SERVER", self.pending_match.get("name", "")))
                        self._restore_sat_for_release()
                        self.retry_timer.start(self._retry_release_ms(), True)
                        return True
                except Exception as err:
                    self._log("SESSION_REMATCH_ERR", str(err))
            self._final_restore_sat("All safe IPTV candidates failed or missed the required resolution")
            return False

        previous_server = current.get("server_id","") if current else ""
        self._activate_candidate(next_index)
        new_server = self.pending_match.get("server_id","") if self.pending_match else ""
        self.retry_pending = True
        self.retry_kind = "candidate"
        self.fallback_active = False
        self.play_result = "NEXT CANDIDATE"
        role = self.pending_match.get("server_role") or "SERVER"
        self._set_state("CANDIDATE_WAIT", "Trying next verified candidate on %s" % role, "release stream")
        self._log("CANDIDATE_NEXT", "reason=%s idx=%d/%d server_change=%s next='%s'" % (
            reason, self.candidate_index + 1, len(self.candidate_plan),
            "YES" if previous_server and new_server and previous_server != new_server else "NO",
            self.pending_match.get("name","") if self.pending_match else "-"))
        self._restore_sat_for_release()
        self.retry_timer.start(self._retry_release_ms(), True)
        return True

    def _current_audio_track_count(self):
        """Return audio track count, or None when the player API is not ready/unsupported."""
        try:
            service = self.session.nav.getCurrentService()
            if service is None:
                return None
            tracks = service.audioTracks()
            if tracks is None:
                return None
            return max(0, int(tracks.getNumberOfTracks()))
        except Exception:
            return None

    def _remember_native_audio_missing(self, candidate):
        try:
            fp = channel_fingerprint(candidate or {})
            if not fp:
                return
            rec = dict((self.stream_health or {}).get(fp) or {})
            rec["native_audio_missing"] = True
            rec["native_audio_missing_at"] = time.time()
            self.stream_health[fp] = rec
            self._schedule_health_save()
        except Exception:
            pass

    def _schedule_audio_guard(self, candidate):
        try:
            self.audio_guard_timer.stop()
        except Exception:
            pass
        self.audio_guard_round = 0
        self.audio_guard_fp = channel_fingerprint(candidate or {})
        if not self.audio_guard_fp or str(self.current_play_mode) != "dvb":
            return
        # Respect an explicit user request to force Native DVB. Auto mode is the only mode
        # allowed to self-heal from video-without-audio to ServiceApp.
        try:
            if self._current_player_override() == "dvb" or str(self.cfg.service_type.value) == "dvb":
                return
        except Exception:
            pass
        try:
            self.audio_guard_timer.start(self.AUDIO_GUARD_FIRST_MS, True)
        except Exception:
            pass

    def _audio_guard_tick(self):
        if not self.playback_locked or str(self.current_play_mode) != "dvb":
            return
        candidate = self.pending_match or self.last_match
        fp = channel_fingerprint(candidate or {})
        if not candidate or not fp or fp != self.audio_guard_fp:
            return
        count = self._current_audio_track_count()
        if count is None:
            # API unknown is not evidence of missing audio. Do not bounce a working picture.
            self._log("AUDIO_GUARD_UNKNOWN", "iptv='%s' player audioTracks unavailable" % candidate.get("name", ""))
            return
        if count > 0:
            self._log("AUDIO_GUARD_PASS", "iptv='%s' native_tracks=%d" % (candidate.get("name", ""), count))
            return
        self.audio_guard_round += 1
        if self.audio_guard_round < self.AUDIO_GUARD_MAX_ZERO_SAMPLES:
            try: self.audio_guard_timer.start(self.AUDIO_GUARD_STEP_MS, True)
            except Exception: pass
            return

        # Confirmed video but persistent zero audio tracks. Retry the SAME source once through
        # ServiceApp, using a canonical stream identity so SAT PID/audio-selection state cannot
        # leak into the IPTV player. This is a functional recovery, not candidate failover.
        mode = self._safe_serviceapp_mode()
        self._remember_native_audio_missing(candidate)
        self._log("AUDIO_GUARD_RETRY", "iptv='%s' native_tracks=0 samples=%d -> %s" % (
            candidate.get("name", ""), self.audio_guard_round, mode))
        self.playback_locked = False
        self.forced_retry_mode = mode
        self.retry_pending = True
        self.retry_kind = "audio_player"
        self.fallback_active = False
        self.play_result = "AUDIO PLAYER RETRY"
        self._set_state("RETRY_WAIT", "Video OK but native audio missing; retrying same source via %s" % mode, "audio-safe player")
        self._restore_sat_for_release()
        try: self.retry_timer.start(max(40, min(120, self._retry_release_ms())), True)
        except Exception: self._retry_fallback()

    def _accept_verified_video(self, now_pts=None, evidence="PTS"):
        """Accept real moving IPTV immediately; verify quality asynchronously unless strict_exact."""
        now = time.time()
        raw_width, raw_height = self._video_dimensions()
        width, height, dimensions_fresh = self._fresh_iptv_dimensions(now)
        policy = str(getattr(getattr(self.cfg, "resolution_policy", None), "value", "source_strict"))
        strict = policy == "strict_exact"
        verify_resolution = bool(getattr(getattr(self.cfg, "verify_actual_resolution", None), "value", True))
        qlabel, qrank = quality_from_dimensions(width, height)
        candidate = self.pending_match or self.last_match

        # strict_exact is intentionally the only blocking quality mode. The normal source_strict
        # profile prioritizes zap speed: real PTS proves the stream, then resolution/HDR are learned
        # in the background without IPTV->IPTV bouncing after a picture is already visible.
        if verify_resolution and strict and not dimensions_fresh:
            if self.resolution_deadline <= 0:
                self.resolution_deadline = now + (self._resolution_timeout_ms() / 1000.0)
            if now < self.resolution_deadline:
                if now_pts is not None:
                    self.verify_pts = now_pts
                self.video_state = "IPTV moving; strict resolution verification"
                self.verify_timer.start(self._verify_step_ms(), True)
                return False
            if self.target_quality_rank > 0:
                self.counters["resolution_rejects"] += 1
                self._log("QUALITY_UNKNOWN", "iptv='%s' target=%s no fresh dimensions after %dms raw=%dx%d" % (
                    candidate.get("name", "") if candidate else "-", self.target_quality, self._resolution_timeout_ms(), raw_width, raw_height))
                self._schedule_next_candidate("Fresh decoded resolution unavailable for strict_exact", mark_failure=False)
                return False

        if verify_resolution and strict and self.target_quality_rank > 0 and dimensions_fresh:
            if int(qrank or 0) < int(self.target_quality_rank):
                self.counters["resolution_rejects"] += 1
                if candidate is not None:
                    self._record_health(candidate, True, width=width, height=height)
                self._log("QUALITY_REJECT", "iptv='%s' actual=%dx%d/%s target=%s" % (
                    candidate.get("name", "") if candidate else "-", width, height, qlabel, self.target_quality))
                self._schedule_next_candidate("Actual IPTV resolution %s is below SAT target %s" % (qlabel, self.target_quality), mark_failure=False)
                return False

        # Audio identity is intentionally NON-BLOCKING in r4.  Candidate ranking already uses
        # the original SAT audio/provider/orbital context before playback.  Once a real IPTV
        # frame is visible we never tear down that picture just because a player reports an
        # unexpected/missing language descriptor: ServiceApp/Enigma2 remain fully responsible
        # for selecting and decoding the available audio tracks.  A definite mismatch only
        # invalidates disposable learned/session shortcuts for the *next* zap.
        audio_identity_mismatch = False
        if candidate is not None:
            try:
                sat_audio = [str(x).upper() for x in ((self.sat_context or {}).get("audio_language_set") or []) if x]
                declared = explicit_language_tag(candidate.get("name", ""))
                # Avoid synchronous audioTracks() enumeration on the first-frame hot path.
                # The declared feed tag is cheap and sufficient to invalidate a stale shortcut;
                # unknown/no-tag streams are never rejected.
                if sat_audio and declared and declared not in sat_audio:
                    audio_identity_mismatch = True
                    self._log("AUDIO_ID_DEFER", "sat=%s declared=%s iptv='%s' action=KEEP_PICTURE_RECHECK_NEXT_ZAP" % (
                        "/".join(sat_audio), declared, candidate.get("name", "")))
                    if self.last_match_source in ("LEARNED", "SESSION_FAST"):
                        if self.last_match_source == "LEARNED":
                            self._remove_learned_mapping()
                        self._direct_hot_drop_current()
                elif sat_audio:
                    self._log("AUDIO_ID_HINT", "sat=%s declared=%s result=%s" % (
                        "/".join(sat_audio), declared or "-",
                        "MATCH" if declared and declared in sat_audio else "UNKNOWN"))
            except Exception as err:
                self._log("AUDIO_ID_ERR", str(err))

        latency_ms = int(max(0.0, time.time() - self.current_candidate_started_at) * 1000.0)
        self.last_first_frame_ms = latency_ms
        if self.current_play_mode in self.player_status:
            self.player_status[self.current_play_mode] = "PASS"

        hdr = self._video_hdr() if dimensions_fresh else ""
        if candidate is not None:
            if dimensions_fresh:
                self._commit_current_resolution(candidate, width, height)
            self._record_health(candidate, True, width=width if dimensions_fresh else 0, height=height if dimensions_fresh else 0, mode=self.current_play_mode, latency_ms=latency_ms, evidence=evidence)
            if dimensions_fresh and hdr:
                self._update_resolution_observation(candidate, width, height, hdr=hdr)
            try:
                current_ref = self.session.nav.getCurrentlyPlayingServiceReference()
                if current_ref is not None:
                    self._mirror_sat_epg_to_stream(current_ref)
            except Exception:
                pass

            below_target = bool(dimensions_fresh and self.target_quality_rank > 0 and int(qrank or 0) < int(self.target_quality_rank))
            if self.last_match_source in ("LEARNED", "SESSION_FAST"):
                if ((not verify_resolution) or self.target_quality_rank < 500 or dimensions_fresh) and not audio_identity_mismatch:
                    # A successful first frame, including a measured fallback tier, locks the
                    # best identity-safe source. The measured dimensions are saved with it.
                    self._save_learned_mapping(candidate)
            elif self.last_match_source != "MANUAL_LOCK":
                # For explicit FHD/UHD targets wait for decoded dimensions, but retain a
                # verified lower-tier fallback once its actual resolution is known.
                if ((not verify_resolution) or self.target_quality_rank < 500 or dimensions_fresh) and not audio_identity_mismatch:
                    self._save_learned_mapping(candidate)

        if dimensions_fresh and self.target_quality_rank > 0 and int(qrank or 0) < int(self.target_quality_rank):
            self.video_state = "IPTV verified • %dx%d %s • quality fallback" % (width, height, qlabel)
            self.play_result = "SUCCESS • QUALITY FALLBACK"
            self._log("QUALITY_DEGRADED", "iptv='%s' actual=%dx%d/%s target=%s; no post-picture bounce" % (candidate.get("name", "") if candidate else "-", width, height, qlabel, self.target_quality))
        else:
            self.video_state = ("IPTV TS ready • decoder unconfirmed" if evidence == "validated-ts-data" else
                                "IPTV video verified%s" % ((" • %dx%d %s" % (width, height, qlabel)) if dimensions_fresh else " • resolution pending"))
            self.play_result = "SUCCESS"

        self.playback_state = "IPTV OK"
        # r7 First-image-wins: once decoded playback is accepted, no late metadata/EOF/watchdog
        # event is allowed to bounce the user to another player/source during this viewing.
        self.playback_locked = True
        self.retry_pending = False
        self.retry_kind = ""
        try: self.retry_timer.stop()
        except Exception: pass
        try: self.start_guard_timer.stop()
        except Exception: pass
        try: self.verify_timer.stop()
        except Exception: pass
        # The stream may have been accepted on PTS/resolution before the native-TS ready
        # marker was consumed.  Remove only our own marker; playback and timeshift continue.
        self._cleanup_bridge_ready_marker()
        self.counters["success"] += 1
        self._set_state("IPTV_OK", "Transport packets received; decoder pending" if evidence == "validated-ts-data" else "IPTV video decoded and accepted", "fallback success")
        self._schedule_neighbor_prepare()
        if verify_resolution and not dimensions_fresh and candidate is not None:
            self._schedule_resolution_followup(candidate)
        if candidate is not None and str(self.current_play_mode) == "dvb":
            self._schedule_audio_guard(candidate)
        self._log("IPTV_OK", "candidate=%d/%d attempt=%d mode=%s role=%s sat='%s' iptv='%s' actual=%s target=%s hdr=%s latency=%dms evidence=%s" % (
            self.candidate_index + 1, len(self.candidate_plan), self.fallback_attempt, self.current_play_mode,
            candidate.get("server_role") if candidate else "-", self.current_sat_name, candidate.get("name", "") if candidate else "",
            ("%dx%d/%s" % (width, height, qlabel)) if dimensions_fresh else "PENDING", self.target_quality, hdr or "-", latency_ms, evidence))
        return True

    def _verify_iptv(self):
        if not self.fallback_active or self.retry_pending:
            return
        current = self.session.nav.getCurrentlyPlayingServiceReference()
        try:
            current_path = current and current.getPath() or ""
        except Exception:
            current_path = ""
        try: current_string = current.toString() if current is not None else ""
        except Exception: current_string = ""
        current_type = current_string.split(":", 1)[0] if current_string else ""
        if current is None or (not current_path and current_type not in ("4097", "5001", "5002", "5003")):
            self._handle_iptv_failure("IPTV service did not remain active")
            return
        if not self._is_expected_bridge_iptv(current, current_string, current_path):
            # Navigation ownership changed after bridge startup (for example the user selected a
            # normal IPTV bouquet while verification was still running). Never validate that
            # unrelated decoder/PTS as success for the previous SAT mapping.
            self._abandon_bridge_for_manual_iptv(current_string, current_path)
            return

        if self.verify_deadline <= 0:
            self._arm_video_watchdog()

        now = time.time()
        now_pts = self._read_pts()
        self.pts_after = self._format_pts(now_pts)
        width, height = self._video_dimensions()

        # r11 Native TS proof: the localhost bridge writes this marker only after it has
        # received and validated real 188-byte MPEG-TS packets. On OpenATV type-1 streams,
        # decoder PTS/video-size events can arrive late even while the picture is already
        # visible. Trusting validated TS data prevents the 2.8/3.6s watchdog from performing
        # a false ServiceApp retry that causes the visible one-second freeze after zap.
        if str(self.current_play_mode) == "dvb" and self.bridge_ready_marker:
            try:
                bridge_ready = os.path.isfile(self.bridge_ready_marker)
            except Exception:
                bridge_ready = False
            if bridge_ready:
                try:
                    os.unlink(self.bridge_ready_marker)
                except Exception:
                    pass
                if not self.first_video_evidence_at:
                    self.first_video_evidence_at = now
                    self._log("FIRST_TS_DATA", "mode=dvb after=%dms marker=%s" % (
                        int(max(0.0, now - self.current_candidate_started_at) * 1000.0),
                        os.path.basename(self.bridge_ready_marker)))
                if self._accept_verified_video(now_pts=now_pts, evidence="validated-ts-data"):
                    return
        pts_moved = self.verify_pts is not None and now_pts is not None and now_pts != 0 and now_pts != self.verify_pts
        # A size event is authoritative. A bounded stable-sample fallback is handled inside
        # _accept_verified_video after real PTS movement, so raw stale dimensions alone never
        # count as the first decoded-frame evidence.
        dimensions_ready = width > 0 and height > 0 and self.iptv_video_event_seen
        raw_size_ready = self._raw_size_decode_evidence(now, width, height) if not dimensions_ready else False

        # Accept the first real decoder evidence immediately. Fast mode polls every 75ms while
        # keeping a quality-adaptive failure ceiling for genuinely slow FHD/UHD streams.
        if pts_moved or dimensions_ready or raw_size_ready:
            if not self.first_video_evidence_at:
                self.first_video_evidence_at = now
                self.resolution_deadline = now + (self._resolution_timeout_ms() / 1000.0)
                evidence = "PTS" if pts_moved else ("resolution-event" if dimensions_ready else "stable-size")
                self._log("FIRST_VIDEO", "mode=%s after=%dms evidence=%s size=%dx%d" % (
                    self.current_play_mode, int(max(0.0, now - self.current_candidate_started_at) * 1000.0),
                    evidence, width, height))
            evidence = "PTS" if pts_moved else ("resolution" if dimensions_ready else "stable-size")
            if self._accept_verified_video(now_pts=now_pts, evidence=evidence):
                return
            return

        self.verify_round += 1
        if now_pts is not None:
            self.verify_pts = now_pts

        if now < self.verify_deadline:
            elapsed = int(max(0.0, now - self.verify_started_at) * 1000.0)
            self.video_state = "IPTV buffering / waiting first decoded frame (%dms)" % elapsed
            self._set_state("BUFFERING_IPTV", "Waiting for first decoded IPTV frame", "adaptive watchdog")
            self.verify_timer.start(self._verify_step_ms(), True)
            return

        self._handle_iptv_failure("No decoded IPTV video after %.1f s" % (self._video_timeout_ms() / 1000.0))

    def _handle_iptv_failure(self, reason):
        if getattr(self, "playback_locked", False):
            self._log("LATE_FAIL_IGNORED", "first-image-wins reason=%s mode=%s" % (reason, self.current_play_mode))
            return
        try:
            self.start_guard_timer.stop()
        except Exception:
            pass
        self.switch_in_progress = False
        self.last_error = str(reason)
        if self.current_play_mode in self.player_status:
            self.player_status[self.current_play_mode] = "FAIL"
        # Per-fingerprint player failure is just a routing hint; never mark the
        # entire candidate bad until both player modes fail.
        try:
            ch = self.pending_match or self.last_match
            if ch:
                fp = channel_fingerprint(ch)
                rec = dict((self.stream_health or {}).get(fp) or {})
                rec["last_failed_player"] = str(self.current_play_mode or "")
                rec["last_failed_player_at"] = time.time()
                self.stream_health[fp] = rec
                self._schedule_health_save()
        except Exception:
            pass
        self.video_state = "IPTV video not confirmed"
        self.playback_state = "IPTV FAILED"
        self.play_result = "FAILED"
        self.counters["failures"] += 1
        if "decoded IPTV video" in str(reason) or "start event" in str(reason) or "remain active" in str(reason):
            self.counters["black_streams"] += 1
        self._set_state("IPTV_FAIL", str(reason), "watchdog failure")
        self._log("IPTV_FAIL", "candidate=%d/%d attempt=%d mode=%s role=%s sat='%s' iptv='%s' reason=%s" % (
            self.candidate_index + 1, len(self.candidate_plan), self.fallback_attempt, self.current_play_mode,
            self.pending_match.get("server_role") if self.pending_match else "-",
            self.current_sat_name, self.pending_match.get("name", "") if self.pending_match else "", reason))

        allow_retry = bool(getattr(getattr(self.cfg, "retry_failed_stream", None), "value", True))
        plan = self._playback_plan()
        alternate_player = len(plan) > 1 and plan[0] != plan[1]
        if allow_retry and alternate_player and self.fallback_attempt < 2 and self.pending_match is not None:
            self.retry_pending = True
            self.retry_kind = "player"
            self.fallback_active = False
            self.play_result = "PLAYER RETRY"
            next_mode = plan[1]
            self._set_state("RETRY_WAIT", "Same stream failed; retry via %s" % next_mode, "alternate player")
            self._log("RETRY_PLAYER", "release_ms=%d next_mode=%s candidate=%d" % (
                self._retry_release_ms(), next_mode, self.candidate_index + 1))
            self._restore_sat_for_release()
            self.retry_timer.start(self._retry_release_ms(), True)
            return

        # Both player paths failed (or fixed player mode).  A direct mapping may now contain
        # same-identity replicas on PRIMARY/BACKUP1/BACKUP2, so keep the learned identity until
        # those replicas are exhausted.  _schedule_next_candidate() drops/rematches only then.
        self._schedule_next_candidate(str(reason), mark_failure=True)

    def _retry_fallback(self):
        if self._r80_user_unmapped_guard("RETRY"):
            return
        if not self.retry_pending or self.pending_match is None or self.current_sat_ref is None:
            return
        current_pin = self._load_overrides().get(sat_service_key(self.current_sat_ref_string))
        pinned = (str(current_pin.get("channel_id") or "")
                  if isinstance(current_pin,dict) else "")
        if (pinned and self.direct_mapping_source == "MANUAL_LOCK"
                and channel_fingerprint(self.pending_match) != pinned):
            self.retry_pending = False
            self.retry_kind = ""
            self.candidate_plan = []
            self.pending_match = None
            self._direct_hot_drop_current()
            self.direct_mapping_cache = None
            self.direct_mapping_source = ""
            self._log("MANUAL_REMAP_DROP_RETRY", "sat=%r" % sat_service_key(self.current_sat_ref_string))
            if self._same_sat_still_playing():
                self._fallback_if_matched()
            return
        if not self.cfg.enabled.value:
            self.retry_pending = False
            self.retry_kind = ""
            return
        kind = self.retry_kind or "player"
        self.retry_pending = False
        self.retry_kind = ""
        if kind == "candidate":
            self._log("CANDIDATE_NOW", "sat='%s' iptv='%s' role=%s" % (
                self.current_sat_name, self.pending_match.get("name",""), self.pending_match.get("server_role") or "-"))
            self._play_match(self.pending_match, self.pending_score, retry=False)
        else:
            plan = self._playback_plan()
            next_mode = str(self.forced_retry_mode or "") or (plan[1] if len(plan) > 1 else plan[0])
            self._log("RETRY_NOW", "sat='%s' iptv='%s' next_mode=%s kind=%s" % (
                self.current_sat_name, self.pending_match.get("name", ""), next_mode, kind))
            self._play_match(self.pending_match, self.pending_score, retry=True)
