"""Regression tests for rc5 failed-player recovery; no Enigma2 execution."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "r70"))
from player_recovery_rc5 import attach_recovery


class FakeMonitor:
    def __init__(self, plan, mode="auto", player_override="auto",
                 audio_sensitive=False, retry=True, s5002=True):
        self.base_plan = list(plan)
        self.cfg = SimpleNamespace(
            service_type=SimpleNamespace(value=mode),
            retry_failed_stream=SimpleNamespace(value=retry))
        self.player_override = player_override
        self.audio_sensitive = audio_sensitive
        self.serviceapp_5002_available = s5002
        self.pending_match = {"id": "LaLiga", "url": "hls"}
        self.last_match = None

    def _playback_plan(self):
        return list(self.base_plan)

    def _current_player_override(self):
        return self.player_override

    def _audio_safe_serviceapp_required(self, channel):
        return self.audio_sensitive


class PlayerRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        attach_recovery(FakeMonitor)

    def test_single_5002_gets_4097_after_failure(self):
        self.assertEqual(FakeMonitor(["5002"])._playback_plan(), ["5002", "4097"])

    def test_single_4097_can_try_5002(self):
        self.assertEqual(FakeMonitor(["4097"])._playback_plan(), ["4097", "5002"])

    def test_no_5002_available_for_4097(self):
        self.assertEqual(FakeMonitor(["4097"], s5002=False)._playback_plan(), ["4097"])

    def test_existing_dual_plan_preserved(self):
        self.assertEqual(FakeMonitor(["dvb", "5002"])._playback_plan(), ["dvb", "5002"])
        self.assertEqual(FakeMonitor(["5002", "dvb"])._playback_plan(), ["5002", "dvb"])

    def test_explicit_player_dvb_or_serviceapp_is_authoritative(self):
        self.assertEqual(FakeMonitor(["5002"], player_override="serviceapp")._playback_plan(), ["5002"])
        self.assertEqual(FakeMonitor(["5002"], mode="5002")._playback_plan(), ["5002"])

    def test_audio_sensitive_protects_tod(self):
        self.assertEqual(FakeMonitor(["5002"], audio_sensitive=True)._playback_plan(), ["5002"])

    def test_opted_out_retry_is_respected(self):
        self.assertEqual(FakeMonitor(["5002"], retry=False)._playback_plan(), ["5002"])

    def test_already_verified_native_unchanged(self):
        self.assertEqual(FakeMonitor(["dvb"])._playback_plan(), ["dvb"])

    def test_installed_once_only(self):
        method = FakeMonitor._playback_plan
        self.assertIs(attach_recovery(FakeMonitor)._playback_plan, method)


if __name__ == "__main__":
    unittest.main()
