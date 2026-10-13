#!/usr/bin/env python3
"""R75 actual installable IPK: consolidated R74.11-.18 + smart index.

Not a mock or one-file hotfix. Build from the byte-verified real R74.10
Enigma2 IPK; apply every staged correction to the packaged modules; change
package/GUI/updater version consistently; retain untouched native player,
serviceapp, timeshift, bouquets and persistent mapping files.

Staging only: no update to production main/update.json until receiver tests.
"""
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def module(name, filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/filename)
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

base=module("r74real","build-r74-unified.py")
p11=module("r75p11","r7411_preview_persist_priority_hotfix.py")
p12=module("r75p12","r7412_preview_fast_shortlist_hotfix.py")
p13=module("r75p13","r7413_preview_inline_hotfix.py")
p14=module("r75p14","r7414_fast_candidates_manual_lock.py")
p15=module("r75p15","r7415_firstpaint_green_any_focus.py")
p16=module("r75p16","r7416_unmap_fta_crypt_icons.py")
aac=module("r75aac","r74_tod_bein_audio_hotfix.py")
p17=module("r75p17","r7417_fta_signal_native_guard.py")
p18=module("r75p18","r7418_bounded_cancel_fuzzy.py")
p75=module("r75smart","r75_smart_index_patch.py")

PREVIOUS=base.NEW
VERSION="1.0.46-r75.0-smart-index-beta"
P=base.P
PLUGIN=base.PLUGIN
CORE=base.CORE
MONITOR=base.MONITOR
UPDATER=base.UPDATER
CHANGELOG=P+"CHANGELOG-R75-SMART-INDEX.txt"


def transform_package(files):
    """Return new packaged bytes; validate every prerequisite exact source."""
    plugin=files[PLUGIN].decode()
    core=files[CORE].decode()
    monitor=files[MONITOR].decode()
    updater=files[UPDATER].decode()
    steps=[]
    for name, function in [
        ("R74.11",p11.patch_plugin),
        ("R74.12",p12.patch),
        ("R74.13",p13.patch),
        ("R74.14",p14.patch),
        ("R74.15",p15.patch),
        ("R74.16",p16.patch)]:
        plugin,status=function(plugin)
        assert status=="ready",(name,status)
        steps.append(name)
    monitor,status=aac.patch(monitor)
    assert status=="ready",("beIN AAC",status)
    steps.append("beIN AAC")
    monitor,status=p17.patch(monitor)
    assert status=="ready",("FTA guard",status)
    steps.append("R74.17")
    core,status=p18.patch_core(core)
    assert status=="ready",("bounded fuzzy core",status)
    monitor,status=p18.patch_monitor(monitor)
    assert status=="ready",("bounded fuzzy monitor",status)
    steps.append("R74.18")
    core=p75.patch_core(core)
    monitor=p75.patch_monitor(monitor)
    steps.append("R75")
    needle='PLUGIN_VERSION = "'+PREVIOUS+'"'
    assert plugin.count(needle)==1,"R74 plugin version drift"
    plugin=plugin.replace(needle,'PLUGIN_VERSION = "'+VERSION+'"')
    old_updater='CURRENT_VERSION = "'+PREVIOUS+'"'
    assert updater.count(old_updater)==1,"R74 updater version drift"
    updater=updater.replace(old_updater,'CURRENT_VERSION = "'+VERSION+'"')
    # Update URL normally still points to production R70, which must not
    # downgrade experimental R75. Replace updater's manifest only after
    # verifying the exact source anchor in CI.
    updater=p75.patch_updater(updater)
    updated={PLUGIN:plugin.encode(),CORE:core.encode(),MONITOR:monitor.encode(),
             UPDATER:updater.encode()}
    for path,raw in updated.items():
        compile(raw,path,"exec")
    return updated,steps


def build(destination=None):
    with tempfile.TemporaryDirectory() as td:
        baseline=Path(td)/"r74.ipk"
        base.build(baseline)
        pack=base.b.b.base.pack
        parts=pack.unpack_ar(baseline.read_bytes())
        original=pack.members_from(parts["data.tar.gz"])
        control=pack.members_from(parts["control.tar.gz"])
        changed,steps=transform_package(original)
        control_old=control["control"].decode()
        assert control_old.count("Version: "+PREVIOUS)==1
        control_new=control_old.replace("Version: "+PREVIOUS,"Version: "+VERSION)
        note=("R75 consolidated R74.11-R74.18, normal Preview24/deep192, "
              "first-paint index, manual GREEN without OK, per-channel UNMAP, "
              "FTA/crypted icons and filtering, native SAT FTA priority, beIN "
              "AAC ServiceApp fix, bounded cancellable auto fuzzy 96, "
              "indexed source nomination, short-lived negative caching; "
              "native player/timeshift/EPG/configuration/mappings unchanged. "
              "Experimental until receiver validation; production unchanged.").encode()
        parts["data.tar.gz"]=pack.make_tar(parts["data.tar.gz"],changed,
                                           {CHANGELOG:note})
        parts["control.tar.gz"]=pack.make_tar(parts["control.tar.gz"],
                                              {"control":control_new.encode()})
        output=Path(destination) if destination else ROOT/"iptosatpro-r75-smart-index-beta.ipk"
        if output.exists():output.unlink()
        ipk=pack.assemble(parts,output)
        inspected=pack.members_from(pack.unpack_ar(ipk)["data.tar.gz"])
        assert set(inspected)==set(original)|{CHANGELOG}
        for filename,data in original.items():
            assert inspected[filename]==changed.get(filename,data),filename
        for filename,data in inspected.items():
            if filename.endswith(".py"):compile(data,filename,"exec")
        assert inspected.get(P+"player.py")==original.get(P+"player.py")
        assert inspected.get(P+"metadata_shadow.py")==original.get(P+"metadata_shadow.py")
        return {"version":VERSION,"size":len(ipk),
                "sha256":hashlib.sha256(ipk).hexdigest(),
                "changed":list(sorted(changed)),"steps":steps,
                "player_unchanged":True,"receiver_tested":False,
                "production_published":False,"beta":True}


if __name__=="__main__":
    print("R75_BUILD_OK",json.dumps(build(sys.argv[1] if len(sys.argv)>1 else None),
                                     sort_keys=True))
