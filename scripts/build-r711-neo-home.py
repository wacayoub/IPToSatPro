#!/usr/bin/env python3
"""R71.1 Neo Home preview candidate from the SHA-pinned R71 UI beta.

Only dashboard skin, screen labels, dashboard action routing and read-only
presentation data change. Binary/player/fast-zap/mapping/TS/Preview all byte exact.
No source downloads, locks, user settings or receiver actions during build.
"""
import ast
import base64
import hashlib
import importlib.util
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("r71ui", ROOT/"scripts/build-r71-ui-beta.py")
b = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(b)
archive = b.base
PREFIX = archive.PREFIX
PLUGIN = PREFIX + "plugin.py"
UPDATER = PREFIX + "updater.py"
VERSION = "1.0.46-r71.1-neo-home-beta"
BASE_VERSION = "1.0.46-r71-ui-beta"
B64 = ROOT/"payload/r71-ui-beta.b64"
BASE_BYTES = 278240
BASE_SHA = "f61fda976653ef3b17c717f8798cd96277437ec9984402b75bed5c4389634b56"
CHANGELOG = PREFIX + "CHANGELOG-r71.1-NEO-HOME.txt"

# 1660 x 900 Enigma2 pixel coordinates. All widgets use native Label and
# ProgressBar; no SVG, custom fonts, HTML or expensive image decoding.
HOME_SKIN = r'''
<screen name="SatIPTVBridgeDashboard" position="center,center" size="1660,900" title="IPToSat Pro • Neo Home" backgroundColor="#0C1421">
    <eLabel zPosition="0" position="0,0" size="1660,105" backgroundColor="#111C2C" />
    <eLabel zPosition="1" position="0,102" size="1660,3" backgroundColor="#49D6B1" />
    <ePixmap zPosition="2" position="32,18" size="100,66" pixmap="__IPTOSAT_PLUGIN_LOGO__" alphatest="blend" />
    <widget name="title" zPosition="3" position="148,16" size="850,50" font="Regular;38" foregroundColor="#F4F7FD" transparent="1" />
    <widget name="subtitle" zPosition="3" position="150,68" size="1010,27" font="Regular;19" foregroundColor="#9DAEC5" transparent="1" />
    <widget name="version" zPosition="3" position="1070,28" size="310,32" font="Regular;20" halign="right" foregroundColor="#A8BDD5" transparent="1" />
    <eLabel zPosition="1" position="1413,25" size="207,51" backgroundColor="#20483F" />
    <widget name="home_status" zPosition="3" position="1422,25" size="190,50" font="Regular;21" foregroundColor="#78F0CE" halign="center" valign="center" transparent="1" />

    <eLabel zPosition="0" position="40,125" size="1580,170" backgroundColor="#162338" />
    <eLabel zPosition="1" position="40,125" size="6,170" backgroundColor="#49D6B1" />
    <widget name="home_channel_caption" zPosition="3" position="74,141" size="1200,26" font="Regular;18" foregroundColor="#93A8BF" transparent="1" />
    <widget name="home_sat_name" zPosition="3" position="74,170" size="1480,56" font="Regular;41" foregroundColor="#F4F7FD" transparent="1" />
    <widget name="home_sat_context" zPosition="3" position="76,237" size="1480,36" font="Regular;23" foregroundColor="#B5C5D9" transparent="1" />

    <eLabel zPosition="0" position="40,316" size="765,132" backgroundColor="#162338" />
    <eLabel zPosition="0" position="825,316" size="795,132" backgroundColor="#162338" />
    <widget name="home_snr_head" zPosition="3" position="76,329" size="450,27" font="Regular;20" foregroundColor="#93A8BF" transparent="1" />
    <widget name="home_snr_bar" zPosition="3" position="76,378" size="557,19" foregroundColor="#49D6B1" backgroundColor="#30455C" />
    <widget name="home_snr_value" zPosition="3" position="652,365" size="110,43" font="Regular;30" halign="right" foregroundColor="#E8F0FF" transparent="1" />
    <widget name="home_iptv_head" zPosition="3" position="862,329" size="500,27" font="Regular;20" foregroundColor="#93A8BF" transparent="1" />
    <widget name="home_iptv_status" zPosition="3" position="862,360" size="700,42" font="Regular;31" foregroundColor="#65E5CE" transparent="1" />
    <widget name="home_iptv_detail" zPosition="3" position="863,406" size="730,28" font="Regular;18" foregroundColor="#ADC2D8" transparent="1" />

    <eLabel zPosition="0" position="40,467" size="1580,220" backgroundColor="#162338" />
    <eLabel zPosition="1" position="40,467" size="6,220" backgroundColor="#28639C" />
    <widget name="home_selected_head" zPosition="3" position="75,483" size="720,28" font="Regular;21" foregroundColor="#A4B8D1" transparent="1" />
    <eLabel zPosition="1" position="1367,476" size="225,39" backgroundColor="#20483F" />
    <widget name="home_lock_badge" zPosition="3" position="1374,476" size="210,39" font="Regular;20" halign="center" valign="center" foregroundColor="#78F0CE" transparent="1" />
    <widget name="home_selected_name" zPosition="3" position="76,526" size="1470,51" font="Regular;34" foregroundColor="#F0F5FD" transparent="1" />
    <widget name="home_selected_badges" zPosition="3" position="76,591" size="1480,34" font="Regular;22" foregroundColor="#7EE6C9" transparent="1" />
    <widget name="home_selected_info" zPosition="3" position="76,642" size="1480,28" font="Regular;18" foregroundColor="#A8B9D1" transparent="1" />

    <eLabel zPosition="0" position="40,707" size="765,100" backgroundColor="#1F4245" />
    <eLabel zPosition="1" position="40,707" size="7,100" backgroundColor="#49D6B1" />
    <widget name="home_preview_action" zPosition="3" position="62,726" size="720,36" font="Regular;28" foregroundColor="#EDFDF8" halign="center" transparent="1" />
    <widget name="home_preview_hint" zPosition="3" position="62,766" size="720,23" font="Regular;18" foregroundColor="#B0D6CE" halign="center" transparent="1" />
    <eLabel zPosition="0" position="825,707" size="795,100" backgroundColor="#263750" />
    <eLabel zPosition="1" position="825,707" size="7,100" backgroundColor="#E4C15B" />
    <widget name="home_update_action" zPosition="3" position="845,726" size="754,36" font="Regular;28" foregroundColor="#F3F7FF" halign="center" transparent="1" />
    <widget name="home_update_hint" zPosition="3" position="845,766" size="754,23" font="Regular;18" foregroundColor="#B9C8DA" halign="center" transparent="1" />

    <eLabel zPosition="0" position="40,824" size="1580,59" backgroundColor="#111C2C" />
    <widget name="key_red" zPosition="3" position="60,830" size="235,42" font="Regular;21" foregroundColor="#F08C8C" transparent="1" />
    <widget name="key_green" zPosition="3" position="291,830" size="360,42" font="Regular;21" foregroundColor="#65E5CE" transparent="1" />
    <widget name="key_yellow" zPosition="3" position="660,830" size="390,42" font="Regular;21" foregroundColor="#E4C15B" transparent="1" />
    <widget name="key_blue" zPosition="3" position="1068,830" size="280,42" font="Regular;21" foregroundColor="#91B9F3" transparent="1" />
    <widget name="home_menu_hint" zPosition="3" position="1370,830" size="225,42" font="Regular;20" halign="right" foregroundColor="#BED1E7" transparent="1" />
</screen>
'''.strip()

