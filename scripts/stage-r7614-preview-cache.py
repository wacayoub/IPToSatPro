#!/usr/bin/env python3
"""Stage R76.14 parsecache beta in testing branch ONLY, no receiver installation."""
import base64,hashlib,importlib.util,json,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("build7614",R/"scripts/build-r7614-preview-cache.py")
b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
BRANCH="release/r769-finalization-20261014"
PAYLOAD=R/"payload/r7614-preview-cache.b64"
MANIFEST=R/"staging/r7614-preview-cache.update.json"
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/"+BRANCH+"/payload/r7614-preview-cache.b64"


def stage():
 with tempfile.TemporaryDirectory() as td:
  package=Path(td)/"r7614.ipk"
  meta=b.build(package);raw=package.read_bytes()
  assert meta["sha256"]==hashlib.sha256(raw).hexdigest()
  PAYLOAD.parent.mkdir(parents=True,exist_ok=True)
  MANIFEST.parent.mkdir(parents=True,exist_ok=True)
  PAYLOAD.write_bytes(base64.encodebytes(raw))
  m={
   "version":meta["version"],"size":meta["size"],"sha256":meta["sha256"],
   "parts":[URL],
   "notes":"Preview-only pure name parsing memoization with bounded in-memory LRU. Preserve all R76.13 rank and scoring bodies, complete catalogs, mappings and player. Beta not tested on Vu+ hardware.",
   "beta":True,"receiver_tested":False,"production_published":False,
   "installation_requires_explicit_flag":True
  }
  MANIFEST.write_text(json.dumps(m,indent=2)+"\n",encoding="utf8")
  assert base64.b64decode(PAYLOAD.read_bytes())==raw
  print("R7614_STAGED",json.dumps(m,sort_keys=True))
  return meta

if __name__=="__main__":
 stage()
