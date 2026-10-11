"""Synthetic tests for opt-in screenshot worker; NOT receiver hardware tests."""
import threading
import time
import unittest

from enigma2_tod_event_bridge import Enigma2TodEventBridge
from tod_dynamic_runtime import DynamicTodController
from tod_screenshot_worker import TodScreenshotWorker, TodScreenshotTimerAdapter


class Events:
    evStart, evEnd, evUpdatedEventInfo, evEOF = 1, 2, 3, 4


class Ref:
    def __init__(self, value):
        self.value = value

    def toString(self):
        return self.value


class Nav:
    def __init__(self):
        self.event = []
        self.ref = Ref("4097:KING:TOD3")

    def getCurrentlyPlayingServiceReference(self):
        return self.ref

    def playService(self, *args):
        raise AssertionError("TOD screenshot worker MUST NEVER zap")


class InlineThread:
    """Run synchronously in tests only; production uses a real daemon thread."""
    def __init__(self, target, args):
        self.target, self.args = target, args
        self.daemon = False

    def start(self):
        self.target(*self.args)


class Matcher:
    def __init__(self):
        self.references = {6: 1, 8: 1}
        self.samples = 0
        self.logo = 6

    def classify(self, bmp):
        self.samples += 1
        return dict(number=self.logo, confidence=.98,
                    capture_digest="%064x" % self.samples, corner="right")


class Timer:
    def __init__(self):
        self.callback = []
        self.starts = []
        self.stopped = False

    def start(self, period, periodic):
        self.starts.append((period, periodic))

    def stop(self):
        self.stopped = True

    def fire(self):
        for callback in tuple(self.callback):
            callback()


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.now = [0.]
        self.ctx = dict(source_id="provider-king-real-ID", tod_channel="TOD Sports 3",
                        stream_id="king-url-A", event_id="event-1",
                        manual_lock=False, timeshift=False, recording=False)
        self.nav = Nav()
        self.ctrl = DynamicTodController("provider-king-real-ID")
        self.bridge = Enigma2TodEventBridge(
            self.nav, self.ctrl, lambda: self.ctx, events=Events,
            clock=lambda: self.now[0])
        self.bridge.attach()
        self.bridge._event(Events.evStart)
        self.matcher = Matcher()
        self.calls = []
        def capture():
            self.calls.append(self.ctx["event_id"])
            return b"decoded-video-BMP-placeholder"
        self.capture = capture

    def tearDown(self):
        self.bridge.detach()

    def make_worker(self, **kwargs):
        return TodScreenshotWorker(
            self.bridge, self.matcher, capture=self.capture,
            clock=lambda: self.now[0], thread_factory=InlineThread,
            startup_delay=0., interval=.65, enabled=True, **kwargs)

    def tick(self, worker, moment):
        self.now[0] = moment
        return worker.tick()

    def test_opt_in_only_and_three_screen_captures(self):
        worker = self.make_worker()
        worker.enabled = False
        self.tick(worker, 1.)
        self.assertEqual(len(self.calls), 0)
        worker.enabled = True
        self.assertIsNone(self.tick(worker, 1.))
        self.assertIsNone(self.tick(worker, 1.8))
        self.assertIsNone(self.tick(worker, 2.6))
        self.assertEqual(len(self.calls), 3)
        assignment = self.tick(worker, 3.4)  # GUI receives third worker result
        self.assertEqual(assignment.tod, 3)
        self.assertEqual(assignment.bein, 6)
        self.assertEqual(worker.stats["accepted"], 1)
        self.assertEqual(len(self.calls), 3)  # no probing after verified match
        self.assertEqual(worker.stats["attempts"], 3)

    def test_no_probes_during_protected_playback(self):
        worker = self.make_worker()
        for flag in ("manual_lock", "timeshift", "recording", "parental_blocked"):
            self.ctx[flag] = True
            self.tick(worker, self.now[0] + 2.)
            self.ctx[flag] = False
        self.assertEqual(self.calls, [])

    def test_missing_templates_skips_probe(self):
        worker = self.make_worker()
        self.matcher.references.clear()
        self.tick(worker, 1.)
        self.tick(worker, 2.)
        self.assertEqual(worker.stats["attempts"], 0)

    def test_event_changed_while_capturing_discards_stale_result(self):
        worker = self.make_worker()
        self.tick(worker, 1.)  # request captured but not consumed
        self.ctx["event_id"] = "event-2"
        self.tick(worker, 2.)  # discard old frame, then first fresh capture
        self.assertEqual(worker.stats["stale"], 1)
        self.assertFalse(self.ctrl.resolve_bein(
            source_id="provider-king-real-ID", bein_channel=6, now=2))
        self.tick(worker, 2.8)
        self.tick(worker, 3.6)
        assignment = self.tick(worker, 4.4)
        self.assertEqual(assignment.bein, 6)
        self.assertEqual(len(self.calls), 4)

    def test_protected_playback_change_drops_pending_result(self):
        worker = self.make_worker()
        self.tick(worker, 1.)
        self.ctx["manual_lock"] = True
        self.tick(worker, 2.)
        self.assertEqual(worker.stats["stale"], 1)
        self.assertEqual(worker.stats["recognized"], 0)

    def test_never_more_than_max_attempts(self):
        class Unknown:
            references = {6: 1}
            def classify(self, data):
                return None
        self.matcher = Unknown()
        worker = self.make_worker(max_attempts=3)
        for i in range(8):
            self.tick(worker, float(i+1))
        self.assertEqual(worker.stats["attempts"], 3)
        self.assertEqual(len(self.calls), 3)

    def test_real_thread_cannot_block_gui_when_capture_stalls(self):
        started, release = threading.Event(), threading.Event()
        def slow_capture():
            started.set()
            release.wait(2.0)
            return b"fake BMP"
        worker = TodScreenshotWorker(
            self.bridge, self.matcher, capture=slow_capture, enabled=True,
            startup_delay=0., interval=.65, clock=time.monotonic)
        t0 = time.monotonic()
        worker.tick()
        self.assertLess(time.monotonic() - t0, .3)
        self.assertTrue(started.wait(1.))
        t1 = time.monotonic()
        worker.tick()  # no second capture while first is in-flight
        self.assertLess(time.monotonic() - t1, .3)
        self.assertEqual(worker.stats["attempts"], 1)
        worker.close()
        release.set()

    def test_timer_adapter_opt_in_start_stop_and_cleanup(self):
        worker = self.make_worker()
        timer = Timer()
        adapter = TodScreenshotTimerAdapter(worker, timer, interval_ms=200)
        self.assertFalse(adapter.running)
        self.assertEqual(timer.starts, [])
        timer.fire()
        self.assertEqual(self.calls, [])
        adapter.start()
        self.assertEqual(timer.starts, [(200, False)])
        self.now[0] = 2.
        timer.fire()
        self.assertEqual(len(self.calls), 1)
        adapter.close()
        self.assertTrue(timer.stopped)
        self.assertEqual(timer.callback, [])
        self.assertTrue(worker._closed)

    def test_foreign_provider_never_probed(self):
        worker = self.make_worker()
        self.ctx["source_id"] = "other-provider"
        self.tick(worker, 1.)
        self.assertEqual(len(self.calls), 0)


if __name__ == "__main__":
    unittest.main()
