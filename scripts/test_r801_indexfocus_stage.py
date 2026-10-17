#!/usr/bin/env python3
"""Offline tests for R80.0 source-preserving Index Focus candidate builder."""
import base64
import hashlib
import importlib.util
import io
import tarfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
spec = importlib.util.spec_from_file_location(
    "stage_indexfocus_test_only", HERE / "stage_r801_indexfocus_readonly.py")
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)

class PackagingSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = b"".join((ROOT / "payload/r801-preview-hotpath.b64").read_bytes().split())
        cls.ipk = base64.b64decode(data, validate=True)
        cls.blocks, cls.order = stage.ar_unpack(cls.ipk)
        cls.members, cls.body = stage.tar_read(cls.blocks["data.tar.gz"][1])
        cls.controls, cls.control_data = stage.tar_read(cls.blocks["control.tar.gz"][1])

    def test_pinned_candidate_blob(self):
        self.assertEqual(len(self.ipk),461044)
        self.assertEqual(stage.sha(self.ipk),stage.CANDIDATE_SHA)
        self.assertEqual(set(self.blocks),{"debian-binary","control.tar.gz","data.tar.gz"})

    def test_ar_roundtrip_preserves_all_payloads(self):
        rebuilt = stage.ar_pack(self.blocks,self.order)
        pieces, order = stage.ar_unpack(rebuilt)
        self.assertEqual(order,self.order)
        for key in order:
            self.assertEqual(pieces[key][1],self.blocks[key][1])

    def test_tar_roundtrip_data(self):
        raw = stage.tar_pack(self.members,self.body,{})
        converted, rebuilt = stage.tar_read(raw)
        self.assertEqual([x.name for x in converted],[x.name for x in self.members])
        self.assertEqual(rebuilt,self.body)

    def test_tar_roundtrip_control(self):
        raw = stage.tar_pack(self.controls,self.control_data,{})
        converted, rebuilt = stage.tar_read(raw)
        self.assertEqual([x.name for x in converted],[x.name for x in self.controls])
        self.assertEqual(rebuilt,self.control_data)

    def test_no_packaged_config_or_install_scripts(self):
        datafiles = [stage.normalized_name(m.name) for m in self.members if m.isfile()]
        self.assertEqual(len(datafiles),87)
        self.assertTrue(all(x.startswith(stage.PFX) for x in datafiles))
        controlfiles = {stage.normalized_name(m.name) for m in self.controls if m.isfile()}
        self.assertNotIn("preinst",controlfiles)
        self.assertNotIn("prerm",controlfiles)
        self.assertNotIn("postrm",controlfiles)
        self.assertIn("postinst",controlfiles)

    def test_version_rewrite_changes_only_single_assignment(self):
        before = ('PLUGIN_VERSION = "'+stage.OLD+'"\n').encode("utf8")
        after = stage.new_version(before,"PLUGIN_VERSION")
        self.assertEqual(after,('PLUGIN_VERSION = "'+stage.NEW+'"\n').encode("utf8"))
        with self.assertRaises(ValueError):
            stage.new_version(before + before,"PLUGIN_VERSION")

    def test_version_and_installer_guard(self):
        self.assertNotEqual(stage.NEW,stage.CANDIDATE_VERSION)
        self.assertTrue(stage.DEST.as_posix().startswith("/tmp/"))
        self.assertNotIn("opkg",stage.POSTINST.decode())
        self.assertNotIn("rm ",stage.POSTINST.decode())
        self.assertNotIn("mv ",stage.POSTINST.decode())

if __name__ == "__main__":
    unittest.main()
