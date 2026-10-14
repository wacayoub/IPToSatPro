#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild actual R76 beta IPK from R75, changing presentation only.

Do NOT update production main/update.json or install on Vu+ from CI.
Retains player, monitor, catalog, mappings, timeshift and service databases.
"""
import hashlib
import importlib.util
import json
import tempfile
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(name,file):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/file)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

base=load("r75_builder","build-r75-smart-index.py")
layout=load("r76_layout","r76_metrix_preview_layout.py")
r763=load("r763_preview","r763_preview_fast_medal_patch.py")
r764=load("r764_multi","r764_multi_seed_patch.py")
VERSION="1.0.46-r76.4-all-indexed-firstpaint-beta"
OLD=base.VERSION
P=base.P
PLUGIN=base.PLUGIN
UPDATER=base.UPDATER
THEME=P+"preview_theme_r74.py"
NOTE=P+"CHANGELOG-R76-METRIX-PREVIEW-B.txt"
pack=base.base.b.b.base.pack


def build(destination=None):
    with tempfile.TemporaryDirectory() as work:
        baseline=Path(work)/"r75.ipk"
        base_info=base.build(baseline)
        assert base_info["version"]==OLD and not base_info["production_published"]
        archive=pack.unpack_ar(baseline.read_bytes())
        original=pack.members_from(archive["data.tar.gz"])
        controls=pack.members_from(archive["control.tar.gz"])

        plugin=r764.patch_plugin(r763.patch_plugin(layout.patch_preview_plugin(layout.patch_plugin(original[PLUGIN].decode()))))
        original_version='PLUGIN_VERSION = "'+OLD+'"'
        assert plugin.count(original_version)==1
        plugin=plugin.replace(original_version,'PLUGIN_VERSION = "'+VERSION+'"',1)
        updater=original[UPDATER].decode()
        updater_version='CURRENT_VERSION = "'+OLD+'"'
        assert updater.count(updater_version)==1
        updater=updater.replace(updater_version,'CURRENT_VERSION = "'+VERSION+'"',1)
        # Staged R76 beta intentionally disables old R75 manifest fallback:
        # an update attempt MUST NEVER silently downgrade to the R75 beta.
        # No external R76 manifest is advertised until package is staged/pinned.
        oldmanifest=base.p75.UPDATER_URL
        assert updater.count(oldmanifest)==1
        updater=updater.replace(oldmanifest,
            "https://raw.githubusercontent.com/wacayoub/IPToSatPro/"
            "feature/r76-metrix-home-preview-b/staging/r76-metrix-preview.update.json",1)

        rebuilt_theme=layout.theme_module()
        changes={PLUGIN:plugin.encode("utf-8"),UPDATER:updater.encode("utf-8"),
                 THEME:rebuilt_theme}
        assert set(changes)=={PLUGIN,UPDATER,THEME}
        for name,data in changes.items():
            assert name in original
            if name.endswith(".py"):compile(data,name,"exec")
        control=controls["control"].decode("utf-8")
        assert control.count("Version: "+OLD)==1
        changed_control=control.replace("Version: "+OLD,"Version: "+VERSION,1)
        desc=(
          "R76.4 beta: initial incomplete cached single-source augmented with all plausible indexed candidate variations across provider roles, correct OSNtv alias, medal for measured best overall, compact M/C source labels; professional Metrix Home 1660x900 "
          "and 1245x675 layouts with safe margins, existing live R72 monitor fields; "
          "Neo Dark Classic 2-panel browser with full-height IPTV candidates, "
          "removed inline VideoWindow while stock OK video test remains intact. "
          "Unchanged COLOR/number key actions, saved mappings, player, "
          "monitor, core, watchdog, FTA priority, backup streams, timeshift, "
          "EPGImport and update production. Static/CI simulation not actual "
          "video-hardware validation; NEVER claim PLAYING from match metadata. "
          "Installed R76 must be validated on receiver before stable publication.\n"
        ).encode("utf-8")
        archive["data.tar.gz"]=pack.make_tar(archive["data.tar.gz"],changes,{NOTE:desc})
        archive["control.tar.gz"]=pack.make_tar(archive["control.tar.gz"],
                                                 {"control":changed_control.encode()})
        output=Path(destination) if destination else ROOT/"iptosatpro-r76-metrix-preview-b-beta.ipk"
        if output.exists():output.unlink()
        raw=pack.assemble(archive,output)
        resulting=pack.members_from(pack.unpack_ar(raw)["data.tar.gz"])
        assert set(resulting)==set(original)|{NOTE}
        for name,data in original.items():
            assert resulting[name]==changes.get(name,data),name
        assert resulting.get(P+"player.py")==original.get(P+"player.py")
        assert resulting.get(P+"metadata_shadow.py")==original.get(P+"metadata_shadow.py")
        assert resulting[base.CORE]==original[base.CORE]
        assert resulting[base.MONITOR]==original[base.MONITOR]
        assert not any(("mapping" in n.lower() or "override" in n.lower())
                       for n in changes)
        for n,blob in resulting.items():
            if n.endswith(".py"):compile(blob,n,"exec")
        return {"version":VERSION,"sha256":hashlib.sha256(raw).hexdigest(),
          "size":len(raw),"changes":sorted(changes),"added":[NOTE],
          "unchanged":len(original)-len(changes),"receiver_tested":False,
          "production_published":False,"beta":True,
          "original_r75_sha":base_info["sha256"]}


if __name__=="__main__":
    print("R76_BUILD_OK",json.dumps(build(sys.argv[1] if len(sys.argv)>1 else None),
                                    sort_keys=True))
