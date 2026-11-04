"""Text-level evaluation of the order pipeline (speech-to-text is measured separately).

  python -m evaluation.run_eval --mode both

improved = the real pipeline: LLM extraction -> catalogue matching -> validation ->
           clarification -> confirmation -> atomic commit.
baseline = naive: LLM extraction -> first catalogue match -> save immediately.
           No clarification, no unit/stock checks, no confirmation.

LLM answers are cached (evaluation/.llm_cache.json) so re-runs are free and both modes
see identical extractions. The cache is invalidated when the prompt or model changes."""
import argparse
import asyncio
import hashlib
import json
import os
import statistics
import time
from pathlib import Path

HERE = Path(__file__).parent
CACHE_PATH = HERE / ".llm_cache.json"
CASES_PATH = HERE / "cases.jsonl"
HELDOUT_PATH = HERE / "heldout_cases.jsonl"


def setup_env(db_path: str | None = None) -> None:
    """Use a separate database so the demo store is never touched."""
    from dotenv import load_dotenv
    load_dotenv(HERE.parent / ".env")
    os.environ["KIRANA_DB"] = db_path or str(HERE / "eval.db")


# ---------------------------------------------------------------- judging

def lines_match(got: list[dict], expected: list[dict]) -> bool:
    if len(got) != len(expected):
        return False
    g = {l["product_id"]: (l["qty"], l["unit"]) for l in got}
    for e in expected:
        if e["product_id"] not in g:
            return False
        qty, unit = g[e["product_id"]]
        if abs(qty - e["qty"]) > 1e-6 or unit != e["unit"]:
            return False
    return True


def judge(case: dict, orders: list[list[dict]], last: dict) -> bool:
    exp = case["expect"]
    kind = exp["kind"]
    if kind == "commit":
        return len(orders) == 1 and lines_match(orders[0], exp["lines"])
    if orders:  # anything saved when we should not have saved is a failure
        return False
    if kind == "clarify":
        return any(l["status"] == exp["line_status"] for l in last.get("lines", []))
    if kind == "cancel":
        return last["status"] == "cancelled"
    if kind == "none":
        return last["status"] == "none"
    return False


# ---------------------------------------------------------------- LLM cache

def _key(text: str) -> str:
    from app.extract import SYSTEM
    return hashlib.sha256((os.environ.get("GROQ_MODEL", "default") + SYSTEM + text).encode()).hexdigest()


async def cached_extract(text: str, cache: dict):
    from fastapi import HTTPException
    from app.extract import Extraction, extract

    k = _key(text)
    if k in cache:
        return Extraction.model_validate(cache[k]["ex"]), cache[k]["latency"]
    from app.extract import retry_after_seconds
    for attempt in range(15):
        t0 = time.perf_counter()
        try:
            ex = await extract(text)
            break
        except HTTPException as e:  # wait out rate limits instead of failing the case
            msg = str(e.detail)
            if ("429" in msg or "Rate limit" in msg) and attempt < 14:
                await asyncio.sleep(min(retry_after_seconds(msg) + 0.5, 30))
                continue
            raise
    lat = time.perf_counter() - t0
    cache[k] = {"ex": ex.model_dump(), "latency": lat}
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return ex, lat


# ---------------------------------------------------------------- pipelines

async def run_improved(case: dict, cache: dict, lats: list[float]) -> dict:
    from app import db, flow
    db.reset_demo()
    flow.SESSIONS.clear()
    flow.COMMITTED.clear()
    last: dict = {"status": "none", "lines": []}
    for turn in case["turns"]:
        ex, lat = await cached_extract(turn, cache)
        t0 = time.perf_counter()
        last = flow.handle_turn(case["id"], turn, ex)
        lats.append(lat + time.perf_counter() - t0)
    orders = [[{"product_id": i["product_id"], "qty": i["qty"], "unit": i["unit"]} for i in o["items"]]
              for o in db.list_orders(50)]
    return {"orders": orders, "last": {"status": last["status"], "lines": last["lines"]}}


async def run_baseline(case: dict, cache: dict, lats: list[float]) -> dict:
    from app.catalog import BY_ID
    from app.matcher import match
    orders: list[list[dict]] = []
    status = "none"
    for turn in case["turns"]:
        ex, lat = await cached_extract(turn, cache)
        lats.append(lat)
        if ex.intent == "order" and ex.items:
            lines = []
            for it in ex.items:
                m = match(it.phrase)
                if m.status == "unknown":
                    continue
                pid = m.product_ids[0]  # picks the first candidate, never asks
                lines.append({"product_id": pid, "qty": it.qty if it.qty is not None else 1.0,
                              "unit": BY_ID[pid].unit})  # unit conversion ignored
            if lines:
                orders.append(lines)
        status = "committed" if orders else ("cancelled" if ex.intent == "reject" else "none")
    return {"orders": orders, "last": {"status": status, "lines": []}}


