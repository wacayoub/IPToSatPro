#!/usr/bin/env python3
"""R76.12 numeric-only Preview profiler beta, fully reconstructed from R76.11.

- No ranking, lock, manual mapping, candidate, IPTV player, GUI/skin changes.
- Harden inherited R62 postinst hook: passive message only; do not delete,
  chmod, migrate or rewrite user configuration and catalog caches on install.
- Stage only, never publish main, never install receiver.
"""
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

R=Path(__file__).resolve().parents[1]


def module(name,file):
    s=importlib.util.spec_from_file_location(name,R/"scripts"/file)
    v=importlib.util.module_from_spec(s)
    s.loader.exec_module(v)
    return v

base=module("r7612_old","build-r7611-preview-cold.py")
fix=module("r7612_profile","r7612_preview_stage_profile_patch.py")
pack=base.pack
VERSION=fix.VERSION
OLD=base.VERSION
P=base.P
CORE=base.CORE
PLUGIN=base.PLUGIN
UPDATER=base.UPDATER
MANIFEST="https://raw.githubusercontent.com/wacayoub/IPToSatPro/release/r769-finalization-20261014/staging/r7612-phase-profile.update.json"
NOTE=P+"CHANGELOG-R7612-PHASE-PROFILER.txt"

SAFE_POSTINST="""#!/bin/sh
# R7612 passive install hook: no user files or backups touched.
printf '%s\\n' 'IPToSatPro R76.12 profiling beta installed; GUI restart manually via OpenATV.'
exit 0
""".encode("utf8")


def build(destination=None):
    with tempfile.TemporaryDirectory() as td:
        old=Path(td)/"r7611.ipk"
        meta=base.build(old)
        assert meta["version"]==OLD
        ar=pack.unpack_ar(old.read_bytes())
        before=pack.members_from(ar["data.tar.gz"])
        control=pack.members_from(ar["control.tar.gz"])
        assert "postinst" in control and b"1.0.46-r62" in control["postinst"]
        changes={}
        changes[CORE]=fix.patch_core(before[CORE].decode("utf8")).encode("utf8")
        plugin=fix.patch_plugin(before[PLUGIN].decode("utf8"))
        x='PLUGIN_VERSION = "'+OLD+'"'
        assert plugin.count(x)==1
        changes[PLUGIN]=plugin.replace(x,'PLUGIN_VERSION = "'+VERSION+'"',1).encode("utf8")
        updater=before[UPDATER].decode("utf8")
        old_ver='CURRENT_VERSION = "'+OLD+'"'
        assert updater.count(old_ver)==1
        updater=updater.replace(old_ver,'CURRENT_VERSION = "'+VERSION+'"',1)
        old_manifest="https://raw.githubusercontent.com/wacayoub/IPToSatPro/release/r769-finalization-20261014/staging/r7611-preview-cold.update.json"
        assert updater.count(old_manifest)==1
        updater=updater.replace(old_manifest,MANIFEST,1)
        changes[UPDATER]=updater.encode("utf8")
        assert set(changes)=={CORE,PLUGIN,UPDATER}
        ctrl=control["control"].decode("utf8")
        assert ctrl.count("Version: "+OLD)==1
        assert set(control).intersection({"preinst","postrm","prerm"})==set()
        ar["control.tar.gz"]=pack.make_tar(ar["control.tar.gz"],{
            "control":ctrl.replace("Version: "+OLD,"Version: "+VERSION,1).encode("utf8"),
            "postinst":SAFE_POSTINST,
        })
        ar["data.tar.gz"]=pack.make_tar(ar["data.tar.gz"],changes,{
            NOTE:("R76.12 profiling-only beta: exact R76.11 ranked list, limits, "
                  "scores, cache and candidate behavior; new PREVIEW_STAGE numeric "
                  "logs show candidate nomination, scoring, missing-role rescue "
                  "and sorting time in ms. Inherited R62 postinst replaced with "
                  "passive hook: does not delete import_spec.json, mutate settings "
                  "or rebuild caches. No verified TV picture/audio results.\n").encode("utf8")})
        destination=Path(destination) if destination else R/"iptosatpro-r7612-phase-profile-beta.ipk"
        if destination.exists():
            destination.unlink()
        blob=pack.assemble(ar,destination)
        installed=pack.members_from(pack.unpack_ar(blob)["data.tar.gz"])
        assert set(installed)==set(before)|{NOTE}
        for k in before:
            assert installed[k]==changes.get(k,before[k]),k
        for k,data in installed.items():
            if k.endswith(".py"):
                compile(data,k,"exec")
        actual_control=pack.members_from(pack.unpack_ar(blob)["control.tar.gz"])
        assert actual_control["postinst"]==SAFE_POSTINST
        assert b"rm " not in SAFE_POSTINST
        assert b"mv " not in SAFE_POSTINST
        assert b"import_spec" not in SAFE_POSTINST
        return {
            "version":VERSION,
            "sha256":hashlib.sha256(blob).hexdigest(),
            "size":len(blob),
            "old_sha256":meta["sha256"],
            "changed":sorted(changes),
            "added":[NOTE],
            "production_published":False,
            "receiver_tested":False,
            "beta":True,
        }


if __name__=="__main__":
    print("R7612_BUILD",json.dumps(build(sys.argv[1] if len(sys.argv)>1 else None),sort_keys=True))
