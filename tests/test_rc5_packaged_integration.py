#!/usr/bin/env python3
"""Real packaged monitor player/failure/retry methods against fake Enigma2 I/O.

No tuner, decoder, network, installed plugin or receiver configuration.
This verifies control-flow integration, not actual video/audio playback.
"""
import ast
import io
import os
import subprocess
import tarfile
import time
from pathlib import Path
from types import SimpleNamespace as S

ROOT = Path(__file__).resolve().parents[1]
IPK = ROOT / "r70-candidate.ipk"
RELPATH = "./usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/"


def packaged_python():
    compressed = subprocess.check_output(["ar", "p", str(IPK), "data.tar.gz"])
    with tarfile.open(fileobj=io.BytesIO(compressed), mode="r:gz") as tar:
        return {name: tar.extractfile(RELPATH + name).read().decode("utf-8")
                for name in ("monitor.py", "player_recovery_rc5.py")}


def compile_real_monitor(package):
    source = package["monitor.py"]
    tree = ast.parse(source)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name == "SatFallbackMonitor")
    required = {"_playback_plan", "_handle_iptv_failure", "_retry_fallback"}
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef)
               and n.name in required]
    assert {n.name for n in methods} == required
    compiled = ast.fix_missing_locations(ast.Module(body=[ast.ClassDef(
        name="PublishedMonitorMethods", bases=[], keywords=[], body=methods,
        decorator_list=[])], type_ignores=[]))
    ns = {"time": time, "os": os,
          "effective_quality_info": lambda c: ("FHD", 500, "virtual"),
          "channel_fingerprint": lambda c: c.get("id", ""),
          "unquote": lambda value: value}
    exec(compile(compiled, "packaged monitor.py", "exec"), ns)
    player_ns = {"__name__": "rc5_package_adapter"}
    exec(compile(package["player_recovery_rc5.py"],
                 "packaged player_recovery_rc5.py", "exec"), player_ns)
    return ns["PublishedMonitorMethods"], player_ns["attach_recovery"]


class Timer:
    def __init__(self):
        self.started = []
    def stop(self):
        return None
    def start(self, delay, single):
        self.started.append((delay, single))


def make_monitor(base):
    class Fake(base):
        def __init__(self, configured="auto", mode="5002", audio=False,
                     forced="auto", retry=True, uhd=False, locked=False,
                     can_5002=True):
            self.cfg = S(service_type=S(value=configured),
                         retry_failed_stream=S(value=retry), enabled=S(value=True),
                         native_timeshift=S(value="xtream"),
                         openatv_playback=S(value=True),
                         uhd_playback=S(value="stable"))
            self.pending_match = {"id": "m-laliga", "name": "M+ LALIGA HD",
                                  "url": "http://mock.invalid/hls.m3u8"}
            self.last_match = None
            self.stream_health = {}
            self.serviceapp_5002_available = can_5002
            self.mode, self.forced, self.audio = mode, forced, audio
            self.target_quality_rank = 650 if uhd else 0
            self.current_sat_ref = object()
            self.current_sat_name = "M+ LALIGA HD"
            self.current_play_mode = ""
            self.playback_locked = locked
            self.counters = {"retries": 0, "failures": 0, "black_streams": 0}
            self.player_status = {"5002": "", "4097": "", "dvb": ""}
            self.candidate_plan = [self.pending_match]
            self.candidate_index = 0
            self.fallback_attempt = 0
            self.start_guard_timer, self.retry_timer = Timer(), Timer()
            self.retry_pending = False
            self.retry_kind = ""
            self.forced_retry_mode = ""
            self.pending_score = 100
            self.logs = []
            self.modes = []
            self.next_candidate_called = 0
        def _current_player_override(self): return self.forced
        def _safe_serviceapp_mode(self): return self.mode
        def _audio_safe_serviceapp_required(self, ch): return self.audio
        def _audio_sensitive_stream(self, ch): return self.audio
        def _stream_transport_kind(self, ch): return "hls"
        def _log(self, *args): self.logs.append(args)
        def _schedule_health_save(self): return None
        def _set_state(self, *args): return None
        def _retry_release_ms(self): return 180
        def _restore_sat_for_release(self): return None
        def _schedule_next_candidate(self, *args, **kwargs):
            self.next_candidate_called += 1
        def _play_match(self, match, score, retry=False):
            # Mode-selection logic copied from actual r69 _play_match.
            # Enigma2 playService() and other hardware operations are stubbed.
            if not retry: self.fallback_attempt = 1
            else: self.fallback_attempt += 1; self.counters["retries"] += 1
            plan = self._playback_plan()
            forced_mode = str(self.forced_retry_mode or "") if retry else ""
            if forced_mode:
                mode = forced_mode
                self.forced_retry_mode = ""
            else:
                mode = plan[min(self.fallback_attempt - 1, len(plan) - 1)]
            self.current_play_mode = mode
            self.modes.append(mode)
    return Fake


def verify_case(name, monitor, expected, retry):
    monitor._play_match(monitor.pending_match, 100)
    assert monitor.modes == expected[:1], (name, monitor.modes)
    monitor._handle_iptv_failure("No decoded IPTV video")
    assert monitor.retry_pending == retry, (name, monitor.logs)
    if retry:
        monitor._retry_fallback()
    assert monitor.modes == expected, (name, monitor.modes, expected)
    print("PASS", name, "modes=", monitor.modes)


def main():
    assert IPK.is_file(), "Build the RC5 IPK before integration test"
    base, attach = compile_real_monitor(packaged_python())
    Fake = make_monitor(base)
    attach(Fake)
    verify_case("5002 failure -> 4097", Fake(), ["5002", "4097"], True)
    verify_case("4097 failure -> 5002", Fake(mode="4097"), ["4097", "5002"], True)
    verify_case("4097 without 5002", Fake(mode="4097", can_5002=False), ["4097"], False)
    verify_case("TOD audio protected", Fake(audio=True), ["5002"], False)
    verify_case("Manual ServiceApp lock", Fake(forced="serviceapp"), ["5002"], False)
    verify_case("Retry disabled", Fake(retry=False), ["5002"], False)
    verify_case("Fixed player", Fake(configured="5002"), ["5002"], False)
    verify_case("Existing UHD player plan", Fake(uhd=True), ["5002", "dvb"], True)
    verified = Fake(locked=True)
    verified._play_match(verified.pending_match, 100)
    verified._handle_iptv_failure("late event after picture")
    assert verified.modes == ["5002"] and not verified.retry_pending
    print("PASS verified video ignores late failure")
    failed = Fake()
    failed._play_match(failed.pending_match, 100)
    failed._handle_iptv_failure("No decoded IPTV video")
    failed._retry_fallback()
    failed._handle_iptv_failure("No decoded IPTV video on alternate player")
    assert failed.modes == ["5002", "4097"]
    assert failed.next_candidate_called == 1 and not failed.retry_pending
    print("PASS bounded fallback after both players fail")
    print("PASS 10 packaged RC5 monitor state-machine checks; decoder/audio not simulated")


if __name__ == "__main__":
    main()
