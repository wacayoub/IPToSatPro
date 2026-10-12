#!/usr/bin/env python3
"""R74.11 Preview hotfix: remain in Preview; SAFE AUTO priority provider > language > resolution.

Preserves protected manual mappings, candidate safety, SAT identity, timeshift,
player/monitor files and the separate TOD/beIN AAC fix in monitor.py.
In Preview, AUTO still chooses and saves SAFE candidates, but no longer
closes Preview to start a live channel. OK's timed video test stays intact.
Use --check (read only), --apply, or --rollback; restart Enigma2 GUI after edits.
"""
import argparse
import os
import stat
import tempfile
import shutil
from pathlib import Path

TARGET=Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/plugin.py")
TAG="R7411_STAY_PREVIEW_PROVIDER_LANGUAGE_RESOLUTION"
BACKUP_NAME="plugin.py.r7411-preview-original.bak"

RESOLUTION_FUNCTION='''def _r7411_resolution_rank(channel, width=0, height=0):
    """Prefer measured video dimensions; never conflate quality labels with proof."""
    try:
        w, h = int(width or 0), int(height or 0)
    except (ValueError, TypeError):
        w = h = 0
    if w > 0 and h > 0:
        tier = (5 if h >= 4000 else 4 if h >= 1900 or w >= 3500
                else 3 if h >= 1000 else 2 if h >= 680 else 1)
        return (tier, 1, w * h)
    import re
    label = " ".join(str((channel or {}).get(field) or "")
                     for field in ("quality", "resolution", "name")).upper()
    if re.search(r"(?<![A-Z0-9])(8K|4320P?)(?![A-Z0-9])", label):
        tier = 5
    elif re.search(r"(?<![A-Z0-9])(4K|UHD|2160P?|3840P?)(?![A-Z0-9])", label):
        tier = 4
    elif re.search(r"(?<![A-Z0-9])(FHD|FULL\\s*HD|1080P?)(?![A-Z0-9])", label):
        tier = 3
    elif re.search(r"(?<![A-Z0-9])(HD|720P?)(?![A-Z0-9])", label):
        tier = 2
    elif re.search(r"(?<![A-Z0-9])(SD|576P?|480P?)(?![A-Z0-9])", label):
        tier = 1
    else:
        tier = 0
    return (tier, 0, 0)


'''

ORIGINAL_AUTO_CACHE='                _r738_queue_auto_open(self, raw, auto_state, _pick)'
ORIGINAL_AUTO_FRESH='            _r738_queue_auto_open(self, raw, automap_state, _chosen)'
ORIGINAL_SELECTOR='''            order=(tier,iband,identity,audio_fit,float(score or 0),measured,qual,
                   w*hh,-priority,-pos)'''
ORIGINAL_PREVIEW='''            return (d_band,exact,identity,provider,score,measured,w*h,
                    -int(ch.get("server_priority") or 0))'''
ORIGINAL_PROVIDER='''            provider=int(bool(details.get("provider_identity")))
            health=self._health_record(ch)'''

REPLACE_SELECTOR='''            # R7411_STAY_PREVIEW_PROVIDER_LANGUAGE_RESOLUTION
            # Safety and same-channel identity gate FIRST. Within equally
            # valid matches: exact provider > SAT audio language > best picture.
            # Final score and server position only resolve ties.
            provider=int(bool(details.get("provider_identity")))
            resolution=_r7411_resolution_rank(ch,w,hh)
            order=(tier,iband,identity,provider,audio_fit,resolution,
                   float(score or 0),measured,qual,-priority,-pos)'''

REPLACE_PREVIEW_PROVIDER='''            provider=int(bool(details.get("provider_identity")))
            sat_languages,_lang_proof=_r74_sat_original_languages(
                self.sat_ref_string, context or {})
            iptv_lang=_r74_normalize_lang(ch.get("language"))
            language_fit=(2 if sat_languages and iptv_lang in sat_languages
                          else 0 if sat_languages and iptv_lang else 1)
            health=self._health_record(ch)'''

REPLACE_PREVIEW='''            resolution=_r7411_resolution_rank(ch,w,h)
            return (d_band,exact,identity,provider,language_fit,resolution,
                    score,measured,-int(ch.get("server_priority") or 0))'''


