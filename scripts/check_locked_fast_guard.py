#!/usr/bin/env python3
"""Fail CI if the user-confirmed r64 MANUAL_LOCK fast path changes silently.

Checks packages offline; no Enigma2, IPTV credentials, network, stream probes or
receiver modifications. An intentional runtime change requires receiver testing
and explicitly revising the approved r64 baseline policy.
"""
import ast
import base64
import hashlib
import io
import json
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "efee95fb38929f3f8f5f0aea2795f524e447a83694c1a6bc4249dd2230eb208c"
PROTECTED_METHODS = (
    "_fast_zap_enabled",
    "_prewarm_locked_stream",
    "_direct_hot_get",
    "_direct_hot_put",
    "_video_timeout_ms",
    "_on_start",
    "_native_pat_guard_remaining_ms",
    "_fallback_with_native_pat_guard",
    "_native_pat_guard_fire",
    "_play_match",
)
PROTECTED_CONSTANTS = (
    "FAST_VERIFY_STEP_MS",
    "FAST_MAPPED_DELAY_MS",
    "FAST_LOCK_PREWARM_TIMEOUT_S",
    "FAST_LOCK_NATIVE_TIMEOUT_MS",
    "FAST_LOCK_UHD_NATIVE_TIMEOUT_MS",
    "FAST_LOCK_SERVICEAPP_TIMEOUT_MS",
    "NATIVE_PAT_GUARD_MS",
    "NATIVE_PAT_GUARD_POLL_MS",
)

def decode_payload(path):
    blob = base64.b64decode(path.read_bytes(), validate=False)
    if not blob.startswith(b"!<arch>\n"):
        raise ValueError("Invalid IPK ar header for " + str(path))
    return blob

def data_members(ipk):
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        package = Path(tmp) / "package.ipk"
        package.write_bytes(ipk)
        data = subprocess.run(
            ["ar", "p", str(package), "data.tar.gz"],
            capture_output=True, check=True,
        )
    with tarfile.open(fileobj=io.BytesIO(data.stdout), mode="r:*") as tf:
        names = tf.getnames()
        def get(suffix):
            hits = [n for n in names if n.lstrip("./").endswith(suffix.lstrip("/"))]
            if len(hits) != 1:
                raise ValueError("Missing or duplicate archive path: " + suffix)
            return tf.extractfile(hits[0]).read()
        return (
            get("/SatIPTVBridge/monitor.py"),
            get("/usr/bin/iptosat-tsbridge"),
            get("/etc/init.d/iptosat-tsbridge"),
        )

def protected_ast(raw):
    tree = ast.parse(raw)
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef)
               and node.name == "SatFallbackMonitor")
    nodes = {}
    for node in cls.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in PROTECTED_METHODS:
                nodes[node.name] = ast.dump(node, include_attributes=False)
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in PROTECTED_CONSTANTS:
                nodes[target.id] = ast.literal_eval(node.value)
    missing = (set(PROTECTED_METHODS) | set(PROTECTED_CONSTANTS)) - set(nodes)
    if missing:
        raise ValueError("Missing lock invariants: " + ", ".join(sorted(missing)))
    return nodes

def main():
    baseline = decode_payload(ROOT / "payload/r64.b64")
    if hashlib.sha256(baseline).hexdigest() != BASE_SHA:
        raise ValueError("Pinned known-good r64 SHA256 mismatch")
    if len(sys.argv) > 1:
        # Release-build gate: check an IPK *before* it is published.
        candidate_path = Path(sys.argv[1])
        candidate = candidate_path.read_bytes()
        if not candidate.startswith(b"!<arch>\n"):
            raise ValueError("Invalid candidate IPK ar header")
        version = candidate_path.name
    else:
        # Post-publication check: validate the current online update.
        manifest = json.loads((ROOT / "update.json").read_text())
        version = manifest["version"]
        rev = version.rsplit("-r", 1)[-1]
        candidate_path = ROOT / ("payload/r%s.b64" % rev)
        candidate = decode_payload(candidate_path)
        size = len(candidate)
        sha = hashlib.sha256(candidate).hexdigest()
        if size != manifest["size"] or sha != manifest["sha256"]:
            raise ValueError("Candidate size / SHA256 mismatch with online manifest")
    base_monitor, base_relay, base_init = data_members(baseline)
    cand_monitor, cand_relay, cand_init = data_members(candidate)
    before = protected_ast(base_monitor)
    after = protected_ast(cand_monitor)
    changed = [name for name in sorted(before) if before[name] != after[name]]
    if base_relay != cand_relay:
        changed.append("iptosat-tsbridge binary")
    if base_init != cand_init:
        changed.append("iptosat-tsbridge init")
    if changed:
        print("LOCKED FAST-OPEN REGRESSION REVIEW REQUIRED:", ", ".join(changed))
        print("Do not auto-publish without receiver field testing and explicit baseline review.")
        return 1
    print("PASS LOCKED FAST-OPEN GUARDED:", version,
          "| approved prewarm, PMT guard, mapping, timeout and relay unchanged")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("LOCKED FAST-OPEN GUARD ERROR:", exc, file=sys.stderr)
        sys.exit(1)

# CI guard automatically checks each published IPK against the field-proven r64 path.
