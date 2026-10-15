#!/usr/bin/env python3
"""R76.14 installer safety gate: synthetic no-op only, never install."""
import base64
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

R=Path(__file__).resolve().parents[1]
SCRIPT=R/"download-r7614-cache-beta.sh"
VERS="1.0.46-r76.14-preview-parsecache-beta"
SHA="0445acb6790adc81b51f4d2605fc80bdc15942b2ec7204389bebb8c3fd23c0d2"


class R7614InstallerSafety(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory()
  self.plugin=Path(self.tmp.name)
 def tearDown(self):
  self.tmp.cleanup()
 def source(self):
  return SCRIPT.read_text(encoding="utf8")
 def configure(self,version=VERS,complete=True):
  (self.plugin/"plugin.py").write_text(
    'PLUGIN_VERSION = "'+version+'"\n'+
    ("# R7612_PREVIEW_STAGE_NUMERIC_ONLY\n" if complete else ""))
  (self.plugin/"core.py").write_text("# R7612_NORMAL_PREVIEW_PHASE_TIMINGS\n"+
    ("# R7614_PREVIEW_PARSE_CACHE_IMMUTABLE\n# R7613_PREVIEW_SCORING_POSTINGS\n" if complete else ""))
  (self.plugin/"updater.py").write_text('CURRENT_VERSION = "'+version+'"\n')
 def guard(self):
  s=self.source()
  a=s.index("# R7614_ALREADY_INSTALLED_GUARD")
  b=s.index("# Avoid overwriting the only known-good R75 backup",a)
  test=s[a:b]
  env={**os.environ,"PLUGIN":str(self.plugin),"VERSION":VERS}
  return subprocess.run(["sh","-c",'set -eu\n'+test+'\necho CONTINUE\n'],
    capture_output=True,text=True,env=env,timeout=5)
 def test_complete_already_installed_is_noop(self):
  self.configure()
  result=self.guard()
  self.assertEqual(result.returncode,0,result.stderr)
  self.assertIn("ALREADY_INSTALLED",result.stdout)
  self.assertNotIn("CONTINUE",result.stdout)
 def test_inconsistent_installed_r7614_is_refused(self):
  self.configure(complete=False)
  result=self.guard()
  self.assertEqual(result.returncode,7)
  self.assertIn("INCONSISTENT",result.stdout)
 def test_r7613_passes_only_already_installed_guard(self):
  self.configure(version="1.0.46-r76.13-preview-cpu-fast-beta")
  result=self.guard()
  self.assertEqual(result.returncode,0)
  self.assertIn("CONTINUE",result.stdout)
 def test_checks_include_explicit_base_and_pin(self):
  s=self.source()
  subprocess.run(["sh","-n",str(SCRIPT)],check=True,capture_output=True)
  self.assertIn('expected_sha="'+SHA+'"',s)
  self.assertIn("expected_size=459734",s)
  self.assertIn('installed R76.13 required for R76.14',s)
  self.assertIn('if [ "$#" -eq 0 ]; then MODE="--check"',s)
  self.assertIn('sh /tmp/download-r7614-cache-beta.sh --rollback',s)
  self.assertIn("BACKUP_MAPPINGS",s)
  self.assertIn("MAPPING_BACKUP_FAILED",s)
  self.assertNotIn("opkg install --force-reinstall",s[:s.index('if [ "$MODE" = "--check" ]; then')])
 def test_exact_staged_payload_matches_manifest(self):
  manifest=json.loads((R/"staging/r7614-preview-cache.update.json").read_text())
  raw=base64.b64decode((R/"payload/r7614-preview-cache.b64").read_bytes())
  self.assertEqual(manifest["size"],len(raw))
  self.assertEqual(hashlib.sha256(raw).hexdigest(),SHA)
  self.assertEqual(manifest["sha256"],SHA)
  self.assertEqual(manifest["version"],VERS)
  self.assertFalse(manifest["production_published"])
  self.assertFalse(manifest["receiver_tested"])


if __name__=="__main__":
 unittest.main()
