#!/usr/bin/env python3
"""R80 promotion gate: run against exact R76.15 reference and staged R80 RC1.

No network/receiver/credentials; byte-parity and non-destructive package tests.
"""
import hashlib,importlib.util,tempfile,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]

def load(name,file):
    sp=importlib.util.spec_from_file_location(name,R/"scripts"/file)
    obj=importlib.util.module_from_spec(sp);sp.loader.exec_module(obj)
    return obj

before=load("r7615ref80","build-r7615-preview-index.py")
r80=load("r80rc1","build-r80-final-rc1.py")


class FinalCandidate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        d=Path(cls.tmp.name)
        p=d/"before.ipk";q=d/"r80.ipk"
        cls.bmeta=before.build(p)
        cls.rmeta=r80.build(q)
        cls.bdata=before.pack.members_from(before.pack.unpack_ar(p.read_bytes())["data.tar.gz"])
        cls.rdata=before.pack.members_from(before.pack.unpack_ar(q.read_bytes())["data.tar.gz"])
        cls.bctrl=before.pack.members_from(before.pack.unpack_ar(p.read_bytes())["control.tar.gz"])
        cls.rctrl=before.pack.members_from(before.pack.unpack_ar(q.read_bytes())["control.tar.gz"])
    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_reference_exact(self):
        self.assertEqual(self.bmeta["sha256"],r80.BASE_SHA)
        self.assertEqual(self.rmeta["source_sha256"],r80.BASE_SHA)
        self.assertEqual(self.rmeta["version"],"1.0.46-r80-final-rc1")
        self.assertFalse(self.rmeta["receiver_tested"])
        self.assertFalse(self.rmeta["index_target_met"])
        self.assertFalse(self.rmeta["production_published"])

    def test_all_executable_engine_and_player_bytes_identical(self):
        self.assertEqual(set(self.rmeta["changed"]),{r80.PLUGIN,r80.UPDATER})
        for file,value in self.bdata.items():
            if file not in (r80.PLUGIN,r80.UPDATER):
                self.assertEqual(self.rdata[file],value,file)
        self.assertEqual(self.rdata[r80.CORE],self.bdata[r80.CORE])
        # Verify only one exact version substitution in user interface.
        old=self.bdata[r80.PLUGIN].decode("utf8")
        new=self.rdata[r80.PLUGIN].decode("utf8")
        self.assertEqual(new,old.replace(
            'PLUGIN_VERSION = "'+r80.OLD+'"',
            'PLUGIN_VERSION = "'+r80.VERSION+'"',1))

    def test_manual_mapping_and_source_state_files_unaffected(self):
        for file in self.bdata:
            name=file.lower()
            if ("mapping" in name or "override" in name or "catalog" in name or
                "cache" in name or "player" in name or "serviceapp" in name or
                "theme" in name or "skin" in name):
                self.assertEqual(self.rdata[file],self.bdata[file],file)

    def test_postinst_never_migrates_or_deletes_user_files(self):
        script=self.rctrl["postinst"].decode("utf8")
        self.assertIn("R80 release candidate installed",script)
        for word in ("rm ","mv ","chmod ","chown ","python3 ","opkg ","import_spec",
                     "cache_migrator","wget ","curl "):
            self.assertNotIn(word,script)
        self.assertFalse({"preinst","prerm","postrm"}.intersection(self.rctrl))
        self.assertNotIn("R76.15 Preview index beta installed",script)

    def test_package_name_and_updater_manifest_consistent(self):
        self.assertIn("Version: "+r80.VERSION,
                      self.rctrl["control"].decode("utf8"))
        upd=self.rdata[r80.UPDATER].decode("utf8")
        self.assertIn(r80.MANIFEST,upd)
        self.assertIn('CURRENT_VERSION = "'+r80.VERSION+'"',upd)
        self.assertIn("R80-RELEASE-CANDIDATE.md","\n".join(self.rdata))


if __name__=="__main__":
    unittest.main()
