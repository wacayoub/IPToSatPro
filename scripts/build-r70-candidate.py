#!/usr/bin/env python3
"""Build an UNPUBLISHED r70 candidate from pinned r69; never change online update.

Usage: python3 scripts/build-r70-candidate.py
No network, GitHub tag, push, manifest edit, release or installer update.
"""
from pathlib import Path
import ast
import base64
import hashlib
import io
import os
import re
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "payload/r69-beta.b64"
OUT = ROOT / "r70-candidate.ipk"
VERSION = "1.0.46-r70-rc3"
BASE_BYTES = 276666
BASE_SHA256 = "123e1118a7471075ad18dee3014b7367fa9a2cf02f8cdd52ad1e5e65034035ed"
REL = "usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge"


def once(source, old, new):
    if source.count(old) != 1:
        raise AssertionError("Unexpected baseline: anchor mismatch for " + old[:90])
    return source.replace(old, new, 1)


def copy_tar_members(src_tar, dst, name):
    data = subprocess.check_output(["ar", "p", str(src_tar), name + ".tar.gz"])
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        tar.extractall(dst, filter="data")


def main():
    raw = base64.b64decode(PAYLOAD.read_bytes(), validate=False)
    if len(raw) != BASE_BYTES or hashlib.sha256(raw).hexdigest() != BASE_SHA256:
        raise AssertionError("Published r69 baseline has changed. Build blocked.")
    if not raw.startswith(b"!<arch>\n"):
        raise AssertionError("r69 is not an IPK ar archive")

    with tempfile.TemporaryDirectory(prefix="iptosat-r70-") as tmp:
        work = Path(tmp)
        base_file = work / "r69.ipk"
        base_file.write_bytes(raw)
        for name in ("data", "control"):
            (work / name).mkdir()
            copy_tar_members(base_file, work / name, name)
        package = work / "data" / REL
        mon_path = package / "monitor.py"
        plugin_path = package / "plugin.py"
        updater_path = package / "updater.py"
        baseline_monitor = mon_path.read_bytes()
        original_ast = ast.parse(baseline_monitor)

        cls = next((node for node in original_ast.body
                    if isinstance(node, ast.ClassDef)
                    and node.name == "SatFallbackMonitor"), None)
        if cls is None:
            raise AssertionError("SatFallbackMonitor missing; refuse unsafe integration")
        names = {node.name for node in cls.body if isinstance(node, ast.FunctionDef)}
        required = {"_play_match", "_post_success_quality_update",
                    "_handle_iptv_failure"}
        if not required.issubset(names):
            raise AssertionError("Runtime hooks changed; manual code review required")

        for module in ("r70_safety_core.py", "r70_monitor_adapter.py", "r70_lock_adapter.py", "r70_preview_async.py", "no_signal_policy.py", "fta_runtime_adapter.py"):
            source = (ROOT / "r70" / module).read_bytes()
            compile(source, module, "exec")
            (package / module).write_bytes(source)

        glue = (
            "\n# r70 candidate: passive telemetry integration; playback plan untouched.\n"
            "try:\n"
            "    from .r70_monitor_adapter import attach_monitor as _r70_attach\n"
            "    _r70_attach(SatFallbackMonitor)\n"
            "except Exception:\n"
            "    pass  # Always prefer the unmodified r69 playback to a failed adapter.\n"
        )
        fta_monitor_glue = (
            "\n# r70-rc3: opt-in FTA no-signal only; preserve native deferred DVB/PAT.\n"
            "try:\n"
            "    from .fta_runtime_adapter import attach_monitor as _rc3_fta_attach\n"
            "    _rc3_fta_attach(SatFallbackMonitor)\n"
            "except Exception:\n"
            "    pass  # fail closed: native encrypted-only mode remains active\n"
        )
        mon_path.write_bytes(baseline_monitor + glue.encode("utf-8") + fta_monitor_glue.encode("utf-8"))
        for filename, key in (("plugin.py", "PLUGIN_VERSION"),
                              ("updater.py", "CURRENT_VERSION")):
            p = package / filename
            before = p.read_text()
            p.write_text(once(before, key + ' = "1.0.46-r69-beta"',
                              key + ' = "' + VERSION + '"'))

        # Preview is a UI-only source transformation. Abort on any baseline drift.
        preview_ns = {}
        exec(compile((ROOT / "r70/r70_preview_patch.py").read_bytes(),
                     "r70_preview_patch.py", "exec"), preview_ns)
        plugin_path.write_text(preview_ns["improve"](plugin_path.read_text()))

        # Hook *user-initiated* manual mapping saves only; original UI unchanged.
        # Native r69 overrides remain the authority, and no I/O occurs on zap.
        plugin_glue = (
            "\n# r70: backup mirror of manual locks, legacy mappings are authoritative.\n"
            "try:\n"
            "    from .r70_lock_adapter import attach_mapping_hooks as _r70_locks\n"
            "    _r70_locks(globals())\n"
            "except Exception:\n"
            "    pass  # r69 manual lock behavior wins in case of adapter issue.\n"
        )
        plugin_path.write_bytes(plugin_path.read_bytes() + plugin_glue.encode("utf-8"))
        preview_glue = (
            "\n# r70: asynchronous All Sources index-ranking, no playback modifications.\n"
            "try:\n"
            "    from .r70_preview_async import attach_alternatives as _r70_preview_attach\n"
            "    _r70_preview_attach(SatIPTVBridgeAlternatives, globals())\n"
            "except Exception:\n"
            "    pass  # preserve native Preview if async adapter is unavailable.\n"
        )
        plugin_path.write_bytes(plugin_path.read_bytes() + preview_glue.encode("utf-8"))
        fta_plugin_glue = (
            "\n# r70-rc3 opt-in FTA no-signal option + TV roster\n"
            "try:\n"
            "    from .fta_runtime_adapter import attach_plugin as _rc3_fta_plugin\n"
            "    _rc3_fta_plugin(globals())\n"
            "except Exception:\n"
            "    pass  # no new menu or FTA fallback on unavailable API\n"
        )
        plugin_path.write_bytes(plugin_path.read_bytes() + fta_plugin_glue.encode("utf-8"))

        # The inherited r69 postinst still prints "r62 installed".
        # Replace only the stale human-readable label, never its commands.
        postinst = work / "control/postinst"
        if postinst.is_file():
            post_text = postinst.read_text()
            post_text = post_text.replace(
                "IPToSat Pro 1.0.46-r62 installed",
                "IPToSat Pro " + VERSION + " candidate installed"
            )
            postinst.write_text(post_text)

        control_path = work / "control/control"
        ctrl = control_path.read_text()
        ctrl = once(ctrl, "Version: 1.0.46-r69-beta", "Version: " + VERSION)
        ctrl = re.sub(r"^Description:.*$",
                      "Description: IPToSat Pro r70 unified RC - hardware validation required",
                      ctrl, flags=re.M)
        control_path.write_text(ctrl)

        (package / "R70-UNIFIED-RC-HOLD.txt").write_text(
            "r70 candidate: all eight safety components staged.\n"
            "Real evidence, no-frame advisory, manual lock mirror, watchdog policy, "
            "source health, advisory audio guard, candidate history, update preflight.\n"
            "Live recovery, black pixel analysis and updater activation require receiver validation.\n"
            "r69 playback plan, native SAT/timeshift, core and TS relay unchanged.\n"
            "NOT PUBLISHED: never update update.json from this script.\n"
        )
        # Show exact non-regression in the original monitor code.
        current = mon_path.read_bytes()
        if not current.startswith(baseline_monitor) or len(current) == len(baseline_monitor):
            raise AssertionError("r69 original monitor altered")
        for name in ("plugin.py", "monitor.py", "r70_safety_core.py",
                     "r70_monitor_adapter.py", "r70_lock_adapter.py", "r70_preview_async.py", "no_signal_policy.py", "fta_runtime_adapter.py", "core.py", "updater.py"):
            compile((package / name).read_bytes(), name, "exec")
        for name in ("data", "control"):
            dest = work / (name + ".tar.gz")
            with tarfile.open(dest, "w:gz", format=tarfile.GNU_FORMAT) as tar:
                for f in sorted((work / name).rglob("*")):
                    if "__pycache__" in f.parts or f.suffix in (".pyc", ".pyo"):
                        continue
                    tar.add(f, arcname="./" + str(f.relative_to(work / name)),
                            recursive=False)
        (work / "debian-binary").write_text("2.0\n")
        candidate = work / "r70-candidate.ipk"
        subprocess.run(["ar", "r", str(candidate), str(work / "debian-binary"),
                        str(work / "control.tar.gz"), str(work / "data.tar.gz")],
                       check=True, stdout=subprocess.PIPE)
        shutil.copyfile(candidate, OUT)

    built = OUT.read_bytes()
    assert built.startswith(b"!<arch>\n")
    print("R70_CANDIDATE_BUILT", VERSION, "bytes=", len(built),
          "sha256=", hashlib.sha256(built).hexdigest())
    print("HOLD: no release, no merge, no update.json change, receiver tests required")


if __name__ == "__main__":
    main()
