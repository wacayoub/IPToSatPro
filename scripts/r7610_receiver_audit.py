#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""IPToSatPro R76.10: LOCAL read-only receiver diagnostic, no VuLink.

Runs using stock Python 3 on Vu+ OpenATV. Never connects to GitHub, launches
a player, changes a mapping, restarts Enigma2, reads account secrets or prints
stream URLs/channel names. The performance report contains numbers only.

Typical invocation:
  python3 /tmp/r7610_receiver_audit.py
  python3 /tmp/r7610_receiver_audit.py --json
"""
import argparse
import ast
import hashlib
import json
import math
import re
from pathlib import Path

VERSION = "1.0.46-r76.10-preview-normal48-fast-beta"
DEFAULT_PLUGIN = Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge")
DEFAULT_CONFIG = Path("/etc/enigma2/SatIPTVBridge")
DEFAULT_BACKUPS = Path("/home/root/iptosatpro-r76-backups")
MAX_LOG_BYTES = 262144
MAX_LOG_EVENTS = 1000

EVENTS = {
    "PREVIEW_RANK_BG",
    "MATCH_BG_DONE",
    "MATCH_BG_START",
    "IPTV_OK",
    "IPTV_FAIL",
    "NO_MATCH",
    "AUDIO_SAFE_PLAYER",
}
EVENT_PATTERN = re.compile(r"\|\s*([A-Z][A-Z0-9_]+)\s*\|")
ELAPSED_PATTERN = re.compile(r"(?:^|\s)(?:elapsed|cost)=(\d+)ms(?:\s|$)")
INDEX_PATTERN = re.compile(r"(?:^|\s)index=(\d+)ms(?:\s|$)")
SCORING_PATTERN = re.compile(r"(?:^|\s)scoring=(\d+)ms(?:\s|$)")
COUNT_PATTERN = re.compile(r"(?:^|\s)candidate_count=(\d+)(?:\s|$)")
STAMP_PATTERN = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)")


def static_literals(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=path.name)
    found = {}
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign):
            continue
        for node in stmt.targets:
            if isinstance(node, ast.Name):
                try:
                    found[node.id] = ast.literal_eval(stmt.value)
                except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                    pass
    return found


def valid_screen(xml, expected_size):
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml)
    actual_size = tuple(map(int, root.attrib["size"].split(",")))
    if actual_size != expected_size:
        return False
    widgets = set()
    for element in root:
        if element.tag not in ("widget", "eLabel", "ePixmap"):
            return False
        x, y = map(int, element.attrib["position"].split(","))
        w, h = map(int, element.attrib["size"].split(","))
        if min(x, y) < 0 or min(w, h) <= 0:
            return False
        if x + w > actual_size[0] or y + h > actual_size[1]:
            return False
        if element.tag == "widget":
            widget = element.attrib["name"]
            if widget in widgets:
                return False
            widgets.add(widget)
    return len(widgets) >= 20


def percentile(values, p):
    if not values:
        return None
    values = sorted(values)
    return values[max(0, min(len(values) - 1, math.ceil(p * len(values)) - 1))]


def summarize_event_lines(lines):
    """Parse only whitelisted event names and numeric metrics, not messages."""
    counts = {event: 0 for event in sorted(EVENTS)}
    samples = {"PREVIEW_RANK_BG": [], "MATCH_BG_DONE": []}
    candidate_counts = []
    preview_index_ms = []
    preview_scoring_ms = []
    first_time = last_time = None
    for line in lines:
        marker = EVENT_PATTERN.search(line)
        if not marker or marker.group(1) not in counts:
            continue
        event = marker.group(1)
        counts[event] += 1
        stamp = STAMP_PATTERN.match(line)
        if stamp:
            if first_time is None:
                first_time = stamp.group(1)
            last_time = stamp.group(1)
        if event in samples:
            elapsed = ELAPSED_PATTERN.search(line)
            if elapsed:
                samples[event].append(int(elapsed.group(1)))
        if event == "PREVIEW_RANK_BG":
            count = COUNT_PATTERN.search(line)
            if count:
                candidate_counts.append(int(count.group(1)))
            index = INDEX_PATTERN.search(line)
            scoring = SCORING_PATTERN.search(line)
            if index:
                preview_index_ms.append(int(index.group(1)))
            if scoring:
                preview_scoring_ms.append(int(scoring.group(1)))
    return {
        "event_counts": {k: v for k, v in counts.items() if v},
        "sample_first": first_time,
        "sample_last": last_time,
        "latency_ms": {
            event: {
                "samples": len(samples[event]),
                "p50": percentile(samples[event], .50),
                "p95": percentile(samples[event], .95),
                "max": max(samples[event]) if samples[event] else None,
            }
            for event in sorted(samples)
        },
        "preview_candidate_count_max": max(candidate_counts) if candidate_counts else None,
        "preview_breakdown_ms": {
            "index_max": max(preview_index_ms) if preview_index_ms else None,
            "scoring_max": max(preview_scoring_ms) if preview_scoring_ms else None,
            "breakdown_samples": min(len(preview_index_ms), len(preview_scoring_ms)),
        },
        "interpretation": "PREVIEW_RANK_BG elapsed includes timer/poll and potential worker waiting, not only CPU scoring. MATCH_BG_DONE cost is the backend runtime; p95 with fewer than 20 samples is not robust.",
        "not_measured": [
            "time-to-picture",
            "audio-decoding",
            "UHD-frame-drops",
            "GUI-remote-interaction",
        ],
    }


def read_recent_log(path):
    if not path.is_file():
        return {"status": "log_unavailable"}
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - MAX_LOG_BYTES))
            raw = f.read(MAX_LOG_BYTES)
        lines = raw.decode("utf-8", "replace").splitlines()
        if size > MAX_LOG_BYTES:
            lines = lines[1:]  # first row could be truncated
        report = summarize_event_lines(lines[-MAX_LOG_EVENTS:])
        report["status"] = "numeric_events_only"
        report["truncated_to_recent_bytes"] = size > MAX_LOG_BYTES
        return report
    except (OSError, ValueError):
        return {"status": "log_unreadable"}


def backup_mapping_integrity(config_root, backup_root):
    """Compare saved mapping hashes, never display contents or filenames.

    A changed mapping hash may be a legitimate user edit: warn only.
    """
    marker = backup_root / "last-backup-path"
    if not marker.is_file():
        return {"status": "no_backup_reference"}
    try:
        path = Path(marker.read_text(encoding="utf-8").strip())
        if (not path.is_absolute() or path.parent != backup_root or
                not path.is_dir() or path.is_symlink()):
            return {"status": "invalid_backup_reference"}
        source = path / "mapping-hashes.json"
        values = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(values, dict):
            return {"status": "invalid_hash_manifest"}
        unchanged = altered = missing = 0
        for name, digest in values.items():
            if (not isinstance(name, str) or not re.fullmatch(r"[a-zA-Z0-9_.-]+", name)
                    or not isinstance(digest, str) or
                    not re.fullmatch(r"[a-f0-9]{64}", digest)):
                return {"status": "invalid_hash_manifest"}
            target = config_root / name
            if target.is_symlink() or not target.is_file():
                missing += 1
                continue
            with target.open("rb") as f:
                actual = hashlib.sha256(f.read()).hexdigest()
            if actual == digest:
                unchanged += 1
            else:
                altered += 1
        return {"status": "verified_against_backup",
                "unchanged": unchanged, "changed_since_backup": altered,
                "missing": missing, "automatic_restore": False}
    except (OSError, ValueError, TypeError, UnicodeError):
        return {"status": "backup_unreadable"}


def check_receiver(plugin_root=DEFAULT_PLUGIN, config_root=DEFAULT_CONFIG,
                   backup_root=DEFAULT_BACKUPS, log_path=None, proc_root=Path("/proc")):
    """No writes or network connections. Result contains no secrets."""
    checks = {}
    def check(key, okay):
        checks[key] = bool(okay)
    version = None
    if not plugin_root.is_dir():
        check("plugin_present", False)
        return {"version": None, "checks": checks, "static_pass": False,
                "mapping_backup": {"status": "not_checked"},
                "log": {"status": "not_checked"}, "hardware_av_pass": None}
    paths = {name: plugin_root / name for name in
             ("plugin.py", "core.py", "monitor.py", "updater.py",
              "preview_theme_r74.py", "home_themes_r767.py")}
    sources = {}
    for name, path in paths.items():
        try:
            source = path.read_text(encoding="utf-8")
            compile(source, name, "exec")
            sources[name] = source
            check("python_" + name.replace(".py", ""), True)
        except (OSError, UnicodeError, SyntaxError, ValueError):
            check("python_" + name.replace(".py", ""), False)
    plugin_src = sources.get("plugin.py", "")
    core_src = sources.get("core.py", "")
    updater_src = sources.get("updater.py", "")
    found_version = re.search(r'(?m)^PLUGIN_VERSION\s*=\s*["\x27]([^"\x27]+)', plugin_src)
    if found_version:
        version = found_version.group(1)[:90]
    check("exact_r7610_installed", version == VERSION)
    check("updater_version_matches", ("CURRENT_VERSION = \"" + VERSION + "\"") in updater_src)
    check("preview_manual_rank_parity", all(token in plugin_src for token in (
        "R769_PREVIEW_MANUAL_PARITY", "PreviewManualMappingList",
        "fast_rank_matches_all_servers(", "_r769_preview_sat_context")))
    check("region_priority", "R768_CONTEXT_REGION_PRIORITY" in core_src)
    check("normal48_bounded_candidate_pool", all(token in core_src for token in (
        "R7610_NORMAL48_FAST_BUDGET",
        "if limit > 48 else {}",
        "if limit <= 48 and roles_cap <= 16 else",
    )))
    check("cache_speed_guards", "R766_COLD_RANK_FAST" in core_src and
          "R765_POSTINGS_FAST_FIRSTPAINT" in plugin_src)
    check("preserved_preview_controls", "R7413_PREVIEW_INLINE_NO_HIDE" in plugin_src)

    try:
        home = static_literals(paths["plugin.py"])
        preview = static_literals(paths["preview_theme_r74.py"])
        themes = static_literals(paths["home_themes_r767.py"])
        check("home_metrix_fhd", valid_screen(home["R76_METRIX_FHD"], (1660, 900)))
        check("home_metrix_hd", valid_screen(home["R76_METRIX_HD"], (1245, 675)))
        check("preview_fhd", valid_screen(preview["PREVIEW_R74_FHD"], (1660, 900)))
        check("preview_hd", valid_screen(preview["PREVIEW_R76_HD"], (1245, 675)))
        fhd = themes["THEME_FHD"]
        hd = themes["THEME_HD"]
        check("eleven_native_themes",
              isinstance(fhd, dict) and isinstance(hd, dict) and
              len(fhd) == len(hd) == 11 and set(fhd) == set(hd) and
              all(valid_screen(s, (1660, 900)) for s in fhd.values()) and
              all(valid_screen(s, (1245, 675)) for s in hd.values()))
    except (OSError, UnicodeError, SyntaxError, KeyError, ValueError, TypeError,
            OverflowError, RecursionError):
        for key in ("home_metrix_fhd", "home_metrix_hd", "preview_fhd",
                    "preview_hd", "eleven_native_themes"):
            check(key, False)

    gui_live = None
    try:
        gui_live = any(
            p.is_dir() and p.name.isdigit() and
            (p / "comm").read_text(encoding="utf-8", errors="replace").strip().startswith("enigma2")
            for p in proc_root.iterdir() if p.name.isdigit())
    except OSError:
        gui_live = None

    return {
        "audit": "IPToSatPro R76.10 local read-only",
        "version": version,
        "checks": checks,
        "static_pass": bool(checks) and all(checks.values()),
        "gui_enigma2_running": gui_live,
        "mapping_backup": backup_mapping_integrity(config_root, backup_root),
        "log": read_recent_log(log_path if log_path is not None else config_root / "bridge.log"),
        "hardware_av_pass": None,
        "warning": "A static scan and log timing do not prove picture, sound, fast zap or 4K stability",
        "no_changes": True,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--json", action="store_true", help="compact JSON report")
    p.add_argument("--strict", action="store_true", help="exit nonzero if static checks fail")
    args = p.parse_args()
    result = check_receiver()
    if args.json:
        print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    else:
        print("IPTOSAT_R7610_LOCAL_AUDIT")
        print(json.dumps(result, ensure_ascii=True, sort_keys=True, indent=2))
    if args.strict and not result["static_pass"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