def replace_once(s, old, new):
    if s.count(old) != 1:
        raise AssertionError("Unexpected shipped plugin anchor %d: %s" %
                             (s.count(old), repr(old[:120])))
    return s.replace(old,new,1)

def inspect_skin(xml):
    screen = ET.fromstring(xml)
    assert screen.tag == "screen"
    assert screen.attrib.get("size") == "1660,900"
    names=set()
    for element in screen.iter():
        if element.tag not in ("screen","widget","eLabel","ePixmap"):
            raise AssertionError("Unsupported skin item "+element.tag)
        if element.tag!="screen":
            x,y=map(int,element.attrib["position"].split(","))
            w,h=map(int,element.attrib["size"].split(","))
            assert 0<=x and 0<=y and w>0 and h>0 and x+w<=1660 and y+h<=900, (element.tag,element.attrib)
            if element.tag=="widget":
                key=element.attrib["name"]
                assert key not in names,"duplicate widget: "+key
                names.add(key)
    required=("title","subtitle","version","home_status","home_sat_name",
              "home_sat_context","home_snr_bar","home_snr_value","home_iptv_status",
              "home_selected_name","home_selected_badges","home_selected_info",
              "home_lock_badge","home_preview_action","home_update_action",
              "key_red","key_green","key_yellow","key_blue","home_menu_hint")
    assert set(required)<=names
    return names

