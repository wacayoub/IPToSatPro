#!/usr/bin/env python3
"""No receiver bootstrap may omit a file required by the current local IPK builder."""
from pathlib import Path
import ast
import re
ROOT = Path(__file__).resolve().parents[1]
boot = (ROOT / "scripts/receiver-build-r70-test.sh").read_text()
builder = (ROOT / "scripts/build-r70-candidate.py").read_text()
required = [
    "scripts/build-r70-candidate.py",
    "scripts/portable_ar_r70.py",
    "r70/r70_safety_core.py",
    "r70/r70_monitor_adapter.py",
    "r70/r70_lock_adapter.py",
    "r70/r70_preview_patch.py",
    "r70/r70_preview_async.py",
    "r70/no_signal_policy.py",
    "r70/fta_runtime_adapter.py",
    "r70/preview_autotest_rc4.py",
    "r70/player_recovery_rc5.py",
    "r70/tod_audio_recovery_rc6.py",
    "payload/r69-beta.b64",
]
for path in required:
    if not (ROOT / path).is_file():
        raise AssertionError("Missing source in repository: " + path)
    if not re.search(r"(?m)^    " + re.escape(path) + r"\s*(?:\\)?$", boot):
        raise AssertionError("Receiver bootstrap omits: " + path)
assert '"1.0.46-r70-rc6"' in builder
assert "1.0.46-r70-rc6" in boot
assert "r70_preview_patch.py" in builder
assert "r70_preview_async.py" in builder
assert "feature/r70-rc6-tod-audio-recovery" in boot, "Wrong GitHub branch for receiver build"
compile(ast.parse(builder), "builder", "exec")
print("PASS receiver bootstrap includes every r70-rc6 source file and correct version")
