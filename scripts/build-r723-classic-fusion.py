#!/usr/bin/env python3
"""R72.3 Neo Classic Fusion: restore proven R71.1 Home with R72 icons/data.

Classic Neo Home is the DEFAULT. Current R72.2 Live Monitor remains available
under MENU -> Appearance -> Home layout; saving selection requires reopening
plugin. No changes to player, sources, timing, matching, timeshift or mappings.
"""
import ast,base64,hashlib,importlib.util,io,json,sys,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/path)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
    return obj
r722=load("r722_base","build-r722-tv-polish.py")
r711=load("r711_legacy","build-r711-cleanup-beta.py")
pack=r722.archive
P=r722.P;PLUGIN=r722.PLUGIN;UPDATER=r722.UPDATER
OLD="1.0.46-r72.2-tv-polish-beta"
NEW="1.0.46-r72.3-classic-premium-beta"
B64=ROOT/"payload/r722-tv-polish.b64"
SIZE=359174
PIN="fdfa391b6ead34b27977be9e9592b60be7a50247bbe45a2a2645e3a5488bdfb1"
ICON=P+"images/r723-classic-premium.png"
CHANGELOG=P+"CHANGELOG-R723-CLASSIC-PREMIUM.txt"

def replace_one(s,a,b):
    assert s.count(a)==1,("Expected one anchor",repr(a[:125]),s.count(a))
    return s.replace(a,b,1)

def classic_skin():
    xml=r711.source_skin()
    root=ET.fromstring(xml)
    nodes={w.get("name"):w for w in root if w.tag=="widget"}
    # Original R71.1 spatial organization restored: hero SAT headline, small
    # SAT/ IPTV statuses, Selected IPTV section, two large actions.
    for name,x,y,w,h,sz in [
      ("home_channel_caption",137,164,1295,26,20),
      ("home_snr_head",144,351,524,29,20),
      ("home_iptv_head",929,350,576,28,20),
      ("home_selected_head",149,501,700,35,20),
      ("home_sat_name",76,213,1470,54,39),
      ("home_selected_name",76,550,1460,58,30),
      ("home_snr_value",665,397,114,45,27),
      ("home_iptv_status",902,385,620,39,28),
      ("home_iptv_detail",863,430,724,28,19),
      ("home_selected_info",76,663,1500,31,18),
      ("home_preview_action",213,754,450,41,28),
      ("home_update_action",1010,754,445,41,28),
      ("home_preview_hint",215,791,447,22,17),
      ("home_update_hint",1010,791,447,22,17),
      ("home_quality_chip",107,625,83,34,18),
      ("home_audio_chip",241,625,165,34,18),
      ("home_role_chip",462,625,130,34,18),
      ("home_speed_chip",656,625,123,34,18),
    ]:
        node=nodes[name]
        node.set("position",f"{x},{y}");node.set("size",f"{w},{h}")
        node.set("font",f"Regular;{sz}")
    for key in ("home_quality_chip","home_audio_chip","home_role_chip","home_speed_chip"):
        nodes[key].set("halign","center")
    nodes["home_snr_bar"].set("foregroundColor","#49D6B1")
    nodes["version"].set("position","1115,80");nodes["version"].set("font","Regular;16")
    nodes["home_menu_hint"].set("font","Regular;19")
    for elem in root:
        if elem.tag=="ePixmap":
            assert elem.get("pixmap")=="__IPTOSAT_NEO_CLEANUP_BG__"
            elem.set("pixmap","__IPTOSAT_R723_CLASSIC_BG__")
            elem.set("alphatest","blend")
    new=ET.tostring(root,encoding="unicode")
    names=set()
    for element in ET.fromstring(new):
        if element.tag in ("widget","ePixmap"):
            x,y=map(int,element.get("position").split(","))
            w,h=map(int,element.get("size").split(","))
            assert 0<=x and 0<=y and w>0 and h>0 and x+w<=1660 and y+h<=900,(element.tag,element.attrib)
        if element.tag=="widget":
            assert element.get("name") not in names
            names.add(element.get("name"))
    return new

