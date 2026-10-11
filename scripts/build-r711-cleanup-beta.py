#!/usr/bin/env python3
"""R71.1 Neo Home CLEANUP: graphical fidelity + consolidated Tools menu.

Pinned to the exact R71.1 Neo Home experimental package. All player, monitor,
catalog, Preview Browser, mapping storage, fallback, audio and timeshift files
remain byte-identical. Uses a generated, static PNG backdrop so rounded cards
cost no repeated CPU/GPU redraw on Vu+ Zero 4K. Pillow is required at BUILD
time on GitHub Actions, NEVER on the receiver.
"""
import ast
import base64
import hashlib
import importlib.util
import io
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("r711_original", ROOT/"scripts/build-r711-neo-home.py")
original = importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
archive=original.archive
P=original.PREFIX
PLUGIN=P+"plugin.py"
UPDATER=P+"updater.py"
ASSET=P+"images/neo-home-cleanup.png"
CHANGELOG=P+"CHANGELOG-r711-NEO-CLEANUP.txt"
BASE_VERSION=original.VERSION
VERSION="1.0.46-r71.1-neo-cleanup-beta"
B64=ROOT/"payload/r711-neo-home-beta.b64"
BASE_SHA="e6108f374ac7aa5a5ac8f06bb0c707e94c1932754f75ee62b25091609bef68ff"
BASE_SIZE=279792

def background():
    from PIL import Image,ImageDraw
    scale=2
    W,H=1660,900
    c=lambda x:int(x*scale)
    img=Image.new("RGBA",(c(W),c(H)),(0,0,0,0))
    d=ImageDraw.Draw(img,"RGBA")
    def rect(x,y,w,h,fill,r=0,outline=None,width=1):
        shape=[c(x),c(y),c(x+w-1),c(y+h-1)]
        if r:
            d.rounded_rectangle(shape,radius=c(r),fill=fill,outline=outline,width=c(width) if outline else 1)
        else:
            d.rectangle(shape,fill=fill,outline=outline,width=c(width) if outline else 1)
    def line(points,color,width=2):
        d.line([(c(x),c(y)) for x,y in points],fill=color,width=c(width),joint="curve")
    def circle(x,y,r,col,width=2):
        d.ellipse([c(x-r),c(y-r),c(x+r),c(y+r)],outline=col,width=c(width))
    def arc(x,y,w,h,start,end,col,width=3):
        d.arc([c(x),c(y),c(x+w),c(y+h)],start,end,fill=col,width=c(width))
    bg="#0D1523";card="#19283F";accent="#49D6B1"
    rect(0,0,W,H,bg,31)
    line([(51,113),(1608,113)],"#253249",2)
    # TV glyph: small rounded television with aerial
    rect(55,31,62,47,None,9,"#49D6B1",3)
    line([(78,31),(69,23)],accent,3);line([(93,31),(103,21)],accent,3)
    line([(69,70),(104,70)],accent,2)
    # Active status pill
    rect(1398,28,213,51,"#143B36",24)
    # Main SAT channel, two status cards, selected IPTV
    rect(40,145,1580,166,card,28)
    rect(40,330,765,134,card,27)
    rect(825,330,795,134,card,27)
    rect(40,482,1580,213,card,29)
    rect(1356,495,235,49,"#16473D",22)
    # Signal track base with rounded ends; native progress bar will overlay it
    rect(75,411,562,17,"#344761",8)
    # IPTV READY check outline in second card
    circle(866,410,14,accent,3)
    line([(859,410),(864,415),(874,404)],accent,3)
    # Concept-matching cards with rounded corners
    rect(40,716,765,104,"#1F4146",24)
    rect(825,716,795,104,"#24334B",24)
    # scanner/preview icon (no fonts or icon dependencies)
    line([(381,745),(381,734),(391,734)],"#67E8CD",3)
    line([(425,745),(425,734),(415,734)],"#67E8CD",3)
    line([(381,761),(381,772),(391,772)],"#67E8CD",3)
    line([(425,761),(425,772),(415,772)],"#67E8CD",3)
    circle(403,752,8,"#67E8CD",2)
    circle(403,752,2,"#67E8CD",2)
    # Update icon
    arc(1189,734,32,32,200,345,"#D7E1F4",3)
    arc(1189,734,32,32,20,165,"#D7E1F4",3)
    line([(1217,732),(1223,738),(1214,739)],"#D7E1F4",3)
    line([(1191,767),(1185,761),(1194,759)],"#D7E1F4",3)
    # Footer uses understated blue / MENU only
    # Transparent/flat text zones are native Enigma2 Labels.
    img=img.resize((W,H),Image.Resampling.LANCZOS)
    out=io.BytesIO();img.save(out,format="PNG",optimize=True)
    blob=out.getvalue()
    assert blob[:8]==b"\x89PNG\r\n\x1a\n" and len(blob)<230000
    return blob

