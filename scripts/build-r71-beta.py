#!/usr/bin/env python3
"""Deterministic R71 BETA candidate builder from PINNED published R70.

This stage changes ONLY the exact-name/confirmed-SAT-audio weak-IPTV-GROUP
market-review gate; it DOES NOT touch player, FAST LOCK, audio decoding,
timeshift, stored mappings, retries, stream probing, or production updater.
Fail closed on any drift in baseline code or package files.
"""
import base64
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/build-r70-final.py"
spec = importlib.util.spec_from_file_location("iptosat_r70_archive", SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
unpack_ar = mod.unpack_ar
members_from = mod.members_from
make_tar = mod.make_tar
assemble = mod.assemble
PREFIX = "usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"
R70_SHA = "471039d712e81c03bacbcf0394325dd07b56d8bbf3f2002bf6a48f89f93b791c"
R70_SIZE = 277002
OLD_VERSION = "1.0.46-r70-final"
NEW_VERSION = "1.0.46-r71-beta"
CHANGELOG = PREFIX + "CHANGELOG-r71-STABILITY-BETA.txt"

# Read from REAL packaged core.py. Literal anchor checked EXACTLY ONCE.
OLD = '''                if cand_market_source == "group":
                    # Group/category metadata is weak and providers often misfile channels.
                    # Keep an exact/plausible identity visible for manual preview, but never
                    # auto-switch it until the user/audio verification confirms it.
                    details["market"] = -10.0
                    details["context"] = -22.0
                    details["review_reason"] = "IPTV bouquet market %s conflicts with strong SAT market %s" % (cand_market, desired_markets[0])
'''
NEW = '''                if cand_market_source == "group":
                    # R71: IPTV group names are unverified hints, not actual audio evidence.
                    # Permit an EXACT service identity only when SAT audio metadata and the
                    # IPTV candidate's explicit language field agree. Never waive numbered
                    # channel, service-variant, explicit-feed, or provider contradictions.
                    # This does NOT verify the stream's decoded audio or speed of opening.
                    r71_exact_identity = bool(sat_norm and sat_norm == ip_norm)
                    r71_audio_supported = bool(
                        sat_audio_set and sat_audio_target and
                        sat_audio_target in sat_audio_set and
                        str(ch.get("language") or "").upper() == sat_audio_target)
                    r71_weak_group_only = bool(
                        r71_exact_identity and r71_audio_supported and
                        not explicit_feed_lang and not details.get("reject_reason") and
                        not details.get("review_reason") and
                        float(details.get("variant") or 0) >= 0)
                    if r71_weak_group_only:
                        details["market"] = -4.0
                        details["context"] = -4.0
                        details["allow_reason"] = "R71 exact identity + SAT/candidate language; IPTV group only"
                        details["allowed_floor"] = 82.0
                    else:
                        details["market"] = -10.0
                        details["context"] = -22.0
                        details["review_reason"] = "IPTV bouquet market %s conflicts with strong SAT market %s" % (cand_market, desired_markets[0])
'''

DESCRIPTION = (
    "R71 BETA - conservative SAT audio corroborated IPTV GROUP matching.\n"
    "An exact-name IPTV candidate with matching SAT+catalogue language can be\n"
    "automatically eligible despite a contradictory IPTV GROUP category.\n"
    "Explicit IT/PL feed tags, conflicting audio or mismatched service numbers\n"
    "remain rejected. Ambiguous cases remain manual REVIEW.\n"
    "MAPPINGS, fast-zap monitor, black-screen recovery, audio/TS player, timeshift\n"
    "and relay are BYTE-IDENTICAL to R70. NO TOD dynamic functions.\n"
    "EXPERIMENTAL staging only, not installed on Vu+ and not production update.\n"
)

def get_r70():
    blob = base64.b64decode((ROOT / "payload/r70-final.b64").read_bytes())
    if len(blob) != R70_SIZE or hashlib.sha256(blob).hexdigest() != R70_SHA:
        raise ValueError("R70 immutable baseline integrity mismatch")
    return blob

def build(output=None):
    blob = get_r70()
    parts = unpack_ar(blob)
    before = members_from(parts["data.tar.gz"])
    controls = members_from(parts["control.tar.gz"])
    core_path = PREFIX + "core.py"
    source = before[core_path].decode("utf-8")
    if source.count(OLD) != 1:
        raise AssertionError("R70 source drift: expected EXACT market gate not found")
    updated = source.replace(OLD, NEW, 1)
    changes = {core_path: updated.encode("utf-8")}
    for module, symbol in (("plugin.py", "PLUGIN_VERSION"), ("updater.py", "CURRENT_VERSION")):
        path = PREFIX + module
        src = before[path].decode("utf-8")
        old = '%s = "%s"' % (symbol, OLD_VERSION)
        if src.count(old) != 1:
            raise AssertionError("missing pinned version %s" % path)
        changes[path] = src.replace(old, '%s = "%s"' % (symbol, NEW_VERSION), 1).encode()
    control = controls["control"].decode("utf-8")
    old_control = "Version: " + OLD_VERSION
    if control.count(old_control) != 1:
        raise AssertionError("wrong base control version")
    new_control = control.replace(old_control, "Version: " + NEW_VERSION, 1).encode()
    parts["data.tar.gz"] = make_tar(parts["data.tar.gz"], changes,
                                     {CHANGELOG: DESCRIPTION.encode("utf-8")})
    parts["control.tar.gz"] = make_tar(parts["control.tar.gz"], {"control": new_control})
    out = Path(output) if output else ROOT / "r71-beta.ipk"
    if out.exists():
        out.unlink()
    built = assemble(parts, out)
    new_files = members_from(unpack_ar(built)["data.tar.gz"])
    new_controls = members_from(unpack_ar(built)["control.tar.gz"])
    if set(new_files) != set(before) | {CHANGELOG}:
        raise AssertionError("R71 unexpected files")
    for name, old_bytes in before.items():
        if new_files[name] != changes.get(name, old_bytes):
            raise AssertionError("R71 unapproved change: " + name)
    for name, old_bytes in controls.items():
        if new_controls[name] != (new_control if name == "control" else old_bytes):
            raise AssertionError("R71 control drift: " + name)
    for name, raw in new_files.items():
        if name.endswith(".py"):
            compile(raw, name, "exec")
    protected = ["monitor.py", "timeshift_seek_patch.py", "metadata_shadow.py",
                 "converter_patch.py", "native_selection_follow.py"]
    for module in protected:
        key = PREFIX + module
        if key in before and before[key] != new_files[key]:
            raise AssertionError("R71 protected module changed: " + module)
    # Also guard complete core AST: only one controlled textual branch may change.
    if updated.replace(NEW, OLD, 1) != source:
        raise AssertionError("Unexpected core patch side-effect")
    metadata = {"version": NEW_VERSION, "size": len(built),
                "sha256": hashlib.sha256(built).hexdigest(),
                "baseline_sha256": R70_SHA, "changed": sorted(changes),
                "unchanged_files": len(before) - len(changes),
                "player_changed": False, "tod_included": False,
                "field_tested": False, "published": False}
    print("R71_BETA_BUILD_GUARDED", json.dumps(metadata, sort_keys=True))
    return metadata

if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else None)
