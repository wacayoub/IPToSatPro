#!/usr/bin/env python3
"""Build R72 SAT -> IPTV Live Monitor from byte-pinned R71.1 cleanup.

Changes: Dashboard screen XML, static rounded background and read-only
screen Labels only. Preview, catalog, mapping, player, playback, fallback,
timeshift, encrypted filter and all receiver files stay byte identical.
"""
import ast, base64, hashlib, importlib.util, io, json, re, sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r711",ROOT/"scripts/build-r711-cleanup-beta.py")
base=importlib.util.module_from_spec(sp);sp.loader.exec_module(base)
pack=base.archive
P=base.P
PLUGIN=base.PLUGIN
UPDATER=base.UPDATER
OLD="1.0.46-r71.1-neo-cleanup-beta"
NEW="1.0.46-r72-live-monitor-beta"
B64=ROOT/"payload/r711-neo-cleanup.b64"
PIN_SIZE=308552
PIN_SHA="ae70b0e84827a5bb0edc8b79abf5ebaf1e98e4ccb64fe10c1f8b5b05cb66cedd"
IMAGE=P+"images/r72-sat-iptv-live.png"
CHANGELOG=P+"CHANGELOG-r72-SAT-IPTV-LIVE.txt"

def draw_background():
    from PIL import Image,ImageDraw
    # Raster assets are built in CI once and rendered by the receiver once.
    W,H=1660,900
    im=Image.new("RGB",(W,H),"#0B1422")
    d=ImageDraw.Draw(im)
    def tile(x,y,w,h,fill,r=19):
        d.rounded_rectangle((x,y,x+w,y+h),radius=r,fill=fill)
    def line(p,fill,width=2):d.line(p,fill=fill,width=width)
    def rect(p,fill):d.rectangle(p,fill=fill)
    def circ(p,fill,outline=None,width=1):d.ellipse(p,fill=fill,outline=outline,width=width)
    # Top header with restrained cyan brand.
    rect((0,0,W,103),"#111C2B")
    rect((40,99,1620,102),"#3CBFAD")
    tile(1383,25,230,48,"#16493B",24)
    # SAT and IPTV side-by-side, separate real-world and virtual transport identities.
    tile(38,132,772,398,"#1A2A40",24)
    tile(829,132,791,398,"#15382F",24)
    tile(60,153,145,33,"#2B4866",14)
    tile(849,153,142,33,"#245C45",14)
    # SAT signal progress background. Native Enigma2 ProgressBar overlaid.
    tile(73,450,566,18,"#36526A",8)
    # explicit LOCK and PLAY separate status pills.
    tile(855,437,166,52,"#31506B",14)
    tile(1040,437,182,52,"#245947",14)
    # Arrow from SAT identity to IPTV replacement (static).
    line([(809,300),(829,300)],"#72BFC3",4)
    line([(821,292),(830,300),(821,308)],"#72BFC3",3)
    # Metric grid (2 rows x 3 columns), high contrast and readable.
    w=505
    xs=[39,568,1097]
    for x in xs:
        tile(x,546,w,112,"#1C2C42",18)
        tile(x,672,w,112,"#1C2C42",18)
    # Mini accent chips to echo requested resolution icon colors.
    for x,co in zip(xs,["#54C69C","#7ABCF2","#D6A758"]):
        tile(x+14,560,7,84,co,3)
    for x,co in zip(xs,["#AA97D5","#75C4DE","#93A9C8"]):
        tile(x+14,686,7,84,co,3)
    # Bottom simple actions, unchanged click via remote.
    tile(39,805,763,60,"#1D5B52",17)
    tile(825,805,794,60,"#2C3E5E",17)
    # Small static symbols: satellite dish, network play, clock.
    d.arc((70,198,102,229),0,170,fill="#9DCDF7",width=4)
    line([(85,225),(92,240),(109,249)],"#9DCDF7",3)
    tile(863,211,41,29,"#65DCAE",9)
    d.polygon([(879,216),(879,234),(892,225)],fill="#14382F")
    out=io.BytesIO();im.save(out,format="PNG",optimize=True)
    blob=out.getvalue()
    assert len(blob)<160000 and blob[:8]==b"\x89PNG\r\n\x1a\n"
    return blob