def source_skin():
    root=ET.fromstring(original.HOME_SKIN)
    # All rounded cards and icons are background-pixmap assets. Avoid any
    # rectangular eLabel overlays which would mask the rounded shapes.
    for child in list(root):
        if child.tag in ("eLabel","ePixmap"):
            root.remove(child)
    bg=ET.Element("ePixmap",{
        "zPosition":"0","position":"0,0","size":"1660,900",
        "pixmap":"__IPTOSAT_NEO_CLEANUP_BG__","alphatest":"blend"})
    root.insert(0,bg)
    wanted={
       "title", "subtitle", "version", "home_status", "home_channel_caption",
       "home_sat_name", "home_sat_context", "home_snr_head", "home_snr_bar",
       "home_snr_value", "home_iptv_head", "home_iptv_status", "home_iptv_detail",
       "home_selected_head", "home_selected_name", "home_lock_badge",
       "home_selected_badges", "home_selected_info", "home_preview_action",
       "home_preview_hint", "home_update_action", "home_update_hint",
       "home_menu_hint", "key_blue"}
    for w in list(root):
        if w.tag != "widget":continue
        name=w.get("name")
        if name not in wanted:
            root.remove(w)
            continue
        w.set("zPosition","3")
        if name=="title":
            w.set("position","148,26");w.set("size","1000,49");w.set("font","Regular;39")
        elif name=="subtitle":
            w.set("position","150,81");w.set("size","1080,24");w.set("font","Regular;18")
            w.set("foregroundColor","#9DAEC5")
        elif name=="version":
            w.set("position","1130,86");w.set("size","360,22");w.set("font","Regular;17")
        elif name=="home_status":
            w.set("position","1408,28");w.set("size","193,50");w.set("font","Regular;21")
            w.set("foregroundColor","#49D6B1")
        elif name=="home_channel_caption":
            w.set("position","73,164");w.set("size","1400,25");w.set("font","Regular;19")
        elif name=="home_sat_name":
            w.set("position","73,207");w.set("size","1490,55");w.set("font","Regular;41")
        elif name=="home_sat_context":
            w.set("position","75,266");w.set("size","1460,34");w.set("font","Regular;23")
        elif name=="home_snr_head":
            w.set("position","75,349");w.set("size","560,25")
        elif name=="home_snr_bar":
            w.set("position","76,411");w.set("size","562,17")
            w.set("foregroundColor","#49D6B1")
            w.set("backgroundColor","#344761")
        elif name=="home_snr_value":
            w.set("position","664,391");w.set("size","105,50");w.set("font","Regular;29")
        elif name=="home_iptv_head":
            w.set("position","860,350");w.set("size","600,25")
        elif name=="home_iptv_status":
            w.set("position","893,390");w.set("size","674,42")
            w.set("font","Regular;31");w.set("foregroundColor","#EFF8FA")
        elif name=="home_iptv_detail":
            w.set("position","860,433");w.set("size","733,22");w.set("font","Regular;16")
        elif name=="home_selected_head":
            w.set("position","75,504");w.set("size","970,27")
        elif name=="home_lock_badge":
            w.set("position","1369,497");w.set("size","213,45")
        elif name=="home_selected_name":
            w.set("position","76,550");w.set("size","1470,51")
        elif name=="home_selected_badges":
            w.set("position","76,619");w.set("size","1480,35")
            w.set("font","Regular;23")
        elif name=="home_selected_info":
            w.set("position","76,666");w.set("size","1480,22")
            w.set("font","Regular;16")
        elif name=="home_preview_action":
            w.set("position","160,755");w.set("size","531,35")
            w.set("font","Regular;27")
        elif name=="home_preview_hint":
            w.set("position","160,794");w.set("size","531,23")
            w.set("font","Regular;17")
        elif name=="home_update_action":
            w.set("position","936,755");w.set("size","550,35")
            w.set("font","Regular;27")
        elif name=="home_update_hint":
            w.set("position","936,794");w.set("size","550,23")
            w.set("font","Regular;17")
        elif name=="key_blue":
            w.set("position","50,846");w.set("size","670,31")
            w.set("font","Regular;20")
            w.set("foregroundColor","#A0B5CA")
            w.attrib.pop("halign",None)
        elif name=="home_menu_hint":
            w.set("position","1080,846");w.set("size","526,31")
            w.set("font","Regular;20")
            w.set("foregroundColor","#A0B5CA")
    # Enigma2 XML parser accepts self-closing native component tags.
    xml=ET.tostring(root,encoding="unicode")
    original.inspect_skin(xml)
    return xml

