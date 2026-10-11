#!/usr/bin/env python3
"""Build isolated R71 UI BETA from SHA-pinned R71 BETA.

UI Home cleanup + ALL configured source roles inside Preview without navigation.
NO player, mapper, Enigma2 lock, backup, streaming, audio or timeshift changes.
"""
import base64, hashlib, importlib.util, json, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r71_base",ROOT/"scripts/build-r71-beta.py")
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
PATH=base.PREFIX+"plugin.py"
NEW_VERSION="1.0.46-r71-ui-beta"
BASE_VERSION="1.0.46-r71-beta"
B64=ROOT/"payload/r71-beta.b64"
PIN="2fe47964933906522680114f7d3ac23aee928caf4dd7e02554a8cd183d2980f3"
CHANGELOG=base.PREFIX+"CHANGELOG-r71-UI-ALL-SOURCES.txt"

def patch(src,old,new,expected=1):
    found=src.count(old)
    if found!=expected:
        raise AssertionError("R71 UI anchor drift expected=%d got=%d: %s" %
                             (expected, found,repr(old[:100])))
    return src.replace(old,new)

def patched_plugin(raw):
    src=raw.decode("utf-8")
    # Home: green is ONE STEP into Preview; deep manual alternatives retained on 4.
    src=patch(src,'self["card_auto_title"] = Label("BRIDGE")',
              'self["card_auto_title"] = Label("AUTO FALLBACK")')
    src=patch(src,'self["card_live_title"] = Label("IPTV CATALOG")',
              'self["card_live_title"] = Label("IPTV SOURCES")')
    src=patch(src,'self["card_engine_title"] = Label("SMARTMATCH")',
              'self["card_engine_title"] = Label("BEST MATCH")')
    src=patch(src,'self["monitor_head"] = Label("LIVE BRIDGE")',
              'self["monitor_head"] = Label("LIVE CHANNEL  •  SAT / IPTV")')
    src=patch(src,'self["context_head"] = Label("CHANNEL CONTEXT")',
              'self["context_head"] = Label("SATELLITE / LANGUAGE")')
    src=patch(src,'self["log_head"] = Label("SUGGESTION")',
              'self["log_head"] = Label("NEXT ACTION")')
    src=patch(src,'self["key_green"] = Label("ALL SOURCES")',
              'self["key_green"] = Label("PREVIEW")')
    src=patch(src,'"cancel": self.close, "red": self.close, "green": self.open_all_sources,',
              '"cancel": self.close, "red": self.close, "green": self.open_preview_sources,')
    src=patch(src,'"menu": self.open_settings, "0": self.player_lock_current, "1": self.open_safe_diagnostics, "2": self.open_updater, "3": self.open_auto_scan,',
              '"menu": self.open_settings, "0": self.player_lock_current, "1": self.open_safe_diagnostics, "2": self.open_updater, "3": self.open_auto_scan, "4": self.open_all_sources,')
    src=patch(src,'    def open_all_sources(self):\n        try:\n            sat_name, sat_ref, ctx, ranked = _rank_current(self.session)',
              '    def open_preview_sources(self):\n        try:\n            _open_preview_sources_direct(self.session)\n        except Exception as err:\n            self.session.open(MessageBox, str(err), type=MessageBox.TYPE_INFO, timeout=6)\n\n    def open_all_sources(self):\n        try:\n            sat_name, sat_ref, ctx, ranked = _rank_current(self.session)')
    src=patch(src,'self["key_yellow"] = Label("SMART MATCH"); self["key_blue"] = Label("EVENT LOG")',
              'self["key_yellow"] = Label("SMART MATCH"); self["key_blue"] = Label("EVENT LOG")') if False else src
    src=patch(src,'GREEN All Sources   •   YELLOW Smart Match', 'GREEN Preview All   •   YELLOW Smart Match',expected=2)
    src=patch(src,'BLUE Event Log   •   0 Player Lock   •   1 Diagnostics   •   2 Update',
              'BLUE Logs   •   4 Manual All   •   0 Player   •   2 Update',expected=2)
    # Preview: first screen opens with fast seed; full all-servers is ranked AFTER first paint.
    src=patch(src,'MAX_BROWSER_CANDIDATES = 36','MAX_BROWSER_CANDIDATES = 48')
    src=patch(src,'FAST_PER_SERVER = 12','FAST_PER_SERVER = 16')
    src=patch(src,'self._candidate_cache = {}\n        self._source_pos_by_sat = {}',
              'self._candidate_cache = {}\n        self._r71_deep_target_ref = ""\n        self._r71_deep_requested = False\n        self._r71_worker_deep = False\n        self._source_pos_by_sat = {}')
    src=patch(src,'self["title"] = Label("PREVIEW BROWSER PRO • IMAGE • DOLBY • OPEN SPEED")',
              'self["title"] = Label("PREVIEW BROWSER PRO • ALL IPTV SOURCES • FAST")')
    src=patch(src,'self["right_head"] = Label("CANDIDATES • PRIMARY + B1 + B2 • FULL")',
              'self["right_head"] = Label("ALL SOURCES • PRIMARY / BACKUP 1 / BACKUP 2")')
    src=patch(src,'self["key_yellow"] = Label("ALL SOURCES")',
              'self["key_yellow"] = Label("SHOW MORE")')
    src=patch(src,'self["key_menu"] = Label("MENU REJECT • 0 RESCAN • 1 ADD • 2 AUTO SCAN")',
              'self["key_menu"] = Label("MENU REJECT • 0 RESCAN • 1 ADD • 2 AUTO • 4 MANUAL")')
    src=patch(src,'"green": self._lock, "yellow": self._all_sources,',
              '"green": self._lock, "yellow": self._all_sources,')
    src=patch(src,'"blue": self._blue_action, "menu": self._toggle_reject, "0": self._rescan_selected_sat, "1": self._manual_add_candidate, "2": self._open_auto_scan,',
              '"blue": self._blue_action, "menu": self._toggle_reject, "0": self._rescan_selected_sat, "1": self._manual_add_candidate, "2": self._open_auto_scan, "4": self._open_legacy_all_sources,')
    src=patch(src,'if shared is not None and bool(shared[3]):\n            self._candidate_cache[key]',
              'if shared is not None and bool(shared[3]) and not (self._r71_deep_requested and self._r71_deep_target_ref == raw):\n            self._candidate_cache[key]')
    src=patch(src,'''        self._expand_ref = raw
        self._expand_started_at = time.monotonic()
        self._expand_result = None
        def worker():
''','''        self._expand_ref = raw
        self._expand_started_at = time.monotonic()
        self._expand_result = None
        self._r71_worker_deep = bool(self._r71_deep_requested and self._r71_deep_target_ref == raw)
        candidate_budget = 72 if self._r71_worker_deep else self.MAX_BROWSER_CANDIDATES
        candidate_per_server = 24 if self._r71_worker_deep else self.FAST_PER_SERVER
        def worker():
''')
    src=patch(src,'''                    per_server=self.FAST_PER_SERVER, topn=self.MAX_BROWSER_CANDIDATES,
                    quality_mode=quality_mode)
''','''                    per_server=candidate_per_server, topn=candidate_budget,
                    quality_mode=quality_mode)
''')
    src=patch(src,'channels = self._sort_candidates_with_cached_evidence(channels, context=ctx)[:self.MAX_BROWSER_CANDIDATES]',
              'channels = self._sort_candidates_with_cached_evidence(channels, context=ctx)[:(72 if self._r71_worker_deep else self.MAX_BROWSER_CANDIDATES)]')
    src=patch(src,'''        self["status"].setText("%d BEST candidates • BG READY • P/B1/B2 • YELLOW = ALL SOURCES" % len(self.channels))
''','''        if self._r71_deep_requested and self._r71_deep_target_ref == raw and not self._r71_worker_deep:
            # YELLOW was pressed while the first 48-row background worker was running.
            # Finish that job, then use the 72-row budget without blocking the GUI.
            try: self.candidate_expand_timer.start(90, True)
            except Exception: pass
            self["status"].setText("%d candidates • ALL SOURCES expanding in background" % len(self.channels))
            return
        deep_done = bool(self._r71_worker_deep and self._r71_deep_target_ref == raw)
        if deep_done:
            self._r71_deep_requested = False
            self._r71_deep_target_ref = ""
        self["status"].setText("%d candidates • ALL SERVERS%s • READY • YELLOW = MORE" %
                               (len(self.channels), " • EXPANDED" if deep_done else ""))
''')
    old='''    def _all_sources(self):
        # Keep exact SAT and IPTV candidate (fingerprint survives re-sorting).
        selected_fp = ""
        if self.channels and self.focus == "right":
            try:
                ch = self.channels[max(0, min(self._source_index_now(), len(self.channels) - 1))]
                selected_fp = channel_fingerprint(ch)
            except Exception:
                selected_fp = ""
        self.close({"action": "all_sources", "sat_ref": self.sat_ref_string,
                    "sat_name": self.sat_name, "context": dict(self.context or {}),
                    "selected_channel_id": selected_fp})
'''
    new='''    def _all_sources(self):
        """YELLOW expands ALL configured IPTV server roles IN THIS SCREEN, asynchronously."""
        if self._closed_for_async:
            return
        row = self._selected_sat_row() or {}
        raw = str(row.get("ref") or "")
        if not raw:
            return
        self._r71_deep_requested = True
        self._r71_deep_target_ref = raw
        self["status"].setText("ALL SOURCES • expanding up to 72 candidates • P/B1/B2 • please use RIGHT")
        if self._expand_worker is not None and self._expand_worker.is_alive():
            # _poll_expanded_candidates will schedule the deeper pass after this job.
            return
        key = sat_service_key(raw)
        self._candidate_cache.pop(key, None)
        _preview_candidate_cache_drop(raw)
        try: self.candidate_expand_timer.stop()
        except Exception: pass
        try: self.candidate_expand_timer.start(10, True)
        except Exception as err:
            self["status"].setText("ALL SOURCES retry unavailable • %s" % str(err)[:65])

    def _open_legacy_all_sources(self):
        """Optional old Manual Mapping accessible on number 4 for deep source browsing."""
        selected_fp = ""
        if self.channels and self.focus == "right":
            try:
                ch = self.channels[max(0, min(self._source_index_now(), len(self.channels) - 1))]
                selected_fp = channel_fingerprint(ch)
            except Exception:
                selected_fp = ""
        self.close({"action": "all_sources", "sat_ref": self.sat_ref_string,
                    "sat_name": self.sat_name, "context": dict(self.context or {}),
                    "selected_channel_id": selected_fp})
'''
    src=patch(src,old,new)
    # Do not rewrite support modules, fast locked monitor, satellite lists, or player.
    compile(src,PATH,"exec")
    return src.encode("utf-8")

