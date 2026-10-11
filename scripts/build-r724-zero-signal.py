#!/usr/bin/env python3
"""R72.4 experimental fix for explicit SAT no-lock (FTA or encrypted) IPTV fallback.

No changes to player, Fast Lock timing, _on_start, tuner callback, timers,
matching, source catalog or IPTV stream selection. The only monitor runtime
change is an exception in the centralized FTA fence for PROVEN SAT no-lock
after the existing native PAT guard / delayed tune-failed callback.
"""
import ast,base64,hashlib,importlib.util,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("r723",ROOT/"scripts/build-r723-classic-fusion.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)
pack=b.pack;P=b.P;PLUGIN=b.PLUGIN;UPDATER=b.UPDATER;MONITOR=P+"monitor.py"
BASE=ROOT/"payload/r723-neo-classic-premium.b64"
BASE_LEN=402536
BASE_SHA="b76e9fb551cef1d0422d6303f3d74e38b94cadae6fda6b6f90d6eecf7739afa3"
OLD="1.0.46-r72.3-classic-premium-beta"
NEW="1.0.46-r72.4-zero-signal-beta"
CHANGELOG=P+"CHANGELOG-r724-NO-SAT-SIGNAL.txt"

def replace_one(src,old,new):
    count=src.count(old)
    if count!=1:raise AssertionError("MONITOR version guard drift: %s matches=%s"%(old[:100],count))
    return src.replace(old,new,1)

def patch_monitor(binary):
    src=binary.decode()
    anchor='''        if self._fallback_crypto_gate is True or self._fallback_crypto_gate is False:
            return self._fallback_crypto_gate

        # Manual mappings created by current builds already store sat_crypted. Trust that'''
    add='''        # R72.4: A definite FAILED satellite tuner cannot deliver SAT video, regardless
        # of FTA / encrypted markers. A failed tune without PMT commonly reports NO/?
        # for CAIDs, which previously produced FTA_FALLBACK_BLOCK indefinitely.
        #
        # This exception is deliberately narrow: it runs only inside a real fallback
        # request, after the native evTuneFailed callback was deferred. It DOES NOT
        # consider SNR=0 on its own (some drivers display 0 even with working video).
        # Nor does it override healthy LOCKED, transitional TUNING/ACQUIRING, or
        # an unknown '?' state. Existing matching and video verification still decide.
        try:
            no_sat_fallback = bool(self.cfg.fallback_no_signal.value)
        except Exception:
            no_sat_fallback = False
        state = str(self.tuner_state or "").upper().strip()
        failed_states = ("TUNE_FAILED", "FAILED", "NO_SIGNAL", "NO_LOCK", "NOT_LOCKED", "UNLOCKED")
        if no_sat_fallback and state in failed_states and not self.fallback_active:
            try:
                same_ref = bool(self.current_sat_ref_string) and self._same_sat_still_playing()
            except Exception:
                same_ref = False
            if same_ref:
                self._fallback_crypto_gate = True
                # Do NOT rewrite the service as encrypted. An FTA SAT source can
                # legitimately use IPTV only when its tuner has actually failed.
                self.crypted_state = "?"
                self._log("NO_SIGNAL_FTA_IPTV_ALLOWED",
                          "channel='%s' tuner=%s mode=SAT_NO_LOCK" %
                          (self.current_sat_name, state))
                return True

'''
    assert src.count(anchor)==1
    src=src.replace(anchor,add+anchor,1)
    before=ast.parse(binary.decode())
    after=ast.parse(src)
    def methods(tree):
        cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="SatFallbackMonitor")
        return {m.name:ast.dump(m,include_attributes=False) for m in cls.body if isinstance(m,ast.FunctionDef)}
    original,new=methods(before),methods(after)
    assert set(original)==set(new)
    assert {k for k in original if original[k]!=new[k]}=={"_encrypted_fallback_allowed_once"}
    compile(src,MONITOR,"exec")
    return src.encode()

def build(output=None):
    raw=base64.b64decode(BASE.read_bytes())
    assert len(raw)==BASE_LEN and hashlib.sha256(raw).hexdigest()==BASE_SHA
    parts=pack.unpack_ar(raw)
    old=pack.members_from(parts["data.tar.gz"])
    ctrl=pack.members_from(parts["control.tar.gz"])
    changes={MONITOR:patch_monitor(old[MONITOR])}
    for key,var in ((PLUGIN,"PLUGIN_VERSION"),(UPDATER,"CURRENT_VERSION")):
        text=old[key].decode()
        token='%s = "%s"'%(var,OLD)
        assert text.count(token)==1
        changes[key]=text.replace(token,'%s = "%s"'%(var,NEW),1).encode()
    control=ctrl["control"].decode()
    assert control.count("Version: "+OLD)==1
    newctrl=control.replace("Version: "+OLD,"Version: "+NEW,1).encode()
    additions={CHANGELOG:(
        "R72.4 ZERO SAT SIGNAL BETA: FTA_FALLBACK_BLOCK no longer prevents the "
        "existing IPTV fallback after definitive SAT TUNE_FAILED/NO_LOCK with "
        "same current satellite reference and no-signal fallback enabled. "
        "Other FTA/encrypted checks, matcher, native PAT safety defer, user locks, "
        "player, Fast Zap and timeshift remain unchanged. Signal 0% alone does "
        "NOT guarantee SAT failure; no match still yields no IPTV. Field testing required.\n"
    ).encode()}
    parts["data.tar.gz"]=pack.make_tar(parts["data.tar.gz"],changes,additions)
    parts["control.tar.gz"]=pack.make_tar(parts["control.tar.gz"],{"control":newctrl})
    path=Path(output) if output else ROOT/"r724-zero-signal-beta.ipk"
    if path.exists():path.unlink()
    blob=pack.assemble(parts,path)
    resulting=pack.members_from(pack.unpack_ar(blob)["data.tar.gz"])
    result_control=pack.members_from(pack.unpack_ar(blob)["control.tar.gz"])
    assert set(resulting)==set(old)|{CHANGELOG}
    for f,v in old.items():assert resulting[f]==changes.get(f,v),"unexpected changed "+f
    for f,v in ctrl.items():assert result_control[f]==(newctrl if f=="control" else v)
    for file,data in resulting.items():
        if file.endswith(".py"):compile(data,file,"exec")
    metadata={"version":NEW,"size":len(blob),"sha256":hashlib.sha256(blob).hexdigest(),
      "changed":sorted(changes),"unchanged_package_files":len(old)-len(changes),
      "affected_monitor_methods":["_encrypted_fallback_allowed_once"],
      "player_changed":False,"tune_event_changed":False,
      "field_tested":False,"published_to_main":False}
    print("R724_NO_SIGNAL_BUILD_OK",json.dumps(metadata,sort_keys=True))
    return metadata

if __name__=="__main__":build(sys.argv[1] if len(sys.argv)>1 else None)
