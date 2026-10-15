#!/usr/bin/env python3
"""R76.13 indexed normal-Preview CPU optimization from safe R76.12 baseline.

Offline build. No receiver install; no changes to user mappings/caches.
"""
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def load(name,fn):
 s=importlib.util.spec_from_file_location(name,ROOT/"scripts"/fn)
 m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

base=load("r7612base_r7613","build-r7612-preview-profile.py")
fix=load("r7613patch","r7613_preview_cpu_patch.py")
pack=base.pack
VERSION=fix.NAME
OLD=base.VERSION
CORE=base.CORE
PLUGIN=base.PLUGIN
UPDATER=base.UPDATER
P=base.P
NOTE=P+"CHANGELOG-R7613-PREVIEW-CPU.txt"
MANIFEST="https://raw.githubusercontent.com/wacayoub/IPToSatPro/release/r769-finalization-20261014/staging/r7613-preview-cpu.update.json"


def build(destination=None):
 with tempfile.TemporaryDirectory() as td:
  old=Path(td)/"r7612.ipk"
  previous=base.build(old)
  assert previous["version"]==OLD
  assert previous["sha256"]=="773bbbba6c32be3b1f61a21c773593f6ff5d04382beeffc341e38961d5b3a911"
  ar=pack.unpack_ar(old.read_bytes())
  before=pack.members_from(ar["data.tar.gz"])
  control=pack.members_from(ar["control.tar.gz"])
  changes={}
  changes[CORE]=fix.patch_core(before[CORE].decode("utf8")).encode("utf8")
  plugin=before[PLUGIN].decode("utf8")
  old_version='PLUGIN_VERSION = "'+OLD+'"'
  assert plugin.count(old_version)==1
  changes[PLUGIN]=plugin.replace(old_version,'PLUGIN_VERSION = "'+VERSION+'"',1).encode("utf8")
  updater=before[UPDATER].decode("utf8")
  ver='CURRENT_VERSION = "'+OLD+'"'
  old_manifest="https://raw.githubusercontent.com/wacayoub/IPToSatPro/release/r769-finalization-20261014/staging/r7612-phase-profile.update.json"
  assert updater.count(ver)==1 and updater.count(old_manifest)==1
  updater=updater.replace(ver,'CURRENT_VERSION = "'+VERSION+'"',1)
  updater=updater.replace(old_manifest,MANIFEST,1)
  changes[UPDATER]=updater.encode("utf8")
  assert set(changes)=={CORE,PLUGIN,UPDATER}
  assert "postinst" in control and control["postinst"]==base.SAFE_POSTINST
  ctrl=control["control"].decode("utf8")
  assert ctrl.count("Version: "+OLD)==1
  ar["control.tar.gz"]=pack.make_tar(ar["control.tar.gz"],{
    "control":ctrl.replace("Version: "+OLD,"Version: "+VERSION,1).encode("utf8"),
    # Retain R76.12 postinst behavior: passive, no user mutations.
    "postinst":control["postinst"],
  })
  ar["data.tar.gz"]=pack.make_tar(ar["data.tar.gz"],changes,{
    NOTE:("R76.13 scoped Preview-CPU beta, based on R76.12. Preserve live "
          "SmartMatch and playback. Use existing indexed token postings "
          "to prefilter Preview shortlist; verify same norm tokens before "
          "admitting a candidate. Reuse identical SequenceMatcher ratio "
          "inside Preview scorer. No streaming, mapping or manual-lock "
          "changes; no runtime receiver speed verified.\n").encode()
  })
  destination=Path(destination) if destination else ROOT/"iptosatpro-r7613-preview-cpu-beta.ipk"
  if destination.exists():destination.unlink()
  blob=pack.assemble(ar,destination)
  after=pack.members_from(pack.unpack_ar(blob)["data.tar.gz"])
  assert set(after)==set(before)|{NOTE}
  for name,raw in before.items():
   assert after[name]==changes.get(name,raw),name
  for name,raw in after.items():
   if name.endswith(".py"):
    compile(raw,name,"exec")
  actual_control=pack.members_from(pack.unpack_ar(blob)["control.tar.gz"])
  assert actual_control["postinst"]==base.SAFE_POSTINST
  return {"version":VERSION,"sha256":hashlib.sha256(blob).hexdigest(),
          "size":len(blob),"old_sha256":previous["sha256"],
          "changed":sorted(changes),"added":[NOTE],"production_published":False,
          "receiver_tested":False,"beta":True}


if __name__=="__main__":
 print("R7613_CPU_BUILD",json.dumps(build(sys.argv[1] if len(sys.argv)>1 else None),sort_keys=True))
