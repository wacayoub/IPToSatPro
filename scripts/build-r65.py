#!/usr/bin/env python3
"""r65: keep satellite AND candidate cursor on All Sources navigation."""
from pathlib import Path
import io, tarfile, subprocess, re, hashlib, shutil

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"r64.ipk"
WORK=ROOT/"_r65_build"
OUT=ROOT/"r65.ipk"
if WORK.exists(): shutil.rmtree(WORK)
for kind in ("data","control"):
    (WORK/kind).mkdir(parents=True)
    raw=subprocess.check_output(["ar","p",str(BASE),kind+".tar.gz"])
    with tarfile.open(fileobj=io.BytesIO(raw),mode="r:gz") as tar:
        tar.extractall(WORK/kind,filter="data")
P=WORK/"data/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge"
plugin=P/"plugin.py"
s=plugin.read_text()
def once(old,new):
    global s
    assert s.count(old)==1,("anchor",old[:90],s.count(old))
    s=s.replace(old,new,1)
once('PLUGIN_VERSION = "1.0.46-r64"','PLUGIN_VERSION = "1.0.46-r65"')
once('''    def _all_sources(self):
        self.close({"action": "all_sources", "sat_ref": self.sat_ref_string,
                    "sat_name": self.sat_name, "context": dict(self.context or {})})''', '''    def _all_sources(self):
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
                    "selected_channel_id": selected_fp})''')
once('''    def __init__(self, session, sat_name, sat_ref_string, context, ranked):
        self.skin = _theme_skin(ALTERNATIVES_FHD)
        Screen.__init__(self,session)
        self.sat_name=sat_name; self.sat_ref_string=sat_ref_string; self.context=context or {}
        self.auto_ranked=ranked or []; self.ranked=[]; self.search_query=""; self.server_filter="ALL"; self.group_filter="ALL"; self.browse_mode=False; self._manual_channel_id=""; self._user_rejected_ids=set()''','''    def __init__(self, session, sat_name, sat_ref_string, context, ranked, selected_channel_id=""):
        self.skin = _theme_skin(ALTERNATIVES_FHD)
        Screen.__init__(self,session)
        self.sat_name=sat_name; self.sat_ref_string=sat_ref_string; self.context=context or {}
        self.auto_ranked=ranked or []; self.ranked=[]; self.search_query=""; self.server_filter="ALL"; self.group_filter="ALL"; self.browse_mode=False; self._manual_channel_id=""; self._user_rejected_ids=set()
        self._pending_selected_fp = str(selected_channel_id or "")
        self._shown_fps = []
        self._initial_selection = True''')
once('''    def _render(self):
        # One override read per render keeps manual/corrected highlighting fast even with 48 rows.
        self._refresh_manual_selection()''','''    def _render(self):
        # Restore by IPTV fingerprint, never by a stale index from a re-ranked list.
        preferred_fp = str(getattr(self, "_pending_selected_fp", "") or "")
        previous_ids = getattr(self, "_shown_fps", []) or []
        old_pos = self._index()
        if not preferred_fp and 0 <= old_pos < len(previous_ids):
            preferred_fp = previous_ids[old_pos]
        # One override read per render keeps manual/corrected highlighting fast even with 48 rows.
        self._refresh_manual_selection()''')
once('''        rendered=[]
        best_marked=False
        display_rows = self.ranked if (self.browse_mode or self.search_query) else self.ranked[:self.MAX_VISIBLE_CANDIDATES]
        for idx,(ch,score,details) in enumerate(display_rows,1):''','''        rendered=[]
        shown_fps=[]
        best_marked=False
        display_rows = self.ranked if (self.browse_mode or self.search_query) else self.ranked[:self.MAX_VISIBLE_CANDIDATES]
        for idx,(ch,score,details) in enumerate(display_rows,1):
            try: shown_fps.append(channel_fingerprint(ch))
            except Exception: shown_fps.append("")''')
once('''        try:
            self["list"].setList(rendered)
        except Exception:
            try: self["list"].rows = rendered
            except Exception: pass
        mode=("Search: %s"%self.search_query)''','''        target = -1
        if preferred_fp:
            try: target = shown_fps.index(preferred_fp)
            except ValueError: pass
        if target < 0 and getattr(self, "_initial_selection", False):
            try: target = shown_fps.index(self._manual_channel_id)
            except ValueError: pass
        if target < 0 and not getattr(self, "_initial_selection", False) and not self._pending_selected_fp and shown_fps:
            target = min(max(0, old_pos), len(shown_fps) - 1)
        try:
            self["list"].setList(rendered)
        except Exception:
            try: self["list"].rows = rendered
            except Exception: pass
        self._shown_fps = shown_fps
        if target >= 0:
            try: self["list"].moveToIndex(target)
            except Exception: pass
            if preferred_fp == getattr(self, "_pending_selected_fp", ""):
                self._pending_selected_fp = ""
        self._initial_selection = False
        mode=("Search: %s"%self.search_query)''')
