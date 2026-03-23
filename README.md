# Bubbles - Kids Chatbot

A push-to-talk chatbot for kids built with MiniMax AI.

## Features

- 🎤 **Push-to-talk** — Hold button to talk, release to get a response
- 🧠 **Memory** — Remembers facts about your child (name, age, preferences)
- 🎙️ **MiniMax TTS** — Natural voice using Radiant Girl voice
- 📱 **Works on mobile** — Browser-based, no app needed
- 💬 **Simple design** — Kid-friendly interface

## Tech Stack

- **Frontend**: HTML/CSS/JS (single page)
- **Backend**: Python/FastAPI
- **STT**: Deepgram (speech to text)
- **LLM**: MiniMax M2.5 (chat)
- **TTS**: MiniMax Speech-2.8-HD (text to speech)
- **Hosting**: Railway

## Setup

### 1. Install dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Environment variables

Create a `.env` file in `backend/`:

```
DEEPGRAM_API_KEY=your_deepgram_key
MINIMAX_API_KEY=your_minimax_llm_key
MINIMAX_TTS_API_KEY=your_minimax_tts_key
MINIMAX_GROUP_ID=your_group_id
```

### 3. Run locally

```bash
cd backend
uvicorn server:app --port 8000 --reload
```

Open `http://localhost:8000` in your browser.

## Deployment

The app deploys automatically to Railway when you push to GitHub.

Set these environment variables in Railway:
- `DEEPGRAM_API_KEY`
- `MINIMAX_API_KEY`
- `MINIMAX_TTS_API_KEY`
- `MINIMAX_GROUP_ID`

## Project Structure

```
bubbles/
├── frontend/
│   └── index.html      # Single-page React-like app
├── backend/
│   ├── server.py       # FastAPI server
│   ├── memory.py       # SQLite memory system
│   └── config.py      # Environment config
├── requirements.txt
└── README.md
```

## How it works

1. Child holds the button and speaks
2. Audio is recorded and sent to Deepgram (STT)
3. Text is sent to MiniMax LLM for a response
4. Response is sent to MiniMax TTS to generate audio
5. Audio plays back to the child
6. Memory is updated (facts extracted, conversation stored)

## For Kids

Bubbles is designed for children under 10. The bot:
- Keeps responses short (1-2 sentences)
- Never asks for personal info
- Avoids inappropriate topics
- Adapts to the child's personality (silly, quiet, enthusiastic)
