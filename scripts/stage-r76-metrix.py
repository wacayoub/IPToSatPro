#!/usr/bin/env python3
"""Byte-verified R76 QA staging to dedicated beta branch; NO main publication."""
import base64
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import importlib.util
sp=importlib.util.spec_from_file_location("r76_build",ROOT/"scripts"/"build-r76-metrix-preview.py")
build=importlib.util.module_from_spec(sp);sp.loader.exec_module(build)
BRANCH="feature/r76-metrix-home-preview-b"
PAYLOAD=ROOT/"payload"/"r76-metrix-preview.b64"
MANIFEST=ROOT/"staging"/"r76-metrix-preview.update.json"
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/"+BRANCH+"/payload/r76-metrix-preview.b64"

def stage():
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        target=Path(td)/"package.ipk"
        result=build.build(target)
        raw=target.read_bytes()
        assert len(raw)==result["size"]
        assert hashlib.sha256(raw).hexdigest()==result["sha256"]
        PAYLOAD.parent.mkdir(parents=True,exist_ok=True)
        MANIFEST.parent.mkdir(parents=True,exist_ok=True)
        PAYLOAD.write_bytes(base64.encodebytes(raw))
        meta={"version":result["version"],"size":len(raw),
              "sha256":result["sha256"],"parts":[URL],
              "notes":"R76 Metrix OpenATV dashboard + Neo Dark Preview+ B beta. "
                      "HD/FHD native skins, real read-only dashboard diagnostics, "
                      "original player/monitor/mappings/key actions protected. "
                      "On-device Enigma2/video validation required.",
              "beta":True,"receiver_tested":False,"production_published":False,
              "installation_requires_explicit_flag":True}
        MANIFEST.write_text(json.dumps(meta,indent=2,ensure_ascii=False)+"\n")
        assert base64.b64decode(PAYLOAD.read_bytes())==raw
        assert json.loads(MANIFEST.read_text())["sha256"]==result["sha256"]
        print("R76_STAGED "+json.dumps({"sha256":result["sha256"],"size":len(raw),
               "version":result["version"],"parts":len(meta["parts"])},sort_keys=True))
        return result

if __name__=="__main__":stage()