LABELS=[
# name, x,y,w,h,font,fg, halign
("title",140,25,945,43,34,"#F6F9FE","left"),
("subtitle",143,75,965,20,17,"#9AAFC5","left"),
("version",1100,77,240,22,16,"#B1C3D5","right"),
("home_status",1390,26,214,46,21,"#6EF3B9","center"),
("r72_sat_head",78,155,115,29,19,"#C9E3FF","left"),
("r72_sat_name",74,250,697,50,33,"#F4F7FF","left"),
("r72_sat_position",74,315,687,31,21,"#A8C9E5","left"),
("r72_sat_provider",74,365,687,30,23,"#F2F6FD","left"),
("r72_sat_signal_title",74,412,368,24,17,"#94B8D4","left"),
("home_snr_bar",73,450,566,18,16,"#49D6B1","left"),
("r72_sat_signal",651,431,110,50,30,"#6FEBBA","right"),
("r72_sat_foot",74,487,680,23,17,"#A6BED7","left"),
("r72_iptv_head",866,155,120,29,19,"#D3F5E4","left"),
("r72_iptv_name",861,250,725,50,31,"#FFFFFF","left"),
("r72_iptv_provider",862,318,698,26,21,"#D1F1E1","left"),
("r72_iptv_role",862,366,698,27,20,"#C2DAD0","left"),
("r72_mapping_status",859,444,154,39,20,"#DBE7F6","center"),
("r72_play_status",1044,444,173,39,20,"#79F0B7","center"),
("r72_iptv_foot",862,496,704,24,16,"#B7DCCC","left"),
("r72_res_head",73,560,442,25,16,"#B2C2D6","left"),
("r72_res_val",75,598,443,47,29,"#6FE4AE","left"),
("r72_speed_head",601,560,439,25,16,"#B2C2D6","left"),
("r72_speed_val",601,598,441,47,29,"#B2DFFF","left"),
("r72_audio_lang_head",1132,560,436,25,16,"#B2C2D6","left"),
("r72_audio_lang_val",1132,598,424,47,26,"#F0D28B","left"),
("r72_audio_codec_head",73,686,450,25,16,"#B2C2D6","left"),
("r72_audio_codec_val",75,724,445,45,27,"#D5C6F5","left"),
("r72_video_codec_head",601,686,450,25,16,"#B2C2D6","left"),
("r72_video_codec_val",601,724,450,45,27,"#B2EAF6","left"),
("r72_source_head",1132,686,446,25,16,"#B2C2D6","left"),
("r72_source_val",1132,724,448,45,27,"#DDE7F4","left"),
("home_preview_action",72,815,698,40,26,"#E8FFF8","center"),
("home_update_action",849,815,722,40,26,"#F2F7FF","center"),
]
def skin():
    # Avoid legacy hidden UI widgets; only NEW screen's labels render.
    root=ET.Element("screen",{"name":"SatIPTVBridgeDashboard","position":"center,center",
       "size":"1660,900","title":"IPToSat Pro • Live Monitor","backgroundColor":"#0B1422"})
    ET.SubElement(root,"ePixmap",{"position":"0,0","size":"1660,900","zPosition":"0",
                                  "pixmap":"__IPTOSAT_R72_BG__","alphatest":"off"})
    for name,x,y,w,h,font,color,align in LABELS:
        attr={"name":name,"zPosition":"3","position":f"{x},{y}","size":f"{w},{h}",
              "font":f"Regular;{font}","foregroundColor":color,"transparent":"1"}
        if align!="left":attr["halign"]=align
        if name=="home_snr_bar":
            del attr["font"];del attr["halign"] if "halign" in attr else None
            attr["foregroundColor"]="#49D6B1";attr["backgroundColor"]="#36526A"
        ET.SubElement(root,"widget",attr)
    ret=ET.tostring(root,encoding="unicode")
    parsed=ET.fromstring(ret)
    assert parsed.attrib["size"]=="1660,900"
    names=set()
    for w in parsed:
        x,y=map(int,w.attrib["position"].split(","))
        width,height=map(int,w.attrib["size"].split(","))
        assert 0<=x<1660 and 0<=y<900 and x+width<=1660 and y+height<=900
        if w.tag=="widget":
            assert w.attrib["name"] not in names
            names.add(w.attrib["name"])
    return ret

