import os

import httpx
from fastapi import HTTPException

BASE = "https://api.vachana.ai"
HEADERS = {"X-API-Key-ID": os.environ["GNANI_API_KEY"]}


def _check(r: httpx.Response) -> None:
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"Gnani error: {r.text[:500]}")


async def stt(wav_bytes: bytes, language_code: str) -> dict:
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            f"{BASE}/stt/v3",
            headers=HEADERS,
            files={"audio_file": ("audio.wav", wav_bytes, "audio/wav")},
            data={"language_code": language_code},
        )
        _check(r)
        return r.json()


async def tts(text: str, voice: str = "Shivani", language: str = "bn-IN") -> bytes:
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(
            f"{BASE}/api/v1/tts/inference",
            headers={**HEADERS, "Content-Type": "application/json"},
            json={
                "text": text,
                "voice": voice,
                "model": "timbre-v3.0",
                "language": language,
                "speed": 1.0,
                "audio_config": {
                    "sample_rate": 24000,
                    "num_channels": 1,
                    "sample_width": 2,
                    "encoding": "linear_pcm",
                    "container": "wav",
                },
            },
        )
        _check(r)
        return r.content