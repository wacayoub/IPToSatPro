#!/usr/bin/env python3
"""Read-only IPToSatPro / Enigma2 CPU-RAM and Preview latency diagnosis.

Designed for Vu+ Zero 4K OpenATV /proc. Does not modify service state,
Enigma2 settings, bouquets or any mapping. Never prints URLs, credentials,
raw process arguments, or IPTV catalogue entries.

Example:
  python3 /tmp/iptosat_perf_audit.py --seconds 10
Run once while ordinary TV plays; optionally again with Preview searching.
"""
import argparse
import os
import re
import statistics
import time
from pathlib import Path

BRIDGE = Path("/etc/enigma2/SatIPTVBridge")
PLUGIN = Path("/usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge")


def cpu_snapshot(path="/proc/stat"):
    with open(path, "r", encoding="ascii") as fh:
        line = fh.readline().split()
    if not line or line[0] != "cpu":
        raise ValueError("Unable to parse /proc/stat CPU")
    values = [int(x) for x in line[1:]]
    total = sum(values)
    idle = values[3] + (values[4] if len(values) > 4 else 0)
    return total, idle


def cpu_util(old, new):
    total = new[0] - old[0]
    idle = new[1] - old[1]
    return max(0.0, min(100.0, 100.0 * (total - idle) / total)) if total > 0 else 0.0


def proc_stat(pid):
    try:
        with open("/proc/%s/stat" % pid, "r", encoding="utf-8", errors="replace") as f:
            row = f.read().strip()
        # Kernel comm is bracketed in parentheses; it may itself contain spaces.
        end = row.rfind(")")
        if end == -1:
            return None
        name = row[row.find("(") + 1:end]
        fields = row[end + 2:].split()
        ticks = int(fields[11]) + int(fields[12]) # utime field 14 + stime 15
        rss_pages = int(fields[21])                # rss field 24
        threads = int(fields[17])                  # num_threads field 20
        return name, ticks, rss_pages, threads
    except (OSError, ValueError, IndexError):
        return None


def process_label(pid, comm):
    # The diagnostic is itself Python with "iptosat" in argv: never count it
    # as a real plugin background worker in CPU comparisons.
    if pid == os.getpid():
        return "AUDIT (SELF)"
    name = comm.lower()
    if "enigma2" in name:
        return "ENIGMA2"
    if "exteplayer" in name or "gstplayer" in name:
        return "IPTV PLAYER"
    if "ffmpeg" in name:
        return "FFMPEG"
    if "oscam" in name:
        return "OSCAM"
    if "iptosat" in name or "tsbridge" in name:
        return "IPTOSAT RELAY"
    # Inspect arguments ONLY to classify generic python/busybox processes.
    # Never output the args; Xtream and M3U URLs may contain credentials.
    if name in ("python", "python3", "python3.13", "sh", "busybox"):
        try:
            raw = Path("/proc/%s/cmdline" % pid).read_bytes()[:4096].lower()
            if b"satiptvbridge" in raw or b"iptosat" in raw or b"tsbridge" in raw:
                return "IPTOSAT WORKER"
        except OSError:
            pass
    return name[:26] or "?"


def processes(page_kb):
    result = {}
    try:
        entries = os.listdir("/proc")
    except OSError:
        return result
    for text_pid in entries:
        if not text_pid.isdigit():
            continue
        item = proc_stat(text_pid)
        if item is None:
            continue
        comm, ticks, rss_pages, threads = item
        pid = int(text_pid)
        result[pid] = (ticks, float(rss_pages) * page_kb / 1024.0,
                       threads, process_label(pid, comm))
    return result


def mem_available_mb():
    try:
        lines = Path("/proc/meminfo").read_text().splitlines()
        values = {}
        for row in lines:
            if ":" in row:
                k, v = row.split(":", 1)
                bits = v.split()
                if bits:
                    values[k] = int(bits[0])
        total = values.get("MemTotal", 0)
        avail = values.get("MemAvailable")
        if avail is None:
            avail = values.get("MemFree", 0) + values.get("Buffers", 0) + values.get("Cached", 0)
        return total / 1024.0, avail / 1024.0
    except (OSError, ValueError):
        return 0.0, 0.0


def log_latency():
    log = BRIDGE / "bridge.log"
    try:
        with open(log, "rb") as fp:
            fp.seek(0, 2)
            size = fp.tell()
            fp.seek(max(0, size - 262144))
            content = fp.read().decode("utf-8", errors="replace")
    except OSError:
        return [], []
    rank = [s.strip() for s in content.splitlines()
            if "PREVIEW_RANK_BG" in s]
    keep = [s.strip() for s in content.splitlines()
            if "FTA_SIGNAL_KEEP_SAT" in s or "NO_SIGNAL_FAST_TRY" in s]
    output = []
    for line in rank[-30:]:
        vals = dict(re.findall(r"\b(elapsed|index|scoring|candidate_count|cache)=(\d+)", line))
        if "elapsed" not in vals:
            continue
        output.append({"ms": int(vals["elapsed"]),
                       "index_ms": int(vals.get("index", "0")),
                       "score_ms": int(vals.get("scoring", "0")),
                       "count": int(vals.get("candidate_count", "0")),
                       "cached": vals.get("cache", "?") == "1"})
    return output, keep[-5:]


