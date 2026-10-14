#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent V3 GitHub PAT diagnostics. No receiver changes, no token persistence.

Safe usage: download this file over HTTPS from the verified GitHub repository,
run on the Vu+ shell, enter the token via hidden terminal prompt.
"""
import getpass
import json
import re
import sys
from urllib import error, request

REPOSITORY = "wacayoub/VuLink-Relay"
BASE = "https://api.github.com"


def github_get(opener, token, route):
    """Fixed GitHub REST API host; never redirect the PAT to user-input URLs."""
    if route not in ("/user",
                     "/repos/" + REPOSITORY,
                     "/repos/" + REPOSITORY + "/issues?state=open&per_page=1"):
        raise ValueError("unrecognized GitHub endpoint")
    req = request.Request(
        BASE + route,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28",
                 "User-Agent": "VuLink-V3-Github-Auth-Probe"})
    try:
        with opener.open(req, timeout=12) as stream:
            raw = stream.read(65537)
            if len(raw) > 65536:
                return 0, {}
            return getattr(stream, "status", 200), json.loads(raw.decode("utf-8"))
    except error.HTTPError as exc:
        return exc.code, {}
    except error.URLError:
        return -1, {}


def diagnosis(token, opener=None, emit=print):
    """Print only HTTP numbers and the authenticated GitHub login, never secrets."""
    opener = opener or request.build_opener(request.ProxyHandler({}))
    emit("VULINK_AUTH_DIAGNOSTIC_START")
    code, user = github_get(opener, token, "/user")
    emit("AUTH_HTTP: %d" % code)
    if code != 200:
        if code == 401:
            emit("RESULT: TOKEN_INVALID_OR_EXPIRED")
        elif code == 403:
            emit("RESULT: GITHUB_AUTH_FORBIDDEN")
        else:
            emit("RESULT: HTTPS_AUTH_ERROR")
        return False
    login = str(user.get("login", ""))
    if not re.fullmatch("[A-Za-z0-9-]{1,39}", login):
        emit("RESULT: UNKNOWN_GITHUB_ACCOUNT")
        return False
    emit("AUTH_ACCOUNT: " + login)
    if login.lower() != REPOSITORY.split("/")[0].lower():
        emit("RESULT: WRONG_TOKEN_RESOURCE_OWNER")
        emit("Create the token while logged into the GitHub account wacayoub.")
        return False
    code, info = github_get(opener, token, "/repos/" + REPOSITORY)
    emit("REPO_HTTP: %d" % code)
    if code != 200:
        if code == 404:
            emit("RESULT: TOKEN_CANNOT_SEE_SELECTED_PRIVATE_REPO")
            emit("GitHub token settings: Resource owner = wacayoub; "
                 "Repository access = Only select repositories; selected = VuLink-Relay.")
        else:
            emit("RESULT: PRIVATE_REPO_ACCESS_ERROR")
        return False
    if info.get("private") is not True:
        emit("RESULT: RELAY_REPO_IS_NOT_PRIVATE")
        return False
    code, _issues = github_get(
        opener, token, "/repos/" + REPOSITORY + "/issues?state=open&per_page=1")
    emit("ISSUES_HTTP: %d" % code)
    if code != 200:
        emit("RESULT: TOKEN_REQUIRES_ISSUES_READ_WRITE")
        return False
    emit("RESULT: GITHUB_TOKEN_READ_ACCESS_OK")
    emit("You can now rerun VuLink v3_setup.py with the same token.")
    return True


def main():
    print("VuLink V3 — controle du jeton GitHub, lecture seule")
    print("Depot attendu: " + REPOSITORY)
    print("Ne partage pas le jeton; rien n'est enregistre.")
    try:
        token = getpass.getpass("GitHub token (saisie masquee) : ").strip()
    except (EOFError, KeyboardInterrupt):
        print("Annule")
        return 2
    if len(token) < 30 or any(c.isspace() for c in token):
        print("RESULT: INVALID_TOKEN_INPUT")
        return 2
    return 0 if diagnosis(token) else 3


if __name__ == "__main__":
    sys.exit(main())
