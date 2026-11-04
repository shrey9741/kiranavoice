import asyncio
import json
import os
import re
from typing import Literal

import httpx
from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError, field_validator

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-20b"


class Item(BaseModel):
    phrase: str = ""
    qty: float | None = None
    unit: str | None = None

    @field_validator("phrase", mode="before")
    @classmethod
    def _no_null_phrase(cls, v):
        return "" if v is None else v


class Extraction(BaseModel):
    intent: Literal["order", "confirm", "reject", "other"] = "other"
    items: list[Item] = Field(default_factory=list)


SYSTEM = """You extract shop orders from speech transcripts. The shopkeeper speaks Bengali, Benglish, Hindi or Hinglish.
Return ONLY a JSON object with this shape:
{"intent": "order" | "confirm" | "reject" | "other", "items": [{"phrase": string, "qty": number or null, "unit": string or null}]}

Rules:
- intent "confirm": the speaker says yes/ok (হ্যাঁ, ঠিক আছে, haan, yes, confirm). intent "reject": no/cancel (না, বাদ দাও, cancel). intent "order": products are requested. Otherwise "other".
- phrase: the product words copied character for character from the transcript. Never transliterate between scripts: Latin letters stay Latin, Devanagari stays Devanagari, Bengali stays Bengali ("chawal" stays "chawal", never "চাওয়াল"). Do NOT translate, correct, or pick a specific brand or variety. If the speaker says only "তেল", the phrase is "তেল".
- The phrase is an empty string ONLY when no product word is spoken at all (for example the answer "পাঁচ লিটার" to "how much?"); then intent is still "order" and items has ONE item with that empty phrase. If any product word is present ("এক লিটার তেল" has the product "তেল"), the phrase is that product word. Never return intent "other" for a quantity.
- qty: the number exactly as spoken, in the spoken unit. Do NOT convert units yourself: "এক ডজন ডিম" is qty 1, unit "dozen"; "পাঁচশো গ্রাম" is qty 500, unit "g"; "আধা কেজি" is qty 0.5, unit "kg". A count word such as এক/একটা/একটি/ek/ek ta means 1, so qty is never null when one is spoken. Convert number words: এক=1, দুই/দু=2, তিন=3, চার=4, পাঁচ=5, ছয়=6, সাত=7, আট=8, নয়=9, দশ=10, আধা/আধ=0.5, দেড়=1.5, আড়াই=2.5, সাড়ে তিন=3.5, সাড়ে চার=4.5. শো/শ means hundred and হাজার thousand: পাঁচশো=500, আড়াইশো=250, দুইশো=200, সাড়ে তিনশো=350, এক হাজার=1000. Hindi: ek=1, do=2, teen=3, char=4, paanch=5, aadha=0.5, dedh=1.5, dhai=2.5. If no quantity is stated, use null. Never guess a quantity.
- unit: one of "kg", "g", "litre", "ml", "piece", "packet", "dozen", or null if not stated. কেজি/কিলো/kilo/kg = kg; গ্রাম = g; লিটার/litre/ltr = litre; পিস/টা/টি = piece; প্যাকেট = packet; ডজন = dozen.
- Ignore filler words (কালকে, আমার, লাগবে, অর্ডার করে রাখো, নিয়ে যাব). Do not invent items that were not said.
- If nothing relevant was said, return {"intent": "other", "items": []}.

Examples:
"আমার পাঁচ কেজি আটা আর পাঁচ লিটার তেল লাগবে" -> {"intent":"order","items":[{"phrase":"আটা","qty":5,"unit":"kg"},{"phrase":"তেল","qty":5,"unit":"litre"}]}
"দেড় কেজি চিনি আর একটা সাবান" -> {"intent":"order","items":[{"phrase":"চিনি","qty":1.5,"unit":"kg"},{"phrase":"সাবান","qty":1,"unit":"piece"}]}
"হ্যাঁ ঠিক আছে" -> {"intent":"confirm","items":[]}
"পাঁচ লিটার" -> {"intent":"order","items":[{"phrase":"","qty":5,"unit":"litre"}]}
"দুই কেজি" -> {"intent":"order","items":[{"phrase":"","qty":2,"unit":"kg"}]}
"সরষের তেল" -> {"intent":"order","items":[{"phrase":"সরষের তেল","qty":null,"unit":null}]}
"এক লিটার তেল" -> {"intent":"order","items":[{"phrase":"তেল","qty":1,"unit":"litre"}]}
"teen kilo chawal" -> {"intent":"order","items":[{"phrase":"chawal","qty":3,"unit":"kg"}]}
"একটা সাবান" -> {"intent":"order","items":[{"phrase":"সাবান","qty":1,"unit":"piece"}]}
"এক প্যাকেট চা পাতা" -> {"intent":"order","items":[{"phrase":"চা পাতা","qty":1,"unit":"packet"}]}
"এক ডজন ডিম" -> {"intent":"order","items":[{"phrase":"ডিম","qty":1,"unit":"dozen"}]}
"পাঁচশো গ্রাম আটা" -> {"intent":"order","items":[{"phrase":"আটা","qty":500,"unit":"g"}]}
"আড়াইশো গ্রাম নুন" -> {"intent":"order","items":[{"phrase":"নুন","qty":250,"unit":"g"}]}
"আমার চিনি লাগবে" -> {"intent":"order","items":[{"phrase":"চিনি","qty":null,"unit":null}]}
"""


def retry_after_seconds(text: str) -> float:
    """Reads 'Please try again in 2.3s' / '337ms' from a rate-limit message."""
    m = re.search(r"try again in ([0-9.]+)(ms|s)", text)
    if not m:
        return 5.0
    v = float(m.group(1))
    return v / 1000 if m.group(2) == "ms" else v


def parse_extraction(raw: str) -> Extraction:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    try:
        return Extraction.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as e:
        raise ValueError(f"Bad extraction output: {e}") from e


async def extract(transcript: str) -> Extraction:
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise HTTPException(500, "GROQ_API_KEY is not set in backend/.env")
    model = os.environ.get("GROQ_MODEL", DEFAULT_MODEL)

    payload = {
        "model": model,
        "temperature": 0,
        "max_completion_tokens": 1500,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": transcript},
        ],
    }
    if "gpt-oss" in model:
        payload["reasoning_effort"] = "low"

    last_err = ""
    async with httpx.AsyncClient(timeout=30) as c:
        for attempt in range(3):  # also covers one retry on malformed output
            r = await c.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
            )
            if r.status_code == 429 and attempt < 2:  # short rate-limit wait: just retry
                wait = retry_after_seconds(r.text)
                if wait <= 4:
                    await asyncio.sleep(wait + 0.2)
                    continue
            if r.status_code >= 400:
                raise HTTPException(502, f"LLM error {r.status_code}: {r.text[:300]}")
            content = r.json()["choices"][0]["message"].get("content") or ""
            try:
                return parse_extraction(content)
            except ValueError as e:
                last_err = str(e)
    raise HTTPException(502, last_err)