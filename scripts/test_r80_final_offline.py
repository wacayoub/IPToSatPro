#!/usr/bin/env python3
"""R80 final packaging smoke tests with synthetic IPKs, no receiver files."""
import io
import tarfile
import unittest
from pathlib import Path

from prepare_r80_final_offline import (EXTERNAL, FINAL, OLD, PREFIX,
     digest, get_ar, pack_ar, transform, unpack_tar)


def bundle(files):
    from gzip import GzipFile
    data=io.BytesIO()
    with GzipFile(fileobj=data,mode='wb',mtime=0) as z:
        with tarfile.open(fileobj=z,mode='w',format=tarfile.GNU_FORMAT) as tar:
            for name,payload in files.items():
                ent=tarfile.TarInfo(name)
                ent.size=len(payload)
                ent.mode=0o644
                tar.addfile(ent,io.BytesIO(payload))
    return data.getvalue()


def fake_header(name, contents):
    h=bytearray(b' '*60)
    h[:len(name)]=name.encode()
    h[48:58]=str(len(contents)).encode().ljust(10)
    h[58:60]=b'\x60\n'
    return bytes(h)


def synthetic(extra_files=None,postinst=None,updater_url='https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r80-preview-hotpath-20261015/staging/r801-preview-hotpath.update.json'):
    core=b'\nprint(123)\n'
    plug=('PLUGIN_VERSION = "'+OLD+'"\n').encode()
    updater=('CURRENT_VERSION = "'+OLD+'"\nMANIFEST_URL = "'+updater_url+'"\n').encode()
    data={PREFIX+'core.py':core,PREFIX+'plugin.py':plug,PREFIX+'updater.py':updater}
    data.update({PREFIX+'asset%02d.dat'%i:b'stable' for i in range(84)})
    data.update({x:b'#!/bin/sh\nexit 0\n' for x in EXTERNAL})
    data.update(extra_files or {})
    ctl={'control':('Package: enigma2-plugin-extensions-satiptvbridge\nVersion: '+OLD+'\n').encode(),
         'postinst':postinst or b"#!/bin/sh\nprintf '%s\\n' 'IPToSatPro Index Focus Preview hot-path RC staged; restart GUI manually.'\nexit 0\n"}
    parts={'debian-binary':b'2.0\n','control.tar.gz':bundle(ctl),'data.tar.gz':bundle(data)}
    entries={n:(fake_header(n+'/',b),b) for n,b in parts.items()}
    raw=pack_ar(entries,list(parts))
    return raw,core


def run_fixture(raw,core):
    return transform(raw,expected_size=len(raw),expected_sha=digest(raw),
                     expected_core=digest(core))


class FinalOfflineTests(unittest.TestCase):
    def test_identity_and_metadata_only(self):
        raw,core=synthetic()
        result,summary=run_fixture(raw,core)
        self.assertTrue(summary['unchanged_operational_payload'])
        self.assertEqual(summary['final_version'],FINAL)
        self.assertFalse(summary['published'])
        entry,_=get_ar(result)
        _,files=unpack_tar(entry['data.tar.gz'][1])
        self.assertEqual(files[PREFIX+'core.py'],core)
        self.assertIn(FINAL.encode(),files[PREFIX+'plugin.py'])
        self.assertIn(b'/main/update.json',files[PREFIX+'updater.py'])
        self.assertNotIn(OLD.encode(),files[PREFIX+'updater.py'])
        for ext in EXTERNAL:
            self.assertEqual(files[ext],b'#!/bin/sh\nexit 0\n')
        ctr=unpack_tar(entry['control.tar.gz'][1])[1]
        self.assertIn(('Version: '+FINAL).encode(),ctr['control'])
        self.assertIn(b'Index Focus Preview hot-path RC staged',ctr['postinst'])

    def test_real_pinned_size_sha_required(self):
        raw,core=synthetic()
        with self.assertRaisesRegex(ValueError,'TESTED_INPUT_PACKAGE_MISSING_OR_SHA_MISMATCH'):
            transform(raw)

    def test_core_immutable_guard(self):
        raw,core=synthetic()
        with self.assertRaisesRegex(ValueError,'CORE_NOT_EXACT_HARDWARE_VALIDATED_CODE'):
            transform(raw,len(raw),digest(raw),'0'*64)

    def test_unexpected_system_file_blocks(self):
        raw,core=synthetic({'etc/cron.d/unknown':b'hello'})
        with self.assertRaisesRegex(ValueError,'OUTSIDE_FILES_NOT_EXPECTED'):
            run_fixture(raw,core)

    def test_duplicate_updater_urls_block(self):
        raw,core=synthetic(updater_url='https://raw.githubusercontent.com/wacayoub/IPToSatPro/main/update.json'+' ; https://raw.githubusercontent.com/wacayoub/IPToSatPro/feature/r80/staging/x.json')
        with self.assertRaisesRegex(ValueError,'UPDATER_SOURCE_URL_AMBIGUOUS'):
            run_fixture(raw,core)

    def test_unrecognized_postinst_blocks(self):
        raw,core=synthetic(postinst=b'#!/bin/sh\nrm -rf /etc/enigma2\nexit 0\n')
        with self.assertRaisesRegex(ValueError,'UNEXPECTED_POSTINST'):
            run_fixture(raw,core)

    def test_deterministic_output(self):
        raw,core=synthetic()
        a,_=run_fixture(raw,core)
        b,_=run_fixture(raw,core)
        self.assertEqual(a,b)


if __name__=='__main__':
    unittest.main(verbosity=2)
