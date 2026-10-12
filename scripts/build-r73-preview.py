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
NEW = "1.0.46-r73.3-turbo-candidates-beta"
CHANGELOG = P + "CHANGELOG-r733-TURBO-CANDIDATES.txt"
B64 = ROOT/"payload/r727-fuzzy-cache.b64"
BASE_SHA256 = "cd638f40b1bbfcbbc9007634a59683f159cb415a4668190269a5aa1ec4ab0d62"

patchspec = importlib.util.spec_from_file_location("r731_patch", ROOT/"scripts/r731_core_patch.py")
r731 = importlib.util.module_from_spec(patchspec)
patchspec.loader.exec_module(r731)

megasp = importlib.util.spec_from_file_location("r732",ROOT/"scripts/r732_megafast_patch.py")
r732 = importlib.util.module_from_spec(megasp)
megasp.loader.exec_module(r732)

turbosp = importlib.util.spec_from_file_location("r733",ROOT/"scripts/r733_turbo_patch.py")
r733 = importlib.util.module_from_spec(turbosp)
turbosp.loader.exec_module(r733)

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
    # R73: true native Neo Dark theme, preserving all original widget names.
    src = exactly(src, 'self.skin = _theme_skin(PREVIEW_FHD)',
        '''try:
            from .preview_theme_r73 import PREVIEW_R73_FHD
            self.skin = _theme_skin(PREVIEW_R73_FHD)
        except Exception:
            self.skin = _theme_skin(PREVIEW_FHD)''')
    # Button actions: OK tests video; BLUE displays evidence (no redundant playback).
    src = exactly(src, '''    def _blue_action(self):
        if self.focus != "right":
            self._focus_right()
            if self.focus != "right":
                return
        self._preview_selected()
''', '''    def _blue_action(self):
        """Read-only candidate details. OK alone performs video preview."""
        if self.focus != "right":
            self._focus_right()
            return
        ch = self._selected_channel()
        if not ch:
            return
        details = ch.get("_preview_details") if isinstance(ch.get("_preview_details"), dict) else {}
        try:
            health = self._health_record(ch) or {}
        except Exception:
            health = {}
        score = ch.get("_preview_score")
        score_text = ("%.1f" % float(score)) if score is not None else "unscored"
        messages = [
            "Candidate: " + presentation_name(ch.get("name") or "IPTV"),
            "Source: " + str(ch.get("server_role") or "?") + " / " + str(ch.get("server_label") or "?"),
            "Matching: " + self._candidate_decision(ch) + " | score " + score_text,
            "Language (catalog): " + str(ch.get("language") or "?"),
            "Quality (catalog): " + str(ch.get("quality") or "?"),
            "Video observed: " + ("%sx%s" % (health.get("width"), health.get("height")) if health.get("width") and health.get("height") else "not verified"),
            "Audio observation: " + str(health.get("dolby") or "not verified"),
            "Open latency: " + (str(health.get("latency_ms")) + " ms" if health.get("latency_ms") else "not measured"),
            "Identity policy: " + str(details.get("reject_reason") or details.get("review_reason") or details.get("allow_reason") or "no objection"),
            "OK tests the source; GREEN locks only after confirmation.",
        ]
        self.session.open(MessageBox, "\\n".join(messages), type=MessageBox.TYPE_INFO)
''')
    src = exactly(src, '''    def _page_sat_next(self):
        self._page_sat(+1)

    def _page_sat_previous(self):
        self._page_sat(-1)
''', '''    def _r73_page_focused(self, step):
        """CH+/- pages the focused SAT or IPTV panel, never zaps the tuner."""
        if self.focus != "right":
            return self._page_sat(step)
        if not self.channels:
            return
        lst = self["source_list"]
        old = self._source_index_now()
        try:
            if step > 0:
                lst.pageDown()
            else:
                lst.pageUp()
        except Exception:
            target = max(0, min(old + (self.SAT_PAGE_STEP if step > 0 else -self.SAT_PAGE_STEP), len(self.channels) - 1))
            try: lst.moveToIndex(target)
            except Exception: return
        self.selected_index = self._source_index_now()
        self["status"].setText("IPTV candidates: %d/%d  |  CH+/- page  |  OK preview  |  BLUE details" %
                               (self.selected_index + 1, len(self.channels)))

    def _page_sat_next(self):
        self._r73_page_focused(+1)

    def _page_sat_previous(self):
        self._r73_page_focused(-1)
''')
    src = exactly(src, 'self["title"] = Label("PREVIEW BROWSER PRO • ALL IPTV SOURCES • FAST")',
        'self["title"] = Label("PREVIEW BROWSER PRO  |  NEO DARK R73")')
    src = exactly(src, 'self["key_blue"] = Label("PREVIEW / RETRY")',
        'self["key_blue"] = Label("CANDIDATE INFO")')
    src = exactly(src, 'self["key_green"] = Label("USE / LOCK")',
        'self["key_green"] = Label("VERIFIED LOCK")')
    src = exactly(src, 'self["key_yellow"] = Label("SHOW MORE")',
        'self["key_yellow"] = Label("DEEP SEARCH")')
    src = exactly(src, 'self["key_menu"] = Label("MENU REJECT • 0 RESCAN • 1 ADD • 2 AUTO • 4 MANUAL")',
        'self["key_menu"] = Label("MENU REJECT  |  1 ADD  |  4 ALL")')
    # Expand in a background thread: deeper index coverage, no remote stream probe.
    src = exactly(src, 'candidate_budget = 72 if self._r71_worker_deep else self.MAX_BROWSER_CANDIDATES',
                    'candidate_budget = 144 if self._r71_worker_deep else self.MAX_BROWSER_CANDIDATES')
    src = exactly(src, 'candidate_per_server = 24 if self._r71_worker_deep else self.FAST_PER_SERVER',
                    'candidate_per_server = 42 if self._r71_worker_deep else self.FAST_PER_SERVER')
    src = exactly(src, 'channels = self._sort_candidates_with_cached_evidence(channels, context=ctx)[:(72 if self._r71_worker_deep else self.MAX_BROWSER_CANDIDATES)]',
                    'channels = self._sort_candidates_with_cached_evidence(channels, context=ctx)[:(144 if self._r71_worker_deep else self.MAX_BROWSER_CANDIDATES)]')
    src = exactly(src, 'self["status"].setText("ALL SOURCES • expanding up to 72 candidates • P/B1/B2 • please use RIGHT")',
                    'self["status"].setText("DEEP SEARCH • up to 144 indexed candidates • use CH+/- in IPTV panel")')
    src = exactly(src, '''            priorities = [x.strip().upper() for x in cfg.languages.value.split(",") if x.strip()]
            quality_mode = cfg.quality_mode.value
        except Exception:
            return
        self._expand_ref = raw''', '''            priorities = [x.strip().upper() for x in cfg.languages.value.split(",") if x.strip()]
            quality_mode = cfg.quality_mode.value
            ctx = dict(ctx or {})
            ctx["match_threshold"] = float(cfg.match_threshold.value)
        except Exception:
            return
        self._expand_ref = raw''')
    src = r731.patch_plugin_r731(src)
    src = r732.patch_plugin(src)
    src = r733.patch_plugin(src)
    src = exactly(src, 'PLUGIN_VERSION = "'+OLD+'"', 'PLUGIN_VERSION = "'+NEW+'"')
    compile(src, PLUGIN, "exec")
    return src.encode("utf-8")

