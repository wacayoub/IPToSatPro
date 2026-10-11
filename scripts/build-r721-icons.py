#!/usr/bin/env python3
"""R72.1 premium real Enigma2 icon pack and resolution badges.

Extends the exact SHA-verified R72 beta package. No source/player/monitor code
is modified: static, antialiased, 1660x900 pixel art rendered at BUILD TIME.
Dynamic SAT / IPTV resolution badges are native Label components showing
verified decoder-reported video class, never guessed from IPTV channel names.
"""
import ast
import base64
import hashlib
import importlib.util
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r72_builder", ROOT/"scripts/build-r72-live-monitor.py")
baseline=importlib.util.module_from_spec(spec);spec.loader.exec_module(baseline)
archive=baseline.pack
P=baseline.P
PLUGIN=baseline.PLUGIN
UPDATER=baseline.UPDATER
IMAGE=P+"images/r721-premium-icons.png"
CHANGELOG=P+"CHANGELOG-r721-PREMIUM-ICONS.txt"
B64=ROOT/"payload/r72-live-monitor.b64"
PIN_SIZE=314512
PIN_SHA="6bb68ed906637c19e8e22a33a66165db53044a759258d19e39ec1898dee2c8d0"
OLD="1.0.46-r72-live-monitor-beta"
NEW="1.0.46-r72.1-premium-icons-beta"

def replace_exact(src,old,new):
    assert src.count(old)==1,("R72 protected source anchor mismatch",src.count(old),old[:150])
    return src.replace(old,new,1)

