#!/usr/bin/env python3
"""IPToSatPro R74.17: native SAT wins on verified picture or LOCKED FTA.

Stops the R74.6 "black" timer, stale manual locks, and cached failure
callbacks from hijacking a working DVB FTA service. True native tune failure
still permits IPTV; encrypted SAT with no decoded picture still falls back.
No signal-percent thresholds, no changes to preview/EPG/mapping/timeshift/AAC.

Guarded --check, --apply (one backup), --rollback. Restart Enigma2 GUI.
"""
import argparse
import os
import shutil
import stat
import tempfile
from pathlib import Path

TARGET = Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/monitor.py")
BACKUP = "monitor.py.r7417-fta-signal-original.bak"
TAG = "R7417_FTA_SIGNAL_NATIVE_GUARD"

HELPER='''    # R7417_FTA_SIGNAL_NATIVE_GUARD
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

'''

PATCHES=[
    ("    def _r745_tp_key(self):",
     HELPER+"    def _r745_tp_key(self):",
     "guard helper",1),
    ('    def _fallback_with_native_pat_guard(self):',
     '''    def _fallback_with_native_pat_guard(self):
        if self._r7417_keep_sat("FALLBACK_REQUEST"):
            return''',
     "central fallback entry",1),
    ('''    def _native_pat_guard_fire(self):
        if not self.native_pat_guard_pending:''',
     '''    def _native_pat_guard_fire(self):
        if self._r7417_keep_sat("PAT_GUARD"):
            return
        if not self.native_pat_guard_pending:''',
     "native PAT release",1),
    ('''    def _fallback_if_matched(self):
        # Known manual/learned mappings are the hot path.''',
     '''    def _fallback_if_matched(self):
        if self._r7417_keep_sat("MATCH_SWITCH"):
            return
        # Known manual/learned mappings are the hot path.''',
     "final mapping selection",1),
    ('''    def _play_match(self, match, score, retry=False):
        url = match.get("url", "")''',
     '''    def _play_match(self, match, score, retry=False):
        if not retry and self._r7417_keep_sat("PLAYER_SWITCH"):
            return
        url = match.get("url", "")''',
     "last player handover",1),
    ('''        live=self._is_crypted()
        # Positive live/CAID evidence overrides provisional/saved negative.''',
     '''        if self._r7417_keep_sat("ACCESS_RECHECK_2S"):
            return
        live=self._is_crypted()
        # Positive live/CAID evidence overrides provisional/saved negative.''',
     "two second black/FTA check",1)
]


def patch(src):
    if TAG in src:
        return src,"already-installed"
    for old,new,where,count in PATCHES:
        actual=src.count(old)
        if actual!=count:
            raise ValueError("R7417 incompatible monitor at %s: expected %d anchor, found %d" %
                             (where,count,actual))
        src=src.replace(old,new,count)
    compile(src,"monitor.py","exec")
    return src,"ready"


def atomic_write(path,data,mode):
    fd,tmp=tempfile.mkstemp(prefix=".r7417-",suffix=".tmp",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(tmp,stat.S_IMODE(mode))
        os.replace(tmp,str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv=None):
    cli=argparse.ArgumentParser(description=__doc__)
    mode=cli.add_mutually_exclusive_group()
    mode.add_argument("--check",action="store_true",help="default; read-only")
    mode.add_argument("--apply",action="store_true")
    mode.add_argument("--rollback",action="store_true")
    cli.add_argument("--target",type=Path,default=TARGET,help=argparse.SUPPRESS)
    a=cli.parse_args(argv)
    target=a.target
    backup=target.with_name(BACKUP)
    if not target.is_file():
        cli.error("monitor.py not found")
    raw=target.read_bytes()
    perms=target.stat().st_mode
    try:original=raw.decode("utf-8")
    except UnicodeError:cli.error("monitor.py not UTF-8")
    if a.rollback:
        if TAG not in original or not backup.is_file():
            cli.error("Guard absent or backup missing")
        old=backup.read_bytes()
        compile(old,"monitor.py","exec")
        atomic_write(target,old,perms)
        print("ROLLBACK_OK: previous monitor.py restored; restart GUI")
        return 0
    try:new,status=patch(original)
    except (ValueError,SyntaxError) as err:cli.error(str(err))
    if not a.apply:
        print("CHECK_OK:",status)
        print("DVB picture or FTA LOCKED -> SAT; true tune failure -> normal IPTV fallback")
        print("Existing beIN TOD AAC fix, Preview and mappings untouched")
        return 0
    if status=="already-installed":
        print("ALREADY_INSTALLED")
        return 0
    if backup.exists():
        cli.error("R7417 backup already exists; refusing overwrite")
    shutil.copy2(str(target),str(backup))
    try:atomic_write(target,new.encode("utf-8"),perms)
    except Exception:
        atomic_write(target,raw,perms)
        raise
    print("PATCH_OK: backup="+str(backup))
    print("Restart Enigma2 GUI; check FTA_SIGNAL_KEEP_SAT and IPTV logs")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