def replace_exact(src,old,new,number=1):
    if src.count(old)!=number:
        raise AssertionError("Guarded cleanup anchor drift: "+repr(old[:110])+" count "+str(src.count(old)))
    return src.replace(old,new,number)

def patched(raw):
    s=raw.decode()
    # Preserve all R71.1 original content except Dashboard skin and actual menu/actions.
    ss='DASHBOARD_FHD = """\n'
    ee='\n"""\n\nSETTINGS_FHD = """'
    assert s.count(ss)==1 and s.count(ee)==1
    before,rest=s.split(ss,1)
    old,after=rest.split(ee,1)
    skin=source_skin()
    s=before+ss+skin+ee+after
    s=replace_exact(s,'self.skin = _theme_skin(DASHBOARD_FHD)',
        '''self.skin = _theme_skin(DASHBOARD_FHD.replace(
            "__IPTOSAT_NEO_CLEANUP_BG__",
            os.path.join(os.path.dirname(__file__), "images", "neo-home-cleanup.png")))''')
    # Home doesn't need an additional label for the RED EXIT button;
    # visual buttons are native Labels over painted pixel-art rounded cards.
    s=replace_exact(s,'self["home_preview_action"] = Label("PREVIEW BROWSER")',
                    'self["home_preview_action"] = Label("Preview Browser")')
    s=replace_exact(s,'self["home_update_action"] = Label("ONLINE UPDATE")',
                    'self["home_update_action"] = Label("Online Update")')
    s=replace_exact(s,'self["home_preview_hint"] = Label("GREEN  •  All IPTV sources")',
                    'self["home_preview_hint"] = Label("GREEN")')
    s=replace_exact(s,'self["home_update_hint"] = Label("YELLOW  •  Check GitHub")',
                    'self["home_update_hint"] = Label("YELLOW")')
    s=replace_exact(s,'self["home_menu_hint"] = Label("MENU  SETTINGS")',
                    'self["home_menu_hint"] = Label("MENU  •  Settings / Tools")')
    s=replace_exact(s,'self["key_blue"] = Label("BLUE  LOGS")',
                    'self["key_blue"] = Label("BLUE  •  Logs")')
    s=replace_exact(s,'''ActionMap(["OkCancelActions", "ColorActions", "DirectionActions", "MenuActions", "NumberActions"], {
            "cancel": self.close, "red": self.close, "green": self.open_preview_sources,
            "yellow": self.open_updater, "ok": self.open_preview_sources, "blue": self.open_logs,
            "menu": self.open_settings, "0": self.player_lock_current, "1": self.open_safe_diagnostics, "2": self.open_updater, "3": self.open_auto_scan, "4": self.open_all_sources, "5": self.test_match,
            "chplus": self.zap_next_channel, "chminus": self.zap_previous_channel,
        }, -2)''',
        '''ActionMap(["OkCancelActions", "ColorActions", "DirectionActions", "MenuActions"], {
            "cancel": self.close, "red": self.close,
            "green": self.open_preview_sources, "ok": self.open_preview_sources,
            "yellow": self.open_updater, "blue": self.open_logs,
            "menu": self.open_settings,
            "chplus": self.zap_next_channel, "chminus": self.zap_previous_channel,
        }, -2)''')
    s=replace_exact(s,'''    def open_settings(self):
        def done(result=None):
            self._safe_refresh_view()
        # MENU opens the complete settings list directly; no numbered hub/sub-menu.
        self.session.openWithCallback(done, SatIPTVBridgeSettings, "all")
''',
    '''    def open_settings(self):
        """R71.1 Tools hub: keep advanced power features but OFF the compact Home."""
        from Screens.ChoiceBox import ChoiceBox
        entries = [
            ("Settings  •  Essential", "quick"),
            ("Settings  •  Advanced / IPTV sources", "advanced"),
            ("Tools  •  Manual Mapping (All Sources)", "mapping"),
            ("Tools  •  Smart Match Test", "match_test"),
            ("Tools  •  Auto Scan", "auto_scan"),
            ("Tools  •  Player Lock", "player_lock"),
            ("Tools  •  System Diagnostics", "diagnostics"),
            ("Tools  •  Event Log", "logs"),
            ("Tools  •  Online Update", "update"),
        ]
        self.session.openWithCallback(
            self._r711_tools_choice, ChoiceBox,
            title="IPToSat Pro  •  Settings / Tools", list=entries)

    def _r711_tools_choice(self, item):
        if not item:
            return
        try:
            selected = item[1] if isinstance(item, (tuple, list)) and len(item)>1 else item
        except Exception:
            return
        if selected in ("quick","advanced"):
            mode = "quick" if selected=="quick" else "all"
            def done(result=None):
                self._safe_refresh_view()
            self.session.openWithCallback(done, SatIPTVBridgeSettings, mode)
        elif selected=="mapping":
            self.open_all_sources()
        elif selected=="match_test":
            self.test_match()
        elif selected=="auto_scan":
            self.open_auto_scan()
        elif selected=="player_lock":
            self.player_lock_current()
        elif selected=="diagnostics":
            self.open_safe_diagnostics()
        elif selected=="logs":
            self.open_logs()
        elif selected=="update":
            self.open_updater()
''')
    # Remove unverified "LIVE" assertions; mapping != confirmed playing video.
    s=replace_exact(s,'self["home_lock_badge"].setText("LOCKED" if self._r711_lock_active else ("LIVE" if active else "NO LOCK"))',
                    'self["home_lock_badge"].setText("LOCKED" if self._r711_lock_active else ("IPTV LIVE" if active else "UNMAPPED"))')
    # Show actual named video class and FR metadata when present, but never invent.
    s=replace_exact(s,'''        self["home_selected_badges"].setText("%s     •     %s     •     %s" % (quality, role, mode or "AUTO"))''',
        '''        quality_short = ("4K/UHD" if iw>=3000 else ("FHD" if iw>=1800 and ih>=1000
                         else ("HD" if iw>=1200 and ih>=700 else ("SD" if iw and ih else "?"))))
        language = str(snap.get("language") or "").strip().upper()
        audio_badge = ("Audio %s*" % language[:6]) if language not in ("", "-", "UNKNOWN", "NONE") else "Audio ?"
        ready_mark = "Fast Zap" if 0 < timing <= 2000 else (mode or "AUTO")
        self["home_selected_badges"].setText(
            "%s  •  %s  •  %s  •  %s" % (quality_short, audio_badge, role, ready_mark))''')
    s=replace_exact(s,'self["home_selected_info"].setText("First frame: %s  •  %s" %',
                    'self["home_selected_info"].setText("Video %s  •  First frame %s  •  %s" %',1)
    s=replace_exact(s,'''(elapsed, str(snap.get("play_result") or "Waiting")[:45]))''',
                    '''(quality, elapsed, str(snap.get("play_result") or "Waiting")[:45]))''',1)
    # Present source availability accurately: "READY" means catalogue cache,
    # not confirmed live video or verified source reachability.
    s=replace_exact(s,'self["home_iptv_detail"].setText("%d IPTV channels cached  •  no live stream probe" % count)',
                    'self["home_iptv_detail"].setText("%d IPTV channels in catalog" % count)')
    # Screen state "ACTIVE" only when fallback enabled and monitor exists.
    s=replace_exact(s,'self["home_status"].setText("AUTO ON" if cfg.enabled.value and MONITOR is not None',
                    'self["home_status"].setText("ACTIVE" if cfg.enabled.value and MONITOR is not None')
    # Ensure key routes exist, no duplicate methods, all displayed widgets backed.
    parsed=ast.parse(s)
    dashboard=next(x for x in parsed.body if isinstance(x,ast.ClassDef) and x.name=="SatIPTVBridgeDashboard")
    names=[x.name for x in dashboard.body if isinstance(x,ast.FunctionDef)]
    assert len(names)==len(set(names)), "Duplicate Dashboard method"
    widgets={w.get("name") for w in ET.fromstring(skin) if w.tag=="widget"}
    init=next(x for x in dashboard.body if isinstance(x,ast.FunctionDef) and x.name=="__init__")
    initialized=set()
    for x in ast.walk(init):
        if isinstance(x,ast.Subscript) and isinstance(x.value,ast.Name) and x.value.id=="self":
            if isinstance(x.slice,ast.Constant) and isinstance(x.slice.value,str):initialized.add(x.slice.value)
    assert widgets<=initialized, "Unbound skin UI: "+repr(widgets-initialized)
    assert "TOD Dynamic" not in s[0:15000]
    compile(s,PLUGIN,"exec")
    return s.encode()

