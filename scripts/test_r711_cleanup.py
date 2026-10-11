#!/usr/bin/env python3
"""R71.1 cleanup exact-package tests: image, UI skin, remote, sources protected."""
import ast,base64,hashlib,importlib.util,io,tempfile,unittest,xml.etree.ElementTree as ET
from pathlib import Path
from PIL import Image
spec=importlib.util.spec_from_file_location("cleanup",Path(__file__).with_name("build-r711-cleanup-beta.py"))
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)

class CleanupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir=tempfile.TemporaryDirectory()
        cls.path=Path(cls.dir.name)/"candidate.ipk"
        cls.meta=b.build(cls.path)
        cls.out=b.archive.members_from(b.archive.unpack_ar(cls.path.read_bytes())["data.tar.gz"])
        cls.base=b.archive.members_from(b.archive.unpack_ar(base64.b64decode(b.B64.read_bytes()))["data.tar.gz"])
        cls.plugin=cls.out[b.PLUGIN].decode()
        cls.tree=ast.parse(cls.plugin)
        cls.dashboard=next(x for x in cls.tree.body if isinstance(x,ast.ClassDef) and x.name=="SatIPTVBridgeDashboard")

    @classmethod
    def tearDownClass(cls):cls.dir.cleanup()

    def test_screen_like_reference_and_rounded_asset(self):
        from PIL import Image
        art=self.out[b.ASSET]
        self.assertEqual(art[:8],b"\x89PNG\r\n\x1a\n")
        with Image.open(io.BytesIO(art)) as pic:
            self.assertEqual(pic.size,(1660,900))
            self.assertEqual(pic.mode,"RGBA")
            self.assertTrue(pic.getpixel((45,335))[3])
        xml=b.source_skin()
        parsed=ET.fromstring(xml)
        names=[x.get("name") for x in parsed if x.tag=="widget"]
        self.assertEqual(len(names),len(set(names)))
        for gone in ("card_engine_value","context_market","source_server","log_preview",
                     "key_red","key_green","key_yellow","banner"):
            self.assertNotIn(gone,names)
        for kept in ("home_sat_name","home_snr_bar","home_selected_name","home_lock_badge",
                     "home_preview_action","home_update_action","key_blue","home_menu_hint"):
            self.assertIn(kept,names)
        self.assertIn("__IPTOSAT_NEO_CLEANUP_BG__",xml)
        self.assertIn("neo-home-cleanup.png",self.plugin)

    def test_clean_remote_navigation_and_tools(self):
        s=self.plugin
        self.assertIn('"green": self.open_preview_sources',s)
        self.assertIn('"yellow": self.open_updater',s)
        self.assertIn('"blue": self.open_logs',s)
        self.assertIn('"menu": self.open_settings',s)
        self.assertIn('title="IPToSat Pro  •  Settings / Tools"',s)
        for s2 in ("Settings  •  Essential","Settings  •  Advanced",
                   "Tools  •  Manual Mapping","Tools  •  Smart Match Test",
                   "Tools  •  Auto Scan","Tools  •  Player Lock",
                   "Tools  •  System Diagnostics","Tools  •  Event Log",
                   "Tools  •  Online Update"):
            self.assertIn(s2,s)
        init=next(x for x in self.dashboard.body if isinstance(x,ast.FunctionDef) and x.name=="__init__")
        source=ast.get_source_segment(s,init)
        self.assertNotIn('"NumberActions"',source)
        self.assertNotIn('"3": self.open_auto_scan',source)
        self.assertNotIn('"0": self.player_lock_current',source)
        self.assertNotIn('"4": self.open_all_sources',source)

    def test_audio_and_status_no_fake_values(self):
        s=self.plugin
        self.assertIn('language = str(snap.get("language") or "")',s)
        self.assertIn('quality_short = ("4K/UHD"',s)
        self.assertIn('self["home_snr_bar"].setValue(',s)
        self.assertIn('else "N/A"',s)
        self.assertIn('_load_overrides().get(sat_service_key(sat_ref))',s)
        self.assertIn('self["home_iptv_detail"].setText("%d IPTV channels in catalog"',s)
        self.assertNotIn("72 candidates (live tested)",s)

    def test_retain_actual_player_preview_mapping(self):
        allow={b.PLUGIN,b.UPDATER}
        self.assertEqual(set(self.out),set(self.base)|{b.ASSET,b.CHANGELOG})
        for path,raw in self.base.items():
            if path not in allow:self.assertEqual(raw,self.out[path],path)
        bt=ast.parse(self.base[b.PLUGIN])
        oldcls=next(x for x in bt.body if isinstance(x,ast.ClassDef) and x.name=="SatIPTVBridgeDashboard")
        old={x.name:ast.dump(x,include_attributes=False) for x in oldcls.body if isinstance(x,ast.FunctionDef)}
        new={x.name:ast.dump(x,include_attributes=False) for x in self.dashboard.body if isinstance(x,ast.FunctionDef)}
        changed=set(x for x in old if x in new and old[x]!=new[x])
        self.assertEqual(changed,{"__init__","_refresh_monitor","open_settings"})
        self.assertEqual(set(new)-set(old),{"_r711_tools_choice"})

    def test_reproducible_package(self):
        other=Path(self.dir.name)/"again.ipk"
        meta=b.build(other)
        self.assertEqual(self.path.read_bytes(),other.read_bytes())
        self.assertEqual(meta['sha256'],hashlib.sha256(other.read_bytes()).hexdigest())
        self.assertTrue(meta['stable_main_unchanged'])
        self.assertFalse(meta['receiver_tested'])

if __name__=="__main__":unittest.main()
