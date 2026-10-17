"""Offline tests: receiver TOD diagnostic NEVER accesses a real tuner."""
import json
import os
import stat
import struct
import tempfile
import types
import unittest
import zipfile
from unittest import mock

from receiver_tod_capture import (bmp_decode, bmp_encode, collect,
                                  checked_tmp_parent, crop_raw_bmp, bmp_metadata,
                                  CORNER_ROIS)


def fake_bmp(seed):
    rows = [[(12, 15, 20) for x in range(120)] for y in range(80)]
    for y in range(4, 13):
        for x in range(8 + seed, 14 + seed):
            rows[y][x] = (250, 250, 250)
        for x in range(100 - seed, 106 - seed):
            rows[y][x] = (240, 240, 240)
    return bmp_encode(rows)


class ReadOnlyCaptureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir="/tmp")
        self.grab = os.path.join(self.tmp.name, "fake-grab")
        with open(self.grab, "w") as handle:
            handle.write("fake executable placeholder")
        self.commands = []
        self.delays = []

    def tearDown(self):
        self.tmp.cleanup()

    def test_three_independent_frames_and_both_corners(self):
        def runner(args, **kwargs):
            self.commands.append((args, kwargs))
            i = len(self.commands)
            with open(args[-1], "wb") as out:
                out.write(fake_bmp(i))
            return types.SimpleNamespace(returncode=0)

        folder, report = collect(grab_path=self.grab, parent=self.tmp.name,
                                 run_command=runner,
                                 sleep_fn=self.delays.append)
        self.assertEqual(report["captured"], 3)
        self.assertEqual(report["distinct_images"], 3)
        self.assertFalse(report["source_verified"])
        self.assertEqual(self.delays, [.85, .85])
        self.assertEqual(len(self.commands), 3)
        self.assertEqual(len(report["samples"]), 3)
        for entry in report["samples"]:
            self.assertTrue(entry["unique"])
            self.assertEqual(set(entry["corners"]), {"left", "right"})
            for corner in entry["corners"].values():
                with open(os.path.join(folder, corner), "rb") as handle:
                    w, h, _ = bmp_decode(handle.read())
                self.assertEqual((w, h), (38, 19))
        for args, kwargs in self.commands:
            self.assertEqual(args[1:4], ["-v", "-r", "480"])
            self.assertFalse(kwargs["check"])
            self.assertEqual(kwargs["timeout"], 3)
        with open(os.path.join(folder, "report.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["distinct_images"], 3)
        with zipfile.ZipFile(os.path.join(folder, "tod-images.zip")) as package:
            names = set(package.namelist())
            self.assertIn("report.json", names)
            self.assertIn("frame-01.bmp", names)
            self.assertIn("frame-03-right.bmp", names)
            self.assertEqual(len(names), 10)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(folder, "tod-images.zip")).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(folder).st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(folder, "report.json")).st_mode), 0o600)

    def test_cropped_raw_bmp_equals_legacy_pixel_crop(self):
        from receiver_tod_capture import extract_corner
        raw = fake_bmp(2)
        frame = bmp_decode(raw)
        for roi in CORNER_ROIS.values():
            self.assertEqual(crop_raw_bmp(raw, roi), extract_corner(frame, roi))

    def test_memory_bounded_crop_accepts_32bit_and_top_down_bmp(self):
        original = fake_bmp(2)
        w, h, rows = bmp_decode(original)
        row_stride = w * 4
        pixels = bytearray()
        # Windows BMP top-down encoding; uses BGRA 32-bit source.
        for row in rows:
            for red, green, blue in row:
                pixels.extend((blue, green, red, 127))
        bmp32 = (b"BM" + struct.pack("<IHHI", 54 + len(pixels), 0, 0, 54) +
                 struct.pack("<IiiHHIIiiII", 40, w, -h, 1, 32, 0,
                             len(pixels), 0, 0, 0, 0) + pixels)
        self.assertEqual(bmp_metadata(bmp32)[:2], (w, h))
        from receiver_tod_capture import extract_corner
        for roi in CORNER_ROIS.values():
            self.assertEqual(crop_raw_bmp(bmp32, roi),
                             extract_corner((w, h, rows), roi))

    def test_optional_960_requests_only_current_picture(self):
        def make_960(seed):
            width, height = 960, 540
            row = b"\x10\x20\x30" * width
            pixels = bytearray(row * height)
            pixels[seed] = 100 + seed
            return (b"BM" +
                    struct.pack("<IHHI", 54 + len(pixels), 0, 0, 54) +
                    struct.pack("<IiiHHIIiiII", 40, width, height,
                                1, 24, 0, len(pixels), 0, 0, 0, 0) +
                    pixels)

        def runner(args, **kwargs):
            self.commands.append((args, kwargs))
            with open(args[-1], "wb") as out:
                out.write(make_960(len(self.commands)))
            return types.SimpleNamespace(returncode=0)

        folder, report = collect(grab_path=self.grab, parent=self.tmp.name,
                                 width=960, run_command=runner,
                                 sleep_fn=lambda _: None)
        self.assertEqual(report["requested_width"], 960)
        self.assertEqual(report["captured"], 3)
        self.assertEqual(report["distinct_images"], 3)
        self.assertEqual([item["width"] for item in report["samples"]],
                         [960, 960, 960])
        self.assertTrue(all(call[0][1:4] == ["-v", "-r", "960"]
                            for call in self.commands))
        for roi in CORNER_ROIS.values():
            _ = roi
        with open(os.path.join(folder, "frame-01-right.bmp"), "rb") as f:
            w, h, *_ = bmp_metadata(f.read())
        self.assertEqual((w, h), (307, 130))

    def test_identical_frames_are_not_three_independent_samples(self):
        def runner(args, **kwargs):
            with open(args[-1], "wb") as handle:
                handle.write(fake_bmp(1))
            return types.SimpleNamespace(returncode=0)
        _, report = collect(grab_path=self.grab, parent=self.tmp.name,
                            run_command=runner, sleep_fn=lambda _: None)
        self.assertEqual(report["captured"], 3)
        self.assertEqual(report["distinct_images"], 1)
        self.assertIn("warning", report)

    def test_bad_image_is_failure_not_black_screen(self):
        def runner(args, **kwargs):
            with open(args[-1], "wb") as handle:
                handle.write(b"\x89PNG\r\n\0bad-image")
            return types.SimpleNamespace(returncode=0)
        folder, report = collect(grab_path=self.grab, parent=self.tmp.name,
                                 run_command=runner, sleep_fn=lambda _: None)
        self.assertEqual(report["captured"], 0)
        self.assertEqual(report["distinct_images"], 0)
        self.assertTrue(all("NOT screen black" in s["status"] for s in report["samples"]))
        self.assertEqual(sorted(os.listdir(folder)), ["report.json", "tod-images.zip"])

    def test_openatv_tmp_symlink_target_is_allowed(self):
        """On OpenATV /tmp commonly resolves to /var/volatile/tmp."""
        root = os.path.join(self.tmp.name, "volatile-tmp")
        os.mkdir(root)
        sub = os.path.join(root, "captures")
        os.mkdir(sub)
        original_realpath = os.path.realpath

        def emulate_openatv_realpath(path):
            if path == "/tmp":
                return root
            if path == "/tmp/captures":
                return sub
            return original_realpath(path)

        with mock.patch("receiver_tod_capture.os.path.realpath",
                        side_effect=emulate_openatv_realpath):
            self.assertEqual(checked_tmp_parent("/tmp"), root)
            self.assertEqual(checked_tmp_parent("/tmp/captures"), sub)
            with self.assertRaises(ValueError):
                checked_tmp_parent("/etc")

    def test_path_resolution_rejects_symlink_escape(self):
        escape = tempfile.TemporaryDirectory(dir="/var/tmp")
        self.addCleanup(escape.cleanup)
        link = os.path.join(self.tmp.name, "escape-link")
        os.symlink(escape.name, link)
        with self.assertRaises(ValueError):
            checked_tmp_parent(link)

    def test_rejects_unsafe_location_and_missing_grab(self):
        with self.assertRaises(ValueError):
            collect(grab_path=self.grab, parent="/etc")
        with self.assertRaises(RuntimeError):
            collect(grab_path="/usr/bin/definitely-no-grab", parent=self.tmp.name)
        with self.assertRaises(ValueError):
            collect(grab_path=self.grab, parent=self.tmp.name, count=14)
        with self.assertRaises(ValueError):
            collect(grab_path=self.grab, parent=self.tmp.name, spacing=.1)
        with self.assertRaises(ValueError):
            collect(grab_path=self.grab, parent=self.tmp.name, width=1920)
        with self.assertRaises(ValueError):
            collect(grab_path=self.grab, parent=self.tmp.name, width=True)

    def test_error_does_not_touch_receiver_settings_or_network(self):
        def failing(args, **kwargs):
            self.commands.append(args)
            return types.SimpleNamespace(returncode=1)
        folder, report = collect(grab_path=self.grab, parent=self.tmp.name,
                                 run_command=failing, sleep_fn=lambda _: None)
        self.assertEqual(len(self.commands), 3)
        self.assertEqual(report["captured"], 0)
        self.assertEqual(sorted(os.listdir(folder)), ["report.json", "tod-images.zip"])
        for call in self.commands:
            self.assertEqual(call[0], self.grab)
            self.assertNotIn("wget", " ".join(call))


if __name__ == "__main__":
    unittest.main()
