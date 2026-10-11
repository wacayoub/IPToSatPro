#!/usr/bin/env python3
"""R72.2 TV polish on the exact installed R72.1 premium-icons baseline.

Only screen XML/Labels and display decisions: no service, player, audio,
fallback, preview, mappings, cache, timeshift, or monitor changes.
"""
import ast,base64,hashlib,importlib.util,json,sys,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r721",ROOT/"scripts/build-r721-icons.py")
r721=importlib.util.module_from_spec(sp);sp.loader.exec_module(r721)
archive=r721.archive
PLUGIN=r721.PLUGIN;UPDATER=r721.UPDATER;P=r721.P
BASE=ROOT/"payload/r721-premium-icons.b64"
PIN="5da1148476b471a000f9b2064f0b2e01d4db131f946783b24a70c098ebd97092"
SIZE=358772
OLD="1.0.46-r72.1-premium-icons-beta"
VERSION="1.0.46-r72.2-tv-polish-beta"
CHANGELOG=P+"CHANGELOG-r722-TV-POLISH.txt"

def only(s,a,b):
    n=s.count(a)
    assert n==1,(repr(a[:130]),n)
    return s.replace(a,b,1)

def layout(xml):
    root=ET.fromstring(xml)
    widgets={x.get("name"):x for x in root if x.tag=="widget"}
    def move(key,pos=None,size=None,font=None):
        w=widgets[key]
        if pos:w.set("position",pos)
        if size:w.set("size",size)
        if font:w.set("font","Regular;%d"%font)
    move("r72_iptv_name","861,251","689,81",27)
    move("r72_iptv_provider","862,347","695,28",21)
    move("r72_iptv_role","862,386","695,28",19)
    move("r72_sat_position","74,316","686,30",20)
    # Source/footer remain inside original artwork bounds.
    # Native version is already included inside Home; avoid full plugin version
    # being repeated in the top black OpenATV title strip.
    move("version","1090,75","270,24",15)
    for name in ("r72_res_head","r72_speed_head","r72_audio_lang_head",
                 "r72_audio_codec_head","r72_video_codec_head","r72_source_head"):
        w=widgets[name]
        w.set("font","Regular;19")
    for name in ("r72_res_val","r72_speed_val","r72_audio_lang_val",
                 "r72_audio_codec_val","r72_video_codec_val","r72_source_val"):
        w=widgets[name]
        w.set("font","Regular;30")
    ET.SubElement(root,"widget",{
      "name":"r722_footer_hint","position":"300,867","size":"1060,27",
      "font":"Regular;18","foregroundColor":"#B5CFE1",
      "halign":"center","transparent":"1","zPosition":"5"})
    xml=ET.tostring(root,encoding="unicode")
    names=set()
    for node in ET.fromstring(xml):
        if node.get("position") and node.get("size"):
            x,y=map(int,node.get("position").split(","))
            w,h=map(int,node.get("size").split(","))
            assert 0<=x<1660 and 0<=y<900 and x+w<=1660 and y+h<=900
        if node.tag=="widget":
            assert node.get("name") not in names
            names.add(node.get("name"))
    return xml

