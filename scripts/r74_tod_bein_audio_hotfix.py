#!/usr/bin/env python3
"""IPToSatPro R74 audio hotfix: read-only check, guarded apply, safe rollback.

In Auto player mode, send AR BEIN SPORTS and source-marked TOD/beIN directly
to ServiceApp instead of DVB localhost /ts, which can lose AAC audio.
Does not change other channels, mapping data, media binaries or relay code.
A service type switch can affect timeshift for the affected beIN channels.
"""
import argparse
import os
import shutil
import stat
import tempfile
from pathlib import Path

TARGET = Path('/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/monitor.py')
ANCHOR = '        return bool("tod" in raw and "event" in raw and "sport" in raw)'
TAG = 'R74_TOD_BEIN_DIRECT_AUDIO'
REPLACEMENT = '''        # R74_TOD_BEIN_DIRECT_AUDIO: source audio works in direct IPTV
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
                    or (bein and tod_origin) or ar_bein)'''


def patch(source):
    """Fail closed if the installed monitor differs from the verified R74 code."""
    if TAG in source:
        return source, 'already-installed'
    if source.count(ANCHOR) != 1:
        raise ValueError('Unexpected monitor.py: missing or duplicate audio guard anchor')
    start = source.find('    def _audio_sensitive_stream(')
    stop = source.find('    def _audio_safe_serviceapp_required(', start)
    pos = source.find(ANCHOR)
    if not (start >= 0 and stop > start and start < pos < stop):
        raise ValueError('Unexpected monitor.py: target anchor is not in audio guard')
    updated = source.replace(ANCHOR, REPLACEMENT, 1)
    compile(updated, str(TARGET), 'exec')
    return updated, 'ready'


def atomic_write(path, content, original_mode):
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(prefix='.monitor-audio-', suffix='.tmp',
                                   dir=str(path.parent))
        with os.fdopen(fd, 'wb') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, stat.S_IMODE(original_mode))
        os.replace(tmp, str(path))
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--check', action='store_true', help='read-only; default')
    modes.add_argument('--apply', action='store_true', help='back up and patch')
    modes.add_argument('--rollback', action='store_true', help='restore original')
    parser.add_argument('--target', type=Path, default=TARGET, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    target = args.target
    backup = target.with_name('monitor.py.tod-bein-aac.original.bak')
    if not target.is_file():
        parser.error('monitor.py missing')
    original = target.read_bytes()
    original_mode = target.stat().st_mode
    try:
        original_text = original.decode('utf-8')
    except UnicodeDecodeError:
        parser.error('monitor.py is not UTF-8')

    if args.rollback:
        if not backup.is_file():
            parser.error('no hotfix backup found')
        saved = backup.read_bytes()
        compile(saved, str(target), 'exec')
        if TAG not in original_text:
            parser.error('the current monitor is not our hotfix; refusing to overwrite')
        atomic_write(target, saved, original_mode)
        print('ROLLBACK_OK: previous monitor.py restored; restart Enigma2 GUI')
        return 0

    try:
        updated, status = patch(original_text)
    except (ValueError, SyntaxError) as err:
        parser.error(str(err))

    if not args.apply:
        print('CHECK_OK: ' + status + '; backup=' +
              ('present' if backup.exists() else 'absent'))
        print('Auto player only: AR BEIN SPORTS or source-marked TOD/beIN -> direct ServiceApp')
        print('Other channels and manual player locks remain unchanged')
        return 0

    if status == 'already-installed':
        print('ALREADY_INSTALLED: no changes')
        return 0
    if backup.exists():
        parser.error('prior backup present; refusing to overwrite it')

    shutil.copy2(str(target), str(backup))
    try:
        atomic_write(target, updated.encode('utf-8'), original_mode)
    except Exception:
        atomic_write(target, original, original_mode)
        raise
    print('PATCH_OK: backup at ' + str(backup))
    print('Restart Enigma2 GUI; inspect AUDIO_SAFE_PLAYER and AUDIO_SAFE_IDENTITY in bridge.log')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