def exactly(text, previous, updated, label):
    count=text.count(previous)
    if count != 1:
        raise ValueError("%s anchor count %d (expected 1); wrong R74 version" %
                         (label, count))
    return text.replace(previous,updated,1)


def patch_plugin(source):
    if TAG in source:
        return source,"already-installed"
    # Fail closed on incompatible releases. Applying to R74.10 never touches
    # monitor.py or the separate direct ServiceApp beIN AAC workaround.
    for anchor in ("def _r74_normalize_lang(value):",
                   "def _r736_choose_best_safe(",
                   "def _sort_candidates_with_cached_evidence(",
                   "def _r738_queue_auto_open("):
        if anchor not in source:
            raise ValueError("Missing required R74 code: " + anchor)
    changed=exactly(source,"def _r74_normalize_lang(value):",
                    RESOLUTION_FUNCTION+"def _r74_normalize_lang(value):",
                    "resolution function")
    changed=exactly(changed,ORIGINAL_SELECTOR,REPLACE_SELECTOR,"AUTO rank")
    changed=exactly(changed,ORIGINAL_PROVIDER,REPLACE_PREVIEW_PROVIDER,
                    "Preview language rank")
    changed=exactly(changed,ORIGINAL_PREVIEW,REPLACE_PREVIEW,"Preview order")
    changed=exactly(changed,ORIGINAL_AUTO_CACHE,
                    '''                _startup_log("PREVIEW_STAY_OPEN",
                    "source=CACHE auto=%s sat=%r" % (auto_state,self.sat_name))''',
                    "cached Preview auto-play")
    changed=exactly(changed,ORIGINAL_AUTO_FRESH,
                    '''            _startup_log("PREVIEW_STAY_OPEN",
                "source=RANKED auto=%s sat=%r" % (automap_state,self.sat_name))''',
                    "fresh Preview auto-play")
    compile(changed,"plugin.py","exec")
    return changed,"ready"


def atomic_write(path, content, mode):
    fd,tmp=tempfile.mkstemp(prefix=".r7411-",suffix=".tmp",dir=str(path.parent))
    try:
        with os.fdopen(fd,"wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp,stat.S_IMODE(mode))
        os.replace(tmp,str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    opts=parser.add_mutually_exclusive_group()
    opts.add_argument("--check",action="store_true",help="default: read-only preflight")
    opts.add_argument("--apply",action="store_true",help="back up and patch plugin.py")
    opts.add_argument("--rollback",action="store_true",help="restore backed-up plugin.py")
    parser.add_argument("--target",type=Path,default=TARGET,help=argparse.SUPPRESS)
    args=parser.parse_args(argv)
    target=args.target
    backup=target.with_name(BACKUP_NAME)
    if not target.is_file():
        parser.error("plugin.py is missing")
    original=target.read_bytes()
    mode=target.stat().st_mode
    try:
        decoded=original.decode("utf-8")
    except UnicodeDecodeError:
        parser.error("plugin.py not UTF-8")
    if args.rollback:
        if TAG not in decoded or not backup.is_file():
            parser.error("not a recognized hotfix installation or backup missing")
        previous=backup.read_bytes()
        compile(previous,"plugin.py","exec")
        atomic_write(target,previous,mode)
        print("ROLLBACK_OK: original Preview restored; restart Enigma2 GUI")
        return 0
    try:
        new_text,status=patch_plugin(decoded)
    except (ValueError,SyntaxError) as e:
        parser.error(str(e))
    if not args.apply:
        print("CHECK_OK:",status)
        print("Preview remains open after SAFE AUTO selection; OK video test untouched")
        print("Ranking: SAFE and identity > PROVIDER > LANGUAGE > RESOLUTION > score")
        print("Manual locks, source files, relay, monitor and beIN AAC fix untouched")
        return 0
    if status=="already-installed":
        print("ALREADY_INSTALLED")
        return 0
    if backup.exists():
        parser.error("backup exists; refusing to overwrite prior version")
    shutil.copy2(str(target),str(backup))
    try:
        atomic_write(target,new_text.encode("utf-8"),mode)
    except Exception:
        atomic_write(target,original,mode)
        raise
    print("PATCH_OK: backup=" + str(backup))
    print("Restart Enigma2 GUI. Preview stays open; AUTO mapping remains active.")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
