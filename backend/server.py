import asyncio
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import aiohttp
from deepgram import Deepgram
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineTask

import config

app = FastAPI()

# Initialize Deepgram
deepgram = Deepgram(config.DEEPGRAM_API_KEY)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DAILY_API_HEADERS = {
    "Authorization": f"Bearer {config.DAILY_API_KEY}",
    "Content-Type": "application/json",
}


async def create_room() -> dict:
    expiry = int((datetime.utcnow() + timedelta(minutes=config.SESSION_TIMEOUT_MINUTES + 5)).timestamp())
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{config.DAILY_API_URL}/rooms",
            headers=DAILY_API_HEADERS,
            json={
                "privacy": "public",
                "properties": {
                    "exp": expiry,
                    "enable_chat": False,
                    "enable_screenshare": False,
                    "max_participants": 2,
                },
            },
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Failed to create room: {text}")
            return await resp.json()


async def create_token(room_name: str, is_owner: bool = True) -> str:
    expiry = int((datetime.utcnow() + timedelta(minutes=config.SESSION_TIMEOUT_MINUTES + 5)).timestamp())
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{config.DAILY_API_URL}/meeting-tokens",
            headers=DAILY_API_HEADERS,
            json={
                "properties": {
                    "room_name": room_name,
                    "exp": expiry,
                    "is_owner": is_owner,
                },
            },
        ) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise Exception(f"Failed to create token: {text}")
            data = await resp.json()
            return data["token"]


@app.post("/api/start")
async def start_session():
    room = await create_room()
    room_url = room["url"]
    room_name = room["name"]

    bot_token = await create_token(room_name, is_owner=True)
    client_token = await create_token(room_name, is_owner=False)

    # Bot joins room passively (no audio pipeline) - frontend sends audio via /api/chat instead
    asyncio.create_task(run_bot_passive(room_url, bot_token))
    logger.info(f"Session started: {room_name}")

    return {
        "room_url": room_url,
        "token": client_token,
    }


@app.get("/api/health")
async def health():
    return {"status": "ok"}


async def run_bot_passive(room_url: str, token: str):
    """Join Daily room without audio pipeline - just keeps the room alive."""
    from pipecat.transports.daily.transport import DailyTransport, DailyParams
    
    async with aiohttp.ClientSession() as session:
        transport = DailyTransport(
            room_url,
            token,
            "Bubbles",
            DailyParams(
                audio_in_enabled=False,  # No audio input - frontend uses /api/chat instead
                audio_out_enabled=True,
                transcription_enabled=False,
            ),
        )

        @transport.event_handler("on_first_participant_joined")
        async def on_first(transport, participant):
            logger.info(f"Bot joined room: {participant}")

        @transport.event_handler("on_participant_left")
        async def on_left(transport, participant, reason):
            logger.info(f"Participant left: {reason}")

        runner = PipelineRunner()
        task = PipelineTask([])
        await runner.run(task)


@app.post("/api/chat")
async def chat(audio_file: UploadFile = File(...)):
    """Receive audio on button release, transcribe, then get LLM response. Single API call."""
    try:
        # Save uploaded audio to temp file
        with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
            tmp.write(await audio_file.read())
            tmp_path = tmp.name

        # Transcribe with Deepgram
        with open(tmp_path, "rb") as f:
            dg_response = await deepgram.transcription.prerecorded(
                {"buffer": f, "mimetype": audio_file.content_type or "audio/webm"},
                {"punctuate": True, "profanity_filter": True}
            )
        
        # Extract transcript
        transcript = dg_response["results"]["channels"][0]["alternatives"][0]["transcript"]
        if not transcript.strip():
            return {"text": "Hmm, I didn't catch that! Can you say it again?"}
        
        logger.info(f"Transcribed: {transcript}")

        # Get LLM response (single call)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.minimax.io/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.MINIMAX_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "MiniMax-M2.5",
                    "messages": [
                        {"role": "system", "content": "You are Bubbles, a fun talking buddy for kids under 10."},
                        {"role": "user", "content": transcript}
                    ],
                    "max_tokens": 150,
                    "temperature": 0.8,
                    "group_id": config.MINIMAX_GROUP_ID,
                },
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    logger.error(f"LLM error: {error}")
                    return {"text": "Oops, something went wrong! Try again."}
                result = await resp.json()
                reply = result["choices"][0]["message"]["content"]
        
        logger.info(f"Bubbles says: {reply}")
        return {"text": reply}

    except Exception as e:
        logger.exception(f"Chat error: {e}")
        return {"text": "Oops, something went wrong! Try again."}
    finally:
        # Cleanup temp file
        Path(tmp_path).unlink(missing_ok=True)


# Serve frontend static files (must be after API routes)
frontend_dir = Path(__file__).parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
