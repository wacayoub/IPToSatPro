#!/usr/bin/env python3
"""R73 Preview Browser Pro: strictly scoped stage build, never publish or install.

Builds on SHA-verified R72.7 fuzzy-cache package. Protects monitor, media player,
timeshift, existing user mappings, credentials, and LIVE auto matching.
"""
import ast
import base64
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("r727", ROOT/"scripts/build-r727-fast.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
P = base.P
PLUGIN = P + "plugin.py"
UPDATER = P + "updater.py"
CORE = P + "core.py"
OLD = "1.0.46-r72.7-fuzzy-cache-beta"
NEW = "1.0.46-r73-preview-browser-beta"
CHANGELOG = P + "CHANGELOG-r73-PREVIEW-BROWSER.txt"
B64 = ROOT/"payload/r727-fuzzy-cache.b64"
BASE_SHA256 = "PIN_AT_FIRST_BUILD"

def exactly(src, old, new):
    n = src.count(old)
    if n != 1:
        raise AssertionError("Anchor drift: expected one occurrence, got %s: %r" % (n, old[:100]))
    return src.replace(old, new, 1)

def patch_plugin(data):
    src = data.decode("utf-8")
    # The r72.7 'expanded' ranking requests 72, but this sorter silently clips
    # the list back to MAX_BROWSER_CANDIDATES (48). Remove that hidden truncation.
    src = exactly(src,
        "return self._compact_candidate_duplicates(rows, limit=self.MAX_BROWSER_CANDIDATES)",
        "return self._compact_candidate_duplicates(rows)")
    # Refresh a cached Preview when the user changes language, threshold, quality,
    # or matching preferences. Catalog token remains part of the identity.
    old = '''    return (id(catalog), len(getattr(catalog, "channels", []) or []), str(meta.get("generation") or meta.get("updated") or meta.get("source") or ""))'''
    new = '''    try:
            ui_policy = (str(cfg.languages.value), str(cfg.match_threshold.value),
                         str(cfg.quality_mode.value))
        except Exception:
            ui_policy = ("", "", "")
        return (id(catalog), len(getattr(catalog, "channels", []) or []),
                str(meta.get("generation") or meta.get("updated") or meta.get("source") or ""),
                ui_policy)'''
    src = exactly(src, old, new)
    # A manual saved lock should not masquerade as a newly measured 150% match.
    src = exactly(src, 'float((manual or {}).get("auto_scan_score") or 150.0)',
                        'float((manual or {}).get("auto_scan_score") or 0.0)')
    src = exactly(src, 'PLUGIN_VERSION = "'+OLD+'"', 'PLUGIN_VERSION = "'+NEW+'"')
    compile(src, PLUGIN, "exec")
    return src.encode("utf-8")

def build(path=None):
    raw = base64.b64decode(B64.read_bytes())
    if hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise AssertionError("R72.7 baseline digest changed. Pin the verified hash before building.")
    parts = base.pack.unpack_ar(raw)
    original = base.pack.members_from(parts["data.tar.gz"])
    control = base.pack.members_from(parts["control.tar.gz"])
    changes = {PLUGIN: patch_plugin(original[PLUGIN])}
    up = original[UPDATER].decode()
    changes[UPDATER] = exactly(up, 'CURRENT_VERSION = "'+OLD+'"',
                                   'CURRENT_VERSION = "'+NEW+'"').encode()
    description = (
        "R73 staged Preview-only bugfixes: preserve all 72 expanded ranked candidates "
        "after sorting, refresh cache on language/match threshold/quality changes, "
        "stop presenting saved manual lock as fabricated score 150. "
        "No modifications to LIVE matcher, player, monitor, streams, timeshift or user data. "
        "Experimental; do not install until tests and receiver validation.\\n"
    ).encode()
    c = control["control"].decode()
    new_control = exactly(c, "Version: "+OLD, "Version: "+NEW).encode()
    parts["data.tar.gz"] = base.pack.make_tar(parts["data.tar.gz"], changes, {CHANGELOG:description})
    parts["control.tar.gz"] = base.pack.make_tar(parts["control.tar.gz"], {"control":new_control})
    dest = Path(path) if path else ROOT/"r73-preview-browser-beta.ipk"
    if dest.exists(): dest.unlink()
    built = base.pack.assemble(parts, dest)
    rebuilt = base.pack.members_from(base.pack.unpack_ar(built)["data.tar.gz"])
    assert set(rebuilt) == set(original) | {CHANGELOG}
    for k in original:
        assert rebuilt[k] == changes.get(k, original[k]), k
        if k.endswith(".py"): compile(rebuilt[k], k, "exec")
    metadata = {
        "version":NEW, "size":len(built), "sha256":hashlib.sha256(built).hexdigest(),
        "changed": sorted(changes), "protected_unmodified":len(original)-len(changes),
        "production_published":False, "receiver_tested":False,
        "preview_only":True, "player_unchanged":True
    }
    print("R73_PREVIEW_STAGE_OK", json.dumps(metadata, sort_keys=True))
    return metadata

if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv)>1 else None)
