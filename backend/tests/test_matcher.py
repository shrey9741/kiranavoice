from app.matcher import match


def ids(phrase):
    return match(phrase).product_ids


def test_exact_bengali():
    m = match("আটা")
    assert m.status == "exact" and m.product_ids == ["atta"]


def test_exact_benglish():
    assert match("chini").product_ids == ["sugar"]


def test_specific_oil_is_exact():
    m = match("সরষের তেল")
    assert m.status == "exact" and m.product_ids == ["mustard_oil"]


def test_generic_oil_is_ambiguous():
    m = match("তেল")
    assert m.status == "ambiguous"
    assert set(m.product_ids) == {"mustard_oil", "sunflower_oil"}


def test_generic_dal_is_ambiguous():
    assert match("dal").status == "ambiguous"


def test_small_spelling_error_still_matches():
    assert ids("chinni") == ["sugar"]


def test_unknown_item_is_not_guessed():
    assert match("laptop").status == "unknown"


def test_empty_phrase():
    assert match("   ").status == "unknown"


def test_misspelled_chawal_resolves_to_rice_not_tea():
    for spelling in ("chawal", "chaval", "chawl"):
        assert "tea" not in ids(spelling), spelling
    assert ids("chaval") == ["rice"]


def test_short_alias_still_matches_exactly():
    assert match("cha").product_ids == ["tea"]
    assert match("dim").product_ids == ["egg"]