def premium_background():
    from PIL import Image,ImageDraw
    original=Image.open(io.BytesIO(r711.background())).convert("RGBA")
    k=3
    img=original.resize((1660*k,900*k),Image.Resampling.NEAREST)
    d=ImageDraw.Draw(img)
    def s(a):return int(a*k)
    def poly(points,color):
        d.polygon([(s(x),s(y)) for x,y in points],fill=color)
    def line(points,color,width=3):
        d.line([(s(x),s(y)) for x,y in points],fill=color,width=s(width),joint="curve")
    def box(x,y,w,h,color,r=0,outline=None,width=2):
        d.rounded_rectangle((s(x),s(y),s(x+w),s(y+h)),radius=s(r),fill=color,
                            outline=outline,width=s(width))
    def ellipse(x,y,r,color=None,outline=None,width=2):
        d.ellipse((s(x-r),s(y-r),s(x+r),s(y+r)),fill=color,outline=outline,width=s(width))
    def arc(x,y,w,h,a,z,color,width=3):
        d.arc((s(x),s(y),s(x+w),s(y+h)),a,z,fill=color,width=s(width))
    CYAN="#A3D9FF";GREEN="#62E7BB";GOLD="#EDCB7E";PALE="#D5E8F8"
    # Crystal line-icon satellite with small stand, big readable on TV.
    box(77,159,45,43,"#294561",10)
    arc(84,166,30,27,20,145,CYAN,3)
    line([(89,188),(111,168)],CYAN,2)
    line([(91,190),(97,198),(112,198)],CYAN,3)
    ellipse(111,166,3,CYAN)
    # SAT signal meter pictogram; original R71.1 label shifts to the right.
    box(80,343,47,43,"#27445B",10)
    box(90,355,27,17,None,4,CYAN,2)
    line([(103,371),(103,377)],CYAN,2)
    line([(96,378),(111,378)],CYAN,2)
    # IPTV wireless-play icon.
    box(860,343,50,43,"#245746",10)
    box(871,356,27,22,None,5,GREEN,2)
    poly([(882,361),(882,372),(892,366)],GREEN)
    arc(876,347,18,12,195,340,GREEN,2)
    # Selected-stream icon inside hero card.
    box(77,499,52,43,"#2D5360",12)
    box(88,510,29,19,None,4,GREEN,2)
    poly([(99,514),(99,525),(110,520)],GREEN)
    # Four premium resolution/audio/source/speed icons within info chips.
    for x in (78,215,438,628):
        box(x,629,27,27,"#344D68",6)
    box(84,636,15,10,None,2,GREEN,2)
    line([(91,646),(91,650)],GREEN,2)
    line([(86,651),(96,651)],GREEN,2)
    poly([(220,637),(226,637),(232,631),(232,651),(226,646),(220,646)],GOLD)
    arc(224,635,17,15,310,56,GOLD,2)
    ellipse(451,642,4,None,PALE,2)
    ellipse(443,650,3,None,PALE,2)
    ellipse(460,650,3,None,PALE,2)
    line([(451,645),(444,648)],PALE,2)
    line([(452,645),(459,648)],PALE,2)
    ellipse(640,642,9,None,GREEN,2)
    line([(640,642),(646,638)],GREEN,2)
    line([(638,629),(644,629)],GREEN,2)
    # Refresh/Preview graphic in footer: upgrade current R71.1 static icons.
    # Leave existing small icon art untouched for smooth visual compatibility.
    # The anti-aliased icon overlay adds light accents only.
    out=io.BytesIO()
    img=img.resize((1660,900),Image.Resampling.LANCZOS)
    img.save(out,format="PNG",optimize=True)
    data=out.getvalue()
    assert data.startswith(b"\x89PNG\r\n\x1a\n") and len(data)<260000
    return data

