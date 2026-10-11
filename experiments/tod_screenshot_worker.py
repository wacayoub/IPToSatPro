"""Opt-in, bounded screenshot worker for experimental King TOD recognition.

No hook is installed by importing this file. Owner calls tick() periodically ON
Enigma2's GUI thread (e.g. via a manually attached eTimer). The only work in
the worker thread is video-only screenshot capture and image classification.
It never accesses Enigma2 nav, changes channels, edits locks, or scans other
TOD services. Results are polled and validated on the GUI thread.

This is not a release component until genuine King broadcaster watermark
templates, an exact King source ID and receiver hardware are verified.
"""
import queue
import threading
import time

from tod_screenshot_session import TodScreenshotSession
from video_logo_probe import grab_video_bmp


class TodScreenshotWorker:
    """One in-flight screenshot max; bounded per-event attempts; opt-in only."""
    def __init__(self, bridge, matcher, capture=None, session=None,
                 enabled=False, startup_delay=2.0, interval=.65,
                 max_attempts=8, clock=None, thread_factory=None):
        if not (0 <= startup_delay <= 30 and .45 <= interval <= 30
                and isinstance(max_attempts, int) and 3 <= max_attempts <= 20):
            raise ValueError("unsafe screenshot scheduling settings")
        if not hasattr(matcher, "classify"):
            raise TypeError("logo matcher with classify() required")
        self.bridge = bridge
        self.matcher = matcher
        self.capture = capture or grab_video_bmp
        self.clock = clock or time.monotonic
        self.session = session or TodScreenshotSession(bridge, clock=self.clock)
        self.enabled = bool(enabled)
        self.startup_delay = float(startup_delay)
        self.interval = float(interval)
        self.max_attempts = max_attempts
        self.thread_factory = thread_factory or threading.Thread
        self._pending = queue.Queue(maxsize=1)
        self._busy = False
        self._closed = False
        self._token = None
        self._attempts = 0
        self._next_at = 0.0
        self.stats = dict(attempts=0, captures=0, recognized=0,
                          failures=0, stale=0, accepted=0)

    def close(self):
        """Stop new requests WITHOUT blocking GUI for any ongoing worker."""
        self.enabled = False
        self._closed = True
        self._token = None
        self.session.reset()

    def _capture_once(self, token):
        # This entire method executes OFF the GUI thread.
        classified, captured_at = None, None
        try:
            bmp = self.capture()
            if bmp:
                classified = self.matcher.classify(bmp)
            captured_at = self.clock()
        except Exception:
            # A broken/unsupported screenshot MUST NOT cause any channel skip.
            captured_at = self.clock()
        try:
            self._pending.put_nowait((token, captured_at, classified, bool(classified)))
        except queue.Full:
            # Never block, and never overwrite a newer unprocessed result.
            pass

    def poll(self):
        """Call ON GUI thread; consume evidence without any navigation."""
        try:
            token, captured_at, classified, recognized = self._pending.get_nowait()
        except queue.Empty:
            return None
        self._busy = False
        if self._closed or not self.enabled:
            return None
        current = self.bridge.screenshot_token()
        ctx = self.bridge._current()
        if (current != token or current is None or ctx is None or
                any(ctx.get(k) for k in (
                    "manual_lock", "timeshift", "recording", "parental_blocked"))):
            self.stats["stale"] += 1
            return None
        self.stats["captures"] += 1
        if not recognized:
            self.stats["failures"] += 1
            return None
        self.stats["recognized"] += 1
        assignment = self.session.accept(
            classified, token, captured_at, now=self.clock())
        if assignment is not None:
            self.stats["accepted"] += 1
        return assignment

    def tick(self):
        """Call periodically ON GUI thread. Never performs capture inline."""
        if self._closed or not self.enabled:
            return None
        assignment = self.poll()
        token = self.bridge.screenshot_token()
        if token is None:
            self._token = None
            self.session.reset()
            return assignment
        ctx = self.bridge._current()  # GUI-thread only, verified King/TOD context
        if ctx is None or any(ctx.get(k) for k in (
                "manual_lock", "timeshift", "recording", "parental_blocked")):
            return assignment
        now = self.clock()
        if token != self._token:
            self._token = token
            self._attempts = 0
            self._next_at = now + self.startup_delay
            self.session.reset()
        if self._busy or self._attempts >= self.max_attempts or now < self._next_at:
            return assignment
        # Stop if this TOD slot has already been verified for the current event.
        if self.bridge.controller.routes.by_tod(
                "King", ctx["tod_channel"], now=now) is not None:
            return assignment
        # A single beIN watermark (e.g. only 7) is NOT sufficient: most of
        # the channel badge is visually shared between beIN 1-10 and a
        # partial catalog can falsely map 1/6/8 as 7. Keep runtime OFF until
        # all TEN independently confirmed numbered logos are calibrated.
        # Diagnostic tools may still classify individual screenshots offline.
        refs = getattr(self.matcher, "references", None)
        if not isinstance(refs, dict) or not set(range(1, 11)).issubset(refs):
            return assignment
        self._attempts += 1
        self.stats["attempts"] += 1
        self._next_at = now + self.interval
        self._busy = True
        try:
            thread = self.thread_factory(target=self._capture_once, args=(token,))
            thread.daemon = True
            thread.start()
        except Exception:
            self._busy = False
            self.stats["failures"] += 1
        return assignment


class TodScreenshotTimerAdapter:
    """Optional Enigma2 eTimer polling; never auto-starts on import.

    The caller owns its lifespan, source context and receiver integration.
    Avoid invasive nav hooks or scanning 14 feeds from a single tuner.
    """
    def __init__(self, worker, timer, interval_ms=200):
        if not 100 <= interval_ms <= 2000:
            raise ValueError("unsafe GUI polling interval")
        self.worker = worker
        self.timer = timer
        self.interval_ms = interval_ms
        self.running = False
        self._subscription = None
        self._callback_list = None
        signal = getattr(timer, "timeout", None)
        if signal is not None and hasattr(signal, "connect"):
            self._subscription = signal.connect(self._tick)
        elif hasattr(timer, "callback") and hasattr(timer.callback, "append"):
            timer.callback.append(self._tick)
            self._callback_list = timer.callback
        else:
            raise TypeError("eTimer timeout.connect or callback.append required")

    def start(self):
        if not self.running:
            self.running = True
            self.timer.start(self.interval_ms, False)

    def _tick(self):
        if not self.running:
            return
        try:
            self.worker.tick()
        except Exception:
            # Never allow experimental screenshots to crash the Enigma2 event loop.
            self.worker.stats["failures"] += 1

    def stop(self):
        self.running = False
        self.timer.stop()

    def close(self):
        self.stop()
        self.worker.close()
        if self._callback_list is not None:
            try:
                self._callback_list.remove(self._tick)
            except ValueError:
                pass
        # Enigma2's signal connection drops with this adapter's lifetime.
        self._subscription = None
