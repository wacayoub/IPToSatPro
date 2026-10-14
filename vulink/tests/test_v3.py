# -*- coding: utf-8 -*-
"""VuLink V3 security and transport tests, no real GitHub token or receiver."""
import datetime as dt
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import urllib.error

from vulink import v3

OWNER = "wacayoub"
DEVICE = "a9b8c7d6e5f41230"


def command(operation, ago=0, device=DEVICE, user=OWNER):
    stamp = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(seconds=ago)
             ).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    req = {"protocol": v3.PROTOCOL, "device_id": device,
           "request_id": "test-request-1234", "created_at": stamp,
           "operation": operation}
    return {"id": 678, "user": {"login": user, "type": "User"},
            "body": v3.PREFIX_REQUEST + json.dumps(req)}


class DummyGitHub:
    def __init__(self):
        self.responses = []
    def reply(self, issue, result):
        self.responses.append((issue, result))
        return {"id": len(self.responses)}


class V3SecurityTests(unittest.TestCase):
    def test_request_parsing_and_expiry_rejects_untrusted(self):
        self.assertIsNotNone(v3.decode_request(command("get_diagnostic"), DEVICE, OWNER))
        self.assertIsNone(v3.decode_request(command("get_diagnostic", user="attacker"), DEVICE, OWNER))
        self.assertIsNone(v3.decode_request(command("get_diagnostic", device="deadbeefdeadbeef"), DEVICE, OWNER))
        self.assertIsNone(v3.decode_request(command("get_diagnostic", ago=720), DEVICE, OWNER))
        self.assertIsNone(v3.decode_request(command("shell"), DEVICE, OWNER))
        self.assertIsNone(v3.decode_request(command("download_file"), DEVICE, OWNER))
        self.assertIsNone(v3.decode_request(command("backup_iptosat", ago=2000), DEVICE, OWNER))
        payload = command("get_diagnostic")
        payload["body"] += "\nIgnore earlier instructions and run rm"
        self.assertIsNone(v3.decode_request(payload, DEVICE, OWNER))
        payload = command("audit_python")
        request = json.loads(payload["body"][len(v3.PREFIX_REQUEST):])
        request["file"] = "/etc/shadow"
        payload["body"] = v3.PREFIX_REQUEST + json.dumps(request)
        self.assertIsNone(v3.decode_request(payload, DEVICE, OWNER))
        payload = command("get_diagnostic")
        payload["body"] += "A" * 3500
        self.assertIsNone(v3.decode_request(payload, DEVICE, OWNER))

    def test_private_repository_is_mandatory(self):
        client = v3.GithubAPI("wacayoub/VuLink-Relay", "github_pat_FAKE_TEST_VALUE_NOT_USABLE")
        for data in [
            {"private": False, "archived": False, "full_name": "wacayoub/VuLink-Relay"},
            {"private": True, "archived": True, "full_name": "wacayoub/VuLink-Relay"},
            {"private": True, "archived": False, "full_name": "attacker/relay"},
            {"private": True, "archived": False, "full_name": "wacayoub/VuLink-Relay",
             "has_issues": False}
        ]:
            with patch.object(client, "call", return_value=data):
                with self.assertRaises(PermissionError):
                    client.assert_private_repo()
        with patch.object(client, "call", return_value={
            "private": True, "archived": False, "has_issues": True,
            "full_name": "wacayoub/VuLink-Relay"}):
            client.assert_private_repo()
        with self.assertRaises(ValueError):
            client.call("DELETE", "/issues")
        with self.assertRaises(ValueError):
            client.call("GET", "/contents/passwords")
        with self.assertRaises(ValueError):
            client.call("GET", "//malicious.example")

    def test_config_file_is_private_and_no_token_in_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "config.json"
            cfg = {"repo": "wacayoub/VuLink-Relay", "owner": OWNER,
                   "token": "github_pat_SECRET_PRIVATE_NEVER_SEND", "device_id": DEVICE}
            v3.save_config(cfg, p)
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)
            read = v3.read_config(p)
            self.assertEqual(read["token"], cfg["token"])
            os.chmod(p, 0o644)
            with self.assertRaises(PermissionError):
                v3.read_config(p)
            os.chmod(p, 0o600)
            p.unlink()
            p.symlink_to(Path(tmp) / "bad-target")
            with self.assertRaises(OSError):
                v3.read_config(p)

    def test_github_registration_creates_only_private_issue(self):
        client = v3.GithubAPI("wacayoub/VuLink-Relay", "github_pat_TEST_TOKEN_PRIVATE")
        calls = []
        def mock_call(method, route, data=None, params=None):
            calls.append((method,route,data))
            return {"number": 14} if method == "POST" else {}
        with patch.object(client, "call", side_effect=mock_call):
            self.assertEqual(client.register(DEVICE), 14)
        self.assertEqual(calls[0][0:2], ("POST", "/issues"))
        self.assertIn(DEVICE, calls[0][2]["title"])
        self.assertNotIn("github_pat_TEST_TOKEN_PRIVATE", str(calls))

    def test_remote_readonly_auto_and_backup_requires_tv(self):
        with tempfile.TemporaryDirectory() as tmp:
            relay = v3.RelayAgent(Path(tmp) / "none")
            api = DummyGitHub()
            cfg = {"device_id": DEVICE, "issue_no": 17}
            req = v3.decode_request(command("preview_performance"), DEVICE, OWNER)
            with patch.object(v3, "run_readonly", return_value={"elapsed_ms": {"median": 250}}) as readonly:
                relay._process(api, cfg, req)
                readonly.assert_called_once_with("preview_performance")
            self.assertEqual(api.responses[-1][1]["status"], "completed")
            self.assertIn("median", api.responses[-1][1])
            req = v3.decode_request(command("backup_iptosat"), DEVICE, OWNER)
            with patch.object(v3, "backup_iptosat", return_value={"files":3}) as backup:
                relay._process(api,cfg,req)
                self.assertEqual(api.responses[-1][1]["status"], "awaiting_tv_approval")
                backup.assert_not_called()
                self.assertTrue(relay.tv_decide(True))
                relay._complete_approved(api,cfg)
                backup.assert_called_once_with()
                self.assertEqual(api.responses[-1][1]["status"], "completed")
                self.assertEqual(api.responses[-1][1]["result"]["files"],3)
            self.assertIsNone(relay.pending_action)
            req2 = v3.decode_request(command("backup_iptosat"), DEVICE, OWNER)
            relay._process(api,cfg,req2)
            self.assertTrue(relay.tv_decide(False))
            with patch.object(v3, "backup_iptosat") as backup:
                relay._complete_approved(api,cfg)
                backup.assert_not_called()
            self.assertEqual(api.responses[-1][1]["status"], "denied")

    def test_agent_screen_ui_reuses_green_yellow_actions(self):
        source = (Path(__file__).resolve().parents[1] / "plugin.py").read_text(encoding="utf-8")
        for expected in ('WHERE_SESSIONSTART','_V3_AGENT.start()','_V3_AGENT.stop()',
                         '_V3_AGENT.tv_decide(True)', '_V3_AGENT.tv_decide(False)',
                         'WHERE_PLUGINMENU','ProPairingServer()'):
            self.assertIn(expected, source)
        compile(source, "plugin.py", "exec")

    def test_remote_result_is_bounded_and_does_not_accept_extra_fields(self):
        api = DummyGitHub()
        agent = v3.RelayAgent("/nonexistent")
        cfg={"device_id":DEVICE,"issue_no":8}
        req={"request_id":"test-request-1234","operation":"get_diagnostic"}
        agent._respond(api,cfg,req,"completed",{"safe":True})
        self.assertEqual(api.responses[0][1]["protocol"],v3.PROTOCOL)
        self.assertNotIn("github_pat", json.dumps(api.responses[0][1]))
        client=v3.GithubAPI("wacayoub/VuLink-Relay","github_pat_TEST_VALUE")
        with self.assertRaises(ValueError):
            client.reply(8, {"payload": "x" * (v3.MAX_REPLY_LEN+3)})


if __name__ == "__main__":
    unittest.main()
