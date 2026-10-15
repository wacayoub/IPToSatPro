#!/usr/bin/env python3
"""Stage R76.15 preview-index-only beta on testing branch; never install."""
import base64,hashlib,importlib.util,json,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r7615pkg",R/"scripts/build-r7615-preview-index.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
BRANCH="release/r769-finalization-20261014"
PAYLOAD=R/"payload/r7615-preview-index.b64"
MANIFEST=R/"staging/r7615-preview-index.update.json"
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/"+BRANCH+"/payload/r7615-preview-index.b64"

def stage():
 with tempfile.TemporaryDirectory() as d:
  ipk=Path(d)/"r7615.ipk";meta=b.build(ipk)
  raw=ipk.read_bytes()
  assert meta["sha256"]==hashlib.sha256(raw).hexdigest()
  PAYLOAD.parent.mkdir(parents=True,exist_ok=True)
  MANIFEST.parent.mkdir(parents=True,exist_ok=True)
  PAYLOAD.write_bytes(base64.encodebytes(raw))
  manifest={
   "version":meta["version"],"size":meta["size"],"sha256":meta["sha256"],
   "parts":[URL],
   "notes":"R76.15 nominal Preview index rescue only. Avoid huge token posting sets; prefilter provider-family candidate scan against an already built prefix index when safe; fail open otherwise. R76.14 matching/scoring/AV/UI unchanged. Receiver not tested.",
   "beta":True,"receiver_tested":False,"production_published":False,
   "installation_requires_explicit_flag":True,
  }
  MANIFEST.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf8")
  assert base64.b64decode(PAYLOAD.read_bytes())==raw
  print("R7615_STAGED",json.dumps(manifest,sort_keys=True))
  return meta

if __name__=="__main__":
 stage()
