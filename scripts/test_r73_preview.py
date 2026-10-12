#!/usr/bin/env python3
"""R73 isolated preview regression suite; no Enigma2 or IPTV connectivity required."""
import ast
import base64
import importlib.util
import pathlib
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("r73_builder", HERE/"build-r73-preview.py")
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)

class R73PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.destination = pathlib.Path(cls.temp.name)/"r73.ipk"
        cls.info = b.build(cls.destination)
        cls.contents = b.base.pack.members_from(
            b.base.pack.unpack_ar(cls.destination.read_bytes())["data.tar.gz"])
        cls.previous = b.base.pack.members_from(
            b.base.pack.unpack_ar(base64.b64decode(b.B64.read_bytes()))["data.tar.gz"])
        cls.source = cls.contents[b.PLUGIN].decode()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_expanded_candidate_list_no_longer_truncated_at_48(self):
        # Confirm BOTH the post-rank presentation path and the 72-row expansion budget.
        self.assertIn('return self._compact_candidate_duplicates(rows)\n', self.source)
        self.assertNotIn('return self._compact_candidate_duplicates(rows, limit=self.MAX_BROWSER_CANDIDATES)', self.source)
        self.assertIn('candidate_budget = 72 if self._r71_worker_deep else self.MAX_BROWSER_CANDIDATES', self.source)
        self.assertIn('[:(72 if self._r71_worker_deep else self.MAX_BROWSER_CANDIDATES)]', self.source)

    def test_configuration_change_invalidates_preview_cache(self):
        self.assertIn('str(cfg.languages.value)', self.source)
        self.assertIn('str(cfg.match_threshold.value)', self.source)
        self.assertIn('str(cfg.quality_mode.value)', self.source)
        self.assertIn('ui_policy)', self.source)

    def test_manual_lock_no_fabricated_150_score(self):
        self.assertIn('float((manual or {}).get("auto_scan_score") or 0.0)', self.source)
        self.assertNotIn('float((manual or {}).get("auto_scan_score") or 150.0)', self.source)

    def test_player_monitor_core_untouched(self):
        self.assertEqual(set(self.contents), set(self.previous)|{b.CHANGELOG})
        for name,blob in self.previous.items():
            if name not in (b.PLUGIN,b.UPDATER):
                self.assertEqual(blob, self.contents[name], name)
        old=ast.parse(self.previous[b.PLUGIN]); new=ast.parse(self.contents[b.PLUGIN])
        def changed(before,after):
            names = {}
            for node in ast.walk(before):
                if isinstance(node,ast.FunctionDef):
                    names[node.name] = ast.dump(node, include_attributes=False)
            other = {}
            for node in ast.walk(after):
                if isinstance(node,ast.FunctionDef):
                    other[node.name] = ast.dump(node, include_attributes=False)
            return {k for k in names if names[k]!=other[k]}, set(names)^set(other)
        modified,added_removed=changed(old,new)
        self.assertFalse(added_removed)
        self.assertEqual(modified, {"_sort_candidates_with_cached_evidence",
                                    "_preview_catalog_token","_merge_locked_candidate"})

    def test_reproducible_build_no_automatic_install(self):
        dest=pathlib.Path(self.temp.name)/"again.ipk"
        meta=b.build(dest)
        self.assertEqual(self.destination.read_bytes(), dest.read_bytes())
        self.assertTrue(meta["player_unchanged"])
        self.assertFalse(meta["production_published"])
        self.assertFalse(meta["receiver_tested"])

if __name__=="__main__":
    unittest.main()
