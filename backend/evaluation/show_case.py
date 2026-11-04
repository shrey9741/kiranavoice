"""Shows what the LLM extracted for each turn of a case and how the matcher read it.
Uses the cache, so it costs nothing.   python -m evaluation.show_case c28 c43"""
import json
import sys

from evaluation.run_eval import CACHE_PATH, CASES_PATH, HELDOUT_PATH, _key, setup_env


def main() -> None:
    setup_env()
    from app.matcher import match

    ids = sys.argv[1:]
    cases = []
    for path in (CASES_PATH, HELDOUT_PATH):
        if path.exists():
            cases += [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    cache = json.loads(CACHE_PATH.read_text(encoding="utf-8")) if CACHE_PATH.exists() else {}
    for c in cases:
        if ids and c["id"] not in ids:
            continue
        print(f"\n{c['id']} [{c['tag']}] expect={json.dumps(c['expect'], ensure_ascii=False)}")
        for turn in c["turns"]:
            hit = cache.get(_key(turn))
            print(f"  turn: {turn!r}")
            if not hit:
                print("    (not in cache)")
                continue
            ex = hit["ex"]
            print(f"    intent={ex['intent']}")
            for it in ex["items"]:
                m = match(it["phrase"])
                print(f"    item phrase={it['phrase']!r} qty={it['qty']} unit={it['unit']} -> "
                      f"{m.status} {m.product_ids} {m.score:.0f}")


if __name__ == "__main__":
    main()
