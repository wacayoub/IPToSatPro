#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R76.7: installed-IPK acceptance for all 11 theme skins, Settings and MENU."""
import ast
import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/filename)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
    return obj

b=load("r767_actual_build","build-r76-metrix-preview.py")
r767=b.r767
layout=b.layout

def constants(code):
    out={}
    for n in ast.parse(code).body:
        if isinstance(n,ast.Assign):
            for dest in n.targets:
                if isinstance(dest,ast.Name):
                    try:out[dest.id]=ast.literal_eval(n.value)
                    except Exception:pass
    return out

class R767ThemeMenu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        dest=Path(cls.temp.name)/"r767.ipk"
        cls.report=b.build(dest)
        cls.actual=b.pack.members_from(b.pack.unpack_ar(dest.read_bytes())["data.tar.gz"])
        cls.themes=constants(cls.actual[b.HOME_THEMES].decode())
        cls.plugin=cls.actual[b.PLUGIN].decode()
        cls.ast=ast.parse(cls.plugin)
        cls.base_layout=layout.make_home()
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_11_unique_native_skins_in_both_resolutions(self):
        self.assertEqual(len(self.themes["THEME_CHOICES"]),11)
        self.assertEqual(len(self.themes["THEME_FHD"]),11)
        self.assertEqual(len(self.themes["THEME_HD"]),11)
        self.assertEqual(set(self.themes["THEME_FHD"]),set(self.themes["THEME_HD"]))
        self.assertEqual(self.themes["THEME_CHOICES"][-1][1],"metrix")
        seen=set()
        for label,identifier in self.themes["THEME_CHOICES"]:
            fhd=self.themes["THEME_FHD"][identifier]
            hd=self.themes["THEME_HD"][identifier]
            self.assertNotIn(fhd,seen)
            seen.add(fhd)
            for xml,is_hd in ((fhd,False),(hd,True)):
                root=layout.validate_skin(xml,set(layout.HOME_WIDGETS),hd=is_hd)
                names={x.get("name") for x in root if x.tag=="widget"}
                self.assertIn("r72_sat_signal",names)
                self.assertIn("home_snr_bar",names)
                self.assertIn("r72_audio_lang_val",names)
                self.assertIn("r76_epg_label",names)
                self.assertIn("r76_mapping_label",names)
                self.assertEqual(len(names),len(layout.HOME_WIDGETS))
                self.assertEqual({x.get("name") for x in root if x.tag=="widget"
                    and x.get("name","").startswith("key_")},
                                 {"key_red","key_green","key_yellow","key_blue"})
        self.assertEqual(len(seen),11)

    def test_theme_semantics_and_no_runtime_fetches(self):
        text=self.actual[b.HOME_THEMES].decode()
        for word in ("urlopen(", "HTTPConnection(", "eval(", "exec(", "requests.get",
                     "eTimer(", "subprocess.", "sleep("):
            self.assertNotIn(word,text)
        self.assertLess(len(self.actual[b.HOME_THEMES]),500000)
        self.assertNotIn("VideoWindow",text)
        for identifier in ("oled","matrix","cinema","glass","executive","carbon","gold","metro","studio","metrix","neo_dark"):
            self.assertIn(identifier,self.themes["THEME_FHD"])
        bg={k:ET.fromstring(xml).get("backgroundColor")
             for k,xml in self.themes["THEME_FHD"].items()}
        self.assertEqual(len(set(bg.values())),11)

    def test_menu_4_main_groups_and_all_legacy_actions_accessible(self):
        cls=next(c for c in self.ast.body if isinstance(c,ast.ClassDef)
                and c.name=="SatIPTVBridgeDashboard")
        methods={n.name:ast.get_source_segment(self.plugin,n)
                 for n in cls.body if isinstance(n,ast.FunctionDef)}
        main=methods["open_settings"]
        self.assertEqual(main.count('"group_'),4)
        for name in ("group_appearance","group_settings","group_matching","group_system"):
            self.assertIn(name,main)
        grouped=methods["_r767_open_group"]
        self.assertIn('self._r723_select_home_layout()',grouped)
        for action in ("quick","advanced","preview","mapping","auto_scan",
                      "match_test","player_lock","diagnostics","logs","update"):
            self.assertIn('"'+action+'"',grouped)
        self.assertNotIn("NumberActions",methods["__init__"])
        menu=methods["_r711_tools_choice"]
        self.assertIn('if selected.startswith("group_"):',menu)
        self.assertIn("self._r767_open_group(selected)",menu)
        # Buttons and existing action methods stay unchanged.
        for line in ('"green": self.open_preview_sources',
                     '"yellow": self.open_updater',
                     '"blue": self.open_logs',
                     '"menu": self.open_settings'):
            self.assertIn(line,self.plugin)

    def test_theme_selection_persists_only_r76_appearance(self):
        cls=next(c for c in self.ast.body if isinstance(c,ast.ClassDef)
                 and c.name=="SatIPTVBridgeDashboard")
        methods={n.name:ast.get_source_segment(self.plugin,n)
                 for n in cls.body if isinstance(n,ast.FunctionDef)}
        chooser=methods["_r723_select_home_layout"]
        setter=methods["_r723_set_home_layout"]
        self.assertIn("from .home_themes_r767 import THEME_CHOICES",chooser)
        self.assertIn("list=list(THEME_CHOICES)",chooser)
        self.assertIn("_r76_home_pref_path",setter)
        self.assertNotIn("_r723_home_pref_path",setter)
        self.assertIn("os.rename",setter)
        self.assertIn("reopen IPToSat Pro",chooser)
        dashboard=methods["__init__"]
        self.assertIn("R767_ELEVEN_HOME_THEMES",dashboard)
        self.assertIn("THEME_HD if _r76_is_hd else THEME_FHD",dashboard)
        self.assertIn("_r76_layout = \"neo_dark\"",dashboard)
        self.assertIn("_r76_layout = \"studio\"",dashboard)
        self.assertIn("_r76_layout = \"metrix\"",dashboard)

    def test_pkg_keeps_preview_autolock_core_and_player_intact(self):
        baseline=Path(self.temp.name)/"r75.ipk"
        b.base.build(baseline)
        older=b.pack.members_from(b.pack.unpack_ar(baseline.read_bytes())["data.tar.gz"])
        self.assertEqual(set(self.actual)-set(older),{b.NOTE,b.HOME_THEMES})
        for name in older:
            if name not in (b.PLUGIN,b.UPDATER,b.THEME,b.base.CORE):
                self.assertEqual(older[name],self.actual[name])
        self.assertIn("R766_COLD_RANK_FAST",self.actual[b.base.CORE].decode())
        self.assertIn("R764_MULTI_CANDIDATE_FIRST_PAINT",self.plugin)
        self.assertIn("PREVIEW_RANK_BG",self.plugin)
        self.assertFalse(self.report["receiver_tested"])
        self.assertFalse(self.report["production_published"])

if __name__=="__main__":
    unittest.main()
