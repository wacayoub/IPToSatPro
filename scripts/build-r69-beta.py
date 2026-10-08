#!/usr/bin/env python3
"""r69 BETA Quality Guard: metadata-only patch to the published r68 IPK."""
from pathlib import Path
import io, tarfile, subprocess, re, hashlib, shutil, ast
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/"r68-beta.ipk"
WORK=ROOT/"_r69_build"
OUT=ROOT/"r69-beta.ipk"
raw=BASE.read_bytes()
assert len(raw)==276082, "unexpected r68 release size"
assert hashlib.sha256(raw).hexdigest()=="d2d14f38180807e6060cbbb8927e56fe0d4aa03025ccfff061ea70f1d3f09844"
if WORK.exists():shutil.rmtree(WORK)
for kind in ("data","control"):
    (WORK/kind).mkdir(parents=True)
    blob=subprocess.check_output(["ar","p",str(BASE),kind+".tar.gz"])
    with tarfile.open(fileobj=io.BytesIO(blob),mode="r:gz") as tar:
        tar.extractall(WORK/kind,filter="data")
P=WORK/"data/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge"
m=P/"monitor.py"
s=m.read_text()
anchor='''    def _post_success_quality_update(self, candidate, width, height, hdr=""):
        """Persist late decoder metadata without delaying an already moving IPTV picture."""
        if not candidate or width <= 0 or height <= 0:
            return False
        self._commit_current_resolution(candidate, width, height)
        self._update_resolution_observation(candidate, width, height, hdr=hdr)
'''
patch='''    def _post_success_quality_update(self, candidate, width, height, hdr=""):
        """Store current verified metadata once, without touching the fast playback path."""
        if not candidate or width <= 0 or height <= 0:
            return False
        if (not self.fallback_active or self.switch_in_progress or
                not self.iptv_start_seen or self.play_result not in
                ("SUCCESS", "SUCCESS • QUALITY FALLBACK")):
            return False
        active = self.pending_match or self.last_match
        if not active or channel_fingerprint(active) != channel_fingerprint(candidate):
            return False
        try:
            ref = self.session.nav.getCurrentlyPlayingServiceReference()
            path = ref.getPath() if ref is not None else ""
            if ref is None or not self._is_expected_bridge_iptv(ref, ref.toString(), path):
                return False
        except Exception:
            return False
        now = time.time()
        started = float(self.current_candidate_started_at or 0)
        dims = (int(width), int(height))
        previous = (int(self.pre_switch_video_width or 0), int(self.pre_switch_video_height or 0))
        if (previous[0] > 0 and previous[1] > 0 and dims == previous and
                started > 0 and 0 <= now - started < 1.3):
            # Old decoder metadata sometimes reaches the new service during handover.
            # Defer metadata only; never delay the picture or make a network request.
            try:
                self.resolution_followup_fp = channel_fingerprint(candidate)
                self.resolution_followup_timer.start(max(150, int((1.35 - (now - started)) * 1000)), True)
            except Exception:
                pass
            return False
        signature = (channel_fingerprint(candidate), str(self.current_play_mode),
                     started, dims, str(hdr or ""))
        if getattr(self, "_late_quality_signature", None) == signature:
            return True
        self._late_quality_signature = signature
        self._commit_current_resolution(candidate, width, height)
        self._update_resolution_observation(candidate, width, height, hdr=hdr)
'''
assert s.count(anchor)==1, "r68 monitor changed; refusing unsafe patch"
s=s.replace(anchor,patch,1)
m.write_text(s)
for name,tag in (("plugin.py","PLUGIN_VERSION"),("updater.py","CURRENT_VERSION")):
    f=P/name
    val=f'{tag} = "1.0.46-r68-beta"'
    src=f.read_text()
    assert src.count(val)==1,(name,val)
    f.write_text(src.replace(val,f'{tag} = "1.0.46-r69-beta"',1))
(P/"CHANGELOG-r69-QUALITY-GUARD.txt").write_text(
    "r69 BETA Quality Guard: deduplicate late size notifications by candidate and playback attempt.\\n"
    "Ignore stale previous decoder dimensions briefly during handover; recheck asynchronously.\\n"
    "Confirm active bridge reference before saving quality and preferred player mode.\\n"
    "Never change r68 player plan, LOCKED fast path, timeshift, relay or r67 Preview.\\n")
control=WORK/"control/control"
c=control.read_text()
assert c.count("Version: 1.0.46-r68-beta")==1
control.write_text(c.replace("Version: 1.0.46-r68-beta","Version: 1.0.46-r69-beta",1))
for f in P.glob("*.py"): compile(f.read_bytes(),str(f),"exec")
with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(["ar","p",str(BASE),"data.tar.gz"])),mode="r:gz") as old:
    for name in ("core.py","neo_theme.py","native_selection_follow.py","timeshift_seek_patch.py"):
        original=old.extractfile("./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"+name).read()
        assert original==(P/name).read_bytes(),name
    old_m=old.extractfile("./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/monitor.py").read().decode()
    trees=[ast.parse(x) for x in (old_m,s)]
    classes=[next(x for x in t.body if isinstance(x,ast.ClassDef) and x.name=="SatFallbackMonitor") for t in trees]
    for method in ("_playback_plan","_play_match","_verify_iptv","_handle_iptv_failure"):
        fn=[next(x for x in cl.body if isinstance(x,ast.FunctionDef) and x.name==method) for cl in classes]
        assert ast.dump(fn[0])==ast.dump(fn[1]),method
for kind in ("data","control"):
    with tarfile.open(WORK/(kind+".tar.gz"),"w:gz",format=tarfile.GNU_FORMAT) as tar:
        for f in sorted((WORK/kind).rglob("*")):
            if "__pycache__" in f.parts or f.suffix in (".pyc",".pyo"):continue
            tar.add(f,arcname="./"+str(f.relative_to(WORK/kind)),recursive=False)
(WORK/"debian-binary").write_text("2.0\n")
if OUT.exists():OUT.unlink()
subprocess.run(["ar","r",str(OUT),str(WORK/"debian-binary"),str(WORK/"control.tar.gz"),str(WORK/"data.tar.gz")],check=True,stdout=subprocess.PIPE)
print("R69_PACKAGE",OUT.stat().st_size,hashlib.sha256(OUT.read_bytes()).hexdigest())
