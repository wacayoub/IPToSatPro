#!/usr/bin/env python3
"""R74.14: instant indexed Preview seed and explicit GREEN manual lock without OK.

Read-only --check by default; --apply backs up only plugin.py; --rollback
restores original. Requires R7411/R7412/R7413 installed. No changes to core.py,
monitor.py, player, MPEG-TS relay, native SAT metadata, or beIN AAC workaround.

First paint: bounded exact-name index (no full scan/scoring/network). These
results remain REVIEW until background rank finishes; users can explicitly
GREEN lock a selected source without testing. Never auto-map from a seed.
Manual unverified lock is clearly labeled; VERIFIED/PLAYING cannot be faked.
"""
import argparse
import os
import shutil
import stat
import tempfile
from pathlib import Path

TARGET=Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/plugin.py")
BACKUP="plugin.py.r7414-fast-lock-original.bak"
TAG="R7414_PREVIEW_FAST_SEED_MANUAL_LOCK"

SEED_HELPER='''def _r7414_fast_exact_seed(sat_name, catalog):
    """Bounded first-paint index query; never score or probe IPTV playback.

    Existing Catalog._exact is indexed at initial catalogue creation. Limit
    both work and output, retaining representation from all server roles.
    """
    try:
        from .core import normalize_name
        key = normalize_name(sat_name or "")
        groups = getattr(catalog, "_exact", None) or {}
        sources = groups.get(key, ()) if key else ()
        result = []
        seen = set()
        counts = {}
        for ch in sources[:96]:
            if not isinstance(ch, dict) or not ch.get("url"):
                continue
            role = str(ch.get("server_role") or "SERVER")
            if counts.get(role, 0) >= 4:
                continue
            ident = str(ch.get("url"))
            if ident in seen:
                continue
            seen.add(ident)
            counts[role] = counts.get(role, 0) + 1
            item = dict(ch)
            item["_manual_candidate"] = True
            item["_r7414_seed"] = True
            item["_preview_score"] = 0.0
            item["_preview_details"] = {
                "review_reason":"INSTANT INDEX - unverified; press OK or GREEN manual lock"}
            result.append(item)
            if len(result) >= 12:
                break
        return result
    except Exception:
        return []


'''

SAT_ANCHOR='''        # r42: do not paint a blocking "Loading cached candidates" row.  Cursor movement stays
        # O(1), then the tiny exact/index lane is executed immediately.  The fuller bounded
        # candidate set is expanded only after the first list is already visible.
        self.sat_name, self.context = clean_display_name(row.get("name") or "SAT channel"), {}'''
SAT_REPLACEMENT='''        # R7414_PREVIEW_FAST_SEED_MANUAL_LOCK
        # Show an INSTANT unverified subset from an already-built exact index.
        # Keep full 24-result background ranking and SAFE auto-map unchanged.
        try:
            cat = MONITOR.catalog if MONITOR is not None else None
            first = _r7414_fast_exact_seed(row.get("name") or "", cat)
        except Exception:
            first = []
        if first:
            self._candidate_cache[key] = (
                clean_display_name(row.get("name") or "SAT channel"), {}, first, False)
            self._load_selected_sat_candidates()
            self["status"].setText(
                "%d instant unverified candidates • ranking up to 24 in background" % len(first))
            _startup_log("PREVIEW_INSTANT_SEED",
                         "count=%d sat=%r" % (len(first), str(row.get("name") or "")[:70]))
            return
        # No indexed exact match: keep existing async full-rank behavior.
        self.sat_name, self.context = clean_display_name(row.get("name") or "SAT channel"), {}'''

LOCK_ORIGINAL='''        confirmed = result == "PLAYING"
        if not confirmed or not exact_active:
            self["detail"].setText("Preview required • OK → PLAYING, or verify the visible picture/audio after player open.")
            return

        audio_rec = self._preview_audio.get((key, selected_fp)) or {}
        audio_state = str(audio_rec.get("state") or "")
        if audio_state == "CHECKING":'''
LOCK_REPLACE='''        confirmed = result == "PLAYING"
        # GREEN is an explicit human MANUAL LOCK request; unlike unattended
        # Auto Mapping it does not require OK playback to have happened.
        unverified_manual = not (confirmed and exact_active)
        if unverified_manual:
            _startup_log("PREVIEW_MANUAL_UNVERIFIED",
                         "sat=%r iptv=%r no_video_claim=1" %
                         (self.sat_name, str(selected.get("name") or "")[:80]))

        audio_rec = self._preview_audio.get((key, selected_fp)) or {}
        audio_state = str(audio_rec.get("state") or "")
        if not unverified_manual and audio_state == "CHECKING":'''

AUDIO_MISMATCH_ORIGINAL='''        if audio_state == "MISMATCH":
            sat_audio'''
AUDIO_MISMATCH_REPLACE='''        if not unverified_manual and audio_state == "MISMATCH":
            sat_audio'''

FORCED_ORIGINAL='''        forced = before in ("REJECT", "REVIEW", "USER REJECT")'''
FORCED_REPLACE='''        forced = unverified_manual or before in ("REJECT", "REVIEW", "USER REJECT")'''

SAVED_ORIGINAL='''            self.current_result = "PLAYING"
            self.preview_ok = True
            self._preview_results[(key, selected_fp)] = "PLAYING"
            self._render_sat_list(keep_index=True)'''
SAVED_REPLACE='''            if unverified_manual:
                self.current_result = "MANUAL LOCKED"
                self.preview_ok = False
                # Never fabricate a verified playback result.
            else:
                self.current_result = "PLAYING"
                self.preview_ok = True
                self._preview_results[(key, selected_fp)] = "PLAYING"
            self._render_sat_list(keep_index=True)'''

