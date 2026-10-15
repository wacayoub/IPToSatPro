#!/usr/bin/env python3
"""R76.14 Preview parsing-cache beta, staged from exact R76.13 binary.

This package adds only bounded memoization to pure immutable-output helpers.
No video/audio player, mapping, SAT-to-IPTV matching policy, scoring body,
candidate order, catalogs or user files are changed by this patch.
"""
import hashlib,importlib.util,json,sys,tempfile
from pathlib import Path

R=Path(__file__).resolve().parents[1]
def mod(name,fn):
 s=importlib.util.spec_from_file_location(name,R/"scripts"/fn)
 m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

base=mod("r7614_from_r7613","build-r7613-preview-cpu.py")
fix=mod("r7614_cache","r7614_preview_cache_patch.py")
pack=base.pack
VERSION=fix.VERSION
OLD=base.VERSION
CORE=base.CORE
PLUGIN=base.PLUGIN
UPDATER=base.UPDATER
P=base.P
MANIFEST="https://raw.githubusercontent.com/wacayoub/IPToSatPro/release/r769-finalization-20261014/staging/r7614-preview-cache.update.json"
NOTE=P+"CHANGELOG-R7614-PREVIEW-PARSE-CACHE.txt"
SAFE_POSTINST=base.base.SAFE_POSTINST.replace(b"R76.12 profiling beta installed",b"R76.14 Preview cache beta installed")
assert b"rm " not in SAFE_POSTINST and b"mv " not in SAFE_POSTINST and b"import_spec" not in SAFE_POSTINST


def build(destination=None):
 with tempfile.TemporaryDirectory() as td:
  old=Path(td)/"r7613.ipk"
  previous=base.build(old)
  assert previous["version"]==OLD
  assert previous["sha256"]=="817f797b1a60f5b146071366e2dc06a1de6f4c711fc2fbfd5937360e88989c76"
  ar=pack.unpack_ar(old.read_bytes())
  before=pack.members_from(ar["data.tar.gz"])
  control=pack.members_from(ar["control.tar.gz"])
  changes={CORE:fix.patch_core(before[CORE].decode("utf8")).encode("utf8")}
  old_plugin=before[PLUGIN].decode("utf8")
  k='PLUGIN_VERSION = "'+OLD+'"'
  assert old_plugin.count(k)==1
  changes[PLUGIN]=old_plugin.replace(k,'PLUGIN_VERSION = "'+VERSION+'"',1).encode("utf8")
  updater=before[UPDATER].decode("utf8")
  k='CURRENT_VERSION = "'+OLD+'"'
  oldmanifest="https://raw.githubusercontent.com/wacayoub/IPToSatPro/release/r769-finalization-20261014/staging/r7613-preview-cpu.update.json"
  assert updater.count(k)==1 and updater.count(oldmanifest)==1
  updater=updater.replace(k,'CURRENT_VERSION = "'+VERSION+'"',1)
  updater=updater.replace(oldmanifest,MANIFEST,1)
  changes[UPDATER]=updater.encode("utf8")
  assert set(changes)=={CORE,PLUGIN,UPDATER}
  assert control["postinst"]==base.base.SAFE_POSTINST
  ctrl=control["control"].decode("utf8")
  assert ctrl.count("Version: "+OLD)==1
  ar["control.tar.gz"]=pack.make_tar(ar["control.tar.gz"],{
    "control":ctrl.replace("Version: "+OLD,"Version: "+VERSION,1).encode("utf8"),
    "postinst":SAFE_POSTINST,
  })
  ar["data.tar.gz"]=pack.make_tar(ar["data.tar.gz"],changes,{
   NOTE:("R76.14 beta: seven pure, immutable-return Preview parser helpers "
      "use in-memory bounded LRU 2048. Underlying helper and matcher "
      "function bodies, explicit country safety, scoring, quality policy, "
      "channel caps/order, EPG, playback, and manual mappings unchanged. "
      "No receiver performance gain yet validated.\n").encode("utf8")
  })
  target=Path(destination) if destination else R/"iptosatpro-r7614-preview-cache-beta.ipk"
  if target.exists():target.unlink()
  blob=pack.assemble(ar,target)
  after=pack.members_from(pack.unpack_ar(blob)["data.tar.gz"])
  assert set(after)==set(before)|{NOTE}
  for path,raw in before.items():
   assert after[path]==changes.get(path,raw),path
  for path,raw in after.items():
   if path.endswith(".py"):compile(raw,path,"exec")
  ctrl2=pack.members_from(pack.unpack_ar(blob)["control.tar.gz"])
  assert ctrl2["postinst"]==SAFE_POSTINST
  return {"version":VERSION,"size":len(blob),"sha256":hashlib.sha256(blob).hexdigest(),
          "old_sha256":previous["sha256"],"changed":sorted(changes),
          "added":[NOTE],"production_published":False,"receiver_tested":False,"beta":True}

if __name__=="__main__":
 print("R7614_BUILD",json.dumps(build(sys.argv[1] if len(sys.argv)>1 else None),sort_keys=True))
