"""Offline tests for the reversible R74 TOD/beIN AAC audio routing hotfix."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT=Path(__file__).with_name('r74_tod_bein_audio_hotfix.py')
spec=importlib.util.spec_from_file_location('tod_aac_hotfix',str(SCRIPT))
hotfix=importlib.util.module_from_spec(spec)
spec.loader.exec_module(hotfix)

FIXTURE='''class SatFallbackMonitor:
    @staticmethod
    def _audio_sensitive_stream(channel):
        try:
            raw = " ".join(str((channel or {}).get(k) or "") for k in ("name", "group", "source", "server_label")).casefold()
        except Exception:
            raw = ""
        return bool("tod" in raw and "event" in raw and "sport" in raw)

    def _audio_safe_serviceapp_required(self, channel):
        return self._audio_sensitive_stream(channel)
'''


class TODBeinAACRoutingTests(unittest.TestCase):
    def setUp(self):
        source, status=hotfix.patch(FIXTURE)
        self.assertEqual(status,'ready')
        env={}
        exec(compile(source,'fake_monitor.py','exec'),env)
        self.sensitive=env['SatFallbackMonitor']._audio_sensitive_stream
        self.patched=source

    def test_ar_bein_1_to_14(self):
        for number in range(1,15):
            self.assertTrue(self.sensitive({'name': 'AR BEIN SPORTS %d FHD (50 FPS)' % number}))

    def test_known_tod_event_unchanged(self):
        self.assertTrue(self.sensitive({'name':'TOD EVENT SPORTS 7 FHD'}))

    def test_tod_source_non_ar(self):
        self.assertTrue(self.sensitive({'name':'BEIN SPORTS 3 HD','server_label':'TOD Sports'}))

    def test_other_sources_unchanged(self):
        for name in ('TLC HD Austria','AR BEIN MOVIES 1 HD','Mezzo Live HD',
                     'BEIN SPORTS 3 HD','SW SPORT 1'):
            self.assertFalse(self.sensitive({'name':name}))

    def test_unrelated_tod_unchanged(self):
        self.assertFalse(self.sensitive({'name':'TOD Movies','server_label':'TOD'}))

    def test_negative_tod_name_not_source(self):
        self.assertFalse(self.sensitive({'name':'BEIN SPORTS 5 HD','server_label':'NOT A TOD CHANNEL'}))

    def test_extra_audio_guard_and_player_paths_unchanged(self):
        self.assertIn('def _audio_safe_serviceapp_required',self.patched)
        self.assertEqual(self.patched.count('def _audio_safe_serviceapp_required'),1)

    def test_idempotent(self):
        self.assertEqual(hotfix.patch(self.patched)[1],'already-installed')

    def test_wrong_source_aborts(self):
        with self.assertRaises(ValueError):
            hotfix.patch(FIXTURE.replace(hotfix.ANCHOR,'        return False'))

    def test_check_apply_rollback(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'monitor.py'
            path.write_text(FIXTURE)
            self.assertEqual(hotfix.main(['--check','--target',str(path)]),0)
            self.assertEqual(path.read_text(),FIXTURE)
            self.assertEqual(hotfix.main(['--apply','--target',str(path)]),0)
            self.assertIn(hotfix.TAG,path.read_text())
            self.assertEqual(hotfix.main(['--rollback','--target',str(path)]),0)
            self.assertEqual(path.read_text(),FIXTURE)


if __name__=='__main__':
    unittest.main()
