"""Guard screenshots before passing logo evidence to the experimental TOD router.

This is a policy/GUI handoff only. There is NO screenshot worker scheduler,
navigation action, installation hook or background channel scan here.

Usage (receiver integration to be implemented after hardware validation):
  * On GUI thread: token = bridge.screenshot_token()
  * Off GUI thread: bmp = grab_video_bmp(); result = matcher.classify(bmp)
  * On GUI thread: session.accept(result, token, captured_at, now=monotonic())
Capture only the CURRENT King TOD feed, never all 14 simultaneously.
A screenshot is not a video recording. grab -v omits Enigma OSD overlays.
"""
import re
import time

_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class TodScreenshotSession:
    """Pass 3+ independent, spaced, context-valid logo screenshots downstream.

    KingTodRouter still requires >=3 consistent high-confidence detections;
    this adapter guarantees they do not come from an identical stale image.
    """
    def __init__(self, bridge, min_spacing=.45, max_age=3.0,
                 seen_window=20.0, clock=None):
        if not (0.35 <= min_spacing <= 3.0 and
                0.5 <= max_age <= 10.0 and seen_window >= 3 * min_spacing):
            raise ValueError("invalid screenshot verification timing")
        self.bridge = bridge
        self.min_spacing = min_spacing
        self.max_age = max_age
        self.seen_window = seen_window
        self.clock = clock or time.monotonic
        self._token = None
        self._last_at = None
        self._digests = {}

    def reset(self):
        self._token = None
        self._last_at = None
        self._digests.clear()

    def accept(self, classification, capture_token, captured_at, now=None):
        """Consume a *worker-classified* screenshot on Enigma2 GUI thread.

        capture_token was read BEFORE invoking a worker capture and contains
        exact service ref, nav generation, King provider, TOD slot, stream ID
        and event ID. A late screenshot from an earlier event is discarded.
        This method never captures, schedules or zaps.
        """
        if capture_token is None or not isinstance(classification, dict):
            return None
        current = self.bridge.screenshot_token()
        if current is None or current != capture_token:
            return None
        try:
            capture_time = float(captured_at)
            received_at = float(self.clock() if now is None else now)
        except (ValueError, TypeError):
            return None
        if not (capture_time <= received_at + .05 and
                0 <= received_at - capture_time <= self.max_age):
            return None
        digest = classification.get("capture_digest", "")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
            return None
        number = classification.get("number")
        confidence = classification.get("confidence")
        if type(number) is not int or not 1 <= number <= 10:
            return None
        if not isinstance(confidence, (int, float)) or not .93 <= confidence <= 1:
            return None
        if capture_token != self._token:
            self.reset()
            self._token = capture_token
        # Duplicate captures, even nonconsecutive, must NOT count as samples.
        self._digests = {
            key: at for key, at in self._digests.items()
            if capture_time >= at and capture_time - at <= self.seen_window
        }
        if digest in self._digests:
            return None
        if self._last_at is not None and capture_time - self._last_at < self.min_spacing:
            return None
        self._digests[digest] = capture_time
        self._last_at = capture_time
        return self.bridge.classified_video_logo(
            number=number, confidence=float(confidence),
            capture_ref=capture_token[0],
            capture_generation=capture_token[1],
            observed_at=capture_time)
