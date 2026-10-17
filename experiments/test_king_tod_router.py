"""Offline contract tests: no receiver/network/streams necessary."""
import unittest
from king_tod_router import KingTodRouter, next_non_blacklisted, tod_slot, bein_logo_number


class TestKingTodRouting(unittest.TestCase):
    def setUp(self):
        self.router = KingTodRouter()

    def feed(self, channel, logo, start=0, provider="King", event="A", stream="s"):
        last = None
        for n in range(3):
            last = self.router.observe(provider, channel, logo, .95,
                                       stream_id=stream, event_id=event, now=start + n)
        return last

    def test_user_example_tod3_bein6(self):
        a = self.feed("TOD Sports 3", "beIN Sports 6")
        self.assertEqual((a.tod, a.bein), (3, 6))
        self.assertEqual(self.router.by_bein("KING", 6, now=4)[0].tod, 3)

    def test_event_change_reassigns(self):
        self.feed("TOD3", "beIN 6", start=0)
        self.assertIsNone(self.router.observe("King", "TOD 3", "beIN 8", .95,
                                              stream_id="s", event_id="B", now=12))
        self.assertFalse(self.router.by_bein("King", 6, now=12))
        self.router.observe("King", "TOD3", "beIN 8", .95,
                            stream_id="s", event_id="B", now=13)
        a = self.router.observe("King", "TOD3", "beIN 8", .95,
                                stream_id="s", event_id="B", now=14)
        self.assertEqual(a.bein, 8)
        self.assertFalse(self.router.by_bein("King", 6, now=14))

    def test_never_other_provider(self):
        self.assertIsNone(self.feed("TOD Sports 3", "beIN Sports 6", provider="Other"))
        self.assertFalse(self.router.by_bein("Other", 6, now=3))

    def test_conflict_invalidates_old(self):
        self.feed("TOD3", 6)
        self.assertIsNone(self.router.observe("King", "TOD3", 3, .94,
                                              stream_id="s", event_id="A", now=3))
        self.assertFalse(self.router.by_bein("KING", 6, now=3))

    def test_no_title_only_fallback(self):
        self.assertIsNone(self.router.observe("King", "TOD3 beIN6", "unknown", .99, now=0))
        self.assertIsNone(self.router.by_tod("King", "TOD3", now=1))

    def test_confidence_samples_and_expiry(self):
        self.assertIsNone(self.router.observe("King", "TOD3", 6, .5, now=0))
        self.feed("TOD 3", 6, start=1, stream="")
        self.assertIsNotNone(self.router.by_tod("King", "TOD3", now=4))
        self.assertIsNone(self.router.by_tod("King", "TOD3", now=155))

    def test_duplicate_frames_are_ignored(self):
        for i in range(10):
            self.router.observe("King", "TOD1", 3, .97,
                                now=0.0 + 0.01*i)
        self.assertIsNone(self.router.by_tod("King", "TOD1", now=1))

    def test_slot_and_logo_normalization(self):
        self.assertEqual(tod_slot("TOD EVENT SPORTS 14 HD"), 14)
        self.assertIsNone(tod_slot("TOD 15"))
        self.assertEqual(bein_logo_number("beIN SPORTS 10 HD"), 10)
        self.assertIsNone(bein_logo_number("Sport 10"))

    def test_blacklist_both_directions_and_wrap(self):
        channels = ["101", "102", "103", "104"]
        deny = lambda v: v in ("102", "103")
        self.assertEqual(next_non_blacklisted(channels, 0, 1, deny), (3, "104"))
        self.assertEqual(next_non_blacklisted(channels, 3, -1, deny), (0, "101"))
        self.assertEqual(next_non_blacklisted(channels, 3, 1, deny), (0, "101"))
        self.assertEqual(next_non_blacklisted(channels, 0, 1, lambda c: True), (None, None))
        self.assertEqual(next_non_blacklisted([], 0, 1, deny), (None, None))
        with self.assertRaises(ValueError):
            next_non_blacklisted(channels, 0, 0, deny)

if __name__ == "__main__":
    unittest.main()
