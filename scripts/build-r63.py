#!/usr/bin/env python3
"""r63: remove unverified preview resolution hints without probing remote streams."""
from pathlib import Path
import hashlib, io, re, shutil, subprocess, tarfile

ROOT = Path(__file__).resolve().parents[1]
IPK = ROOT / "r62.ipk"
DEST = ROOT / "r63.ipk"
WORK = ROOT / "_r63_build"
if WORK.exists():
    shutil.rmtree(WORK)
for k in ("data", "control"):
    folder = WORK / k
    folder.mkdir(parents=True)
    tar_bytes = subprocess.check_output(["ar", "p", str(IPK), k + ".tar.gz"])
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tar:
        tar.extractall(folder, filter="data")

p = WORK / "data/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge"
pl = p / "plugin.py"
s = pl.read_text()
assert s.count('PLUGIN_VERSION = "1.0.46-r62"') == 1
s = s.replace('PLUGIN_VERSION = "1.0.46-r62"', 'PLUGIN_VERSION = "1.0.46-r63"', 1)
start = s.index("    def _declared_resolution_text(self, channel):")
end = s.index("    def _quality_record_text(self, channel):", start)
s = s[:start] + '''    def _declared_resolution_text(self, channel):
        """Unknown until video evidence is recorded; never substitute name hints.

        Provider names containing HD, 1080p or 4K are commercial labels, not
        verified decoded video dimensions. Do not start another IPTV connection
        merely because the user moves the remote cursor: providers may enforce a
        single connection, and automatic probing can freeze the Vu+ decoder.
        """
        return "NON MESUREE"

''' + s[end:]
old = '''            base = "%dx%d" % (w, h)
            if fps > 0:'''
new = '''            qlabel, _qrank = quality_from_dimensions(w, h)
            base = "MESUREE %dx%d" % (w, h)
            if qlabel and qlabel != "AUTO":
                base += " %s" % qlabel
            if fps > 0:'''
assert s.count(old)==1
s = s.replace(old,new,1)
old = '''            if result not in ("PLAYING", "OPENING"):
                self["status"].setText(("SELECTED • " + self._quality_record_text(ch) + " • OK = LIVE MEASURE")[:220])'''
new = '''            if result not in ("PLAYING", "OPENING"):
                measured_text = self._quality_record_text(ch)
                if measured_text.startswith("NON MESUREE"):
                    self["status"].setText(("SELECTED • RESOLUTION NON MESUREE • OK = MESURER SUR LE DECODEUR • " + clean_display_name(ch.get("name") or "IPTV"))[:220])
                    self["detail"].setText(("RESOLUTION REELLE INCONNUE • OK lance une preview et enregistre les pixels reels; le nom HD/4K du fournisseur ne prouve rien. • " + quality_text)[:250])
                else:
                    self["status"].setText(("SELECTED • " + measured_text + " • VALEUR DU DERNIER TEST")[:220])'''
assert s.count(old)==1
s = s.replace(old,new,1)
# All Sources / Manual Mapping uses another declared-resolution formatter.
alt_start = s.index("class SatIPTVBridgeAlternatives(Screen):")
a_start = s.index("    def _declared_resolution_text(self, channel):", alt_start)
a_end = s.index("    def _real_resolution_text(self, channel):", a_start)
s = s[:a_start] + (
    '    def _declared_resolution_text(self, channel):\n'
    '        """Unknown unless the receiver has a real measurement."""\n'
    '        return "NON MESUREE"\n\n'
) + s[a_end:]
old_age = '''        if width <= 0 or height <= 0:
            declared = self._declared_resolution_text(channel)
            if declared != "HINT ?":
                return "%s • not receiver-measured yet; BLUE PREVIEW will replace this hint with REAL dimensions." % declared
            return "Resolution unknown • BLUE PREVIEW will measure the decoded stream on the receiver."'''
new_age = '''        if width <= 0 or height <= 0:
            return "NON MESUREE • BLUE PREVIEW mesure le flux avec le decodeur; aucune resolution inventee."'''
assert s.count(old_age) == 1
s = s.replace(old_age, new_age, 1)

pl.write_text(s)
updater = p / "updater.py"
u = updater.read_text()
assert u.count('CURRENT_VERSION = "1.0.46-r62"') == 1
updater.write_text(u.replace('CURRENT_VERSION = "1.0.46-r62"', 'CURRENT_VERSION = "1.0.46-r63"',1))
(p / "CHANGELOG-r63-REAL-RESOLUTION.txt").write_text("""IPToSat Pro r63 real resolution
- Real receiver WxH dimensions and quality tier shown instantly when previously measured.
- Never guess actual pixels from provider channel names: HINT HD/4K removed.
- Unknown sources show NON MESUREE and OK prompts decoder measurement.
- Selection and scrolling do not open extra IPTV connections.
- Playback, SmartMatch, core, monitor, NEO theme and timeshift unchanged.
""")
control = WORK/"control/control"
c = control.read_text()
assert c.count("Version: 1.0.46-r62")==1
c=c.replace("Version: 1.0.46-r62","Version: 1.0.46-r63",1)
c=re.sub(r"^Description:.*$", "Description: IPToSat Pro r63 measured preview resolution on NEO Dark", c, flags=re.M)
control.write_text(c)

for kind in ("data","control"):
    with tarfile.open(WORK/(kind+".tar.gz"),"w:gz",format=tarfile.GNU_FORMAT) as tar:
        for path in sorted((WORK/kind).rglob("*")):
            if "__pycache__" in path.parts or path.suffix in (".pyc",".pyo"):
                continue
            tar.add(path,arcname="./"+str(path.relative_to(WORK/kind)),recursive=False)
(WORK/"debian-binary").write_text("2.0\n")
if DEST.exists(): DEST.unlink()
subprocess.check_call(["ar","r",str(DEST),str(WORK/"debian-binary"),str(WORK/"control.tar.gz"),str(WORK/"data.tar.gz")], stdout=subprocess.DEVNULL)

# Host-only static tests; no network, decoder or Enigma2 imports.
for src in p.glob("*.py"):
    compile(src.read_bytes(),str(src),"exec")
assert 'HINT %s' not in s and 'return "NON MESUREE"' in s
assert "MESUREE %dx%d" in s and "OK = MESURER SUR LE DECODEUR" in s
ref_tmp = ROOT/"_r63_build"/"base-check"
for filename in ("core.py","monitor.py","neo_theme.py","timeshift_seek_patch.py"):
    source_bytes=subprocess.check_output(["ar","p",str(IPK),"data.tar.gz"])
    with tarfile.open(fileobj=io.BytesIO(source_bytes),mode="r:gz") as tf:
        original=tf.extractfile("./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"+filename).read()
    assert original == (p/filename).read_bytes(),filename
print("r63 built, size",DEST.stat().st_size, "sha256",hashlib.sha256(DEST.read_bytes()).hexdigest())
