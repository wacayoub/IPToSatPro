#!/usr/bin/env python3
"""IPToSatPro R80 RC1 — nomination-index release candidate.

No scoring, sorting, GUI, player, mapping, metadata, source refresh or
core cache changes; passive postinst inherited from R76.14.
"""
import hashlib,importlib.util,json,sys,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]

def load(name,file):
 sp=importlib.util.spec_from_file_location(name,R/"scripts"/file)
 obj=importlib.util.module_from_spec(sp);sp.loader.exec_module(obj);return obj
base=load("r80_from_r7615","build-r7615-preview-index.py")
patch=load("r80_nomination_guards","r80_index_focus_patch.py")
pack=base.pack
VERSION=patch.VERSION
OLD=base.VERSION
P=base.P;CORE=base.CORE;PLUGIN=base.PLUGIN;UPDATER=base.UPDATER
SAFE_POSTINST=base.SAFE_POSTINST.replace(b"R76.15 Preview index beta installed",
                                       b"R80 RC1 index focus installed")
assert b"import_spec" not in SAFE_POSTINST
NOTE=P+"CHANGELOG-R80-RC1-INDEX-FOCUS.txt"
MANIFEST="https://raw.githubusercontent.com/wacayoub/IPToSatPro/release/r769-finalization-20261014/staging/r80-rc1-index-focus.update.json"

def build(destination=None):
 with tempfile.TemporaryDirectory() as td:
  old=Path(td)/"r7615.ipk"
  previous=base.build(old)
  assert previous["version"]==OLD
  assert previous["sha256"]=="c3991af773c6700c1aac0652f5027b27b4e1a91ff0820bf25e801e8d8488c468"
  ar=pack.unpack_ar(old.read_bytes())
  before=pack.members_from(ar["data.tar.gz"])
  control=pack.members_from(ar["control.tar.gz"])
  assert control["postinst"]==base.SAFE_POSTINST
  changes={CORE:patch.patch_core(before[CORE].decode("utf8")).encode("utf8")}
  plugin=before[PLUGIN].decode("utf8")
  old_version='PLUGIN_VERSION = "'+OLD+'"'
  assert plugin.count(old_version)==1
  changes[PLUGIN]=plugin.replace(old_version,'PLUGIN_VERSION = "'+VERSION+'"',1).encode("utf8")
  updater=before[UPDATER].decode("utf8")
  key='CURRENT_VERSION = "'+OLD+'"'
  prev_manifest="https://raw.githubusercontent.com/wacayoub/IPToSatPro/release/r769-finalization-20261014/staging/r7615-preview-index.update.json"
  assert updater.count(key)==1 and updater.count(prev_manifest)==1
  updater=updater.replace(key,'CURRENT_VERSION = "'+VERSION+'"',1)
  changes[UPDATER]=updater.replace(prev_manifest,MANIFEST,1).encode("utf8")
  assert set(changes)=={CORE,PLUGIN,UPDATER}
  ctrl=control["control"].decode("utf8")
  assert ctrl.count("Version: "+OLD)==1
  ar["control.tar.gz"]=pack.make_tar(ar["control.tar.gz"],{
   "control":ctrl.replace("Version: "+OLD,"Version: "+VERSION,1).encode("utf8"),
   "postinst":SAFE_POSTINST,
  })
  ar["data.tar.gz"]=pack.make_tar(ar["data.tar.gz"],changes,{
   NOTE:("R80 RC1 Preview ONLY: avoid unnecessary number, prefix and provider parsing; "
       "retain R76.15 prefiltered provider candidate selection and existing validated "
       "prefix index. Fall back to original scan for incomplete indexes "
       "or ambiguous short/numeric labels. Preserve scores, order, candidate "
       "caps, manual locks, IPTV player and AV. Receiver speed not yet measured.\n").encode("utf8")
  })
  dest=Path(destination) if destination else R/"iptosatpro-r80-rc1-index-focus.ipk"
  if dest.exists():dest.unlink()
  blob=pack.assemble(ar,dest)
  after=pack.members_from(pack.unpack_ar(blob)["data.tar.gz"])
  assert set(after)==set(before)|{NOTE}
  for name,val in before.items():
   assert after[name]==changes.get(name,val),name
  for name,val in after.items():
   if name.endswith(".py"):compile(val,name,"exec")
  resultcontrol=pack.members_from(pack.unpack_ar(blob)["control.tar.gz"])
  assert resultcontrol["postinst"]==SAFE_POSTINST
  assert not set(resultcontrol).intersection({"preinst","prerm","postrm"})
  return {"version":VERSION,"sha256":hashlib.sha256(blob).hexdigest(),
          "size":len(blob),"old_sha256":previous["sha256"],
          "changed":sorted(changes),"added":[NOTE],
          "production_published":False,"receiver_tested":False,"beta":True}

if __name__=="__main__":
 print("R80_RC1_BUILD",json.dumps(build(sys.argv[1] if len(sys.argv)>1 else None),sort_keys=True))
