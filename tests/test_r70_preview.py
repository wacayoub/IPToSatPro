"""Preview Browser r70 regression tests against the published, SHA-pinned r69 code."""
import ast
import base64
import hashlib
import io
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "r70"))
from r70_preview_patch import improve
from r70_preview_async import attach_alternatives

BASE_SHA = "123e1118a7471075ad18dee3014b7367fa9a2cf02f8cdd52ad1e5e65034035ed"


def baseline_plugin():
    raw = base64.b64decode((ROOT / "payload/r69-beta.b64").read_bytes())
    assert hashlib.sha256(raw).hexdigest() == BASE_SHA
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "baseline.ipk"
        p.write_bytes(raw)
        data = subprocess.check_output(["ar", "p", str(p), "data.tar.gz"])
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        return tar.extractfile(
            "./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/plugin.py"
        ).read().decode()


def get_class_method(source, klass, method):
    module = ast.parse(source)
    cls = next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name == klass)
    m = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == method)
    ns = {}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[m], type_ignores=[])),
                 "<isolated-preview-method>", "exec"), ns)
    return ns[method]


class PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = baseline_plugin()
        cls.patched = improve(cls.baseline)

    def test_pinned_preview_patch_compiles(self):
        compile(self.patched, "plugin-preview-r70", "exec")
        self.assertIn("R70_PREVIEW_AUDITED_UPGRADE", self.patched)
        with self.assertRaises(AssertionError):
            improve(self.patched)

    def test_global_full_cache_survives_partial_preview_seed(self):
        self.assertIn("if existing is not None and bool(existing[3]) and not complete", self.patched)
        self.assertIn("shared = _preview_candidate_cache_get(self.input_sat_ref)", self.patched)
        self.assertIn("if matching is not None:", self.patched)

    def test_selected_manual_candidate_survives_missing_top36(self):
        self.assertIn('window.append(dict(incoming[incoming_selected]))', self.patched)
        self.assertIn('channels.append(dict(current_selected))', self.patched)
        self.assertIn('self._source_pos_by_sat[key] = len(window)-1', self.patched)

    def test_video_quality_live_poll_does_not_repaint_all_rows_300ms(self):
        self.assertIn('time.monotonic() - last_paint >= 1.0', self.patched)
        self.assertIn('if final or time.monotonic() - last_paint >= 1.0:', self.patched)

    def test_selection_reorders_by_fingerprint(self):
        self.assertIn('self._render_source_list(keep_index=False)', self.patched)
        self.assertIn('if channel_fingerprint(ch) == old_fp:', self.patched)

    def test_all_sources_default_is_instant_then_async(self):
        self.assertIn('_rank_sat_ref_instant(sat_ref_string, topn=10, per_server=3)', self.patched)
        self.assertIn('_rank_sat_ref_instant(raw, topn=10, per_server=3)', self.patched)
        self.assertNotIn('_rank_sat_ref_all_servers(sat_ref_string, topn=48, per_server=16)', self.patched)

    def test_paging_10000_bouquet_rows_without_loss(self):
        class UI:
            def __init__(self):
                self.browse_mode = True
                self.search_query = ""
                self.ranked = [({"id": str(i)}, 1.0, {}) for i in range(10000)]
                self._r70_page_offset = 0
                self._r70_page_target = None
                self._pending_selected_fp = ""
                self._shown_fps = []
                self.repaint = 0
            def _render(self):
                self.repaint += 1
            def _index(self):
                return 2
        for name, fn in (
            ("_r70_next_page", get_class_method(self.patched, "SatIPTVBridgeAlternatives", "_r70_next_page")),
            ("_r70_prev_page", get_class_method(self.patched, "SatIPTVBridgeAlternatives", "_r70_prev_page")),
            ("_selected_row", get_class_method(self.patched, "SatIPTVBridgeAlternatives", "_selected_row")),
        ):
            setattr(UI, name, fn)
        ui = UI()
        self.assertEqual(ui._selected_row()[0]["id"], "2")
        ui._r70_next_page()
        self.assertEqual(ui._r70_page_offset, 48)
        self.assertEqual(ui._selected_row()[0]["id"], "50")
        ui._r70_prev_page()
        self.assertEqual(ui._r70_page_offset, 0)
        self.assertEqual(ui._selected_row()[0]["id"], "2")
        self.assertEqual(len(ui.ranked), 10000)
        self.assertEqual(ui.repaint, 2)

    def test_rank_async_stale_and_modal_close_no_player_calls(self):
        class Timer:
            def __init__(self):
                self.callback = []
                self.calls = 0
            def start(self, milliseconds, singleshot):
                self.calls += 1
            def stop(self):
                pass
        class Catalog:
            channels = [{"id": "source"}]
            def fast_rank_matches_all_servers(self, name, languages, context, per_server, topn, quality_mode):
                return [({"id": name}, 99.0, {})]
        class Fake:
            search_query = ""
            browse_mode = False
            server_filter = "ALL"
            group_filter = "ALL"
            sat_ref_string = "sat"
            sat_name = "sat-name"
            context = {}
            MAX_VISIBLE_CANDIDATES = 48
            def __init__(self):
                self.state = {"detail": type("Label", (), {"setText": lambda _, t: None})()}
                self.rows = []
            def __getitem__(self, k):
                return self.state[k]
            def _catalog(self):
                return Catalog()
            def _load_all_servers(self):
                raise AssertionError("blocking old method should not execute")
            def _stop_zap_timer(self):
                return None
            def _render(self):
                self.rows = self.ranked
        from types import SimpleNamespace
        cfg = SimpleNamespace(
            languages=SimpleNamespace(value="AR,EN"),
            quality_mode=SimpleNamespace(value="best"))
        attach_alternatives(Fake, {"eTimer": Timer, "cfg": cfg})
        ui = Fake()
        ui._load_all_servers()
        self.assertEqual(ui.rows, [])
        ui._r70_rank_worker.join(timeout=5)
        self.assertFalse(ui._r70_rank_worker.is_alive())
        cb = ui._r70_rank_poll_timer.callback[0]
        cb()
        self.assertEqual(ui.rows[0][0]["id"], "sat-name")
        ui._stop_zap_timer()


if __name__ == "__main__":
    unittest.main()
