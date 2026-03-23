"""
Bubbles - Simple push-to-talk chatbot for kids with memory
Receives audio → transcribes → LLM response → returns text + audio
"""
import base64
import json
import re
import tempfile
import uuid
from pathlib import Path

import aiohttp
from deepgram import DeepgramClient
from fastapi import FastAPI, UploadFile, File, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

import config
import memory

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

# Facts to extract from conversation
FACT_PATTERNS = [
    (r"my name is (\w+)", "name"),
    (r"i'm (\w+)", "nickname"),
    (r"i am (\w+)", "nickname"),
    (r"my favorite color is (\w+)", "favorite_color"),
    (r"i like (\w+)", "likes"),
    (r"my dog is (named )?(\w+)", "pet_name"),
    (r"i'm (\d+) years? old", "age"),
    (r"i am (\d+) years? old", "age"),
]


def extract_facts(session_id: str, text: str):
    """Extract facts from child speech and store them."""
    text_lower = text.lower()
    for pattern, key in FACT_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            value = match.group(1) if match.groups() else match.group(0)
            memory.set_fact(session_id, key, value)
            logger.info(f"Extracted fact: {key} = {value}")


def update_personality_from_response(session_id: str, child_speech: str, bubbles_reply: str):
    """Update personality traits based on interaction patterns."""
    child_lower = child_speech.lower()
    
    # Detect silliness level
    silly_words = ["lol", "haha", "funny", "silly", "joke", "laugh", "lmao", "hahaha"]
    if any(word in child_lower for word in silly_words):
        memory.update_personality(session_id, "silly", 0.1)
    
    # Detect quiet/shy behavior
    quiet_words = ["okay", "ok", "yeah", "yes", "sure", "i guess"]
    short_response = len(child_speech.split()) < 5
    if any(word in child_lower for word in quiet_words) and short_response:
        memory.update_personality(session_id, "quiet", 0.1)
    
    # Detect enthusiasm
    excited_words = ["wow", "awesome", "cool", "amazing", "really", "wow!"]
    if any(word in child_lower for word in excited_words):
        memory.update_personality(session_id, "enthusiastic", 0.1)


async def generate_tts(text: str) -> str:
    """Generate TTS audio using MiniMax and return as base64 MP3."""
    # Strip emojis and special chars that don't speak well
    text = re.sub(r'[\U0001F300-\U0001F9FF]', '', text)
    text = text.replace('*', '').replace('#', '')
    text = text.strip()
    
    if not text:
        return ""
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.minimax.io/v1/t2a_v2",
                headers={
                    "Authorization": f"Bearer {config.MINIMAX_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "speech-2.8-hd",
                    "text": text,
                    "stream": False,
                    "output_format": "hex",
                    "group_id": config.MINIMAX_GROUP_ID,
                    "voice_setting": {
                        "voice_id": "English_expressive_narrator",
                        "speed": 1.0,
                        "vol": 1.0,
                        "pitch": 0,
                    },
                    "audio_setting": {
                        "sample_rate": 32000,
                        "format": "mp3",
                        "channel": 1,
                    },
                },
            ) as resp:
                result_text = await resp.text()
                if resp.status != 200:
                    logger.error(f"TTS error status {resp.status}: {result_text}")
                    return ""
                
                result = json.loads(result_text)
                logger.info(f"TTS response: {result}")
                
                # Response is JSON with hex-encoded audio in data.audio
                audio_hex = result.get("data", {}).get("audio", "")
                if not audio_hex:
                    logger.error(f"TTS error: no audio in response")
                    return ""
                
                # Convert hex to bytes then to base64
                audio_bytes = bytes.fromhex(audio_hex)
                return base64.b64encode(audio_bytes).decode('utf-8')
    except Exception as e:
        logger.exception(f"TTS error: {e}")
        return ""


@app.post("/api/chat")
async def chat(
    audio_file: UploadFile = File(...),
    session_id: str = Cookie(default=None)
):
    """Receive audio blob → transcribe → LLM → return text response."""
    tmp_path = None
    try:
        # Get or create session ID
        if not session_id:
            session_id = str(uuid.uuid4())
            logger.info(f"New session: {session_id}")

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
            return {"text": "Hmm, I didn't catch that! Can you say it again?", "session_id": session_id}
        
        # Extract and store facts from child's speech
        extract_facts(session_id, transcript)
        
        # Build context from memory
        context_prompt = memory.build_context_prompt(session_id)
        facts_prompt = memory.build_facts_prompt(session_id)
        personality_prompt = memory.build_personality_prompt(session_id)
        
        # Combine prompts
        full_prompt = BUBBLES_PROMPT + "\n"
        if facts_prompt:
            full_prompt += facts_prompt + "\n"
        if personality_prompt:
            full_prompt += personality_prompt + "\n"
        if context_prompt:
            full_prompt += context_prompt + "\n"
        full_prompt += f"\nChild: {transcript}"

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
                        {"role": "user", "content": full_prompt}
                    ],
                    "max_tokens": 500,
                },
            ) as resp:
                if resp.status != 200:
                    error = await resp.text()
                    logger.error(f"MiniMax error: {error}")
                    return {"error": "Oops, something went wrong on my end!", "session_id": session_id}
                result = await resp.json()
                
                # Parse response
                content = result.get("content", [])
                reply = "Oops, I didn't catch that!"
                for item in content:
                    if item.get("type") == "text":
                        reply = item.get("text", reply)
                        break

        # Store conversation in memory
        memory.add_message(session_id, "child", transcript)
        memory.add_message(session_id, "bubbles", reply)
        
        # Update personality based on interaction
        update_personality_from_response(session_id, transcript, reply)

        logger.info(f"Bubbles: {reply}")
        
        # Generate TTS audio using MiniMax
        audio_b64 = await generate_tts(reply)
        
        return {
            "text": reply, 
            "session_id": session_id,
            "audio": audio_b64
        }

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