def markers():
    expected = {
        "BEIN_AAC_DIRECT": (PLUGIN / "monitor.py", "R74_TOD_BEIN_DIRECT_AUDIO"),
        "FTA_KEEP_SAT": (PLUGIN / "monitor.py", "R7417_FTA_SIGNAL_NATIVE_GUARD"),
        "PREVIEW_24": (PLUGIN / "plugin.py", "R7412_FAST_PREVIEW_SHORTLIST"),
        "PREVIEW_FIRST_PAINT": (PLUGIN / "plugin.py", "R7415_FIRSTPAINT_GREEN_ANY_FOCUS"),
        "PREVIEW_UNMAP": (PLUGIN / "plugin.py", "R7416_UNMAP_CRYPT_ACCESS"),
    }
    results = {}
    texts = {}
    for name, (file, tag) in expected.items():
        try:
            if file not in texts:
                texts[file] = file.read_text(encoding="utf-8", errors="replace")
            results[name] = tag in texts[file]
        except OSError:
            results[name] = False
    return results


def report(seconds, sleep_fn=time.sleep):
    duration = max(3, min(30, int(seconds)))
    hz = float(os.sysconf("SC_CLK_TCK"))
    page_kb = float(os.sysconf("SC_PAGE_SIZE")) / 1024.0
    versions = markers()
    initial_mem = mem_available_mb()
    initial_load = os.getloadavg() if hasattr(os, "getloadavg") else (0.0, 0.0, 0.0)
    start = time.monotonic()
    old_cpu = cpu_snapshot()
    old_procs = processes(page_kb)
    peak = {}
    ticks_sum = {}
    last_rss = {}
    max_threads = {}
    system = []
    while time.monotonic() - start < duration:
        remaining = duration - (time.monotonic() - start)
        sleep_fn(min(1.0, max(0.0, remaining)))
        new_cpu = cpu_snapshot()
        new_procs = processes(page_kb)
        system.append(cpu_util(old_cpu, new_cpu))
        elapsed = max(0.01, time.monotonic() - start)
        for pid, (ticks, rss, threads, label) in new_procs.items():
            old = old_procs.get(pid)
            if old is None or old[3] != label or ticks < old[0]:
                continue
            cpu_diff = ticks - old[0]
            # one-core percent: 100% means one hardware core fully used.
            utilization = 100.0 * cpu_diff / hz
            # The samples are close to 1 second; cap only for protection
            # against momentary scheduler delays, not at 100% on multicore.
            # Track exact consumed CPU time for duration-average.
            ticks_sum[(pid, label)] = ticks_sum.get((pid, label), 0) + cpu_diff
            peak[(pid, label)] = max(peak.get((pid, label), 0.0), utilization)
            last_rss[(pid, label)] = rss
            max_threads[(pid, label)] = max(max_threads.get((pid, label), 0), threads)
        old_cpu, old_procs = new_cpu, new_procs
    wall = max(0.01, time.monotonic() - start)
    total_mem, avail_mem = mem_available_mb()
    ranks, guard = log_latency()
    processes_cpu = []
    for key, ticks in ticks_sum.items():
        pid, label = key
        avg = 100.0 * ticks / hz / wall
        processes_cpu.append((avg, peak.get(key, 0.0), label, pid,
                              last_rss.get(key, 0.0), max_threads.get(key, 0)))
    processes_cpu.sort(reverse=True)
    print("=== IPToSatPro read-only performance audit ===")
    print("Sampling: %.1f seconds; device cores = logical CPUs; 100%% process CPU = one full core" % wall)
    print("System CPU: avg %.1f%%; peak one-second %.1f%%" %
          (statistics.mean(system) if system else 0.0, max(system or [0.0])))
    print("System load (1,5,15 min): %.2f %.2f %.2f" % initial_load)
    print("RAM: total %.1f MB, available %.1f -> %.1f MB (change %+.1f MB)" %
          (total_mem or initial_mem[0], initial_mem[1], avail_mem, avail_mem - initial_mem[1]))
    print("Runtime hotfix markers (loaded after GUI restart only):")
    for k, v in sorted(versions.items()):
        print("  %-22s %s" % (k, "on-disk present" if v else "not detected"))
    print("CPU by process (average 1-core%%, one-second peak CPU%%, RSS MB, threads):")
    if not processes_cpu:
        print("  No running processes read")
    else:
        for avg, p, label, pid, rss, threads in processes_cpu[:9]:
            print("  %-19s pid=%-5d avg=%5.1f%% peak=%5.1f%% RAM=%6.1fMB threads=%d" %
                  (label, pid, avg, p, rss, threads))
    focus = [entry for entry in processes_cpu if "IPTOSAT" in entry[2] or entry[2] == "ENIGMA2"]
    if not focus:
        print("WARNING: Enigma2 process not detected; make sure GUI is running")
    recent = ranks[-6:]
    print("Recent Preview ranking (historical log entries, not current CPU measurement):")
    if recent:
        for r in recent:
            print("  %-5s %4d results total=%5dms index=%5dms score=%5dms" %
                  ("CACHE" if r["cached"] else "FRESH", r["count"], r["ms"],
                   r["index_ms"], r["score_ms"]))
    else:
        print("  No PREVIEW_RANK_BG entries found in last 256 KiB")
    print("DVB fallback evidence: %d recent keep-SAT/no-signal log lines" % len(guard))
    print("Audit read-only; no plugins, mappings or services were modified")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=int, default=10,
                        help="sampling period (3 to 30s, default 10)")
    args = parser.parse_args()
    report(args.seconds)


if __name__ == "__main__":
    main()
