import io
import os
import wave
import tempfile
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

import torch
import numpy as np
from TTS.api import TTS
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SPEAKERS_DIR = Path(__file__).parent / "speakers"
SPEAKERS_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Model loading at startup
# ---------------------------------------------------------------------------
tts_model: TTS | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global tts_model
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[XTTS] Loading model on {device} …")
    tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
    print("[XTTS] Model ready.")
    yield
    tts_model = None


app = FastAPI(
    title="TTS API — XTTS v2",
    description="Text-to-Speech API powered by Coqui XTTS v2 (voice cloning)",
    version="1.0.0",
    lifespan=lifespan,
)

# Supported languages by XTTS v2
SUPPORTED_LANGUAGES = [
    "en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru",
    "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko", "hi",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _wav_bytes(wav_array: list | np.ndarray, sample_rate: int = 24000) -> io.BytesIO:
    """Convert a numpy/list waveform to a WAV byte buffer."""
    audio = np.array(wav_array, dtype=np.float32)
    # Normalise to int16
    audio = (audio / max(abs(audio.max()), abs(audio.min()), 1e-8) * 32767).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())
    buf.seek(0)
    return buf


def _get_speaker_path(speaker_name: str) -> Path:
    """Return path to a stored speaker wav, raise 404 if missing."""
    path = SPEAKERS_DIR / f"{speaker_name}.wav"
    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Speaker '{speaker_name}' not found. Upload one via POST /speakers.",
        )
    return path


# ---------------------------------------------------------------------------
# GET /languages  —  Supported languages
# ---------------------------------------------------------------------------
@app.get("/languages", summary="List supported languages")
async def list_languages():
    return {"languages": SUPPORTED_LANGUAGES}


# ---------------------------------------------------------------------------
# GET /speakers  —  List stored reference speakers
# ---------------------------------------------------------------------------
@app.get("/speakers", summary="List stored speaker references")
async def list_speakers():
    speakers = [p.stem for p in SPEAKERS_DIR.glob("*.wav")]
    return {"speakers": speakers}


# ---------------------------------------------------------------------------
# POST /speakers  —  Upload a reference voice
# ---------------------------------------------------------------------------
@app.post("/speakers", summary="Upload a speaker reference WAV")
async def upload_speaker(
    name: str = Form(..., description="Name for this speaker"),
    file: UploadFile = File(..., description="WAV file (6-30 s recommended)"),
):
    """Store a reference WAV that can later be used by name in /tts."""
    if not name.strip():
        raise HTTPException(status_code=400, detail="Speaker name must not be empty.")
    dest = SPEAKERS_DIR / f"{name.strip()}.wav"
    content = await file.read()
    dest.write_bytes(content)
    return {"message": f"Speaker '{name.strip()}' saved.", "path": str(dest)}


# ---------------------------------------------------------------------------
# POST /tts  —  Synthesise speech with voice cloning
# ---------------------------------------------------------------------------
@app.post("/tts", summary="Convert text to speech with XTTS v2")
async def text_to_speech(
    text: str = Form(..., description="Text to synthesise"),
    language: str = Form("fr", description="Language code (e.g. 'fr', 'en', 'ja')"),
    speaker: Optional[str] = Form(
        None, description="Name of a stored speaker (uploaded via /speakers)"
    ),
    speaker_wav: Optional[UploadFile] = File(
        None, description="Reference WAV file for voice cloning (alternative to stored speaker)"
    ),
):
    """
    Synthesise *text* using XTTS v2.

    Voice cloning requires a reference audio — provide either:
    - **speaker**: name of a previously uploaded speaker, OR
    - **speaker_wav**: a WAV file uploaded directly in this request.

    If neither is provided, a default reference must exist as `speakers/default.wav`.
    """
    if not text.strip():
        raise HTTPException(status_code=400, detail="Text must not be empty.")
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language '{language}'. Supported: {SUPPORTED_LANGUAGES}",
        )

    # Resolve speaker wav path
    tmp_path: str | None = None
    try:
        if speaker_wav is not None:
            # Use the uploaded file directly
            suffix = ".wav"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(await speaker_wav.read())
            tmp.close()
            tmp_path = tmp.name
            ref_path = tmp_path
        elif speaker is not None:
            ref_path = str(_get_speaker_path(speaker))
        else:
            # Fallback to default speaker
            default = SPEAKERS_DIR / "default.wav"
            if not default.exists():
                raise HTTPException(
                    status_code=400,
                    detail="No speaker provided and no default speaker found. "
                    "Upload a default via POST /speakers with name='default', "
                    "or pass 'speaker' or 'speaker_wav'.",
                )
            ref_path = str(default)

        # Run inference
        wav = tts_model.tts(
            text=text,
            speaker_wav=ref_path,
            language=language,
        )
        audio_buf = _wav_bytes(wav)

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return StreamingResponse(
        audio_buf,
        media_type="audio/wav",
        headers={"Content-Disposition": 'inline; filename="tts.wav"'},
    )


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
@app.get("/health", summary="Health check")
async def health():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    return {
        "status": "ok",
        "model": "xtts_v2",
        "device": device,
        "model_loaded": tts_model is not None,
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