def patch_plugin(raw):
    s=raw.decode("utf-8")
    start='DASHBOARD_FHD = """\n'
    end='\n"""\n\nSETTINGS_FHD = """'
    assert s.count(start)==1 and s.count(end)==1
    before, rest=s.split(start,1)
    oldskin,after=rest.split(end,1)
    s=before+start+HOME_SKIN+end+after
    # Keep all existing snapshot computations and failover logic as-is. The old
    # widgets can remain unskinned to make all established methods work.
    anchor='''        self["version"] = Label(PLUGIN_VERSION)
'''
    inject='''        self["home_status"] = Label("STARTING")
        self["home_channel_caption"] = Label("CURRENT CHANNEL")
        self["home_sat_name"] = Label("No SAT channel")
        self["home_sat_context"] = Label("Satellite and provider unavailable")
        from Components.ProgressBar import ProgressBar
        self["home_snr_head"] = Label("SAT SIGNAL")
        self["home_snr_bar"] = ProgressBar()
        self["home_snr_bar"].setValue(0)
        self["home_snr_value"] = Label("N/A")
        self["home_iptv_head"] = Label("IPTV STATUS")
        self["home_iptv_status"] = Label("STARTING")
        self["home_iptv_detail"] = Label("Waiting for catalogue")
        self["home_selected_head"] = Label("SELECTED IPTV")
        self["home_selected_name"] = Label("No active IPTV stream")
        self["home_lock_badge"] = Label("—")
        self["home_selected_badges"] = Label("Resolution —   •   Source —   •   Speed —")
        self["home_selected_info"] = Label("Waiting for stream verification")
        self["home_preview_action"] = Label("PREVIEW BROWSER")
        self["home_preview_hint"] = Label("GREEN  •  All IPTV sources")
        self["home_update_action"] = Label("ONLINE UPDATE")
        self["home_update_hint"] = Label("YELLOW  •  Check GitHub")
        self["home_menu_hint"] = Label("MENU  SETTINGS")
        self._r711_lock_ref = None
        self._r711_lock_checked_at = 0.0
        self._r711_lock_active = False
'''
    s=replace_once(s,anchor,anchor+inject)
    s=replace_once(s,'self["subtitle"] = Label("NEO DARK  •  COMFORTABLE  •  SMARTMATCH  [P] [B1] [B2]" if cfg.ui_theme.value == "neo" and cfg.ui_density.value == "comfortable" else "SAT / IPTV  •  SMARTMATCH  [P] [B1] [B2]")',
                    'self["subtitle"] = Label("R71.1  •  SMART SAT / IPTV  •  NEO HOME")')
    s=replace_once(s,'self["key_red"] = Label("EXIT"); self["key_green"] = Label("PREVIEW"); self["key_yellow"] = Label("SMART MATCH"); self["key_blue"] = Label("EVENT LOG")',
                    'self["key_red"] = Label("RED  EXIT"); self["key_green"] = Label("GREEN  PREVIEW"); self["key_yellow"] = Label("YELLOW  UPDATE"); self["key_blue"] = Label("BLUE  LOGS")')
    s=replace_once(s,'"yellow": self.test_match, "ok": self.test_match, "blue": self.open_logs,',
                    '"yellow": self.open_updater, "ok": self.open_preview_sources, "blue": self.open_logs,')
    s=replace_once(s,'"3": self.open_auto_scan, "4": self.open_all_sources,',
                    '"3": self.open_auto_scan, "4": self.open_all_sources, "5": self.test_match,')
    # Dashboard is refreshed on a 2.5s timer already. Read loaded monitor data,
    # no remote IPTV work, no external network calls, and map lookup at most 12s.
    marker='''        self["log_preview"].setText(self._bridge_suggestion(snap, decision))
'''
    display='''        # R71.1 Neo Home: presentation ONLY, all fields come from the live snapshot.
        # Do not call network, rescan sources, change playback or invent SNR/codec.
        self["home_status"].setText("AUTO ON" if cfg.enabled.value and MONITOR is not None
                                    else ("AUTO OFF" if not cfg.enabled.value else "OFFLINE"))
        sat_name = clean_display_name(snap.get("sat") or "")
        if sat_name in ("", "-"):
            sat_name = "No SAT channel"
        self["home_sat_name"].setText(sat_name[:79])
        provider = str(snap.get("provider") or "Unknown")
        sat = str(snap.get("satellite") or "Unknown")
        orbital = str(snap.get("orbital") or "")
        if orbital not in ("", "-", "Unknown") and orbital not in sat:
            sat += "  •  " + orbital
        self["home_sat_context"].setText("%s  •  %s" % (sat[:46], provider[:52]))
        # Satellite strength and IPTV readiness are deliberately DIFFERENT.
        # If a tuner exposes no numeric SNR, never manufacture a percentage.
        snr_text = str(snap.get("sat_snr") or "").strip()
        snr_numeric = None
        try:
            fragment = "".join(ch for ch in snr_text if ch.isdigit() or ch in ",.")
            value = float(fragment.replace(",", "."))
            if 0 <= value <= 100:
                snr_numeric = int(round(value))
        except Exception:
            pass
        self["home_snr_value"].setText(("%d%%" % snr_numeric) if snr_numeric is not None else "N/A")
        try:
            self["home_snr_bar"].setValue(snr_numeric if snr_numeric is not None else 0)
        except Exception:
            pass
        if job.get("state") == "running":
            iptv_status = "IMPORTING"
        elif snap.get("cache_loading"):
            iptv_status = "LOADING"
        elif count > 0:
            iptv_status = "READY"
        else:
            iptv_status = "NO CATALOG"
        self["home_iptv_status"].setText(iptv_status)
        if count > 0:
            self["home_iptv_detail"].setText("%d IPTV channels cached  •  no live stream probe" % count)
        else:
            self["home_iptv_detail"].setText("Open Settings to refresh sources" if not snap.get("cache_loading")
                                              else "Cache loading in low-impact slices")
        active_name = str(snap.get("iptv") or "")
        active = active_name not in ("", "-", "None")
        self["home_selected_name"].setText(presentation_name(active_name)[:78] if active else "No active IPTV stream")
        mode = str(snap.get("play_mode") or "").upper()
        role = _short_role(snap.get("server_role") or "-") if active else "—"
        try:
            iw = int(snap.get("iptv_width") or 0)
            ih = int(snap.get("iptv_height") or 0)
        except Exception:
            iw = ih = 0
        quality = ("%d × %d" % (iw, ih)) if iw>0 and ih>0 else "Resolution unknown"
        timing = int(snap.get("first_frame_ms") or 0)
        elapsed = ("%d ms" % timing) if timing>0 else "Not measured"
        self["home_selected_badges"].setText("%s     •     %s     •     %s" % (quality, role, mode or "AUTO"))
        self["home_selected_info"].setText("First frame: %s  •  %s" %
                                           (elapsed, str(snap.get("play_result") or "Waiting")[:45]))
        # Read the existing manual mapping only occasionally; do not touch flash
        # on every refresh, and never mark IPTV locked from a scoring estimate.
        sat_ref = str(getattr(MONITOR, "current_sat_ref_string", "") or "") if MONITOR is not None else ""
        now = time.monotonic()
        if sat_ref != self._r711_lock_ref or now-self._r711_lock_checked_at > 12:
            self._r711_lock_ref = sat_ref
            self._r711_lock_checked_at = now
            self._r711_lock_active = False
            if sat_ref:
                try:
                    self._r711_lock_active = bool(_load_overrides().get(sat_service_key(sat_ref)))
                except Exception:
                    pass
        self["home_lock_badge"].setText("LOCKED" if self._r711_lock_active else ("LIVE" if active else "NO LOCK"))
'''
    s=replace_once(s,marker,marker+display)
    # Only the production visible skin must be backed by real initialized keys.
    names=inspect_skin(HOME_SKIN)
    class_node=next(n for n in ast.parse(s).body if isinstance(n,ast.ClassDef) and n.name=="SatIPTVBridgeDashboard")
    init=next(n for n in class_node.body if isinstance(n,ast.FunctionDef) and n.name=="__init__")
    literal_names=set()
    for node in ast.walk(init):
        if isinstance(node,ast.Subscript) and isinstance(node.value,ast.Name) and node.value.id=="self":
            idx=node.slice
            if isinstance(idx,ast.Constant) and isinstance(idx.value,str):
                literal_names.add(idx.value)
    if not names <= literal_names:
        raise AssertionError("Unbound UI components: "+repr(sorted(names-literal_names)))
    compile(s, PLUGIN, "exec")
    return s.encode()

