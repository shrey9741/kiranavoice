import asyncio

import pytest

from app import db
from app.extract import Extraction, Item
from evaluation import run_eval
from evaluation.make_cases import CASES


def test_cases_are_well_formed():
    from app.catalog import BY_ID
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids)) and len(CASES) >= 50
    for c in CASES:
        assert c["turns"] and c["expect"]["kind"] in ("commit", "clarify", "cancel", "none")
        for l in c["expect"].get("lines", []):
            p = BY_ID[l["product_id"]]
            assert l["unit"] == p.unit, c["id"]          # expectations are in the product unit
            assert 0 < l["qty"] <= p.stock, c["id"]      # and within stock
        if c["expect"]["kind"] == "commit":
            assert c["turns"][-1] in ("হ্যাঁ", "haan", "हाँ"), c["id"]


def test_lines_match():
    got = [{"product_id": "atta", "qty": 2.0, "unit": "kg"}]
    assert run_eval.lines_match(got, [{"product_id": "atta", "qty": 2, "unit": "kg"}])
    assert not run_eval.lines_match(got, [{"product_id": "atta", "qty": 3, "unit": "kg"}])
    assert not run_eval.lines_match(got, [{"product_id": "atta", "qty": 2, "unit": "g"}])
    assert not run_eval.lines_match(got, [])


def test_judge_flags_unsafe_commit():
    case = {"expect": {"kind": "clarify", "line_status": "ambiguous"}}
    assert not run_eval.judge(case, [[{"product_id": "atta", "qty": 1, "unit": "kg"}]], {"status": "committed", "lines": []})
    assert run_eval.judge(case, [], {"status": "pending", "lines": [{"status": "ambiguous"}]})


def test_pipelines_end_to_end_with_fake_llm(tmp_path, monkeypatch):
    """Runner logic only: a scripted fake replaces the LLM."""
    run_eval.setup_env(str(tmp_path / "e.db"))
    db.init_db()
    script = {
        "দুই কেজি আটা": Extraction(intent="order", items=[Item(phrase="আটা", qty=2, unit="kg")]),
        "এক লিটার তেল": Extraction(intent="order", items=[Item(phrase="তেল", qty=1, unit="litre")]),
        "হ্যাঁ": Extraction(intent="confirm", items=[]),
    }

    async def fake(text, cache):
        return script[text], 0.01

    monkeypatch.setattr(run_eval, "cached_extract", fake)
    good = {"id": "t1", "tag": "x", "turns": ["দুই কেজি আটা", "হ্যাঁ"],
            "expect": {"kind": "commit", "lines": [{"product_id": "atta", "qty": 2, "unit": "kg"}]}}
    amb = {"id": "t2", "tag": "x", "turns": ["এক লিটার তেল", "হ্যাঁ"],
           "expect": {"kind": "clarify", "line_status": "ambiguous"}}

    # improved pipeline: right order saved, ambiguity stops. baseline: saves immediately,
    # so it gets the clean order right but wrongly saves the ambiguous one.
    for runner, want_good, want_amb in ((run_eval.run_improved, True, True),
                                         (run_eval.run_baseline, True, False)):
        lats: list[float] = []
        o1 = asyncio.run(runner(good, {}, lats))
        o2 = asyncio.run(runner(amb, {}, lats))
        assert run_eval.judge(good, o1["orders"], o1["last"]) is want_good
        assert run_eval.judge(amb, o2["orders"], o2["last"]) is want_amb


def test_retry_after_parser():
    from app.extract import retry_after_seconds
    assert retry_after_seconds("Please try again in 2.3175s. Need more") == pytest.approx(2.3175)
    assert retry_after_seconds("Please try again in 337.5ms.") == pytest.approx(0.3375)
    assert retry_after_seconds("no hint here") == 5.0


def test_prompt_rules_present():
    from app.extract import SYSTEM
    assert "never null" in SYSTEM and '"dozen"' in SYSTEM and "পাঁচশো গ্রাম" in SYSTEM


def test_errored_cases_are_excluded_from_metrics(capsys):
    ok = {"id": "a", "tag": "t", "kind": "commit", "passed": True, "n_orders": 1}
    s = run_eval.summarize("improved", [ok], [0.5], total=3)
    out = capsys.readouterr().out
    assert "only 1 of 3" in out and s["overall"] == (1, 1)


def test_prompt_forbids_transliteration_and_dropping_the_product():
    from app.extract import SYSTEM
    assert "Never transliterate" in SYSTEM and "ONLY when no product word" in SYSTEM
