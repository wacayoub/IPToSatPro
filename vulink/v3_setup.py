#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-time V3 setup on Vu+ terminal. Never paste GitHub PAT into ChatGPT."""
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import sys

def main():
    if os.geteuid() != 0:
        print("ERROR: use Vu+ root shell to configure secure local token.")
        return 2
    plugin_parent = str(Path(__file__).resolve().parents[3])
    # .../python/Plugins/Extensions/VuLink/v3_setup.py -> .../python
    sys.path.insert(0, plugin_parent)
    from Plugins.Extensions.VuLink.v3 import (
        CONFIG_PATH, GithubAPI, REPO_PATTERN, read_config, save_config)
    print("VuLink V3 — connexion GitHub privee (une seule configuration).")
    print("GitHub repo: nouveau depot PRIVATE avec Issues, reserve a VuLink.")
    print("Token GitHub fine-grained: uniquement ce depot, Issues READ/WRITE.")
    print("Le token est saisi ici, jamais dans ChatGPT ou le QR.")
    repo = input("Depot prive owner/repo : ").strip()
    if not REPO_PATTERN.fullmatch(repo):
        print("Depot invalide.")
        return 2
    owner = repo.split("/")[0]
    token = getpass.getpass("GitHub token (saisie masquee) : ").strip()
    if len(token) < 30 or any(c in token for c in ("\n","\r")):
        print("Token invalide (rien n'a ete enregistre).")
        return 2
    try:
        api = GithubAPI(repo, token)
        api.assert_private_repo()
    except Exception as exc:
        # Never log token, request, response or token-bearing headers.
        print("La verification du depot GitHub prive a echoue : " + type(exc).__name__)
        return 3
    try:
        old = read_config(CONFIG_PATH)
        device_id = old.get("device_id") if old.get("repo", "").lower() == repo.lower() else None
    except (OSError, ValueError, PermissionError):
        device_id = None
    if not device_id:
        device_id = secrets.token_hex(8)
    config = {"repo": repo, "owner": owner, "token": token, "device_id": device_id,
              "issue_no": 0, "last_comment_id": 0}
    try:
        save_config(config)
    except (OSError, PermissionError) as exc:
        print("Enregistrement refuse : " + type(exc).__name__)
        return 4
    print("VULINK_V3_CONFIGURED")
    print("Device ID : " + device_id)
    print("Depot prive : " + repo)
    print("Aucun port routeur et aucune connexion SSH entrante necessaires.")
    print("Redemarre uniquement l'interface Enigma2, puis ouvre VuLink sur la TV.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
