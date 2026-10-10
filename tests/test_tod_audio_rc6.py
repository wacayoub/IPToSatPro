"""Pure, offline regression tests for targeted TOD playback plan and audio safety."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "r70"))
import tod_audio_recovery_rc6 as rc6


class FakeMonitor:
    serviceapp_5002_available = True

    def __init__(self, name, *, plan=None, mode="auto", override="auto", retry=True):
        self.pending_match = {"name": name, "url": "http://example.invalid/stream"}
        self.last_match = None
        self.base_plan = plan
        self.cfg = SimpleNamespace(service_type=SimpleNamespace(value=mode),
                                   retry_failed_stream=SimpleNamespace(value=retry))
        self.override = override
        self.events = []
        self.stream_health = {}

    @staticmethod
    def _audio_sensitive_stream(ch):
        return "tod" in ch.get("name", "").lower() and "sports" in ch.get("name", "").lower()

    def _playback_plan(self):
        if self.base_plan is not None:
            return list(self.base_plan)
        if self._audio_sensitive_stream(self.pending_match):
            return ["5002"]
        return ["dvb", "5002"]

    def _current_player_override(self):
        return self.override

    def _log(self, event, value):
        self.events.append((event, value))


class TODAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rc6.attach_tod_audio(FakeMonitor)

    def test_tod_sports_second_4097(self):
        m = FakeMonitor("TOD EVENT SPORTS 7 FHD (EXCLUS)")
        self.assertEqual(m._playback_plan(), ["5002", "4097"])

    def test_tod_4k_without_word_sports_routes_serviceapp(self):
        m = FakeMonitor("TOD EVENT 1 4K HDR (LIVE EVENT ONLY)")
        self.assertEqual(m._playback_plan(), ["5002", "4097"])
        self.assertTrue(m._audio_safe_serviceapp_required(m.pending_match)
                        if hasattr(m, "_audio_safe_serviceapp_required") else
                        m._audio_sensitive_stream(m.pending_match))

    def test_existing_successful_non_tod_4k_is_unchanged(self):
        m = FakeMonitor("PL Museum TV 4K UHD HDR", plan=["5002","dvb"])
        self.assertEqual(m._playback_plan(), ["5002","dvb"])

    def test_no_tod_false_positive(self):
        for name in ("PL: MEZZO LIVE HD", "beIN SPORTS 1", "Star Action EVENT"):
            m = FakeMonitor(name, plan=["dvb", "5002"])
            self.assertEqual(m._playback_plan(), ["dvb", "5002"])
            self.assertFalse(rc6.tod_event(m.pending_match))

    def test_explicit_manual_dvb_wins_even_for_tod(self):
        m=FakeMonitor("TOD EVENT 1 4K HDR", plan=["dvb"], override="dvb")
        self.assertEqual(m._playback_plan(), ["dvb"])

    def test_explicit_player_5002_setting_wins(self):
        m=FakeMonitor("TOD EVENT SPORTS 14 FHD",plan=["5002"],mode="5002")
        self.assertEqual(m._playback_plan(), ["5002"])

    def test_audio_recovery_disabled_wins(self):
        m=FakeMonitor("TOD EVENT SPORTS 13 FHD", retry=False)
        self.assertEqual(m._playback_plan(), ["5002"])

    def test_4097_first_has_5002_second(self):
        m=FakeMonitor("TOD EVENT SPORTS 7 FHD", plan=["4097"])
        self.assertEqual(m._playback_plan(), ["4097","5002"])

    def test_5001_first_can_fallback_to_4097(self):
        m=FakeMonitor("TOD EVENT 1 4K",plan=["5001"])
        self.assertEqual(m._playback_plan(), ["5001","4097"])

    def test_no_double_attach(self):
        before=FakeMonitor._playback_plan
        rc6.attach_tod_audio(FakeMonitor)
        self.assertIs(before, FakeMonitor._playback_plan)

    def test_no_audio_track_switch_from_policy(self):
        self.assertNotIn("setCurrentTrack", Path(rc6.__file__).read_text())

    def test_failed_preference_without_history_does_not_guess(self):
        self.assertEqual(FakeMonitor("TOD EVENT SPORTS 7")._playback_plan(), ["5002","4097"])

if __name__ == "__main__":
    unittest.main()