STATUS_ORIGINAL='''            if forced:
                self["status"].setText("SAFE • LOCKED • PREVIEW VERIFIED • previous REVIEW/REJECT corrected • browser stays open")'''
STATUS_REPLACE='''            if unverified_manual:
                self["status"].setText("MANUAL LOCK SAVED • NOT VIDEO/AUDIO VERIFIED • browser stays open")
                self["detail"].setText("Selected IPTV candidate saved without test • OK can verify later • GREEN can correct again")
            elif forced:
                self["status"].setText("SAFE • LOCKED • PREVIEW VERIFIED • previous REVIEW/REJECT corrected • browser stays open")'''



FAILED_VERIFY_ORIGINAL='''        if result == "VERIFY" and exact_active:
            if not self._preview_player_active():
                self["detail"].setText("The preview player is no longer on this source • press OK to retry")
                return
            # r42: GREEN itself is the explicit human confirmation. No second Yes/No popup.'''
FAILED_VERIFY_REPLACE='''        if result == "VERIFY" and exact_active and self._preview_player_active():
            # r42: GREEN itself is the explicit human confirmation. No second Yes/No popup.'''

GREEN_CAPTION_ORIGINAL='''        self["key_green"] = Label("VERIFIED LOCK")'''
GREEN_CAPTION_REPLACE='''        self["key_green"] = Label("MANUAL LOCK")'''

GREEN_FOCUS_ORIGINAL='''            self["detail"].setText("GREEN locks a tested IPTV source • press RIGHT, select source, OK, wait PLAYING")'''
GREEN_FOCUS_REPLACE='''            self["detail"].setText("GREEN saves selected IPTV source without mandatory OK test • press RIGHT, select candidate")'''

def once(text,old,new,label):
    n=text.count(old)
    if n != 1:
        raise ValueError("R74.14 incompatible %s anchor (count %d)" % (label,n))
    return text.replace(old,new,1)


def patch(source):
    if TAG in source:
        return source,"already-installed"
    for key in ("R7411_STAY_PREVIEW_PROVIDER_LANGUAGE_RESOLUTION",
                "R7412_FAST_PREVIEW_SHORTLIST","R7413_PREVIEW_INLINE_NO_HIDE"):
        if key not in source:
            raise ValueError("Prerequisite missing: "+key)
    source=once(source,"def _r7411_resolution_rank(channel, width=0, height=0):",
                SEED_HELPER+"def _r7411_resolution_rank(channel, width=0, height=0):",
                "seed helper")
    source=once(source,SAT_ANCHOR,SAT_REPLACEMENT,"SAT first-paint")
    source=once(source,FAILED_VERIFY_ORIGINAL,FAILED_VERIFY_REPLACE,"failed Preview green lock")
    source=once(source,GREEN_CAPTION_ORIGINAL,GREEN_CAPTION_REPLACE,"button label")
    source=once(source,GREEN_FOCUS_ORIGINAL,GREEN_FOCUS_REPLACE,"GREEN focus hint")
    source=once(source,LOCK_ORIGINAL,LOCK_REPLACE,"manual lock verification gate")
    source=once(source,AUDIO_MISMATCH_ORIGINAL,AUDIO_MISMATCH_REPLACE,"audio mismatch gate")
    source=once(source,FORCED_ORIGINAL,FORCED_REPLACE,"forced manual lock")
    source=once(source,SAVED_ORIGINAL,SAVED_REPLACE,"saved state")
    source=once(source,STATUS_ORIGINAL,STATUS_REPLACE,"unverified lock status")
    compile(source,"plugin.py","exec")
    return source,"ready"


def atomic_write(path,content,mode):
    fd,tmp=tempfile.mkstemp(prefix=".r7414-",suffix=".tmp",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as handle:
            handle.write(content);handle.flush();os.fsync(handle.fileno())
        os.chmod(tmp,stat.S_IMODE(mode))
        os.replace(tmp,str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    act=parser.add_mutually_exclusive_group()
    act.add_argument("--check",action="store_true")
    act.add_argument("--apply",action="store_true")
    act.add_argument("--rollback",action="store_true")
    parser.add_argument("--target",type=Path,default=TARGET,help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    path=args.target;backup=path.with_name(BACKUP)
    if not path.is_file():
        parser.error("plugin.py missing")
    raw=path.read_bytes();mode=path.stat().st_mode
    try:src=raw.decode("utf-8")
    except UnicodeError:parser.error("plugin.py is not UTF-8")
    if args.rollback:
        if TAG not in src or not backup.is_file():
            parser.error("Recognized hotfix or backup missing")
        older=backup.read_bytes();compile(older,"plugin.py","exec")
        atomic_write(path,older,mode)
        print("ROLLBACK_OK: Preview R74.13 restored; restart GUI")
        return 0
    try:updated,status=patch(src)
    except (ValueError,SyntaxError) as e:parser.error(str(e))
    if not args.apply:
        print("CHECK_OK:",status)
        print("First paint: bounded exact index seed; background ranked 24 retained")
        print("GREEN: manual lock without OK allowed; unverified state labeled")
        print("Protects core/monitor/relay, AAC fix, Auto Mapping and existing locks")
        return 0
    if status=="already-installed":
        print("ALREADY_INSTALLED")
        return 0
    if backup.exists():
        parser.error("Rollback backup exists; refusing overwrite")
    shutil.copy2(str(path),str(backup))
    try:atomic_write(path,updated.encode("utf-8"),mode)
    except Exception:
        atomic_write(path,raw,mode)
        raise
    print("PATCH_OK: backup="+str(backup))
    print("Restart Enigma2 GUI; test instant candidates and GREEN manual lock")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
