# -*- coding: utf-8 -*-
"""R74.5: reuse proven transponder NO SIGNAL to remove 5s repeated tuner waits.

This is a STRICTLY nonpersistent, evidence-based optimization. One genuine
native Enigma2 evTuneFailed is required first. Next zaps on that same DVB
transport can begin the existing guarded IPTV fallback after two frontend
checks (~180/420ms), rather than waiting for another 5s tuner failure.

OpenATV PMT/PAT guard (1250ms) and deferred evTuneFailed mainloop handling
remain intact: first ever unknown no-signal tune may still take 5s.
"""

def one(src,old,new):
    count=src.count(old)
    if count!=1:
        raise AssertionError("R74.5 source drift count=%d anchor=%r"%(count,old[:150]))
    return src.replace(old,new,1)

HELPERS='''    def _r745_tp_key(self):
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
        if live=="LOCKED" or self._sat_pmt_pid()>0:
            self._r745_discard_bad_tp("FRONTEND_RECOVERED")
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

'''
def patch_monitor(src):
    src=one(src,'''    def _r744_arm_access_followup(self):''',
            HELPERS+'''    def _r744_arm_access_followup(self):''')

    # One proof per actual native failed tune: stored only in RAM.
    src=one(src,'''        self._log("TUNE_FAIL_DEFER_FIRE", "channel='%s' event=%s native callback returned" % (self.current_sat_name, event))
        self._fallback_with_native_pat_guard()''',
'''        self._r745_confirm_no_signal()
        self._log("TUNE_FAIL_DEFER_FIRE", "channel='%s' event=%s native callback returned" % (self.current_sat_name, event))
        self._r745_no_signal_once("NATIVE_TUNE_FAILED")''')

    # Watch for NEXT zap on this proven-bad TP, not every channel scan.
    src=one(src,'''        self.timer.start(wait_ms, True)

    # ------------------------------------------------------------------
    # Native OpenATV DVB PMT/PAT crash guard''',
'''        self.timer.start(wait_ms, True)
        self._r745_arm_cached_nosignal()

    # ------------------------------------------------------------------
    # Native OpenATV DVB PMT/PAT crash guard''')

    # Avoid R74.3's 880ms crypto debounce for proven absent SAT signal.
    src=one(src,'''    def _r743_crypto_pending(self):
        """Avoid classifying early sIsCrypted==0 as confirmed FTA.''',
'''    def _r743_crypto_pending(self):
        if self._r745_cached_failure_active() and self._same_sat_still_playing():
            return False
        """Avoid classifying early sIsCrypted==0 as confirmed FTA.''')

    # Treat only the strongly proved cache path as no-signal, independently
    # of a stale sIsCrypted=0; otherwise preserve existing FTA fence.
    src=one(src,'''        # R72.4: A definite FAILED satellite tuner cannot deliver SAT video, regardless''',
'''        if self._r745_cached_failure_active() and self._same_sat_still_playing():
            live=str(self._sat_tuner_state() or "?").upper()
            if live=="LOCKED" or self._sat_pmt_pid()>0:
                self._r745_discard_bad_tp("LATE_TUNER_LOCK")
                return False
            self._fallback_crypto_gate=True
            self.crypted_state="?"
            self._log("NO_SIGNAL_CACHE_ALLOW","sat='%s' tuner=%s crypto=ANY"%
                (self.current_sat_name,live))
            return True

        # R72.4: A definite FAILED satellite tuner cannot deliver SAT video, regardless''')

    # Skip R74.4 encrypted grace when we have native proven no-signal evidence.
    src=one(src,'''        if confirmed_fail and no_signal:
            self._log("FAST_NO_SIGNAL",''',
'''        if self._r745_cached_failure_active() and self._same_sat_still_playing():
            self._log("FAST_NO_SIGNAL_CACHED","sat='%s' tuner=%s crypto=ANY"%(
                self.current_sat_name,signal))
        elif confirmed_fail and no_signal:
            self._log("FAST_NO_SIGNAL",''')

    # Later PMT readiness or lock can invalidate shortcut BEFORE the actual
    # playService; do not steal recovered DVB picture at end of safety window.
    src=one(src,'''        self.native_pat_guard_pending = False
        pmt = self._sat_pmt_pid()
        self._log("DVB_PAT_GUARD_OK",''',
'''        if self._r745_cached_failure_active():
            if str(self._sat_tuner_state() or "?").upper()=="LOCKED" or self._sat_pmt_pid()>0 or self.video_event_seen:
                self.native_pat_guard_pending=False
                self._r745_discard_bad_tp("RECOVERED_DURING_PMTPAT_GUARD")
                return
        self.native_pat_guard_pending = False
        pmt = self._sat_pmt_pid()
        self._log("DVB_PAT_GUARD_OK",''')

    # The 2s FTA timer must not restart the same fallback or turn a cached
    # no-signal into a false FTA after it was already handled.
    src=one(src,'''        if self.fallback_active or self.switch_in_progress or not self.cfg.enabled.value:
            return
        tuner=str(self._sat_tuner_state() or self.tuner_state or "?").upper()''',
'''        if (getattr(self,"_r745_attempt_token",None)==current
                or self.fallback_active or self.switch_in_progress
                or not self.cfg.enabled.value):
            return
        tuner=str(self._sat_tuner_state() or self.tuner_state or "?").upper()''')

    compile(src,"monitor.py","exec")
    return src
