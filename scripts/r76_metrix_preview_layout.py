#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76 Metrix OpenATV dashboard and Neo Dark Classic Preview+ B.

Native Enigma2 XML only; 1660x900 FHD and 1245x675 HD 16:9.
No network calls, new background threads, remote bindings, mapping writes,
key changes, changes to player/monitor/core or native bouquets.
Playback triggered ONLY by the existing OK handler, not by list navigation.
"""
import ast
import xml.etree.ElementTree as ET

VERSION_TAG="R76_METRIX_HOME_PREVIEW_B"
HOME_SIZE=(1660,900)
PREVIEW_SIZE=(1660,900)
HOME_WIDGETS={
 # header
 "title":(66,28,805,42,33,"#F7FBFF"),
 "subtitle":(66,73,1100,24,17,"#AFC9DB"),
 "version":(1120,68,250,26,17,"#B5CBDD"),
 "home_status":(1422,36,174,40,20,"#8BE9C6"),
 # sidebar: read-only labels, real remote actions preserved
 "home_channel_caption":(64,123,305,30,19,"#83BEEA"),
 "home_preview_action":(62,184,308,42,24,"#FFFFFF"),
 "home_update_action":(62,252,308,40,23,"#F9DB90"),
 "home_menu_hint":(64,317,305,32,18,"#BACCDD"),
 "home_selected_head":(66,409,305,27,19,"#83BEEA"),
 "home_selected_name":(66,448,304,47,21,"#F7FBFF"),
 "home_iptv_detail":(66,509,302,52,17,"#B7D1E4"),
 "home_selected_info":(66,575,302,46,16,"#B7D1E4"),
 "home_sat_context":(66,656,303,45,17,"#B7D1E4"),
 "home_lock_badge":(64,726,180,35,18,"#84E5BC"),
 # SAT panel
 "r72_sat_head":(442,123,470,27,20,"#82BDE8"),
 "r72_sat_name":(442,162,740,43,32,"#FFFFFF"),
 "r72_sat_position":(442,213,735,30,20,"#C9D8E5"),
 "r72_sat_provider":(442,253,730,31,19,"#D8E7F2"),
 "r72_sat_foot":(442,302,800,28,17,"#B7CCDA"),
 "r72_sat_signal_title":(1260,162,322,23,17,"#B6CBDD"),
 "home_snr_bar":(1258,228,257,18,0,"#1786CE"),
 "r72_sat_signal":(1519,211,72,42,26,"#75D5FF"),
 # IPTV panel
 "r72_iptv_head":(442,389,400,28,20,"#82BDE8"),
 "r72_iptv_name":(442,427,690,42,29,"#FFFFFF"),
 "r72_iptv_provider":(442,476,740,24,19,"#CDDDEA"),
 "r72_iptv_role":(442,511,745,26,19,"#AFD0E1"),
 "r72_iptv_foot":(442,554,1100,24,17,"#B6C8D9"),
 "r72_mapping_status":(1230,395,168,37,19,"#FFFFFF"),
 "r72_play_status":(1410,395,174,37,19,"#8DEAC1"),
 # dense KPI 3 x 2, only real existing R72 data
 "r72_res_head":(440,619,340,24,17,"#A5C3D9"),
 "r72_res_val":(440,647,344,36,24,"#79C9FA"),
 "r72_speed_head":(835,619,345,24,17,"#A5C3D9"),
 "r72_speed_val":(835,647,344,36,24,"#79C9FA"),
 "r72_audio_lang_head":(1240,619,325,24,17,"#A5C3D9"),
 "r72_audio_lang_val":(1240,647,325,36,22,"#EDCC7D"),
 "r72_audio_codec_head":(440,708,340,23,17,"#A5C3D9"),
 "r72_audio_codec_val":(440,737,340,34,22,"#D8E4F1"),
 "r72_video_codec_head":(835,708,340,23,17,"#A5C3D9"),
 "r72_video_codec_val":(835,737,340,34,22,"#D8E4F1"),
 "r72_source_head":(1240,708,325,23,17,"#A5C3D9"),
 "r72_source_val":(1240,737,325,34,22,"#D8E4F1"),
 # existing buttons (all key bindings are left alone)
 "key_red":(45,814,368,46,21,"#FFFFFF"),
 "key_green":(428,814,367,46,21,"#FFFFFF"),
 "key_yellow":(807,814,367,46,21,"#FFFFFF"),
 "key_blue":(1188,814,427,46,21,"#FFFFFF"),
}
PREVIEW_WIDGETS={
 "title":(52,27,998,39,29,"#FFFFFF"),
 "focus_hint":(1057,33,535,31,19,"#27C7AC"),
 "sat_picon":(50,103,132,76,0,""),
 "picon_fallback":(50,107,132,70,16,"#819AAD"),
 "sat_current":(207,98,1359,36,24,"#F9D981"),
 "context_info":(207,140,1342,27,18,"#B0C4D4"),
 "epg":(207,170,1338,25,17,"#D5E9F5"),
 "status":(50,217,1457,27,18,"#55D9BA"),
 "subtitles":(1200,217,389,25,17,"#9DC9E6"),
 "left_head":(51,255,548,30,20,"#69E1C3"),
 "right_head":(655,255,928,30,20,"#89CFFF"),
 "sat_list":(50,296,535,456,19,"#ECF4F8"),
 "source_list":(653,641,927,111,18,"#ECF4F8"),
 "verify":(50,768,1530,24,17,"#A8BED0"),
 "detail":(50,795,1530,22,17,"#E7F1FA"),
 "key_red":(30,830,301,48,19,"#FFFFFF"),
 "key_green":(342,830,301,48,19,"#FFFFFF"),
 "key_yellow":(653,830,301,48,19,"#FFFFFF"),
 "key_blue":(966,830,301,48,19,"#FFFFFF"),
 "key_menu":(1279,830,351,48,19,"#FFFFFF"),
 "r76_video":(814,292,650,365,0,""),
}
PREVIEW_CLASSIC_NAMES=set(PREVIEW_WIDGETS)-{"r76_video"}


def add_rect(root,x,y,w,h,color,z="0",text=None):
    attrs={"position":"%d,%d"%(x,y),"size":"%d,%d"%(w,h),
           "zPosition":z,"backgroundColor":color}
    if text is not None:attrs["text"]=text
    ET.SubElement(root,"eLabel",attrs)


def make_home():
    root=ET.Element("screen",{"name":"SatIPTVBridgeDashboard","position":"center,center",
        "size":"1660,900","title":"IPToSatPro R76 - Metrix OpenATV",
        "backgroundColor":"#090D12","flags":"wfNoBorder"})
    add_rect(root,0,0,1660,99,"#101820")
    add_rect(root,38,98,1583,4,"#177EC7","1")
    add_rect(root,40,110,345,673,"#141A20")
    add_rect(root,40,110,345,5,"#197FC2","1")
    for y in (171,238):
        add_rect(root,56,y,315,60,"#1D3549")
    add_rect(root,56,388,315,350,"#1C252D")
    add_rect(root,416,110,1204,250,"#151E26")
    add_rect(root,416,110,1204,5,"#147DBE","1")
    add_rect(root,416,372,1204,219,"#151E26")
    add_rect(root,416,372,1204,5,"#1786CE","1")
    # 6 metric panels. Less than 36% of screen devoted to decoration.
    for y in (608,699):
        for x in (416,817,1218):
            add_rect(root,x,y,392,85,"#1B2732")
            add_rect(root,x,y,392,3,"#315D81","1")
    add_rect(root,40,801,1580,75,"#111A23")
    for x,w,c in ((40,377,"#8A343E"),(426,377,"#257955"),
                  (812,377,"#A78129"),(1198,421,"#286B9A")):
        add_rect(root,x,809,w,59,c,"1")
    for name,(x,y,w,h,size,color) in HOME_WIDGETS.items():
        attrs={"name":name,"position":f"{x},{y}","size":f"{w},{h}","zPosition":"3"}
        if name=="home_snr_bar":
            attrs.update({"foregroundColor":"#1786CE","backgroundColor":"#314354"})
        else:
            attrs.update({"font":f"Regular;{size}","foregroundColor":color,"transparent":"1"})
        if name in ("home_status","home_lock_badge","key_red","key_green","key_yellow","key_blue"):
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
    add_rect(root,804,282,670,386,"#060B13","1")
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
        elif name=="r76_video":
            attrs["zPosition"]="2"
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
    # The existing R723 classic/monitor preference, settings and key binds remain.
    # Only override active screen skin in-memory; never rewrite user settings.
    anchor='os.path.join(os.path.dirname(__file__), "images", "r723-classic-premium.png")))'
    inject='''
        # R76 default Metrix style; desktop bounds, not television diagonal.
        # A safe fallback retains the existing R723 skin if desktop probing fails.
        try:
            from enigma import getDesktop as _r76_get_desktop
            _r76_size = _r76_get_desktop(0).size()
            _r76_is_hd = _r76_size.width() < 1660 or _r76_size.height() < 900
            self.skin = _theme_skin(R76_METRIX_HD if _r76_is_hd else R76_METRIX_FHD)
        except Exception as _r76_err:
            _startup_log("R76_METRIX_FALLBACK", str(_r76_err)[:100])
'''
    src=replace_once(src,anchor,anchor+inject)
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
"""R76 Neo Dark Classic Preview+ B, native HD/FHD VideoWindow.
Only visual layout; OK retains R74.13 player trigger and GREEN manual lock.
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
    needle='''        self["title"] = Label("PREVIEW BROWSER PRO  |  NEO DARK R74")'''
    addition='''        # R76: single existing decoder, not a second PiP decoder.
        # Main player still starts exclusively on OK; never on cursor movement.
        try:
            from Components.VideoWindow import VideoWindow
            self["r76_video"] = VideoWindow(decoder=0, fb_width=1280, fb_height=720)
            self.onLayoutFinish.append(lambda: self["r76_video"].hide())
        except Exception:
            self["r76_video"] = Label("Video window unavailable")
'''
    src=replace_once(src,needle,addition+needle)
    needle='''    def _r7413_keep_preview_visible(self):'''
    src=replace_once(src,needle,needle+'''
        # R76: reveal video widget only after existing OK player request.
        try: self["r76_video"].show()
        except Exception: pass
''')
    # Keep initial focus, SAT navigation, all color buttons, existing OK logic.
    # Do not touch play_match, fast zap, stream watchdog or overrides.
    compile(src,"plugin.py","exec")
    return src


if __name__=="__main__":
    for src,names in ((make_home(),set(HOME_WIDGETS)),
                      (make_preview(),set(PREVIEW_WIDGETS))):
        validate_skin(src,names);validate_skin(scale_skin(src,.75),names,hd=True)
    print("R76_NATIVE_LAYOUTS_STATIC_OK")
