from .catalog import BY_ID
from .extract import Extraction
from .matcher import Match, match
from .speech_text import UNIT_BN


def to_product_unit(qty: float, unit: str | None, product_unit: str) -> float | None:
    """Convert qty to the product's unit, or None if the units are incompatible."""
    if unit is None or unit == product_unit:
        return qty
    if unit == "g" and product_unit == "kg":
        return qty / 1000
    if unit == "ml" and product_unit == "litre":
        return qty / 1000
    if unit == "dozen" and product_unit == "piece":
        return qty * 12
    return None


def build_proposal(ex: Extraction, products=None, overrides: dict[int, str] | None = None) -> dict:
    """Deterministic validation. The LLM output is only a suggestion; this decides.
    `products` carries live stock/price (from the database); `overrides` maps a line
    index to a product the shopkeeper chose when answering a clarification."""
    products = products or BY_ID
    overrides = overrides or {}
    lines: list[dict] = []
    questions: list[str] = []

    for idx, it in enumerate(ex.items):
        m = Match("exact", [overrides[idx]], 100.0) if idx in overrides else match(it.phrase)
        line = {"phrase": it.phrase, "product_id": None, "name": it.phrase,
                "qty": it.qty, "unit": it.unit, "amount": None, "status": "ok",
                "options": []}

        if m.status == "unknown":
            line["status"] = "unknown"
            if it.phrase.strip():
                questions.append(f"'{it.phrase}' খুঁজে পাচ্ছি না। অন্য নামে বলবেন?")
            else:
                questions.append("কোন জিনিসটা লাগবে?")
        elif m.status == "ambiguous":
            names = [products[i].name_bn for i in m.product_ids]
            line["status"] = "ambiguous"
            line["options"] = m.product_ids
            questions.append(f"{it.phrase}: কোনটা? " + " না ".join(names) + "?")
        else:
            p = products[m.product_ids[0]]
            line["product_id"] = p.id
            line["name"] = p.name_bn
            if it.qty is None or it.qty <= 0:
                line["status"] = "bad_qty"
                questions.append(f"{p.name_bn} কতটা লাগবে?")
            else:
                qty = to_product_unit(it.qty, it.unit, p.unit)
                if qty is None:
                    line["status"] = "unit_mismatch"
                    questions.append(
                        f"{p.name_bn} {UNIT_BN[p.unit]} হিসেবে বিক্রি হয়। কতটা লাগবে?")
                elif qty > p.stock:
                    line["status"] = "out_of_stock"
                    questions.append(
                        f"{p.name_bn} মাত্র {p.stock:g} {UNIT_BN[p.unit]} আছে।")
                else:
                    line["qty"] = qty
                    line["unit"] = p.unit
                    line["amount"] = round(qty * p.price, 2)
        lines.append(line)

    total = round(sum(l["amount"] or 0 for l in lines), 2)
    can_confirm = ex.intent == "order" and bool(lines) and all(l["status"] == "ok" for l in lines)
    return {"intent": ex.intent, "lines": lines, "total": total,
            "questions": questions, "can_confirm": can_confirm}
