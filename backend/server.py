"""
Bubbles - Simple push-to-talk chatbot for kids
Receives audio → transcribes → LLM response → returns text (frontend uses Web Speech API for TTS)
"""
import asyncio
import tempfile
from pathlib import Path

import aiohttp
from deepgram import DeepgramClient
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

import config

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Deepgram (reads DEEPGRAM_API_KEY from env)
deepgram = DeepgramClient()

BUBBLES_PROMPT = """You are Bubbles, a fun talking buddy for kids under 10. Be adaptive — silly with silly kids, gentle with quiet ones. Use simple words, short sentences, and kid-friendly humor.

You can chat, tell stories, help with homework, play quiz games, and answer "why" questions.

RULES: Never discuss violence, adult topics, or scary things. Never use bad language. Never ask for personal info. Never pretend to be human. If asked something inappropriate, say "That's a great question for a grown-up! Want to play a game instead?" If a child seems upset, be kind and suggest they talk to a trusted adult.

Keep responses to 1-3 sentences. Ask follow-up questions. Be encouraging and fun."""


@app.post("/api/chat")
async def chat(audio_file: UploadFile = File(...)):
    """Receive audio blob → transcribe → LLM → return text response."""
    tmp_path = None
    try:
        # Save uploaded audio
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(await audio_file.read())
            tmp_path = tmp.name

        # Transcribe with Deepgram v5
        with open(tmp_path, "rb") as f:
            dg_response = deepgram.listen.v1.media.transcribe_file(
                request=f.read(),
                model="nova-2",
                punctuate=True,
                profanity_filter=True,
            )
        
        transcript = dg_response.results.channels[0].alternatives[0].transcript
        logger.info(f"Heard: {transcript}")

        if not transcript.strip():
            return {"text": "Hmm, I didn't catch that! Can you say it again?"}
        
        # Get LLM response via MiniMax Anthropic-compatible API
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.minimax.io/anthropic/v1/messages",
                headers={
                    "Authorization": f"Bearer {config.MINIMAX_API_KEY}",
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "MiniMax-M2.5",
                    "messages": [
                        {"role": "user", "content": f"{BUBBLES_PROMPT}\n\nChild: {transcript}"}
                    ],
                    "max_tokens": 150,
                },
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    logger.error(f"MiniMax error: {error}")
                    return {"error": "Oops, something went wrong on my end!"}
                result = await resp.json()
                reply = result["choices"][0]["message"]["content"]
        
        logger.info(f"Bubbles: {reply}")
        return {"text": reply}

    except Exception as e:
        logger.exception(f"Chat error: {e}")
        return {"error": "Oops, something went wrong! Try again."}
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Serve frontend
frontend_dir = Path(__file__).parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