once('''    def _queue_sat_switch_from_preview(self, sat_ref_string, sat_name="", context=None):''','''    def _queue_sat_switch_from_preview(self, sat_ref_string, sat_name="", context=None, selected_channel_id=""):''')
once('''        self._pending_sat_switch=(str(sat_ref_string or ""), clean_display_name(sat_name or ""), dict(context or {}))''','''        self._pending_sat_switch=(str(sat_ref_string or ""), clean_display_name(sat_name or ""), dict(context or {}), str(selected_channel_id or ""))''')
once('''        raw, requested_name, requested_context=pending''','''        raw, requested_name, requested_context, requested_fp=pending''')
once('''            self.search_query=""; self.server_filter="ALL"; self.group_filter="ALL"; self.browse_mode=False
            self.auto_ranked=list(ranked[:24]); self.ranked=list(ranked[:self.MAX_VISIBLE_CANDIDATES])''','''            self.search_query=""; self.server_filter="ALL"; self.group_filter="ALL"; self.browse_mode=False
            self._pending_selected_fp = requested_fp
            self._shown_fps = []
            self._initial_selection = True
            self.auto_ranked=list(ranked[:24]); self.ranked=list(ranked[:self.MAX_VISIBLE_CANDIDATES])''')
once('''        if action == "all_sources":
            result_sat_ref = str(result.get("sat_ref") or self.sat_ref_string)
            if result_sat_ref != self.sat_ref_string:
                self._queue_sat_switch_from_preview(result_sat_ref, result.get("sat_name") or "", result.get("context") or {})
            else:
                # We are already the All Sources / Manual Mapping parent for this SAT row.
                # Just refresh the bounded local list after Preview closes; no new modal needed.
                try:self._load_timer.start(35, True)
                except Exception:pass
            return''','''        if action == "all_sources":
            result_sat_ref = str(result.get("sat_ref") or self.sat_ref_string)
            wanted_fp = str(result.get("selected_channel_id") or "")
            if result_sat_ref != self.sat_ref_string:
                self._queue_sat_switch_from_preview(result_sat_ref, result.get("sat_name") or "", result.get("context") or {}, wanted_fp)
            else:
                # No re-loading or list reset when returning to the same parent.
                if wanted_fp: self._pending_selected_fp = wanted_fp
                self._render()
            return''')
once('''def _open_all_sources_for_ref(session, sat_ref_string, sat_name="", context=None):''','''def _open_all_sources_for_ref(session, sat_ref_string, sat_name="", context=None, selected_channel_id=""):''')
once('''    session.open(SatIPTVBridgeAlternatives, sat_name2, sat_ref, ctx, ranked)
    return True''','''    session.open(SatIPTVBridgeAlternatives, sat_name2, sat_ref, ctx, ranked, selected_channel_id)
    return True''')
once('''        ctx = dict(result.get("context") or {})
        def _open_after_preview_close():
            try:
                if selected_ref:
                    _open_all_sources_for_ref(session, selected_ref, sat_name, ctx)''','''        ctx = dict(result.get("context") or {})
        selected_fp = str(result.get("selected_channel_id") or "")
        def _open_after_preview_close():
            try:
                if selected_ref:
                    _open_all_sources_for_ref(session, selected_ref, sat_name, ctx, selected_fp)''')
plugin.write_text(s)
u=P/"updater.py"
current=u.read_text()
assert current.count('CURRENT_VERSION = "1.0.46-r64"')==1
u.write_text(current.replace('CURRENT_VERSION = "1.0.46-r64"','CURRENT_VERSION = "1.0.46-r65"',1))
(P/"CHANGELOG-r65-SELECTION.txt").write_text(
    "r65 Keep Selection: keep exact SAT ref and IPTV candidate fingerprint on All Sources.\n"
    "Preserve highlighted candidate across automatic re-sorting and deferred All Servers loading.\n"
    "Keep filters and scroll position when returning Preview to the same All Sources screen.\n"
    "No change to LOCKED fast zap, native timeshift, core, monitor or playback relay.\n"
)
ctl=WORK/"control/control"
c=ctl.read_text()
assert c.count("Version: 1.0.46-r64")==1
c=c.replace("Version: 1.0.46-r64","Version: 1.0.46-r65",1)
c=re.sub(r"^Description:.*$","Description: IPToSat Pro r65 keep All Sources SAT and IPTV candidate selection",c,flags=re.M)
ctl.write_text(c)
for f in P.rglob("*.py"): compile(f.read_bytes(),str(f),"exec")
with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(["ar","p",str(BASE),"data.tar.gz"])),mode="r:gz") as tf:
    for name in ("core.py","monitor.py","neo_theme.py","timeshift_seek_patch.py"):
        original=tf.extractfile("./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"+name).read()
        assert original==(P/name).read_bytes(),name
for kind in ("data","control"):
    with tarfile.open(WORK/(kind+".tar.gz"),"w:gz",format=tarfile.GNU_FORMAT) as tar:
        for f in sorted((WORK/kind).rglob("*")):
            if "__pycache__" in f.parts or f.suffix in (".pyc",".pyo"): continue
            tar.add(f,arcname="./"+str(f.relative_to(WORK/kind)),recursive=False)
(WORK/"debian-binary").write_text("2.0\n")
if OUT.exists(): OUT.unlink()
subprocess.check_call(["ar","r",str(OUT),str(WORK/"debian-binary"),str(WORK/"control.tar.gz"),str(WORK/"data.tar.gz")],stdout=subprocess.DEVNULL)
print("R65_NAV_OK",OUT.stat().st_size,hashlib.sha256(OUT.read_bytes()).hexdigest())

# r65 online release trigger
