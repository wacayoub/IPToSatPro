#!/usr/bin/env python3
"""R76.15 hashed installer verification — no actual receiver operation."""
import base64,hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
SCRIPT=R/"download-r7615-index-beta.sh"
VERSION="1.0.46-r76.15-preview-index-fast-beta"
SHA="c3991af773c6700c1aac0652f5027b27b4e1a91ff0820bf25e801e8d8488c468"

class Installer(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory()
  self.root=Path(self.t.name)
 def tearDown(self):
  self.t.cleanup()
 def fake(self,version,consistent=True):
  (self.root/"plugin.py").write_text('PLUGIN_VERSION = "'+version+'"\n')
  (self.root/"core.py").write_text(
   "# R7614_PREVIEW_PARSE_CACHE_IMMUTABLE\n"
   "# R7613_PREVIEW_SCORING_POSTINGS\n"
   "# R7612_NORMAL_PREVIEW_PHASE_TIMINGS\n"+
   ("# R7615_NOMINATION_INDEX_ONLY\n" if consistent else ""))
  (self.root/"updater.py").write_text('CURRENT_VERSION = "'+version+'"\n')
 def check_guard(self):
  source=SCRIPT.read_text()
  start=source.index("# R7615_ALREADY_INSTALLED_GUARD")
  end=source.index("# Avoid overwriting",start)
  return subprocess.run(["sh","-c","set -eu\n"+source[start:end]+"\necho CONTINUE\n"],
   env={**os.environ,"PLUGIN":str(self.root),"VERSION":VERSION},
   text=True,capture_output=True,timeout=6)
 def test_complete_install_is_noop(self):
  self.fake(VERSION)
  r=self.check_guard()
  self.assertEqual(r.returncode,0,r.stderr)
  self.assertIn("ALREADY_INSTALLED",r.stdout)
  self.assertNotIn("CONTINUE",r.stdout)
 def test_partial_install_rejected_before_opkg(self):
  self.fake(VERSION,consistent=False)
  r=self.check_guard()
  self.assertEqual(r.returncode,7)
  self.assertIn("INCONSISTENT",r.stdout)
 def test_old_version_is_eligible_for_next_guard(self):
  self.fake("1.0.46-r76.14-preview-parsecache-beta")
  r=self.check_guard()
  self.assertEqual(r.returncode,0,r.stderr)
  self.assertIn("CONTINUE",r.stdout)
 def test_shell_pin_backup_rollback(self):
  s=SCRIPT.read_text()
  subprocess.run(["sh","-n",str(SCRIPT)],capture_output=True,check=True)
  for phrase in (
   'expected_sha="'+SHA+'"',
   "expected_size=460202",
   "BASE_VERSION_MISMATCH: installed R76.14 required",
   'if [ "$#" -eq 0 ]; then MODE="--check"',
   "MAPPING_BACKUP_FAILED","BACKUP_MAPPINGS",
   "sh /tmp/download-r7615-index-beta.sh --rollback"):
   self.assertIn(phrase,s)
 def test_staged_manifest_payload(self):
  m=json.loads((R/"staging/r7615-preview-index.update.json").read_text())
  raw=base64.b64decode((R/"payload/r7615-preview-index.b64").read_bytes())
  self.assertEqual(len(raw),460202)
  self.assertEqual(hashlib.sha256(raw).hexdigest(),SHA)
  self.assertEqual(m["sha256"],SHA)
  self.assertEqual(m["version"],VERSION)
  self.assertFalse(m["receiver_tested"])
  self.assertFalse(m["production_published"])
  self.assertTrue(m["installation_requires_explicit_flag"])

if __name__=="__main__":
 unittest.main()
