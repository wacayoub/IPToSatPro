#!/usr/bin/env python3
"""Build R73.8 auto-play beta on the exact R73.7 package; NO live publication.

Player, monitor, EPG, timeshift and receiver mappings are byte-identical.
Only core scoring budget, Preview-to-player integration and version are changed.
"""
import ast,hashlib,importlib.util,json,tempfile,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r737base",ROOT/"scripts/build-r73-preview.py")
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
sp=importlib.util.spec_from_file_location("r738patch",ROOT/"scripts/r738_auto_open_patch.py")
p=importlib.util.module_from_spec(sp);sp.loader.exec_module(p)

OLD=b.NEW
NEW="1.0.46-r73.8-safe-auto-play-beta"
CHANGELOG=b.P+"CHANGELOG-r738-SAFE-AUTO-PLAY.txt"

def build(destination=None):
    with tempfile.TemporaryDirectory() as td:
        source=Path(td)/"baseline-r737.ipk"
        old_meta=b.build(source)
        raw=source.read_bytes()
        parts=b.base.pack.unpack_ar(raw)
        original=b.base.pack.members_from(parts["data.tar.gz"])
        control=b.base.pack.members_from(parts["control.tar.gz"])
        old_plugin=original[b.PLUGIN].decode()
        old_core=original[b.CORE].decode()
        plugin=p.patch_plugin(old_plugin)
        core=p.patch_core(old_core)
        assert ast.parse(plugin) and ast.parse(core)
        assert plugin.count("_r738_queue_auto_open(self, raw, ")==2
        assert "_r738_autoplay_current" in plugin
        assert "budget=36" in core
        updater=original[b.UPDATER].decode()
        updater=b.exactly(updater,'CURRENT_VERSION = "'+OLD+'"',
                              'CURRENT_VERSION = "'+NEW+'"')
        plugin=b.exactly(plugin,'PLUGIN_VERSION = "'+OLD+'"',
                              'PLUGIN_VERSION = "'+NEW+'"')
        control_text=control["control"].decode()
        control_text=b.exactly(control_text,"Version: "+OLD,"Version: "+NEW)
        changes={b.PLUGIN:plugin.encode(), b.CORE:core.encode(), b.UPDATER:updater.encode()}
        description=(
            "R73.8 SAFE AUTO PLAY BETA: after an exact SAFE/ALLOWED Preview "
            "auto-map is NEWLY saved for the CURRENTLY PLAYING SAT reference, "
            "close Preview, restore SAT, then asynchronously hand the saved "
            "IPTV candidate to SatFallbackMonitor._play_match using the existing "
            "video verification and same-name backup chain. Stale result, user "
            "zap, manual mapping, busy bridge and healthy SAT video are guarded. "
            "Detailed Preview scoring budget 18->36 across P/B1/B2. "
            "No signal-FTA setting, player, monitor, timeshift, credentials, "
            "mapping files or existing releases are rewritten. Hardware validation "
            "is still required.\n"
        ).encode()
        parts["data.tar.gz"]=b.base.pack.make_tar(parts["data.tar.gz"],
                                                     changes,{CHANGELOG:description})
        parts["control.tar.gz"]=b.base.pack.make_tar(parts["control.tar.gz"],
                                                        {"control":control_text.encode()})
        dest=Path(destination) if destination else ROOT/"r738-safe-auto-play-beta.ipk"
        if dest.exists(): dest.unlink()
        built=b.base.pack.assemble(parts,dest)
        rebuilt=b.base.pack.members_from(b.base.pack.unpack_ar(built)["data.tar.gz"])
        assert set(rebuilt)==set(original)|{CHANGELOG}
        for key,value in original.items():
            assert rebuilt[key]==changes.get(key,value),key
        for name,data in rebuilt.items():
            if name.endswith(".py"): compile(data,name,"exec")
        mon=b.P+"monitor.py"
        assert rebuilt[mon]==original[mon]
        return {
            "version":NEW,"size":len(built),"sha256":hashlib.sha256(built).hexdigest(),
            "changed":list(changes.keys()),"player_unchanged":True,
            "monitor_unchanged":True,"auto_open_current_sat_only":True,
            "receiver_tested":False,"production_published":False,
            "baseline_version":old_meta["version"],
        }

if __name__=="__main__":
    print("R738_BETA_STAGE_OK",json.dumps(build(sys.argv[1] if len(sys.argv)>1 else None),sort_keys=True))