def build(output=None):
    raw=base64.b64decode(B64.read_bytes())
    assert len(raw)==BASE_BYTES and hashlib.sha256(raw).hexdigest()==BASE_SHA, "R71 UI baseline changed"
    parts=archive.unpack_ar(raw)
    before=archive.members_from(parts["data.tar.gz"])
    control=archive.members_from(parts["control.tar.gz"])
    new_plugin=patch_plugin(before[PLUGIN])
    old='%s = "%s"'%("PLUGIN_VERSION",BASE_VERSION)
    assert new_plugin.decode().count(old)==1
    new_plugin=new_plugin.decode().replace(old,'PLUGIN_VERSION = "%s"'%VERSION,1).encode()
    updater=before[UPDATER].decode()
    old='CURRENT_VERSION = "%s"'%BASE_VERSION
    assert updater.count(old)==1
    changes={PLUGIN:new_plugin,UPDATER:updater.replace(old,'CURRENT_VERSION = "%s"'%VERSION,1).encode()}
    orig=control["control"].decode()
    assert orig.count("Version: "+BASE_VERSION)==1
    updated_control=orig.replace("Version: "+BASE_VERSION,"Version: "+VERSION,1).encode()
    parts["data.tar.gz"]=archive.make_tar(parts["data.tar.gz"],changes,{CHANGELOG:
         b"R71.1 Neo Home: new Enigma2 1660x900 one-page layout with SAT signal, IPTV catalog, selected candidate, manual lock status; GREEN Preview, YELLOW Update, BLUE Logs, MENU Settings. No player or mappings changed.\n"})
    parts["control.tar.gz"]=archive.make_tar(parts["control.tar.gz"],{"control":updated_control})
    out=Path(output) if output else ROOT/"r71.1-neo-home-beta.ipk"
    if out.exists():out.unlink()
    built=archive.assemble(parts,out)
    after=archive.members_from(archive.unpack_ar(built)["data.tar.gz"])
    ctl=archive.members_from(archive.unpack_ar(built)["control.tar.gz"])
    assert set(after)==set(before)|{CHANGELOG}
    for path,old_raw in before.items():
        assert after[path]==changes.get(path,old_raw),"Unexpected modified path "+path
    for path,old_raw in control.items():
        assert ctl[path]==(updated_control if path=="control" else old_raw)
    for path,contents in after.items():
        if path.endswith(".py"):compile(contents,path,"exec")
    metadata={"version":VERSION,"size":len(built),"sha256":hashlib.sha256(built).hexdigest(),
              "changed":sorted(changes),"unmodified_files":len(before)-len(changes),
              "fast_zap_changed":False,"preview_changed":False,"receiver_tested":False,
              "published_to_main":False,"needs_gui_validation":True}
    print("R711_HOME_PACKAGE_OK",json.dumps(metadata,sort_keys=True))
    return metadata

if __name__=="__main__":
    build(sys.argv[1] if len(sys.argv)>1 else None)
