#!/usr/bin/env python3
"""R72.1 real packaged native icons, measured resolution and runtime guard."""
import ast,base64,hashlib,importlib.util,io,tempfile,unittest,xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
sp=importlib.util.spec_from_file_location("premium",Path(__file__).with_name("build-r721-icons.py"))
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)

class IconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.tmp.name)/"icons.ipk"
        cls.result=b.build(cls.path)
        cls.data=b.archive.members_from(b.archive.unpack_ar(cls.path.read_bytes())["data.tar.gz"])
        cls.old=b.archive.members_from(b.archive.unpack_ar(base64.b64decode(b.B64.read_bytes()))["data.tar.gz"])
        cls.code=cls.data[b.PLUGIN].decode()
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def test_anti_aliased_real_icon_art_exists_on_all_panels(self):
        png=self.data[b.IMAGE]
        self.assertEqual(png[:8],b"\x89PNG\r\n\x1a\n")
        self.assertLess(len(png),250000)
        with Image.open(io.BytesIO(png)) as im:
            self.assertEqual(im.size,(1660,900))
            # assert actual pixels rendered in SAT badge, IPTV badge,
            # six different metric pictograms, scanner and Update icons.
            for x,y in [(710,213),(1513,213),(104,578),(633,582),
                        (1167,577),(111,720),(642,712),(1163,713),
                        (266,841),(1002,842)]:
                block=im.crop((x-17,y-16,x+18,y+17))
                self.assertGreater(len(set(block.getdata())),5,(x,y))

    def test_enigma2_res_icon_native_badges_and_spatial_bounds(self):
        root=ET.fromstring(b.update_skin(b.baseline.skin()))
        keys={x.get("name"):x for x in root if x.tag=="widget"}
        self.assertIn("r721_sat_res_badge",keys)
        self.assertIn("r721_iptv_res_badge",keys)
        self.assertIn("home_snr_bar",keys)
        self.assertIn("r72_sat_name",keys)
        self.assertIn("r72_iptv_name",keys)
        for x in root:
            if x.tag in ("widget","ePixmap"):
                a,bp=map(int,x.get("position").split(","))
                w,h=map(int,x.get("size").split(","))
                self.assertGreaterEqual(a,0);self.assertGreaterEqual(bp,0)
                self.assertLessEqual(a+w,1660);self.assertLessEqual(bp+h,900)
        for name in ("r72_res_val","r72_speed_val","r72_audio_lang_val",
                     "r72_audio_codec_val","r72_video_codec_val","r72_source_val"):
            # Dynamic text never overwrites vector icon art on the left.
            self.assertGreaterEqual(int(keys[name].get("position").split(",")[0]),140)

    def test_resolution_truth_source(self):
        self.assertIn('if verified else "?"',self.code)
        self.assertIn('sat_badge = _r721_res_class(snap.get("sat_width"),snap.get("sat_height"))',self.code)
        self.assertIn('self["r721_sat_res_badge"].setText(sat_badge)',self.code)
        self.assertIn('self["r721_iptv_res_badge"].setText(iptv_badge)',self.code)
        self.assertIn('w>=3000',self.code)
        self.assertIn('h>=1000',self.code)
        self.assertIn('return "?"',self.code)
        self.assertNotIn("Pixel measured by image name",self.code)

    def test_audio_fastzap_mapping_and_preview_unchanged(self):
        allowed={b.PLUGIN,b.UPDATER}
        self.assertEqual(set(self.data),set(self.old)|{b.IMAGE,b.CHANGELOG})
        for name,blob in self.old.items():
            if name not in allowed:
                with self.subTest(name=name):self.assertEqual(blob,self.data[name])
        oldtree=ast.parse(self.old[b.PLUGIN])
        newtree=ast.parse(self.code)
        def methods(tree):
            dashboard=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="SatIPTVBridgeDashboard")
            return {x.name:ast.dump(x,include_attributes=False) for x in dashboard.body if isinstance(x,ast.FunctionDef)}
        old,new=methods(oldtree),methods(newtree)
        self.assertEqual(set(old),set(new))
        self.assertEqual({n for n in old if old[n]!=new[n]},{"__init__","_refresh_monitor"})
        self.assertFalse(self.result["runtime_player_changed"])
        self.assertFalse(self.result["receiver_tested"])

    def test_reproducible_and_nonproduction(self):
        dest=Path(self.tmp.name)/"again.ipk"
        result=b.build(dest)
        self.assertEqual(self.path.read_bytes(),dest.read_bytes())
        self.assertEqual(result["sha256"],hashlib.sha256(dest.read_bytes()).hexdigest())
        self.assertFalse(result["production_published"])
if __name__=="__main__":unittest.main()
