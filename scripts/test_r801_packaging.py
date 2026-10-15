#!/usr/bin/env python3
"""R80.1 beta package parity. All tests offline and use only synthetic data."""
import ast
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load("r801_original", "build-r80-final-rc1.py")
candidate = load("r801_build", "build-r801-preview-hotpath.py")
patch = load("r801_only_patch", "r80_preview_hotpath_patch.py")


class BuildR801Beta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        directory = Path(cls.tmp.name)
        old_path = directory / "original.ipk"
        new_path = directory / "candidate.ipk"
        cls.old_meta = base.build(old_path)
        cls.new_meta = candidate.build(new_path)
        cls.old_data = base.pack.members_from(
            base.pack.unpack_ar(old_path.read_bytes())["data.tar.gz"])
        cls.new_data = base.pack.members_from(
            base.pack.unpack_ar(new_path.read_bytes())["data.tar.gz"])
        cls.old_ctrl = base.pack.members_from(
            base.pack.unpack_ar(old_path.read_bytes())["control.tar.gz"])
        cls.new_ctrl = base.pack.members_from(
            base.pack.unpack_ar(new_path.read_bytes())["control.tar.gz"])
        cls.raw = new_path.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_pinned_source_digest_and_nonproduction(self):
        self.assertEqual(self.old_meta["sha256"], candidate.BASE_SHA)
        self.assertEqual(self.new_meta["source_sha256"], candidate.BASE_SHA)
        self.assertEqual(self.new_meta["version"], candidate.VERSION)
        self.assertFalse(self.new_meta["receiver_tested"])
        self.assertFalse(self.new_meta["production_published"])
        self.assertFalse(self.new_meta["cold_target_met"])
        self.assertEqual(self.new_meta["sha256"], hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(self.new_meta["size"], len(self.raw))

    def test_every_other_file_is_byte_exact(self):
        self.assertEqual(set(self.new_data), set(self.old_data) | {candidate.NOTE})
        for path, data in self.old_data.items():
            if path not in {candidate.CORE, candidate.PLUGIN, candidate.UPDATER}:
                self.assertEqual(self.new_data[path], data, path)
        self.assertEqual(self.new_data[candidate.CORE],
                         patch.patch_core(self.old_data[candidate.CORE].decode()).encode())
        self.assertIn(patch.TAG.encode(), self.new_data[candidate.CORE])

    def test_matching_changes_are_ast_scoped(self):
        before = ast.parse(self.old_data[candidate.CORE])
        after = ast.parse(self.new_data[candidate.CORE])
        def fns(tree):
            catalog = next(x for x in tree.body if isinstance(x, ast.ClassDef)
                           and x.name == "Catalog")
            found = {"Catalog." + x.name: ast.dump(x, include_attributes=False)
                     for x in catalog.body if isinstance(x, ast.FunctionDef)}
            for i, x in enumerate(n for n in tree.body if isinstance(n, ast.FunctionDef)
                                  and n.name == "match_score_details"):
                found["match_score_details_%d" % i] = ast.dump(x, include_attributes=False)
            return found
        old, new = fns(before), fns(after)
        self.assertEqual(old.keys(), new.keys())
        self.assertEqual({name for name in old if old[name] != new[name]},
                         {"Catalog.fast_rank_matches_all_servers", "match_score_details_0"})

    def test_version_and_manifest_only_changes_elsewhere(self):
        old_ui = self.old_data[candidate.PLUGIN].decode()
        new_ui = self.new_data[candidate.PLUGIN].decode()
        self.assertEqual(
            new_ui,
            old_ui.replace('PLUGIN_VERSION = "' + candidate.OLD + '"',
                           'PLUGIN_VERSION = "' + candidate.VERSION + '"', 1))
        old_updater = self.old_data[candidate.UPDATER].decode()
        new_updater = self.new_data[candidate.UPDATER].decode()
        self.assertEqual(
            new_updater,
            old_updater.replace('CURRENT_VERSION = "' + candidate.OLD + '"',
                                'CURRENT_VERSION = "' + candidate.VERSION + '"', 1)
            .replace(candidate.PREVIOUS_MANIFEST, candidate.MANIFEST, 1))
        self.assertIn("Version: " + candidate.VERSION,
                      self.new_ctrl["control"].decode())

    def test_passive_postinst_no_mutations(self):
        self.assertEqual(self.new_ctrl["postinst"], candidate.POSTINST)
        self.assertFalse({"preinst", "prerm", "postrm"}.intersection(self.new_ctrl))
        post = self.new_ctrl["postinst"].decode()
        for word in ("rm ", "mv ", "opkg ", "wget ", "curl ",
                     "python3 ", "import_spec", "cache_migrator"):
            self.assertNotIn(word, post)

    def test_no_user_mapping_or_receiver_files_in_package(self):
        for name in self.new_data:
            lower = name.lower()
            self.assertFalse(lower.startswith("etc/enigma2"), name)
            if any(token in lower for token in (
                    "mapping", "override", "catalog", "cache", "player",
                    "serviceapp", "theme", "skin")):
                self.assertEqual(self.new_data[name], self.old_data[name], name)


if __name__ == "__main__":
    unittest.main()
