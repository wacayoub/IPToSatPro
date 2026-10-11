"""Offline r70-rc4 Preview Auto-Test safety and navigation regressions.

Mocked Enigma2 timers; no IPTV network access, playback or SAT service mutation.
"""
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "r70"))
from preview_autotest_rc4 import attach_preview


class FakeTimer:
    def __init__(self):
        self.callback = []
        self.armed = False
    def start(self, delay, single):
        self.armed = True
    def stop(self):
        self.armed = False
    def fire(self):
        if self.armed:
            self.armed = False
            for cb in list(self.callback):
                cb()


class Label:
    def __init__(self):
        self.value = ""
    def setText(self, v):
        self.value = v


class SourceList:
    def __init__(self):
        self.index = -1
    def moveToIndex(self, i):
        self.index = i


class FakePreview:
    def __init__(self, channels):
        self.channels = channels
        self.focus = "left"
        self.sat_ref_string = "SAT_TREK"
        self.ref_on_cursor = "SAT_TREK"
        self._closed_for_async = False
        self.selected_index = 0
        self.finished = False
        self.current_result = "UNKNOWN"
        self.active_fp = ""
        self._preview_audio = {}
        self.ui = {"status": Label(), "detail": Label(), "source_list": SourceList()}
        self.played = []
        self.saved = 0

    def __getitem__(self, name):
        return self.ui[name]
    def _selected_sat_row(self):
        return {"ref": self.ref_on_cursor}
    def _sat_key(self):
        return self.sat_ref_string
    def _set_focus(self, focus):
        self.focus = focus
    def _candidate_decision(self, c):
        return c.get("decision", "REVIEW")
    def _blue_action(self):
        self.played.append("original-blue")
    def _preview_selected(self):
        c = self.channels[self.selected_index]
        self.played.append(c["id"])
        self.active_fp = c["id"]
        self.current_result = "OPENING"
        self.finished = False
    def _record_preview_failure(self, reason):
        self.finished = True
        self.current_result = "FAILED"
    def _start_quality_analysis(self):
        return "analysis-started"
    def _poll(self):
        return "poll"
    def _sat_selection_changed(self):
        self.sat_ref_string = self.ref_on_cursor
    def _cleanup(self):
        self._closed_for_async = True
    def _move_up(self):
        return "up"
    def _move_down(self):
        return "down"


Candidate = lambda i, state="REVIEW", reject=None: {
    "id": i, "url": "local-test://" + i, "decision": state,
    "_preview_details": {"reject_reason": reject} if reject else {},
}


class AutoTestCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        attach_preview(FakePreview, {"eTimer": FakeTimer,
                                    "channel_fingerprint": lambda row: row.get("id", "")})

    def test_sat_blue_starts_async_not_blocking_player(self):
        f = FakePreview([Candidate("TREK_MAIN"), Candidate("TREK_BACKUP")])
        f._blue_action()
        self.assertEqual(f.played, [])
        self.assertTrue(f._r70_autotest_running)
        f._r70_autotest_timer.fire()
        self.assertEqual(f.played, ["TREK_MAIN"])
        self.assertEqual(f.focus, "right")
        self.assertEqual(f.ui["source_list"].index, 0)
        self.assertEqual(f.saved, 0)

    def test_failure_tries_next_and_verified_picture_requires_green(self):
        f = FakePreview([Candidate("TREK_MAIN"), Candidate("TREK_BACKUP")])
        f._r70_autotest_start()
        f._r70_autotest_timer.fire()
        f._record_preview_failure("bad player")
        f._r70_autotest_timer.fire()
        self.assertEqual(f.played, ["TREK_MAIN", "TREK_BACKUP"])
        f.current_result = "PLAYING"
        f._preview_audio[(f._sat_key(), f.active_fp)] = {"state": "NO_TARGET"}
        self.assertEqual(f._start_quality_analysis(), "analysis-started")
        self.assertFalse(f._r70_autotest_running)
        self.assertIn("GREEN", f["status"].value)
        self.assertEqual(f.saved, 0)

    def test_hard_reject_and_user_reject_are_never_tried(self):
        f = FakePreview([
            Candidate("wrong", "REJECT", "not same service"),
            Candidate("user-reject", "USER REJECT"),
            Candidate("trek", "REVIEW"),
        ])
        f._r70_autotest_start()
        f._r70_autotest_timer.fire()
        self.assertEqual(f.played, ["trek"])

    def test_unmeasured_source_candidate_is_eligible_only_after_blue(self):
        f = FakePreview([Candidate("TREK_SOURCE", "SOURCE")])
        self.assertEqual(f.played, [])
        f._r70_autotest_start()
        f._r70_autotest_timer.fire()
        self.assertEqual(f.played, ["TREK_SOURCE"])
        self.assertEqual(f.saved, 0)

    def test_trial_limit_six_and_no_mass_scan(self):
        f = FakePreview([Candidate(str(i)) for i in range(100)])
        f._r70_autotest_start()
        self.assertEqual(f._r70_autotest_total, 6)
        for i in range(6):
            f._r70_autotest_timer.fire()
            f._record_preview_failure("timeout")
        f._r70_autotest_timer.fire()
        self.assertFalse(f._r70_autotest_running)
        self.assertEqual(len(f.played), 6)
        self.assertIn("no candidate", f["status"].value)

    def test_unmeasured_player_requires_human_verification(self):
        f = FakePreview([Candidate("TREK")])
        f._r70_autotest_start()
        f._r70_autotest_timer.fire()
        f.finished = True
        f.current_result = "VERIFY"
        f._poll()
        self.assertFalse(f._r70_autotest_running)
        self.assertIn("verify video/audio", f["status"].value)
        self.assertEqual(f.saved, 0)

    def test_sat_cursor_or_manual_navigation_cancels(self):
        f = FakePreview([Candidate("TREK"), Candidate("TREK2")])
        f._r70_autotest_start()
        f.ref_on_cursor = "SAT_OTHER"
        f._sat_selection_changed()
        f._r70_autotest_timer.fire()
        self.assertFalse(f._r70_autotest_running)
        self.assertEqual(f.played, [])
        f.ref_on_cursor = "SAT_OTHER"
        f._r70_autotest_start()
        f._move_up()
        self.assertFalse(f._r70_autotest_running)

    def test_blue_on_right_preserves_manual_preview(self):
        f = FakePreview([Candidate("TREK")])
        f.focus = "right"
        f._blue_action()
        self.assertEqual(f.played, ["original-blue"])

    def test_cleanup_disables_pending_timer(self):
        f = FakePreview([Candidate("TREK")])
        f._r70_autotest_start()
        f._cleanup()
        f._r70_autotest_timer.fire()
        self.assertEqual(f.played, [])

    def test_explicit_key3_entry_not_auto_play_on_navigation(self):
        f = FakePreview([Candidate("TREK")])
        self.assertEqual(f.played, [])
        f._r70_autotest_start()
        self.assertEqual(f.played, [])
        f._r70_autotest_timer.fire()
        self.assertEqual(f.played, ["TREK"])


if __name__ == "__main__":
    unittest.main()
