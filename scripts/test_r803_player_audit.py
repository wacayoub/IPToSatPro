#!/usr/bin/env python3
"""Offline regression checks for the R80.3 read-only playback audit."""
import unittest
from audit_r803_player_readonly import analyze

SAMPLE = """2026-10-17 15:39:46 | SAT_START | channel='beIN SPORTS 3' provider='beIN SPORTS'
2026-10-17 15:39:46 | MANUAL_EXACT_PIN | sat='beIN SPORTS 3'
2026-10-17 15:39:46 | AUDIO_SAFE_PLAYER | direct=5002 reason=TOD_EVENT
2026-10-17 15:39:48 | IPTV_FAIL | mode=5002 reason=No decoded IPTV video after 1.9 s
2026-10-17 15:39:49 | RESTORE_SAT | all IPTV candidates exhausted
2026-10-17 15:45:22 | SAT_START | channel='beIN SPORTS 3'
2026-10-17 15:45:24 | IPTV_OK | mode=dvb actual=PENDING latency=242ms evidence=validated-ts-data
"""

class PlayerAuditTests(unittest.TestCase):
    def test_identifies_failed_5002_before_sat_restore(self):
        sessions = analyze(SAMPLE.splitlines())["sessions"]
        self.assertIn("5002_FAILED_NO_OTHER_MODE_BEFORE_SAT_RESTORE",
                      sessions[0]["notes"])

    def test_ts_data_only_is_not_decoded_video_proof(self):
        sessions = analyze(SAMPLE.splitlines())["sessions"]
        self.assertIn("IPTV_OK_TS_ONLY_VIDEO_NOT_PROVEN", sessions[1]["notes"])

    def test_not_audibility_proof(self):
        sessions = analyze(SAMPLE.splitlines())["sessions"]
        self.assertIn("AUDIBLE_AUDIO_NOT_PROVEN_BY_LOG", sessions[1]["notes"])

    def test_detects_cross_session_mode_disagreement(self):
        findings = analyze(SAMPLE.splitlines())["findings"]
        self.assertIn("CROSS_SESSION_5002_FAIL_DVB_OK:beIN SPORTS 3", findings)

    def test_do_not_export_iptv_url(self):
        private_line = "2026-10-17 15:39:47 | AUDIO_SAFE_PLAYER | direct=5002 url=https://example.net/credentials/password-token"
        report = analyze((SAMPLE + private_line).splitlines())
        self.assertNotIn("example.net", str(report))

    def test_ignore_non_session_failures(self):
        self.assertEqual(analyze(["2026-10-17 15:00:00 | IPTV_FAIL | mode=5002"])["sessions"], [])

if __name__ == "__main__":
    unittest.main()
