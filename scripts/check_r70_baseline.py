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
            tag + ' = "1.0.46-r70-rc6"'
        )
        assert expected != old, "Version anchor missing: " + name
        if name == "plugin.py":
            patch_ns = {}
            exec(compile((ROOT / "r70/r70_preview_patch.py").read_bytes(),
                         "r70_preview_patch.py", "exec"), patch_ns)
            preview_expected = patch_ns["improve"](expected)
            preview_expected = preview_expected.replace(
                '"2": self._open_auto_scan,',
                '"2": self._open_auto_scan, "3": self._r70_autotest_start,', 1)
            preview_expected = preview_expected.replace(
                'self["key_blue"] = Label("PREVIEW / RETRY")',
                'self["key_blue"] = Label("AUTO TEST / PREVIEW")', 1)
            preview_expected = preview_expected.replace(
                '    def __init__(self, session, sat_ref_string, channel,',
                '    def _r70_autotest_start(self):\n'
                '        self["detail"].setText("Auto Test unavailable; RIGHT then BLUE tests one source")\n'
                '\n    def __init__(self, session, sat_ref_string, channel,', 1)
            # Strictly permit the separately audited Preview UI patch, plus
            # appended auxiliary lock and async ranking adapters. Other
            # original classes and non-Preview globals must be AST identical.
            result = cand[name].decode()
            assert result.startswith(preview_expected), "Unexpected plugin changes"
            trailer = result[len(preview_expected):]
            for required in ("_r70_locks(globals())", "r70_lock_adapter",
                             "_r70_preview_attach(SatIPTVBridgeAlternatives, globals())",
                             "r70_preview_async", "_rc3_fta_plugin(globals())", "fta_runtime_adapter",
                             "_rc4_autotest_attach(SatIPTVBridgePreview, globals())",
                             "preview_autotest_rc4"):
                assert required in trailer, "Missing UI hook: " + required
            orig = ast.parse(expected)
            actual = ast.parse(result)
            allowed_classes = {"SatIPTVBridgePreview", "SatIPTVBridgeAlternatives",
                               "SmartMatchAlternativesList"}
            allowed_functions = {"_preview_candidate_cache_put",
                                 "_open_all_sources_for_ref"}
            old_code = {("class", n.name): ast.dump(n, include_attributes=False)
                        for n in orig.body if isinstance(n, ast.ClassDef)
                        and n.name not in allowed_classes}
            old_code.update({("function", n.name): ast.dump(n, include_attributes=False)
                            for n in orig.body if isinstance(n, ast.FunctionDef)
                            and n.name not in allowed_functions})
            new_code = {("class", n.name): ast.dump(n, include_attributes=False)
                        for n in actual.body if isinstance(n, ast.ClassDef)
                        and n.name not in allowed_classes}
            new_code.update({("function", n.name): ast.dump(n, include_attributes=False)
                            for n in actual.body if isinstance(n, ast.FunctionDef)
                            and n.name not in allowed_functions})
            assert old_code == new_code, "Unrelated plugin classes/functions changed"
        else:
            assert cand[name].decode() == expected, name + " changed"
    assert b"r70_monitor_adapter" in cand["monitor.py"]
    assert b"_rc3_fta_attach(SatFallbackMonitor)" in cand["monitor.py"], "Missing opt-in FTA gate"
    assert b"_rc5_recovery_attach(SatFallbackMonitor)" in cand["monitor.py"], "Missing rc5 failed-only decoder fallback"
    assert b"_rc6_tod_attach(SatFallbackMonitor)" in cand["monitor.py"], "TOD audio safety hook missing"
    print("PASS r70 exact locked fast-path AST, SAT/timeshift, relay, GUI core")
    print("BASELINE r69 pinned:", BASE_SHA)
    print("NOTE: r64 legacy guard reports inherited _on_start deviation in r69;")
    print("      this check enforces no ADDITIONAL change from installed r69.")


if __name__ == "__main__":
    main()
