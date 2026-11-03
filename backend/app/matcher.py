from dataclasses import dataclass

from rapidfuzz import fuzz, process

from .catalog import PRODUCTS


def norm(s: str) -> str:
    return " ".join(s.casefold().split())


# alias (normalised) -> set of product ids that use this alias
INDEX: dict[str, set[str]] = {}
for _p in PRODUCTS:
    for _a in _p.aliases:
        INDEX.setdefault(norm(_a), set()).add(_p.id)


# Very short aliases ("cha", "tel", "dal", "dim") are matched exactly only. Fuzzy-matching
# them lets "cha" match inside "chaval" (rice) and wrongly resolve to tea.
FUZZY_KEYS = [k for k in INDEX if len(k) >= 4]


@dataclass
class Match:
    status: str  # "exact" | "fuzzy" | "ambiguous" | "unknown"
    product_ids: list[str]
    score: float


def match(phrase: str) -> Match:
    q = norm(phrase)
    if not q:
        return Match("unknown", [], 0.0)

    if q in INDEX:
        ids = sorted(INDEX[q])
        return Match("exact" if len(ids) == 1 else "ambiguous", ids, 100.0)

    hits = process.extract(q, FUZZY_KEYS, scorer=fuzz.WRatio,
                           score_cutoff=82, limit=5)
    if not hits:
        return Match("unknown", [], 0.0)

    top = hits[0][1]
    ids = sorted({pid for key, score, _ in hits if score >= top - 3 for pid in INDEX[key]})
    return Match("fuzzy" if len(ids) == 1 else "ambiguous", ids, float(top))
