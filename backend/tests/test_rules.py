import pytest

from app.extract import Extraction, Item, parse_extraction
from app.rules import build_proposal


def order(*items):
    return Extraction(intent="order", items=[Item(phrase=p, qty=q, unit=u) for p, q, u in items])


def test_simple_order_can_be_confirmed():
    r = build_proposal(order(("আটা", 2, "kg")))
    assert r["can_confirm"] and r["total"] == 90 and r["lines"][0]["status"] == "ok"


def test_generic_oil_needs_clarification():
    r = build_proposal(order(("তেল", 1, "litre")))
    assert not r["can_confirm"]
    assert r["lines"][0]["status"] == "ambiguous"
    assert set(r["lines"][0]["options"]) == {"mustard_oil", "sunflower_oil"}
    assert r["questions"]


def test_out_of_stock_blocks_commit():
    r = build_proposal(order(("আটা", 500, "kg")))
    assert not r["can_confirm"] and r["lines"][0]["status"] == "out_of_stock"


def test_grams_convert_to_kg():
    r = build_proposal(order(("আটা", 500, "g")))
    assert r["lines"][0]["qty"] == 0.5 and r["total"] == 22.5 and r["can_confirm"]


def test_wrong_unit_asks_instead_of_guessing():
    r = build_proposal(order(("আটা", 2, "litre")))
    assert r["lines"][0]["status"] == "unit_mismatch" and not r["can_confirm"]


def test_missing_quantity_is_not_guessed():
    r = build_proposal(order(("চিনি", None, None)))
    assert r["lines"][0]["status"] == "bad_qty" and not r["can_confirm"]


def test_zero_or_negative_quantity_rejected():
    assert build_proposal(order(("চিনি", 0, "kg")))["lines"][0]["status"] == "bad_qty"
    assert build_proposal(order(("চিনি", -2, "kg")))["lines"][0]["status"] == "bad_qty"


def test_unknown_product_never_committed():
    r = build_proposal(order(("laptop", 1, "piece")))
    assert r["lines"][0]["status"] == "unknown" and not r["can_confirm"]


def test_one_bad_line_blocks_whole_order():
    r = build_proposal(order(("আটা", 2, "kg"), ("তেল", 1, "litre")))
    assert not r["can_confirm"] and r["total"] == 90


def test_confirm_intent_is_not_an_order():
    r = build_proposal(Extraction(intent="confirm", items=[]))
    assert r["lines"] == [] and not r["can_confirm"]


def test_parse_extraction_handles_code_fences():
    raw = '```json\n{"intent":"order","items":[{"phrase":"আটা","qty":2,"unit":"kg"}]}\n```'
    assert parse_extraction(raw).items[0].phrase == "আটা"


def test_parse_extraction_rejects_garbage():
    with pytest.raises(ValueError):
        parse_extraction("not json")


def test_tiny_quantity_is_questioned_not_saved():
    r = build_proposal(order(("নুন", 2.5, "g")))  # "250 g" misread as 2.5 g
    assert r["lines"][0]["status"] == "implausible_qty" and not r["can_confirm"]
    assert r["questions"] and "খুব কম" in r["questions"][0]


def test_normal_small_quantities_still_pass():
    assert build_proposal(order(("নুন", 250, "g")))["can_confirm"]
    assert build_proposal(order(("চিনি", 0.5, "kg")))["can_confirm"]


def test_half_a_piece_is_questioned():
    r = build_proposal(order(("সাবান", 0.5, "piece")))
    assert r["lines"][0]["status"] == "implausible_qty" and not r["can_confirm"]


def test_half_a_dozen_eggs_is_fine():
    assert build_proposal(order(("ডিম", 0.5, "dozen")))["can_confirm"]
