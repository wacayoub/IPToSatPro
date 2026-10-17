#!/usr/bin/env python3
"""Static release invariant tests for opt-in r70. No receiver/network calls."""
import ast
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from audit_r70_baseline import load_release, PREFIX
import importlib.util
_builder_path = Path(__file__).with_name("build-r70-final.py")
_spec = importlib.util.spec_from_file_location("r70_builder", _builder_path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
ROOT, build = _module.ROOT, _module.build
unpack_ar, members_from = _module.unpack_ar, _module.members_from
NEW_VERSION, BASE_VERSION = _module.NEW_VERSION, _module.BASE_VERSION
VERSION_PATHS, CHANGELOG = _module.VERSION_PATHS, _module.CHANGELOG


class R70CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.temp.name) / "candidate.ipk"
        cls.meta = build(cls.out)
        cls.files = members_from(unpack_ar(cls.out.read_bytes())["data.tar.gz"])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_two_separate_rebuilds_are_byte_identical(self):
        path = Path(self.temp.name) / "candidate-again.ipk"
        built_again = build(path)
        self.assertEqual(built_again["sha256"], self.meta["sha256"])
        self.assertEqual(path.read_bytes(), self.out.read_bytes())

    def test_package_integrity_and_labeled_release(self):
        self.assertEqual(self.meta["version"], NEW_VERSION)
        self.assertFalse(self.meta["logic_changed"])
        self.assertFalse(self.meta["published"])
        self.assertFalse(self.meta["receiver_tested"])
        self.assertFalse(self.meta["tod_included"])
        self.assertGreater(self.meta["size"], 250000)
        self.assertEqual(self.meta["sha256"],
                         hashlib.sha256(self.out.read_bytes()).hexdigest())

    def test_exact_original_runtime_methods_unchanged(self):
        originals = load_release()
        for key, before in originals.items():
            with self.subTest(module=key):
                new = self.files[key]
                if key not in VERSION_PATHS:
                    self.assertEqual(new, before)
                else:
                    a = ast.parse(before)
                    b = ast.parse(new)
                    def remove_version(t):
                        for node in t.body:
                            if isinstance(node, ast.Assign):
                                if len(node.targets)==1 and isinstance(node.targets[0], ast.Name):
                                    if node.targets[0].id in ("CURRENT_VERSION","PLUGIN_VERSION"):
                                        node.value = ast.Constant(value="PINNED")
                        return ast.dump(t, include_attributes=False)
                    self.assertEqual(remove_version(a), remove_version(b))

    def test_no_tod_payload_or_experimental_hooks(self):
        self.assertFalse(any(key.lower().find("tod_") >= 0
                             for key in self.files))
        self.assertFalse(any("tod_dynamic" in key.lower()
                             for key in self.files))
        self.assertIn(CHANGELOG, self.files)

    def test_existing_manual_mapping_and_relay_files_stay_identical(self):
        original = load_release()
        for module in ("core.py", "monitor.py", "timeshift_seek_patch.py",
                       "converter_patch.py", "metadata_shadow.py"):
            path = PREFIX + module
            self.assertEqual(self.files[path], original[path])
        ctrl = members_from(unpack_ar(self.out.read_bytes())["control.tar.gz"])
        self.assertIn(("Version: "+NEW_VERSION).encode(),ctrl["control"])

    def test_manifest_is_only_known_approved_r69_or_released_r70(self):
        manifest = json.loads((ROOT/"update.json").read_text())
        authorized = {
            BASE_VERSION: ("123e1118a7471075ad18dee3014b7367fa9a2cf02f8cdd52ad1e5e65034035ed", None),
            NEW_VERSION: ("471039d712e81c03bacbcf0394325dd07b56d8bbf3f2002bf6a48f89f93b791c", self.meta["size"]),
            "1.0.46-r80.2-final": ("5c7e48ba51e5ed1689c5930df72309c7c495cc702f5cff6b91142ddc2985606a", 461198)
        }
        self.assertIn(manifest["version"], authorized)
        approved_sha, approved_size = authorized[manifest["version"]]
        self.assertEqual(manifest["sha256"], approved_sha)
        if approved_size is not None:
            self.assertEqual(manifest["size"], approved_size)
        if manifest["version"] == "1.0.46-r80.2-final":
            self.assertEqual(manifest["parts"], [
                "https://raw.githubusercontent.com/wacayoub/IPToSatPro/main/payload/r80-final.b64"
            ])

    def test_package_does_not_include_cache_or_channel_credentials(self):
        for key in self.files:
            self.assertFalse(key.endswith(".pyc"))
            self.assertNotIn("__pycache__",key)
            self.assertNotIn("/etc/enigma2/settings",key)
            self.assertNotIn("userbouquet.",key)


if __name__ == "__main__":
    unittest.main()
