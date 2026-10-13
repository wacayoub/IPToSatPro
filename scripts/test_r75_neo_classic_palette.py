"""R75 Neo Dark R73 classic palette: test ACTUAL built R75 Preview file.

All Enigma2 screen geometry, 20 widget positions/sizes/fonts/lists, and other
Python modules must remain unchanged. Install to temp directory and rollback.
"""
import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/path)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


theme=load("classic","r75_neo_dark_classic_theme.py")
builder=load("builder","build-r75-smart-index.py")


class R75ClassicThemeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.td=tempfile.TemporaryDirectory()
        dest=Path(cls.td.name)/"r75.ipk"
        cls.details=builder.build(dest)
        pack=builder.base.b.b.base.pack
        cls.files=pack.members_from(pack.unpack_ar(dest.read_bytes())["data.tar.gz"])
        cls.src=cls.files[builder.P+"preview_theme_r74.py"].decode()
        cls.new,cls.status=theme.patch(cls.src)

    @classmethod
    def tearDownClass(cls):cls.td.cleanup()

    def test_real_r75_payload_original_palette(self):
        self.assertEqual(self.status,"ready")
        self.assertEqual(self.details["version"],builder.VERSION)
        self.assertIn('#08131E',self.src)
        self.assertIn('PREVIEW_R74_FHD',self.src)
        self.assertNotIn(theme.TAG,self.src)
        self.assertIn(theme.TAG,self.new)

    def test_theme_only_layout_and_widgets_fully_identical(self):
        nodes,widgets=theme.preserve_layout(self.src,self.new)
        self.assertGreater(nodes,20)
        self.assertEqual(widgets,20)
        old=theme.skin(self.src)
        new=theme.skin(self.new)
        self.assertEqual([w.attrib["name"] for w in old if w.tag=="widget"],
                         [w.attrib["name"] for w in new if w.tag=="widget"])
        self.assertEqual(old.attrib["size"],"1700,790")
        for a,b in zip(old.iter(),new.iter()):
            for key in ("position","size","font","itemHeight","name"):
                self.assertEqual(a.attrib.get(key),b.attrib.get(key),key)

    def test_neo_r73_original_backdrop_and_buttons(self):
        after=theme.skin(self.new)
        self.assertEqual(after.attrib["backgroundColor"],"#090F18")
        colors=[n.attrib.get("backgroundColor","") for n in after.iter()]
        self.assertIn("#27C7AC",colors)
        self.assertIn("#121F2D",colors)
        self.assertIn("#8A343E",colors)
        self.assertIn("#257955",colors)
        self.assertIn("#A78129",colors)
        self.assertIn("#286B9A",colors)
        self.assertIn("#473E69",colors)

    def test_idempotence(self):
        self.assertEqual(theme.patch(self.new),(self.new,"already-installed"))

    def test_rollback_exact_bytes_and_backup(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/"preview_theme_r74.py"
            target.write_text(self.src,encoding="utf-8")
            self.assertEqual(theme.main(["--check","--target",str(target)]),0)
            self.assertEqual(theme.main(["--apply","--target",str(target)]),0)
            self.assertEqual(target.read_text(),self.new)
            backup=target.with_name(theme.BACKUP)
            self.assertEqual(backup.read_text(),self.src)
            self.assertEqual(theme.main(["--rollback","--target",str(target)]),0)
            self.assertEqual(target.read_text(),self.src)

    def test_no_monitor_player_or_map_changes(self):
        # The only modified user-installed file is preview_theme_r74.py.
        self.assertEqual(str(theme.TARGET.name),"preview_theme_r74.py")
        transformed=self.files.copy()
        transformed[builder.P+"preview_theme_r74.py"]=self.new.encode()
        changed=[p for p in transformed if transformed[p]!=self.files[p]]
        self.assertEqual(changed,[builder.P+"preview_theme_r74.py"])
        for path,content in transformed.items():
            if path.endswith(".py"):
                compile(content,path,"exec")


if __name__=="__main__":
    unittest.main()
