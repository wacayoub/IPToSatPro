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
import urllib.error

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
        # Verify the Issues READ permission too. POST write is exercised
        # later by the receiver relay when it registers its device issue.
        api.call("GET", "/issues", params={"state": "open", "per_page": 1})
    except urllib.error.HTTPError as exc:
        # Do NOT include exc, its URL, body or headers: only the HTTP code.
        code = exc.code
        print("VULINK_GITHUB_HTTP_STATUS:", code)
        if code == 401:
            print("Jeton invalide, expire ou colle incorrectement. Cree un nouveau fine-grained token.")
        elif code == 403:
            print("Acces refuse: permissions, politique du compte ou restrictions GitHub.")
            print("Selectionne uniquement ce depot, avec Issues: Read and write.")
        elif code == 404:
            print("Depot introuvable pour CE jeton (meme si le depot existe).")
            print("Verifie owner/repo, Repository access: Only select repositories,")
            print("et choisis exactement ce depot prive dans la liste.")
        elif code == 429:
            print("Trop de requetes GitHub. Reessaie plus tard.")
        else:
            print("Erreur API GitHub HTTP %d. Verifie le token et les droits du depot." % code)
        print("Aucun jeton enregistre. Ne partage jamais le jeton dans ChatGPT.")
        return 3
    except PermissionError:
        print("Le depot n'est pas PRIVATE, ou Issues n'est pas active.")
        print("Le depot GitHub de relais doit rester strictement prive.")
        return 3
    except urllib.error.URLError:
        print("Probleme de connexion HTTPS vers api.github.com, DNS ou certificats.")
        print("Verifie reseau, horloge et certificats du Vu+.")
        return 3
    except (ValueError, OSError, KeyError) as exc:
        print("Verification GitHub echouee : " + type(exc).__name__)
        print("Aucun jeton enregistre.")
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
