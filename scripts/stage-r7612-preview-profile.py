#!/usr/bin/env python3
"""R76.12 profiling-only beta staging. NEVER installs on receiver or main."""
import base64
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

R=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r7612stage",R/"scripts/build-r7612-preview-profile.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
BRANCH="release/r769-finalization-20261014"
PAYLOAD=R/"payload/r7612-phase-profile.b64"
MANIFEST=R/"staging/r7612-phase-profile.update.json"
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/"+BRANCH+"/payload/r7612-phase-profile.b64"


def stage():
 with tempfile.TemporaryDirectory() as d:
  ipk=Path(d)/"r7612.ipk";meta=b.build(ipk)
  raw=ipk.read_bytes()
  assert hashlib.sha256(raw).hexdigest()==meta["sha256"]
  PAYLOAD.parent.mkdir(parents=True,exist_ok=True)
  MANIFEST.parent.mkdir(parents=True,exist_ok=True)
  PAYLOAD.write_bytes(base64.encodebytes(raw))
  m={
   "version":meta["version"],
   "size":meta["size"],"sha256":meta["sha256"],
   "parts":[URL],
   "notes":"R76.12 profiling beta: no matching/locking change; numeric timings for nomination, score, rescue and sorting in Preview. Passive opkg postinst no longer deletes import_spec or rebuilds caches. Receiver and AV not validated.",
   "beta":True,"receiver_tested":False,"production_published":False,
   "installation_requires_explicit_flag":True,
  }
  MANIFEST.write_text(json.dumps(m,indent=2)+"\n",encoding="utf8")
  assert base64.b64decode(PAYLOAD.read_bytes())==raw
  print("R7612_PHASE_PROFILER_STAGED",json.dumps(m,sort_keys=True))
  return meta


if __name__=="__main__":
 stage()
