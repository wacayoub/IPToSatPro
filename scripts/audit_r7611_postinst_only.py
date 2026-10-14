#!/usr/bin/env python3
"""Inspect original packaged opkg postinst without executing any install code.

Offline, reads immutable R76.11 staged payload. Displays commands only;
strips embedded addresses, URLs, credentials. Does not write receiver files.
"""
import base64
import importlib.util
import json
import re
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
builder_path=ROOT/"scripts/build-r7611-preview-cold.py"
spec=importlib.util.spec_from_file_location("r7611_postinst_qa",builder_path)
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
manifest=json.loads((ROOT/"staging/r7611-preview-cold.update.json").read_text())
raw=base64.b64decode((ROOT/"payload/r7611-preview-cold.b64").read_bytes())
import hashlib
assert hashlib.sha256(raw).hexdigest()==manifest["sha256"]
ctrl=builder.pack.members_from(builder.pack.unpack_ar(raw)["control.tar.gz"])
postinst=ctrl.get("postinst",b"").decode("utf8","replace")
assert postinst
result=subprocess.run(["sh","-n"],input=postinst,text=True,capture_output=True)
assert result.returncode==0, "invalid postinst shell syntax"
verbs=re.compile(r"^\s*(?:rm|mv|cp|ln|mkdir|chmod|chown|sed|opkg|systemctl|service|init|killall|wget|curl|echo|printf|touch|install|find|python3?|exit|if |for |case |exec |tar |update-rc|reboot|enigma2|logger)\b",re.I)
cmds=[]
for index,line in enumerate(postinst.splitlines(),1):
    t=line.strip()
    if t.startswith("#") or not t or not verbs.search(t):
        continue
    t=re.sub(r"https?://\S+","[URL]",t)
    t=re.sub(r"(token|password|secret|pass)=\S+",r"\1=[REDACTED]",t,flags=re.I)
    cmds.append({"line":index,"cmd":t[:240]})
print("R7611_POSTINST_SCAN",json.dumps({
    "postinst_sha256": hashlib.sha256(postinst.encode()).hexdigest(),
    "postinst_lines":len(postinst.splitlines()),
    "hardcoded_r62": "1.0.46-r62" in postinst,
    "commands":cmds,
},ensure_ascii=True))
