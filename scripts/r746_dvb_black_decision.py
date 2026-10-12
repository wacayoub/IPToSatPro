# -*- coding: utf-8 -*-
"""R74.6: A DVB frontend LOCKED / PMT is not a decoded picture.

Protect a truly working FTA service, but make a nondecoded black service
eligible for existing IPTV ranking after two independent samples (~850 and
2000ms). Never use signal strength alone. Preserve the native PAT crash guard.
"""
def one(src,old,new):
    count=src.count(old)
    if count != 1:
        raise AssertionError("R74.6 source drift count=%d anchor=%r"%(count,old[:145]))
    return src.replace(old,new,1)

HELPERS='''    def _r746_token(self):
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

'''
def patch_monitor(src):
    src=one(src,'''    def _r745_tp_key(self):''',HELPERS+'''    def _r745_tp_key(self):''')
    # Start nonblocking native video evidence sampling at 850ms after SAT zap.
    src=one(src,'''        self._r744_arm_access_followup()
        # Never SmartMatch against a partially built initial JSONL catalogue.''',
'''        self._r744_arm_access_followup()
        self._r746_arm_video_sample()
        # Never SmartMatch against a partially built initial JSONL catalogue.''')
    # R74.5 incorrectly invalidated confirmed transponder loss merely from
    # frontend LOCKED / PMT, without confirming decoded TV picture.
    src=one(src,'''        if live=="LOCKED" or self._sat_pmt_pid()>0:
            self._r745_discard_bad_tp("FRONTEND_RECOVERED")
            return''',
'''        if self._r746_native_picture():
            self._r745_discard_bad_tp("NATIVE_VIDEO_CONFIRMED")
            return
        if live=="LOCKED" or self._sat_pmt_pid()>0:
            self._log("DVB_LOCK_NO_VIDEO","sat='%s' tuner=%s pmt=%d -> retain proof until 2s"%
                (self.current_sat_name,live,self._sat_pmt_pid()))
            return''')
    # Prevent premature proof loss during the PAT/PMT wait; fallback branch
    # still checks actual decoded picture before native switch.
    src=one(src,'''            if str(self._sat_tuner_state() or "?").upper()=="LOCKED" or self._sat_pmt_pid()>0 or self.video_event_seen:
                self.native_pat_guard_pending=False
                self._r745_discard_bad_tp("RECOVERED_DURING_PMTPAT_GUARD")
                return''',
'''            if self._r746_native_picture():
                self.native_pat_guard_pending=False
                self._r745_discard_bad_tp("NATIVE_VIDEO_RECOVERED")
                return
            if str(self._sat_tuner_state() or "?").upper()=="LOCKED":
                # LOCKED without video: R74.4 two-second observer arbitrates.
                self.native_pat_guard_pending=False
                self._log("DVB_LOCK_NO_VIDEO","sat='%s' still black during PMT guard"%self.current_sat_name)
                return''')
    # A reused failed TP that later says LOCKED may still be black.
    # Do not invalidate actual TUNE_FAILED evidence until video is verified.
    src=one(src,'''            if live=="LOCKED" or self._sat_pmt_pid()>0:
                self._r745_discard_bad_tp("LATE_TUNER_LOCK")
                return False''',
'''            if live=="LOCKED" or self._sat_pmt_pid()>0:
                if self._r746_black_active():
                    self._fallback_crypto_gate=True
                    self.crypted_state="?"
                    self._log("DVB_BLACK_ALLOW","sat='%s' recovered lock but no DVB picture"%self.current_sat_name)
                    return True
                return False''')
    src=one(src,'''            if str(self._sat_tuner_state() or "?").upper()=="LOCKED":
                # LOCKED without video: R74.4 two-second observer arbitrates.''',
'''            if (str(self._sat_tuner_state() or "?").upper()=="LOCKED"
                    and not self._r746_black_active()):
                # LOCKED without video: R74.4 two-second observer arbitrates.''')

    # Re-enable encrypted fallback only once 2 samples show no DVB picture.
    src=one(src,'''        live_state = self._is_crypted()
        if live_state is True:
            self._fallback_crypto_gate = True''',
'''        if self._r746_black_active():
            self._fallback_crypto_gate=True
            self.crypted_state="?"
            self._log("DVB_BLACK_ALLOW","sat='%s' tuner=%s no decoded picture -> IPTV"%
                (self.current_sat_name,self.tuner_state))
            return True
        live_state = self._is_crypted()
        if live_state is True:
            self._fallback_crypto_gate = True''')
    # Live FTA is protected unless independently proven video is absent at 2s.
    src=one(src,'''        if tuner=="LOCKED" and live is False:
            self.crypted_state="NO"
            self._fallback_crypto_gate=False''',
'''        if tuner=="LOCKED" and live is False and self._r746_stable_black():
            self._r746_black_token=current
            self._fallback_crypto_gate=None
            self.crypted_state="?"
            self._log("DVB_BLACK_FALLBACK","sat='%s' tuner=LOCKED first=FTA video=ABSENT after=2000ms"%(
                self.current_sat_name))
            self._fallback_with_native_pat_guard()
            return
        if tuner=="LOCKED" and live is False:
            self.crypted_state="NO"
            self._fallback_crypto_gate=False''')
    # Bypass R74.4's provisional FTA guard only for independently sampled
    # native black screen, not just for a single missing signal reading.
    src=one(src,'''        elif signal=="LOCKED" and self._is_crypted() is False and self._static_crypted_state_fast() is not True:''',
'''        elif (signal=="LOCKED" and self._is_crypted() is False
              and self._static_crypted_state_fast() is not True
              and not self._r746_black_active()):''')
    # Before final stream switch, check again whether real native image appeared.
    src=one(src,'''        self.native_pat_guard_pending = False
        pmt = self._sat_pmt_pid()
        self._log("DVB_PAT_GUARD_OK",''',
'''        if (getattr(self,"_r746_black_token",None)==self._r746_token()
                and self._r746_native_picture()):
            self._r746_black_token=None
            self.native_pat_guard_pending=False
            self._log("DVB_BLACK_CANCEL","native video recovered during guard")
            return
        self.native_pat_guard_pending = False
        pmt = self._sat_pmt_pid()
        self._log("DVB_PAT_GUARD_OK",''')
    compile(src,"monitor.py","exec")
    return src
