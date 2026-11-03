from dotenv import load_dotenv

load_dotenv()  # must run before importing gnani

import os
import pathlib
import time

from fastapi import FastAPI, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from . import db, flow, gnani
from .audio import to_wav16k
from .extract import extract

db.init_db()

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/transcribe")
async def transcribe(audio: UploadFile, language_code: str = Form("hi-IN")):
    wav = await to_wav16k(await audio.read())
    return await gnani.stt(wav, language_code)


@app.post("/api/voice-order")
async def voice_order(
    audio: UploadFile,
    language_code: str = Form("bn-IN"),
    session_id: str = Form("default"),
):
    """Audio -> transcript -> one conversation turn, with per-stage timings."""
    t0 = time.perf_counter()
    wav = await to_wav16k(await audio.read())
    pathlib.Path("last.wav").write_bytes(wav)  # debug only, remove before deploying
    t1 = time.perf_counter()
    stt = await gnani.stt(wav, language_code)
    t2 = time.perf_counter()
    transcript = (stt.get("transcript") or "").strip()

    if transcript:
        ex = await extract(transcript)
        t3 = time.perf_counter()
        reply = flow.handle_turn(session_id, transcript, ex)
    else:
        t3 = time.perf_counter()
        reply = flow._reply("", flow.EMPTY, "none", "বুঝতে পারিনি। আবার বলুন।")
    t4 = time.perf_counter()

    return {
        **reply,
        "timings": {
            "convert": round(t1 - t0, 3),
            "stt": round(t2 - t1, 3),
            "stt_model": stt.get("processing_time"),
            "llm": round(t3 - t2, 3),
            "rules": round(t4 - t3, 3),
            "total": round(t4 - t0, 3),
        },
    }


@app.post("/api/interpret")
async def interpret(text: str = Form(...), session_id: str = Form("default")):
    """Text version of a conversation turn, for testing without a microphone."""
    ex = await extract(text)
    return flow.handle_turn(session_id, text, ex)


@app.post("/api/confirm")
async def confirm(session_id: str = Form("default"), proposal_id: str = Form(...)):
    return flow.confirm(session_id, proposal_id)


@app.post("/api/cancel")
async def cancel(session_id: str = Form("default")):
    return flow.cancel(session_id)


@app.get("/api/orders")
async def orders():
    return db.list_orders()


@app.get("/api/products")
async def products():
    return [
        {"id": p.id, "name_bn": p.name_bn, "name_en": p.name_en, "unit": p.unit,
         "price": p.price, "stock": p.stock}
        for p in db.get_products().values()
    ]


@app.post("/api/dev/reset")
async def dev_reset():
    if os.environ.get("KIRANA_DEV") != "1":
        raise HTTPException(404)
    db.reset_demo()
    flow.SESSIONS.clear()
    flow.COMMITTED.clear()
    return {"ok": True}


@app.post("/api/speak")
async def speak(
    text: str = Form(...),
    voice: str = Form("Shivani"),
    language: str = Form("bn-IN"),
):
    return Response(await gnani.tts(text, voice, language), media_type="audio/wav")
