"""Offline tests: receiver TOD diagnostic NEVER accesses a real tuner."""
import json
import os
import stat
import tempfile
import types
import unittest

from receiver_tod_capture import bmp_decode, bmp_encode, collect


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
                self.assertEqual((w, h), (38, 20))
        for args, kwargs in self.commands:
            self.assertEqual(args[1:4], ["-v", "-r", "480"])
            self.assertFalse(kwargs["check"])
            self.assertEqual(kwargs["timeout"], 3)
        with open(os.path.join(folder, "report.json"), encoding="utf-8") as handle:
            self.assertEqual(json.load(handle)["distinct_images"], 3)
        self.assertEqual(stat.S_IMODE(os.stat(folder).st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.join(folder, "report.json")).st_mode), 0o600)

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
        self.assertEqual(sorted(os.listdir(folder)), ["report.json"])

    def test_rejects_unsafe_location_and_missing_grab(self):
        with self.assertRaises(ValueError):
            collect(grab_path=self.grab, parent="/etc")
        with self.assertRaises(RuntimeError):
            collect(grab_path="/usr/bin/definitely-no-grab", parent=self.tmp.name)
        with self.assertRaises(ValueError):
            collect(grab_path=self.grab, parent=self.tmp.name, count=14)
        with self.assertRaises(ValueError):
            collect(grab_path=self.grab, parent=self.tmp.name, spacing=.1)

    def test_error_does_not_touch_receiver_settings_or_network(self):
        def failing(args, **kwargs):
            self.commands.append(args)
            return types.SimpleNamespace(returncode=1)
        folder, report = collect(grab_path=self.grab, parent=self.tmp.name,
                                 run_command=failing, sleep_fn=lambda _: None)
        self.assertEqual(len(self.commands), 3)
        self.assertEqual(report["captured"], 0)
        self.assertEqual(sorted(os.listdir(folder)), ["report.json"])
        for call in self.commands:
            self.assertEqual(call[0], self.grab)
            self.assertNotIn("wget", " ".join(call))


if __name__ == "__main__":
    unittest.main()
