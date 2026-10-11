#!/usr/bin/env python3
"""R72.5 prevent repeated evTuneFailed from starving fuzzy candidate matching.

Based on checksum-pinned R72.4 shipped package. Changes ONLY:
  * coalesce identical in-flight background searches for the same SAT service
  * give the fuzzy worker time to complete even when evTuneFailed repeats
  * short (45s) no-match repeat cooldown scoped by service, current zap, catalog
Playback, PAT guard, Home, resolver scoring, languages and user locks are untouched.
"""
import ast,base64,hashlib,importlib.util,json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r724",R/"scripts/build-r724-zero-signal.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
pack=b.pack;P=b.P;MONITOR=b.MONITOR;PLUGIN=b.PLUGIN;UPDATER=b.UPDATER
BASE=R/"payload/r724-zero-signal.b64"
PIN_SIZE=403344
PIN_SHA="fe779fc4a2c95bea7166c4ce168e18b76416959d9e51b247fdbc809d1b737194"
OLD="1.0.46-r72.4-zero-signal-beta"
NEW="1.0.46-r72.5-fuzzy-stability-beta"
CHANGELOG=P+"CHANGELOG-r725-FUZZY-STABILITY.txt"

def replace_once(s,a,b):
    n=s.count(a)
    if n!=1:raise AssertionError("R72.5 exact-match anchor drift %s hits=%d"%(a[:115],n))
    return s.replace(a,b,1)

def patch_monitor(raw):
    src=raw.decode("utf-8")
    # Preserve same identity for pending job. A repeated tuner failure must NOT
    # bump generation while current fuzzy thread is still ranking.
    anchor='''        self.smartmatch_generation += 1
        generation = int(self.smartmatch_generation)
        sat_ref = str(self.current_sat_ref_string or "")
        catalog = self.catalog
        languages = list(self._user_languages() or [])
        context = dict(self.sat_context or {})
        name = str(match_name or "")
        qmode = str(quality_mode or "best")
        stage = "fuzzy" if str(stage) == "fuzzy" else "fast"
        self.smartmatch_pending = (generation, sat_ref, name, qmode, stage)'''
    patch='''        sat_ref = str(self.current_sat_ref_string or "")
        catalog = self.catalog
        name = str(match_name or "")
        qmode = str(quality_mode or "best")
        stage = "fuzzy" if str(stage) == "fuzzy" else "fast"

        # R72.5: Enigma2 may emit evTuneFailed again every ~5s on an unavailable
        # transponder. Reusing the SAME pending worker prevents an endless sequence
        # of generation invalidations, which previously caused fast=0, fuzzy=START,
        # fast=0, fuzzy=START, ... without any fuzzy= DONE or NO_MATCH.
        pending = self.smartmatch_pending
        if isinstance(pending, (tuple, list)) and len(pending) >= 5:
            same_job = (str(pending[1]) == sat_ref and str(pending[2]) == name
                        and str(pending[3]) == qmode)
            higher_stage_inflight = str(pending[4]) == "fuzzy" and stage == "fast"
            if same_job and (str(pending[4]) == stage or higher_stage_inflight):
                self._log("MATCH_BG_REUSE",
                          "sat='%s' requested=%s already=%s (no restart)" %
                          (self.current_sat_name, stage, pending[4]))
                if self.smartmatch_result is not None:
                    try: self.smartmatch_timer.start(1, True)
                    except Exception: pass
                return

        # Once fuzzy actually finished with NO_MATCH, do not redo CPU-intensive
        # scoring every 5s on a DVB transponder that keeps emitting evTuneFailed.
        # Next genuine zap or new catalog instance invalidates this short cooldown.
        cooldown_key = (sat_ref, id(catalog), getattr(self, "current_sat_started_at", 0))
        if (stage == "fast" and getattr(self, "_r725_no_match_key", None) == cooldown_key
                and time.monotonic() < float(getattr(self, "_r725_no_match_until", 0) or 0)):
            self.play_result = "NO MATCH"
            self._set_state("NO_MATCH",
                            "No safe IPTV match; wait briefly or use Manual Mapping",
                            "do not repeat fuzzy scoring")
            self._log("MATCH_NO_MATCH_REUSE", "sat='%s' cached negative match; no new worker" %
                      self.current_sat_name)
            return

        self.smartmatch_generation += 1
        generation = int(self.smartmatch_generation)
        languages = list(self._user_languages() or [])
        context = dict(self.sat_context or {})
        self.smartmatch_pending = (generation, sat_ref, name, qmode, stage)'''
    src=replace_once(src,anchor,patch)
    no_match='''            self.play_result = "NO MATCH"
            self._set_state("NO_MATCH", "No safe IPTV candidate satisfies context/resolution policy", "keep SAT black")'''
    new_no_match='''            self.play_result = "NO MATCH"
            if stage == "fuzzy":
                self._r725_no_match_key = (
                    sat_ref, id(self.catalog), getattr(self, "current_sat_started_at", 0))
                self._r725_no_match_until = time.monotonic() + 45.0
            self._set_state("NO_MATCH", "No safe IPTV candidate satisfies context/resolution policy", "keep SAT black")'''
    src=replace_once(src,no_match,new_no_match)
    orig_tree=ast.parse(raw.decode())
    new_tree=ast.parse(src)
    def functions(tree):
        c=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="SatFallbackMonitor")
        return {x.name:ast.dump(x,include_attributes=False) for x in c.body if isinstance(x,ast.FunctionDef)}
    prev,now=functions(orig_tree),functions(new_tree)
    assert set(prev)==set(now)
    assert {k for k in prev if now[k]!=prev[k]} == {"_queue_background_smartmatch","_smartmatch_poll"}
    compile(src,MONITOR,"exec")
    return src.encode()

