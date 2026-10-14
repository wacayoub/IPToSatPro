#!/usr/bin/env python3
"""R76.10 real-IPK regression: optimize ONLY normal Preview 48/16."""
import ast
import tempfile
import unittest
from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "r7610build", ROOT / "scripts" / "build-r7610-normal48.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class NormalPreview48Safety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        old = Path(cls.tmp.name) / "old.ipk"
        new = Path(cls.tmp.name) / "new.ipk"
        cls.old_info = b.previous.build(old)
        cls.info = b.build(new)
        cls.old = b.pack.members_from(
            b.pack.unpack_ar(old.read_bytes())["data.tar.gz"])
        cls.new = b.pack.members_from(
            b.pack.unpack_ar(new.read_bytes())["data.tar.gz"])
        cls.old_core = cls.old[b.CORE].decode("utf-8")
        cls.new_core = cls.new[b.CORE].decode("utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_only_two_budget_gates_change_in_core(self):
        expected = self.old_core.replace(
            b.fix.OLD_DECORATED, b.fix.NEW_DECORATED, 1).replace(
            b.fix.OLD_POOL, b.fix.NEW_POOL, 1)
        self.assertEqual(self.new_core, "# " + b.fix.TAG + "\n" + expected)
        self.assertEqual(self.new_core.count(b.fix.NEW_DECORATED), 1)
        self.assertEqual(self.new_core.count(b.fix.NEW_POOL), 1)
        ast.parse(self.new_core)

    def test_repeated_patch_no_double_mutation(self):
        self.assertEqual(b.fix.patch_core(self.new_core), self.new_core)
        with self.assertRaises(AssertionError):
            b.fix.patch_core("def wrong(): pass\n")

    def test_48_candidate_regime_is_fast_and_192_stays_deep(self):
        # Parse exact active expressions from the packaged core, rather than
        # only checking the patch script content.
        ast.parse(self.new_core)
        self.assertIn("if limit > 48 else {}", self.new_core)
        self.assertIn("if limit <= 48 and roles_cap <= 16 else", self.new_core)
        self.assertNotIn(b.fix.OLD_POOL, self.new_core)
        self.assertNotIn(b.fix.OLD_DECORATED, self.new_core)
        for limit, roles, expected_fast in (
            (24, 8, True), (48, 16, True),
            (49, 16, False), (48, 17, False), (192, 64, False)):
            self.assertEqual(limit <= 48 and roles <= 16, expected_fast)

    def test_match_safety_and_deep_search_code_unchanged(self):
        before = ast.parse(self.old_core)
        after = ast.parse(self.new_core)
        # The policy function implementations are exactly the same; only the
        # two bounds inside ranking/index nomination may differ.
        for name in ("match_score_details", "match_decision"):
            prev = next((n for n in before.body if isinstance(n, ast.FunctionDef) and n.name == name), None)
            nxt = next((n for n in after.body if isinstance(n, ast.FunctionDef) and n.name == name), None)
            self.assertEqual(ast.dump(prev, include_attributes=False),
                             ast.dump(nxt, include_attributes=False), name)
        self.assertIn("fast_preview_mega_matches", self.new_core)

    def test_exact_changed_asset_set_and_protected_player(self):
        changed = {n for n in self.old if self.old[n] != self.new[n]}
        self.assertEqual(changed, {b.PLUGIN, b.UPDATER, b.CORE})
        self.assertEqual(set(self.new) - set(self.old), {b.NOTE})
        for name in ("monitor.py", "player.py", "metadata_shadow.py",
                     "preview_theme_r74.py", "home_themes_r767.py"):
            path = b.P + name
            self.assertEqual(self.old.get(path), self.new.get(path), name)
        self.assertFalse(any("mapping" in p.lower() or "override" in p.lower()
                             for p in changed))

    def test_plugin_ranking_and_manual_override_logic_unchanged(self):
        plugin_before = self.old[b.PLUGIN].decode()
        plugin_after = self.new[b.PLUGIN].decode()
        self.assertEqual(plugin_after,
                         plugin_before.replace(
                             'PLUGIN_VERSION = "' + b.OLD + '"',
                             'PLUGIN_VERSION = "' + b.VERSION + '"', 1))
        self.assertIn("R769_PREVIEW_MANUAL_PARITY", plugin_after)
        self.assertIn("candidate_budget = 192 if self._r71_worker_deep else 48",
                      plugin_after)
        self.assertIn("candidate_per_server = 64 if self._r71_worker_deep else 16",
                      plugin_after)

    def test_no_production_version_replaced_or_claimed(self):
        self.assertFalse(self.info["production_published"])
        self.assertFalse(self.info["receiver_tested"])
        self.assertTrue(self.info["beta"])
        self.assertEqual(self.info["changed"], [b.CORE, b.PLUGIN, b.UPDATER] if
                         [b.CORE, b.PLUGIN, b.UPDATER] == sorted([b.CORE, b.PLUGIN, b.UPDATER])
                         else sorted([b.CORE, b.PLUGIN, b.UPDATER]))
        updater = self.new[b.UPDATER].decode()
        self.assertIn(b.MANIFEST, updater)
        self.assertNotIn(
            "feature/r769-preview-manual-parity/staging/r76-metrix-preview.update.json",
            updater)


if __name__ == "__main__":
    unittest.main()
