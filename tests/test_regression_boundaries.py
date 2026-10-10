"""Forensic boundary tests: identify first code releases that changed good behavior.

These are exact tests against published archived IPK Python sources, not Vu+
hardware tests and not a request to install any older version.
"""
import ast
import base64
import io
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
VERSIONS=("r65","r66-beta","r67-beta","r68-beta","r69-beta")


def source(version, component):
    with tempfile.TemporaryDirectory() as td:
        ipk=Path(td)/"archived.ipk"
        ipk.write_bytes(base64.b64decode(
            (ROOT/"payload"/(version+".b64")).read_bytes()))
        tgz=subprocess.check_output(["ar","p",str(ipk),"data.tar.gz"])
    with tarfile.open(fileobj=io.BytesIO(tgz),mode="r:gz") as tf:
        target="./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"+component
        return tf.extractfile(target).read().decode()


def method(src, spec):
    first,second=spec.split(".",1) if "." in spec else ("",spec)
    tree=ast.parse(src)
    block=tree.body
    if first:
        klass=next(x for x in block if isinstance(x,ast.ClassDef) and x.name==first)
        block=klass.body
    meth=next(x for x in block if isinstance(x,ast.FunctionDef) and x.name==second)
    return "\n".join(src.splitlines()[meth.lineno-1:meth.end_lineno])


class LegacyRegressionBoundaries(unittest.TestCase):
    def test_core_matching_unchanged_r65_to_r69(self):
        from hashlib import sha256
        h=[sha256(source(v,"core.py").encode()).hexdigest() for v in VERSIONS]
        self.assertEqual(len(set(h)),1)

    def test_r66_immediate_preview_discovery_present(self):
        s=method(source("r66-beta","plugin.py"),
            "SatIPTVBridgePreview._load_selected_sat_candidates")
        self.assertIn("_rank_sat_ref_instant(raw, topn=12, per_server=4)",s)
        self.assertIn("self._merge_locked_candidate(key, channels)",s)

    def test_r67_removed_instant_discovery_and_lock_merge(self):
        s=method(source("r67-beta","plugin.py"),
            "SatIPTVBridgePreview._load_selected_sat_candidates")
        self.assertNotIn("_rank_sat_ref_instant(raw",s)
        self.assertNotIn("self._merge_locked_candidate(key, channels)",s)
        self.assertIn("cached = (sat_name, dict(ctx or {}), [], False)",s)

    def test_r68_native_plan_added_unmeasured_uhd_restriction(self):
        before=method(source("r67-beta","monitor.py"),
            "SatFallbackMonitor._build_candidate_plan")
        after=method(source("r68-beta","monitor.py"),
            "SatFallbackMonitor._build_candidate_plan")
        self.assertNotIn("UHD_UNKNOWN_SKIP",before)
        self.assertIn("UHD_UNKNOWN_SKIP",after)

    def test_r68_player_failures_persist_a_failed_mode(self):
        before=method(source("r67-beta","monitor.py"),
            "SatFallbackMonitor._handle_iptv_failure")
        after=method(source("r68-beta","monitor.py"),
            "SatFallbackMonitor._handle_iptv_failure")
        self.assertNotIn('rec["last_failed_player"]',before)
        self.assertIn('rec["last_failed_player"]',after)

    def test_r69_retains_r67_preview_and_r68_candidate_plan(self):
        v67=method(source("r67-beta","plugin.py"),
            "SatIPTVBridgePreview._load_selected_sat_candidates")
        v69=method(source("r69-beta","plugin.py"),
            "SatIPTVBridgePreview._load_selected_sat_candidates")
        self.assertEqual(v67,v69)
        v68=method(source("r68-beta","monitor.py"),
            "SatFallbackMonitor._build_candidate_plan")
        latest=method(source("r69-beta","monitor.py"),
            "SatFallbackMonitor._build_candidate_plan")
        self.assertEqual(v68,latest)


if __name__=="__main__":
    unittest.main()
