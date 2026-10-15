#!/usr/bin/env python3
"""Synthetic R80 installer safety: no receiver install, no files touched."""
import base64,hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
SCRIPT=R/"download-r801-preview-hotpath.sh"
VERSION="1.0.46-r80.1-preview-hotpath-beta"
SHA="210fe7de203353b71f02829f4f2b31acc582dfc663ce7bc8971425e0ecd2f173"

class PinnedR80Installer(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.dir=Path(self.t.name)
    def tearDown(self):
        self.t.cleanup()
    def emulate(self,version=VERSION,complete=True):
        (self.dir/"plugin.py").write_text('PLUGIN_VERSION = "'+version+'"\n')
        (self.dir/"core.py").write_text(
            "# R7615_NOMINATION_INDEX_ONLY\n"+
            ("# R80_PREVIEW_PURE_HOTPATH_V1\n# R7614_PREVIEW_PARSE_CACHE_IMMUTABLE\n# R7612_NORMAL_PREVIEW_PHASE_TIMINGS\n" if complete else ""))
        (self.dir/"updater.py").write_text('CURRENT_VERSION = "'+version+'"\n')
    def early_guard(self):
        script=SCRIPT.read_text()
        a=script.index("# R801_ALREADY_INSTALLED_GUARD")
        b=script.index("# Avoid overwriting",a)
        return subprocess.run(["sh","-c","set -eu\n"+script[a:b]+"\necho CONTINUE\n"],
            env={**os.environ,"PLUGIN":str(self.dir),"VERSION":VERSION},
            capture_output=True,text=True,timeout=5)
    def test_repeat_is_no_op(self):
        self.emulate()
        r=self.early_guard()
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("ALREADY_INSTALLED",r.stdout)
        self.assertNotIn("CONTINUE",r.stdout)
    def test_partial_r80_fails_closed(self):
        self.emulate(complete=False)
        r=self.early_guard()
        self.assertEqual(r.returncode,7)
        self.assertIn("INCONSISTENT",r.stdout)
    def test_original_r7615_can_upgrade(self):
        self.emulate("1.0.46-r76.15-preview-index-fast-beta")
        r=self.early_guard()
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn("CONTINUE",r.stdout)
    def test_no_destructive_default_and_known_version(self):
        content=SCRIPT.read_text()
        subprocess.run(["sh","-n",str(SCRIPT)],check=True)
        for marker in (
            'expected_sha="'+SHA+'"',"expected_size=461044",
            "BASE_VERSION_MISMATCH: installed R76.15 required",
            "MAPPING_BACKUP_FAILED","BACKUP_MAPPINGS",
            'if [ "$#" -eq 0 ]; then MODE="--check"',
            "sh /tmp/download-r801-preview-hotpath.sh --rollback",
            "NO_SETTINGS_OR_MAPPINGS_CHANGED",
            "R801_BETA_INSTALL_OK",
        ):
            self.assertIn(marker,content)
        self.assertIn('CONFIG="/etc/enigma2/SatIPTVBridge"',content)
        self.assertIn('SAVED="$BACKUPROOT/$STAMP"',content)
        self.assertNotIn("opkg install --force-downgrade",content)
    def test_staged_payload_signature_is_pinned(self):
        m=json.loads((R/"staging/r801-preview-hotpath.update.json").read_text())
        raw=base64.b64decode((R/"payload/r801-preview-hotpath.b64").read_bytes())
        self.assertEqual(len(raw),461044)
        self.assertEqual(m["sha256"],SHA)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),SHA)
        self.assertEqual(m["version"],VERSION)
        self.assertEqual(m["source_receiver_version"],"1.0.46-r76.15-preview-index-fast-beta")
        self.assertTrue(m["beta"])
        self.assertFalse(m["cold_target_met"])
        self.assertTrue(m["installation_requires_explicit_flag"])
        self.assertEqual(m["parts"],[
            "https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r80-preview-hotpath-20261015/payload/r801-preview-hotpath.b64"])
        self.assertFalse(m["production_published"])
        self.assertFalse(m["receiver_tested"])


if __name__=="__main__":
    unittest.main()
