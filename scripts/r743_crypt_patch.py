# -*- coding: utf-8 -*-
"""R74.3: live DVB crypto can change NO -> YES during the first SAT zap.

Tri-state access, bounded first-zap recheck, no cross-zap timer bleed, verified
DVB-video protection, manual lock recovers when stale negative access was saved.
No forced encrypted=yes, no edits to mappings or reception configuration.
"""

def one(src,old,new):
    count=src.count(old)
    if count!=1:
        raise AssertionError("R74.3 monitor drift %d: %r"%(count,old[:150]))
    return src.replace(old,new,1)

HELPERS='''    def _r743_crypto_retry(self):
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

'''
def patch_monitor(src):
    src=one(src,'''    def _encrypted_fallback_allowed_once(self):''',
            HELPERS+'''    def _encrypted_fallback_allowed_once(self):''')
    src=one(src,'''        if self._fallback_crypto_gate is True or self._fallback_crypto_gate is False:
            return self._fallback_crypto_gate

        # Manual mappings created by current builds already store sat_crypted. Trust that
        # explicit fact so CH+/CH- does not synchronously re-scan lamedb on every first visit.
        saved_access = self._manual_lock_saved_access()
        if saved_access is True:
            self._fallback_crypto_gate = True
            self.crypted_state = "YES"
            return True
        if saved_access is False:
            self._fallback_crypto_gate = False
            self.crypted_state = "NO"
            return False

        live_state = self._is_crypted()
        if live_state is True:
            self._fallback_crypto_gate = True
            self.crypted_state = "YES"
            return True

        static_state = self._static_crypted_state_fast()
        if static_state is True:''',
'''        # A stored sat_crypted=False is a historic observation, NOT immutable
        # evidence. Refresh positive live/static CAIDs on every requested
        # fallback before consulting any negative cached result.
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
        if static_state is True:''')
    anchor='''        if static_state is False:
            # r41: OpenATV/Vu+ can return a stale clear flag after leaving our IPTV bridge and'''
    new='''        # A user-verified manual IPTV lock is explicit playback intent. A saved
        # negative may have been captured at SAT start before PMT/CA arrived.
        # Only recover after grace, and never override confirmed DVB video.
        if (self.direct_mapping_source=="MANUAL_LOCK" and not self.video_event_seen
                and saved_access is False and self._same_sat_still_playing()
                and (time.time()-float(self.current_sat_started_at or 0))>=0.88):
            self._fallback_crypto_gate=True
            self.crypted_state="?"
            self._log("CRYPT_MANUAL_RECOVER","sat='%s' saved=NO provisional=no-native-video -> IPTV manual lock"%
                self.current_sat_name)
            return True
        if saved_access is False:
            self._fallback_crypto_gate=False
            self.crypted_state="NO"
            return False
        if static_state is False:
            # r41: OpenATV/Vu+ can return a stale clear flag after leaving our IPTV bridge and'''
    src=one(src,anchor,new)
    src=one(src,'''    def _fallback_with_native_pat_guard(self):
        # Central product rule: clear/unknown DVB services never auto-switch to IPTV.
        # This is intentionally checked only on a real fallback request, not on every zap.
        if not self._encrypted_fallback_allowed_once():''',
'''    def _fallback_with_native_pat_guard(self):
        # During a first zap, PMT/CA access may still be initializing.
        # A bounded deferred recheck avoids caching a transient NO as true FTA.
        if self._r743_crypto_pending():
            return
        if not self._encrypted_fallback_allowed_once():''')
    src=one(src,'''                elif saved_access is False:
                    self._fallback_crypto_gate = False; self.crypted_state = "NO"
                else:
                    crypted = self._is_crypted()''',
'''                elif saved_access is False:
                    # Negative saved on the first zap is provisional: never
                    # hard-cache FTA before live CA/PMT recheck has settled.
                    self._fallback_crypto_gate = None; self.crypted_state = "?"
                else:
                    crypted = self._is_crypted()''')
    compile(src,"monitor.py","exec")
    return src
