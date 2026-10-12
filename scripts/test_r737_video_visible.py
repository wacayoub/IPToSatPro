#!/usr/bin/env python3
"""R73.7 compiled IPK: Preview OK video visibility and guaranteed GUI return."""
import ast, base64, importlib.util, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location("builder737",ROOT/"scripts/build-r73-preview.py")
b=importlib.util.module_from_spec(sp);sp.loader.exec_module(b)

class VideoWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.t=tempfile.TemporaryDirectory()
        path=Path(cls.t.name)/"r737.ipk"
        cls.meta=b.build(path)
        cls.files=b.base.pack.members_from(b.base.pack.unpack_ar(path.read_bytes())["data.tar.gz"])
        cls.base=b.base.pack.members_from(b.base.pack.unpack_ar(base64.b64decode(b.B64.read_bytes()))["data.tar.gz"])
        cls.ps=cls.files[b.PLUGIN].decode()
        tree=ast.parse(cls.ps)
        cls.preview=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=="SatIPTVBridgePreview")
        cls.methods={}
        for n in cls.preview.body:
            if isinstance(n,ast.FunctionDef):cls.methods[n.name]=n

    @classmethod
    def tearDownClass(cls):cls.t.cleanup()
    def method(self,name):
        ns={"_startup_log":lambda *args,**kwargs:self.logs.append((args,kwargs))}
        module=ast.fix_missing_locations(ast.Module(body=[self.methods[name]],type_ignores=[]))
        exec(compile(module,"r737_test","exec"),ns)
        return ns[name]
    def setUp(self):self.logs=[]

    def fake(self,broken=False):
        class L:
            def __init__(self):self.value=""
            def setText(self,text):self.value=text
        class Timer:
            def __init__(self):self.started=[];self.stopped=0
            def start(self,delay,one):self.started.append((delay,one))
            def stop(self):self.stopped+=1
        class Fake:
            def __init__(self):
                self._r737_video_visible=False
                self._r737_video_timer=Timer()
                self.values={"detail":L()}
                self.sat_name="V Sport 1 HD"
                self.channel={"name":"V SPORT 1"}
                self.mode="4097"
                self.current_result="VERIFY"
                self.hidden=False
                self.shown=False
                self.rendered=0
            def __getitem__(self,key):return self.values[key]
            def hide(self):
                if broken: raise RuntimeError("unsupported")
                self.hidden=True
            def show(self):self.shown=True;self.hidden=False
            def _dimensions(self):return (0,0)
            def _preview_player_active(self):return True
            def _render_source_list(self,keep_index=True):self.rendered+=1
            def _update_header(self):self.rendered+=1
        return Fake()

    def test_ok_launches_real_playback_then_unobstructs_screen(self):
        body=ast.get_source_segment(self.ps,self.methods["_preview_selected"])
        self.assertIn("self._play_current_mode()",body)
        self.assertIn("self._r737_show_video_fullscreen()",body)
        self.assertLess(body.index("self._play_current_mode()"),
                        body.index("self._r737_show_video_fullscreen()"))
        init=ast.get_source_segment(self.ps,self.methods["__init__"])
        self.assertIn("self._r737_video_timer.callback.append(self._r737_restore_video)",init)
        self.assertIn("self.onClose.append(self._r737_cleanup_video)",init)

    def test_hides_fullscreen_8_seconds_then_returns_even_with_no_dimensions(self):
        v=self.fake()
        opening=self.method("_r737_show_video_fullscreen")
        closing=self.method("_r737_restore_video")
        opening(v)
        self.assertTrue(v.hidden)
        self.assertEqual(v._r737_video_timer.started,[(8000,True)])
        self.assertIn("FULLSCREEN",v["detail"].value)
        self.assertTrue(any("FULLSCREEN" in str(item) for item in self.logs))
        closing(v)
        self.assertFalse(v.hidden)
        self.assertTrue(v.shown)
        self.assertFalse(v._r737_video_visible)
        self.assertEqual(v.rendered,2)
        self.assertTrue(any("dimensions=0x0" in str(item) for item in self.logs))
        self.assertEqual(v.current_result,"VERIFY")

    def test_screen_hide_not_supported_does_not_leave_user_stuck(self):
        v=self.fake(broken=True)
        self.method("_r737_show_video_fullscreen")(v)
        self.assertFalse(v._r737_video_visible)
        self.assertTrue(v.shown)
        self.assertTrue(any("HIDE_FAILED" in str(item) for item in self.logs))

    def test_cleanup_stops_timer(self):
        v=self.fake()
        v._r737_video_visible=True
        self.method("_r737_cleanup_video")(v)
        self.assertFalse(v._r737_video_visible)
        self.assertEqual(v._r737_video_timer.stopped,1)

    def test_opaque_theme_identified_without_destructive_skin_changes(self):
        theme=(ROOT/"scripts/r73_preview_theme.py").read_text()
        self.assertIn('backgroundColor="#090F18"',theme)
        self.assertIn('position="567,213" size="1109,417" backgroundColor=',theme)
        self.assertIn("OK = 8-second FULLSCREEN video test",self.ps)
        self.assertIn("PREVIEW_VIDEO_WINDOW",self.ps)

    def test_all_existing_hardware_modules_and_user_files_protected(self):
        for key,orig in self.base.items():
            if key not in (b.PLUGIN,b.CORE,b.UPDATER):
                self.assertEqual(orig,self.files[key],key)
        self.assertTrue(self.meta["player_unchanged"])
        self.assertFalse(self.meta["receiver_tested"])
        self.assertFalse(self.meta["production_published"])
        self.assertEqual(self.meta["candidate_search"],
            "r737_8s_video_preview_then_auto_restore_with_r736_automap")

if __name__=="__main__":unittest.main()
