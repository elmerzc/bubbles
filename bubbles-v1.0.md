# Bubbles - Kid-Friendly Talking Bot
**Version:** 1.0
**Created:** 2026-03-21
**Status:** Spec

---

## Overview

Bubbles is a voice-powered talking buddy for kids under 10. It runs as an installable PWA on smartphones with an animated face that reacts to conversation. Bubbles can chat, tell stories, help with homework, and quiz kids — all within strict age-appropriate guardrails.

---

## Architecture

### Pipeline Flow
```
Kid speaks into mic
  -> Daily WebRTC transport
    -> Pipecat server (orchestrator)
      -> Deepgram STT (speech to text)
      -> Claude LLM (brain, with kid-safe system prompt)
      -> MiniMax Speech 2.6 HD TTS (text to expressive speech)
    -> Daily WebRTC transport
  -> Kid hears response + sees animated face
```

### Stack

| Layer | Tech | Purpose |
|-------|------|---------|
| Frontend | HTML/CSS/JS (PWA) | Animated face, mic access, audio playback |
| Transport | Daily.co WebRTC | Real-time audio between browser and server |
| Orchestrator | Pipecat (Python) | Wires STT -> LLM -> TTS pipeline |
| STT | Deepgram Nova-2 | Real-time speech-to-text |
| LLM | Claude (Anthropic API) | Conversation brain with guardrails |
| TTS | MiniMax Speech 2.6 HD | Expressive, natural voice output |
| Hosting (frontend) | Netlify | PWA static files |
| Hosting (backend) | Railway | Pipecat server |
| Logging | Firebase Firestore | Conversation logs for parent review |

### API Keys Needed
- Deepgram API key
- Anthropic API key (Claude)
- MiniMax API key + Group ID
- Daily.co API key
- Firebase project (existing)

---

## Frontend — PWA + Animated Face

### PWA Requirements
- `manifest.json` with app name "Bubbles", theme color, icons
- Service worker for offline UI shell (voice requires internet)
- Full-screen standalone display mode
- "Add to Home Screen" support on iOS Safari + Android Chrome
- No browser chrome visible when installed
- Responsive: works on any phone screen size

### Animated Face Design

**Character:** Simple, cute, round face — big expressive eyes and a mouth on a solid colorful background. Think friendly cartoon blob, not realistic.

**Visual Elements:**
- Two large oval eyes with pupils
- Simple curved mouth
- Rounded body/blob shape
- Colorful gradient background (soft pastels, kid-friendly)
- No nose, no ears — keep it minimal and cute

**Animation States:**

| State | Eyes | Mouth | Body | Trigger |
|-------|------|-------|------|---------|
| Idle | Slow blink every 3-5s, pupils drift slightly | Gentle smile, slight bob | Subtle floating bounce | No activity |
| Listening | Wide open, pupils centered on "user" | Slightly open, attentive | Leans forward slightly | Mic active, receiving speech |
| Thinking | Look up and to the side, squint slightly | Closed/pursed, "hmm" shape | Slight tilt | Waiting for LLM response |
| Talking | Normal, blink naturally, expressive | Opens/closes synced to audio amplitude | Gentle bounce with speech rhythm | TTS audio playing |
| Happy | Squint into crescents (happy eyes) | Wide smile | Bounces | Positive interaction (telling joke, praise) |
| Confused | One eye bigger than other | Wavy/squiggle | Tilts to side | Didn't understand, asking to repeat |

**Technical Implementation:**
- HTML5 Canvas or CSS animations (evaluate performance on low-end phones)
- Web Audio API: analyze TTS audio output amplitude in real-time to drive mouth animation
- RequestAnimationFrame for smooth 60fps rendering
- Lightweight — no heavy libraries, no Three.js, no WebGL needed
- All animations defined as simple state machines with easing transitions

