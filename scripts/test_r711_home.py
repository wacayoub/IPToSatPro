#!/usr/bin/env python3
"""R71.1 static Enigma2/XML safety checks for the real package build."""
import ast,base64,hashlib,importlib.util,tempfile,unittest
from pathlib import Path
sp=importlib.util.spec_from_file_location("home",Path(__file__).with_name("build-r711-neo-home.py"))
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)

class NeoHome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        cls.pkg=Path(cls.temp.name)/"candidate.ipk"
        cls.meta=b.build(cls.pkg)
        data=b.archive.members_from(b.archive.unpack_ar(cls.pkg.read_bytes())["data.tar.gz"])
        cls.plugin=data[b.PLUGIN].decode()
        cls.data=data
        cls.old=b.archive.members_from(b.archive.unpack_ar(base64.b64decode(b.B64.read_bytes()))["data.tar.gz"])

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_skin_1660_900_native_and_bound(self):
        names=b.inspect_skin(b.HOME_SKIN)
        self.assertGreaterEqual(len(names),25)
        self.assertIn('home_snr_bar',names)
        self.assertIn('home_status',names)
        self.assertIn('home_preview_action',names)
        self.assertIn('home_update_action',names)
        self.assertIn('home_sat_name',names)
        self.assertIn('home_selected_badges',names)
        self.assertNotIn('log_preview',names)
        self.assertNotIn('card_engine_value',names)
        self.assertNotIn('context_market',names)

    def test_every_real_data_value_has_a_source(self):
        s=self.plugin
        self.assertIn('snap.get("sat_snr")',s)
        self.assertIn('ProgressBar()',s)
        self.assertIn('self["home_snr_bar"].setValue(',s)
        self.assertIn('snap.get("catalog_count")',s)
        self.assertIn('snap.get("iptv_width")',s)
        self.assertIn('snap.get("iptv_height")',s)
        self.assertIn('snap.get("first_frame_ms")',s)
        self.assertIn('_load_overrides().get(sat_service_key(sat_ref))',s)
        self.assertIn('if sat_ref != self._r711_lock_ref or now-self._r711_lock_checked_at > 12:',s)
        self.assertIn('else "N/A"',s)
        self.assertIn('No active IPTV stream',s)

    def test_green_preview_yellow_update_blue_log_menu_settings(self):
        s=self.plugin
        self.assertIn('"green": self.open_preview_sources',s)
        self.assertIn('"yellow": self.open_updater',s)
        self.assertIn('"ok": self.open_preview_sources',s)
        self.assertIn('"blue": self.open_logs',s)
        self.assertIn('"menu": self.open_settings',s)
        self.assertIn('"4": self.open_all_sources',s)
        self.assertIn('"5": self.test_match',s)

    def test_no_player_or_preview_or_source_change(self):
        allow={b.PLUGIN,b.UPDATER}
        self.assertEqual(set(self.data),set(self.old)|{b.CHANGELOG})
        for f,old in self.old.items():
            if f not in allow:
                with self.subTest(file=f):
                    self.assertEqual(old,self.data[f])
        before=ast.parse(self.old[b.PLUGIN])
        after=ast.parse(self.plugin)
        def methods(tree):
            cl=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="SatIPTVBridgeDashboard")
            return {x.name:ast.dump(x,include_attributes=False) for x in cl.body if isinstance(x,ast.FunctionDef)}
        bm=methods(before);am=methods(after)
        self.assertEqual(set(bm),set(am))
        for method in bm:
            if method not in ("__init__","_refresh_monitor"):
                self.assertEqual(bm[method],am[method],method)
        self.assertFalse(self.meta["fast_zap_changed"])
        self.assertFalse(self.meta["preview_changed"])
        self.assertFalse(self.meta["receiver_tested"])

    def test_byte_reproducibility(self):
        again=Path(self.temp.name)/"candidate2.ipk"
        extra=b.build(again)
        self.assertEqual(self.pkg.read_bytes(),again.read_bytes())
        self.assertEqual(extra["sha256"],hashlib.sha256(again.read_bytes()).hexdigest())

if __name__=="__main__":unittest.main()