def draw_background():
    from PIL import Image, ImageDraw
    # Reuse exact original R72 cards/colors, but replace all eight primitive
    # icons with designer-drawn outlined icons and add crisp resolution badges.
    original=Image.open(io.BytesIO(baseline.draw_background())).convert("RGB")
    k=3
    big=original.resize((1660*k,900*k),Image.Resampling.NEAREST)
    d=ImageDraw.Draw(big)
    def S(v):return int(v*k)
    def b(points):return [tuple(S(v) for v in p) for p in points]
    def box(x,y,w,h,color,r=0,outline=None,thick=2):
        area=(S(x),S(y),S(x+w),S(y+h))
        d.rounded_rectangle(area,radius=S(r),fill=color,outline=outline,width=S(thick))
    def circle(x,y,r,fill=None,outline=None,width=2):
        d.ellipse((S(x-r),S(y-r),S(x+r),S(y+r)),fill=fill,outline=outline,width=S(width))
    def line(points,color,width=3):
        d.line(b(points),fill=color,width=S(width),joint="curve")
    def arc(x,y,w,h,start,end,color,width=3):
        d.arc((S(x),S(y),S(x+w),S(y+h)),start,end,fill=color,width=S(width))
    def polygon(points,color):
        d.polygon(b(points),fill=color)
    def icon_box(x,y,color_bg,outline):
        box(x-7,y-8,55,55,color_bg,11,outline,1)

    SAT="#A3D9FF"; IPTV="#7AF0BD"
    CYAN="#8DDFFB"; GREEN="#6CF0B8"; GOLD="#F0CC7F"; PURPLE="#D8C3FC"; PALE="#D5E6F5"

    # Remove crude previous symbols before replacing them.
    box(65,192,60,63,"#1A2A40")
    box(855,197,63,60,"#15382F")

    # Main SAT icon — recognizable parabolic dish with aerial/feed/LNB.
    x,y=80,198
    icon_box(x,y,"#29405B","#416384")
    arc(x-3,y-4,39,40,25,120,SAT,4)
    line([(x+6,y+30),(x+29,y+9)],SAT,3)
    line([(x+13,y+34),(x+21,y+43)],SAT,3)
    line([(x+11,y+43),(x+31,y+43)],SAT,3)
    circle(x+31,y+7,3,SAT)
    arc(x+26,y-8,22,22,270,358,SAT,2)

    # IPTV icon — screen, play symbol and wireless radio signal.
    x,y=869,200
    icon_box(x,y,"#235A48","#38795E")
    box(x+1,y+15,36,24,None,5,IPTV,3)
    polygon([(x+15,y+20),(x+15,y+33),(x+25,y+26)],IPTV)
    line([(x+14,y+42),(x+24,y+42)],IPTV,2)
    arc(x+8,y-4,23,22,220,320,IPTV,2)
    circle(x+20,y+12,2,IPTV)

    # MONITOR badges in top-right of SAT and IPTV cards. The text underneath
    # is a live native Label: HD/FHD/4K only when measured, else question mark.
    for x,y,bg,stroke in [(682,193,"#304761",SAT),(1485,193,"#285946",IPTV)]:
        box(x,y,103,58,bg,12)
        box(x+28,y+8,47,23,None,4,stroke,2)
        line([(x+52,y+31),(x+52,y+36)],stroke,2)
        line([(x+43,y+36),(x+61,y+36)],stroke,2)

    # Metric tile icon backgrounds. Fit 505x112 tiles without obscuring text.
    # Main metric headings will move right by 62px for more generous spacing.
    metric_icons=[(84,557,GREEN),(614,557,CYAN),(1143,557,GOLD),
                  (84,684,PURPLE),(614,684,CYAN),(1143,684,PALE)]
    for x,y,color in metric_icons:
        icon_box(x,y,"#2B3F57",color)
    # 1. Resolution: proper monitor, stand, display dots
    x,y=88,567
    box(x,y,35,24,None,4,GREEN,3)
    line([(x+17,y+24),(x+17,y+31)],GREEN,2)
    line([(x+7,y+31),(x+27,y+31)],GREEN,2)
    line([(x+7,y+9),(x+27,y+9)],GREEN,2)
    # 2. Opening speed: stop watch/clock hands
    x,y=632,583
    circle(x,y,16,None,CYAN,3)
    line([(x,y-15),(x,y-21)],CYAN,3)
    line([(x-5,y-23),(x+5,y-23)],CYAN,3)
    line([(x,y),(x+7,y-7)],CYAN,2)
    line([(x,y),(x,y-11)],CYAN,2)
    # 3. Language: audio speaker with radiating sound and stylized A.
    x,y=1150,571
    polygon([(x,y+13),(x+7,y+13),(x+18,y+5),(x+18,y+31),
             (x+7,y+24),(x,y+24)],GOLD)
    arc(x+7,y+8,30,27,300,60,GOLD,3)
    line([(x+28,y+8),(x+38,y+8)],GOLD,2)
    # 4. Audio codec: horizontal equalizer/waveform
    x,y=96,710
    for dx,lo,hi in [(0,8,26),(7,2,30),(14,11,23),(21,0,34),(28,7,25)]:
        line([(x+dx,y+lo),(x+dx,y+hi)],PURPLE,4)
    # 5. Video codec: film strip border with frames and sprockets.
    x,y=624,697
    box(x,y,37,35,None,4,CYAN,3)
    line([(x+11,y+2),(x+11,y+33)],CYAN,2)
    line([(x+26,y+2),(x+26,y+33)],CYAN,2)
    for iy in (7,17,27):
        circle(x+5,iy+y,1.5,CYAN)
        circle(x+32,iy+y,1.5,CYAN)
    # 6. Source/mapping provider: real network nodes with links
    x,y=1163,715
    line([(x,y-13),(x,y),(x-15,y+13)],PALE,3)
    line([(x,y),(x+15,y+13)],PALE,3)
    for cx,cy in [(x,y-15),(x-15,y+15),(x+15,y+15)]:
        circle(cx,cy,5,"#2B3F57",PALE,2)

    # Footer actions: scanner and refresh symbols, distinct from metric tiles.
    SCAN="#A8FCE1";UPDATE="#E2EEFF"
    fx,fy=252,827
    for dx,dy,xx,yy in [(0,0,1,1),(30,0,-1,1),(0,28,1,-1),(30,28,-1,-1)]:
        line([(fx+dx,fy+dy+yy*8),(fx+dx,fy+dy),
              (fx+dx+xx*8,fy+dy)],SCAN,3)
    circle(fx+15,fy+14,5,None,SCAN,2)
    fx,fy=1002,842
    arc(fx-16,fy-16,32,32,204,356,UPDATE,3)
    arc(fx-16,fy-16,32,32,24,176,UPDATE,3)
    line([(fx+18,fy-13),(fx+17,fy-2),(fx+8,fy-8)],UPDATE,3)
    line([(fx-18,fy+13),(fx-17,fy+2),(fx-8,fy+8)],UPDATE,3)

    # Artwork is a single small, native PNG background: no runtime Pillow,
    # SVG renderer, icon font dependency, animation or decoding on channel zaps.
    result=big.resize((1660,900),Image.Resampling.LANCZOS)
    out=io.BytesIO();result.save(out,format="PNG",optimize=True)
    blob=out.getvalue()
    assert blob[:8]==b"\x89PNG\r\n\x1a\n" and len(blob)<250000
    return blob

