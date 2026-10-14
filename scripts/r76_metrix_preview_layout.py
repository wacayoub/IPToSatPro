#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76 Metrix OpenATV dashboard and Neo Dark Classic Preview+ B.

Native Enigma2 XML only; 1660x900 FHD and 1245x675 HD 16:9.
No network calls, new background threads, remote bindings, mapping writes,
key changes, changes to player/monitor/core or native bouquets.
Original OK playback handler preserved, without embedded preview widget.
"""
import ast
import xml.etree.ElementTree as ET

VERSION_TAG="R76_METRIX_HOME_PREVIEW_B"
HOME_SIZE=(1660,900)
PREVIEW_SIZE=(1660,900)
HOME_WIDGETS={
 # Header
 "title":(70,25,850,46,35,"#F6FAFF"),
 "subtitle":(72,70,940,28,19,"#C0D5E5"),
 "version":(1090,70,298,25,18,"#BDCFDD"),
 "home_status":(1410,31,174,43,21,"#82E6B9"),
 # Sidebar: navigation, real status, selected stream
 "home_channel_caption":(68,130,303,32,21,"#A3D8FF"),
 "home_preview_action":(69,184,304,44,24,"#FFFFFF"),
 "home_update_action":(69,250,304,42,23,"#FFFFFF"),
 "home_menu_hint":(69,312,309,35,19,"#BED1DF"),
 "r76_system_label":(69,360,308,35,19,"#8ECFFF"),
 "home_selected_head":(70,411,299,29,19,"#9FCEF1"),
 "home_selected_name":(69,455,302,55,23,"#FFFFFF"),
 "home_iptv_detail":(69,516,305,50,19,"#D0E3EF"),
 "home_selected_info":(69,575,304,63,18,"#C8DCE9"),
 "home_sat_context":(69,653,304,45,18,"#C8DCE9"),
 "home_lock_badge":(68,704,174,35,19,"#8DEAC1"),
 "r76_mapping_label":(69,746,303,29,18,"#B6DDF4"),
 # Top satellite panel; video details and EPG read from existing monitor
 "r72_sat_head":(454,131,705,28,20,"#9ACFFA"),
 "r72_sat_name":(454,167,745,44,33,"#FFFFFF"),
 "r72_sat_position":(455,218,746,29,21,"#DFE9F3"),
 "r72_sat_provider":(455,248,747,28,20,"#CADCE9"),
 "r72_sat_foot":(455,276,1078,25,18,"#B7CBDC"),
 "r76_epg_label":(455,301,1068,24,18,"#EAD197"),
 "r72_sat_signal_title":(1240,166,323,25,18,"#A7C7DB"),
 "home_snr_bar":(1239,218,262,18,0,"#278ED2"),
 "r72_sat_signal":(1509,207,79,44,28,"#78DDFA"),
 # Middle active IPTV status
 "r72_iptv_head":(454,346,475,29,20,"#9ACFFA"),
 "r72_iptv_name":(454,384,755,43,31,"#FFFFFF"),
 "r72_iptv_provider":(455,428,768,29,20,"#DAE7F2"),
 "r72_iptv_role":(455,456,773,29,19,"#C7DCE9"),
 "r72_iptv_foot":(455,485,737,24,18,"#AFCBDD"),
 "r76_catalog_label":(1224,482,360,26,18,"#A7D5EE"),
 "r72_mapping_status":(1230,348,161,36,20,"#F3F9FF"),
 "r72_play_status":(1406,348,176,36,20,"#8AF0C3"),
 # Six large metric tiles, 2 rows x 3
 "r72_res_head":(449,552,344,25,18,"#B0CFE4"),
 "r72_res_val":(450,587,342,42,27,"#78D7FF"),
 "r72_speed_head":(841,552,346,25,18,"#B0CFE4"),
 "r72_speed_val":(841,587,346,42,27,"#78D7FF"),
 "r72_audio_lang_head":(1232,552,340,25,18,"#B0CFE4"),
 "r72_audio_lang_val":(1232,587,338,42,25,"#F6D889"),
 "r72_audio_codec_head":(449,667,344,24,18,"#B0CFE4"),
 "r72_audio_codec_val":(450,704,344,42,25,"#E4EAF4"),
 "r72_video_codec_head":(841,667,346,24,18,"#B0CFE4"),
 "r72_video_codec_val":(841,704,346,42,25,"#E4EAF4"),
 "r72_source_head":(1232,667,340,24,18,"#B0CFE4"),
 "r72_source_val":(1232,704,340,42,25,"#E4EAF4"),
 # Existing Enigma2 remote labels; callbacks untouched
 "key_red":(49,818,365,45,22,"#FFFFFF"),
 "key_green":(431,818,364,45,22,"#FFFFFF"),
 "key_yellow":(809,818,368,45,22,"#FFFFFF"),
 "key_blue":(1191,818,422,45,22,"#FFFFFF"),
}
PREVIEW_WIDGETS={
 "title":(52,27,998,39,29,"#FFFFFF"),
 "focus_hint":(1057,33,535,31,19,"#27C7AC"),
 "sat_picon":(50,103,132,76,0,""),
 "picon_fallback":(50,107,132,70,16,"#819AAD"),
 "sat_current":(207,98,1359,36,24,"#F9D981"),
 "context_info":(207,140,1342,27,18,"#B0C4D4"),
 "epg":(207,170,1338,25,17,"#D5E9F5"),
 "status":(50,217,1120,27,18,"#55D9BA"),
 "subtitles":(1200,217,389,25,17,"#9DC9E6"),
 "left_head":(51,255,548,30,20,"#69E1C3"),
 "right_head":(655,255,928,30,20,"#89CFFF"),
 "sat_list":(50,296,535,456,19,"#ECF4F8"),
 "source_list":(653,296,927,456,18,"#ECF4F8"),
 "verify":(50,768,1530,24,17,"#A8BED0"),
 "detail":(50,795,1530,22,17,"#E7F1FA"),
 "key_red":(30,830,301,48,19,"#FFFFFF"),
 "key_green":(342,830,301,48,19,"#FFFFFF"),
 "key_yellow":(653,830,301,48,19,"#FFFFFF"),
 "key_blue":(966,830,301,48,19,"#FFFFFF"),
 "key_menu":(1279,830,351,48,19,"#FFFFFF"),
}
PREVIEW_CLASSIC_NAMES=set(PREVIEW_WIDGETS)


def add_rect(root,x,y,w,h,color,z="0",text=None):
    attrs={"position":"%d,%d"%(x,y),"size":"%d,%d"%(w,h),
           "zPosition":z,"backgroundColor":color}
    if text is not None:attrs["text"]=text
    ET.SubElement(root,"eLabel",attrs)


def make_home():
    root=ET.Element("screen",{"name":"SatIPTVBridgeDashboard","position":"center,center",
        "size":"1660,900","title":"IPToSatPro - Metrix OpenATV Professional",
        "backgroundColor":"#090E15","flags":"wfNoBorder"})
    # Native Enigma2 FHD layout with safe 40px side margins.
    add_rect(root,0,0,1660,106,"#111B26")
    add_rect(root,40,103,1580,3,"#2388D1","1")
    add_rect(root,40,116,360,670,"#17222D")
    add_rect(root,40,116,360,4,"#248ED7","1")
    # Sidebar action buttons, selected IPTV and diagnostic sections.
    for y in (179,244):
        add_rect(root,58,y,323,58,"#245781","1")
    add_rect(root,58,403,324,373,"#1B2C3C")
    # SAT service and the IPTV that is actually active are separate cards.
    add_rect(root,425,116,1195,210,"#182633")
    add_rect(root,425,116,1195,4,"#2388D1","1")
    add_rect(root,425,335,1195,183,"#182633")
    add_rect(root,425,335,1195,4,"#2388D1","1")
    add_rect(root,1218,151,382,105,"#213549")
    add_rect(root,1220,343,179,43,"#29445B")
    add_rect(root,1402,343,197,43,"#1D503F")
    # Six metrics; keep clear padding for text at TV viewing distance.
    for y in (536,653):
        for x in (425,816,1207):
            add_rect(root,x,y,382,110,"#1B2D3D")
            add_rect(root,x,y,382,4,"#356E9E","1")
    # Real remote key color strip.
    add_rect(root,40,798,1580,79,"#111D28")
    for x,w,c in ((40,377,"#8A343E"),(426,377,"#257955"),
                  (812,377,"#A78129"),(1198,421,"#286B9A")):
        add_rect(root,x,808,w,61,c,"1")
    for name,(x,y,w,h,size,color) in HOME_WIDGETS.items():
        attrs={"name":name,"position":f"{x},{y}","size":f"{w},{h}","zPosition":"3"}
        if name=="home_snr_bar":
            attrs.update({"foregroundColor":"#2388D1","backgroundColor":"#32495D"})
        else:
            attrs.update({"font":f"Regular;{size}","foregroundColor":color,
                          "transparent":"1"})
        if name in ("home_status","home_lock_badge",
                    "r72_mapping_status","r72_play_status",
                    "key_red","key_green","key_yellow","key_blue"):
            attrs["halign"]="center"
        ET.SubElement(root,"widget",attrs)
    return ET.tostring(root,encoding="unicode")


def make_preview():
    root=ET.Element("screen",{"name":"SatIPTVBridgePreview","position":"center,center",
      "size":"1660,900","title":"IPToSatPro R76 Neo Dark Classic Preview+ B",
      "flags":"wfNoBorder","backgroundColor":"#090F18"})
    add_rect(root,0,0,1660,6,"#27C7AC")
    add_rect(root,30,17,1600,61,"#111C29")
    add_rect(root,30,88,1600,118,"#101C29")
    add_rect(root,30,253,569,507,"#121F2D")
    add_rect(root,635,253,995,507,"#121F2D")
    add_rect(root,30,253,569,4,"#27C7AC","1")
    add_rect(root,635,253,995,4,"#347BA5","1")
    add_rect(root,43,97,144,91,"#192C3A")
    add_rect(root,39,762,1580,61,"#101C29")
    add_rect(root,30,827,1600,59,"#101C29")
    for x,w,c in ((30,301,"#8A343E"),(342,301,"#257955"),
                   (653,301,"#A78129"),(966,301,"#286B9A"),(1279,351,"#473E69")):
        add_rect(root,x,830,w,48,c,"1")
    for name,(x,y,w,h,size,color) in PREVIEW_WIDGETS.items():
        attrs={"name":name,"position":f"{x},{y}","size":f"{w},{h}","zPosition":"3"}
        if name in ("sat_list","source_list"):
            attrs.update({"font":f"Regular;{size}","foregroundColor":color,
                "backgroundColor":"#121F2D","scrollbarMode":"showOnDemand",
                "itemHeight":"36" if name=="source_list" else "42"})
        elif name=="sat_picon":
            attrs.update({"alphatest":"on","scale":"1"})
        else:
            attrs.update({"font":f"Regular;{size}","foregroundColor":color,"transparent":"1"})
            if name in ("key_red","key_green","key_yellow","key_blue","key_menu"):
                attrs["halign"]="center";attrs["valign"]="center"
        ET.SubElement(root,"widget",attrs)
    return ET.tostring(root,encoding="unicode")


def scale_skin(xml,factor):
    root=ET.fromstring(xml)
    ow,oh=map(int,root.get("size").split(","))
    nw,nh=round(ow*factor),round(oh*factor)
    root.set("size",f"{nw},{nh}")
    for el in root:
        for attr in ("position","size"):
            if attr in el.attrib:
                a,b=map(int,el.get(attr).split(","))
                el.set(attr,f"{round(a*factor)},{round(b*factor)}")
        font=el.get("font")
        if font and ";" in font:
            family,sz=font.rsplit(";",1)
            el.set("font",f"{family};{max(13,round(int(sz)*factor))}")
        if el.get("itemHeight"):
            el.set("itemHeight",str(max(29,round(int(el.get("itemHeight"))*factor))))
    return ET.tostring(root,encoding="unicode")


def validate_skin(xml,expected,hd=False):
    root=ET.fromstring(xml)
    width,height=map(int,root.get("size").split(","))
    assert (width,height)==((1245,675) if hd else (1660,900))
    assert width<= (1280 if hd else 1920) and height<= (720 if hd else 1080)
    assert width/height>=1.75 and width/height<=1.9
    names=[]
    for el in root:
        if el.tag not in ("widget","eLabel"):raise ValueError("Unknown Enigma2 element")
        x,y=map(int,el.get("position").split(","))
        w,h=map(int,el.get("size").split(","))
        assert x>=0 and y>=0 and w>0 and h>0 and x+w<=width and y+h<=height,(el.tag,el.get("name"))
        if el.tag=="widget":names.append(el.get("name"))
    assert len(names)==len(expected) and set(names)==expected,sorted(set(names)^expected)
    assert len(names)==len(set(names))
    return root


def replace_once(s,old,new):
    c=s.count(old)
    if c!=1:raise AssertionError("R76 source anchor drift "+str(c)+" "+repr(old[:90]))
    return s.replace(old,new,1)


def patch_plugin(src):
    if VERSION_TAG in src:raise ValueError("R76 already applied")
    home=make_home()
    preview=make_preview()
    validate_skin(home,set(HOME_WIDGETS))
    validate_skin(preview,set(PREVIEW_WIDGETS))
    home_hd=scale_skin(home,.75)
    preview_hd=scale_skin(preview,.75)
    validate_skin(home_hd,set(HOME_WIDGETS),hd=True)
    validate_skin(preview_hd,set(PREVIEW_WIDGETS),hd=True)
    constants=f'''# {VERSION_TAG}: native HD/FHD no-network skins
R76_METRIX_FHD = """{home}"""
R76_METRIX_HD = """{home_hd}"""

'''
    src=replace_once(src,'SETTINGS_FHD = """',constants+'SETTINGS_FHD = """')
    # The Metrix skin is the R76 default, but the existing MENU Appearance
    # choice remains functional. Persist R76 preference separately: no edits
    # to previous R723 preference files unless a user explicitly selects a mode.
    src=replace_once(src,'("R72 Live Monitor + Premium Icons", "monitor"),',
        '("R72 Live Monitor + Premium Icons", "monitor"),\n'
        '                ("Metrix OpenATV R76 (default)", "metrix"),')
    src=replace_once(src,'if chosen not in ("classic","monitor"):',
        'if chosen not in ("classic","monitor","metrix"):')
    # Existing save method writes the previous preference as before, and only
    # explicit Appearance selection creates the new R76 choice file.
    src=replace_once(src,
        '            os.rename(tmp_path,path)\n            self.session.open(',
        '''            os.rename(tmp_path,path)
            _r76_choice_tmp = self._r76_home_pref_path + ".tmp"
            with open(_r76_choice_tmp, "w") as _r76_writer:
                _r76_writer.write(chosen + "\\n")
            os.rename(_r76_choice_tmp, self._r76_home_pref_path)
            self.session.open(''')
    anchor='os.path.join(os.path.dirname(__file__), "images", "r723-classic-premium.png")))'
    inject='''
        # R76: read-only skin selection; Metrix is the default for this version.
        self._r76_home_pref_path = "/etc/enigma2/SatIPTVBridge/r76_home_layout"
        try:
            with open(self._r76_home_pref_path,"r") as _r76_reader:
                _r76_layout = _r76_reader.read(32).strip()
        except Exception:
            _r76_layout = "metrix"
        if _r76_layout not in ("metrix","classic","monitor"):
            _r76_layout = "metrix"
        if _r76_layout == "metrix":
            try:
                from enigma import getDesktop as _r76_get_desktop
                _r76_size = _r76_get_desktop(0).size()
                _r76_is_hd = _r76_size.width() < 1660 or _r76_size.height() < 900
                self.skin = _theme_skin(R76_METRIX_HD if _r76_is_hd else R76_METRIX_FHD)
            except Exception as _r76_err:
                _startup_log("R76_METRIX_FALLBACK", str(_r76_err)[:100])
'''
    src=replace_once(src,anchor,anchor+inject)
    # Extra diagnostics are strictly read-only and throttle local reads to 12s,
    # using the dashboard's existing 2.5s timer (no new timers or network).
    # Values unavailable on a given receiver are explicitly marked N/A.
    src=replace_once(src,
        '        self["home_status"] = Label("STARTING")',
        '''        self["r76_system_label"] = Label("CPU N/A · RAM N/A")
        self["r76_mapping_label"] = Label("Mappings N/A")
        self["r76_epg_label"] = Label("EPG N/A")
        self["r76_catalog_label"] = Label("Catalog N/A")
        self._r76_extras_last = 0.0
        self._r76_cpu_sample = None
        self._r76_extras = {"system":"CPU N/A · RAM N/A",
            "mapping":"Mappings N/A","epg":"EPG N/A","catalog":"Catalog N/A"}
        self["home_status"] = Label("STARTING")''')
    anchor='''        self["log_preview"].setText(self._bridge_suggestion(snap, decision))
'''
    diag='''        # R76 read-only diagnostics: local /proc + current EPG cache + maps.
        # No stream probes, catalog downloads, decoder restarts or mapping edits.
        _r76_now = time.monotonic()
        if _r76_now - self._r76_extras_last >= 12.0:
            self._r76_extras_last = _r76_now
            _r76_cpu = "N/A"
            _r76_ram = "N/A"
            try:
                with open("/proc/stat","r") as _r76_proc:
                    _r76_parts = [int(p) for p in _r76_proc.readline().split()[1:9]]
                _r76_total = sum(_r76_parts)
                _r76_idle = _r76_parts[3] + _r76_parts[4]
                if self._r76_cpu_sample is not None:
                    _r76_dt = _r76_total - self._r76_cpu_sample[0]
                    _r76_di = _r76_idle - self._r76_cpu_sample[1]
                    if _r76_dt > 0:
                        _r76_cpu = "%.0f%%" % max(0.0,min(100.0,
                            100.0*(1.0-_r76_di/float(_r76_dt))))
                self._r76_cpu_sample = (_r76_total,_r76_idle)
            except Exception:
                pass
            try:
                with open("/proc/meminfo","r") as _r76_proc:
                    _r76_mem = {}
                    for _r76_line in _r76_proc:
                        _r76_pair = _r76_line.split(":")
                        if len(_r76_pair)==2 and _r76_pair[0] in ("MemTotal","MemAvailable"):
                            _r76_mem[_r76_pair[0]] = int(_r76_pair[1].strip().split()[0])
                _r76_mt = _r76_mem.get("MemTotal",0)
                _r76_ma = _r76_mem.get("MemAvailable",0)
                if _r76_mt>0 and 0<=_r76_ma<=_r76_mt:
                    _r76_ram = "%.0f%%" % (100.0*(1.0-_r76_ma/float(_r76_mt)))
            except Exception:
                pass
            self._r76_extras["system"] = "CPU %s · RAM %s" % (_r76_cpu,_r76_ram)
            try:
                _r76_maps = _load_overrides()
                _r76_valid = sum(1 for _r76_map in _r76_maps.values()
                    if isinstance(_r76_map,dict) and _r76_map.get("channel_id")
                    and not _r76_map.get("user_unmapped"))
                self._r76_extras["mapping"] = "Saved mappings: %d" % _r76_valid
            except Exception:
                self._r76_extras["mapping"] = "Saved mappings N/A"
            try:
                _r76_service = self.session.nav.getCurrentService()
                _r76_info = _r76_service.info() if _r76_service else None
                _r76_event = _r76_info.getEvent(0) if _r76_info else None
                _r76_title = str(_r76_event.getEventName() or "") if _r76_event else ""
                self._r76_extras["epg"] = "EPG: " + (_r76_title[:84] if _r76_title else "not available")
            except Exception:
                self._r76_extras["epg"] = "EPG not available"
            try:
                self._r76_extras["catalog"] = "IPTV catalog: %d" % int(count)
            except Exception:
                self._r76_extras["catalog"] = "IPTV catalog N/A"
        self["r76_system_label"].setText(self._r76_extras["system"])
        self["r76_mapping_label"].setText(self._r76_extras["mapping"])
        self["r76_epg_label"].setText(self._r76_extras["epg"])
        self["r76_catalog_label"].setText(self._r76_extras["catalog"])
'''
    src=replace_once(src,anchor,anchor+diag)
    # Correct legacy sidebar heading: its first section contains actions, not current SAT.
    src=replace_once(src,
        'self["home_channel_caption"] = Label("CURRENT CHANNEL")',
        'self["home_channel_caption"] = Label("QUICK ACTIONS")')
    # Replace outdated R72 on-screen product labels only (not actual signal data).
    src=replace_once(src,
        'self["subtitle"] = Label("R72  •  SATELLITE → IPTV  •  LIVE MONITOR")',
        'self["subtitle"] = Label("METRIX OPENATV  •  SAT / IPTV  •  LIVE STATUS")')
    src=replace_once(src,
        'self["version"] = Label("R72.3  •  CLASSIC / MONITOR")',
        'self["version"] = Label("R76.2  •  METRIX PROFESSIONAL")')
    # Reuse all displayed R72 monitor fields: no fake values, no new polling.
    # Enigma2 requires every widget name to be initialized in screen.__init__.
    tree=ast.parse(src)
    dash=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=="SatIPTVBridgeDashboard")
    init=next(n for n in dash.body if isinstance(n,ast.FunctionDef) and n.name=="__init__")
    assigned={n.slice.value for n in ast.walk(init) if isinstance(n,ast.Subscript)
             and isinstance(n.value,ast.Name) and n.value.id=="self"
             and isinstance(n.slice,ast.Constant) and isinstance(n.slice.value,str)}
    missing=set(HOME_WIDGETS)-assigned
    if missing:raise AssertionError("Dashboard widgets missing: "+repr(sorted(missing)))
    compile(src,"plugin.py","exec")
    return src


def theme_module():
    h=make_preview(); hd=scale_skin(h,.75)
    validate_skin(h,set(PREVIEW_WIDGETS));validate_skin(hd,set(PREVIEW_WIDGETS),hd=True)
    return ('''# -*- coding: utf-8 -*-
"""R76 Neo Dark Classic two-list SAT/IPTV browser, native HD/FHD.
No embedded video widget; existing OK and GREEN actions unchanged.
"""
PREVIEW_R74_FHD = """'''+h+'''"""
PREVIEW_R76_HD = """'''+hd+'''"""
''').encode()


def patch_preview_plugin(src):
    old='''            from .preview_theme_r74 import PREVIEW_R74_FHD
            self.skin = _theme_skin(PREVIEW_R74_FHD)'''
    new='''            from .preview_theme_r74 import PREVIEW_R74_FHD, PREVIEW_R76_HD
            try:
                from enigma import getDesktop as _r76_desktop
                _r76_screen = _r76_desktop(0).size()
                _r76_small = _r76_screen.width() < 1660 or _r76_screen.height() < 900
                self.skin = _theme_skin(PREVIEW_R76_HD if _r76_small else PREVIEW_R74_FHD)
            except Exception:
                self.skin = _theme_skin(PREVIEW_R76_HD)'''
    src=replace_once(src,old,new)
    # The stock Preview still owns OK fullscreen tests and GREEN manual lock.
    src=replace_once(src,
        'self["title"] = Label("PREVIEW BROWSER PRO  |  NEO DARK R74")',
        'self["title"] = Label("PREVIEW BROWSER PRO  |  NEO DARK CLASSIC")')
    # Keep initial focus, SAT navigation, all color buttons, existing OK logic.
    # Do not touch play_match, fast zap, stream watchdog or overrides.
    compile(src,"plugin.py","exec")
    return src


if __name__=="__main__":
    for src,names in ((make_home(),set(HOME_WIDGETS)),
                      (make_preview(),set(PREVIEW_WIDGETS))):
        validate_skin(src,names);validate_skin(scale_skin(src,.75),names,hd=True)
    print("R76_NATIVE_LAYOUTS_STATIC_OK")