def subonce(s,a,b):
    if s.count(a)!=1:raise AssertionError("R72 unique code anchor count=%d %s"%(s.count(a),a[:100]))
    return s.replace(a,b,1)

INITIAL={
  "r72_sat_head":"SATELLITE", "r72_sat_name":"No SAT channel",
  "r72_sat_position":"Satellite —", "r72_sat_provider":"Provider —",
  "r72_sat_signal_title":"SATELLITE SIGNAL • SNR","r72_sat_signal":"N/A",
  "r72_sat_foot":"Video —  •  SAT audio —",
  "r72_iptv_head":"IPTV CURRENT","r72_iptv_name":"No IPTV candidate",
  "r72_iptv_provider":"IPTV Provider —",
  "r72_iptv_role":"Source —",
  "r72_mapping_status":"NO LOCK","r72_play_status":"NOT PLAYING",
  "r72_iptv_foot":"Candidate metadata; stream not yet verified",
  "r72_res_head":"VIDEO RESOLUTION","r72_res_val":"? • not verified",
  "r72_speed_head":"FIRST FRAME","r72_speed_val":"—",
  "r72_audio_lang_head":"CATALOG LANGUAGE","r72_audio_lang_val":"?",
  "r72_audio_codec_head":"AUDIO CODEC","r72_audio_codec_val":"Not available",
  "r72_video_codec_head":"VIDEO CODEC","r72_video_codec_val":"Not available",
  "r72_source_head":"SOURCE / MATCH","r72_source_val":"—",
}

