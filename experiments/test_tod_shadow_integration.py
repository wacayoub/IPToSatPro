"""Receiver-independent end-to-end TOD proposal boundary regression tests."""
import dataclasses
import unittest

from tod_dynamic_runtime import DynamicTodController
from tod_shadow_integration import TodShadowIntegration

KING = "king-provider-test-id"


class FakeNav:
    calls = 0

    def playService(self, *_a, **_kw):
        self.calls += 1
        raise AssertionError("shadow integration must never navigate")


class TodShadowIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.controller = DynamicTodController(KING, mapping_ttl=60)
        self.gate = TodShadowIntegration(self.controller)
        self.nav = FakeNav()
        self.ctx = dict(source_id=KING, tod_channel="TOD Sports 3",
                        stream_id="eventURL-one", event_id="match-1",
                        manual_lock=False, timeshift=False, recording=False,
                        parental_blocked=False)

    def consensus(self, channel="TOD Sports 3", digit=7,
                  stream="eventURL-one", event="match-1", confidence=.99):
        for t in (1.0, 1.8, 2.6):
            observed = self.controller.verified_video_logo(
                source_id=KING, tod_channel=channel,
                logo=digit, confidence=confidence,
                stream_id=stream, event_id=event,
                observed_at=t, evidence_origin="decoded_video")
        return observed

    def test_end_to_end_tod3_bein7_verified_label_is_read_only(self):
        assigned = self.consensus()
        self.assertEqual((assigned.tod, assigned.bein), (3, 7))
        verdict = self.gate.propose(self.ctx, 7, now=3)
        self.assertEqual(verdict.decision, "SHADOW_SUGGEST_ONLY")
        self.assertEqual((verdict.tod, verdict.bein), (3, 7))
        self.assertGreater(verdict.confidence, .93)
        self.assertTrue(dataclasses.is_dataclass(verdict))
        with self.assertRaises(dataclasses.FrozenInstanceError):
            verdict.bein = 8
        self.assertEqual(self.nav.calls, 0)

    def test_non_matching_requested_bein_always_rejected(self):
        self.consensus()
        for x in [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, "7", None, True]:
            with self.subTest(x=x):
                d = self.gate.propose(self.ctx, x, 4)
                self.assertEqual(d.decision, "BLOCK")

    def test_thirteen_other_slots_and_recycled_slot_rejected(self):
        self.consensus()
        for n in range(1, 15):
            if n == 3:
                continue
            ctx = dict(self.ctx, tod_channel="TOD Sports %d" % n)
            with self.subTest(slot=n):
                d = self.gate.propose(ctx, 7, 3)
                self.assertEqual(d.decision, "BLOCK")
        self.assertEqual(self.nav.calls, 0)

    def test_live_event_change_drops_old_link_before_new_logo(self):
        self.consensus()
        changed = dict(self.ctx, event_id="match-2")
        self.assertEqual(self.gate.propose(changed, 7, 3).decision, "BLOCK")
        self.controller.stream_or_event_changed(
            source_id=KING, tod_channel="TOD Sports 3")
        self.assertEqual(self.gate.propose(self.ctx, 7, 3).decision, "BLOCK")

    def test_tod3_can_later_show_bein6_not_fixed7(self):
        self.consensus()
        changed = dict(self.ctx, stream_id="eventURL-two", event_id="match-2")
        self.controller.stream_or_event_changed(
            source_id=KING, tod_channel="TOD Sports 3")
        for t in (10, 10.8, 11.6):
            new = self.controller.verified_video_logo(
                source_id=KING, tod_channel="TOD Sports 3",
                logo=6, confidence=.99,
                stream_id="eventURL-two", event_id="match-2",
                observed_at=t, evidence_origin="decoded_video")
        self.assertEqual(new.bein, 6)
        self.assertEqual(self.gate.propose(changed, 6, 12).decision,
                         "SHADOW_SUGGEST_ONLY")
        self.assertEqual(self.gate.propose(changed, 7, 12).decision, "BLOCK")
        self.assertEqual(self.gate.propose(self.ctx, 7, 12).decision, "BLOCK")

    def test_stream_change_rejected_even_when_event_same(self):
        self.consensus()
        self.assertEqual(self.gate.propose(
            dict(self.ctx, stream_id="otherURL"), 7, 4).decision, "BLOCK")

    def test_protected_states_block(self):
        self.consensus()
        for flag in TodShadowIntegration.BLOCK_FLAGS:
            with self.subTest(protection=flag):
                ctx = dict(self.ctx, **{flag: True})
                self.assertEqual(self.gate.propose(ctx, 7, 3).decision, "BLOCK")
        self.assertEqual(self.nav.calls, 0)

    def test_missing_current_event_cannot_cross_mapping_boundary(self):
        self.consensus()
        for field in ("stream_id", "event_id"):
            with self.subTest(field=field):
                ctx = dict(self.ctx, **{field: ""})
                self.assertEqual(self.gate.propose(ctx, 7, 4).decision, "BLOCK")

    def test_wrong_source_and_unverified_source_cannot_map(self):
        self.consensus()
        self.assertEqual(self.gate.propose(
            dict(self.ctx, source_id="other-provider"), 7, 4).decision, "BLOCK")
        self.assertEqual(self.gate.propose(
            dict(self.ctx, unverified_king_source=True), 7, 4).decision, "BLOCK")

    def test_no_three_independent_high_confidence_evidence_no_route(self):
        self.controller.verified_video_logo(
            source_id=KING, tod_channel="TOD Sports 3", logo=7,
            confidence=.98, stream_id="eventURL-one", event_id="match-1",
            observed_at=1, evidence_origin="decoded_video")
        self.assertEqual(self.gate.propose(self.ctx, 7, 1.2).decision, "BLOCK")

    def test_stale_mapping_expires_automatically(self):
        self.consensus()
        self.assertEqual(self.gate.propose(self.ctx, 7, 100).decision, "BLOCK")

    def test_forged_future_evidence_not_accepted(self):
        self.consensus()
        self.assertEqual(self.gate.propose(self.ctx, 7, 1).decision, "BLOCK")

    def test_invalid_context_and_time_fail_closed(self):
        self.consensus()
        for ctx in (None, False, [], "TOD Sports 3"):
            self.assertEqual(self.gate.propose(ctx, 7, 3).decision, "BLOCK")
        for now in (None, "now", -1, True):
            self.assertEqual(self.gate.propose(self.ctx, 7, now).decision,
                             "BLOCK")

    def test_low_confidence_router_assignment_blocked_by_stricter_gate(self):
        self.consensus(confidence=.89)
        self.assertEqual(self.gate.propose(self.ctx, 7, 3).decision, "BLOCK")

    def test_gate_threshold_never_below_93_percent(self):
        for threshold in (.0, .92, 1.01):
            with self.assertRaises(ValueError):
                TodShadowIntegration(self.controller, threshold)

    def test_20_virtual_channels_matrix_never_navigates(self):
        # 14 King TOD slots + six unrelated channel names: invalid candidates
        # do NOT create an accepted route or call Enigma2 navigation.
        self.consensus()
        channels = ["TOD Sports %s" % n for n in range(1, 15)] + [
            "CNN", "beIN Sports 7", "TOD 15", "TOD 0", "Movie HD", "OSN"]
        allowed = 0
        for ch in channels:
            with self.subTest(channel=ch):
                result = self.gate.propose(dict(self.ctx, tod_channel=ch), 7, 3)
                if result.decision == "SHADOW_SUGGEST_ONLY":
                    self.assertEqual(ch, "TOD Sports 3")
                    allowed += 1
                else:
                    self.assertEqual(result.decision, "BLOCK")
        self.assertEqual(len(channels), 20)
        self.assertEqual(allowed, 1)
        self.assertEqual(self.nav.calls, 0)


if __name__ == "__main__":
    unittest.main()
