#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reproducible R76.11 test IPK based on EXACT R76.10 content.

Corrects the unconditional cold decorated-index build in actual normal Preview;
192/64 deep, TV player, core scoring, mapping, SAT, audio, themes unchanged.
Staging only. Never publishes on main or installs on the receiver.
"""
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


previous = load("r7611_baseline", "build-r7610-normal48.py")
fix = load("r7611_corefix", "r7611_preview_cold_index_patch.py")
pack = previous.pack
P = previous.P
CORE = previous.base.CORE
PLUGIN = previous.PLUGIN
UPDATER = previous.UPDATER
OLD = previous.VERSION
VERSION = "1.0.46-r76.11-preview-coldstart-fast-beta"
NOTE = P + "CHANGELOG-R7611-NORMAL-PREVIEW-COLD.txt"
MANIFEST = ("https://raw.githubusercontent.com/wacayoub/IPToSatPro/"
            "release/r769-finalization-20261014/staging/r7611-preview-cold.update.json")


def build(destination=None):
    with tempfile.TemporaryDirectory() as tmp:
        baseline = Path(tmp) / "r7610.ipk"
        base_info = previous.build(baseline)
        assert base_info["version"] == OLD
        archive = pack.unpack_ar(baseline.read_bytes())
        before = pack.members_from(archive["data.tar.gz"])
        controls = pack.members_from(archive["control.tar.gz"])
        source = before[CORE].decode("utf-8")
        fixed = fix.patch_core(source)
        assert fixed != source and fix.TAG in fixed
        assert fixed.count("R7611_NORMAL_PREVIEW_NO_COLD_DECORATED_SCAN") == 1
        assert fixed.count("preview_index = getattr(self, \"_preview_decorated_exact\", None)") == 1

        version_old = 'PLUGIN_VERSION = "' + OLD + '"'
        updater_old = 'CURRENT_VERSION = "' + OLD + '"'
        plugin = before[PLUGIN].decode("utf-8")
        updater = before[UPDATER].decode("utf-8")
        assert plugin.count(version_old) == 1
        assert updater.count(updater_old) == 1
        plugin = plugin.replace(version_old, 'PLUGIN_VERSION = "' + VERSION + '"', 1)
        updater = updater.replace(updater_old,
                                  'CURRENT_VERSION = "' + VERSION + '"', 1)
        old_manifest = ("https://raw.githubusercontent.com/wacayoub/IPToSatPro/"
                        "release/r769-finalization-20261014/staging/r7610-normal48.update.json")
        assert updater.count(old_manifest) == 1
        updater = updater.replace(old_manifest, MANIFEST, 1)

        changes = {
            PLUGIN: plugin.encode("utf-8"),
            UPDATER: updater.encode("utf-8"),
            CORE: fixed.encode("utf-8"),
        }
        control = controls["control"].decode("utf-8")
        assert control.count("Version: " + OLD) == 1
        control = control.replace("Version: " + OLD, "Version: " + VERSION, 1)
        note = (
             "R76.11 beta: remove unconditional whole-catalogue decorated index rebuild "
             "on the ACTUAL normal Preview Catalog._preview_nomination_pool route. "
             "Normal 48/16 reuses warm index and fast prebuilt token identity pools. "
            "DEEP 192/64, scoring, ranking, the player's audio/video, "
            "monitor, mappings, manual locks, HD/FHD skins, persistence, "
            "timeshift and EPG all preserved. Requires real Vu+ performance "
            "validation; no 1-2 second video-zap claim.\n"
        ).encode("utf-8")
        archive["data.tar.gz"] = pack.make_tar(
            archive["data.tar.gz"], changes, {NOTE: note})
        archive["control.tar.gz"] = pack.make_tar(
            archive["control.tar.gz"], {"control": control.encode("utf-8")})
        destination = Path(destination) if destination else ROOT / "iptosatpro-r7611-preview-cold-beta.ipk"
        if destination.exists():
            destination.unlink()
        raw = pack.assemble(archive, destination)
        installed = pack.members_from(pack.unpack_ar(raw)["data.tar.gz"])
        assert set(installed) == set(before) | {NOTE}
        for name in before:
            assert installed[name] == changes.get(name, before[name]), name
        for name, payload in installed.items():
            if name.endswith(".py"):
                compile(payload, name, "exec")
        for name in (P + "monitor.py", P + "metadata_shadow.py", P + "player.py",
                     P + "home_themes_r767.py", P + "preview_theme_r74.py"):
            assert before.get(name) == installed.get(name), name
        assert not any("mapping" in p.lower() or "override" in p.lower()
                       for p in changes)
        return {
            "version": VERSION, "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw), "old_sha256": base_info["sha256"],
            "changed": sorted(changes), "added": [NOTE],
            "unchanged": len(before) - len(changes),
            "production_published": False, "receiver_tested": False,
            "beta": True,
        }


if __name__ == "__main__":
    print("R7611_BUILD_OK", json.dumps(build(sys.argv[1] if len(sys.argv)>1 else None),
                                        sort_keys=True))
