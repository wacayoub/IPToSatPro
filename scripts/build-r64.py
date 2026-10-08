#!/usr/bin/env python3
"""r64 Ultra Fast Preview - UI-only optimizations from published r63."""
from pathlib import Path
import io, tarfile, subprocess, re, hashlib, shutil

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"r63.ipk"
WORK=ROOT/"_r64_build"
OUT=ROOT/"r64.ipk"
if WORK.exists(): shutil.rmtree(WORK)
for k in ("data","control"):
    (WORK/k).mkdir(parents=True)
    buf=subprocess.check_output(["ar","p",str(BASE),k+".tar.gz"])
    with tarfile.open(fileobj=io.BytesIO(buf),mode="r:gz") as t:
        t.extractall(WORK/k,filter="data")
P=WORK/"data/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge"
pl=P/"plugin.py"
s=pl.read_text()
def once(a,b):
    global s
    assert s.count(a)==1,("anchor",s.count(a),a[:100])
    s=s.replace(a,b,1)
once('PLUGIN_VERSION = "1.0.46-r63"','PLUGIN_VERSION = "1.0.46-r64"')
once('''        self._manual_overrides = _load_overrides()
        self._learned_mappings = {}  # legacy automatic mappings ignored since 1.0.45
        self._user_rejected_ids = set()
        self.restore_ref = None''','''        self._manual_overrides = _load_overrides()
        self._learned_mappings = {}  # legacy automatic mappings ignored since 1.0.45
        self._user_rejected_ids = set()
        self._preview_file_stamps = {}
        self._sat_list_rendered = None
        self._sat_list_source_id = None
        self._sat_list_dirty = True
        self._last_picon_ref = None
        self.restore_ref = None''')
once('''    def _update_selected_picon(self):
        row = self._selected_sat_row() or {}
        path = _picon_path_for_service(row.get("ref") or self.sat_ref_string)
        try:
            if path and self["sat_picon"].instance is not None:''','''    def _update_selected_picon(self):
        row = self._selected_sat_row() or {}
        raw_ref = str(row.get("ref") or self.sat_ref_string or "")
        # Resolving/decoding the same DVB picon on every IPTV cursor move
        # can block the GUI. Only change image when the SAT row changes.
        if getattr(self, "_last_picon_ref", None) == raw_ref:
            return
        path = _picon_path_for_service(raw_ref)
        self._last_picon_ref = raw_ref
        try:
            if path and self["sat_picon"].instance is not None:''')
once('''    def _refresh_mapping_caches(self):
        try: self._manual_overrides = _load_overrides()
        except Exception: self._manual_overrides = {}
        self._learned_mappings = {}  # persistent AUTO/LEARNED mappings are inactive
        try: self._user_rejected_ids = set(_user_rejection_items(self.sat_ref_string).keys())
        except Exception: self._user_rejected_ids = set()
''','''    def _refresh_mapping_caches(self, force=False):
        """Only parse JSON if changed. Playback keeps using the original stores."""
        stamps = getattr(self, "_preview_file_stamps", {})
        def signature(path):
            try:
                st = os.stat(path)
                return (getattr(st, "st_mtime_ns", int(st.st_mtime * 1000000000)), st.st_size, st.st_ino)
            except OSError:
                return (None, 0, 0)
        override_sig = signature(OVERRIDE_PATH)
        if force or stamps.get("overrides") != override_sig:
            try: self._manual_overrides = _load_overrides()
            except Exception: self._manual_overrides = {}
            self._sat_list_dirty = True
            stamps["overrides"] = override_sig
        self._learned_mappings = {}
        rejection_sig = signature(REJECTED_PATH)
        if force or stamps.get("rejections") != rejection_sig or stamps.get("reject_sat") != self._sat_key():
            try: self._user_rejected_ids = set(_user_rejection_items(self.sat_ref_string).keys())
            except Exception: self._user_rejected_ids = set()
            stamps["rejections"] = rejection_sig
            stamps["reject_sat"] = self._sat_key()
        self._preview_file_stamps = stamps
''')
st=s.index("    def _render_sat_list(self, keep_index=True):",s.index("class SatIPTVBridgePreview(Screen):"))
en=s.index("    def _source_tag(self, ch, best_available=False):",st)
s=s[:st]+'''    def _render_sat_list(self, keep_index=True):
        """Redraw only selected SAT row; fallback to full setList when needed."""
        idx = self._sat_index_now() if keep_index else self.sat_index
        sat_list = self["sat_list"]
        current_source = id(self.sat_rows)
        cached_rows = getattr(self, "_sat_list_rendered", None)
        if (cached_rows is not None and not getattr(self, "_sat_list_dirty", True)
                and getattr(self, "_sat_list_source_id", None) == current_source
                and len(cached_rows) == len(self.sat_rows) and self.sat_rows):
            index = max(0, min(int(idx), len(self.sat_rows) - 1))
            row = self.sat_rows[index]
            label, state = self._sat_status(row)
            text = "[%s] %s" % (label, clean_display_name(row.get("name") or "SAT channel"))
            if cached_rows[index][0] != text:
                updated = sat_list.row(text, state)
                cached_rows[index] = updated
                try:
                    sat_list.l.invalidateEntry(index)
                except Exception:
                    self._suppress_sat_change = True
                    try:
                        sat_list.setList(cached_rows)
                        try: sat_list.moveToIndex(index)
                        except Exception: pass
                    finally: self._suppress_sat_change = False
            self.sat_index = index
            return

        rows = []
        for row in self.sat_rows:
            label, state = self._sat_status(row)
            text = "[%s] %s" % (label, clean_display_name(row.get("name") or "SAT channel"))
            rows.append(sat_list.row(text, state))
        if not rows:
            rows = [sat_list.row("[NO CRYPTED TV] No confirmed encrypted TV service", "NO_SOURCE")]
        self._suppress_sat_change = True
        try:
            try: sat_list.setList(rows)
            except Exception:
                try: sat_list.l.setList(rows)
                except Exception: pass
            if self.sat_rows:
                idx = max(0, min(int(idx), len(self.sat_rows) - 1))
                try: sat_list.moveToIndex(idx)
                except Exception: pass
                self.sat_index = idx
        finally:
            self._suppress_sat_change = False
        self._sat_list_rendered = rows
        self._sat_list_source_id = current_source
        self._sat_list_dirty = False

''' +s[en:]
once('''            self._refresh_mapping_caches()
            self._render_sat_list(keep_index=True)
            self._render_source_list(keep_index=True)''','''            self._refresh_mapping_caches(force=True)
            self._render_sat_list(keep_index=True)
            self._render_source_list(keep_index=True)''')
