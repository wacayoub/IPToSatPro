#!/usr/bin/env python3
"""R80 RC1 protected installer: no-op reinstall, version pin, mappings/rollback."""
import base64,hashlib,json,os,subprocess,tempfile,unittest
from pathlib import Path
R=Path(__file__).resolve().parents[1]
SH=R/"download-r80-rc1.sh"
V="1.0.46-r80.0-rc1-index-focus"
SHA="ca1b00ec0f1e93f523c244281451efcc78257c328a59786e6b60b0cdac1695da"

class R80SafeInstall(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory()
  self.p=Path(self.t.name)
 def tearDown(self):
  self.t.cleanup()
 def setversion(self,v,complete=True):
  (self.p/"plugin.py").write_text('PLUGIN_VERSION = "'+v+'"\n')
  (self.p/"updater.py").write_text('CURRENT_VERSION = "'+v+'"\n')
  (self.p/"core.py").write_text(
   "# R7615_NOMINATION_INDEX_ONLY\n# R7614_PREVIEW_PARSE_CACHE_IMMUTABLE\n"
   "# R7612_NORMAL_PREVIEW_PHASE_TIMINGS\n"+
   ("# R80_INDEX_LAZY_GUARDS\n" if complete else ""))
 def excerpt(self):
  src=SH.read_text()
  a=src.index("# R80RC1_ALREADY_INSTALLED_GUARD")
  z=src.index("# Avoid overwriting",a)
  return src[a:z]
 def run_guard(self):
  cmd="set -eu\n"+self.excerpt()+"\necho CONTINUE\n"
  return subprocess.run(["sh","-c",cmd],text=True,capture_output=True,timeout=5,
   env={**os.environ,"PLUGIN":str(self.p),"VERSION":V})
 def test_existing_complete_rc1_is_noop(self):
  self.setversion(V)
  r=self.run_guard()
  self.assertEqual(r.returncode,0,r.stderr)
  self.assertIn("ALREADY_INSTALLED",r.stdout)
  self.assertNotIn("CONTINUE",r.stdout)
 def test_partial_rc1_cannot_be_overwritten(self):
  self.setversion(V,False)
  r=self.run_guard()
  self.assertEqual(r.returncode,7)
  self.assertIn("INCONSISTENT",r.stdout)
 def test_previous_r7615_passes_idempotence_guard(self):
  self.setversion("1.0.46-r76.15-preview-index-fast-beta")
  r=self.run_guard()
  self.assertEqual(r.returncode,0,r.stderr)
  self.assertIn("CONTINUE",r.stdout)
 def test_pinned_sha_and_explicit_backup_rollback(self):
  s=SH.read_text()
  subprocess.run(["sh","-n",str(SH)],check=True,capture_output=True)
  for item in ("expected_sha="+chr(34)+SHA+chr(34),"expected_size=460442",
   "BASE_VERSION_MISMATCH: installed R76.15 required for R80 RC1",
   "MAPPING_BACKUP_FAILED","BACKUP_MAPPINGS","PERSISTENT_BACKUP",
   "sh /tmp/download-r80-rc1.sh --rollback",
   'if [ "$#" -eq 0 ]; then MODE="--check"'):
   self.assertIn(item,s)
  self.assertNotIn("opkg install --force-reinstall",s[:s.index('if [ "$MODE" = "--check" ]; then')])
 def test_manifest_and_payload_match(self):
  m=json.loads((R/"staging/r80-rc1-index-focus.update.json").read_text())
  raw=base64.b64decode((R/"payload/r80-rc1-index-focus.b64").read_bytes())
  self.assertEqual(m["size"],len(raw))
  self.assertEqual(m["sha256"],hashlib.sha256(raw).hexdigest())
  self.assertEqual(m["sha256"],SHA)
  self.assertEqual(m["version"],V)
  self.assertTrue(m["installation_requires_explicit_flag"])
  self.assertFalse(m["production_published"])
  self.assertFalse(m["receiver_tested"])

if __name__=="__main__":unittest.main()
