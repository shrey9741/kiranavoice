"""Builds the Bengali sentence that is read aloud. Numbers are written as words
where we know them, because TTS can mispronounce digits."""

UNIT_BN = {
    "kg": "কেজি", "g": "গ্রাম", "litre": "লিটার", "ml": "মিলি",
    "piece": "পিস", "packet": "প্যাকেট", "dozen": "ডজন",
}

_WORDS = ["শূন্য", "এক", "দুই", "তিন", "চার", "পাঁচ", "ছয়", "সাত", "আট", "নয়", "দশ",
          "এগারো", "বারো", "তেরো", "চোদ্দ", "পনেরো", "ষোলো", "সতেরো", "আঠারো",
          "উনিশ", "কুড়ি"]


def bn_num(x: float) -> str:
    if x == int(x) and 0 <= x <= 20:
        return _WORDS[int(x)]
    if x > 0 and x * 2 == int(x * 2):
        whole = int(x)
        if x == 0.5:
            return "আধা"
        if x == 1.5:
            return "দেড়"
        if x == 2.5:
            return "আড়াই"
        if whole <= 20:
            return "সাড়ে " + _WORDS[whole]
    return f"{x:g}"  # unknown value: fall back to digits


def spoken_text(p: dict) -> str:
    if p["questions"]:
        return " ".join(p["questions"][:2])
    if p["can_confirm"]:
        parts = []
        for l in p["lines"]:
            unit = UNIT_BN.get(l["unit"] or "", "")
            parts.append(f'{bn_num(l["qty"])} {unit} {l["name"]}'.replace("  ", " "))
        return " আর ".join(parts) + f". মোট {bn_num(p['total'])} টাকা। নিশ্চিত করব?"
    if p["intent"] in ("confirm", "reject"):
        return ""
    return "বুঝতে পারিনি। আবার বলুন।"