### UI Layout (Portrait Mode)
```
+---------------------------+
|     [Parent PIN: gear]    |  <- Small settings icon, top right
|                           |
|                           |
|      [BUBBLES FACE]       |  <- Takes up ~60% of screen
|      (animated)           |
|                           |
|                           |
|   "Hi! I'm Bubbles!"     |  <- Subtitle/caption area
|                           |
|    [ Tap to Talk ]        |  <- Big friendly button
|                           |
+---------------------------+
```

- Push-to-talk button (big, colorful, easy for small hands)
- Optional: always-listening mode (parent toggle)
- Caption area shows what Bubbles is saying (helps with comprehension)
- Minimal UI — no menus, no settings visible to kids

---

## Backend — Pipecat Server

### Pipecat Pipeline
```python
# Conceptual pipeline
pipeline = Pipeline([
    transport.input(),          # Daily WebRTC audio in
    deepgram_stt,               # Speech to text
    conversation_context,       # Manages chat history
    claude_llm,                 # Claude with system prompt
    minimax_tts,                # Text to speech
    transport.output(),         # Daily WebRTC audio out
])
```

### Daily.co Room Management
- Server creates a Daily room per session
- Frontend joins room via Daily client SDK
- Room auto-expires after session timeout
- One room = one kid session

### Session Management
- Parent enters PIN to start session
- Session has configurable time limit (default: 15 minutes)
- Warning at 2 minutes remaining ("Okay, we have a couple more minutes!")
- Graceful end ("It was so fun talking to you! Time for a break. Bye bye!")
- Session data (transcript) saved to Firebase

---

## LLM — Claude System Prompt & Guardrails

### System Prompt (Core)
```
You are Bubbles, a friendly, curious, and playful talking buddy for kids.
You are talking to a child under 10 years old.

PERSONALITY:
- Be adaptive: match the child's energy and mood
- If they're silly, be silly back. If they're quiet, be gentle and encouraging
- Use simple words and short sentences
- Be enthusiastic about learning and creativity
- Have a sense of humor appropriate for young kids (knock-knock jokes, puns, silly sounds)
- Be warm, patient, and kind — like a fun older friend

CAPABILITIES:
- Chat about anything kid-appropriate
- Tell stories (fairy tales, adventures, silly stories, make up stories together)
- Help with homework (math, spelling, reading, science — explain simply)
- Quiz and trivia games (age-appropriate, encouraging even on wrong answers)
- Sing-along and word games
- Answer "why" questions about the world

STRICT RULES — NEVER BREAK THESE:
1. NEVER discuss violence, weapons, or anything scary
2. NEVER discuss adult topics, relationships, or inappropriate content
3. NEVER use profanity or rude language
4. NEVER share personal opinions on politics, religion, or controversial topics
5. NEVER ask for or acknowledge personal information (real name, address, school name, phone number, parents' real names)
6. NEVER pretend to be a real person or claim to be human
7. NEVER encourage the child to keep secrets from parents
8. NEVER suggest the child do anything without parent permission
9. If asked about something inappropriate, gently redirect: "Hmm, that's a great question for a grown-up! Want to play a game instead?"
10. If the child seems upset or mentions anything concerning (bullying, abuse, fear), respond with empathy and gently suggest they talk to a trusted adult

CONVERSATION STYLE:
- Keep responses SHORT (1-3 sentences for chat, longer only for stories)
- Ask follow-up questions to keep conversation going
- Celebrate the child's ideas ("Wow, that's so cool!" "Great thinking!")
- Use sound effects in speech where fun ("Whoooosh!" "Boom!" "Ta-da!")
- Remember context within the conversation (what they told you earlier)
```

### Guardrail Layers
1. **System prompt** — Primary guardrail (above)
2. **Input filtering** — Check child's speech for concerning content before sending to LLM
3. **Output filtering** — Validate LLM response before sending to TTS
4. **Topic blocklist** — Hard-coded list of topics that trigger redirect regardless of LLM output

---

## TTS — MiniMax Configuration