def patch_plugin(raw):
    s=raw.decode()
    start='DASHBOARD_FHD = """\n';end='\n"""\n\nSETTINGS_FHD = """'
    assert s.count(start)==1 and s.count(end)==1
    before,rest=s.split(start,1)
    old,after=rest.split(end,1)
    s=before+start+skin()+end+after
    old_init='''self.skin = _theme_skin(DASHBOARD_FHD.replace(
            "__IPTOSAT_NEO_CLEANUP_BG__",
            os.path.join(os.path.dirname(__file__), "images", "neo-home-cleanup.png")))'''
    new_init='''self.skin = _theme_skin(DASHBOARD_FHD.replace(
            "__IPTOSAT_R72_BG__",
            os.path.join(os.path.dirname(__file__), "images", "r72-sat-iptv-live.png")))'''
    s=subonce(s,old_init,new_init)
    # Existing hidden legacy Labels remain so existing stable _refresh_monitor
    # methods never try to update missing components. Only new native labels
    # appear on screen, initialized below.
    anchor='''        self["home_menu_hint"] = Label("MENU  •  Settings / Tools")
'''
    inject="".join('        self["%s"] = Label(%s)\n'%(k,repr(v)) for k,v in INITIAL.items())
    s=subonce(s,anchor,anchor+inject)
    anchor='''        self["home_lock_badge"].setText("LOCKED" if self._r711_lock_active else ("IPTV LIVE" if active else "UNMAPPED"))
'''
    derived='''        # R72: presentation only. The SAT and IPTV cards have separate truth sources.
        # first_image_locked is actual player evidence; a saved manual mapping alone
        # NEVER means playback. Stale last_match is never marked PLAYING.
        live = bool(active and snap.get("first_image_locked"))
        selected = active_name not in ("", "-", "None")
        self["r72_sat_name"].setText(sat_name[:37])
        self["r72_sat_position"].setText("%s  •  %s" % (sat[:40], orbital[:18] if orbital else ""))
        self["r72_sat_provider"].setText("Provider: %s" % provider[:36])
        self["r72_sat_signal"].setText("%d%%" % snr_numeric if snr_numeric is not None else "N/A")
        sw = int(snap.get("sat_width") or 0)
        sh = int(snap.get("sat_height") or 0)
        sat_res = ("%dx%d (reported)" % (sw,sh)) if sw and sh else "resolution unknown"
        sat_audio = "/".join(str(v) for v in (snap.get("sat_audio_languages") or [])[:3]) or "?"
        self["r72_sat_foot"].setText("Video %s  •  Audio SAT %s" % (sat_res, sat_audio))
        self["r72_iptv_name"].setText(presentation_name(active_name)[:37] if selected else "No IPTV candidate")
        server_label = str(snap.get("server_label") or "").strip()
        if server_label in ("", "-", "None"): server_label = "Unknown"
        self["r72_iptv_provider"].setText("Provider: %s" % (server_label[:39] if selected else "—"))
        self["r72_iptv_role"].setText("Source %s  •  %s" % (role, mode if mode else "AUTO") if selected else "No selected source")
        self["r72_mapping_status"].setText("LOCKED" if self._r711_lock_active else "UNMAPPED")
        self["r72_play_status"].setText("PLAYING" if live else ("CANDIDATE" if selected else "NO VIDEO"))
        self["r72_iptv_foot"].setText("First frame confirmed" if live else
            ("Listed candidate — video not confirmed" if selected else "No IPTV stream selected"))
        verified = bool(live and snap.get("quality_verified") and iw>0 and ih>0)
        actual = ("%d × %d" % (iw,ih)) if verified else ""
        claimed = str(snap.get("quality") or "").strip()
        if verified:
            real_class = "4K" if iw>=3000 else ("FHD" if iw>=1800 and ih>=1000 else
                       ("HD" if iw>=1200 and ih>=700 else "SD"))
            res_label = real_class+"  "+actual
        elif selected and claimed not in ("", "-", "Unknown"):
            res_label = ("Claimed " + claimed)[:31]
        else:
            res_label = "Not verified"
        self["r72_res_val"].setText(res_label)
        self["r72_speed_val"].setText(("%.2f s" % (timing/1000.0)) if live and timing>0 else "Not measured")
        # language from candidate catalog, NOT verified against active decoder audio.
        self["r72_audio_lang_val"].setText(
            (language[:19]+" (catalog)") if selected and language not in ("", "-", "NONE", "UNKNOWN") else "Unknown")
        # The current R71 snapshot contains no active audio/video CODEC or FPS.
        # Explicitly avoid deriving codecs from format names or old decoder dimensions.
        self["r72_audio_codec_val"].setText("Not available")
        self["r72_video_codec_val"].setText("Not available")
        self["r72_source_val"].setText(
            ("%s  •  %.0f score" % (role, float(snap.get("score") or 0))) if selected else "—")
'''
    s=subonce(s,anchor,anchor+derived)
    s=subonce(s,'self["subtitle"] = Label("R71.1  •  SMART SAT / IPTV  •  NEO HOME")',
              'self["subtitle"] = Label("R72  •  SATELLITE → IPTV  •  LIVE MONITOR")')
    s=subonce(s,'self["home_preview_action"] = Label("Preview Browser")',
              'self["home_preview_action"] = Label("GREEN  •  Preview Browser")')
    s=subonce(s,'self["home_update_action"] = Label("Online Update")',
              'self["home_update_action"] = Label("YELLOW  •  Online Update")')
    tree=ast.parse(s)
    dash=next(c for c in tree.body if isinstance(c,ast.ClassDef) and c.name=="SatIPTVBridgeDashboard")
    init=next(c for c in dash.body if isinstance(c,ast.FunctionDef) and c.name=="__init__")
    keys=set()
    for node in ast.walk(init):
        if isinstance(node,ast.Subscript) and isinstance(node.value,ast.Name) and node.value.id=="self" and isinstance(node.slice,ast.Constant) and isinstance(node.slice.value,str):
            keys.add(node.slice.value)
    visual={w.get("name") for w in ET.fromstring(skin()) if w.tag=="widget"}
    assert visual<=keys, "Missing initialized Labels: "+str(visual-keys)
    compile(s,PLUGIN,"exec")
    return s.encode()

