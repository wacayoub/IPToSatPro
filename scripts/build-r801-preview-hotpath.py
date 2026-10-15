#!/usr/bin/env python3
"""Build nonproduction R80.1 Preview hot-path beta from exact R80 RC1.

R80 RC1 inherits the SHA-verified R76.15 engine. This package changes ONLY:
- core.py: deterministic Preview-only ratio memoization and repeat sort key;
- plugin.py: version string;
- updater.py: beta manifest and version strings;
- passive package metadata and readme note.

No receiver communication, installation, media/player modifications, mappings,
service catalogs or settings. Actual Vu+ latency still unmeasured.
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
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


baseline = load("r801_from_frozen_rc1", "build-r80-final-rc1.py")
patch = load("r801_hotpath", "r80_preview_hotpath_patch.py")
pack = baseline.pack
PLUGIN = baseline.PLUGIN
UPDATER = baseline.UPDATER
CORE = baseline.CORE
P = baseline.P
OLD = baseline.VERSION
VERSION = "1.0.46-r80.1-preview-hotpath-beta"
NOTE = P + "R801-EXPERIMENTAL-HOTPATH.txt"
BASE_SHA = "ca4077a83869d7b7b52510bb4816b2c57c5320cc84d249fc004c5b47c9f055ce"
MANIFEST = ("https://raw.githubusercontent.com/wacayoub/IPToSatPro/"
            "feature/r80-preview-hotpath-20261015/staging/r801-preview-hotpath.update.json")
PREVIOUS_MANIFEST = baseline.MANIFEST
POSTINST = baseline.POSTINST.replace(
    b"R80 release candidate installed", b"R80.1 Preview hot-path beta installed")
assert b"R80.1 Preview hot-path beta installed" in POSTINST
assert b"rm " not in POSTINST and b"mv " not in POSTINST and b"import_spec" not in POSTINST


def build(destination=None):
    with tempfile.TemporaryDirectory() as temp:
        original = Path(temp) / "r80-rc1.ipk"
        meta = baseline.build(original)
        assert meta["version"] == OLD and meta["sha256"] == BASE_SHA
        ar = pack.unpack_ar(original.read_bytes())
        before = pack.members_from(ar["data.tar.gz"])
        ctrl = pack.members_from(ar["control.tar.gz"])
        assert ctrl["postinst"] == baseline.POSTINST
        assert not {"preinst", "prerm", "postrm"}.intersection(ctrl)

        old_core = before[CORE].decode("utf8")
        new_core = patch.patch_core(old_core)
        assert patch.TAG in new_core and patch.TAG not in old_core
        old_version = 'PLUGIN_VERSION = "' + OLD + '"'
        old_plugin = before[PLUGIN].decode("utf8")
        assert old_plugin.count(old_version) == 1
        new_plugin = old_plugin.replace(old_version, 'PLUGIN_VERSION = "' + VERSION + '"', 1)
        old_updater = before[UPDATER].decode("utf8")
        updater_version = 'CURRENT_VERSION = "' + OLD + '"'
        assert old_updater.count(updater_version) == 1
        assert old_updater.count(PREVIOUS_MANIFEST) == 1
        new_updater = old_updater.replace(updater_version,
                                          'CURRENT_VERSION = "' + VERSION + '"', 1)
        new_updater = new_updater.replace(PREVIOUS_MANIFEST, MANIFEST, 1)
        changes = {CORE: new_core.encode("utf8"),
                   PLUGIN: new_plugin.encode("utf8"),
                   UPDATER: new_updater.encode("utf8")}

        old_control = ctrl["control"].decode("utf8")
        assert old_control.count("Version: " + OLD) == 1
        ar["control.tar.gz"] = pack.make_tar(ar["control.tar.gz"], {
            "control": old_control.replace("Version: " + OLD, "Version: " + VERSION, 1).encode("utf8"),
            "postinst": POSTINST,
        })
        note = (
            "IPToSatPro R80.1 Preview hot-path beta / NOT stable.\n"
            "Source: exact verified R80 RC1 package, inheriting R76.15.\n"
            "Only Preview scoring ratio memoization and repeated sort keys change.\n"
            "No player, mappings, catalog persistence or preview GUI changes.\n"
            "Requires independent real Vu+ Zero 4K cold benchmark, quality parity\n"
            "and stable rollback validation before release promotion.\n"
        )
        ar["data.tar.gz"] = pack.make_tar(ar["data.tar.gz"], changes,
                                           {NOTE: note.encode("utf8")})
        target = Path(destination) if destination else ROOT / "iptosatpro-r801-preview-hotpath-beta.ipk"
        if target.exists():
            target.unlink()
        raw = pack.assemble(ar, target)
        after = pack.members_from(pack.unpack_ar(raw)["data.tar.gz"])
        assert set(after) == set(before) | {NOTE}
        for filename, data in before.items():
            assert after[filename] == changes.get(filename, data), filename
        for filename, data in after.items():
            if filename.endswith(".py"):
                compile(data, filename, "exec")
        assert patch.patch_core(new_core) == new_core
        final_control = pack.members_from(pack.unpack_ar(raw)["control.tar.gz"])
        assert final_control["postinst"] == POSTINST
        assert not {"preinst", "prerm", "postrm"}.intersection(final_control)
        assert after[CORE] != before[CORE]
        return {
            "version": VERSION,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "size": len(raw),
            "source_sha256": BASE_SHA,
            "source_receiver_version": "1.0.46-r76.15-preview-index-fast-beta",
            "changed": sorted(changes),
            "added": [NOTE],
            "player_byte_identical": True,
            "mapping_files_unchanged": True,
            "production_published": False,
            "receiver_tested": False,
            "cold_target_met": False,
            "beta": True,
        }


if __name__ == "__main__":
    output = build(sys.argv[1] if len(sys.argv) > 1 else None)
    print("R801_BETA_BUILD", json.dumps(output, sort_keys=True))