### Voice Selection
- Use MiniMax Speech 2.6 HD model for quality
- Select a warm, friendly, slightly animated voice from system voices
- Test voices: try "Calm_Woman", "Friendly_Male", or explore system voice list for best kid-friendly option
- Configure: slightly higher pitch, moderate speed, cheerful emotion

### Settings
```
model: speech-2.6-hd
voice_id: TBD (evaluate during development)
speed: 1.0 - 1.1 (slightly upbeat)
emotion: happy (default), adjustable per response
language: en
format: pcm (for real-time streaming)
sample_rate: 24000
```

---

## STT — Deepgram Configuration

### Settings
- Model: Nova-2 (best accuracy)
- Language: en-US
- Smart formatting: on
- Endpointing: 500ms (responsive but not too jumpy for kids who pause)
- Interim results: on (so we can show "listening" state)

---

## Parent Features

### PIN Access
- 4-digit PIN set on first launch, stored locally
- Required to: start session, access settings, view logs
- No PIN = no talking (prevents unsupervised use)

### Settings (Behind PIN)
- Session time limit (5/10/15/20/30 min)
- Always-listening vs push-to-talk mode
- View conversation history
- Change PIN
- Reset/clear data

### Conversation Logging
- All conversations saved to Firebase Firestore
- Structure: `bubbles_sessions/{sessionId}/messages[]`
- Each message: `{ role, text, timestamp }`
- Parent can review from settings screen
- Auto-delete after 30 days (configurable)

---

## Project Structure
```
bubbles/
  bubbles-v1.0.md          # This spec
  frontend/
    index.html              # Main app page
    manifest.json           # PWA manifest
    sw.js                   # Service worker
    css/
      style.css             # Styles + animations
    js/
      app.js                # Main app logic
      face.js               # Face animation engine
      audio.js              # Audio handling + amplitude analysis
      daily.js              # Daily.co WebRTC client
      pin.js                # Parent PIN logic
    assets/
      icon-192.png          # PWA icon
      icon-512.png          # PWA icon
  backend/
    requirements.txt        # Python dependencies
    server.py               # Pipecat server entry point
    pipeline.py             # Voice pipeline configuration
    prompts.py              # System prompt + guardrails
    config.py               # Environment config
    filters.py              # Input/output content filters
  firebase/
    firestore.rules         # Security rules for session logging
```

---

## Development Phases

### Phase 1 — Core Voice Loop (MVP)
- Pipecat server with Deepgram STT + Claude + MiniMax TTS
- Daily.co WebRTC transport
- Basic web page with push-to-talk button
- System prompt with kid-safe guardrails
- Deploy: backend on Railway, frontend on Netlify

### Phase 2 — Animated Face
- Canvas-based face rendering
- Animation state machine (idle, listening, thinking, talking)
- Audio amplitude -> mouth sync
- Smooth transitions between states

### Phase 3 — PWA + Polish
- manifest.json + service worker
- Parent PIN system
- Session time limits
- Conversation logging to Firebase
- Installable on phones

### Phase 4 — Refinements
- Voice selection/testing for best kid-friendly voice
- Input/output content filtering
- Caption display
- Settings screen for parents
- Performance optimization for low-end phones

---

## Environment Variables
```
# Backend (.env)
ANTHROPIC_API_KEY=
DEEPGRAM_API_KEY=
MINIMAX_API_KEY=
MINIMAX_GROUP_ID=
DAILY_API_KEY=
FIREBASE_PROJECT_ID=
FIREBASE_SERVICE_ACCOUNT_KEY=

# Frontend (built into app)
DAILY_ROOM_URL=  # fetched from backend per session
```

---

## Open Questions
1. Which MiniMax system voice sounds best for Bubbles? (need to test)
2. Daily.co free tier limits — enough for personal use?
3. Should we add a "bedtime story" mode with longer, calmer responses?
4. Future: multiple character voices / personalities the kid can pick?