once('''            self._refresh_mapping_caches()
            # Preserve the exact SAT/source cursor''','''            self._refresh_mapping_caches(force=True)
            # Preserve the exact SAT/source cursor''')
pl.write_text(s)
u=P/"updater.py"
uv=u.read_text()
assert uv.count('CURRENT_VERSION = "1.0.46-r63"')==1
u.write_text(uv.replace('CURRENT_VERSION = "1.0.46-r63"','CURRENT_VERSION = "1.0.46-r64"',1))
(P/"CHANGELOG-r64-ULTRAFAST.txt").write_text(
    "r64 Ultra Fast Preview stage 1\n"
    "Only selected SAT row repainted while navigating cached list.\n"
    "Mapping and rejection JSON stat-cached; explicit writes force refresh.\n"
    "Unchanged picon never reloaded for IPTV cursor moves.\n"
    "No changes to playback, monitor, core, automatic matching, relay, NEO theme or timeshift.\n"
)
ctrl=WORK/"control/control"
c=ctrl.read_text()
assert c.count("Version: 1.0.46-r63")==1
c=c.replace("Version: 1.0.46-r63","Version: 1.0.46-r64",1)
c=re.sub(r"^Description:.*$","Description: IPToSat Pro r64 Ultra Fast Preview UI caching",c,flags=re.M)
ctrl.write_text(c)
for f in P.rglob("*.py"): compile(f.read_bytes(),str(f),"exec")
# Guard bytewise identity of all non-UI engine files.
with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(["ar","p",str(BASE),"data.tar.gz"])),mode="r:gz") as tf:
    for filename in ("core.py","monitor.py","neo_theme.py","timeshift_seek_patch.py"):
        old=tf.extractfile("./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"+filename).read()
        assert old==(P/filename).read_bytes(),filename
for k in ("data","control"):
    with tarfile.open(WORK/(k+".tar.gz"),"w:gz",format=tarfile.GNU_FORMAT) as tf:
        for path in sorted((WORK/k).rglob("*")):
            if "__pycache__" in path.parts or path.suffix in (".pyc",".pyo"): continue
            tf.add(path,arcname="./"+str(path.relative_to(WORK/k)),recursive=False)
(WORK/"debian-binary").write_text("2.0\n")
if OUT.exists():OUT.unlink()
subprocess.check_call(["ar","r",str(OUT),str(WORK/"debian-binary"),str(WORK/"control.tar.gz"),str(WORK/"data.tar.gz")],stdout=subprocess.DEVNULL)
print("R64 built",len(OUT.read_bytes()),hashlib.sha256(OUT.read_bytes()).hexdigest())

# r64 build release automation trigger
