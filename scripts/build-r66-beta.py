#!/usr/bin/env python3
"""Construct r66-beta from released r65; verify every changed file byte-for-byte."""
from pathlib import Path
import base64,hashlib,io,json,lzma,re,shutil,subprocess,tarfile
root=Path(__file__).resolve().parents[1]
base=root/"r65.ipk"; delta=root/"scripts/r66-beta-delta.b64"
work=root/"_build_r66_beta"; out=root/"r66-beta.ipk"
assert base.is_file() and delta.is_file()
raw=base.read_bytes()
assert len(raw)==270986
assert hashlib.sha256(raw).hexdigest()=="ad226ae2b511264a64d8778937daa900e88d28536fbe6ddb6841ede42d48045e"
if work.exists():shutil.rmtree(work)
for kind in ("data","control"):
    (work/kind).mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(["ar","p",str(base),kind+".tar.gz"])),mode="r:gz") as t:
        t.extractall(work/kind,filter="data")
plugin=work/"data/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge"
payload=json.loads(lzma.decompress(base64.b64decode(delta.read_text())).decode("utf-8"))
for name in ("plugin.py","monitor.py","updater.py"):
    subprocess.run(["patch","--batch","--fuzz=0","--forward","-p1"],input=payload[name].encode(),cwd=plugin,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
for name in ("native_selection_follow.py","CHANGELOG-r66-beta.txt"):
    (plugin/name).write_text(payload[name],encoding="utf-8")
verified={
"plugin.py":"65ae5e9cdbed1acfd5cd47a741cd5c8e9081c88f300d7158064e95ff3a706ee8",
"monitor.py":"e9f82f2be33b8db93bc9b75f6d11e7d1c8fa17365092059325f56018316f4a97",
"updater.py":"c6958de06db3e300a357d7faefd8b2f60a6b92568761fb2646baa562040e02f7",
"native_selection_follow.py":"f130694778b421eea48d5834fa5f93d4743211834052c0d828acd54079628955",
"CHANGELOG-r66-beta.txt":"611be88cbc77333cbd6822cb94797c51d07546d7a2f392f40a2f97b0a932a170"}
for name,sha in verified.items():
    assert hashlib.sha256((plugin/name).read_bytes()).hexdigest()==sha,name
for f in plugin.glob("*.py"):compile(f.read_bytes(),str(f),"exec")
control=work/"control/control";txt=control.read_text()
assert txt.count("Version: 1.0.46-r65")==1
txt=txt.replace("Version: 1.0.46-r65","Version: 1.0.46-r66-beta",1)
txt=re.sub(r"^Description:.*$","Description: IPToSat Pro r66 beta native All Services and safe fallback",txt,flags=re.M)
control.write_text(txt)
with tarfile.open(fileobj=io.BytesIO(subprocess.check_output(["ar","p",str(base),"data.tar.gz"])),mode="r:gz") as original:
    for fn in ("core.py","timeshift_seek_patch.py","neo_theme.py"):
        assert original.extractfile("./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"+fn).read()==(plugin/fn).read_bytes(),fn
for kind in ("data","control"):
    with tarfile.open(work/(kind+".tar.gz"),"w:gz",format=tarfile.GNU_FORMAT) as t:
        for f in sorted((work/kind).rglob("*")):
            if "__pycache__" in f.parts or f.suffix in (".pyc",".pyo"):continue
            t.add(f,arcname="./"+str(f.relative_to(work/kind)),recursive=False)
(work/"debian-binary").write_text("2.0\n")
if out.exists():out.unlink()
subprocess.run(["ar","r",str(out),str(work/"debian-binary"),str(work/"control.tar.gz"),str(work/"data.tar.gz")],check=True,stdout=subprocess.PIPE)
assert out.stat().st_size>200000
print("R66_BETA_CHECKED",out.stat().st_size,hashlib.sha256(out.read_bytes()).hexdigest())
