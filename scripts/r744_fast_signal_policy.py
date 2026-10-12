# -*- coding: utf-8 -*-
"""R74.4: fast DVB priority + 2 second initial-FTA reassessment.

Priorities:
  TUNE_FAILED/NO_LOCK etc + any crypto status -> IPTV through existing safe
    deferred tuner-failure and native PMT/PAT guards.
  Confirmed encrypted + signal -> IPTV without 880ms crypto postponement.
  LOCKED + still clear after 2s -> SAT.
  First-read clear + later encrypted at 2s -> IPTV without second zap.

No SNR=0 shortcut; TUNING is not a signal failure.
No fuzzy score/mapping change and no runtime settings mutation.
"""

def one(src,old,new):
    amount=src.count(old)
    if amount!=1:
        raise AssertionError("R74.4 drift %s %s"%(amount,repr(old[:125])))
    return src.replace(old,new,1)

HELPERS='''    def _r744_arm_access_followup(self):
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
        if self.fallback_active or self.switch_in_progress or not self.cfg.enabled.value:
            return
        tuner=str(self._sat_tuner_state() or self.tuner_state or "?").upper()
        self.tuner_state=tuner
        failures=("TUNE_FAILED","FAILED","NO_SIGNAL","NO_LOCK","NOT_LOCKED","UNLOCKED")
        if tuner in failures and bool(getattr(getattr(self.cfg,"fallback_no_signal",None),"value",True)):
            self._log("FAST_NO_SIGNAL","sat='%s' tuner=%s crypto=ANY"% (self.current_sat_name,tuner))
            self._fallback_crypto_gate=None
            self._fallback_with_native_pat_guard()
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
        if tuner=="LOCKED" and live is False:
            self.crypted_state="NO"
            self._fallback_crypto_gate=False
            self._log("SIGNAL_FTA_KEEP_SAT","sat='%s' tuner=LOCKED crypted=NO after=2000ms"%
                self.current_sat_name)
            return
        self.crypted_state="?"
        self._log("CRYPT_UNKNOWN_2S","sat='%s' tuner=%s live=%s -> keep SAT until evidence"%
            (self.current_sat_name,tuner,live))

'''
def patch_monitor(src):
    src=one(src,'''    def _r743_crypto_retry(self):''',HELPERS+'''    def _r743_crypto_retry(self):''')
    # Establish the deferred check on every real SAT service start. The native
    # SAT tuner work continues without waiting for this check.
    src=one(src,'''        if not self.cfg.enabled.value:
            self._set_state("DISABLED", "Automatic fallback is disabled"); self._log("SKIP_DISABLED", "channel='%s'" % self.current_sat_name); return
        # Never SmartMatch against a partially built initial JSONL catalogue.''',
'''        if not self.cfg.enabled.value:
            self._set_state("DISABLED", "Automatic fallback is disabled"); self._log("SKIP_DISABLED", "channel='%s'" % self.current_sat_name); return
        self._r744_arm_access_followup()
        # Never SmartMatch against a partially built initial JSONL catalogue.''')
    # Critical: old R74.3 manual-lock escape can turn a real FTA signal into
    # IPTV after only 880ms. Explicit user priority says ONLY signal+FTA stays
    # on SAT. Positive crypted evidence or a failed tuner can still bypass.
    src=one(src,'''        if (self.direct_mapping_source=="MANUAL_LOCK" and not self.video_event_seen
                and saved_access is False and self._same_sat_still_playing()
                and (time.time()-float(self.current_sat_started_at or 0))>=0.88):
            self._fallback_crypto_gate=True
            self.crypted_state="?"
            self._log("CRYPT_MANUAL_RECOVER","sat='%s' saved=NO provisional=no-native-video -> IPTV manual lock"%
                self.current_sat_name)
            return True
        if saved_access is False:''',
'''        # Historical manual sat_crypted=False is NOT authority over fresh
        # positive CA evidence. Without such evidence, a LOCKED + clear
        # signal remains DVB regardless of the saved IPTV candidate.
        if saved_access is False:''')
    src=one(src,'''        if self._r743_crypto_pending():
            return
        if not self._encrypted_fallback_allowed_once():''',
'''        signal=str(self.tuner_state or "").upper().strip()
        no_signal=bool(getattr(getattr(self.cfg,"fallback_no_signal",None),"value",True))
        confirmed_fail=signal in ("TUNE_FAILED","FAILED","NO_SIGNAL","NO_LOCK","NOT_LOCKED","UNLOCKED")
        if confirmed_fail and no_signal:
            self._log("FAST_NO_SIGNAL","sat='%s' tuner=%s crypto=ANY"% (self.current_sat_name,signal))
        elif self._is_crypted() is True:
            self._log("FAST_SIGNAL_CRYPTED","sat='%s' source=LIVE -> IPTV"%self.current_sat_name)
        elif signal=="LOCKED" and self._is_crypted() is False and self._static_crypted_state_fast() is not True:
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
        if not self._encrypted_fallback_allowed_once():''')
    compile(src,"monitor.py","exec")
    return src
