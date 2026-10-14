# -*- coding: utf-8 -*-
"""Offline tests for the VuLink V3 PAT diagnostic: 401/403/404, no token leaks."""
import io
import json
import urllib.error
import unittest

from vulink import v3_auth_probe as probe


class Reply(io.BytesIO):
    status = 200
    def __init__(self, data):
        super().__init__(json.dumps(data).encode("utf-8"))


class MockOpener:
    def __init__(self, user, repo, issues=200):
        self.codes = [user, repo, issues]
        self.paths = []
        self.auth_headers = []
    def open(self, req, timeout=12):
        self.paths.append(req.full_url)
        self.auth_headers.append(req.get_header("Authorization"))
        index = len(self.paths) - 1
        code = self.codes[index]
        if isinstance(code, int) and code != 200:
            raise urllib.error.HTTPError(req.full_url, code, "mock", {}, None)
        return Reply(code)


class AuthProbeTests(unittest.TestCase):
    def test_auth_is_invalid_or_expired(self):
        runner = MockOpener(401, 200)
        out = []
        self.assertFalse(probe.diagnosis("github_pat_TEST_NEVER_EXPOSE", runner, out.append))
        self.assertIn("AUTH_HTTP: 401", out)
        self.assertIn("RESULT: TOKEN_INVALID_OR_EXPIRED", out)
        self.assertEqual(len(runner.paths), 1)

    def test_wrong_authenticated_github_account(self):
        runner = MockOpener({"login": "other-user"}, 200)
        out = []
        self.assertFalse(probe.diagnosis("github_pat_TEST_NEVER_EXPOSE", runner, out.append))
        self.assertIn("RESULT: WRONG_TOKEN_RESOURCE_OWNER", out)
        self.assertEqual(len(runner.paths), 1)

    def test_private_repo_404_diagnosed_as_repository_selection(self):
        runner = MockOpener({"login": "wacayoub"}, 404)
        out = []
        self.assertFalse(probe.diagnosis("github_pat_TEST_NEVER_EXPOSE", runner, out.append))
        self.assertIn("AUTH_HTTP: 200", out)
        self.assertIn("REPO_HTTP: 404", out)
        self.assertIn("RESULT: TOKEN_CANNOT_SEE_SELECTED_PRIVATE_REPO", out)
        self.assertEqual(len(runner.paths), 2)

    def test_issue_access_rejected(self):
        runner = MockOpener({"login": "wacayoub"}, {"private": True}, 403)
        out = []
        self.assertFalse(probe.diagnosis("github_pat_TEST_NEVER_EXPOSE", runner, out.append))
        self.assertIn("REPO_HTTP: 200", out)
        self.assertIn("ISSUES_HTTP: 403", out)
        self.assertIn("RESULT: TOKEN_REQUIRES_ISSUES_READ_WRITE", out)

    def test_success_and_token_always_redacted(self):
        token="github_pat_TEST_SUPER_SECRET_NEVER_SEND"
        runner = MockOpener({"login": "wacayoub"}, {"private": True}, [])
        out = []
        self.assertTrue(probe.diagnosis(token, runner, out.append))
        self.assertIn("RESULT: GITHUB_TOKEN_READ_ACCESS_OK", out)
        self.assertNotIn(token, "\n".join(out))
        self.assertTrue(all(value == "Bearer " + token for value in runner.auth_headers))
        self.assertTrue(all(url.startswith("https://api.github.com/") for url in runner.paths))
        self.assertEqual(len(runner.paths), 3)

    def test_token_cannot_change_endpoint_host(self):
        op = MockOpener({}, {})
        with self.assertRaises(ValueError):
            probe.github_get(op, "github_pat_TEST", "//evil.example/private")
        with self.assertRaises(ValueError):
            probe.github_get(op, "github_pat_TEST", "/repos/wacayoub/IPToSatPro")


if __name__ == "__main__":
    unittest.main()
