import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import aiohttp
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

import config
from bot import run_bot

app = FastAPI()

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

    asyncio.create_task(run_bot(room_url, bot_token))
    logger.info(f"Session started: {room_name}")

    return {
        "room_url": room_url,
        "token": client_token,
    }


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Serve frontend static files (must be after API routes)
frontend_dir = Path(__file__).parent.parent / "frontend"
app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