def update_skin(xml):
    root=ET.fromstring(xml)
    widgets={x.get("name"):x for x in root if x.tag=="widget"}
    for name in ("r72_res_head","r72_speed_head","r72_audio_lang_head",
                 "r72_audio_codec_head","r72_video_codec_head","r72_source_head"):
        target=widgets[name]
        x,y=map(int,target.get("position").split(","))
        w,h=map(int,target.get("size").split(","))
        target.set("position",f"{x+65},{y}")
        target.set("size",f"{w-65},{h}")
    # Make two live resolution badges, distinct from the metric tile.
    # Do not expose "4K" from channel NAME alone.
    for name,x,y,w,fg in [
        ("r721_sat_res_badge",699,224,68,"#B9E4FF"),
        ("r721_iptv_res_badge",1502,224,68,"#8DF1C2")]:
        ET.SubElement(root,"widget",{"name":name,"zPosition":"4",
                   "position":f"{x},{y}","size":f"{w},23","font":"Regular;19",
                   "foregroundColor":fg,"transparent":"1","halign":"center"})
    for name,pos,size in [
        ("home_preview_action","292,817","445,41"),
        ("home_update_action","1050,817","497,41")
    ]:
        widgets[name].set("position",pos)
        widgets[name].set("size",size)
        widgets[name].set("halign","left")
    for item in root:
        if item.tag=="ePixmap":
            if item.get("pixmap")!="__IPTOSAT_R72_BG__":
                raise AssertionError("Unexpected screen pixmap")
            item.set("pixmap","__IPTOSAT_R721_BG__")
    built=ET.tostring(root,encoding="unicode")
    names=set()
    for tag in ET.fromstring(built):
        p=tag.attrib.get("position");z=tag.attrib.get("size")
        if p and z:
            x,y=map(int,p.split(","));w,h=map(int,z.split(","))
            assert x>=0 and y>=0 and w>0 and h>0 and x+w<=1660 and y+h<=900
        if tag.tag=="widget":
            assert tag.get("name") not in names
            names.add(tag.get("name"))
    assert len(names)>=len(widgets)+2
    return built

def patch_plugin(raw):
    src=raw.decode()
    start='DASHBOARD_FHD = """\n'
    end='\n"""\n\nSETTINGS_FHD = """'
    assert src.count(start)==1 and src.count(end)==1
    before,rest=src.split(start,1)
    original_skin,after=rest.split(end,1)
    new_skin=update_skin(original_skin)
    src=before+start+new_skin+end+after
    old_bg='''os.path.join(os.path.dirname(__file__), "images", "r72-sat-iptv-live.png")'''
    new_bg='''os.path.join(os.path.dirname(__file__), "images", "r721-premium-icons.png")'''
    src=replace_exact(src,old_bg,new_bg)
    src=replace_exact(src,'"__IPTOSAT_R72_BG__"', '"__IPTOSAT_R721_BG__"')
    init='''        self["r72_source_val"] = Label("—")
'''
    extra='''        self["r721_sat_res_badge"] = Label("?")
        self["r721_iptv_res_badge"] = Label("?")
'''
    src=replace_exact(src,init,init+extra)
    # SAT reports tuner video dimensions; IPTV badge only after confirmed
    # playback AND successful quality verification. Prevent stale 4K labels.
    final='''        self["r72_source_val"].setText(
            ("%s  •  %.0f score" % (role, float(snap.get("score") or 0))) if selected else "—")
'''
    addon='''        def _r721_res_class(w,h):
            try:
                w,h=int(w),int(h)
            except Exception:
                return "?"
            if w<=0 or h<=0:
                return "?"
            return ("4K" if w>=3000 else ("FHD" if w>=1800 and h>=1000
                    else ("HD" if w>=1200 and h>=700 else "SD")))
        sat_badge = _r721_res_class(snap.get("sat_width"),snap.get("sat_height"))
        iptv_badge = _r721_res_class(iw,ih) if verified else "?"
        self["r721_sat_res_badge"].setText(sat_badge)
        self["r721_iptv_res_badge"].setText(iptv_badge)
'''
    src=replace_exact(src,final,final+addon)
    tree=ast.parse(src)
    dash=next(c for c in tree.body if isinstance(c,ast.ClassDef) and c.name=="SatIPTVBridgeDashboard")
    init=next(c for c in dash.body if isinstance(c,ast.FunctionDef) and c.name=="__init__")
    keys=set()
    for n in ast.walk(init):
        if isinstance(n,ast.Subscript) and isinstance(n.value,ast.Name) and n.value.id=="self" and isinstance(n.slice,ast.Constant) and isinstance(n.slice.value,str):
            keys.add(n.slice.value)
    visual={w.get("name") for w in ET.fromstring(new_skin) if w.tag=="widget"}
    assert visual<=keys,visual-keys
    compile(src,PLUGIN,"exec")
    return src.encode()

