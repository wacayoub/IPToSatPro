#!/usr/bin/env python3
"""R72.6: permit exact RO Digi 24 HD IPTV on confirmed SAT no-lock only.

Reads SHA-pinned R72.5 package and modifies just monitor._build_candidate_plan
with *one* protected ALLOWED decision for 71/100 Digi 24 in the Romanian
original feed. Does not lower global threshold (82), change core matching,
preview/audio, player, PAT, FTA fallback, quality or provider priority.
"""
import ast,base64,hashlib,importlib.util,json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r725",R/"scripts/build-r725-fuzzy.py")
base=importlib.util.module_from_spec(sp);sp.loader.exec_module(base)
pack=base.pack; P=base.P; MONITOR=base.MONITOR;PLUGIN=base.PLUGIN;UPDATER=base.UPDATER
BASE=R/"payload/r725-fuzzy-stability.b64"
PIN_SIZE=404226
PIN_SHA="f4b1c1ab8a23ced1856e95b2481b70e6fbb245af3cd5b36fb0d63a3d3a5983f5"
OLD="1.0.46-r72.5-fuzzy-stability-beta"
NEW="1.0.46-r72.6-digi24-safe-beta"
CHANGELOG=P+"CHANGELOG-r726-DIGI24-SAFE.txt"

def one(text,old,new):
    assert text.count(old)==1,(old[:180],text.count(old))
    return text.replace(old,new,1)

def patch_monitor(binary):
    src=binary.decode()
    old='''            decision = match_decision(score, details, threshold)
            if decision not in ("SAFE", "ALLOWED"):
                # REVIEW candidates stay visible in Preview/Manual Mapping but are never
                # auto-switched. Only SAFE/ALLOWED enters the automatic fallback plan.
                continue'''
    new='''            decision = match_decision(score, details, threshold)
            if decision not in ("SAFE", "ALLOWED"):
                # R72.6: very narrow controlled Romanian broadcaster exception.
                # The real Digi 24 case: SAT "Digi 24" on a wrong/inferred
                # orbital-country (Telekom Srbija at 23.5E); IPTV explicitly
                # "RO: DIGI 24 HD". Score 71 is below the global 82, but the
                # service identity and explicit country prefix are exact.
                # Never bypass hard reject (number, feed/audio, variant), and
                # never apply without a DEFINITE failed tuner/no SAT lock.
                # Manual rejected IDs, health and all resolution guards remain.
                sat_label = str(self.current_match_name or self.current_sat_name or "").strip().upper()
                ip_label = str(ch.get("name") or "").strip().upper()
                no_sat_state = str(self.tuner_state or "").upper().strip()
                review_reason = str((details or {}).get("review_reason") or "").lower()
                deny_reason = str((details or {}).get("reject_reason") or "").strip()
                market = str(ch.get("market") or "").upper().strip()
                lang = str(ch.get("language") or "").upper().strip()
                try:
                    no_signal_enabled = bool(self.cfg.fallback_no_signal.value)
                except Exception:
                    no_signal_enabled = False
                ro_digi24 = (
                    sat_label in ("DIGI 24", "DIGI 24 HD")
                    and ip_label in ("RO: DIGI 24 HD", "RO: DIGI 24 FHD")
                    and market in ("", "RO")
                    and lang in ("", "RO")
                    and not deny_reason
                    and (not review_reason or ("market" in review_reason or "bouquet" in review_reason))
                    and 65.0 <= float(score) < float(threshold)
                    and no_signal_enabled
                    and no_sat_state in ("TUNE_FAILED", "FAILED", "NO_SIGNAL", "NO_LOCK", "NOT_LOCKED", "UNLOCKED")
                    and not self.fallback_active
                    and bool(self.current_sat_ref_string)
                    and self._same_sat_still_playing()
                )
                if ro_digi24:
                    decision = "ALLOWED"
                    self._log("DIGI24_RO_NO_SIGNAL_ALLOW",
                              "sat='Digi 24' iptv='%s' score=%.1f global_threshold=%.1f no_lock=1" %
                              (ch.get("name",""), float(score), float(threshold)))
                else:
                    # Ordinary REVIEW stays manual; hard REJECT never auto-plays.
                    continue'''
    src=one(src,old,new)
    tree_old=ast.parse(binary)
    tree_new=ast.parse(src)
    def funcs(tree):
        c=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="SatFallbackMonitor")
        return {x.name:ast.dump(x,include_attributes=False) for x in c.body if isinstance(x,ast.FunctionDef)}
    a,b=funcs(tree_old),funcs(tree_new)
    assert set(a)==set(b)
    assert {k for k in a if a[k]!=b[k]}=={"_build_candidate_plan"}
    compile(src,MONITOR,"exec")
    return src.encode()

def build(target=None):
    raw=base64.b64decode(BASE.read_bytes())
    assert len(raw)==PIN_SIZE and hashlib.sha256(raw).hexdigest()==PIN_SHA
    pkg=pack.unpack_ar(raw)
    old=pack.members_from(pkg["data.tar.gz"])
    controls=pack.members_from(pkg["control.tar.gz"])
    changes={MONITOR:patch_monitor(old[MONITOR])}
    for path,key in ((PLUGIN,"PLUGIN_VERSION"),(UPDATER,"CURRENT_VERSION")):
        code=old[path].decode();ver='%s = "%s"'%(key,OLD)
        assert code.count(ver)==1
        changes[path]=code.replace(ver,'%s = "%s"'%(key,NEW),1).encode()
    ctrl=controls["control"].decode();assert ctrl.count("Version: "+OLD)==1
    newctrl=ctrl.replace("Version: "+OLD,"Version: "+NEW,1).encode()
    additions={CHANGELOG:(
        "R72.6 BETA: Only confirmed no-SAT-lock Digi 24 HD Romanian stream "
        "(RO: DIGI 24 HD/FHD) with safe identity, RO metadata and score>=65 "
        "can be ALLOWED when below global threshold 82. All hard rejects, "
        "manual user exclusions, quality, stream-health, market and audio "
        "rules remain. R72.5 fuzzy stability, Fast Zap and player unchanged. "
        "Receiver not yet tested; this only permits a probe, does not verify "
        "the actual content of the stream.\n").encode()}
    pkg["data.tar.gz"]=pack.make_tar(pkg["data.tar.gz"],changes,additions)
    pkg["control.tar.gz"]=pack.make_tar(pkg["control.tar.gz"],{"control":newctrl})
    p=Path(target) if target else R/"r726-digi24-safe-beta.ipk"
    if p.exists():p.unlink()
    result=pack.assemble(pkg,p)
    after=pack.members_from(pack.unpack_ar(result)["data.tar.gz"])
    ca=pack.members_from(pack.unpack_ar(result)["control.tar.gz"])
    assert set(after)==set(old)|set(additions)
    for f,b in old.items():assert after[f]==changes.get(f,b),f
    for f,b in controls.items():assert ca[f]==(newctrl if f=="control" else b),f
    for f,b in after.items():
        if f.endswith(".py"):compile(b,f,"exec")
    info={"version":NEW,"size":len(result),"sha256":hashlib.sha256(result).hexdigest(),
       "changed":sorted(changes),"monitor_methods_changed":["_build_candidate_plan"],
       "protected_files":len(old)-len(changes),"global_threshold_unchanged":True,
       "receiver_tested":False,"production_published":False}
    print("R726_DIGI24_BUILD_OK",json.dumps(info,sort_keys=True))
    return info
if __name__=="__main__":build(sys.argv[1] if len(sys.argv)>1 else None)
