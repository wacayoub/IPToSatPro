"""r70 Preview/All Sources async ranking: UI-free workers, bounded GUI updates.

This module modifies only the manual mapping/preview screen's deferred full
candidate ranking callback. It DOES NOT touch the playback or service engine.
"""
import functools
import threading
import time


def attach_alternatives(cls, namespace):
    if getattr(cls, "_r70_async_rank_attached", False):
        return cls
    original = getattr(cls, "_load_all_servers", None)
    stop = getattr(cls, "_stop_zap_timer", None)
    timer_type = namespace.get("eTimer")
    if not callable(original) or not callable(stop) or timer_type is None:
        return cls

    def _poll(self):
        if not getattr(self, "_r70_rank_alive", True):
            return
        worker = getattr(self, "_r70_rank_worker", None)
        if worker is not None and worker.is_alive():
            try: self._r70_rank_poll_timer.start(110, True)
            except Exception: pass
            return
        result = getattr(self, "_r70_rank_result", None)
        self._r70_rank_worker = None
        self._r70_rank_result = None
        if result:
            ref, sat_name, rows, error, elapsed_ms = result
            latest = str(getattr(self, "sat_ref_string", "") or "")
            if (ref == latest and not self.search_query and not self.browse_mode
                    and self.server_filter == "ALL" and self.group_filter == "ALL"):
                if not error:
                    # Selection restoration by fingerprint remains inside _render.
                    self.ranked = list(rows)
                    self._render()
                    try:
                        self["detail"].setText(
                            "ALL SOURCES READY • %d candidates • local index • %d ms • 8/9 bouquet pages"
                            % (len(rows), elapsed_ms))
                    except Exception:
                        pass
                else:
                    try: self["detail"].setText(
                        "All Servers ranking failed; cached quick candidates remain available")
                    except Exception: pass
        # A newer selected SAT channel was queued while the previous worker ran.
        # Spawn only one new job and never apply an obsolete result.
        wanted = getattr(self, "_r70_rank_wanted", None)
        self._r70_rank_wanted = None
        if wanted and wanted != (getattr(self, "sat_ref_string", None),
                                getattr(self, "sat_name", None)):
            return  # no longer current
        if wanted and not self.search_query and not self.browse_mode:
            self._load_all_servers()

    @functools.wraps(original)
    def deferred(self):
        if (self.search_query or self.browse_mode or
                self.server_filter != "ALL" or self.group_filter != "ALL"):
            return
        try:
            selected_ref = str(self.sat_ref_string or "")
            sat_name = str(self.sat_name or "")
            ctx = dict(self.context or {})
            catalog = self._catalog()
            if catalog is None or not getattr(catalog, "channels", None):
                return
            cfg = namespace["cfg"]
            priorities = [x.strip().upper() for x in cfg.languages.value.split(",") if x.strip()]
            quality_mode = cfg.quality_mode.value
            timer = getattr(self, "_r70_rank_poll_timer", None)
            if timer is None:
                timer = timer_type()
                timer.callback.append(lambda: _poll(self))
                self._r70_rank_poll_timer = timer
            self._r70_rank_alive = True
            worker = getattr(self, "_r70_rank_worker", None)
            if worker is not None and worker.is_alive():
                self._r70_rank_wanted = (selected_ref, sat_name)
                try: timer.start(110, True)
                except Exception: pass
                return
            # Do not touch the GUI, session/nav, filesystem or satellite
            # service APIs from the thread. Snapshot all settings on GUI turn.
            self._r70_rank_wanted = None
            self._r70_rank_result = None

            def rank():
                started = time.monotonic()
                try:
                    rows = catalog.fast_rank_matches_all_servers(
                        sat_name, priorities, context=ctx, per_server=16,
                        topn=self.MAX_VISIBLE_CANDIDATES, quality_mode=quality_mode)
                    error = ""
                except Exception as e:
                    rows, error = [], e.__class__.__name__
                elapsed = int((time.monotonic() - started) * 1000)
                # Plain data assignment only; the GUI polling thread applies it.
                self._r70_rank_result = (selected_ref, sat_name, rows, error, elapsed)
            task = threading.Thread(target=rank, name="IPToSatPreviewAllSources")
            task.daemon = True
            self._r70_rank_worker = task
            task.start()
            try:
                self["detail"].setText(
                    "Quick candidates ready • preparing ALL servers in background • "
                    "BLUE preview works now")
            except Exception:
                pass
            timer.start(110, True)
        except Exception:
            # Safe fallback retains the original known-good manual screen.
            try: original(self)
            except Exception: pass

    @functools.wraps(stop)
    def stop_all(self):
        self._r70_rank_alive = False
        try: self._r70_rank_poll_timer.stop()
        except Exception: pass
        return stop(self)

    cls._load_all_servers = deferred
    cls._stop_zap_timer = stop_all
    cls._r70_async_rank_attached = True
    return cls
