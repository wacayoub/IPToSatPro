#!/usr/bin/env python3
"""r68 BETA Smart Player builder; abort publication on any patch mismatch."""
from pathlib import Path
import base64, hashlib, io, lzma, re, shutil, subprocess, tarfile
R=Path(__file__).resolve().parents[1]
base=R/"r67-beta.ipk"
out=R/"r68-beta.ipk"
work=R/"_build_r68"
b=base.read_bytes()
assert len(b)==274348, len(b)
assert hashlib.sha256(b).hexdigest()=="f47a170dab971f90bae7053031e2af6a8e32ca4620a083f72794617e5bba889f"
if work.exists(): shutil.rmtree(work)
for kind in ("data","control"):
    (work/kind).mkdir(parents=True)
    gz=subprocess.check_output(["ar","p",str(base),kind+".tar.gz"])
    with tarfile.open(fileobj=io.BytesIO(gz),mode="r:gz") as t:
        t.extractall(work/kind,filter="data")
P=work/"data/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge"
monitor=P/"monitor.py"
patch=lzma.decompress(base64.b64decode((R/"scripts/r68-monitor.patch.xz.b64").read_text()))
assert hashlib.sha256(patch).hexdigest()=="73dcbb73a264bfa024fa0661709c7875d3ef0fad053701acf666725d5b1dad48"
process=subprocess.run(["patch","--batch","--fuzz=0","--forward","-p0"],cwd=P,input=patch,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
if process.returncode:
    raise RuntimeError("Patch must apply without fuzz: "+process.stdout.decode(errors="replace")+process.stderr.decode(errors="replace"))
for filename,key in (("plugin.py","PLUGIN_VERSION"),("updater.py","CURRENT_VERSION")):
    p=P/filename
    txt=p.read_text()
    old=key+' = "1.0.46-r67-beta"'
    assert txt.count(old)==1,(filename,old)
    p.write_text(txt.replace(old,key+' = "1.0.46-r68-beta"',1))
(P/"CHANGELOG-r68-SMART-PLAYER.txt").write_text(
    "r68 BETA Smart Player memory and verified evidence:\n"
    "MPEG-TS readiness is provisional; no invented decoded resolution.\n"
    "Remember exact DVB/5002/4097 per-stream decoder-confirmed mode for 24h.\n"
    "Allow short DVB transport hint after failed ServiceApp where exact same TS worked.\n"
    "Exclude unknown-quality generic candidates from automatic UHD fallback; keep in Preview.\n"
    "Keep MANUAL LOCK, fast prewarm, OpenATV PAT guard, native timeshift and r67 Preview unchanged.\n"
)
control=work/"control/control"
c=control.read_text()
assert c.count("Version: 1.0.46-r67-beta")==1
c=c.replace("Version: 1.0.46-r67-beta","Version: 1.0.46-r68-beta",1)
c=re.sub(r"^Description:.*$","Description: IPToSat Pro r68 BETA Smart Player memory and verified TS fallback",c,flags=re.M)
control.write_text(c)
for f in P.glob("*.py"): compile(f.read_bytes(),str(f),"exec")
# Crucial: no file except monitor, version literals, and changelog changes.
with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(["ar","p",str(base),"data.tar.gz"])),mode="r:gz") as orig:
    for filename in ("core.py","neo_theme.py","native_selection_follow.py","timeshift_seek_patch.py"):
        old=orig.extractfile("./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"+filename).read()
        assert (P/filename).read_bytes()==old,filename
    old_plugin=orig.extractfile("./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/plugin.py").read().decode()
    assert (P/"plugin.py").read_text().replace("PLUGIN_VERSION = \"1.0.46-r68-beta\"","PLUGIN_VERSION = \"1.0.46-r67-beta\"")==old_plugin
old_monitor=orig.extractfile("./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/monitor.py").read().decode()
new_monitor=monitor.read_text()
for key in ("FAST_LOCK_NATIVE_TIMEOUT_MS","FAST_LOCK_UHD_NATIVE_TIMEOUT_MS","NATIVE_PAT_GUARD_MS","FAST_LOCK_PREWARM_TIMEOUT_S","FAST_MAPPED_DELAY_MS"):
    pat=r"^\s*"+key+r"\s*=\s*[^\n]+"
    assert re.search(pat,old_monitor,re.M).group()==re.search(pat,new_monitor,re.M).group(),key
for kind in ("data","control"):
    with tarfile.open(work/(kind+".tar.gz"),"w:gz",format=tarfile.GNU_FORMAT) as archive:
        for f in sorted((work/kind).rglob("*")):
            if "__pycache__" in f.parts or f.suffix in (".pyc",".pyo"): continue
            archive.add(f,arcname="./"+str(f.relative_to(work/kind)),recursive=False)
(work/"debian-binary").write_text("2.0\n")
if out.exists():out.unlink()
subprocess.run(["ar","r",str(out),str(work/"debian-binary"),str(work/"control.tar.gz"),str(work/"data.tar.gz")],check=True,stdout=subprocess.PIPE)
assert out.stat().st_size>200000
print("R68_BETA_PACKAGED",out.stat().st_size,hashlib.sha256(out.read_bytes()).hexdigest())
