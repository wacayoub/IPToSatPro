# -*- coding: utf-8 -*-
"""Offline VuLink checks: LAN session, expiry, brute-force throttle, redaction."""
import importlib.util
import json
import pathlib
import tempfile
import unittest
import urllib.error
import urllib.request
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("vulink_bridge", ROOT / "bridge.py")
vulink = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vulink)


class VuLinkTests(unittest.TestCase):
    def test_pairing_secret_code_and_throttle(self):
        pair = vulink.PairingServer(ip="192.168.1.50", lifetime=600)
        self.assertEqual(len(pair.code), 12)
        self.assertNotIn("-", pair.code)
        self.assertTrue(pair._allowed(pair.code, "192.168.1.6"))
        self.assertTrue(pair._allowed("-".join((pair.code[:4],pair.code[4:8],pair.code[8:])),
                                      "192.168.1.6"))
        for _ in range(8):
            self.assertFalse(pair._allowed("BADCODE", "192.168.1.9"))
        self.assertFalse(pair._allowed(pair.code, "192.168.1.9"))
        self.assertTrue(pair._allowed(pair.code, "192.168.1.8"))
        with mock.patch.object(vulink.time, "monotonic", return_value=pair.deadline + 1):
            self.assertFalse(pair._allowed(pair.code, "192.168.1.8"))

    def test_public_ip_rejected_before_http_start(self):
        for address in ("8.8.8.8", "1.1.1.1", "127.0.0.1"):
            with self.assertRaises(ValueError):
                vulink.PairingServer(ip=address)

    def test_report_is_whitelist_only(self):
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            app = base / "SatIPTVBridge"
            app.mkdir()
            (app / "plugin.py").write_text('PLUGIN_VERSION = "1.0.46-r76.9"\n')
            (app / "player.py").write_text("secret-iptv-token=xyz\\n")
            log = base / "bridge.log"
            log.write_text(
                "2026-10-14 01:00:00 | IPTV_OK | url=https://evil.example/"
                "SECRET-CREDENTIAL login=do-not-leak latency=1043ms\n"
                "2026-10-14 01:00:01 | PREVIEW_RANK_BG | sat='Sensitive Channel' "
                "elapsed=2800ms scored=8\n"
                "2026-10-14 01:00:02 | NO_MATCH | sat='Sensitive Channel' "
                "pass=ANOTHER-SECRET\n", encoding="utf-8")
            with mock.patch.object(vulink, "PLUGIN_ROOT", app), mock.patch.object(
                vulink, "LOG_FILE", log):
                doc = vulink.collect_report()
            payload = json.dumps(doc)
            self.assertIn("1.0.46-r76.9", payload)
            for token in ("SECRET-CREDENTIAL", "do-not-leak", "Sensitive Channel",
                          "ANOTHER-SECRET", "evil.example"):
                self.assertNotIn(token, payload)
            self.assertEqual(doc["diagnostics"]["events"]["IPTV_OK"], 1)
            self.assertEqual(doc["diagnostics"]["metrics"]["latency_ms"]["median"], 1043)
            self.assertTrue(doc["iptosatpro"]["files"]["player.py"]["present"])

    def test_live_http_pairing_and_revocation(self):
        try:
            address = vulink.detect_lan_ipv4()
        except OSError:
            self.skipTest("CI does not expose an RFC1918 LAN interface")
        server = vulink.PairingServer(ip=address, lifetime=600)
        try:
            server.start()
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            def get(path):
                return opener.open(server.base_url + path, timeout=5)
            with get("") as response:
                self.assertEqual(response.status, 200)
                self.assertIn(b"Appairage local", response.read())
                self.assertEqual(response.headers.get("Cache-Control"), "no-store, max-age=0")
            with self.assertRaises(urllib.error.HTTPError) as error:
                get("report/WRONG.json")
            self.assertEqual(error.exception.code, 403)
            with get("p/" + server.code) as response:
                self.assertIn(b"rapport", response.read())
            with get("report/" + server.code + ".json") as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers["Content-Type"], "application/json; charset=utf-8")
                doc = json.loads(response.read())
                self.assertEqual(doc["schema"], "vulink-diagnostic-v1")
                self.assertNotIn("192.", json.dumps(doc))
            server.deadline = vulink.time.monotonic() - 1
            with self.assertRaises(urllib.error.HTTPError) as error:
                get("p/" + server.code)
            self.assertEqual(error.exception.code, 410)
        finally:
            server.stop()

    def test_offline_qr_png_without_dependencies(self):
        spec = importlib.util.spec_from_file_location("vulink_qrpng", ROOT / "qrpng.py")
        qr = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(qr)
        import random
        import struct
        randomizer = random.Random(123)
        known = set()
        for _ in range(100):
            code = "".join(randomizer.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=12))
            url = "http://192.168.1.12:43000/p/" + code
            data = qr.qr_png(url)
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack("!II", data[16:24]), (246, 246))
            self.assertGreater(len(data), 800)
            known.add(data)
        self.assertEqual(len(known), 100)
        with self.assertRaises(ValueError):
            qr.qr_png("https://example.com/" + "x" * 100)

    def test_enigma2_gui_syntax_and_scope(self):
        text = (ROOT / "plugin.py").read_text(encoding="utf-8")
        compile(text, "vulink/plugin.py", "exec")
        self.assertIn("WHERE_PLUGINMENU", text)
        self.assertIn("WHERE_EXTENSIONSMENU", text)
        self.assertIn("self.pair.stop()", text)
        self.assertNotIn("os.system(", text)
        self.assertNotIn("subprocess.run(", text)
        self.assertNotIn("password", text.lower())


if __name__ == "__main__":
    unittest.main()
