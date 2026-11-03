"""Generates cases.jsonl. Texts are what the speech model would return (post-STT).
Run once:  python -m evaluation.make_cases
kinds: commit (exact lines) | clarify (must stop with a line in the given status) |
       cancel | none (nothing understood, nothing saved)."""
import json
from pathlib import Path

CASES = []


def add(tag, turns, kind, lines=None, line_status=None):
    exp = {"kind": kind}
    if lines:
        exp["lines"] = [{"product_id": p, "qty": q, "unit": u} for p, q, u in lines]
    if line_status:
        exp["line_status"] = line_status
    CASES.append({"id": f"c{len(CASES) + 1:02d}", "tag": tag, "turns": turns, "expect": exp})


YES_BN, YES_EN, YES_HI = "হ্যাঁ", "haan", "हाँ"

# --- Bengali script, clean orders -------------------------------------------------
add("bengali", ["আমার দুই কেজি আটা লাগবে", YES_BN], "commit", [("atta", 2, "kg")])
add("bengali", ["এক কেজি চিনি আর আধা কেজি নুন", YES_BN], "commit", [("sugar", 1, "kg"), ("salt", 0.5, "kg")])
add("bengali", ["তিন কেজি চাল", YES_BN], "commit", [("rice", 3, "kg")])
add("bengali", ["দেড় কেজি পেঁয়াজ আর দুই কেজি আলু", YES_BN], "commit", [("onion", 1.5, "kg"), ("potato", 2, "kg")])
add("bengali", ["একটা সাবান", YES_BN], "commit", [("soap", 1, "piece")])
add("bengali", ["এক প্যাকেট চা পাতা", YES_BN], "commit", [("tea", 1, "packet")])
add("bengali", ["দুই প্যাকেট বিস্কুট আর এক প্যাকেট দুধ", YES_BN], "commit", [("biscuit", 2, "packet"), ("milk", 1, "packet")])
add("bengali", ["এক ডজন ডিম", YES_BN], "commit", [("egg", 12, "piece")])
add("bengali", ["পাঁচ কেজি আটা আর পাঁচ কেজি চাল", YES_BN], "commit", [("atta", 5, "kg"), ("rice", 5, "kg")])
add("bengali", ["আড়াই কেজি চিনি", YES_BN], "commit", [("sugar", 2.5, "kg")])
add("bengali", ["সরষের তেল দুই লিটার", YES_BN], "commit", [("mustard_oil", 2, "litre")])
add("bengali", ["এক লিটার সানফ্লাওয়ার তেল", YES_BN], "commit", [("sunflower_oil", 1, "litre")])
add("bengali", ["মসুর ডাল এক কেজি", YES_BN], "commit", [("masoor_dal", 1, "kg")])
add("bengali", ["মুগ ডাল আধা কেজি", YES_BN], "commit", [("moong_dal", 0.5, "kg")])
add("bengali", ["পাঁচশো গ্রাম আটা", YES_BN], "commit", [("atta", 0.5, "kg")])
add("bengali", ["আড়াইশো গ্রাম নুন", YES_BN], "commit", [("salt", 0.25, "kg")])
add("bengali", ["আমার পাঁচ কেজি আটা আর পাঁচ লিটার সরষের তেল লাগবে", YES_BN], "commit", [("atta", 5, "kg"), ("mustard_oil", 5, "litre")])

# --- Benglish (Bengali words in Latin script) -------------------------------------
add("benglish", ["amar 2 kilo atta lagbe", YES_EN], "commit", [("atta", 2, "kg")])
add("benglish", ["1 kilo chini ar 1 packet cha pata", YES_EN], "commit", [("sugar", 1, "kg"), ("tea", 1, "packet")])
add("benglish", ["ek litre sorshe tel", YES_EN], "commit", [("mustard_oil", 1, "litre")])
add("benglish", ["3 kg alu ar 2 kg peyaj", YES_EN], "commit", [("potato", 3, "kg"), ("onion", 2, "kg")])
add("benglish", ["ek dozen dim", YES_EN], "commit", [("egg", 12, "piece")])
add("benglish", ["dui kilo chal", YES_EN], "commit", [("rice", 2, "kg")])
add("benglish", ["ek ta sabun", YES_EN], "commit", [("soap", 1, "piece")])
add("benglish", ["dedh kilo atta", YES_EN], "commit", [("atta", 1.5, "kg")])
add("benglish", ["aadha kilo masur dal", YES_EN], "commit", [("masoor_dal", 0.5, "kg")])