# ---------------------------------------------------------------- reporting

def pct(n: int, d: int) -> str:
    return f"{100 * n / d:5.1f}%  ({n}/{d})" if d else "n/a"


def percentile(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def summarize(mode: str, results: list[dict], lats: list[float], total: int | None = None) -> dict:
    commit = [r for r in results if r["kind"] == "commit"]
    clarify = [r for r in results if r["kind"] == "clarify"]
    safe_kinds = [r for r in results if r["kind"] != "commit"]
    s = {
        "mode": mode,
        "order_accuracy": (sum(r["passed"] for r in commit), len(commit)),
        "task_completion": (sum(1 for r in commit if r["n_orders"] >= 1), len(commit)),
        "clarification_correct": (sum(r["passed"] for r in clarify), len(clarify)),
        "unsafe_commits": (sum(1 for r in safe_kinds if r["n_orders"] > 0), len(safe_kinds)),
        "overall": (sum(r["passed"] for r in results), len(results)),
        "latency_p50": percentile(lats, 0.5),
        "latency_p95": percentile(lats, 0.95),
    }
    print(f"\n=== {mode.upper()} ===")
    if total is not None and total != len(results):
        print(f"WARNING: only {len(results)} of {total} cases were evaluated; "
              f"{total - len(results)} hit API errors and are excluded. Re-run to continue "
              f"(finished LLM calls are cached).")
    print(f"Order exact-match accuracy : {pct(*s['order_accuracy'])}")
    print(f"Task completion (committed): {pct(*s['task_completion'])}")
    print(f"Correct clarification      : {pct(*s['clarification_correct'])}")
    print(f"UNSAFE commits (target 0)  : {s['unsafe_commits'][0]} of {s['unsafe_commits'][1]} non-order cases")
    print(f"Overall pass               : {pct(*s['overall'])}")
    print(f"LLM+rules latency per turn : p50 {s['latency_p50']:.2f}s   p95 {s['latency_p95']:.2f}s")
    tags = sorted({r["tag"] for r in results})
    print("By group: " + "   ".join(
        f"{t} {sum(r['passed'] for r in results if r['tag'] == t)}/{sum(1 for r in results if r['tag'] == t)}"
        for t in tags))
    return s


async def main_async(args) -> None:
    setup_env()
    from app import db
    db.init_db()

    heldout = args.cases == "heldout"
    cases_path = HELDOUT_PATH if heldout else CASES_PATH
    cases = [json.loads(l) for l in cases_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.only:
        cases = [c for c in cases if c["id"] in args.only.split(",")]
    if args.limit:
        cases = cases[: args.limit]
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}

    modes = ["improved", "baseline"] if args.mode == "both" else [args.mode]
    report = {}
    for mode in modes:
        runner = run_improved if mode == "improved" else run_baseline
        results, lats = [], []
        for c in cases:
            try:
                out = await runner(c, cache, lats)
                passed = judge(c, out["orders"], out["last"])
                err = None
            except Exception as e:  # an API failure counts as a failed case, never a pass
                out, passed, err = {"orders": [], "last": {"status": "error", "lines": []}}, False, repr(e)
            results.append({"id": c["id"], "tag": c["tag"], "kind": c["expect"]["kind"],
                            "turns": c["turns"], "expected": c["expect"], "passed": passed,
                            "n_orders": len(out["orders"]), "orders": out["orders"],
                            "last_status": out["last"]["status"],
                            "last_line_statuses": [l["status"] for l in out["last"].get("lines", [])],
                            "error": err})
            print(f"{c['id']} {'PASS' if passed else 'FAIL'}", end="  ", flush=True)
        print()
        evaluated = [x for x in results if not x["error"]]
        errored = [x for x in results if x["error"]]
        report[mode] = {"summary": summarize(mode, evaluated, lats, total=len(results)), "results": results}
        if errored:
            print(f"{len(errored)} cases errored, e.g. {errored[0]['id']}: {errored[0]['error'][:200]}")

        fails = [x for x in evaluated if not x["passed"]]
        if fails:
            print(f"\n--- {mode}: {len(fails)} failing cases ---")
            for r in fails:
                print(f"{r['id']} [{r['tag']}] turns={r['turns']}")
                print(f"    expected={json.dumps(r['expected'], ensure_ascii=False)}")
                print(f"    got: orders={r['orders']} status={r['last_status']} "
                      f"lines={r['last_line_statuses']} {r['error'] or ''}")

    out_name = "results_heldout.json" if heldout else "results.json"
    (HERE / out_name).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved evaluation/{out_name}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["improved", "baseline", "both"], default="both")
    ap.add_argument("--cases", choices=["dev", "heldout"], default="dev",
                    help="dev = cases.jsonl (tuned on), heldout = heldout_cases.jsonl (never tuned on)")
    ap.add_argument("--only", help="comma-separated case ids, e.g. c01,c02")
    ap.add_argument("--limit", type=int)
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
