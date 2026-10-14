#!/usr/bin/env python3
"""IPToSatPro R76.11: local installer idempotency and package hook QA.

The real receiver installer is never executed. Only the guarded shell branch
is run against disposable fake plugin files. Reads staged IPK offline.
"""
import base64
import importlib.util
import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"download-r7611-beta.sh"
MODULE=ROOT/"scripts/build-r7611-preview-cold.py"
sp=importlib.util.spec_from_file_location("r7611_package_qa",MODULE)
builder=importlib.util.module_from_spec(sp);sp.loader.exec_module(builder)
VERSION=builder.VERSION


def guard_code():
    src=SCRIPT.read_text(encoding="utf8")
    begin=src.index("# R7611_ALREADY_INSTALLED_GUARD")
    end=src.index("# Avoid overwriting the only known-good R75 backup",begin)
    assert "mkdir -p \"$BACKUPROOT\"" not in src[:end]
    assert "opkg install" not in src[:end]
    assert src.index('if [ "$MODE" = "--check" ]; then')<begin
    return src[begin:end]


class IdempotentInstall(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory()
        self.plugin=Path(self.t.name)
    def tearDown(self):
        self.t.cleanup()

    def set_installed(self,version=VERSION,complete=True):
        (self.plugin/"plugin.py").write_text('PLUGIN_VERSION = "'+version+'"\n')
        (self.plugin/"core.py").write_text(
            "# R7611_NORMAL_PREVIEW_NO_COLD_DECORATED_SCAN\n"
            "# R7610_NORMAL48_FAST_BUDGET\n" if complete else "# incomplete\n")
        (self.plugin/"updater.py").write_text('CURRENT_VERSION = "'+version+'"\n')

    def run_guard(self):
        # Simulate JUST the guard. No network, filesystem backup or opkg.
        env={**os.environ,"PLUGIN":str(self.plugin),"VERSION":VERSION}
        return subprocess.run(
            ["sh","-c",'set -eu\n'+guard_code()+'\nprintf "NEXT_INSTALL_STEP\n"'],
            env=env,capture_output=True,text=True,timeout=5,check=False)

    def test_complete_r7611_is_successful_noop(self):
        self.set_installed()
        before={p.name:p.read_bytes() for p in self.plugin.iterdir()}
        v=self.run_guard()
        self.assertEqual(v.returncode,0,v.stderr)
        self.assertIn("ALREADY_INSTALLED:",v.stdout)
        self.assertIn("NO_OPKG_ACTION",v.stdout)
        self.assertNotIn("NEXT_INSTALL_STEP",v.stdout)
        self.assertEqual({p.name:p.read_bytes() for p in self.plugin.iterdir()},before)

    def test_inconsistent_r7611_refuses_reinstall(self):
        self.set_installed(complete=False)
        v=self.run_guard()
        self.assertEqual(v.returncode,7,v.stdout+v.stderr)
        self.assertIn("INSTALLED_R7611_INCONSISTENT",v.stdout)
        self.assertNotIn("NEXT_INSTALL_STEP",v.stdout)

    def test_r769_is_not_mistaken_for_installed_r7611(self):
        self.set_installed("1.0.46-r76.9-preview-manual-parity-beta")
        v=self.run_guard()
        self.assertEqual(v.returncode,0,v.stdout+v.stderr)
        self.assertIn("NEXT_INSTALL_STEP",v.stdout)
        self.assertNotIn("ALREADY_INSTALLED",v.stdout)

    def test_shell_and_pinned_payload(self):
        p=subprocess.run(["sh","-n",str(SCRIPT)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
        src=SCRIPT.read_text(encoding="utf8")
        self.assertIn('expected_sha="3c3f7b0e623808681884aef4f7975965b2eccdbc224cc4ba0b4393830a7d24d5"',src)
        self.assertIn("expected_size=459492",src)
        self.assertIn('if [ "$#" -eq 0 ]; then MODE="--check"',src)
        self.assertIn("MAPPING_BACKUP_FAILED",src)

    def test_staged_ipk_identity_and_hook_version(self):
        meta=json.loads((ROOT/"staging/r7611-preview-cold.update.json").read_text())
        raw=base64.b64decode((ROOT/"payload/r7611-preview-cold.b64").read_bytes())
        import hashlib
        self.assertEqual(hashlib.sha256(raw).hexdigest(),meta["sha256"])
        self.assertEqual(meta["version"],VERSION)
        ctr=builder.pack.members_from(builder.pack.unpack_ar(raw)["control.tar.gz"])
        ctrl=ctr["control"].decode("utf8")
        self.assertIn("Version: "+VERSION,ctrl)
        hooks={}
        for name in ("postinst","preinst","postrm","prerm"):
            if name in ctr:
                data=ctr[name].decode("utf8")
                hooks[name]={
                    "r62_string": bool(re.search(r"r62.*installed|installed.*r62",data,re.I)),
                    "hardcoded_r62": bool(re.search(r"1\.0\.46-r62",data)),
                    "size":len(data)
                }
        # Record hook origin, DO NOT assert that this legacy cosmetic problem
        # is fixed by existing installed IPK. That requires a future rebuild.
        print("R7611_CONTROL_HOOK_AUDIT",json.dumps(hooks,sort_keys=True))
        self.assertFalse(meta["production_published"])
        self.assertFalse(meta["receiver_tested"])


if __name__=="__main__":
    unittest.main()