# --- Hinglish / Hindi --------------------------------------------------------------
add("hinglish", ["do kilo aata aur ek kilo cheeni", YES_EN], "commit", [("atta", 2, "kg"), ("sugar", 1, "kg")])
add("hinglish", ["teen kilo chawal", YES_EN], "commit", [("rice", 3, "kg")])
add("hinglish", ["ek kilo namak aur do packet biscuit", YES_EN], "commit", [("salt", 1, "kg"), ("biscuit", 2, "packet")])
add("hinglish", ["dedh kilo pyaaz", YES_EN], "commit", [("onion", 1.5, "kg")])
add("hinglish", ["ek packet doodh", YES_EN], "commit", [("milk", 1, "packet")])
add("hinglish", ["दो किलो आटा और एक किलो चीनी", YES_HI], "commit", [("atta", 2, "kg"), ("sugar", 1, "kg")])
add("hinglish", ["तीन किलो चावल", YES_HI], "commit", [("rice", 3, "kg")])

# --- Code-mixed ---------------------------------------------------------------------
add("mixed", ["kalke 2 kilo atta ar ek litre sorshe tel lagbe", YES_EN], "commit", [("atta", 2, "kg"), ("mustard_oil", 1, "litre")])
add("mixed", ["amar পাঁচ kg চিনি", YES_BN], "commit", [("sugar", 5, "kg")])
add("mixed", ["দু kilo আলু আর ek kilo পেঁয়াজ", YES_BN], "commit", [("potato", 2, "kg"), ("onion", 1, "kg")])

# --- Ambiguity resolved over several turns -----------------------------------------
add("clarified", ["আমার এক লিটার তেল লাগবে", "সরষের তেল", YES_BN], "commit", [("mustard_oil", 1, "litre")])
add("clarified", ["ek litre tel", "sunflower oil", YES_EN], "commit", [("sunflower_oil", 1, "litre")])
add("clarified", ["দুই কেজি ডাল", "মসুর ডাল", YES_BN], "commit", [("masoor_dal", 2, "kg")])
add("clarified", ["ek kilo dal chahiye", "moong dal", YES_EN], "commit", [("moong_dal", 1, "kg")])
add("clarified", ["এক কেজি আটা আর দুই লিটার তেল", "সানফ্লাওয়ার", YES_BN], "commit", [("atta", 1, "kg"), ("sunflower_oil", 2, "litre")])
add("clarified", ["আমার দুই কেজি আটা আর পাঁচ কেজি তেল", "সরষের তেল", "পাঁচ লিটার", YES_BN], "commit", [("atta", 2, "kg"), ("mustard_oil", 5, "litre")])

# --- Must stop and ask (and must stay stopped even if the user says yes) ------------
add("negative", ["এক লিটার তেল"], "clarify", line_status="ambiguous")
add("negative", ["দুই কেজি ডাল", YES_BN], "clarify", line_status="ambiguous")
add("negative", ["একটা ল্যাপটপ"], "clarify", line_status="unknown")
add("negative", ["আমার চিনি লাগবে", YES_BN], "clarify", line_status="bad_qty")
add("negative", ["দুই লিটার আটা"], "clarify", line_status="unit_mismatch")
add("negative", ["পাঁচশো কেজি আটা", YES_BN], "clarify", line_status="out_of_stock")
add("negative", ["এক কেজি আটা আর একটা টিভি", YES_BN], "clarify", line_status="unknown")
add("negative", ["এক লিটার নুন"], "clarify", line_status="unit_mismatch")
add("negative", ["দুই কেজি আটা আর এক লিটার তেল", YES_BN], "clarify", line_status="ambiguous")
add("negative", ["ek litre tel chahiye", YES_EN], "clarify", line_status="ambiguous")
add("negative", ["एक लीटर तेल"], "clarify", line_status="ambiguous")

# --- Cancel ----------------------------------------------------------------------------
add("cancel", ["দুই কেজি আটা", "না"], "cancel")
add("cancel", ["এক কেজি চিনি", "বাদ দাও"], "cancel")
add("cancel", ["ek kilo chini", "cancel"], "cancel")

# --- Nothing to confirm / not an order ------------------------------------------------
add("noise", [YES_BN], "none")
add("noise", ["আজকে আবহাওয়া কেমন"], "none")
add("noise", ["হ্যালো"], "none")

if __name__ == "__main__":
    out = Path(__file__).parent / "cases.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for c in CASES:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"wrote {len(CASES)} cases to {out}")
