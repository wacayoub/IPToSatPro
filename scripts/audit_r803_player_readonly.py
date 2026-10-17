#!/usr/bin/env python3
"""R80.3 playback audit — read-only. No stream URLs, credentials or mapping contents."""
import argparse
import ast
from collections import deque
import hashlib
import json
from pathlib import Path
import re

BASE = Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge")
LOG = Path("/etc/enigma2/SatIPTVBridge/bridge.log")
MARKERS = ("AUDIO_SAFE_PLAYER", "PLAYER_VERIFIED_RE", "FIRST_VIDEO",
           "IPTV_FAIL", "IPTV_OK", "RETRY_PLAYER", "AUDIO_GUARD",
           "RESTORE_SAT", "TOD_EVENT")
EVENTS = ("SAT_START", "MANUAL_EXACT_PIN", "CANDIDATE_SELECT", "AUDIO_SAFE_PLAYER",
          "PLAYER_VERIFIED_RE", "PLAYER_VERIFIED", "FIRST_VIDEO", "IPTV_OK",
          "IPTV_FAIL", "RETRY_PLAYER", "AUDIO_GUARD", "AUDIO_GUARD_PASS",
          "AUDIO_GUARD_FAIL", "RESTORE_SAT")

def field(s, key):
    m = re.search(r"(?<!\w)" + re.escape(key) + r"=(?:'([^']*)'|([^\s]+))", s)
    return (m.group(1) if m.group(1) is not None else m.group(2)) if m else ""

def analyze(lines, limit=12):
    sessions, current = [], None
    for raw in lines:
        columns = raw.rstrip("\n").split(" | ", 2)
        if len(columns) != 3:
            continue
        when, event, details = (p.strip() for p in columns)
        if event not in EVENTS:
            continue
        if event == "SAT_START":
            current = dict(time=when, channel=field(details, "channel")[:80],
                           manual_exact=False, candidates=0, modes=[],
                           attempts=[], decoder_video=False, audio_tracks=False,
                           restored_sat=False, notes=[])
            sessions.append(current)
        if current is None:
            continue
        if event == "MANUAL_EXACT_PIN":
            current["manual_exact"] = True
        elif event == "CANDIDATE_SELECT":
            current["candidates"] += 1
        elif event == "AUDIO_SAFE_PLAYER":
            current["modes"].append(field(details, "direct")[:12])
        elif event in ("PLAYER_VERIFIED_RE", "PLAYER_VERIFIED", "FIRST_VIDEO"):
            if "decoder-video" in details or event == "FIRST_VIDEO":
                current["decoder_video"] = True
        elif event == "AUDIO_GUARD_PASS":
            current["audio_tracks"] = True
        elif event == "RESTORE_SAT":
            current["restored_sat"] = True
        elif event in ("IPTV_OK", "IPTV_FAIL"):
            current["attempts"].append(dict(
                when=when, status="ok" if event == "IPTV_OK" else "fail",
                mode=field(details, "mode")[:12],
                evidence=field(details, "evidence")[:40],
                actual=field(details, "actual")[:20],
                failure=("NO_DECODED_VIDEO" if event == "IPTV_FAIL"
                         and "No decoded IPTV video" in details else
                         "OTHER_FAILURE" if event == "IPTV_FAIL" else None)))
    sessions = sessions[-max(1, min(int(limit), 30)):]
    for s in sessions:
        s["modes"] = s["modes"][-8:]
        if (s["restored_sat"] and any(a["mode"] == "5002" and
                a["status"] == "fail" for a in s["attempts"]) and not
                any(a["mode"] != "5002" for a in s["attempts"])):
            s["notes"].append("5002_FAILED_NO_OTHER_MODE_BEFORE_SAT_RESTORE")
        if any(a["status"] == "ok" and a["evidence"] == "validated-ts-data" and
               a["actual"] == "PENDING" for a in s["attempts"]):
            if not s["decoder_video"]:
                s["notes"].append("IPTV_OK_TS_ONLY_VIDEO_NOT_PROVEN")
        if any(a["status"] == "ok" for a in s["attempts"]):
            s["notes"].append("AUDIBLE_AUDIO_NOT_PROVEN_BY_LOG")
    summary = sorted({note for s in sessions for note in s["notes"]})
    grouped = {}
    for s in sessions:
        grouped.setdefault(s["channel"], set()).update(
            a["mode"] + ":" + a["status"] for a in s["attempts"])
    for channel, modes in grouped.items():
        if "5002:fail" in modes and "dvb:ok" in modes:
            summary.append("CROSS_SESSION_5002_FAIL_DVB_OK:" + channel[:50])
    return dict(sessions=sessions, findings=summary)

def inspect_code(base):
    path = base / "core.py"
    result = dict(core_present=path.is_file())
    if path.is_file():
        source = path.read_bytes()
        result["core_sha256"] = hashlib.sha256(source).hexdigest()
        try:
            source_text = source.decode("utf-8-sig")
            tree = ast.parse(source_text)
            rows = source_text.splitlines()
            matches = []
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    fragment = "\n".join(rows[node.lineno - 1:node.end_lineno])
                    found = [m for m in MARKERS if m in fragment]
                    if found:
                        matches.append(dict(function=node.name[:80],
                                            line=node.lineno, markers=found))
            result["syntax_ok"] = True
            result["relevant_functions"] = matches[:40]
        except (UnicodeError, SyntaxError, ValueError):
            result["syntax_ok"] = False
    plugin = base / "plugin.py"
    if plugin.is_file():
        m = re.search(r"(?m)^\s*PLUGIN_VERSION\s*=\s*['\"]([^'\"]+)",
                      plugin.read_text(errors="replace"))
        result["version"] = m.group(1)[:80] if m else "UNKNOWN"
    return result

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--log", default=str(LOG))
    p.add_argument("--base", default=str(BASE))
    p.add_argument("--limit", type=int, default=12)
    args = p.parse_args()
    report = dict(audit="R80.3 PLAYER READONLY", mode="READ_ONLY",
                  receiver_modified=False, network_calls=False,
                  exported_stream_urls=False, exported_mapping_contents=False,
                  plugin=inspect_code(Path(args.base)))
    log = Path(args.log)
    if log.is_file():
        with log.open(errors="replace") as stream:
            report["playback"] = analyze(deque(stream, maxlen=100000), args.limit)
    else:
        report["playback"] = dict(status="LOG_NOT_FOUND")
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))

if __name__ == "__main__":
    main()
