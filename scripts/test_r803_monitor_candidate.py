#!/usr/bin/env python3
"""Offline static regression for UNMAP RC2 -> R80.3 playback-only patch.

No Enigma2 imports, decoder control, stream URLs or receiver configuration.
"""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "staging/r803/monitor_rc2_baseline.py"
CANDIDATE = ROOT / "staging/r803/monitor_rc2_candidate.py"
ALLOWED = {
    "_r803_native_rescue_eligible", "_playback_plan", "_play_match",
    "_verify_iptv", "_audio_guard_tick",
}

def members(tree):
    result = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            result.setdefault(node.name, []).append(ast.dump(node, include_attributes=False))
    return result

class MonitorR803CandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_text = BASE.read_text(encoding="utf-8")
        cls.new_text = CANDIDATE.read_text(encoding="utf-8")
        cls.old_tree = ast.parse(cls.old_text, filename=str(BASE))
        cls.new_tree = ast.parse(cls.new_text, filename=str(CANDIDATE))
        cls.old_funcs = members(cls.old_tree)
        cls.new_funcs = members(cls.new_tree)
        cls.new_source_methods = {node.name: ast.get_source_segment(cls.new_text, node)
                                  for node in ast.walk(cls.new_tree)
                                  if isinstance(node, ast.FunctionDef)}

    def test_syntax_compiles(self):
        compile(self.new_text, str(CANDIDATE), "exec")

    def test_no_removed_functions_or_unrelated_function_changes(self):
        for name, before in self.old_funcs.items():
            with self.subTest(function=name):
                self.assertIn(name, self.new_funcs)
                if name not in ALLOWED:
                    self.assertEqual(before, self.new_funcs[name],
                                     "Unrelated RC2 function altered: " + name)
        self.assertEqual(set(self.new_funcs) - set(self.old_funcs),
                         {"_r803_native_rescue_eligible"})

    def test_exact_unmap_pinning_is_preserved(self):
        for fn in ("_direct_candidate_plan", "_activate_candidate",
                   "_r80_user_unmapped_guard"):
            self.assertIn(fn, self.old_funcs)
            self.assertEqual(self.old_funcs[fn], self.new_funcs[fn])

    def test_audio_protection_and_compatibility_guard(self):
        self.assertIn("AUDIO_SAFE_RESCUE_PLAN", self.new_text)
        self.assertIn("native_audio_missing", self.new_text)
        self.assertIn("openatv_playback", self.new_text)
        self.assertIn('return [mode, "dvb"]', self.new_text)
        self.assertIn('return [mode]', self.new_text)
        self.assertIn('kind == "ts"', self.new_text)

    def test_explicit_player_locks_unchanged(self):
        self.assertIn('if lock == "dvb":\n            return ["dvb"]', self.new_text)
        self.assertIn('if lock == "serviceapp":\n            return [self._safe_serviceapp_mode()]',
                      self.new_text)

    def test_ts_only_not_final_video_success(self):
        new_verify = self.new_source_methods["_verify_iptv"]
        self.assertNotIn("validated-ts-data", new_verify)
        self.assertIn("IPTV_TS_PENDING", new_verify)
        self.assertIn("FIRST_VIDEO", new_verify)
        self.assertIn("self.verify_deadline", new_verify)
        self.assertIn("self.current_candidate_started_at", new_verify)

    def test_no_repeat_audio_retry_after_two_players(self):
        guard = self.new_source_methods["_audio_guard_tick"]
        self.assertIn("AUDIO_GUARD_EXHAUSTED", guard)
        self.assertIn("self.fallback_attempt", guard)
        self.assertIn("_schedule_next_candidate", guard)

    def test_no_stream_content_leaked_in_test_asset(self):
        for text in (self.old_text, self.new_text):
            self.assertNotIn("myIPTV.example", text)
            self.assertNotIn("userbouquet.", text)

if __name__ == "__main__":
    unittest.main()
