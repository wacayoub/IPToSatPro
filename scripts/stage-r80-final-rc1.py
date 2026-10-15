#!/usr/bin/env python3
"""Stage R80 RC1 on private release-candidate branch; NEVER publish production."""
import base64,hashlib,importlib.util,json,tempfile
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r80_candidate",R/"scripts/build-r80-final-rc1.py")
builder=importlib.util.module_from_spec(sp);sp.loader.exec_module(builder)
BRANCH="release/r80-final-candidate-20261015"
PAYLOAD=R/"payload/r80-final-rc1.b64"
MANIFEST=R/"staging/r80-final-rc1.update.json"
URL="https://raw.githubusercontent.com/wacayoub/IPToSatPro/"+BRANCH+"/payload/r80-final-rc1.b64"

def stage():
    with tempfile.TemporaryDirectory() as tmp:
        artifact=Path(tmp)/"r80.ipk"
        info=builder.build(artifact);raw=artifact.read_bytes()
        assert hashlib.sha256(raw).hexdigest()==info["sha256"]
        PAYLOAD.parent.mkdir(parents=True,exist_ok=True)
        MANIFEST.parent.mkdir(parents=True,exist_ok=True)
        PAYLOAD.write_bytes(base64.encodebytes(raw))
        manifest={
            "version":info["version"],"sha256":info["sha256"],"size":info["size"],
            "source_version":builder.OLD,"source_sha256":info["source_sha256"],
            "parts":[URL],
            "notes":"R80 RC1: freeze exact R76.15 nominee/scorer/player; no changes to algorithms. Safe passive postinst. Requires physical receiver performance, candidate mapping and AV acceptance before promotion.",
            "production_published":False,"receiver_tested":False,
            "index_target_met":False,"beta":True,
            "installation_requires_explicit_flag":True,
        }
        MANIFEST.write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n",encoding="utf8")
        assert base64.b64decode(PAYLOAD.read_bytes())==raw
        print("R80_RC1_STAGED",json.dumps(manifest,sort_keys=True))
        return info

if __name__=="__main__":
    stage()
