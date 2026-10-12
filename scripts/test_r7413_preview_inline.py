"""R7413 tests against real built R74 plugin, then staged R7411/12 fixes."""
import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]


def load(name,filename):
    spec=importlib.util.spec_from_file_location(name,ROOT/"scripts"/filename)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder=load("r74_build_for_r7413","build-r74-unified.py")
fix11=load("r7411_for_r7413","r7411_preview_persist_priority_hotfix.py")
fix12=load("r7412_for_r7413","r7412_preview_fast_shortlist_hotfix.py")
fix13=load("r7413_for_tests","r7413_preview_inline_hotfix.py")


class PreviewInlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        ipk=Path(cls.temp.name)/"r74.ipk"
        builder.build(ipk)
        pack=builder.b.b.base.pack
        entries=pack.members_from(pack.unpack_ar(ipk.read_bytes())["data.tar.gz"])
        cls.original=entries[builder.PLUGIN].decode()
        cls.r11=fix11.patch_plugin(cls.original)[0]
        cls.r12=fix12.patch(cls.r11)[0]
        cls.r13,cls.stage=fix13.patch(cls.r12)
        cls.tree=ast.parse(cls.r13)
        cls.preview=next(x for x in cls.tree.body if isinstance(x,ast.ClassDef)
                         and x.name=="SatIPTVBridgePreview")
        cls.methods={x.name:x for x in cls.preview.body if isinstance(x,ast.FunctionDef)}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def method(self,name,globs):
        function=self.methods[name]
        code=ast.fix_missing_locations(ast.Module(body=[function],type_ignores=[]))
        exec(compile(code,"r7413-test","exec"),globs)
        return globs[name]

    def test_guards_and_changes_only_gui_method_and_call(self):
        self.assertEqual(self.stage,"ready")
        self.assertEqual(fix13.patch(self.r13)[1],"already-installed")
        self.assertIn(fix13.TAG,self.r13)
        self.assertEqual(self.r13.count("_r7413_keep_preview_visible()"),1)
        self.assertEqual(self.r13.count("def _r7413_keep_preview_visible(self):"),1)
        preview_body=ast.get_source_segment(self.r13,self.methods["_preview_selected"])
        self.assertIn("self._play_current_mode()",preview_body)
        self.assertIn("self._r7413_keep_preview_visible()",preview_body)
        self.assertNotIn("self._r737_show_video_fullscreen()",preview_body)

    def test_video_starts_then_preview_stays_visible(self):
        method=ast.get_source_segment(self.r13,self.methods["_preview_selected"])
        self.assertLess(method.index("self._play_current_mode()"),
                        method.index("self._r7413_keep_preview_visible()"))
        code=ast.get_source_segment(self.r13,self.methods["_r7413_keep_preview_visible"])
        self.assertNotIn("self.hide()",code)
        self.assertNotIn(".start(8000",code)
        self.assertNotIn("self.close()",code)

    def test_keep_table_visible_does_not_hide_or_close(self):
        events=[]
        class Fake:
            _r737_video_visible=False
            sat_name="beIN SPORTS 2"
            channel={"name":"AR BEIN SPORTS 2 FHD"}
            def __init__(self):self._r737_video_timer=SimpleNamespace(stop=lambda:events.append("timer-stopped"))
            def __getitem__(self,key):
                return SimpleNamespace(setText=lambda message:events.append(("detail",message)))
            def hide(self):events.append("HIDE")
            def close(self):events.append("CLOSE")
            def show(self):events.append("SHOW")
        globs={"_startup_log":lambda *args:events.append("LOG")}
        f=Fake()
        self.method("_r7413_keep_preview_visible",globs)(f)
        self.assertNotIn("HIDE",events)
        self.assertNotIn("CLOSE",events)
        self.assertNotIn("SHOW",events)
        self.assertTrue(any(isinstance(x,tuple) and "list stays open" in x[1] for x in events))

    def test_hidden_stale_video_window_recovers(self):
        actions=[]
        class Fake:
            _r737_video_visible=True
            sat_name="BBC"
            channel={"name":"BBC"}
            _r737_video_timer=SimpleNamespace(stop=lambda:actions.append("STOP"))
            def __getitem__(self,key):return SimpleNamespace(setText=lambda text:None)
            def show(self):actions.append("SHOW")
        f=Fake()
        self.method("_r7413_keep_preview_visible",{"_startup_log":lambda *a:None})(f)
        self.assertFalse(f._r737_video_visible)
        self.assertEqual(actions,["STOP","SHOW"])

    def test_normal_and_deep_counts_unchanged(self):
        self.assertIn(fix12.TAG,self.r13)
        self.assertIn("candidate_budget = 192 if self._r71_worker_deep else 24",self.r13)
        self.assertIn("candidate_per_server = 64 if self._r71_worker_deep else 8",self.r13)

    def test_auto_selection_and_audio_unchanged(self):
        self.assertIn(fix11.TAG,self.r13)
        self.assertIn("PREVIEW_STAY_OPEN",self.r13)
        self.assertIn("_r736_auto_map_single_sat(",self.r13)
        self.assertIn("def _r737_show_video_fullscreen",self.r13)
        self.assertIn("def _play_current_mode",self.r13)

    def test_apply_rollback_byte_identical(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"plugin.py"
            path.write_text(self.r12)
            self.assertEqual(fix13.main(["--check","--target",str(path)]),0)
            self.assertEqual(path.read_text(),self.r12)
            self.assertEqual(fix13.main(["--apply","--target",str(path)]),0)
            self.assertEqual(path.read_text(),self.r13)
            self.assertEqual(fix13.main(["--rollback","--target",str(path)]),0)
            self.assertEqual(path.read_text(),self.r12)

    def test_unpatched_r74_rejected(self):
        with self.assertRaises(ValueError):
            fix13.patch(self.original)


if __name__=="__main__":
    unittest.main()
