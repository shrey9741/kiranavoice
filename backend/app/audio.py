import asyncio
import os
import subprocess
import tempfile

from fastapi import HTTPException


def _convert(data: bytes) -> bytes:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
        f.write(data)
        path = f.name
    try:
        r = subprocess.run(
            [
                "ffmpeg", "-y", "-i", path,
                  
                "-ar", "16000", "-ac", "1", "-f", "wav", "pipe:1",
            ],
            capture_output=True,
        )
    finally:
        os.remove(path)
    if r.returncode != 0 or not r.stdout:
        msg = r.stderr.decode(errors="ignore")[-400:]
        raise HTTPException(400, f"ffmpeg failed: {msg}")
    return r.stdout


async def to_wav16k(data: bytes) -> bytes:
    return await asyncio.to_thread(_convert, data)
