#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.7: eleven real native Enigma2 HD/FHD dashboard skins and grouped TV menu.

All themes share IDENTICAL existing live widgets, bindings, remote controls,
mapping files, stream player and Preview B. Only appearance and HOME menu
presentation change. All XML is fully static at runtime (no SVG, animations,
network image fetches, Python overlay, CPU-heavy renderer or extra polling).
"""
import ast
import importlib.util
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def base_layout():
    spec=importlib.util.spec_from_file_location("r767_base",ROOT/"scripts"/"r76_metrix_preview_layout.py")
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
    return obj

# 11 user-requested home themes. IDs are stable persistent values.
THEME_CHOICES=(
 ("01  Neo Dark Classic", "neo_dark"),
 ("02  OLED Black Pro", "oled"),
 ("03  Matrix Command Center", "matrix"),
 ("04  Cinema TV Launcher", "cinema"),
 ("05  NeoPro Glass Blue", "glass"),
 ("06  Executive Light", "executive"),
 ("07  Carbon Speed", "carbon"),
 ("08  Royal Gold Premium", "gold"),
 ("09  Metro Tiles", "metro"),
 ("10  Studio Compact Pro", "studio"),
 ("11  Metrix OpenATV  (default)", "metrix"),
)
# Layouts: side-left or side-right, left and right with the same live data.
THEMES={
 "neo_dark":  dict(bg="#080E15",head="#111B25",side="#162532",main="#102034",tile="#1B2B38",accent="#24C7AF",text="#F0F6FC",muted="#A7C1D2",highlight="#22565A",placement="left"),
 "oled":      dict(bg="#000000",head="#080808",side="#101010",main="#101010",tile="#171717",accent="#72E9CD",text="#FFFFFF",muted="#C2C2C2",highlight="#184E44",placement="left"),
 "matrix":    dict(bg="#030A06",head="#08150E",side="#0B1B10",main="#0B2012",tile="#11291B",accent="#58E48B",text="#DFFFE4",muted="#9FCCAF",highlight="#24583A",placement="right"),
 "cinema":    dict(bg="#0B0E17",head="#16182B",side="#201927",main="#131827",tile="#252336",accent="#F7BC73",text="#FFF7ED",muted="#CFBAC3",highlight="#534059",placement="right"),
 "glass":     dict(bg="#07142C",head="#112A4F",side="#123052",main="#153458",tile="#214971",accent="#55CAFA",text="#F5FAFF",muted="#BDDDF3",highlight="#236BA0",placement="right"),
 "executive": dict(bg="#E8EEF3",head="#F7FAFD",side="#D6E1EB",main="#FFFFFF",tile="#F1F5F8",accent="#1E649B",text="#102A3F",muted="#445C6D",highlight="#BFD7EC",placement="right"),
 "carbon":    dict(bg="#0A0B0C",head="#171A1C",side="#1B2023",main="#1F2428",tile="#272D31",accent="#F6A34B",text="#FAFAFA",muted="#C8D1D5",highlight="#5F3D23",placement="left"),
 "gold":      dict(bg="#0B0A0A",head="#17130E",side="#211B13",main="#201C16",tile="#2A241B",accent="#E9C472",text="#FFF4D9",muted="#D2BC92",highlight="#5E4B27",placement="left"),
 "metro":     dict(bg="#0D1423",head="#1A2335",side="#152D46",main="#122944",tile="#204363",accent="#4DA4F7",text="#FCFCFF",muted="#C0D9F3",highlight="#1765A4",placement="left"),
 "studio":    dict(bg="#0E1720",head="#1B2732",side="#202C38",main="#1B303F",tile="#283E4D",accent="#9AC9F5",text="#F5F9FC",muted="#BCCDDD",highlight="#2B5273",placement="right"),
 "metrix":    dict(bg="#090E15",head="#111B26",side="#17222D",main="#182633",tile="#1B2D3D",accent="#2388D1",text="#F6FAFF",muted="#C0D5E5",highlight="#245781",placement="left"),
}
assert len(THEME_CHOICES)==len(THEMES)==11

# Native key-strip semantics never recolored out of red/green/yellow/blue.
KEY_COLORS={"key_red":"#8A343E","key_green":"#257955",
            "key_yellow":"#A78129","key_blue":"#286B9A"}
# Widgets that represent actual status; do not invent success/playing state.
SIDEBAR_WIDGETS={
 "home_channel_caption","home_preview_action","home_update_action",
 "home_menu_hint","r76_system_label","home_selected_head","home_selected_name",
 "home_iptv_detail","home_selected_info","home_sat_context",
 "home_lock_badge","r76_mapping_label"
}

def _modify_geometry(el,placement,compact):
    y0=map(int,el.get("position","0,0").split(","))
    x,y=tuple(y0)
    w,h=map(int,el.get("size","0,0").split(","))
    # Header and remote strip stay untouched for consistent muscle memory.
    if placement=="right" and 115<=y<790:
        name=el.get("name") or ""
        sidebar=name in SIDEBAR_WIDGETS if el.tag=="widget" else x<410
        if sidebar:
            x=1211+round((x-40)*.91)
            w=round(w*.91)
        else:
            x=40+round((x-425)*.957)
            w=round(w*.957)
        # Clamp only where needed for right-side inner widgets.
        if x+w>1620:
            w=1620-x
    # Studio and Metro: raise KPI group slightly; utility bottom remains fixed.
    if compact and 535<=y<789 and x>=416 and placement=="left":
        y-=12
    el.set("position",f"{x},{y}")
    el.set("size",f"{w},{h}")

def make_theme(base,theme_id):
    cfg=THEMES[theme_id]
    root=ET.fromstring(base)
    root.set("backgroundColor",cfg["bg"])
    root.set("title","IPToSatPro • "+dict((b,a) for a,b in THEME_CHOICES)[theme_id])
    for el in root:
        name=el.get("name","")
        if el.tag=="eLabel":
            old=el.get("backgroundColor","").upper()
            if old in ("#8A343E","#257955","#A78129","#286B9A"):
                pass
            elif old in ("#111B26","#111D28"):
                el.set("backgroundColor",cfg["head"])
            elif old in ("#17222D","#1B2C3C"):
                el.set("backgroundColor",cfg["side"])
            elif old in ("#245781",):
                el.set("backgroundColor",cfg["highlight"])
            elif old in ("#182633",):
                el.set("backgroundColor",cfg["main"])
            elif old in ("#1B2D3D","#213549","#29445B","#1D503F"):
                el.set("backgroundColor",cfg["tile"])
            else:
                el.set("backgroundColor",cfg["accent"])
            # Colored metro metric tiles, not status badges.
            if theme_id=="metro" and old=="#1B2D3D":
                x=int(el.get("position").split(",")[0])
                el.set("backgroundColor",("#28578A","#256657","#824E72")[int((x-425)/391)%3])
        elif el.tag=="widget":
            if name not in KEY_COLORS:
                if name=="home_snr_bar":
                    el.set("foregroundColor",cfg["accent"])
                    el.set("backgroundColor",cfg["highlight"])
                elif name in ("home_status","r72_play_status","home_lock_badge"):
                    el.set("foregroundColor","#126B49" if theme_id=="executive" else "#8FE9B9")
                elif name in ("r72_sat_signal","r72_res_val","r72_speed_val"):
                    el.set("foregroundColor",cfg["accent"])
                elif name in ("r76_epg_label","r72_audio_lang_val"):
                    el.set("foregroundColor","#745212" if theme_id=="executive" else "#F0D391")
                elif name in ("subtitle","version","r72_sat_provider","r72_iptv_provider",
                              "r72_sat_position","r72_iptv_role","r72_iptv_foot",
                              "home_iptv_detail","home_sat_context","home_selected_info",
                              "home_menu_hint","r76_mapping_label","r76_catalog_label"):
                    el.set("foregroundColor",cfg["muted"])
                else:
                    el.set("foregroundColor",cfg["text"])
        _modify_geometry(el,cfg["placement"],theme_id in ("studio","metro"))
    return ET.tostring(root,encoding="unicode")

def generate_module():
    layout=base_layout()
    base=layout.make_home()
    fhd={};hd={}
    for tid in THEMES:
        skin=make_theme(base,tid)
        layout.validate_skin(skin,set(layout.HOME_WIDGETS))
        smaller=layout.scale_skin(skin,.75)
        layout.validate_skin(smaller,set(layout.HOME_WIDGETS),hd=True)
        fhd[tid]=skin;hd[tid]=smaller
    return (
      '# -*- coding: utf-8 -*-\n'
      '"""R76.7 native HD/FHD Enigma2 themes. Do not modify mappings."""\n'
      'THEME_CHOICES = '+repr(THEME_CHOICES)+'\n'
      'THEME_FHD = '+repr(fhd)+'\n'
      'THEME_HD = '+repr(hd)+'\n'
    ).encode("utf-8")

def replace_once(s,a,b,label):
    n=s.count(a)
    if n!=1:raise AssertionError("R767 "+label+" original anchor count "+str(n))
    return s.replace(a,b,1)

ROOT_MENU_OLD='''        entries = [
            ("Appearance  •  Home layout", "home_layout"),
            ("Settings  •  Essential", "quick"),
            ("Settings  •  Advanced / IPTV sources", "advanced"),
            ("Tools  •  Manual Mapping (All Sources)", "mapping"),
            ("Tools  •  Smart Match Test", "match_test"),
            ("Tools  •  Auto Scan", "auto_scan"),
            ("Tools  •  Player Lock", "player_lock"),
            ("Tools  •  System Diagnostics", "diagnostics"),
            ("Tools  •  Event Log", "logs"),
            ("Tools  •  Online Update", "update"),
        ]'''
ROOT_MENU_NEW='''        # R767: four TV-friendly groups; all prior tools still reachable.
        entries = [
            ("01  APPEARANCE  •  Home Themes (11)", "group_appearance"),
            ("02  SETTINGS  •  IPTV / Playback", "group_settings"),
            ("03  MATCHING  •  Preview / Mapping", "group_matching"),
            ("04  SYSTEM  •  Diagnostics / Update", "group_system"),
        ]'''

NEW_THEME_CHOICES='''            list=list(__import__(__package__+".home_themes_r767",
                                 fromlist=["THEME_CHOICES"]).THEME_CHOICES)'''
# Relative import avoid module path issues for top-level python script parsing.
# "__package__" at plugin import is its Enigma2 extension namespace.

def patch_plugin(src):
    if "R767_ELEVEN_HOME_THEMES" in src:return src
    choices=tuple(tid for label,tid in THEME_CHOICES)
    old='''        if _r76_layout not in ("metrix","classic","monitor"):
            _r76_layout = "metrix"
        if _r76_layout == "metrix":
            try:
                from enigma import getDesktop as _r76_get_desktop
                _r76_size = _r76_get_desktop(0).size()
                _r76_is_hd = _r76_size.width() < 1660 or _r76_size.height() < 900
                self.skin = _theme_skin(R76_METRIX_HD if _r76_is_hd else R76_METRIX_FHD)
            except Exception as _r76_err:
                _startup_log("R76_METRIX_FALLBACK", str(_r76_err)[:100])'''
    new='''        # R767_ELEVEN_HOME_THEMES: old preferences remain readable.
        if _r76_layout == "classic":
            _r76_layout = "neo_dark"
        elif _r76_layout == "monitor":
            _r76_layout = "studio"
        try:
            from .home_themes_r767 import THEME_FHD,THEME_HD
            if _r76_layout not in THEME_FHD:
                _r76_layout = "metrix"
            from enigma import getDesktop as _r76_get_desktop
            _r76_size = _r76_get_desktop(0).size()
            _r76_is_hd = _r76_size.width() < 1660 or _r76_size.height() < 900
            self.skin = _theme_skin(
                (THEME_HD if _r76_is_hd else THEME_FHD)[_r76_layout])
        except Exception as _r76_err:
            _startup_log("R767_THEME_FALLBACK", str(_r76_err)[:100])
            self.skin = _theme_skin(R76_METRIX_FHD)'''
    src=replace_once(src,old,new,"dashboard selection")
    # Header always reflects chosen theme; no stale 'R76.2 Metrix' on OLED/Matrix.
    src=replace_once(src,
        'self["subtitle"] = Label("METRIX OPENATV  •  SAT / IPTV  •  LIVE STATUS")',
        'self["subtitle"] = Label("SAT / IPTV  •  LIVE STATUS  •  HOME THEMES")',
        "dashboard subtitle")
    src=replace_once(src,
        'self["version"] = Label("R76.2  •  METRIX PROFESSIONAL")',
        'self["version"] = Label("R76.8  •  "+_r76_layout.replace("_"," ").upper())',
        "selected theme label")
    src=replace_once(src,ROOT_MENU_OLD,ROOT_MENU_NEW,"menu consolidation")
    src=replace_once(src,
        'title="IPToSat Pro  •  Settings / Tools", list=entries)',
        'title="IPToSat Pro  •  Menu", list=entries)',
        "menu title")
    old_box='''            title="Home layout • select then close and reopen IPToSat Pro",
            list=[
                ("Classic Neo Dark + Premium Icons (default)", "classic"),
                ("R72 Live Monitor + Premium Icons", "monitor"),
                ("Metrix OpenATV R76 (default)", "metrix"),
            ])'''
    new_box='''            title="HOME THEMES  •  11 choices  •  reopen plugin to apply",
            list=list(THEME_CHOICES))'''
    src=replace_once(src,old_box,new_box,"theme ChoiceBox")
    src=replace_once(src,
        '    def _r723_select_home_layout(self):\n        from Screens.ChoiceBox import ChoiceBox',
        '    def _r723_select_home_layout(self):\n        from Screens.ChoiceBox import ChoiceBox\n        from .home_themes_r767 import THEME_CHOICES',
        "theme import")
    src=replace_once(src,'if chosen not in ("classic","monitor","metrix"):',
        'if chosen not in '+repr(choices)+':',"theme validation")
    # Keep existing settings-and-mappings intact; theme preference is *only*
    # r76_home_layout, not the old r723 file.
    save_old='''            folder = os.path.dirname(self._r723_home_pref_path)
            if not os.path.isdir(folder):
                os.makedirs(folder)
            path = self._r723_home_pref_path
            tmp_path = path + ".tmp"
            with open(tmp_path,"w") as out:
                out.write(chosen+"\\n")
            os.rename(tmp_path,path)
            _r76_choice_tmp = self._r76_home_pref_path + ".tmp"
            with open(_r76_choice_tmp, "w") as _r76_writer:
                _r76_writer.write(chosen + "\\n")
            os.rename(_r76_choice_tmp, self._r76_home_pref_path)'''
    save_new='''            folder = os.path.dirname(self._r76_home_pref_path)
            if not os.path.isdir(folder):
                os.makedirs(folder)
            _r76_choice_tmp = self._r76_home_pref_path + ".tmp"
            with open(_r76_choice_tmp, "w") as _r76_writer:
                _r76_writer.write(chosen + "\\n")
            os.rename(_r76_choice_tmp, self._r76_home_pref_path)'''
    src=replace_once(src,save_old,save_new,"save only R76 theme")
    # Existing _r711_tools_choice stays as the only action dispatcher. Existing
    # callbacks and numeric / colored remote keys are not altered.
    src=replace_once(src,
        '        if selected in ("quick","advanced"):',
        '''        if selected.startswith("group_"):
            self._r767_open_group(selected)
            return
        if selected == "preview":
            self.open_preview_sources()
            return
        if selected in ("quick","advanced"):''',"group dispatcher")
    helper='''    def _r767_open_group(self, name):
        """Native Enigma2 ChoiceBox: no new buttons, settings or services."""
        from Screens.ChoiceBox import ChoiceBox
        groups={
          "group_appearance":(
             ("Select Home Theme  •  11 layouts", "home_layout"),
          ),
          "group_settings":(
             ("Essential settings", "quick"),
             ("Advanced / IPTV sources / Playback", "advanced"),
          ),
          "group_matching":(
             ("Preview Browser  •  candidates", "preview"),
             ("Manual Mapping  •  all sources", "mapping"),
             ("Auto Scan", "auto_scan"),
             ("Smart Match Test", "match_test"),
             ("Player Lock", "player_lock"),
          ),
          "group_system":(
             ("System Diagnostics", "diagnostics"),
             ("Event Logs", "logs"),
             ("Online Update", "update"),
          ),
        }
        if name=="group_appearance":
            self._r723_select_home_layout()
            return
        entries=list(groups.get(name,()))
        if not entries:
            return
        self.session.openWithCallback(
            self._r711_tools_choice, ChoiceBox,
            title="IPToSatPro  •  "+name.replace("group_","").upper(),
            list=entries)

'''
    src=replace_once(src,'    def _r711_tools_choice(self, item):',helper+'    def _r711_tools_choice(self, item):',"menu helper")
    compile(src,"plugin.py","exec")
    return src

if __name__=="__main__":
    x=generate_module()
    compile(x,"home_themes_r767.py","exec")
    print("R767_ALL_11_HD_FHD_VALID bytes",len(x))
