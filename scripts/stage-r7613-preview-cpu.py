#!/usr/bin/env python3
"""Stage R76.13 preview CPU beta in testing branch only, never update main."""
import base64
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location("r7613pkg",ROOT/"scripts/build-r7613-preview-cpu.py")
b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
BRANCH="release/r769-finalization-20261014"
PAYLOAD=ROOT/"payload/r7613-preview-cpu.b64"
MANIFEST=ROOT/"staging/r7613-preview-cpu.update.json"
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/"+BRANCH+"/payload/r7613-preview-cpu.b64"


def stage():
 with tempfile.TemporaryDirectory() as t:
  target=Path(t)/"r7613.ipk"
  meta=b.build(target)
  data=target.read_bytes()
  assert meta["sha256"]==hashlib.sha256(data).hexdigest()
  PAYLOAD.parent.mkdir(parents=True,exist_ok=True)
  MANIFEST.parent.mkdir(parents=True,exist_ok=True)
  PAYLOAD.write_bytes(base64.encodebytes(data))
  manifest={
   "version":meta["version"],"size":meta["size"],"sha256":meta["sha256"],
   "parts":[URL],
   "notes":"Preview CPU-only optimization: indexed postings prefilter and reused fuzzy ratio. R76.12 phase profiler and passive package hook retained. Live player and manual maps untouched by code. Receiver not yet tested.",
   "beta":True,"receiver_tested":False,"production_published":False,
   "installation_requires_explicit_flag":True,
  }
  MANIFEST.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf8")
  assert base64.b64decode(PAYLOAD.read_bytes())==data
  print("R7613_STAGING_OK",json.dumps(manifest,sort_keys=True))
  return meta

if __name__=="__main__":
 stage()
