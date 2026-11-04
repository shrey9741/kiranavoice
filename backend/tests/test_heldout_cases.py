from app.catalog import BY_ID
from evaluation.make_heldout import CASES

YES = ("হ্যাঁ", "haan", "हाँ", "ok", "yes", "ঠিক আছে")


def test_heldout_set_is_well_formed():
    ids = [c["id"] for c in CASES]
    assert len(CASES) == 30 and len(ids) == len(set(ids))
    kinds = [c["expect"]["kind"] for c in CASES]
    assert kinds.count("commit") == 19 and kinds.count("clarify") == 7
    assert kinds.count("cancel") == 3 and kinds.count("none") == 1
    for c in CASES:
        assert c["turns"], c["id"]
        for l in c["expect"].get("lines", []):
            p = BY_ID[l["product_id"]]
            assert l["unit"] == p.unit and 0 < l["qty"] <= p.stock, c["id"]
        if c["expect"]["kind"] == "commit":
            assert c["turns"][-1] in YES, c["id"]


def test_heldout_texts_do_not_repeat_development_texts():
    from evaluation.make_cases import CASES as DEV
    dev_turns = {t for c in DEV for t in c["turns"]}
    shared = {t for c in CASES for t in c["turns"]} & dev_turns
    assert shared <= set(YES), shared  # only bare confirmations may overlap
