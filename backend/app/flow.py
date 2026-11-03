"""Conversation state machine: propose -> (clarify)* -> confirm -> commit | cancel.
Nothing is written to the database except inside confirm(), and only when the
proposal is clean and has been confirmed."""
import uuid

from . import db
from .extract import Extraction, Item
from .matcher import match
from .rules import build_proposal
from .speech_text import bn_num, spoken_text

EMPTY = {"intent": "other", "lines": [], "total": 0, "questions": [], "can_confirm": False}


class Draft:
    def __init__(self, proposal_id: str, items: list[Item], transcript: str):
        self.proposal_id = proposal_id
        self.items = items
        self.overrides: dict[int, str] = {}
        self.transcripts = [transcript]  # every utterance that shaped this order

    @property
    def transcript(self) -> str:
        return " | ".join(t for t in self.transcripts if t)


SESSIONS: dict[str, Draft] = {}
COMMITTED: dict[str, dict] = {}  # proposal_id -> the response sent when it was committed


def _proposal(draft: Draft, products) -> dict:
    return build_proposal(Extraction(intent="order", items=draft.items), products, draft.overrides)


def _reply(transcript, prop, status, spoken, proposal_id=None, order_id=None) -> dict:
    return {"transcript": transcript, **prop, "status": status,
            "proposal_id": proposal_id, "order_id": order_id, "spoken": spoken}


def _merge(target: Item, item: Item) -> None:
    if item.qty is not None:
        target.qty = item.qty
    if item.unit:
        target.unit = item.unit


def _try_resolve(draft: Draft, item: Item, products) -> bool:
    """Treat a short utterance as the answer to the pending question, if it fits."""
    prop = _proposal(draft, products)
    unresolved = [i for i, l in enumerate(prop["lines"]) if l["status"] != "ok"]
    if not unresolved:
        return False
    m = match(item.phrase) if item.phrase.strip() else None

    # 1) the answer names one of the options of an ambiguous line
    if m and m.status in ("exact", "fuzzy") and len(m.product_ids) == 1:
        pid = m.product_ids[0]
        cands = [i for i in unresolved
                 if prop["lines"][i]["status"] == "ambiguous" and pid in prop["lines"][i]["options"]]
        if len(cands) == 1:
            draft.overrides[cands[0]] = pid
            _merge(draft.items[cands[0]], item)
            return True

    # 2) a quantity/unit answer for the single unresolved line
    if len(unresolved) == 1 and item.qty is not None:
        i = unresolved[0]
        line = prop["lines"][i]
        same = bool(m and line["product_id"] and m.product_ids == [line["product_id"]])
        if m is None or m.status == "unknown" or same:
            draft.items[i].qty = item.qty
            if item.unit:
                draft.items[i].unit = item.unit
            return True
    return False


def handle_turn(session_id: str, transcript: str, ex: Extraction) -> dict:
    products = db.get_products()
    draft = SESSIONS.get(session_id)

    if ex.intent == "reject":
        return cancel(session_id, transcript)
    if ex.intent == "confirm":
        return confirm(session_id, None, transcript)
    if ex.intent != "order" or not ex.items:
        if draft:  # keep the pending order on screen and repeat what we still need
            prop = _proposal(draft, products)
            hint = " ".join(prop["questions"][:1])
            return _reply(transcript, prop, "pending",
                          ("বুঝতে পারিনি। " + hint).strip(), draft.proposal_id)
        return _reply(transcript, EMPTY, "none", "বুঝতে পারিনি। আবার বলুন।")

    if draft and len(ex.items) == 1 and _try_resolve(draft, ex.items[0], products):
        draft.transcripts.append(transcript)
        db.log_event(session_id, "clarified", {"answer": transcript})
    else:
        draft = Draft(uuid.uuid4().hex, [i.model_copy() for i in ex.items], transcript)
        SESSIONS[session_id] = draft
        db.log_event(session_id, "proposal", {"transcript": transcript})

    prop = _proposal(draft, products)
    return _reply(transcript, prop, "pending", spoken_text(prop), draft.proposal_id)


def confirm(session_id: str, proposal_id: str | None, transcript: str = "") -> dict:
    if proposal_id and proposal_id in COMMITTED:  # idempotent: a double tap changes nothing
        r = dict(COMMITTED[proposal_id])
        r["status"] = "already_committed"
        r["spoken"] = ""
        return r

    draft = SESSIONS.get(session_id)
    if draft is None or (proposal_id and draft.proposal_id != proposal_id):
        return _reply(transcript, EMPTY, "none", "কোনো অর্ডার নেই। আগে অর্ডার বলুন।")

    products = db.get_products()
    prop = _proposal(draft, products)
    if not prop["can_confirm"]:
        q = " ".join(prop["questions"][:1])
        return _reply(transcript, {**prop, "intent": "confirm"}, "pending",
                      ("আগে প্রশ্নের উত্তর দিন। " + q).strip(), draft.proposal_id)

    res = db.commit_order(draft.proposal_id, prop["lines"], draft.transcript)
    if res["status"] in ("committed", "already_committed"):
        prop["total"] = res["total"]
        out = _reply(transcript, {**prop, "intent": "confirm"}, "committed",
                     f"অর্ডার হয়ে গেছে। মোট {bn_num(res['total'])} টাকা।",
                     draft.proposal_id, res["order_id"])
        COMMITTED[draft.proposal_id] = out
        SESSIONS.pop(session_id, None)
        return out

    db.log_event(session_id, "commit_rejected", res)
    fresh = _proposal(draft, db.get_products())
    return _reply(transcript, fresh, "rejected",
                  "দুঃখিত, স্টক বদলে গেছে। অর্ডার হয়নি।", draft.proposal_id)


def cancel(session_id: str, transcript: str = "") -> dict:
    draft = SESSIONS.pop(session_id, None)
    if draft:
        db.log_event(session_id, "cancel", {"proposal_id": draft.proposal_id})
    return _reply(transcript, {**EMPTY, "intent": "reject"}, "cancelled",
                  "ঠিক আছে, অর্ডার বাতিল করলাম।")