def patch_plugin(raw):
    src=raw.decode()
    start='DASHBOARD_FHD = """\n'
    end='\n"""\n\nSETTINGS_FHD = """'
    assert src.count(start)==src.count(end)==1
    before,rest=src.split(start,1)
    modern,after=rest.split(end,1)
    # Keep unchanged fully working modern R72.2 GUI as optional layout.
    classic=classic_skin()
    src=before+start+modern+'''\\n"""\\n\\nR723_CLASSIC_FHD = """\\n'''.replace("\\n","\n")+classic+end+after
    old_init='''        self.skin = _theme_skin(DASHBOARD_FHD.replace(
            "__IPTOSAT_R721_BG__",
            os.path.join(os.path.dirname(__file__), "images", "r721-premium-icons.png")))'''
    new_init='''        self._r723_home_pref_path = "/etc/enigma2/SatIPTVBridge/r723_home_layout"
        try:
            with open(self._r723_home_pref_path, "r") as reader:
                self._r723_layout = reader.read(32).strip()
        except Exception:
            self._r723_layout = "classic"
        if self._r723_layout not in ("classic","monitor"):
            self._r723_layout = "classic"
        if self._r723_layout == "monitor":
            self.skin = _theme_skin(DASHBOARD_FHD.replace(
                "__IPTOSAT_R721_BG__",
                os.path.join(os.path.dirname(__file__), "images", "r721-premium-icons.png")))
        else:
            self.skin = _theme_skin(R723_CLASSIC_FHD.replace(
                "__IPTOSAT_R723_CLASSIC_BG__",
                os.path.join(os.path.dirname(__file__), "images", "r723-classic-premium.png")))'''
    src=replace_one(src,old_init,new_init)
    src=replace_one(src,'self["version"] = Label("R72.2 BETA")','self["version"] = Label("R72.3  •  CLASSIC / MONITOR")')
    src=replace_one(src,'''            ("Settings  •  Essential", "quick"),''',
                         '''            ("Appearance  •  Home layout", "home_layout"),
            ("Settings  •  Essential", "quick"),''')
    src=replace_one(src,'''        elif selected=="mapping":
            self.open_all_sources()''',
        '''        elif selected=="home_layout":
            self._r723_select_home_layout()
        elif selected=="mapping":
            self.open_all_sources()''')
    # Open a native two-option ChoiceBox inside existing MENU/Tools, preserving
    # old color-button callbacks unchanged. Must re-open plugin to recreate skin.
    marker='''    def _r711_tools_choice(self, item):'''
    helper='''    def _r723_select_home_layout(self):
        from Screens.ChoiceBox import ChoiceBox
        self.session.openWithCallback(
            self._r723_set_home_layout, ChoiceBox,
            title="Home layout • select then close and reopen IPToSat Pro",
            list=[
                ("Classic Neo Dark + Premium Icons (default)", "classic"),
                ("R72 Live Monitor + Premium Icons", "monitor"),
            ])

    def _r723_set_home_layout(self, item):
        if not item or not isinstance(item, (tuple,list)) or len(item)<2:
            return
        chosen = item[1]
        if chosen not in ("classic","monitor"):
            return
        try:
            folder = os.path.dirname(self._r723_home_pref_path)
            if not os.path.isdir(folder):
                os.makedirs(folder)
            path = self._r723_home_pref_path
            tmp_path = path + ".tmp"
            with open(tmp_path,"w") as out:
                out.write(chosen+"\\n")
            os.rename(tmp_path,path)
            self.session.open(
                MessageBox,
                "Home style saved: %s. Close and reopen IPToSat Pro to apply." % chosen,
                type=MessageBox.TYPE_INFO, timeout=6)
        except Exception as err:
            self.session.open(MessageBox, "Home layout not saved: %s" % str(err),
                              type=MessageBox.TYPE_ERROR, timeout=8)

'''
    src=replace_one(src,marker,helper+marker)
    # Reuse trusted R72 real fields in the earlier R71.1 skin. No live network
    # requests or additional decoders; all values already in monitor snapshot.
    anchor='''        self["r721_iptv_res_badge"].setText(iptv_badge)'''
    render='''        if self._r723_layout == "classic":
            # Old Neo Dark layout + new IPTV and SAT live evidence.
            self["home_iptv_status"].setText(
                "PLAYING" if live else ("IPTV CATALOG READY" if count>0 else "NO IPTV SOURCE"))
            self["home_iptv_detail"].setText(
                "Provider %s  •  %s" % (server_label[:35], "video confirmed" if live
                    else ("%d cached channels" % count)) if selected
                else ("%d IPTV channels in catalog" % count))
            disp = presentation_name(active_name) if selected else "No active IPTV"
            self["home_selected_name"].setText(
                (disp[:64] + "…" if len(disp)>64 else disp))
            self["home_lock_badge"].setText("LOCKED" if self._r711_lock_active else "NO LOCK")
            self["home_quality_chip"].setText(iptv_badge if iptv_badge != "?" else "?")
            self["home_audio_chip"].setText(
                "Audio "+language[:6]+"*" if language not in ("","-","NONE","UNKNOWN") else "Audio ?")
            self["home_role_chip"].setText(role)
            self["home_speed_chip"].setText(
                "%.2f s" % (timing/1000.0) if live and timing>0 else "—")
            self["home_selected_info"].setText(
                "IPTV: %s  •  %s  •  %s" %
                (server_label[:39], ("PLAYING" if live else "Not verified"),
                 ("3840×2160" if verified and iw==3840 and ih==2160 else
                  ("%d×%d"%(iw,ih) if verified else "resolution unknown"))))
'''
    src=replace_one(src,anchor,anchor+"\n"+render)
    tree=ast.parse(src)
    dash=next(c for c in tree.body if isinstance(c,ast.ClassDef) and c.name=="SatIPTVBridgeDashboard")
    functions=[n for n in dash.body if isinstance(n,ast.FunctionDef)]
    assert len(functions)==len({n.name for n in functions})
    init=next(n for n in functions if n.name=="__init__")
    names=set()
    for n in ast.walk(init):
        if isinstance(n,ast.Subscript) and isinstance(n.value,ast.Name) and n.value.id=="self" and isinstance(n.slice,ast.Constant) and isinstance(n.slice.value,str):
            names.add(n.slice.value)
    for layout in (classic,modern):
        missing={w.get("name") for w in ET.fromstring(layout) if w.tag=="widget"}-names
        assert not missing,"Missing native widget "+str(missing)
    compile(src,PLUGIN,"exec")
    return src.encode()

