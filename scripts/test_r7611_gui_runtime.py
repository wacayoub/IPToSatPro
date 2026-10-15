#!/usr/bin/env python3
"""Offline R76.11 GUI process timeline tests; never touch a real receiver."""
import datetime
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

SCRIPT=Path(__file__).resolve().parent/"audit_r7611_gui_runtime_readonly.py"
spec=importlib.util.spec_from_file_location("gui_runtime",SCRIPT)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class GuiRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.proc=self.root/"proc";self.proc.mkdir()
        self.config=self.root/"config";self.config.mkdir()
        self.backups=self.root/"backups";self.backups.mkdir()
        self.snapshot=self.backups/"20261014T222823";self.snapshot.mkdir()
        (self.backups/"last-backup-path").write_text(str(self.snapshot))
        self.plugin=self.root/"plugin.py"
        self.plugin.write_text('PLUGIN_VERSION = "1.0.46-r76.11-preview-coldstart-fast-beta"\n')
        self.log=self.config/"bridge.log"
        self.install=datetime.datetime.strptime(
            "2026-10-14 22:28:23","%Y-%m-%d %H:%M:%S").timestamp()
        self.boot=int(self.install)-10000
        (self.proc/"stat").write_text("cpu 1 2 3\nbtime %d\n"%self.boot)
        self.hz=os.sysconf("SC_CLK_TCK")

    def tearDown(self):
        self.tmp.cleanup()

    def add_gui(self,start_relative,pid=2734,name="enigma2"):
        p=self.proc/str(pid);p.mkdir()
        (p/"comm").write_text(name+"\n")
        # Fields 3.. are after ')' with start ticks in zero-index 19.
        fields=["0"]*50
        fields[0]="S"
        fields[19]=str(int((self.install+start_relative-self.boot)*self.hz))
        (p/"stat").write_text(f"{pid} (enigma2) "+" ".join(fields)+"\n")

    def audit(self):
        return m.report(self.proc,self.plugin,self.backups,self.log)

    def test_old_gui_detects_loaded_before_upgrade(self):
        self.add_gui(-900)
        self.log.write_text("2026-10-15 04:13:50 | IPTV_OK | url=supersecret\n")
        r=self.audit()
        self.assertTrue(r["installed_r7611_on_disk"])
        self.assertFalse(r["gui_started_after_install"])
        self.assertEqual(r["finding"],
            "ENIGMA2_GUI_PREDATES_R7611_INSTALL_RESTART_MAY_BE_NEEDED")
        self.assertEqual(r["log_activity"]["timestamped_lines_after_install"],1)
        self.assertNotIn("supersecret",json.dumps(r))

    def test_restarted_gui_no_preview(self):
        self.add_gui(50)
        self.log.write_text("2026-10-15 19:08:52 | IPTV_OK | secret=http://foo\n")
        r=self.audit()
        self.assertTrue(r["gui_started_after_install"])
        self.assertEqual(r["finding"],"GUI_STARTED_AFTER_INSTALL_BUT_NO_PREVIEW_EVENTS_LOGGED")
        self.assertEqual(r["log_activity"]["preview_events_after_install"],{})
        self.assertNotIn("http://foo",json.dumps(r))

    def test_restarted_gui_with_preview_event(self):
        self.add_gui(100)
        self.log.write_text(
            "2026-10-14 20:26:58 | PREVIEW_RANK_BG | elapsed=56042ms\n"
            "2026-10-15 19:09:00 | PREVIEW_RANK_BG | elapsed=141ms sat=SECRET\n")
        r=self.audit()
        self.assertTrue(r["gui_started_after_install"])
        self.assertEqual(r["log_activity"]["preview_events_after_install"],{"PREVIEW_RANK_BG":1})
        self.assertEqual(r["finding"],"GUI_STARTED_AFTER_INSTALL_AND_PREVIEW_EVENTS_PRESENT")
        self.assertNotIn("SECRET",json.dumps(r))

    def test_no_gui_does_not_claim_restart(self):
        self.assertEqual(self.audit()["finding"],"ENIGMA2_GUI_PROCESS_NOT_FOUND")
        self.assertIsNone(self.audit()["gui_started_after_install"])

    def test_backup_untrusted_pointer(self):
        (self.backups/"last-backup-path").write_text("/etc")
        self.assertIsNone(m.baseline(self.backups))
        self.assertEqual(self.audit()["finding"],"INSTALL_BASELINE_UNKNOWN")

    def test_proc_stat_starttime_field_22(self):
        mock="123 (enigma2 engine) S "+" ".join(["0"]*18+["12345"]+["0"]*20)
        self.assertEqual(m.proc_start(mock,1000,100),1123.45)
        self.assertIsNone(m.proc_start("garbled",1000,100))


if __name__=="__main__":
    unittest.main()
