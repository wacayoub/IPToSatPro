#!/usr/bin/env python3
"""R71 UI static+package CI. No Enigma2 receiver, no IPTV network calls."""
import ast
import base64
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

script=Path(__file__).with_name("build-r71-ui-beta.py")
spec=importlib.util.spec_from_file_location("ui_build",script)
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class UIBetaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t=tempfile.TemporaryDirectory()
        cls.out=Path(cls.t.name)/"ui.ipk"
        cls.meta=b.build(cls.out)
        cls.after=b.base.members_from(b.base.unpack_ar(cls.out.read_bytes())["data.tar.gz"])
        cls.before=b.base.members_from(b.base.unpack_ar(
            base64.b64decode(b.B64.read_bytes()))["data.tar.gz"])
        cls.text=cls.after[b.PATH].decode()

    @classmethod
    def tearDownClass(cls):
        cls.t.cleanup()

    def test_bounded_all_servers(self):
        s=self.text
        for x in ('MAX_BROWSER_CANDIDATES = 48','FAST_PER_SERVER = 16',
                  'candidate_budget = 72 if self._r71_worker_deep else self.MAX_BROWSER_CANDIDATES',
                  'candidate_per_server = 24 if self._r71_worker_deep else self.FAST_PER_SERVER',
                  'ranked = catalog.fast_rank_matches_all_servers(',
                  'self._r71_deep_target_ref = raw'):
            self.assertIn(x,s)
        # no background remote network probes in preview worker.
        start=s.index('        def worker():\n',s.index('    def _expand_selected_sat_candidates(self):'))
        end=s.index('        th = threading.Thread',start)
        worker=s[start:end]
        self.assertNotIn('requests.',worker)
        self.assertNotIn('urlopen(',worker)
        self.assertNotIn('session.nav',worker)

    def test_home_and_preview_buttons(self):
        s=self.text
        self.assertIn('"green": self.open_preview_sources',s)
        self.assertIn('"4": self.open_all_sources',s)
        self.assertIn('def open_preview_sources(self):',s)
        self.assertIn('_open_preview_sources_direct(self.session)',s)
        self.assertIn('"yellow": self._all_sources',s)
        self.assertIn('"4": self._open_legacy_all_sources',s)
        self.assertIn('def _open_legacy_all_sources(self):',s)
        start=s.index('    def _all_sources(self):')
        end=s.index('    def _open_legacy_all_sources(self):',start)
        self.assertNotIn('self.close(',s[start:end])
        self.assertIn('self.candidate_expand_timer.start(10, True)',s[start:end])
        self.assertIn('GREEN Preview All',s)

    def test_all_unapproved_runtime_unchanged(self):
        allow={b.PATH,b.base.PREFIX+'updater.py'}
        self.assertEqual(set(self.after),set(self.before)|{b.CHANGELOG})
        for p,raw in self.before.items():
            if p not in allow:
                self.assertEqual(raw,self.after[p],p)
        self.assertNotIn('tod_dynamic', '\n'.join(self.after).lower())

    def test_reproducible_and_main_manifest_not_changed(self):
        again=Path(self.t.name)/"again.ipk"
        meta=b.build(again)
        self.assertEqual(meta['sha256'],self.meta['sha256'])
        self.assertEqual(self.out.read_bytes(),again.read_bytes())
        self.assertEqual(meta['sha256'],hashlib.sha256(self.out.read_bytes()).hexdigest())
        self.assertEqual(json.loads((b.ROOT/'update.json').read_text())['version'],'1.0.46-r70-final')
        self.assertFalse(meta['production_published'])
        self.assertTrue(meta['todo_hardware_test'])

if __name__=='__main__':
    unittest.main()
