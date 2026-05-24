import subprocess
import tempfile
import os
import json
import datetime
from config import BENCHMARK_RUNS, BENCHMARK_TIMEOUT, LOG_DIR

BENCHMARK_LOG = os.path.join(LOG_DIR, "benchmarks.jsonl")


def _write_temp(code: str) -> str:
    """Write code to a temp file with UTF-8 encoding. Returns temp path."""
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".py",
        delete=False,
        encoding="utf-8"
    ) as f:
        f.write(code)
        return f.name


def benchmark_code(code: str, runs: int = None) -> dict:
    """
    Benchmark code using timeit (runtime) and tracemalloc (memory).
    Returns {avg_ms, min_ms, max_ms, peak_kb, runs, success, error}
    """
    if runs is None:
        runs = BENCHMARK_RUNS

    # Build a benchmarking wrapper script
    wrapper = f"""
import timeit
import tracemalloc
import sys

_code = {repr(code)}

# Runtime benchmark
try:
    timer = timeit.Timer(stmt=compile(_code, '<string>', 'exec'), setup='pass')
    times = timer.repeat(repeat={runs}, number=1)
    times_ms = [t * 1000 for t in times]
    avg_ms = sum(times_ms) / len(times_ms)
    min_ms = min(times_ms)
    max_ms = max(times_ms)
except Exception as e:
    avg_ms = min_ms = max_ms = -1

# Memory benchmark
try:
    tracemalloc.start()
    exec(compile(_code, '<string>', 'exec'), {{}})
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_kb = peak / 1024
except Exception:
    peak_kb = -1

print(f"{{avg_ms:.4f}},{{min_ms:.4f}},{{max_ms:.4f}},{{peak_kb:.4f}}")
"""
    tmp_path = _write_temp(wrapper)
    try:
        result = subprocess.run(
            ["python", tmp_path],
            capture_output=True,
            timeout=BENCHMARK_TIMEOUT,
            encoding="utf-8",
            errors="replace"
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {
                "avg_ms": None, "min_ms": None, "max_ms": None,
                "peak_kb": None, "runs": runs,
                "success": False, "error": result.stderr.strip()
            }
        parts = result.stdout.strip().split(",")
        avg_ms = float(parts[0])
        min_ms = float(parts[1])
        max_ms = float(parts[2])
        peak_kb = float(parts[3])
        return {
            "avg_ms": round(avg_ms, 4),
            "min_ms": round(min_ms, 4),
            "max_ms": round(max_ms, 4),
            "peak_kb": round(peak_kb, 2),
            "runs": runs,
            "success": True,
            "error": ""
        }
    except subprocess.TimeoutExpired:
        return {
            "avg_ms": None, "min_ms": None, "max_ms": None,
            "peak_kb": None, "runs": runs,
            "success": False, "error": "Benchmark timed out"
        }
    except Exception as e:
        return {
            "avg_ms": None, "min_ms": None, "max_ms": None,
            "peak_kb": None, "runs": runs,
            "success": False, "error": str(e)
        }
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def benchmark_memory_only(code: str) -> dict:
    """Fast memory-only benchmark using tracemalloc."""
    wrapper = f"""
import tracemalloc
_code = {repr(code)}
tracemalloc.start()
try:
    exec(compile(_code, '<string>', 'exec'), {{}})
except Exception:
    pass
current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
print(f"{{peak / 1024:.4f}}")
"""
    tmp_path = _write_temp(wrapper)
    try:
        result = subprocess.run(
            ["python", tmp_path],
            capture_output=True,
            timeout=BENCHMARK_TIMEOUT,
            encoding="utf-8",
            errors="replace"
        )
        if result.returncode == 0 and result.stdout.strip():
            return {"peak_kb": round(float(result.stdout.strip()), 2), "success": True}
        return {"peak_kb": None, "success": False, "error": result.stderr.strip()}
    except Exception as e:
        return {"peak_kb": None, "success": False, "error": str(e)}
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


def compare(before: dict, after: dict) -> dict:
    """Compute improvement deltas between before and after benchmarks."""
    result = {"runtime_delta_pct": None, "memory_delta_pct": None, "improved": False}

    if before.get("avg_ms") and after.get("avg_ms") and before["avg_ms"] > 0:
        delta = ((after["avg_ms"] - before["avg_ms"]) / before["avg_ms"]) * 100
        result["runtime_delta_pct"] = round(delta, 2)
        result["runtime_improved"] = delta < 0

    if before.get("peak_kb") and after.get("peak_kb") and before["peak_kb"] > 0:
        delta = ((after["peak_kb"] - before["peak_kb"]) / before["peak_kb"]) * 100
        result["memory_delta_pct"] = round(delta, 2)
        result["memory_improved"] = delta < 0

    result["improved"] = bool(
        result.get("runtime_improved") or result.get("memory_improved")
    )
    return result


def log_benchmark(task: str, before: dict, after: dict, comparison: dict):
    """Append benchmark results to the log file."""
    record = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "task": task,
        "before": before,
        "after": after,
        "comparison": comparison
    }
    os.makedirs(LOG_DIR, exist_ok=True)
    with open(BENCHMARK_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