def build(output=None):
    from PIL import Image
    raw=base64.b64decode(B64.read_bytes())
    assert len(raw)==PIN_SIZE and hashlib.sha256(raw).hexdigest()==PIN_SHA
    parts=archive.unpack_ar(raw)
    before=archive.members_from(parts["data.tar.gz"])
    controls=archive.members_from(parts["control.tar.gz"])
    plugin=patch_plugin(before[PLUGIN]).decode()
    oldver='PLUGIN_VERSION = "%s"' % OLD
    assert plugin.count(oldver)==1
    plugin=plugin.replace(oldver,'PLUGIN_VERSION = "%s"'%NEW,1).encode()
    updater=before[UPDATER].decode()
    oldver='CURRENT_VERSION = "%s"'%OLD
    assert updater.count(oldver)==1
    updater=updater.replace(oldver,'CURRENT_VERSION = "%s"'%NEW,1).encode()
    ctrl=controls["control"].decode()
    assert ctrl.count("Version: "+OLD)==1
    ctrl=ctrl.replace("Version: "+OLD,"Version: "+NEW,1).encode()
    icon_png=draw_background()
    with Image.open(io.BytesIO(icon_png)) as image:
        assert image.size==(1660,900)
    modified={PLUGIN:plugin,UPDATER:updater}
    added={IMAGE:icon_png,CHANGELOG:(
        "R72.1 premium native icons: SAT dish, IPTV WiFi+play, source monitors with "
        "measured HD/FHD/4K labels, 6 metric pictograms, Preview scan and Update "
        "refresh. Antialiased BUILD TIME icons on 1660x900 static PNG; no new "
        "rendering dependencies on receiver. Fast Zap, mapping, player, "
        "timeshift, source match engine and settings unchanged.\n").encode()}
    parts["data.tar.gz"]=archive.make_tar(parts["data.tar.gz"],modified,added)
    parts["control.tar.gz"]=archive.make_tar(parts["control.tar.gz"],{"control":ctrl})
    out=Path(output) if output else ROOT/"r721-premium-icons-beta.ipk"
    if out.exists():out.unlink()
    buf=archive.assemble(parts,out)
    after=archive.members_from(archive.unpack_ar(buf)["data.tar.gz"])
    control_after=archive.members_from(archive.unpack_ar(buf)["control.tar.gz"])
    assert set(after)==set(before)|set(added)
    for name,blob in before.items():
        assert after[name]==modified.get(name,blob),"Protected plugin file changed: "+name
    for name,blob in controls.items():
        assert control_after[name]==(ctrl if name=="control" else blob)
    for name,blob in after.items():
        if name.endswith(".py"):compile(blob,name,"exec")
    result={"version":NEW,"size":len(buf),"sha256":hashlib.sha256(buf).hexdigest(),
       "changed":sorted(modified),"added":sorted(added),
       "runtime_player_changed":False,"unchanged_files":len(before)-len(modified),
       "receiver_tested":False,"production_published":False}
    print("R721_PREMIUM_ICON_PACKAGE_OK",json.dumps(result,sort_keys=True))
    return result

if __name__=="__main__":
    build(sys.argv[1] if len(sys.argv)>1 else None)
