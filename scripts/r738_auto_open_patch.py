# -*- coding: utf-8 -*-
"""R73.8: SAFE auto-mapping triggers actual IPTV playback on the CURRENT SAT only.

Uses SatFallbackMonitor's existing candidate plan / _play_match / watchdog / backup
path. Never performs playback on the Preview background ranking thread, never
changes the FTA/signal configuration, and never overwrites manual mappings.
"""
def exactly(src, old, new):
    count = src.count(old)
    if count != 1:
        raise AssertionError("R73.8 patch drift %d: %s" % (count, repr(old[:120])))
    return src.replace(old, new, 1)


def patch_plugin(src):
    helpers = '''def _r738_autoplay_current(sat_ref, fingerprint):
    """Start an approved saved AUTO candidate through the SAME live bridge player.

    Invoked from a deferred mainloop callback after Preview has closed and restored
    the original SAT service. The double current-service guard prevents stale
    Preview results or user zaps from stealing an unrelated channel.
    """
    mon = MONITOR
    if mon is None:
        return "NO_MONITOR"
    try:
        if not bool(cfg.enabled.value):
            return "AUTO_DISABLED"
        ref = mon.session.nav.getCurrentlyPlayingServiceReference()
        current = ref.toString() if ref is not None else ""
        if current != str(sat_ref or "") or not mon._same_sat_still_playing():
            _startup_log("AUTO_PLAY_SKIP", "reason=SAT_CHANGED ref=%s" % str(sat_ref)[:70])
            return "SAT_CHANGED"
        if bool(getattr(mon, "manual_preview_active", False)):
            return "PREVIEW_ACTIVE"
        if bool(getattr(mon, "fallback_active", False)) or bool(getattr(mon, "switch_in_progress", False)):
            return "PLAYER_BUSY"
        # Do not replace a working native DVB picture; an IPTV match alone
        # is not evidence that a healthy satellite channel should be hijacked.
        if bool(getattr(mon, "video_event_seen", False)) and str(getattr(mon, "tuner_state", "")) == "LOCKED":
            return "SAT_VIDEO_ACTIVE"
        key = sat_service_key(sat_ref)
        saved = _load_overrides().get(key) or {}
        if not isinstance(saved, dict) or not saved.get("auto_best_lock") or str(saved.get("channel_id") or "") != str(fingerprint or ""):
            return "MAPPING_CHANGED"
        token = (str(sat_ref), str(fingerprint), float(getattr(mon, "current_sat_started_at", 0) or 0))
        if getattr(mon, "_r738_autoplay_token", None) == token:
            return "ALREADY_REQUESTED"
        catalog = getattr(mon, "catalog", None)
        ch = catalog.find_fingerprint(fingerprint) if catalog is not None else None
        if not ch or not ch.get("url"):
            return "CANDIDATE_MISSING"
        mon._ensure_sat_switch_metadata()
        mon._prepare_target_quality()
        plan = mon._direct_candidate_plan(ch, source="SESSION_FAST")
        if not plan:
            return "NO_REPLICA"
        # The requested safe candidate remains PRIMARY of this single switch.
        # Existing direct-replica plan provides the normal retry/backup path.
        for pos, row in enumerate(plan):
            if channel_fingerprint(row[0]) == fingerprint:
                if pos:
                    plan.insert(0, plan.pop(pos))
                break
        try:
            mon.smartmatch_generation += 1
            mon.smartmatch_pending = None
            mon.smartmatch_result = None
            mon.smartmatch_timer.stop()
        except Exception:
            pass
        mon.candidate_plan = plan
        if not mon._activate_candidate(0, source="SESSION_FAST"):
            return "ACTIVATION_FAILED"
        mon.last_match_source = "SESSION_FAST"
        mon._r738_autoplay_token = token
        mon._r738_autoplay_last = (str(sat_ref), str(fingerprint), time.monotonic())
        mon._log("AUTO_PLAY_START", "sat='%s' iptv='%s' role=%s candidates=%d source=PREVIEW_SAFE" %
                 (str(getattr(mon, "current_sat_name", ""))[:70],
                  str(ch.get("name") or "")[:80], str(ch.get("server_role") or "-"), len(plan)))
        mon._play_match(mon.pending_match, mon.pending_score, retry=False)
        return "PLAY_REQUESTED"
    except Exception as error:
        _startup_log("AUTO_PLAY_ERROR", "sat=%s error=%s" % (str(sat_ref)[:65], str(error)[:150]))
        return "ERROR"


def _r738_queue_auto_open(screen, sat_ref, state, channel):
    """Queue SAFE newly created/replaced and previously saved AUTO maps for live SAT.

    Preview's normal _restore() always restores SAT on close. Close Preview
    before opening IPTV; otherwise _restore() could undo the new stream.
    """
    if state not in ("AUTO_CREATED", "AUTO_REPLACED", "ALREADY_AUTO") or not isinstance(channel, dict):
        return False
    if bool(getattr(screen, "_r738_auto_open_queued", False)):
        return False
    try:
        if MONITOR is None or not bool(cfg.enabled.value):
            return False
        current = screen.session.nav.getCurrentlyPlayingServiceReference()
        current = current.toString() if current is not None else ""
        restore = getattr(screen, "restore_ref", None)
        original = restore.toString() if restore is not None else ""
        if current != sat_ref or original != sat_ref:
            _startup_log("AUTO_PLAY_SKIP", "reason=NOT_CURRENT_SAT target=%r" % str(sat_ref)[:70])
            return False
        fp = channel_fingerprint(channel)
        if not fp:
            return False
        # Existing AUTO mappings from previous releases need one recovery too.
        # Do not auto-close Preview repeatedly if a source has just failed:
        # leave the user time to select a manual correction via GREEN.
        last = getattr(MONITOR, "_r738_autoplay_last", None)
        if isinstance(last, tuple) and len(last) == 3:
            if last[0] == sat_ref and last[1] == fp and time.monotonic()-float(last[2]) < 60:
                return False
        screen._r738_auto_open_queued = True
        _startup_log("AUTO_PLAY_QUEUED", "sat=%r iptv=%r status=%s" %
                     (str(getattr(screen, "sat_name", ""))[:75], str(channel.get("name") or "")[:85], state))
        def close_and_open():
            if bool(getattr(screen, "_closed_for_async", False)):
                return
            now = screen.session.nav.getCurrentlyPlayingServiceReference()
            if now is None or now.toString() != sat_ref:
                _startup_log("AUTO_PLAY_SKIP", "reason=ZAP_BEFORE_CLOSE target=%r" % str(sat_ref)[:70])
                return
            screen.close()
            # The original SAT evStart must settle after Preview._restore()
            # before the live monitor starts its existing playback state machine.
            _defer_ui_call(lambda: _r738_autoplay_current(sat_ref, fp), 240)
        _defer_ui_call(close_and_open, 65)
        return True
    except Exception as err:
        _startup_log("AUTO_PLAY_ERROR", "queue=%s" % str(err)[:120])
        return False


'''
    src = exactly(src, '\ndef _r736_auto_map_single_sat(sat_ref, sat_name, ctx, ranked):',
                  '\n'+helpers+'def _r736_auto_map_single_sat(sat_ref, sat_name, ctx, ranked):')
    src = exactly(src,
'''                if auto_state in ("AUTO_CREATED","AUTO_REPLACED"):
                    self._manual_overrides=_load_overrides()
            except Exception as auto_error:''',
'''                if auto_state in ("AUTO_CREATED","AUTO_REPLACED"):
                    self._manual_overrides=_load_overrides()
                    _r738_queue_auto_open(self, raw, auto_state, _pick)
            except Exception as auto_error:''')
    src = exactly(src,
'''            if automap_state in ("AUTO_CREATED","AUTO_REPLACED"):
                self._manual_overrides=_load_overrides()
        except Exception as auto_err:''',
'''            if automap_state in ("AUTO_CREATED","AUTO_REPLACED"):
                self._manual_overrides=_load_overrides()
                _r738_queue_auto_open(self, raw, automap_state, _chosen)
        except Exception as auto_err:''')
    compile(src, "plugin.py", "exec")
    return src


def patch_core(src):
    # 18 candidates is an indexing optimization, not a channel-selection rule.
    # Score up to 36 distributed across P/B1/B2 so SAFE exact/FR alternatives
    # are not stranded as INDEX ONLY; the remaining candidates stay REVIEW.
    src = exactly(src,
'''        budget=18
        for i in range(18):''',
'''        budget=36
        for i in range(36):''')
    compile(src, "core.py", "exec")
    return src
