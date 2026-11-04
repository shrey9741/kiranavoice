"""Held-out evaluation set: written AFTER the development rounds and never used to tune
the prompt, the matcher or the rules. Generate once:  python -m evaluation.make_heldout

Rules for this file: do not edit a case after you have seen the result, and do not
change app/ code in response to a failing case here. If you do, say so in the README
and treat the numbers as development data.

Expected outcomes describe what is CORRECT for the shop, not what the system happens to do.
kinds: commit (exact saved lines, in the product's unit) | clarify (no order saved, and the
last reply must contain a line with the given status) | cancel | none."""
import json
from pathlib import Path

CASES = []


def add(tag, turns, kind, lines=None, line_status=None):
    exp = {"kind": kind}
    if lines:
        exp["lines"] = [{"product_id": p, "qty": q, "unit": u} for p, q, u in lines]
    if line_status:
        exp["line_status"] = line_status
    CASES.append({"id": f"h{len(CASES) + 1:02d}", "tag": tag, "turns": turns, "expect": exp})


# --- Bengali script ----------------------------------------------------------------
add("bengali", ["ভাই তিন কেজি আলু আর এক কেজি পেঁয়াজ দিন", "হ্যাঁ"], "commit", [("potato", 3, "kg"), ("onion", 1, "kg")])
add("bengali", ["চার কেজি চাল একটু তাড়াতাড়ি দাও", "ঠিক আছে"], "commit", [("rice", 4, "kg")])
add("bengali", ["আড়াই কেজি আটা আর আধা কেজি মুগ ডাল", "হ্যাঁ"], "commit", [("atta", 2.5, "kg"), ("moong_dal", 0.5, "kg")])
add("bengali", ["দুটো সাবান আর তিন প্যাকেট দুধ লাগবে", "হ্যাঁ"], "commit", [("soap", 2, "piece"), ("milk", 3, "packet")])
add("bengali", ["আধা ডজন ডিম", "হ্যাঁ"], "commit", [("egg", 6, "piece")])
add("bengali", ["দুই লিটার সরষের তেল আর পাঁচ কেজি চিনি দিয়ে দিন", "হ্যাঁ"], "commit", [("mustard_oil", 2, "litre"), ("sugar", 5, "kg")])

# --- Benglish ----------------------------------------------------------------------
add("benglish", ["dada 2 kilo chal ar 1 kilo nun den", "haan"], "commit", [("rice", 2, "kg"), ("salt", 1, "kg")])
add("benglish", ["ek packet biscuit ar duto sabun", "ok"], "commit", [("biscuit", 1, "packet"), ("soap", 2, "piece")])
add("benglish", ["arai kilo alu", "haan"], "commit", [("potato", 2.5, "kg")])
add("benglish", ["tin kilo peyaj ar 500 gram chini", "yes"], "commit", [("onion", 3, "kg"), ("sugar", 0.5, "kg")])
add("benglish", ["sunflower tel ek litre dao", "haan"], "commit", [("sunflower_oil", 1, "litre")])

# --- Hinglish / Hindi ---------------------------------------------------------------
add("hinglish", ["bhaiya do kilo chawal aur ek kilo namak dena", "haan"], "commit", [("rice", 2, "kg"), ("salt", 1, "kg")])
add("hinglish", ["teen packet chai aur ek dozen anda", "haan"], "commit", [("tea", 3, "packet"), ("egg", 12, "piece")])
add("hinglish", ["मुझे एक किलो प्याज और दो किलो आलू चाहिए", "हाँ"], "commit", [("onion", 1, "kg"), ("potato", 2, "kg")])

# --- Messy / code-mixed / self-correction -------------------------------------------------
add("mixed", ["amar লাগবে দুই kilo atta ar ek packet দুধ", "হ্যাঁ"], "commit", [("atta", 2, "kg"), ("milk", 1, "packet")])
add("mixed", ["দুই কেজি আটা না না তিন কেজি আটা দিন", "হ্যাঁ"], "commit", [("atta", 3, "kg")])

# --- Ambiguity resolved over several turns ----------------------------------------------
add("clarified", ["এক লিটার তেল দাও ভাই", "সানফ্লাওয়ারটাই দাও", "হ্যাঁ"], "commit", [("sunflower_oil", 1, "litre")])
add("clarified", ["dui kilo dal", "masur", "haan"], "commit", [("masoor_dal", 2, "kg")])
add("clarified", ["ek kilo atta aur do litre tel", "sarson ka tel", "haan"], "commit", [("atta", 1, "kg"), ("mustard_oil", 2, "litre")])

# --- Must stop and ask (and stay stopped) -------------------------------------------------
add("negative", ["পাঁচ কেজি ডাল দিন", "হ্যাঁ"], "clarify", line_status="ambiguous")
add("negative", ["ভাই এক কেজি পনির দাও"], "clarify", line_status="unknown")
add("negative", ["do litre atta chahiye", "haan"], "clarify", line_status="unit_mismatch")
add("negative", ["একশো কেজি চিনি", "হ্যাঁ"], "clarify", line_status="out_of_stock")
add("negative", ["ek packet tel", "haan"], "clarify", line_status="ambiguous")
add("negative", ["আমি আটা নেব", "হ্যাঁ"], "clarify", line_status="bad_qty")
add("negative", ["ek bottle cold drink dena", "haan"], "clarify", line_status="unknown")

# --- Cancel ---------------------------------------------------------------------------------
add("cancel", ["তিন কেজি চাল দিন", "না থাক"], "cancel")
add("cancel", ["ek kilo sugar", "nahi nahi cancel kar do"], "cancel")
add("cancel", ["दो किलो आटा चाहिए", "नहीं"], "cancel")

# --- Not an order ---------------------------------------------------------------------------
add("noise", ["দোকান কখন খুলবে"], "none")

if __name__ == "__main__":
    out = Path(__file__).parent / "heldout_cases.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for c in CASES:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"wrote {len(CASES)} held-out cases to {out}")
