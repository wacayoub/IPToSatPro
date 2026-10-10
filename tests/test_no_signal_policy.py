import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "r70"))
from no_signal_policy import decide_fta_fallback, should_bypass_instant_manual_lock


def decide(**overrides):
    inputs = dict(
        enabled=True,
        clear_no_signal_opt_in=True,
        sat_fallback_enabled=True,
        is_dvb=True,
        current_service_unchanged=True,
        satellite_access=False,
        tuner_state="FAILED",
        verified_decoder_video=False,
        video_pts_present=False,
        video_resolution_present=False,
        time_since_sat_start_s=1.6,
        explicit_tune_failure=False,
    )
    inputs.update(overrides)
    return decide_fta_fallback(**inputs)


class NoSignalTests(unittest.TestCase):
    def test_unavailable_by_default(self):
        self.assertEqual(decide(clear_no_signal_opt_in=False)[0], False)
        self.assertEqual(decide(enabled=False)[0], False)

    def test_explicit_fta_signal_failure_qualifies(self):
        self.assertEqual(decide(), (True, "FTA_NO_SIGNAL_CONFIRMED"))
        self.assertTrue(decide(tuner_state="LOST_LOCK")[0])
        self.assertTrue(decide(tuner_state="TUNE_FAILED")[0])

    def test_confirmed_fta_healthy_must_stay_sat(self):
        self.assertEqual(decide(tuner_state="LOCKED")[1], "SAT_LOCKED")
        self.assertFalse(decide(tuner_state="LOCKED", explicit_tune_failure=True)[0])

    def test_tuning_not_yet_no_signal(self):
        for status in ("ACQUIRING", "TUNING", "SEARCHING", "LOCKING"):
            self.assertFalse(decide(tuner_state=status)[0])
        self.assertEqual(decide(time_since_sat_start_s=0.2)[1], "TUNER_GRACE_PERIOD")

    def test_video_evidence_prevents_unnecessary_switch(self):
        self.assertEqual(decide(video_pts_present=True)[1], "SAT_VIDEO_PRESENT")
        self.assertFalse(decide(video_resolution_present=True)[0])
        self.assertFalse(decide(verified_decoder_video=True)[0])

    def test_unknown_access_is_not_automatically_classified_fta(self):
        self.assertFalse(decide(satellite_access=None)[0])
        self.assertFalse(decide(satellite_access=True)[0])

    def test_no_or_invalid_frontend_needs_native_failure_event(self):
        self.assertFalse(decide(tuner_state="?", explicit_tune_failure=False)[0])
        self.assertFalse(decide(tuner_state="UNKNOWN", explicit_tune_failure=True,
                                time_since_sat_start_s=0.8)[0])
        self.assertTrue(decide(tuner_state="UNKNOWN", explicit_tune_failure=True,
                               time_since_sat_start_s=1.3)[0])

    def test_stale_service_identity_and_wrong_source_never_pass(self):
        self.assertFalse(decide(current_service_unchanged=False)[0])
        self.assertFalse(decide(is_dvb=False)[0])
        self.assertFalse(decide(sat_fallback_enabled=False)[0])

    def test_manual_lock_fast_path_remains_for_encrypted(self):
        self.assertFalse(should_bypass_instant_manual_lock(
            feature_enabled=True, confirmed_fta=False))
        self.assertTrue(should_bypass_instant_manual_lock(
            feature_enabled=True, confirmed_fta=True))
        self.assertFalse(should_bypass_instant_manual_lock(
            feature_enabled=False, confirmed_fta=True))

    def test_no_bad_timers(self):
        self.assertFalse(decide(time_since_sat_start_s=-1)[0])
        self.assertFalse(decide(time_since_sat_start_s=9999)[0])


if __name__ == "__main__":
    unittest.main()
