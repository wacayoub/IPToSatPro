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
        # Confirm BOTH the post-rank presentation path and the 144-row deep expansion budget.
        self.assertIn('return self._compact_candidate_duplicates(rows)\n', self.source)
        self.assertNotIn('return self._compact_candidate_duplicates(rows, limit=self.MAX_BROWSER_CANDIDATES)', self.source)
        self.assertIn('candidate_budget = 144 if self._r71_worker_deep else self.MAX_BROWSER_CANDIDATES', self.source)
        self.assertIn('[:(144 if self._r71_worker_deep else self.MAX_BROWSER_CANDIDATES)]', self.source)

    def test_configuration_change_invalidates_preview_cache(self):
        self.assertIn('str(cfg.languages.value)', self.source)
        self.assertIn('str(cfg.match_threshold.value)', self.source)
        self.assertIn('str(cfg.quality_mode.value)', self.source)
        self.assertIn('ui_policy)', self.source)

    def test_manual_lock_no_fabricated_150_score(self):
        self.assertIn('float((manual or {}).get("auto_scan_score") or 0.0)', self.source)
        self.assertNotIn('float((manual or {}).get("auto_scan_score") or 150.0)', self.source)

    def test_player_monitor_core_untouched(self):
        self.assertEqual(set(self.contents), set(self.previous)|{b.CHANGELOG, b.P+"preview_theme_r73.py"})
        for name,blob in self.previous.items():
            if name not in (b.PLUGIN,b.UPDATER,b.CORE):
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
        self.assertEqual(added_removed, {"_r73_page_focused"})
        self.assertEqual(modified, {
            "_sort_candidates_with_cached_evidence", "_preview_catalog_token",
            "_merge_locked_candidate", "_poll_expanded_candidates", "_blue_action",
            "_page_sat_next", "_page_sat_previous", "_expand_selected_sat_candidates",
            "_all_sources"
        })
        core_before = ast.parse(self.previous[b.CORE])
        core_after = ast.parse(self.contents[b.CORE])
        core_modified, core_extra = changed(core_before, core_after)
        self.assertFalse(core_extra)
        self.assertEqual(core_modified, {"_fast_cache_key","fast_rank_matches_all_servers"})

    def test_native_theme_geometry_and_widget_bindings(self):
        import xml.etree.ElementTree as ET
        namespace = {}
        exec(self.contents[b.P+"preview_theme_r73.py"].decode(), namespace)
        skin = ET.fromstring(namespace["PREVIEW_R73_FHD"])
        self.assertEqual(skin.attrib["size"], "1700,790")
        widgets = [x for x in skin if x.tag == "widget"]
        names = [x.get("name") for x in widgets]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(set(names), {
            "title","focus_hint","sat_picon","picon_fallback","sat_current",
            "context_info","epg","status","subtitles","left_head","right_head",
            "sat_list","source_list","verify","detail","key_red","key_green",
            "key_yellow","key_blue","key_menu"
        })
        for element in skin:
            if element.tag not in ("widget","eLabel"):
                continue
            x,y = map(int, element.get("position").split(","))
            w,h = map(int, element.get("size").split(","))
            self.assertGreaterEqual(x,0)
            self.assertGreaterEqual(y,0)
            self.assertLessEqual(x+w,1700)
            self.assertLessEqual(y+h,790)
        self.assertIn('from .preview_theme_r73 import PREVIEW_R73_FHD',self.source)
        self.assertIn('self.skin = _theme_skin(PREVIEW_R73_FHD)',self.source)

    def test_remote_controls_in_preview_do_not_autozap(self):
        self.assertIn('"blue": self._blue_action',self.source)
        self.assertIn('def _r73_page_focused(self, step):',self.source)
        self.assertIn('self._r73_page_focused(+1)',self.source)
        self.assertIn('self._r73_page_focused(-1)',self.source)
        blue=self.source.split("    def _blue_action(self):",1)[1].split("    def _preferred_modes",1)[0]
        self.assertNotIn('self._preview_selected()',blue)
        self.assertNotIn('playService(',blue)
        self.assertIn('type=MessageBox.TYPE_INFO',blue)
        self.assertIn('self._preview_selected()',self.source)

    def test_deep_search_budget_and_threshold_is_preview_only(self):
        core=self.contents[b.CORE].decode()
        self.assertIn('nomination_cap = max(60, min(400 if limit > 72 else 132',core)
        self.assertIn('nomination_per_server = max(10, min(54 if limit > 72 else 24',core)
        self.assertIn('float((context or {}).get("match_threshold") or 82.0)',core)
        self.assertIn('ctx["match_threshold"] = float(cfg.match_threshold.value)',self.source)
        self.assertIn('candidate_per_server = 42 if self._r71_worker_deep',self.source)
        self.assertTrue(self.info["player_unchanged"])

    def test_reproducible_build_no_automatic_install(self):
        dest=pathlib.Path(self.temp.name)/"again.ipk"
        meta=b.build(dest)
        self.assertEqual(self.destination.read_bytes(), dest.read_bytes())
        self.assertTrue(meta["player_unchanged"])
        self.assertFalse(meta["production_published"])
        self.assertFalse(meta["receiver_tested"])

if __name__=="__main__":
    unittest.main()
