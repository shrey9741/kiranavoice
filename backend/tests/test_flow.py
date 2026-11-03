import sqlite3

import pytest

from app import db, flow
from app.extract import Extraction, Item


@pytest.fixture(autouse=True)
def fresh(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setenv("KIRANA_DB", str(path))
    db.init_db()
    flow.SESSIONS.clear()
    flow.COMMITTED.clear()
    return path


def say(session, text, intent="order", *items):
    return flow.handle_turn(session, text, Extraction(
        intent=intent, items=[Item(phrase=p, qty=q, unit=u) for p, q, u in items]))


def stock(pid):
    return db.get_products()[pid].stock


def test_nothing_is_saved_before_confirmation():
    r = say("s", "atta", "order", ("আটা", 2, "kg"))
    assert r["status"] == "pending" and r["can_confirm"]
    assert db.list_orders() == [] and stock("atta") == 50


def test_voice_confirm_commits_once_and_reduces_stock():
    say("s", "atta", "order", ("আটা", 2, "kg"))
    r = say("s", "haan", "confirm")
    assert r["status"] == "committed" and r["total"] == 90
    assert stock("atta") == 48 and len(db.list_orders()) == 1
    r2 = say("s", "haan", "confirm")  # second "yes" must not commit again
    assert r2["status"] == "none" and stock("atta") == 48 and len(db.list_orders()) == 1


def test_double_tap_confirm_is_idempotent():
    pid = say("s", "atta", "order", ("আটা", 2, "kg"))["proposal_id"]
    assert flow.confirm("s", pid)["status"] == "committed"
    assert flow.confirm("s", pid)["status"] == "already_committed"
    assert stock("atta") == 48 and len(db.list_orders()) == 1


def test_cannot_confirm_with_open_question():
    say("s", "x", "order", ("তেল", 1, "litre"))
    r = say("s", "haan", "confirm")
    assert r["status"] == "pending" and db.list_orders() == []


def test_oil_clarification_then_wrong_unit_then_fix():
    say("s", "x", "order", ("আটা", 2, "kg"), ("তেল", 5, "kg"))
    r = say("s", "sorshe", "order", ("সরষের তেল", None, None))
    assert r["lines"][1]["product_id"] == "mustard_oil"
    assert r["lines"][1]["status"] == "unit_mismatch" and not r["can_confirm"]
    r = say("s", "5 litre", "order", ("", 5, "litre"))
    assert r["can_confirm"] and r["total"] == 90 + 5 * 165
    assert say("s", "haan", "confirm")["status"] == "committed"
    assert stock("mustard_oil") == 15


def test_reject_clears_draft():
    say("s", "atta", "order", ("আটা", 2, "kg"))
    assert say("s", "na", "reject")["status"] == "cancelled"
    assert say("s", "haan", "confirm")["status"] == "none"
    assert db.list_orders() == [] and stock("atta") == 50


def test_new_order_replaces_unrelated_draft():
    a = say("s", "atta", "order", ("আটা", 2, "kg"))
    b = say("s", "chini", "order", ("চিনি", 1, "kg"))
    assert a["proposal_id"] != b["proposal_id"] and b["lines"][0]["product_id"] == "sugar"


def test_stock_changed_after_proposal_blocks_commit(fresh):
    say("s", "atta", "order", ("আটা", 40, "kg"))
    c = sqlite3.connect(fresh)
    c.execute("UPDATE products SET stock = 10 WHERE id = 'atta'")
    c.commit()
    c.close()
    r = say("s", "haan", "confirm")  # re-validated against live stock before any write
    assert r["status"] == "pending" and not r["can_confirm"]
    assert r["lines"][0]["status"] == "out_of_stock"
    assert stock("atta") == 10 and db.list_orders() == []


def test_commit_itself_refuses_insufficient_stock():
    r = db.commit_order("p2", [{"product_id": "atta", "qty": 51, "unit": "kg"}], "t")
    assert r["status"] == "rejected" and stock("atta") == 50 and db.list_orders() == []


def test_partial_failure_rolls_back_everything(fresh):
    lines = [
        {"product_id": "atta", "qty": 2, "unit": "kg"},
        {"product_id": "sugar", "qty": 999, "unit": "kg"},
    ]
    assert db.commit_order("p1", lines, "t")["status"] == "rejected"
    assert stock("atta") == 50 and db.list_orders() == []


def test_confirm_without_draft():
    assert say("s", "haan", "confirm")["status"] == "none"


def test_sessions_are_isolated():
    say("a", "atta", "order", ("আটা", 2, "kg"))
    assert say("b", "haan", "confirm")["status"] == "none"
    assert stock("atta") == 50


def test_unclear_answer_keeps_pending_order_and_repeats_question():
    say("s", "x", "order", ("আটা", 2, "kg"), ("তেল", 1, "litre"))
    r = flow.handle_turn("s", "???", Extraction(intent="other", items=[]))
    assert r["status"] == "pending" and len(r["lines"]) == 2
    assert "কোনটা" in r["spoken"] and r["proposal_id"]
    assert db.list_orders() == []


def test_null_phrase_from_llm_is_accepted():
    from app.extract import parse_extraction
    e = parse_extraction('{"intent":"order","items":[{"phrase":null,"qty":5,"unit":"litre"}]}')
    assert e.items[0].phrase == "" and e.items[0].qty == 5


def test_saved_order_keeps_the_spoken_order_not_just_the_yes():
    say("s", "দুই কেজি আটা", "order", ("আটা", 2, "kg"))
    say("s", "haan", "confirm")
    assert "দুই কেজি আটা" in db.list_orders()[0]["transcript"]
