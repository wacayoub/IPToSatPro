"""Offline regression for Enigma2 event bridge. No receiver required."""
import unittest
from enigma2_tod_event_bridge import Enigma2TodEventBridge
from tod_dynamic_runtime import DynamicTodController


class E:
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
        self.zaps = 0

    def getCurrentlyPlayingServiceReference(self):
        return self.ref

    def playService(self, *args, **kwargs):
        self.zaps += 1
        raise AssertionError("bridge must not zap")


class EventBridgeTests(unittest.TestCase):
    def setUp(self):
        self.nav = Nav()
        self.now = [0.0]
        self.ctx = {
            "source_id": "king-exact-007", "tod_channel": "TOD Sports 3",
            "stream_id": "url-A", "event_id": "event-A",
            "allow_auto_skip": True, "backup_available": False,
            "timeshift": False, "manual_lock": False,
        }
        self.decisions = []
        self.ctrl = DynamicTodController("king-exact-007")
        self.bridge = Enigma2TodEventBridge(
            self.nav, self.ctrl, lambda: self.ctx,
            on_proposal=self.decisions.append, events=E,
            clock=lambda: self.now[0])
        self.bridge.attach()

    def tearDown(self):
        self.bridge.detach()

    def fire(self, event):
        for callback in list(self.nav.event):
            callback(event)

    def logo(self, number=6, at=1, generation=None, ref=None):
        return self.bridge.classified_video_logo(
            number=number, confidence=0.97,
            capture_ref=ref or self.nav.ref.toString(),
            capture_generation=(self.bridge.generation if generation is None else generation),
            observed_at=at)

    def test_tod_logo_event_switch_and_no_mapping_file_write(self):
        self.fire(E.evStart)
        for i in (1, 2, 3):
            self.logo(6, at=i)
        self.assertEqual(self.ctrl.resolve_bein(
            source_id="king-exact-007", bein_channel=6, now=4)[0].tod, 3)
        self.ctx["event_id"] = "event-B"
        self.fire(E.evUpdatedEventInfo)
        self.assertFalse(self.ctrl.resolve_bein(
            source_id="king-exact-007", bein_channel=6, now=5))
        for i in (6, 7, 8):
            self.logo(8, at=i)
        self.assertEqual(self.ctrl.resolve_bein(
            source_id="king-exact-007", bein_channel=8, now=9)[0].tod, 3)
        self.assertEqual(self.nav.zaps, 0)

    def test_stale_capture_and_changed_reference_rejected(self):
        self.fire(E.evStart)
        old_generation = self.bridge.generation
        self.nav.ref = Ref("4097:OTHER")
        self.assertIsNone(self.logo(at=2, generation=old_generation, ref="4097:KING:TOD3"))
        self.assertFalse(self.ctrl.resolve_bein(
            source_id="king-exact-007", bein_channel=6, now=3))
        self.nav.ref = Ref("4097:KING:TOD3")
        self.fire(E.evEnd)
        self.fire(E.evStart)
        self.assertIsNone(self.logo(at=4, generation=old_generation))
        self.assertEqual(self.nav.zaps, 0)

    def test_eof_is_advisory_with_backup_first(self):
        self.ctx["backup_available"] = True
        self.fire(E.evStart)
        self.now[0] = 2.0
        self.fire(E.evEOF)
        self.assertEqual([d.action for d in self.decisions], ["try_backup"])
        self.fire(E.evEOF)
        self.assertEqual(len(self.decisions), 1)
        self.assertEqual(self.nav.zaps, 0)

    def test_timeshift_manual_lock_and_wrong_source_never_skip(self):
        self.ctx["manual_lock"] = True
        self.fire(E.evStart)
        self.now[0] = 5
        self.fire(E.evEOF)
        self.assertEqual(self.decisions, [])
        self.ctx["manual_lock"] = False
        self.ctx["timeshift"] = True
        self.fire(E.evEOF)
        self.assertEqual(self.decisions, [])
        self.ctx["timeshift"] = False
        self.ctx["source_id"] = "not-king"
        self.fire(E.evEOF)
        self.assertEqual(self.decisions, [])
        self.assertEqual(self.nav.zaps, 0)

    def test_eof_without_opt_in_does_not_advance(self):
        self.ctx["allow_auto_skip"] = False
        self.fire(E.evStart)
        self.now[0] = 2
        self.fire(E.evEOF)
        self.assertEqual(self.decisions, [])
        self.assertEqual(self.nav.zaps, 0)

    def test_attach_idempotent_and_detach(self):
        self.bridge.attach()
        self.assertEqual(len(self.nav.event), 1)
        self.bridge.detach()
        self.assertEqual(len(self.nav.event), 0)


if __name__ == "__main__":
    unittest.main()
