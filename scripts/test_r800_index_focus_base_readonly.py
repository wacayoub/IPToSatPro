#!/usr/bin/env python3
"""Offline strict R80.0 compatibility audit tests: no receiver access or network."""
import importlib.util
import io
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "r800_strict_audit", ROOT / "scripts/audit_r800_index_focus_base_readonly.py")
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

RC1 = "1.0.46-r80-final-rc1"
R800 = "1.0.46-r80.0-rc1-index-focus"
REF_MANIFEST = "https://raw.githubusercontent.com/wacayoub/IPToSatPro/release/r80-final-candidate-20261015/staging/r80-final-rc1.update.json"
R800_MANIFEST = "https://raw.githubusercontent.com/wacayoub/IPToSatPro/release/experimental-index-focus/staging/r800-index-focus.update.json"

class StrictParityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.reference = {
            "core.py": b"R7615_NOMINATION_INDEX_ONLY\nORIGINAL\n",
            "plugin.py": ('PLUGIN_VERSION = "' + RC1 + '"\nplugin_runtime=1\n').encode(),
            "updater.py": ('CURRENT_VERSION = "' + RC1 + '"\nurl="' +
                           REF_MANIFEST + '"\nupdater_runtime=1\n').encode(),
            "util/helper.py": b"helper=True\n",
        }
        for name,data in self.reference.items():
            path=self.root/name
            path.parent.mkdir(parents=True,exist_ok=True)
            if name=="plugin.py":
                data=data.replace(RC1.encode(),R800.encode())
            elif name=="updater.py":
                data=data.replace(RC1.encode(),R800.encode()).replace(
                    REF_MANIFEST.encode(), R800_MANIFEST.encode())
            path.write_bytes(data)
    def tearDown(self):
        self.temp.cleanup()

    def check(self):
        return audit.compatible_runtime(self.root,self.reference,R800)

    def test_safe_version_and_manifest_only_parity(self):
        ok,reason,count=self.check()
        self.assertTrue(ok,(reason,count))
        self.assertEqual(reason,"STRICT_CODE_PARITY")
        self.assertEqual(count,len(self.reference))

    def test_core_optimization_or_accidental_edit_blocks(self):
        (self.root/"core.py").write_bytes(b"R80_INDEX_FOCUS_DIFFERENT\n")
        self.assertFalse(self.check()[0])
        self.assertIn("core.py",self.check()[1])

    def test_unexpected_extra_python_module_blocks(self):
        (self.root/"custom_plugin.py").write_text("custom=True\n")
        self.assertEqual(self.check()[1],"PYTHON_FILE_SET_DIFFERS")

    def test_missing_python_module_blocks(self):
        (self.root/"util/helper.py").unlink()
        self.assertEqual(self.check()[1],"PYTHON_FILE_SET_DIFFERS")

    def test_changed_plugin_logic_blocks(self):
        with (self.root/"plugin.py").open("ab") as f:
            f.write(b"\nextra=1\n")
        self.assertEqual(self.check()[1],"PYTHON_CONTENT_DIFFERS:plugin.py")

    def test_changed_updater_logic_blocks(self):
        with (self.root/"updater.py").open("ab") as f:
            f.write(b"\nextra=1\n")
        self.assertEqual(self.check()[1],"PYTHON_CONTENT_DIFFERS:updater.py")

    def test_unknown_version_blocks(self):
        self.assertEqual(audit.compatible_runtime(self.root,self.reference,"R75")[1],
                         "UNSUPPORTED_VERSION")

    def test_reference_tar_memory_extraction(self):
        with io.BytesIO() as buf:
            with tarfile.open(fileobj=buf,mode="w:gz") as tf:
                for name,raw in self.reference.items():
                    info=tarfile.TarInfo(name="./"+audit.PACKAGE_ROOT+name)
                    info.size=len(raw)
                    tf.addfile(info,io.BytesIO(raw))
            gz=buf.getvalue()
        def member(name,data):
            hdr=(name.encode().ljust(16,b" ") +
                 b"0".ljust(12,b" ") +
                 b"0".ljust(6,b" ") +
                 b"0".ljust(6,b" ") +
                 b"100644".ljust(8,b" ") +
                 str(len(data)).encode().ljust(10,b" ") +
                 b"\x60\x0a")
            self.assertEqual(len(hdr),60)
            return hdr+data+(b"\n" if len(data)%2 else b"")
        ipk=b"!<arch>\n"+member("data.tar.gz/",gz)
        self.assertEqual(audit.reference_code(ipk),self.reference)

if __name__=="__main__":
    unittest.main()
