#!/usr/bin/env python3
"""R71 test actual packaged core, not a replacement scorer or simulated Enigma2."""
import base64
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_BUILDER = Path(__file__).with_name("build-r71-beta.py")
_spec = importlib.util.spec_from_file_location("r71_builder", _BUILDER)
_builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_builder)
ROOT = _builder.ROOT
P = _builder.PREFIX

CASES = [
    ("Ushuaia TV HD", "Ushuaia TV HD", "ITALY", "FR", "SAFE"),
    ("Ushuaia TV HD", "Ushuaia TV FHD", "ITALY", "FR", "SAFE"),
    ("Ushuaia TV HD", "Ushuaia TV FHD", "ITALY", "", "REVIEW"),
    ("Ushuaia TV HD", "Ushuaia TV HD", "ITALY", "IT", "REVIEW"),
    ("Ushuaia TV HD", "FR: Ushuaia TV HD", "FRANCE", "FR", "SAFE"),
    ("Ushuaia TV HD", "IT: Ushuaia TV HD", "ITALY", "IT", "REJECT"),
    ("CANAL+ Golf HD", "CANAL+ Golf FHD", "POLAND", "FR", "SAFE"),
    ("CANAL+ Golf HD", "CANAL+ Golf FHD", "POLAND", "", "REVIEW"),
    ("CANAL+ Golf HD", "PL: CANAL+ Golf FHD", "POLAND", "PL", "REJECT"),
    ("CANAL+ Golf HD", "FR: CANAL+ Golf FHD", "FRANCE", "FR", "SAFE"),
    ("beIN Sports 6 HD", "FR: beIN Sports 6 HD", "FRANCE", "FR", "SAFE"),
    ("beIN Sports 6 HD", "FR: beIN Sports 8 HD", "FRANCE", "FR", "REJECT"),
    ("beIN Sports 1 HD", "beIN Sports 1 FHD", "ITALY", "FR", "SAFE"),
    ("beIN Sports 1 HD", "beIN Sports 2 FHD", "ITALY", "FR", "REJECT"),
    ("Nat Geo HD", "Nat Geo FHD", "ITALY", "FR", "SAFE"),
    ("Nat Geo HD", "Nat Geo FHD", "ITALY", "", "REVIEW"),
    ("FRANCE 2 HD", "FRANCE 3 HD", "FRANCE", "FR", "REJECT"),
    ("OSN Movies 1", "OSN Movies 2", "ITALY", "FR", "REJECT"),
    ("MBC 1 HD", "MBC 2 HD", "ITALY", "FR", "REJECT"),
    ("Sky Cinema 1", "Sky Cinema 2", "ITALY", "FR", "REJECT"),
    ("Canal+ Sport HD", "FR: Canal+ Sport FHD", "FRANCE", "FR", "SAFE"),
    ("Canal+ Sport HD", "PL: Canal+ Sport FHD", "POLAND", "PL", "REJECT"),
]
CTX = {"confidence": "HIGH", "market_preferences": ["FR"],
       "language_priorities": ["FR"], "audio_language_set": ["FR"],
       "audio_language_target": "FR", "provider": "ABSat",
       "sat_provider": "ABSat", "orbital_position": 130}


def load_from_ipk(package_path):
    data = _builder.members_from(_builder.unpack_ar(package_path.read_bytes())["data.tar.gz"])
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "core.py"
        path.write_bytes(data[P + "core.py"])
        spec = importlib.util.spec_from_file_location("r71_real_core", path)
        obj = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(obj)
    return obj, data


class R71StabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.tmp.name) / "r71.ipk"
        cls.meta = _builder.build(cls.path)
        cls.core, cls.files = load_from_ipk(cls.path)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_22_channel_cases_in_both_modes(self):
        self.assertGreaterEqual(len(CASES), 20)
        for sat, name, group, language, expected in CASES:
            for preview in [False, True]:
                with self.subTest(sat=sat, iptv=name, preview=preview):
                    ch = {"name": name, "group": group, "language": language,
                          "server_priority": 1, "url": "http://127.0.0.1/NOT_USED"}
                    score, details = self.core.match_score_details(
                        sat, ch, ["FR"], dict(CTX), "best", preview=preview)
                    state = self.core.match_decision(score, details, 82.0)
                    print("R71_REAL_CASE", sat, name, group, language,
                          "preview" if preview else "auto", round(score,1), state,
                          "REJECT", details.get("reject_reason"),
                          "REVIEW", details.get("review_reason"),
                          "ALLOW", details.get("allow_reason"))
                    self.assertEqual(state, expected)
                    if expected == "REJECT":
                        self.assertTrue(details.get("reject_reason"))
                    if expected == "SAFE":
                        self.assertFalse(details.get("reject_reason"))
                        self.assertFalse(details.get("review_reason"))

    def test_baseline_manifest_untouched(self):
        manifest = json.loads((ROOT / "update.json").read_text())
        self.assertEqual(manifest["version"], "1.0.46-r70-final")
        self.assertEqual(manifest["sha256"], _builder.R70_SHA)
        self.assertFalse(self.meta["published"])
        self.assertFalse(self.meta["field_tested"])
        self.assertFalse(self.meta["player_changed"])
        self.assertFalse(self.meta["tod_included"])

    def test_byte_exact_protected_runtime_and_replay(self):
        orig = _builder.members_from(_builder.unpack_ar(_builder.get_r70())["data.tar.gz"])
        allowed = {P + "core.py", P + "plugin.py", P + "updater.py"}
        for key, data in orig.items():
            with self.subTest(file=key):
                if key not in allowed:
                    self.assertEqual(data, self.files[key])
        self.assertEqual(self.meta["changed"], sorted(allowed))
        for name in self.files:
            self.assertFalse(name.endswith(".pyc"))
            self.assertNotIn("__pycache__",name)
            self.assertNotIn("tod_dynamic", name.lower())

    def test_reproducible_sha256(self):
        again = Path(self.tmp.name) / "again.ipk"
        result = _builder.build(again)
        self.assertEqual(again.read_bytes(), self.path.read_bytes())
        self.assertEqual(result["sha256"], hashlib.sha256(self.path.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()
