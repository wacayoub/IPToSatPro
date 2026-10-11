#!/usr/bin/env python3
"""R72.2 regression tests grounded in screenshot and shipped R72.1 beta."""
import ast,base64,hashlib,importlib.util,tempfile,unittest,xml.etree.ElementTree as ET
from pathlib import Path
sp=importlib.util.spec_from_file_location("r722",Path(__file__).with_name("build-r722-tv-polish.py"))
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)

class TvPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.path=Path(cls.tmp.name)/"test.ipk"
        cls.info=b.build(cls.path)
        cls.after=b.archive.members_from(b.archive.unpack_ar(cls.path.read_bytes())["data.tar.gz"])
        cls.before=b.archive.members_from(b.archive.unpack_ar(base64.b64decode(b.BASE.read_bytes()))["data.tar.gz"])
        cls.code=cls.after[b.PLUGIN].decode()
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_photo_issues_resolved_in_native_ui(self):
        self.assertIn('self.setTitle("IPToSat Pro")',self.code)
        self.assertIn('Label("R72.2 BETA")',self.code)
        self.assertIn('self["home_snr_bar"].hide()',self.code)
        self.assertIn('self["home_snr_bar"].show()',self.code)
        self.assertIn('self["r72_sat_signal_title"].setText(',self.code)
        self.assertIn('SAT SIGNAL • NO LOCK',self.code)
        self.assertIn('full_iptv_name = first_name + "\\n" + remaining[:35]',self.code)
        self.assertIn('self["r72_iptv_name"].setText(full_iptv_name)',self.code)
        self.assertIn('if snap.get("sat_shadow_lock") else "?"',self.code)
        self.assertIn('SAT video %s • Audio %s',self.code)
    def test_iptv_long_line_has_real_two_rows(self):
        xml=self.code.split('DASHBOARD_FHD = """\n',1)[1].split('\n"""\n\nSETTINGS_FHD = """',1)[0]
        root=ET.fromstring(xml)
        widget={x.get("name"):x for x in root if x.tag=="widget"}
        self.assertGreaterEqual(int(widget["r72_iptv_name"].get("size").split(",")[1]),76)
        self.assertGreaterEqual(int(widget["r72_iptv_provider"].get("position").split(",")[1]),333)
        self.assertLessEqual(int(widget["r72_iptv_role"].get("position").split(",")[1]),404)
        self.assertIn("r722_footer_hint",widget)
        for el in root:
            if el.tag in ("widget","ePixmap"):
                x,y=map(int,el.get("position").split(","))
                w,h=map(int,el.get("size").split(","))
                self.assertLessEqual(x+w,1660)
                self.assertLessEqual(y+h,900)
    def test_player_preview_sources_audio_mapping_byte_identical(self):
        self.assertEqual(set(self.after),set(self.before)|{b.CHANGELOG})
        for p,raw in self.before.items():
            if p not in (b.PLUGIN,b.UPDATER):
                with self.subTest(name=p):self.assertEqual(raw,self.after[p])
        before=ast.parse(self.before[b.PLUGIN])
        after=ast.parse(self.code)
        def methods(tree):
            klass=next(c for c in tree.body if isinstance(c,ast.ClassDef) and c.name=="SatIPTVBridgeDashboard")
            return {m.name:ast.dump(m,include_attributes=False) for m in klass.body if isinstance(m,ast.FunctionDef)}
        old,new=methods(before),methods(after)
        self.assertEqual(set(old),set(new))
        self.assertEqual({m for m in new if old[m]!=new[m]},{"__init__","_refresh_monitor"})
        self.assertFalse(self.info["player_changed"])
    def test_reproducibility_and_isolation(self):
        again=Path(self.tmp.name)/"again.ipk"
        meta=b.build(again)
        self.assertEqual(self.path.read_bytes(),again.read_bytes())
        self.assertEqual(meta["sha256"],hashlib.sha256(again.read_bytes()).hexdigest())
        import json
        self.assertEqual(json.loads((b.ROOT/"update.json").read_text())["version"],"1.0.46-r70-final")
        self.assertFalse(self.info["field_tested"])
if __name__=="__main__":unittest.main()