def patch_plugin(binary):
    s=binary.decode()
    start='DASHBOARD_FHD = """\n';end='\n"""\n\nSETTINGS_FHD = """'
    assert s.count(start)==s.count(end)==1
    a,rest=s.split(start,1);old,b=rest.split(end,1)
    updated=layout(old)
    s=a+start+updated+end+b
    # Enigma2 Screen.setTitle controls the native OpenATV header.
    s=only(s,'self.setTitle("%s %s" % (PLUGIN_NAME, PLUGIN_VERSION))',
             'self.setTitle("IPToSat Pro")')
    s=only(s,'self["version"] = Label(PLUGIN_VERSION)',
             'self["version"] = Label("R72.2 BETA")')
    s=only(s,'self["r721_iptv_res_badge"] = Label("?")',
             'self["r721_iptv_res_badge"] = Label("?")\n        self["r722_footer_hint"] = Label("BLUE • Event Log    |    MENU • Settings / Tools")')
    # Give genuine long provider/channel names enough room on two rows rather
    # than silently slicing them to 37 characters. Enigma2 Label supports \n.
    old='''self["r72_iptv_name"].setText(presentation_name(active_name)[:37] if selected else "No IPTV candidate")'''
    new='''full_iptv_name = presentation_name(active_name) if selected else "No IPTV candidate"
        if len(full_iptv_name) > 27:
            first_break = full_iptv_name.rfind(" ",0,28)
            if first_break < 14:
                first_break = 27
            first_name = full_iptv_name[:first_break].strip()
            remaining = full_iptv_name[first_break:].strip()
            full_iptv_name = first_name + "\\n" + remaining[:35]
        self["r72_iptv_name"].setText(full_iptv_name)'''
    s=only(s,old,new)
    # 0% native SNR ProgressBar appeared FULL on physical receiver. Hide
    # the fill at zero/unknown so the dark static track does not lie.
    anchor='''self["r72_sat_signal"].setText("%d%%" % snr_numeric if snr_numeric is not None else "N/A")'''
    replace=anchor+'''
        zero_or_unknown = (snr_numeric is None or snr_numeric == 0)
        try:
            if zero_or_unknown:
                self["home_snr_bar"].hide()
            else:
                self["home_snr_bar"].show()
        except Exception:
            pass
        sat_lock = bool(snap.get("sat_shadow_lock"))
        self["r72_sat_signal_title"].setText(
            "SAT SIGNAL • NO LOCK" if not sat_lock and zero_or_unknown
            else "SATELLITE SIGNAL • SNR")'''
    s=only(s,anchor,replace)
    # A decoder-reported SAT dimension is not a verified SAT resolution when
    # the SAT tuner is unlocked and IPTV is playing. Avoid false 4K proof.
    s=only(s,
        'sat_badge = _r721_res_class(snap.get("sat_width"),snap.get("sat_height"))',
        'sat_badge = _r721_res_class(snap.get("sat_width"),snap.get("sat_height")) if snap.get("sat_shadow_lock") else "?"')
    # Clarify cached SAT video info, still displayed for useful context.
    s=only(s,
        '''self["r72_sat_foot"].setText("Video %s  •  Audio SAT %s" % (sat_res, sat_audio))''',
        '''self["r72_sat_foot"].setText("SAT video %s • Audio %s" % (sat_res if snap.get("sat_shadow_lock") else "not verified",sat_audio))''')
    tree=ast.parse(s)
    screen=next(c for c in tree.body if isinstance(c,ast.ClassDef) and c.name=="SatIPTVBridgeDashboard")
    init=next(c for c in screen.body if isinstance(c,ast.FunctionDef) and c.name=="__init__")
    names=set()
    for n in ast.walk(init):
        if isinstance(n,ast.Subscript) and isinstance(n.value,ast.Name) and n.value.id=="self" and isinstance(n.slice,ast.Constant) and isinstance(n.slice.value,str):
            names.add(n.slice.value)
    visuals={x.get("name") for x in ET.fromstring(updated) if x.tag=="widget"}
    assert visuals<=names,visuals-names
    compile(s,PLUGIN,"exec")
    return s.encode()

def build(dest=None):
    raw=base64.b64decode(BASE.read_bytes())
    assert len(raw)==SIZE and hashlib.sha256(raw).hexdigest()==PIN
    parts=archive.unpack_ar(raw)
    original=archive.members_from(parts["data.tar.gz"])
    control=archive.members_from(parts["control.tar.gz"])
    code=patch_plugin(original[PLUGIN]).decode()
    assert code.count('PLUGIN_VERSION = "%s"'%OLD)==1
    code=code.replace('PLUGIN_VERSION = "%s"'%OLD,'PLUGIN_VERSION = "%s"'%VERSION).encode()
    updater=original[UPDATER].decode()
    assert updater.count('CURRENT_VERSION = "%s"'%OLD)==1
    updater=updater.replace('CURRENT_VERSION = "%s"'%OLD,'CURRENT_VERSION = "%s"'%VERSION).encode()
    ctrl=control["control"].decode()
    assert ctrl.count("Version: "+OLD)==1
    ctrl=ctrl.replace("Version: "+OLD,"Version: "+VERSION,1).encode()
    changes={PLUGIN:code,UPDATER:updater}
    additions={CHANGELOG:b"R72.2 TV polish: shorter native title, two-line long IPTV name, correctly hidden 0% SNR fill, unlocked SAT video marked unknown, larger metrics, footer with MENU Settings. Player/mappings/source unchanged.\n"}
    parts["data.tar.gz"]=archive.make_tar(parts["data.tar.gz"],changes,additions)
    parts["control.tar.gz"]=archive.make_tar(parts["control.tar.gz"],{"control":ctrl})
    out=Path(dest) if dest else ROOT/"r722-tv-polish-beta.ipk"
    if out.exists():out.unlink()
    result=archive.assemble(parts,out)
    after=archive.members_from(archive.unpack_ar(result)["data.tar.gz"])
    con_after=archive.members_from(archive.unpack_ar(result)["control.tar.gz"])
    assert set(after)==set(original)|set(additions)
    for p,blob in original.items():assert after[p]==changes.get(p,blob),p
    for p,blob in control.items():assert con_after[p]==(ctrl if p=="control" else blob),p
    for p,blob in after.items():
        if p.endswith(".py"):compile(blob,p,"exec")
    info={"version":VERSION,"bytes":len(result),"sha256":hashlib.sha256(result).hexdigest(),
          "unchanged_files":len(original)-len(changes),"player_changed":False,
          "field_tested":False,"published_to_main":False}
    print("R722_TV_POLISH_PACKAGE_OK",json.dumps(info,sort_keys=True))
    return info
if __name__=="__main__":
    build(sys.argv[1] if len(sys.argv)>1 else None)
