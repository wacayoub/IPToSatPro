# -*- coding: utf-8 -*-
"""V2: real local HTTP, one-time authentication, CSRF, TV authorization, backup."""
import http.cookiejar
import importlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from unittest import mock

from vulink import v2


class VuLinkV2Tests(unittest.TestCase):
    def test_preview_stage_metrics_strip_sensitive_log_text(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            log=p/"bridge.log"
            log.write_text(
                "2026-10-14 | PREVIEW_RANK_BG | sat='SECRET: NILE HD' "
                "candidate_count=48 elapsed=11714ms index=11000ms scoring=714ms scored=48 error=\n"
                "2026-10-14 | PREVIEW_RANK_BG | provider=PRIVATE "
                "candidate_count=0 elapsed=34269ms index=34000ms scoring=269ms scored=0 error=NoCandidates\n"
                "2026-10-14 | IPTV_OK | account=DO-NOT-LEAK latency=900ms\n")
            with mock.patch.object(v2, "CONF_ROOT", p):
                report=v2._preview_stage_statistics()
            self.assertEqual(report["stage_metrics"]["elapsed_ms"]["median"],34269)
            self.assertEqual(report["stage_metrics"]["index_ms"]["max"],34000)
            self.assertEqual(report["stage_metrics"]["scoring_ms"]["samples"],2)
            self.assertEqual(report["error_count"],1)
            self.assertNotIn("PRIVATE",json.dumps(report))
            self.assertNotIn("SECRET",json.dumps(report))
            self.assertNotIn("DO-NOT-LEAK",json.dumps(report))

    def test_pro_session_is_private_and_short_lived(self):
        obj = v2.ProPairingServer(ip="192.168.0.2")
        self.assertIsNone(obj._make_session("192.168.0.4", "WRONG"))
        token = obj._make_session("192.168.0.4", obj.code)
        self.assertEqual(len(token) > 32, True)
        self.assertIsNotNone(obj._auth("192.168.0.4", "vulink_v2=" + token))
        self.assertIsNone(obj._auth("192.168.0.5", "vulink_v2=" + token))
        self.assertIsNone(obj._auth("192.168.0.4", "vulink_v2=INVALID"))
        obj.deadline = time.monotonic() - 1
        self.assertIsNone(obj._auth("192.168.0.4", "vulink_v2=" + token))

    def test_pending_needs_actual_tv_decision_and_expires(self):
        obj = v2.ProPairingServer(ip="192.168.0.2")
        rid = obj.request("audit_python")
        self.assertIsNotNone(rid)
        self.assertIsNone(obj.request("backup_iptosat"))
        self.assertFalse(obj.decide("FAKE", True))
        self.assertFalse(obj.decide(rid, False) is False)
        self.assertEqual(obj._queue[rid]["status"], "denied")
        rid2 = obj.request("audit_python")
        obj._queue[rid2]["expires"] = time.monotonic() - 1
        self.assertIsNone(obj.pending())
        self.assertFalse(obj.decide(rid2, True))
        self.assertEqual(obj._queue[rid2]["status"], "expired")
        obj.stop()

    def test_approved_audit_runs_allowlisted_handler(self):
        obj = v2.ProPairingServer(ip="192.168.0.2")
        with mock.patch.object(v2, "perform_action", return_value={"audit": "yes"}) as run:
            rid = obj.request("audit_python")
            self.assertTrue(obj.decide(rid, True))
            for _ in range(30):
                if not obj.public_state()["busy"]:
                    break
                time.sleep(0.05)
            self.assertEqual(obj.public_state()["last_action"]["status"], "completed")
            run.assert_called_once_with("audit_python")
        obj.stop()

    def test_backup_never_follows_symlink_and_is_private(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            plugin = root / "source_plugin"
            conf = root / "source_settings"
            plugin.mkdir()
            conf.mkdir()
            (plugin / "plugin.py").write_text('SAFE SOURCE\n', encoding="utf-8")
            (conf / "mappings.json").write_text('{"private":"token-value"}', encoding="utf-8")
            (plugin / "leak").symlink_to(conf / "mappings.json")
            backups = root / "secure_backup"
            with mock.patch.object(v2, "PLUGIN_ROOT", plugin), mock.patch.object(
                v2, "CONF_ROOT", conf), mock.patch.object(v2, "BACKUP_ROOT", backups):
                result = v2.backup_iptosat()
            self.assertEqual(result["files"], 2)
            self.assertEqual(result["skipped"], 1)
            dest = next(backups.iterdir())
            self.assertTrue((dest / "plugin/plugin.py").exists())
            self.assertFalse((dest / "plugin/leak").exists())
            self.assertTrue((dest / "settings/mappings.json").exists())
            self.assertEqual(os.stat(backups).st_mode & 0o777, 0o700)
            self.assertEqual(os.stat(dest / "settings/mappings.json").st_mode & 0o777, 0o600)
            self.assertNotIn("token-value", json.dumps(result))
            with mock.patch.object(v2, "PLUGIN_ROOT", plugin), mock.patch.object(
                v2, "CONF_ROOT", conf), mock.patch.object(v2, "BACKUP_ROOT", backups), mock.patch.object(
                v2, "MAX_BACKUP_BYTES", 5):
                with self.assertRaises(ValueError):
                    v2.backup_iptosat()
            self.assertEqual(len(list(backups.iterdir())), 1)

    def test_unsupported_remote_action_refused(self):
        with self.assertRaises(ValueError):
            v2.perform_action("rm -rf /")
        obj = v2.ProPairingServer(ip="192.168.0.2")
        self.assertIsNone(obj.request("ssh_exec"))
        self.assertIsNone(obj.request("../plugin.py"))
        obj.stop()

    def test_http_session_cookie_csrf_and_report_retrieval(self):
        try:
            from vulink.bridge import detect_lan_ipv4
            address = detect_lan_ipv4()
        except OSError:
            self.skipTest("CI has no RFC1918 interface")
        service = v2.ProPairingServer(ip=address)
        jar = http.cookiejar.CookieJar()
        browser = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), urllib.request.HTTPCookieProcessor(jar))
        raw = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        def get(path):
            return browser.open(service.base_url + path, timeout=4)
        def post(path, payload, opener=browser, origin=None):
            request = urllib.request.Request(
                service.base_url + path,
                data=urllib.parse.urlencode(payload).encode("ascii"),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST")
            if origin:
                request.add_header("Origin", origin)
            return opener.open(request, timeout=4)
        try:
            service.start()
            base_url = service.base_url
            with self.assertRaises(urllib.error.HTTPError) as e:
                get("api/report")
            self.assertEqual(e.exception.code, 401)
            with get("p/" + service.code) as response:
                self.assertIn(b"VuLink Pro V2", response.read())
                self.assertIn("vulink_v2", str(jar))
            with get("api/report") as response:
                self.assertEqual(json.load(response)["schema"], "vulink-pro-v2-diagnostic")
            with self.assertRaises(urllib.error.HTTPError) as e:
                post("action", {"action": "audit_python", "csrf": "WRONG"})
            self.assertEqual(e.exception.code, 403)
            with self.assertRaises(urllib.error.HTTPError) as e:
                post("action", {"action": "audit_python", "csrf": "WRONG"},
                     origin="https://attacker.example")
            self.assertEqual(e.exception.code, 403)
            session = service._auth("127.0.0.1", "invalid")
            self.assertIsNone(session)
            csrf = next(iter(service._sessions.values()))["csrf"]
            with post("action", {"action": "audit_python", "csrf": csrf}) as response:
                self.assertIn(b"VuLink Pro V2", response.read())
            pending = service.pending()
            self.assertIsNotNone(pending)
            self.assertEqual(pending[1]["action"], "audit_python")
            with self.assertRaises(urllib.error.HTTPError) as e:
                post("action", {"action": "ssh", "csrf": csrf})
            self.assertEqual(e.exception.code, 409)
            self.assertTrue(service.decide(pending[0], False))
            service.stop()
            with self.assertRaises((urllib.error.HTTPError, urllib.error.URLError,
                                    ConnectionResetError)):
                browser.open(base_url + "api/report", timeout=4)
        finally:
            service.stop()

    def test_receiver_plugin_wires_green_yellow_and_timer(self):
        source = (Path(__file__).resolve().parents[1] / "plugin.py").read_text()
        self.assertIn("ProPairingServer()", source)
        self.assertIn('"green": self._approve', source)
        self.assertIn('"yellow": self._deny', source)
        self.assertIn("self.pair.decide(self._pending_id, True)", source)
        self.assertIn("self.pair.decide(self._pending_id, False)", source)
        self.assertIn("self.approval_timer.stop()", source)
        self.assertIn("self.pair.stop()", source)
        compile(source, "plugin.py", "exec")


if __name__ == "__main__":
    unittest.main()
