#!/usr/bin/env python3
"""R74.13 reversible Preview OK fix: keep the candidate table displayed.

Existing R73.7 code does Screen.hide() for 8s after OK, which hides the
candidate table and can appear to close Preview. Keep the video playing as
before but retain the browser over the video. No changes to selecting,
candidate count, auto mapping, ServiceApp, monitor, relay or timeshift.
Apply only after R7411 + R7412; check first, rollback supported.
"""
import argparse
import os
import shutil
import stat
import tempfile
from pathlib import Path

TARGET = Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/plugin.py")
BACKUP_NAME = "plugin.py.r7413-preview-inline-original.bak"
TAG = "R7413_PREVIEW_INLINE_NO_HIDE"
OLD_CALL = '''        if not self.finished:
            self._r737_show_video_fullscreen()

    def _play_current_mode(self):'''
NEW_CALL = '''        if not self.finished:
            self._r7413_keep_preview_visible()

    def _play_current_mode(self):'''
OLD_METHOD = '    def _r737_show_video_fullscreen(self):'
NEW_METHOD = '''    def _r7413_keep_preview_visible(self):
        """Keep the two-panel Preview table visible above the running video.

        OK starts the SAME player through _play_current_mode(); this method
        only handles presentation. A prior hidden window is restored if one
        was somehow active; never start the fullscreen hide timer again.
        """
        try:
            timer = getattr(self, "_r737_video_timer", None)
            if timer is not None:
                timer.stop()
            if getattr(self, "_r737_video_visible", False):
                self._r737_video_visible = False
                self.show()
        except Exception as error:
            _startup_log("PREVIEW_INLINE", "restore_error=%s" % str(error)[:100])
        try:
            self["detail"].setText(
                "PREVIEW ACTIVE • candidate list stays open • "
                "compare picture and audio • GREEN for verified manual lock")
        except Exception:
            pass
        _startup_log("PREVIEW_INLINE",
                     "state=TABLE_VISIBLE sat=%r iptv=%r" %
                     (str(getattr(self,"sat_name",""))[:60],
                      str((getattr(self,"channel",None) or {}).get("name",""))[:75]))

''' + OLD_METHOD


def patch(source):
    if TAG in source:
        return source, "already-installed"
    if "R7411_STAY_PREVIEW_PROVIDER_LANGUAGE_RESOLUTION" not in source:
        raise ValueError("R7411 prerequisite missing")
    if "R7412_FAST_PREVIEW_SHORTLIST" not in source:
        raise ValueError("R7412 prerequisite missing")
    if source.count(OLD_CALL) != 1:
        raise ValueError("Preview OK call changed or missing; refusing to patch")
    if source.count(OLD_METHOD) != 1:
        raise ValueError("Old Preview fullscreen method not uniquely found")
    if source.count("def _preview_selected(self):") != 1:
        raise ValueError("Preview selection handler changed")
    changed = source.replace(OLD_CALL, NEW_CALL, 1)
    changed = changed.replace(OLD_METHOD, NEW_METHOD, 1)
    compile(changed, "plugin.py", "exec")
    return changed, "ready"


def replace_atomically(path, contents, mode):
    fd, temp = tempfile.mkstemp(prefix=".r7413-", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, stat.S_IMODE(mode))
        os.replace(temp, str(path))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    options = parser.add_mutually_exclusive_group()
    options.add_argument("--check", action="store_true")
    options.add_argument("--apply", action="store_true")
    options.add_argument("--rollback", action="store_true")
    parser.add_argument("--target", type=Path, default=TARGET, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    path = args.target
    backup = path.with_name(BACKUP_NAME)
    if not path.is_file():
        parser.error("plugin.py is missing")
    original = path.read_bytes()
    mode = path.stat().st_mode
    try:
        text = original.decode("utf-8")
    except UnicodeError:
        parser.error("plugin.py is not UTF-8")
    if args.rollback:
        if TAG not in text or not backup.is_file():
            parser.error("R7413 patch or rollback backup missing")
        saved = backup.read_bytes()
        compile(saved, "plugin.py", "exec")
        replace_atomically(path, saved, mode)
        print("ROLLBACK_OK: prior Preview restored; restart Enigma2 GUI")
        return 0
    try:
        changed, status = patch(text)
    except (ValueError, SyntaxError) as error:
        parser.error(str(error))
    if not args.apply:
        print("CHECK_OK:", status)
        print("OK = start video without hiding Preview; GREEN = manual lock")
        print("R7411 ranking, R7412 24/192 candidates, TOD AAC: unchanged")
        return 0
    if status == "already-installed":
        print("ALREADY_INSTALLED")
        return 0
    if backup.exists():
        parser.error("Existing backup will not be overwritten")
    shutil.copy2(str(path), str(backup))
    try:
        replace_atomically(path, changed.encode("utf-8"), mode)
    except Exception:
        replace_atomically(path, original, mode)
        raise
    print("PATCH_OK: backup=" + str(backup))
    print("Restart Enigma2 GUI; OK keeps both Preview panes visible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
