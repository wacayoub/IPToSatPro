#!/usr/bin/env python3
"""Strict r70-vs-r69 release-candidate regression check (no publishing)."""
from pathlib import Path
import ast
import base64
import hashlib
import io
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BASE_RAW = base64.b64decode((ROOT / "payload/r69-beta.b64").read_bytes())
BASE_SHA = "123e1118a7471075ad18dee3014b7367fa9a2cf02f8cdd52ad1e5e65034035ed"
REL = "./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"
assert hashlib.sha256(BASE_RAW).hexdigest() == BASE_SHA


def members(data):
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "v.ipk"
        f.write_bytes(data)
        raw = subprocess.check_output(["ar", "p", str(f), "data.tar.gz"])
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
        def read(path):
            return tf.extractfile(path).read()
        return {name: read(REL + name) for name in (
            "monitor.py", "plugin.py", "updater.py",
            "core.py", "timeshift_seek_patch.py", "neo_theme.py",
        )}, (
            read("./usr/bin/iptosat-tsbridge"),
            read("./etc/init.d/iptosat-tsbridge")
        )


def functions(data):
    module = ast.parse(data)
    cls = next(x for x in module.body
               if isinstance(x, ast.ClassDef) and x.name == "SatFallbackMonitor")
    return {n.name: ast.dump(n, include_attributes=False)
            for n in cls.body if isinstance(n, ast.FunctionDef)}


def main():
    new = (ROOT / "r70-candidate.ipk").read_bytes()
    base, base_bridge = members(BASE_RAW)
    cand, new_bridge = members(new)
    monitor = base["monitor.py"]
    assert cand["monitor.py"].startswith(monitor), "Original r69 monitor changed"
    assert cand["monitor.py"] != monitor, "r70 adapter was not attached"
    assert functions(cand["monitor.py"]) == functions(monitor), (
        "Existing monitor method/locked fast-open AST changed"
    )
    for name in ("core.py", "timeshift_seek_patch.py", "neo_theme.py"):
        assert cand[name] == base[name], name + " changed"
    assert new_bridge == base_bridge, "Relay changed"
    for name, tag in (("plugin.py", "PLUGIN_VERSION"), ("updater.py", "CURRENT_VERSION")):
        old = base[name].decode()
        expected = old.replace(
            tag + ' = "1.0.46-r69-beta"',
            tag + ' = "1.0.46-r70-rc1"'
        )
        assert expected != old and cand[name].decode() == expected, name + " changed"
    assert b"r70_monitor_adapter" in cand["monitor.py"]
    print("PASS r70 exact locked fast-path AST, SAT/timeshift, relay, GUI core")
    print("BASELINE r69 pinned:", BASE_SHA)
    print("NOTE: r64 legacy guard reports inherited _on_start deviation in r69;")
    print("      this check enforces no ADDITIONAL change from installed r69.")


if __name__ == "__main__":
    main()
