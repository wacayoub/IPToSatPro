#!/usr/bin/env python3
"""R74 staged beta: apply real current bouquet, Neo Dark UI and source rank
improvements to exact R73.8 package, preserving protected runtime modules.
Not released to main automatically.
"""
import hashlib,importlib.util,json,sys,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r738",ROOT/"scripts/build-r738-auto-open.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
pp=importlib.util.spec_from_file_location("r74patch",ROOT/"scripts/r74_unified_patch.py")
p=importlib.util.module_from_spec(pp);pp.loader.exec_module(p)
OLD=b.NEW
NEW="1.0.46-r74.1-original-audio-beta"
P=b.b.P
PLUGIN=b.b.PLUGIN
CORE=b.b.CORE
UPDATER=b.b.UPDATER
THEME=P+"preview_theme_r74.py"
CHANGELOG=P+"CHANGELOG-r74-UNIFIED-PREVIEW.txt"

def _validate_skin(theme):
    ns={}
    exec(compile(theme,"preview_theme_r74.py","exec"),ns)
    root=ET.fromstring(ns["PREVIEW_R74_FHD"])
    assert root.attrib["size"]=="1700,790"
    widgets={w.attrib["name"]:w for w in root if w.tag=="widget"}
    expected={"title","focus_hint","sat_picon","picon_fallback","sat_current",
        "context_info","epg","status","subtitles","left_head","right_head",
        "sat_list","source_list","verify","detail","key_red","key_green",
        "key_yellow","key_blue","key_menu"}
    assert set(widgets)==expected
    def rect(w):
        x,y=map(int,w.attrib["position"].split(","))
        ww,hh=map(int,w.attrib["size"].split(","))
        assert x>=0 and y>=0 and ww>0 and hh>0 and x+ww<=1700 and y+hh<=790
        return (x,y,x+ww,y+hh)
    # The picon and its NO PICON fallback intentionally share one image region.
    for a,aw in widgets.items():
        for name,bw in widgets.items():
            if name<=a or {a,name}=={"sat_picon","picon_fallback"}:
                continue
            ax,ay,ar,ab=rect(aw);bx,by,br,bb=rect(bw)
            assert max(ax,bx)>=min(ar,br) or max(ay,by)>=min(ab,bb),("overlap",a,name)
    for w in widgets.values():rect(w)
    return True

def build(destination=None):
    with tempfile.TemporaryDirectory() as td:
        baseline=Path(td)/"r738.ipk"
        b.build(baseline)
        raw=baseline.read_bytes()
        parts=b.b.base.pack.unpack_ar(raw)
        original=b.b.base.pack.members_from(parts["data.tar.gz"])
        control=b.b.base.pack.members_from(parts["control.tar.gz"])
        plugin=p.patch_plugin(original[PLUGIN].decode())
        core=p.patch_core(original[CORE].decode())
        updater=original[UPDATER].decode()
        plugin=b.b.exactly(plugin,'PLUGIN_VERSION = "'+OLD+'"',
                            'PLUGIN_VERSION = "'+NEW+'"')
        updater=b.b.exactly(updater,'CURRENT_VERSION = "'+OLD+'"',
                             'CURRENT_VERSION = "'+NEW+'"')
        ctl=b.b.exactly(control["control"].decode(),"Version: "+OLD,"Version: "+NEW)
        theme_bytes=(ROOT/"scripts/r74_preview_theme.py").read_bytes()
        _validate_skin(theme_bytes.decode())
        changes={PLUGIN:plugin.encode(),CORE:core.encode(),UPDATER:updater.encode()}
        desc=("R74.1 original-SAT-audio Preview beta: native CURRENT bouquet with original Enigma2 "
            "service order including DVB FTA and encrypted TV, numeric 7 switches to "
            "current satellite, fast list load, a legible Neo Dark screen, 48 "
            "bounded all-server scored candidates, visible catalog-versus-measured "
            "labels, current-channel SAFE Auto Select/Auto Play (R73.8 engine), "
            "manual mapping, source detail, video preview, original player watchdog "
            "and failover protected. Native playback/monitor/timeshift modules "
            "unchanged. Do not treat CI tests as receiver validation.").encode()
        parts["data.tar.gz"]=b.b.base.pack.make_tar(parts["data.tar.gz"],changes,
                                                       {THEME:theme_bytes,CHANGELOG:desc})
        parts["control.tar.gz"]=b.b.base.pack.make_tar(parts["control.tar.gz"],
                                                          {"control":ctl.encode()})
        dest=Path(destination) if destination else ROOT/"r74-unified-preview-beta.ipk"
        if dest.exists():dest.unlink()
        result=b.b.base.pack.assemble(parts,dest)
        actual=b.b.base.pack.members_from(b.b.base.pack.unpack_ar(result)["data.tar.gz"])
        assert set(actual)==set(original)|{THEME,CHANGELOG}
        for key,val in original.items():
            assert actual[key]==changes.get(key,val),key
        for path,payload in actual.items():
            if path.endswith(".py"):compile(payload,path,"exec")
        assert actual[P+"monitor.py"]==original[P+"monitor.py"]
        assert actual[P+"player.py"]==original[P+"player.py"] if P+"player.py" in original else True
        return {"version":NEW,"size":len(result),
                "sha256":hashlib.sha256(result).hexdigest(),
                "changed":sorted(changes),"new_theme":THEME,
                "monitor_unchanged":True,"receiver_tested":False,
                "production_published":False,"theme_widgets":20}

if __name__=="__main__":
    print("R74_BETA_STAGE_OK",json.dumps(build(sys.argv[1] if len(sys.argv)>1 else None),sort_keys=True))
