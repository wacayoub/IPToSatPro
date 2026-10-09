#!/usr/bin/env python3
"""Offline regression and safety checks for the UNPUBLISHED r70 candidate."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "r70"))
from r70_safety_core import (
    PlaybackGuard, CandidateHistory, ManualLockGuard, RecoveryPolicy,
    validate_update, FEATURES
)
from r70_monitor_adapter import attach_monitor


class Clock:
    def __init__(self):
        self.value = 100
    def __call__(self):
        return self.value
    def advance(self, seconds):
        self.value += seconds


class GuardTests(unittest.TestCase):
    def test_provisional_is_not_decoded(self):
        now = Clock()
        g = PlaybackGuard(now)
        seq = g.begin("stream1", "sat1")
        self.assertTrue(g.connected(seq))
        self.assertFalse(g.snapshot()["video_decoded"])
        self.assertFalse(g.mark_stable(seq))
        now.advance(3)
        self.assertTrue(g.no_frame_due(seq))
        self.assertFalse(g.snapshot()["stable"])

    def test_decoded_verified_and_stale_event_rejected(self):
        now = Clock()
        g = PlaybackGuard(now)
        old = g.begin("old", "SAT")
        new = g.begin("new", "SAT")
        self.assertFalse(g.decoded_frame(old, 3840, 2160))
        self.assertTrue(g.decoded_frame(new, 1920, 1080))
        self.assertEqual(g.snapshot()["dimensions"], [1920, 1080])
        self.assertFalse(g.mark_stable(new))
        now.advance(1.1)
        self.assertTrue(g.mark_stable(new))

    def test_video_without_audio_evidence_allowed(self):
        g = PlaybackGuard()
        seq = g.begin("a", "b")
        g.decoded_frame(seq, 1280, 720)
        self.assertEqual(g.snapshot()["audio"], "UNKNOWN")
        g.set_audio_observation(seq, True)
        self.assertEqual(g.snapshot()["audio"], "TRACK_PRESENT")

    def test_history_bounded_and_sanitized(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "health.json")
            clock = Clock()
            h = CandidateHistory(p, clock)
            secret = "https://iptv.example/stream?username=alice&password=DO_NOT_LOG"
            h.record(secret, True, mode="dvb", elapsed_ms=120, source_id="my-provider")
            h.record(secret, False, mode="5002")
            self.assertEqual(h.health(secret)["mode"], "dvb")
            h.flush()
            raw = Path(p).read_text()
            self.assertNotIn("DO_NOT_LOG", raw)
            self.assertNotIn("username", raw)
            self.assertNotIn("my-provider", raw)
            self.assertEqual(CandidateHistory(p, clock).health(secret)["mode"], "dvb")

    def test_persistent_lock_and_legacy_backup(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "locks.json")
            lock = ManualLockGuard(path)
            lock.keep("BBC Earth", "AR BBC EARTH FHD")
            self.assertTrue(ManualLockGuard(path).matches("BBC Earth", "AR BBC EARTH FHD"))
            original = os.path.join(td, "overrides.json")
            backup = os.path.join(td, "backup", "overrides.json")
            Path(original).write_text('{"a":"b"}')
            self.assertTrue(lock.snapshot_legacy(original, backup))
            self.assertEqual(Path(original).read_bytes(), Path(backup).read_bytes())

    def test_recovery_budget_and_audio_guard(self):
        now = Clock()
        p = RecoveryPolicy(now)
        self.assertTrue(p.allow("ch", 1))
        self.assertFalse(p.allow("ch", 1))
        now.advance(12)
        self.assertTrue(p.allow("ch", 1))
        now.advance(12)
        self.assertFalse(p.allow("ch", 1))
        self.assertFalse(p.audio_recovery_needed(2, -1, known_silence=False))
        self.assertTrue(p.audio_recovery_needed(2, -1, known_silence=True))

    def test_update_preflight_without_install(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "candidate.ipk")
            data = b"!<arch>\n" + bytes(10240)
            Path(path).write_bytes(data)
            manifest = {"version": "1.0.46-r70-rc1", "size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest()}
            self.assertEqual(validate_update(path, manifest)["size"], len(data))
            manifest["sha256"] = "0" * 64
            with self.assertRaises(ValueError):
                validate_update(path, manifest)

    def test_all_eight_features_in_kernel(self):
        self.assertEqual(len(FEATURES), 8)

    def test_monitor_hook_preserves_original_player_return(self):
        class FakeMonitor:
            def __init__(self):
                self.current_play_mode = "dvb"
                self.sat_ref_string = "SAT-REF"
                self.pending_match = {"id": "A"}
            def _play_match(self, candidate):
                return ("PLAYED", candidate)
            def _post_success_quality_update(self, candidate, width, height, hdr=""):
                return width > 0 and height > 0
            def _handle_iptv_failure(self, reason="unknown"):
                return "RECOVER"
        cls = attach_monitor(FakeMonitor)
        self.assertIs(cls, attach_monitor(FakeMonitor))
        a = cls()
        item = {"id": "A", "source_id": "provider"}
        self.assertEqual(a._play_match(item), ("PLAYED", item))
        self.assertTrue(a._post_success_quality_update(item, 1920, 1080))
        self.assertTrue(a._r70_playback.snapshot()["video_decoded"])
        self.assertEqual(a._handle_iptv_failure("EOF"), "RECOVER")


if __name__ == "__main__":
    unittest.main()
