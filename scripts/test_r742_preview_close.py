#!/usr/bin/env python3
"""Regression of OpenATV 8.0.x 20261012-170137 Preview GUI crash.

Trace: Session.processDelay callback(*retVal) with retVal=() caused:
 TypeError: _open_preview_sources_direct.<locals>.<lambda>() missing 'result'.

Run extracted entrypoint from the REAL R74.2 generated IPK, never a separately
hand-copied callback implementation.
"""
import ast
import importlib.util
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("r742",ROOT/"scripts/build-r74-unified.py")
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class PreviewCloseCrashTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory()
        pkg=Path(cls.temp.name)/"r742.ipk"
        cls.meta=builder.build(pkg)
        cls.members=builder.b.b.base.pack.members_from(
            builder.b.b.base.pack.unpack_ar(pkg.read_bytes())["data.tar.gz"])
        cls.plugin=cls.members[builder.PLUGIN].decode()
        cls.tree=ast.parse(cls.plugin)
        cls.functions={n.name:n for n in cls.tree.body if isinstance(n,ast.FunctionDef)}

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.callback=None
        self.done=[]
        self.first=[]
        self.ref="1:0:19:24CD:43C:1:C00000:0:0:0:"
        self.session=SimpleNamespace()
        def open_with_callback(cb,*args):
            self.callback=cb
            self.first.extend(args)
        self.session.openWithCallback=open_with_callback

    def make_entrypoint(self):
        env={
            "time":time,
            "_match_context_for_current":lambda session:("NICKELODEON",self.ref,
                {"channel_language":"FR","audio_language_set":["FR"]}),
            "_load_overrides":lambda:{},
            "sat_service_key":lambda ref:ref,
            "MONITOR":None,
            "SatIPTVBridgePreview":object(),
            "_startup_log":lambda *args:None,
            "_direct_preview_done":lambda session,result=None:self.done.append(result),
        }
        fn=self.functions["_open_preview_sources_direct"]
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),
                     "actual-r742-package.py","exec"),env)
        return env["_open_preview_sources_direct"]

    def test_open_then_close_without_result_never_crashes_enigma2(self):
        self.assertTrue(self.make_entrypoint()(self.session))
        self.assertIsNotNone(self.callback)
        self.callback()
        self.assertEqual(self.done,[None])

    def test_open_then_close_with_none_is_safe(self):
        self.make_entrypoint()(self.session)
        self.callback(None)
        self.assertEqual(self.done,[None])

    def test_back_button_returns_result_dictionary(self):
        self.make_entrypoint()(self.session)
        value={"action":"back","sat_ref":self.ref}
        self.callback(value)
        self.assertEqual(self.done,[value])

    def test_manually_confirmed_candidate_returns_result_dictionary(self):
        self.make_entrypoint()(self.session)
        value={"action":"lock","channel":{"name":"NICKELODEON HD"},
               "sat_ref":self.ref}
        self.callback(value)
        self.assertEqual(self.done,[value])

    def test_autoplay_close_without_result_does_not_trigger_manual_lock(self):
        self.make_entrypoint()(self.session)
        self.callback()
        self.assertEqual(self.done,[None])
        # The real close handler treats None as no explicit user action.
        done=self.functions["_direct_preview_done"]
        self.assertIn("if not isinstance(result, dict):",ast.get_source_segment(self.plugin,done))

    def test_callback_no_missing_positional_argument_in_actual_package(self):
        self.assertIn(
            "session.openWithCallback(lambda result=None: _direct_preview_done(session, result)",
            self.plugin)
        self.assertNotIn(
            "session.openWithCallback(lambda result: _direct_preview_done(session, result)",
            self.plugin)

    def test_player_monitor_and_timeshift_remain_unchanged(self):
        self.assertTrue(self.meta["monitor_unchanged"])
        self.assertFalse(self.meta["receiver_tested"])
        self.assertFalse(self.meta["production_published"])


if __name__=="__main__":
    unittest.main()
