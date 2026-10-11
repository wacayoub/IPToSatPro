#!/usr/bin/env python3
"""R72.3 split layouts, original menu, icon art, strict core runtime invariance."""
import ast,base64,hashlib,importlib.util,io,tempfile,unittest,xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
sp=importlib.util.spec_from_file_location("fusion",Path(__file__).with_name("build-r723-classic-fusion.py"))
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)

class FusionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.tmp.name)/"r723.ipk"
        cls.result=b.build(cls.path)
        cls.after=b.pack.members_from(b.pack.unpack_ar(cls.path.read_bytes())["data.tar.gz"])
        cls.before=b.pack.members_from(b.pack.unpack_ar(base64.b64decode(b.B64.read_bytes()))["data.tar.gz"])
        cls.code=cls.after[b.PLUGIN].decode()
        cls.tree=ast.parse(cls.code)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_old_home_is_default_and_modern_alternate(self):
        self.assertIn('self._r723_layout = "classic"',self.code)
        self.assertIn('if self._r723_layout == "monitor":',self.code)
        self.assertIn('self.skin = _theme_skin(R723_CLASSIC_FHD.replace(',self.code)
        self.assertIn('self.skin = _theme_skin(DASHBOARD_FHD.replace(',self.code)
        self.assertIn('Appearance  •  Home layout',self.code)
        self.assertIn('def _r723_select_home_layout(self):',self.code)
        self.assertIn('def _r723_set_home_layout(self, item):',self.code)
        self.assertIn('os.rename(tmp_path,path)',self.code)
        self.assertIn('with open(self._r723_home_pref_path, "r") as reader:',self.code)
        self.assertIn('"menu": self.open_settings',self.code)

    def test_original_r711_layout_and_new_icons(self):
        classic=b.classic_skin()
        root=ET.fromstring(classic)
        keys={x.get("name") for x in root if x.tag=="widget"}
        for name in ("home_sat_name","home_snr_bar","home_iptv_status","home_selected_name",
                     "home_quality_chip","home_audio_chip","home_role_chip","home_speed_chip",
                     "home_preview_action","home_update_action","home_lock_badge"):
            self.assertIn(name,keys)
        for forbidden in ("r72_sat_name","r72_iptv_name","r72_audio_codec_val"):
            self.assertNotIn(forbidden,keys)
        png=self.after[b.ICON]
        with Image.open(io.BytesIO(png)) as image:
            self.assertEqual(image.size,(1660,900))
            self.assertEqual(image.mode,"RGBA")
            self.assertGreaterEqual(len(set(image.crop((77,158,122,198)).getdata())),5)
            self.assertGreaterEqual(len(set(image.crop((860,343,910,386)).getdata())),5)

    def test_truthful_current_sat_and_iptv_details_in_classic_mode(self):
        for literal in ('self["home_iptv_status"].setText(', 'if live else ("IPTV CATALOG READY"',
                        'self["home_selected_name"].setText(', 'self["home_lock_badge"].setText("LOCKED"',
                        'self["home_quality_chip"].setText(iptv_badge',
                        'self["home_audio_chip"].setText(', 'self["home_role_chip"].setText(role)',
                        'self["home_speed_chip"].setText(', 'self["home_selected_info"].setText('):
            self.assertIn(literal,self.code)
        self.assertIn('if self._r723_layout == "classic":',self.code)
        self.assertIn('self["home_snr_bar"].hide()',self.code)
        self.assertNotIn('self.session.nav.playService(',self.code[self.code.index('        if self._r723_layout == "classic":'):][:1500])

    def test_no_player_preview_or_mapping_changed(self):
        self.assertEqual(set(self.after),set(self.before)|{b.ICON,b.CHANGELOG})
        for filename,original in self.before.items():
            if filename not in (b.PLUGIN,b.UPDATER):
                with self.subTest(filename=filename):self.assertEqual(original,self.after[filename])
        def methods(tree):
            clazz=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="SatIPTVBridgeDashboard")
            return {x.name:ast.dump(x,include_attributes=False) for x in clazz.body if isinstance(x,ast.FunctionDef)}
        old,new=methods(ast.parse(self.before[b.PLUGIN])),methods(self.tree)
        self.assertEqual(set(old)|{"_r723_select_home_layout","_r723_set_home_layout"},set(new))
        self.assertEqual({k for k in old if old[k]!=new[k]},{"__init__","_refresh_monitor","open_settings","_r711_tools_choice"})

    def test_reproducible_and_main_updater_untouched(self):
        other=Path(self.tmp.name)/"again.ipk"
        info=b.build(other)
        self.assertEqual(self.path.read_bytes(),other.read_bytes())
        self.assertEqual(info["sha256"],hashlib.sha256(other.read_bytes()).hexdigest())
        import json
        self.assertEqual(json.loads((b.ROOT/"update.json").read_text())["version"],"1.0.46-r70-final")
        self.assertFalse(self.result["receiver_tested"])
        self.assertFalse(self.result["published_to_main"])

if __name__=="__main__":unittest.main()