def patch_core(data):
    """Deep Preview only: wider indexed nomination, coherent configurable ranking."""
    src=data.decode("utf-8")
    src=exactly(src,
        'nomination_per_server = max(10, min(24, per_server + 8))',
        'nomination_per_server = max(10, min(54 if limit > 72 else 24, per_server + 8))')
    src=exactly(src,
        'nomination_cap = max(60, min(132, (limit * 2) + 24))',
        'nomination_cap = max(60, min(400 if limit > 72 else 132, (limit * 2) + 24))')
    src=exactly(src, 'if match_decision(r[1], r[2], 82.0) in ("SAFE", "ALLOWED")',
        'if match_decision(r[1], r[2], float((context or {}).get("match_threshold") or 82.0)) in ("SAFE", "ALLOWED")')
    # Only the all-server PREVIEW ranking decision; do not touch live Auto matching.
    old='''            decision = match_decision(score, det, 82.0)
            decision_band = 2 if decision in ("SAFE", "ALLOWED") else (1 if decision == "REVIEW" else 0)
            provider_band = 1 if det.get("provider_identity") else 0'''
    new='''            decision = match_decision(score, det, float((context or {}).get("match_threshold") or 82.0))
            decision_band = 2 if decision in ("SAFE", "ALLOWED") else (1 if decision == "REVIEW" else 0)
            provider_band = 1 if det.get("provider_identity") else 0'''
    src=exactly(src,old,new)
    src=exactly(src,
        'str(ctx.get("target_hdr") or ""), str(quality_mode or "best"), tuple(extra or ()),',
        'str(ctx.get("target_hdr") or ""), str(ctx.get("match_threshold") or ""), str(quality_mode or "best"), tuple(extra or ()),')
    src = r731.patch_core_r731(src)
    src = r732.patch_core(src)
    src = r733.patch_core(src)
    compile(src,CORE,"exec")
    return src.encode("utf-8")

