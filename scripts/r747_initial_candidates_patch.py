# -*- coding: utf-8 -*-
"""R74.7 Preview initial manual-lock seed does not expand full IPTV sources.

Keep initial single candidate for instant first paint, but always launch full
ranking when cache is marked incomplete. Handle busy old-channel worker safely
without abandoning current SAT. No player, monitor, or mapping edits.
"""
def one(src,old,new):
    n=src.count(old)
    if n!=1: raise AssertionError("R74.7 source drift %d anchor=%r"%(n,old[:180]))
    return src.replace(old,new,1)

def patch_plugin(src):
    src=one(src,'''        if not complete and not self._r732_auto_rows:
            try: self.candidate_expand_timer.start(20, True)
            except Exception: pass''',
'''        if not complete:
            # The initial channel can have one MANUAL_LOCK seed, still incomplete.
            # A nonempty seed is NOT complete multi-server candidate coverage.
            self["status"].setText(
                "%d instant source(s) • searching ALL IPTV servers..." % len(self._r732_auto_rows))
            _startup_log("PREVIEW_SEED_EXPAND",
                "sat=%r initial=%d cache_complete=NO -> full P/B1/B2" %
                (self.sat_name,len(self._r732_auto_rows)))
            try: self.candidate_expand_timer.start(20, True)
            except Exception: self._expand_selected_sat_candidates()''')

    src=one(src,'''        # Never launch dozens of expensive ranking workers when the SAT cursor moves.
        if self._expand_worker is not None and self._expand_worker.is_alive():
            return''',
'''        # One ranking worker at a time, but never abandon the latest SAT
        # selection when an old background worker is still running.
        if self._expand_worker is not None and self._expand_worker.is_alive():
            _startup_log("PREVIEW_EXPAND_WAIT",
                "sat=%r waiting_for_existing_worker=1" % clean_display_name(row.get("name") or ""))
            try: self.candidate_expand_timer.start(150, True)
            except Exception: pass
            return''')

    assert "if selected_raw != raw:" in src
    assert "def _merge_locked_candidate" in src
    assert "PREVIEW_SEED_EXPAND" in src
    compile(src,"plugin.py","exec")
    return src
