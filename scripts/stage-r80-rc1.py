#!/usr/bin/env python3
"""Stage R80 RC1 preview-index-only beta on testing branch; never install."""
import base64,hashlib,importlib.util,json,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r80rcpkg",R/"scripts/build-r80-rc1-index-focus.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
BRANCH="release/r769-finalization-20261014"
PAYLOAD=R/"payload/r80-rc1-index-focus.b64"
MANIFEST=R/"staging/r80-rc1-index-focus.update.json"
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/"+BRANCH+"/payload/r80-rc1-index-focus.b64"

def stage():
 with tempfile.TemporaryDirectory() as d:
  ipk=Path(d)/"r80-rc1.ipk";meta=b.build(ipk)
  raw=ipk.read_bytes()
  assert meta["sha256"]==hashlib.sha256(raw).hexdigest()
  PAYLOAD.parent.mkdir(parents=True,exist_ok=True)
  MANIFEST.parent.mkdir(parents=True,exist_ok=True)
  PAYLOAD.write_bytes(base64.encodebytes(raw))
  manifest={
   "version":meta["version"],"size":meta["size"],"sha256":meta["sha256"],
   "parts":[URL],
   "notes":"R80 RC1 Preview index finalization: lazy number, prefix and provider checks during candidate nomination. Based on R76.15 identical candidates, scoring and AV/UI. Receiver not tested.",
   "beta":True,"receiver_tested":False,"production_published":False,
   "installation_requires_explicit_flag":True,
  }
  MANIFEST.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf8")
  assert base64.b64decode(PAYLOAD.read_bytes())==raw
  print("R80_RC1_STAGED",json.dumps(manifest,sort_keys=True))
  return meta

if __name__=="__main__":
 stage()
