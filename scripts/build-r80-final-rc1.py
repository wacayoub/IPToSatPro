#!/usr/bin/env python3
"""Build IPToSatPro R80 release-candidate 1 from exact verified R76.15 binary.

Release-freeze approach: no SAT/IPTV nomination, scoring, media playback, theme,
mapping, manual lock or cache serialization changes in this build. Only package
version, updater metadata, passive postinst text and an audit note are updated.

Final approval requires fresh measurements and hardware AV test; building this
package is NOT a claim that the indexing latency is solved.
"""
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

R=Path(__file__).resolve().parents[1]

def load(name,file):
    sp=importlib.util.spec_from_file_location(name,R/"scripts"/file)
    module=importlib.util.module_from_spec(sp)
    sp.loader.exec_module(module)
    return module

baseline=load("r80_base_r7615","build-r7615-preview-index.py")
pack=baseline.pack
P=baseline.P
CORE=baseline.CORE
PLUGIN=baseline.PLUGIN
UPDATER=baseline.UPDATER
OLD=baseline.VERSION
VERSION="1.0.46-r80-final-rc1"
BASE_SHA="c3991af773c6700c1aac0652f5027b27b4e1a91ff0820bf25e801e8d8488c468"
NOTE=P+"R80-RELEASE-CANDIDATE.md"
MANIFEST="https://raw.githubusercontent.com/wacayoub/IPToSatPro/release/r80-final-candidate-20261015/staging/r80-final-rc1.update.json"
BEFORE_MANIFEST="https://raw.githubusercontent.com/wacayoub/IPToSatPro/release/r769-finalization-20261014/staging/r7615-preview-index.update.json"
POSTINST=baseline.SAFE_POSTINST.replace(
    b"R76.15 Preview index beta installed",
    b"R80 release candidate installed")
assert b"R80 release candidate installed" in POSTINST
assert b"import_spec" not in POSTINST and b"rm " not in POSTINST and b"mv " not in POSTINST


def build(destination=None):
    with tempfile.TemporaryDirectory() as temp:
        orig=Path(temp)/"r7615.ipk"
        meta=baseline.build(orig)
        assert meta["version"]==OLD and meta["sha256"]==BASE_SHA
        ar=pack.unpack_ar(orig.read_bytes())
        prior=pack.members_from(ar["data.tar.gz"])
        ctrl=pack.members_from(ar["control.tar.gz"])
        assert ctrl["postinst"]==baseline.SAFE_POSTINST
        assert not {"preinst","prerm","postrm"}.intersection(ctrl)
        before_plugin=prior[PLUGIN].decode("utf8")
        old='PLUGIN_VERSION = "'+OLD+'"'
        assert before_plugin.count(old)==1
        new_plugin=before_plugin.replace(old,'PLUGIN_VERSION = "'+VERSION+'"',1)
        old_updater=prior[UPDATER].decode("utf8")
        updater_marker='CURRENT_VERSION = "'+OLD+'"'
        assert old_updater.count(updater_marker)==1
        assert old_updater.count(BEFORE_MANIFEST)==1
        new_updater=old_updater.replace(updater_marker,'CURRENT_VERSION = "'+VERSION+'"',1)
        new_updater=new_updater.replace(BEFORE_MANIFEST,MANIFEST,1)
        changes={PLUGIN:new_plugin.encode("utf8"),UPDATER:new_updater.encode("utf8")}
        c=ctrl["control"].decode("utf8")
        assert c.count("Version: "+OLD)==1
        ar["control.tar.gz"]=pack.make_tar(ar["control.tar.gz"],{
            "control":c.replace("Version: "+OLD,"Version: "+VERSION,1).encode("utf8"),
            "postinst":POSTINST,
        })
        note=(
            "# IPToSatPro R80 — Release Candidate 1\n\n"
            "Source: byte-exact R76.15 index nomination beta. No executable "
            "matcher, ranker, preview GUI, media reader, mapper, config, or "
            "catalog files were changed by this R80 release-freeze build.\n\n"
            "R80 RC1 is not a performance fix beyond R76.15. "
            "Latency go/no-go is pending on the Vu+ hardware. "
            "No automatic opkg installs, migration or EPG operations. "
            "Use a separate SHA-verified download installer with a persistent "
            "backup and code-only rollback. Manual TV video/audio and mapping "
            "checks are mandatory before any final promotion.\n"
        )
        ar["data.tar.gz"]=pack.make_tar(ar["data.tar.gz"],changes,{NOTE:note.encode()})
        dst=Path(destination) if destination else R/"iptosatpro-r80-final-rc1.ipk"
        if dst.exists():dst.unlink()
        blob=pack.assemble(ar,dst)
        after=pack.members_from(pack.unpack_ar(blob)["data.tar.gz"])
        assert set(after)==set(prior)|{NOTE}
        for path,raw in prior.items():
            assert after[path]==changes.get(path,raw),path
        assert after[CORE]==prior[CORE],"R80 must preserve matching byte-for-byte"
        for path,data in after.items():
            if path.endswith(".py"):
                compile(data,path,"exec")
        actual=pack.members_from(pack.unpack_ar(blob)["control.tar.gz"])
        assert actual["postinst"]==POSTINST
        return {
            "version":VERSION,"sha256":hashlib.sha256(blob).hexdigest(),
            "size":len(blob),"source_sha256":BASE_SHA,
            "changed":sorted(changes),"added":[NOTE],
            "core_byte_identical":True,"player_byte_identical":True,
            "production_published":False,"receiver_tested":False,
            "index_target_met":False,"beta":True,
        }


if __name__=="__main__":
    print("R80_RC1_BUILD",json.dumps(build(sys.argv[1] if len(sys.argv)>1 else None),sort_keys=True))