def build(path=None):
    raw=base64.b64decode(BASE.read_bytes())
    assert len(raw)==PIN_SIZE and hashlib.sha256(raw).hexdigest()==PIN_SHA
    pkg=pack.unpack_ar(raw)
    old=pack.members_from(pkg["data.tar.gz"])
    controls=pack.members_from(pkg["control.tar.gz"])
    updates={MONITOR:patch_monitor(old[MONITOR])}
    for file,field in [(PLUGIN,"PLUGIN_VERSION"),(UPDATER,"CURRENT_VERSION")]:
        text=old[file].decode()
        key='%s = "%s"'%(field,OLD)
        assert text.count(key)==1,key
        updates[file]=text.replace(key,'%s = "%s"'%(field,NEW),1).encode()
    control=controls["control"].decode()
    assert control.count("Version: "+OLD)==1
    newctrl=control.replace("Version: "+OLD,"Version: "+NEW,1).encode()
    adds={CHANGELOG:(
        "R72.5: coalesce repeated SAT evTuneFailed background matches by exact DVB "
        "service/name/quality to let fuzzy finish and produce MATCH_BG_DONE stage=fuzzy "
        "or NO_MATCH. Negative fuzzy matches have 45s per-zap/catalog cooldown. "
        "No change to matching scores, names, player, Enigma2 PAT safety, "
        "user mapping, audio, timeshift, source index or core.py.\n").encode()}
    pkg["data.tar.gz"]=pack.make_tar(pkg["data.tar.gz"],updates,adds)
    pkg["control.tar.gz"]=pack.make_tar(pkg["control.tar.gz"],{"control":newctrl})
    dest=Path(path) if path else R/"r725-fuzzy-stability-beta.ipk"
    if dest.exists():dest.unlink()
    binary=pack.assemble(pkg,dest)
    newfiles=pack.members_from(pack.unpack_ar(binary)["data.tar.gz"])
    newctrls=pack.members_from(pack.unpack_ar(binary)["control.tar.gz"])
    assert set(newfiles)==set(old)|set(adds)
    for f,data in old.items():assert newfiles[f]==updates.get(f,data),f
    for f,data in controls.items():assert newctrls[f]==(newctrl if f=="control" else data),f
    for filename,data in newfiles.items():
        if filename.endswith(".py"):compile(data,filename,"exec")
    report={"version":NEW,"size":len(binary),"sha256":hashlib.sha256(binary).hexdigest(),
      "changed":sorted(updates),"protected_files":len(old)-len(updates),
      "changed_monitor_methods":["_queue_background_smartmatch","_smartmatch_poll"],
      "scoring_changed":False,"player_changed":False,
      "field_tested":False,"production_published":False}
    print("R725_FUZZY_BUILD_OK",json.dumps(report,sort_keys=True))
    return report

if __name__=="__main__":build(sys.argv[1] if len(sys.argv)>1 else None)