def build(output=None):
    raw=base64.b64decode(B64.read_bytes())
    if hashlib.sha256(raw).hexdigest()!=PIN or len(raw)!=277614:
        raise AssertionError("staged R71 beta baseline changed")
    parts=base.unpack_ar(raw)
    data=base.members_from(parts["data.tar.gz"])
    control=base.members_from(parts["control.tar.gz"])
    changes={PATH:patched_plugin(data[PATH])}
    path=base.PREFIX+"updater.py"
    old='CURRENT_VERSION = "%s"'%BASE_VERSION
    assert data[path].decode().count(old)==1
    changes[path]=data[path].decode().replace(old,'CURRENT_VERSION = "%s"'%NEW_VERSION).encode()
    # updated plugin.py version ONLY in the requested UI file
    oldver='PLUGIN_VERSION = "%s"'%BASE_VERSION
    assert changes[PATH].decode().count(oldver)==1
    changes[PATH]=changes[PATH].decode().replace(oldver,'PLUGIN_VERSION = "%s"'%NEW_VERSION).encode()
    ctrl=control["control"].decode()
    assert ctrl.count("Version: "+BASE_VERSION)==1
    ctrl2=ctrl.replace("Version: "+BASE_VERSION,"Version: "+NEW_VERSION,1).encode()
    changeset=set(changes)
    parts["data.tar.gz"]=base.make_tar(parts["data.tar.gz"],changes,{CHANGELOG:
        b"R71 UI BETA: GREEN direct Preview, YELLOW expands all servers inline, 4 opens Manual Mapping.\nBackground indexing only. No network refresh, player, timeshift, TOD or fast zap changes.\n"})
    parts["control.tar.gz"]=base.make_tar(parts["control.tar.gz"],{"control":ctrl2})
    output=Path(output) if output else ROOT/"r71-ui-beta.ipk"
    if output.exists():output.unlink()
    blob=base.assemble(parts,output)
    after=base.members_from(base.unpack_ar(blob)["data.tar.gz"])
    ctl=base.members_from(base.unpack_ar(blob)["control.tar.gz"])
    assert set(after)==set(data)|{CHANGELOG}
    assert all(after[k]==changes.get(k,data[k]) for k in data)
    assert all(ctl[k]==(ctrl2 if k=="control" else control[k]) for k in control)
    for name,raw in after.items():
        if name.endswith(".py"):compile(raw,name,"exec")
    for key in data:
        if key not in changeset:
            assert data[key]==after[key],"protected file touched: "+key
    meta={"version":NEW_VERSION,"sha256":hashlib.sha256(blob).hexdigest(),
          "size":len(blob),"protected_unchanged":len(data)-len(changeset),
          "changed":sorted(changeset),"todo_hardware_test":True,"production_published":False}
    print("R71_UI_BETA_PACKAGE_OK",json.dumps(meta,sort_keys=True))
    return meta

if __name__=="__main__":
    build(sys.argv[1] if len(sys.argv)>1 else None)
