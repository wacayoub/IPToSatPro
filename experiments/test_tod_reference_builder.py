"""Tests only synthetic bitmaps: calibrated genuine beIN logos still missing."""
import json
import os
import tempfile
import unittest

from tod_reference_builder import (
    encode_bmp, reference_crop, create_reference, load_verified_templates,
)
from video_logo_probe import VideoLogoMatcher, load_bmp


def screenshot(corner):
    rows = [[(22, 29, 39) for _ in range(100)] for _ in range(60)]
    if corner == "right":
        start_x = 80
    elif corner == "left":
        start_x = 10
    else:
        return encode_bmp(rows)
    for y in range(5, 17):
        for x in range(start_x, start_x + 5):
            rows[y][x] = (250, 250, 250)
    return encode_bmp(rows)


class ReferenceCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.right = (.75, 0, .25, .3333333)
        self.left = (.05, 0, .25, .3333333)

    def test_verified_logo_crop_and_load_two_corners(self):
        with tempfile.TemporaryDirectory() as outdir:
            screenshot_path = os.path.join(outdir, "on-air.bmp")
            for corner, roi in (("right", self.right), ("left", self.left)):
                with open(screenshot_path, "wb") as stream:
                    stream.write(screenshot(corner))
                ref, manifest = create_reference(
                    screenshot_path, 6, corner, roi, outdir, verified=True)
                self.assertTrue(os.path.isfile(ref))
                self.assertTrue(os.path.isfile(manifest))
                self.assertEqual(load_bmp(open(ref, "rb").read())[0], 25)
            templates = load_verified_templates(manifest)
            matcher = VideoLogoMatcher(templates)
            right_match = matcher.classify(screenshot("right"))
            left_match = matcher.classify(screenshot("left"))
            self.assertEqual(right_match["number"], 6)
            self.assertEqual(right_match["corner"], "right")
            self.assertEqual(left_match["number"], 6)
            self.assertEqual(left_match["corner"], "left")
            self.assertIsNone(matcher.classify(screenshot(None)))

    def test_manual_verification_mandatory(self):
        with tempfile.TemporaryDirectory() as outdir:
            screenshot_path = os.path.join(outdir, "on-air.bmp")
            with open(screenshot_path, "wb") as stream:
                stream.write(screenshot("right"))
            with self.assertRaises(ValueError):
                create_reference(screenshot_path, 6, "right", self.right, outdir)
            self.assertFalse(os.path.isfile(
                os.path.join(outdir, "manifest.json")))

    def test_wrong_corner_and_non_logo_fail(self):
        with self.assertRaises(ValueError):
            reference_crop(screenshot("right"), self.right, "left", 6)
        with self.assertRaises(ValueError):
            reference_crop(screenshot(None), self.right, "right", 6)
        with self.assertRaises(ValueError):
            reference_crop(screenshot("right"), self.right, "right", 11)
        with self.assertRaises(ValueError):
            reference_crop(screenshot("right"), (.2, .6, .2, .2), "left", 6)

    def test_reject_unverified_and_parent_reference(self):
        with tempfile.TemporaryDirectory() as outdir:
            manifest = os.path.join(outdir, "manifest.json")
            for entry in (
                dict(logo=6, roi=list(self.right),
                     corner="right", file="../escape.bmp", human_verified=True),
                dict(logo=6, roi=list(self.right),
                     corner="right", file="ref.bmp", human_verified=False)
            ):
                with open(manifest, "w", encoding="utf-8") as stream:
                    json.dump({"schema": 1, "references": [entry]}, stream)
                with self.assertRaises(ValueError):
                    load_verified_templates(manifest)


if __name__ == "__main__":
    unittest.main()
