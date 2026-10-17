"""Synthetic pixel tests only: cannot validate actual broadcaster logos."""
import struct
import unittest

from video_logo_probe import (
    VideoLogoMatcher, crop_rows, grab_video_bmp, load_bmp, white_mask,
    top_corner_rois,
)


def bmp(rows):
    h, w = len(rows), len(rows[0])
    stride = (w * 3 + 3) & ~3
    payload = bytearray()
    for row in reversed(rows):
        for r, g, b in row:
            payload += bytes((b, g, r))
        payload += b"\0" * (stride - w * 3)
    return (b"BM" + struct.pack("<IHHI", 54 + len(payload), 0, 0, 54) +
            struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0,
                        len(payload), 0, 0, 0, 0) + bytes(payload))


def scene(logo=None):
    rows = [[(24, 40, 60) for x in range(48)] for y in range(32)]
    if logo == 6:
        for y in range(4, 14):
            for x in range(27, 31):
                rows[y][x] = (251, 251, 251)
    elif logo == 8:
        for y in range(4, 14):
            for x in range(39, 43):
                rows[y][x] = (251, 251, 251)
    elif logo == "unknown":
        for y in range(4, 14):
            for x in range(33, 37):
                rows[y][x] = (251, 251, 251)
    return rows


def roi_bmp(rows):
    return bmp([row[24:48] for row in rows[:16]])


class LogoProbeTests(unittest.TestCase):
    def setUp(self):
        self.roi = (.5, 0., .5, .5)
        self.templates = {
            6: {"roi": self.roi, "bmp": roi_bmp(scene(6))},
            8: {"roi": self.roi, "bmp": roi_bmp(scene(8))},
        }

    def test_synthetic_shape_detected_without_name_or_epg(self):
        verifier = VideoLogoMatcher(self.templates)
        result = verifier.classify(bmp(scene(6)))
        self.assertEqual(result["number"], 6)
        self.assertEqual(result["confidence"], 1)
        self.assertEqual(len(result["capture_digest"]), 64)
        self.assertEqual(verifier.classify(bmp(scene(8)))["number"], 8)

    def test_unknown_or_conflicting_logo_fails_closed(self):
        verifier = VideoLogoMatcher(self.templates)
        self.assertIsNone(verifier.classify(bmp(scene("unknown"))))
        self.assertIsNone(verifier.classify(bmp(scene(None))))
        same = {6: self.templates[6], 8: self.templates[6]}
        self.assertIsNone(VideoLogoMatcher(same).classify(bmp(scene(6))))

    def test_bad_image_input_and_reference_rejected(self):
        for raw in (b"", b"garbage", bmp(scene(6))[:60]):
            with self.assertRaises(ValueError):
                load_bmp(raw)
        with self.assertRaises(ValueError):
            VideoLogoMatcher({11: self.templates[6]})
        self.assertIsNone(VideoLogoMatcher({}).classify(bmp(scene(6))))
        self.assertEqual(len(white_mask(crop_rows(load_bmp(bmp(scene(6))), self.roi))), 384)

    def test_missing_grab_returns_no_evidence(self):
        self.assertIsNone(grab_video_bmp("/usr/bin/definitely-no-grab-exists"))


    def test_recognize_same_logo_in_left_or_right_corner(self):
        """A broadcaster can place the SAME watermark on either side."""
        rois = {"left": (0.0, 0.0, .5, .5),
                "right": (.5, 0.0, .5, .5)}
        templates = {
            n: {"rois": rois, "bmp": self.templates[n]["bmp"]}
            for n in (6, 8)
        }
        matcher = VideoLogoMatcher(templates)

        def at_left(number):
            rows = scene(None)
            original = scene(number)
            for y in range(16):
                rows[y][:24] = original[y][24:48]
            return bmp(rows)

        self.assertEqual(matcher.classify(bmp(scene(6)))["number"], 6)
        self.assertEqual(matcher.classify(bmp(scene(6)))["corner"], "right")
        self.assertEqual(matcher.classify(at_left(6))["number"], 6)
        self.assertEqual(matcher.classify(at_left(6))["corner"], "left")
        self.assertEqual(matcher.classify(at_left(8))["number"], 8)
        self.assertEqual(matcher.classify(at_left(8))["corner"], "left")
        self.assertNotEqual(matcher.classify(at_left(6))["capture_digest"],
                            matcher.classify(bmp(scene(6)))["capture_digest"])

        # Two equally strong DIFFERENT logos: never guess the winner.
        both = scene(6)
        left_eight = scene(8)
        for y in range(16):
            both[y][:24] = left_eight[y][24:48]
        self.assertIsNone(matcher.classify(bmp(both)))
        self.assertIsNone(matcher.classify(bmp(scene("unknown"))))

    def test_top_corner_rois_are_bounded_and_require_verified_templates(self):
        rois = top_corner_rois()
        self.assertEqual(set(rois), {"left", "right"})
        self.assertLess(rois["left"][0] + rois["left"][2], .5)
        self.assertGreater(rois["right"][0], .5)
        self.assertLess(rois["left"][1] + rois["left"][3], .35)
        for kwargs in ({"width": .6}, {"height": .7}, {"top_margin": .3}):
            with self.assertRaises(ValueError):
                top_corner_rois(**kwargs)
        with self.assertRaises(ValueError):
            VideoLogoMatcher({6: {"rois": rois}})
        with self.assertRaises(ValueError):
            VideoLogoMatcher({6: {"rois": {}, "bmp": self.templates[6]["bmp"]}})


if __name__ == "__main__":
    unittest.main()