def build(output=None):
    from PIL import Image
    raw=base64.b64decode(B64.read_bytes())
    assert len(raw)==BASE_SIZE and hashlib.sha256(raw).hexdigest()==BASE_SHA, "R71.1 baseline drift"
    parts=archive.unpack_ar(raw)
    original_data=archive.members_from(parts["data.tar.gz"])
    ctrl=archive.members_from(parts["control.tar.gz"])
    new_plugin=patched(original_data[PLUGIN]).decode()
    oldver='PLUGIN_VERSION = "%s"' % BASE_VERSION
    assert new_plugin.count(oldver)==1
    new_plugin=new_plugin.replace(oldver,'PLUGIN_VERSION = "%s"'%VERSION,1).encode()
    updated=original_data[UPDATER].decode()
    old='CURRENT_VERSION = "%s"'%BASE_VERSION
    assert updated.count(old)==1
    updated=updated.replace(old,'CURRENT_VERSION = "%s"'%VERSION,1).encode()
    control=ctrl["control"].decode()
    assert control.count("Version: "+BASE_VERSION)==1
    new_control=control.replace("Version: "+BASE_VERSION,"Version: "+VERSION,1).encode()
    asset_bytes=background()
    with Image.open(io.BytesIO(asset_bytes)) as rendered:
        assert rendered.size==(1660,900) and rendered.mode=="RGBA"
    changes={PLUGIN:new_plugin,UPDATER:updated}
    adds={ASSET:asset_bytes,CHANGELOG:(
        "R71.1 Neo Home CLEANUP: rounded static PNG cards and icons based on approved conceptual screenshot; "
        "Home GREEN Preview, YELLOW Update, BLUE Logs, MENU Settings/Tools ChoiceBox. "
        "Old separate Smart Match, classic All Sources, Auto Scan, Player Lock, "
        "Diagnostics kept in Tools; Quality Target/Best Match/Suggestion/Context removed "
        "from Home visual only. SAT SNR actual, IPTV cached not live probe; unknowns not invented. "
        "All player, mapping, Preview and timeshift runtime byte-identical. "
        "NOT tested on physical receiver.\n").encode()}
    parts["data.tar.gz"]=archive.make_tar(parts["data.tar.gz"],changes,adds)
    parts["control.tar.gz"]=archive.make_tar(parts["control.tar.gz"],{"control":new_control})
    path=Path(output) if output else ROOT/"r711-neo-cleanup-beta.ipk"
    if path.exists():path.unlink()
    package=archive.assemble(parts,path)
    after=archive.members_from(archive.unpack_ar(package)["data.tar.gz"])
    controls=archive.members_from(archive.unpack_ar(package)["control.tar.gz"])
    assert set(after)==set(original_data)|set(adds)
    for name,old in original_data.items():
        assert after[name]==changes.get(name,old),"Unauthorized code changed: "+name
    assert controls["control"]==new_control
    for name,old in ctrl.items():
        if name!="control":assert controls[name]==old
    for name,src in after.items():
        if name.endswith(".py"):compile(src,name,"exec")
    info={"version":VERSION,"bytes":len(package),"sha256":hashlib.sha256(package).hexdigest(),
          "changed":sorted(changes),"new_assets":sorted(adds),"protected_unchanged":len(original_data)-len(changes),
          "receiver_tested":False,"stable_main_unchanged":True}
    print("R711_CLEANUP_PACKAGE_OK",json.dumps(info,sort_keys=True))
    return info

if __name__=="__main__":
    build(sys.argv[1] if len(sys.argv)>1 else None)