def build(path=None):
    raw = base64.b64decode(B64.read_bytes())
    if hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise AssertionError("R72.7 baseline digest changed. Pin the verified hash before building.")
    parts = base.pack.unpack_ar(raw)
    original = base.pack.members_from(parts["data.tar.gz"])
    control = base.pack.members_from(parts["control.tar.gz"])
    changes = {PLUGIN: patch_plugin(original[PLUGIN]), CORE: patch_core(original[CORE])}
    up = original[UPDATER].decode()
    changes[UPDATER] = exactly(up, 'CURRENT_VERSION = "'+OLD+'"',
                                   'CURRENT_VERSION = "'+NEW+'"').encode()
    description = (
        "R73.3: 192 candidates in one indexed pass, 18 detailed scores; title memoization and phase timings; manual catalogue search "
        "(48-row paging, no progressive UI); FTA SAT option; preview country REVIEW, "
        "keep hard number/audio safety checks; native Neo Dark theme, "
        "focused SAT/IPTV pagination and read-only BLUE details. LIVE player, monitor, timeshift and user data unchanged. "
        "Experimental; do not install until tests and receiver validation.\\n"
    ).encode()
    c = control["control"].decode()
    new_control = exactly(c, "Version: "+OLD, "Version: "+NEW).encode()
    theme_source = (ROOT/"scripts/r73_preview_theme.py").read_bytes()
    import xml.etree.ElementTree as ET
    ns = {}
    exec(compile(theme_source, "preview_theme_r73.py", "exec"), ns)
    skin = ET.fromstring(ns["PREVIEW_R73_FHD"])
    assert skin.attrib["size"] == "1700,790"
    assert {w.attrib["name"] for w in skin if w.tag == "widget"} == {
       "title", "focus_hint", "sat_picon", "picon_fallback", "sat_current",
       "context_info", "epg", "status", "subtitles", "left_head", "right_head",
       "sat_list", "source_list", "verify", "detail", "key_red", "key_green",
       "key_yellow", "key_blue", "key_menu"
    }
    parts["data.tar.gz"] = base.pack.make_tar(parts["data.tar.gz"], changes,
        {CHANGELOG:description, P+"preview_theme_r73.py":theme_source})
    parts["control.tar.gz"] = base.pack.make_tar(parts["control.tar.gz"], {"control":new_control})
    dest = Path(path) if path else ROOT/"r733-turbo-candidates-beta.ipk"
    if dest.exists(): dest.unlink()
    built = base.pack.assemble(parts, dest)
    rebuilt = base.pack.members_from(base.pack.unpack_ar(built)["data.tar.gz"])
    assert set(rebuilt) == set(original) | {CHANGELOG, P+"preview_theme_r73.py"}
    for k in original:
        assert rebuilt[k] == changes.get(k, original[k]), k
        if k.endswith(".py"): compile(rebuilt[k], k, "exec")
    metadata = {
        "version":NEW, "size":len(built), "sha256":hashlib.sha256(built).hexdigest(),
        "changed": sorted(changes), "protected_unmodified":len(original)-len(changes),
        "production_published":False, "receiver_tested":False,
        "preview_only":True, "player_unchanged":True, "theme":"neo-dark-r73", "candidate_search":"one_shot_192_turbo_18scored_plus_manual"
    }
    print("R73_PREVIEW_STAGE_OK", json.dumps(metadata, sort_keys=True))
    return metadata

if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv)>1 else None)