def build(output=None):
    raw=base64.b64decode(B64.read_bytes())
    assert len(raw)==PIN_SIZE and hashlib.sha256(raw).hexdigest()==PIN_SHA
    parts=pack.unpack_ar(raw)
    before=pack.members_from(parts["data.tar.gz"])
    ctrls=pack.members_from(parts["control.tar.gz"])
    code=patch_plugin(before[PLUGIN]).decode()
    oldver='PLUGIN_VERSION = "%s"' % OLD
    assert code.count(oldver)==1
    code=code.replace(oldver,'PLUGIN_VERSION = "%s"'%NEW,1).encode()
    updated=before[UPDATER].decode()
    oldu='CURRENT_VERSION = "%s"'%OLD
    assert updated.count(oldu)==1
    updated=updated.replace(oldu,'CURRENT_VERSION = "%s"'%NEW,1).encode()
    control=ctrls["control"].decode()
    assert control.count("Version: "+OLD)==1
    newctrl=control.replace("Version: "+OLD,"Version: "+NEW,1).encode()
    asset=draw_background()
    changes={PLUGIN:code,UPDATER:updated}
    additions={IMAGE:asset,CHANGELOG:(
       "R72 SAT and IPTV actual two-column monitor: signal, satellite/provider, candidate IPTV/server, "
       "independent LOCKED and PLAYING, claimed vs verified video resolution, real first-image timing, "
       "SAT and catalog language. Audio/video codec marked unavailable until actual decoding metadata. "
       "No changes to Enigma2 playback, Fast LOCK zap, stream probing, timeshift, sources or mappings. "
       "Beta not field validated on Vu+.\n").encode()}
    parts["data.tar.gz"]=pack.make_tar(parts["data.tar.gz"],changes,additions)
    parts["control.tar.gz"]=pack.make_tar(parts["control.tar.gz"],{"control":newctrl})
    out=Path(output) if output else ROOT/"r72-live-monitor-beta.ipk"
    if out.exists():out.unlink()
    built=pack.assemble(parts,out)
    after=pack.members_from(pack.unpack_ar(built)["data.tar.gz"])
    ctrl_after=pack.members_from(pack.unpack_ar(built)["control.tar.gz"])
    assert set(after)==set(before)|set(additions)
    for name,blob in before.items():assert after[name]==changes.get(name,blob),name
    for name,blob in ctrls.items():assert ctrl_after[name]==(newctrl if name=="control" else blob),name
    for name,blob in after.items():
        if name.endswith(".py"):compile(blob,name,"exec")
    meta={"version":NEW,"size":len(built),"sha256":hashlib.sha256(built).hexdigest(),
          "modified_files":sorted(changes),"new_files":sorted(additions),
          "protected_unchanged":len(before)-len(changes),"playback_changed":False,
          "receiver_verified":False,"main_published":False}
    print("R72_LIVE_MONITOR_BUILD_OK",json.dumps(meta,sort_keys=True))
    return meta

if __name__=="__main__":build(sys.argv[1] if len(sys.argv)>1 else None)
