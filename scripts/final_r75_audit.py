#!/usr/bin/env python3
"""Read-only final audit of the *real installable* R75 IPK, not mocked code.

Reports source-module changes, exact published payload identity, immutable
player path, core/monitor safeguards and default tuning evidence.
Never installs, modifies receiver settings or handles subscriber credentials.
"""
import hashlib
import importlib.util
import json
import re
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
def load(filename):
    spec=importlib.util.spec_from_file_location("r75_release_audit",ROOT/"scripts"/filename)
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

b=load("build-r75-smart-index.py")
pack=b.base.b.b.base.pack
with tempfile.TemporaryDirectory() as temporary:
    base_file=Path(temporary)/"r74.ipk"
    next_file=Path(temporary)/"r75.ipk"
    b.base.build(base_file)
    details=b.build(next_file)
    r74=pack.members_from(pack.unpack_ar(base_file.read_bytes())["data.tar.gz"])
    r75=pack.members_from(pack.unpack_ar(next_file.read_bytes())["data.tar.gz"])
    control=pack.members_from(pack.unpack_ar(next_file.read_bytes())["control.tar.gz"])
    manifest=json.loads((ROOT/"staging/r75-smart-index.update.json").read_text())
    ipk=next_file.read_bytes()

    changed=[p for p in r74 if r74[p]!=r75.get(p)]
    added=[p for p in r75 if p not in r74]
    removed=[p for p in r74 if p not in r75]
    expected_changed=sorted([b.PLUGIN,b.CORE,b.MONITOR,b.UPDATER])
    assert sorted(changed)==expected_changed,(changed,expected_changed)
    assert added==[b.CHANGELOG],added
    assert not removed,removed
    assert len(ipk)==manifest["size"],"Published size differs from reproducible build"
    digest=hashlib.sha256(ipk).hexdigest()
    assert digest==manifest["sha256"],"Published SHA differs from reproducible build"
    assert manifest["version"]==b.VERSION
    assert manifest["beta"] and not manifest["receiver_tested"]
    assert b"Version: "+b.VERSION.encode() in control["control"]

    for path,data in r75.items():
        assert ".." not in Path(path).parts and not path.startswith("/"),path
        if path.endswith(".py"):compile(data,path,"exec")
    assert r75.get(b.P+"player.py")==r74.get(b.P+"player.py")
    assert r75.get(b.P+"metadata_shadow.py")==r74.get(b.P+"metadata_shadow.py")
    core=r75[b.CORE].decode()
    monitor=r75[b.MONITOR].decode()
    plugin=r75[b.PLUGIN].decode()
    updater=r75[b.UPDATER].decode()
    must_have={
        "identity country / prefix":(core,["_R748_COUNTRY_LABELS","_r749_reordered_identity",
                                            "country_relation==\"CONFLICT\""]),
        "instant preview / manual":(plugin,["R7412_FAST_PREVIEW_SHORTLIST",
                                          "R7414_PREVIEW_FAST_SEED_MANUAL_LOCK",
                                          "R7415_FIRSTPAINT_GREEN_ANY_FOCUS"]),
        "FTA / UNMAP":(plugin,["R7416_UNMAP_CRYPT_ACCESS"]),
        "native SAT FTA":(monitor,["R7417_FTA_SIGNAL_NATIVE_GUARD"]),
        "bounded cancellable fuzzy":(monitor,["R7418_BG_CANCEL_FUZZY"]),
        "bounded scoring":(core,["R7418_BOUNDED_FUZZY",
                                 "R75_SMART_INDEX_MEMO"]),
        "negative result cache":(monitor,["R75_SMART_NEGATIVE_CACHE"]),
        "AAC / beIN":(monitor,["AUDIO_SAFE_PLAYER"]),
    }
    passed={}
    for label,(src,markers) in must_have.items():
        missing=[word for word in markers if word not in src]
        passed[label]="PASS" if not missing else "FAIL: "+repr(missing)
    # The published beta updater must never silently downgrade to R70 main.
    assert "feature/r75-smart-index-optimized/staging/r75-smart-index.update.json" in updater
    assert "candidate_budget=96" in monitor
    assert "candidate_budget = 192 if self._r71_worker_deep else 24" in plugin
    assert all(value=="PASS" for value in passed.values()),passed
    interesting=re.compile(r"(threshold|timeout|candidate_budget|cache|signal|auto.?lock|ConfigYesNo|ConfigSelection|ConfigInteger)",re.I)
    samples={}
    for name,src in [("plugin",plugin),("monitor",monitor),("core",core)]:
        hits=[{"line":i,"code":line.strip()[:150]}
              for i,line in enumerate(src.splitlines(),1)
              if interesting.search(line) and not line.lstrip().startswith("#")
              and any(k in line.lower() for k in ("default","threshold","candidate_budget","max_age","timeout","no_match"))]
        samples[name]=hits[:40]

    result={
        "package":b.VERSION,
        "published_sha256_verified":digest,
        "actual_ipk_bytes":len(ipk),
        "changed_modules":changed,
        "added":added,
        "removed":removed,
        "unchanged_modules":len(r74)-len(changed),
        "native_player_identical_to_baseline":True,
        "existing_user_mapping_files_modified":False,
        "protections":passed,
        "tested_on_receiver":False,
        "selected_default_evidence":samples,
    }
    print(json.dumps(result,indent=2,ensure_ascii=False))
    out=ROOT/"staging"/"final-r75-audit.json"
    out.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    print("FINAL_AUDIT_STATIC_PASS",len(r75),"package entries")
