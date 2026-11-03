from app.extract import Extraction, Item
from app.rules import build_proposal
from app.speech_text import bn_num, spoken_text


def prop(*items, intent="order"):
    return build_proposal(Extraction(intent=intent, items=[Item(phrase=p, qty=q, unit=u) for p, q, u in items]))


def test_bn_num():
    assert bn_num(2) == "দুই"
    assert bn_num(1.5) == "দেড়"
    assert bn_num(2.5) == "আড়াই"
    assert bn_num(3.5) == "সাড়ে তিন"
    assert bn_num(0.5) == "আধা"
    assert bn_num(107) == "107"


def test_confirmation_sentence():
    s = spoken_text(prop(("আটা", 2, "kg")))
    assert "দুই কেজি আটা" in s and "নিশ্চিত করব" in s


def test_question_is_spoken_when_ambiguous():
    s = spoken_text(prop(("তেল", 1, "litre")))
    assert "কোনটা" in s


def test_nothing_understood():
    s = spoken_text(prop())
    assert "বুঝতে পারিনি" in s
