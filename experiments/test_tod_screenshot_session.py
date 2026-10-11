"""Offline tests for capture/recognition handoff: no real Vu+ playback evidence."""
import unittest

from enigma2_tod_event_bridge import Enigma2TodEventBridge
from tod_dynamic_runtime import DynamicTodController
from tod_screenshot_session import TodScreenshotSession


class Events:
    evStart = 1
    evEnd = 2
    evUpdatedEventInfo = 3
    evEOF = 4


class Ref:
    def __init__(self, value):
        self.value = value

    def toString(self):
        return self.value


class Nav:
    def __init__(self):
        self.event = []
        self.ref = Ref("4097:KING:TOD3")


class ScreenshotSessionTests(unittest.TestCase):
    def setUp(self):
        self.nav = Nav()
        self.ctx = {
            "source_id": "provider-king-007", "tod_channel": "TOD Sports 3",
            "stream_id": "stream-A", "event_id": "event-A"
        }
        self.now = [0.]
        self.ctrl = DynamicTodController("provider-king-007")
        self.bridge = Enigma2TodEventBridge(
            self.nav, self.ctrl, lambda: self.ctx,
            events=Events, clock=lambda: self.now[0])
        self.bridge.attach()
        self.bridge._event(Events.evStart)
        self.session = TodScreenshotSession(self.bridge, clock=lambda: self.now[0])

    def tearDown(self):
        self.bridge.detach()

    def evidence(self, number, n, at, token=None):
        self.now[0] = at
        token = self.bridge.screenshot_token() if token is None else token
        data = {"number": number, "confidence": .98,
                "capture_digest": "%064x" % n}
        return self.session.accept(data, token, at)

    def test_three_independent_captures_assign_tod(self):
        self.assertIsNone(self.evidence(6, 1, 1.0))
        self.assertIsNone(self.evidence(6, 2, 1.5))
        route = self.evidence(6, 3, 2.0)
        self.assertEqual(route.bein, 6)
        self.assertEqual(route.tod, 3)

    def test_repeated_or_too_fast_capture_does_not_count(self):
        self.evidence(6, 1, 1.0)
        self.assertIsNone(self.evidence(6, 1, 1.6))  # duplicate frame
        self.assertIsNone(self.evidence(6, 2, 1.7))
        self.assertIsNone(self.evidence(6, 3, 1.75))  # less than .45 s
        self.assertFalse(self.ctrl.resolve_bein(
            source_id="provider-king-007", bein_channel=6, now=2))
        self.assertIsNone(self.evidence(6, 4, 2.3))
        self.assertEqual(self.evidence(6, 5, 2.9).bein, 6)

    def test_old_event_capture_rejected_even_if_number_is_correct(self):
        old_token = self.bridge.screenshot_token()
        self.evidence(6, 1, 1.)
        self.evidence(6, 2, 1.6)
        self.evidence(6, 3, 2.2)
        self.assertTrue(self.ctrl.resolve_bein(
            source_id="provider-king-007", bein_channel=6, now=3))
        self.ctx["event_id"] = "event-B"
        self.assertIsNone(self.evidence(6, 4, 3.))
        self.assertIsNone(self.evidence(6, 5, 3.5, old_token))
        self.assertFalse(self.ctrl.resolve_bein(
            source_id="provider-king-007", bein_channel=6, now=4))
        self.assertIsNone(self.evidence(8, 6, 4.))
        self.assertIsNone(self.evidence(8, 7, 4.6))
        self.assertEqual(self.evidence(8, 8, 5.2).bein, 8)

    def test_new_service_generation_rejects_late_screenshot(self):
        old_token = self.bridge.screenshot_token()
        self.bridge._event(Events.evEnd)
        self.nav.ref = Ref("4097:KING:TOD4")
        self.ctx["tod_channel"] = "TOD Sports 4"
        self.bridge._event(Events.evStart)
        self.assertIsNone(self.evidence(6, 1, 1., old_token))
        self.assertIsNone(self.evidence(6, 2, 1.5))
        self.assertIsNone(self.evidence(6, 3, 2.))
        self.assertEqual(self.evidence(6, 4, 2.6).tod, 4)

    def test_invalid_evidence_or_late_delivery_fails_closed(self):
        token = self.bridge.screenshot_token()
        self.now[0] = 8.
        self.assertIsNone(self.session.accept(
            {"number": 6, "confidence": .98, "capture_digest": "a" * 64},
            token, 1.))
        self.assertIsNone(self.session.accept(
            {"number": 6, "confidence": .98, "capture_digest": "wrong"},
            token, 8.))
        self.assertIsNone(self.session.accept(
            {"number": 6, "confidence": .60, "capture_digest": "a" * 64},
            token, 8.))
        self.ctx["source_id"] = "other"
        self.assertIsNone(self.evidence(6, 9, 9.))


if __name__ == "__main__":
    unittest.main()