def build(output=None):
    from PIL import Image
    raw=base64.b64decode(B64.read_bytes())
    assert len(raw)==SIZE and hashlib.sha256(raw).hexdigest()==PIN
    members=pack.unpack_ar(raw)
    before=pack.members_from(members["data.tar.gz"])
    controls=pack.members_from(members["control.tar.gz"])
    plugin=patch_plugin(before[PLUGIN]).decode()
    assert plugin.count('PLUGIN_VERSION = "%s"'%OLD)==1
    plugin=plugin.replace('PLUGIN_VERSION = "%s"'%OLD,'PLUGIN_VERSION = "%s"'%NEW).encode()
    updater=before[UPDATER].decode()
    assert updater.count('CURRENT_VERSION = "%s"'%OLD)==1
    updater=updater.replace('CURRENT_VERSION = "%s"'%OLD,'CURRENT_VERSION = "%s"'%NEW).encode()
    control=controls["control"].decode()
    assert control.count("Version: "+OLD)==1
    control=control.replace("Version: "+OLD,"Version: "+NEW,1).encode()
    art=premium_background()
    with Image.open(io.BytesIO(art)) as png:
        assert png.size==(1660,900)
    modified={PLUGIN:plugin,UPDATER:updater}
    added={ICON:art,CHANGELOG:b"R72.3: restore R71.1 Neo Dark Home by default with premium R72 icons and verified SAT/IPTV data. Live Monitor optional via MENU Appearance Home layout. Fast Zap, player, sources, mapping, timeshift unchanged. Hardware visual test pending.\n"}
    members["data.tar.gz"]=pack.make_tar(members["data.tar.gz"],modified,added)
    members["control.tar.gz"]=pack.make_tar(members["control.tar.gz"],{"control":control})
    path=Path(output) if output else ROOT/"r723-neo-classic-fusion-beta.ipk"
    if path.exists():path.unlink()
    blob=pack.assemble(members,path)
    after=pack.members_from(pack.unpack_ar(blob)["data.tar.gz"])
    check=pack.members_from(pack.unpack_ar(blob)["control.tar.gz"])
    assert set(after)==set(before)|set(added)
    for key,value in before.items():assert after[key]==modified.get(key,value),key
    for key,value in controls.items():assert check[key]==(control if key=="control" else value),key
    for name,source in after.items():
        if name.endswith(".py"):compile(source,name,"exec")
    info={"version":NEW,"size":len(blob),"sha256":hashlib.sha256(blob).hexdigest(),
      "protected_unchanged":len(before)-len(modified),
      "modified":sorted(modified),"new_files":sorted(added),
      "receiver_tested":False,"published_to_main":False}
    print("R723_CLASSIC_FUSION_PACKAGE_OK",json.dumps(info,sort_keys=True))
    return info

if __name__=="__main__":build(sys.argv[1] if len(sys.argv)>1 else None)
