const API_BASE = window.location.hostname === "localhost"
  ? "http://localhost:8000"
  : ""; // Same origin in production, or set your Railway URL

const DEFAULT_PIN = "1234";
let storedPin = localStorage.getItem("bubbles_pin");
let callObject = null;
let face = null;
let audioAnalyser = null;
let audioDataArray = null;
let isListening = false;

// ---- PIN ----

const pinScreen = document.getElementById("pin-screen");
const chatScreen = document.getElementById("chat-screen");
const pinDots = document.querySelectorAll("#pin-dots .dot");
const pinStatus = document.getElementById("pin-status");
let pinInput = "";

if (!storedPin) {
  storedPin = DEFAULT_PIN;
  localStorage.setItem("bubbles_pin", storedPin);
}

document.querySelectorAll(".pin-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const digit = btn.dataset.digit;
    if (digit === "clear") {
      pinInput = "";
    } else if (digit === "enter") {
      if (pinInput === storedPin) {
        pinScreen.classList.remove("active");
        chatScreen.classList.add("active");
        initChat();
      } else {
        pinStatus.textContent = "Wrong PIN";
        pinInput = "";
      }
    } else if (pinInput.length < 4) {
      pinInput += digit;
    }
    updatePinDots();
  });
});

function updatePinDots() {
  pinDots.forEach((dot, i) => {
    dot.classList.toggle("filled", i < pinInput.length);
  });
}

// ---- Chat ----

async function initChat() {
  const canvas = document.getElementById("face-canvas");
  face = new BubblesFace(canvas);

  const caption = document.getElementById("caption-text");
  const talkBtn = document.getElementById("talk-btn");
  const talkBtnText = document.getElementById("talk-btn-text");

  caption.textContent = "Connecting to Bubbles...";
  face.setState("thinking");

  try {
    const res = await fetch(`${API_BASE}/api/start`, { method: "POST" });
    if (!res.ok) throw new Error("Server error");
    const data = await res.json();

    callObject = DailyIframe.createCallObject({
      audioSource: true,
      videoSource: false,
    });

    callObject.on("joined-meeting", () => {
      caption.textContent = "Bubbles is waking up...";
      callObject.setLocalAudio(false);
      talkBtn.disabled = false;
    });

    callObject.on("track-started", (event) => {
      if (event.participant && !event.participant.local && event.track.kind === "audio") {
        setupAudioAnalysis(event.track);
        face.setState("talking");
      }
    });

    callObject.on("track-stopped", (event) => {
      if (event.participant && !event.participant.local && event.track.kind === "audio") {
        face.setState("idle");
        face.setMouthOpenness(0);
      }
    });

    callObject.on("app-message", (event) => {
      if (event.data && event.data.text) {
        caption.textContent = event.data.text;
      }
    });

    callObject.on("participant-left", (event) => {
      if (event.participant && !event.participant.local) {
        caption.textContent = "Bubbles went to sleep. Bye bye!";
        face.setState("idle");
        talkBtn.disabled = true;
      }
    });

    await callObject.join({ url: data.room_url, token: data.token });

    // Push-to-talk
    const startListening = () => {
      if (talkBtn.disabled) return;
      isListening = true;
      callObject.setLocalAudio(true);
      talkBtn.classList.add("listening");
      talkBtnText.textContent = "Listening...";
      face.setState("listening");
      caption.textContent = "I'm listening...";
    };

    const stopListening = () => {
      if (!isListening) return;
      isListening = false;
      callObject.setLocalAudio(false);
      talkBtn.classList.remove("listening");
      talkBtnText.textContent = "Hold to Talk";
      face.setState("thinking");
      caption.textContent = "Hmm, let me think...";
    };

    // Mouse
    talkBtn.addEventListener("mousedown", startListening);
    talkBtn.addEventListener("mouseup", stopListening);
    talkBtn.addEventListener("mouseleave", stopListening);

    // Touch
    talkBtn.addEventListener("touchstart", (e) => { e.preventDefault(); startListening(); });
    talkBtn.addEventListener("touchend", (e) => { e.preventDefault(); stopListening(); });
    talkBtn.addEventListener("touchcancel", stopListening);

  } catch (err) {
    caption.textContent = "Oops! Could not connect. Try again later.";
    console.error("Connection error:", err);
  }
}

// ---- Audio Analysis for Mouth Sync ----

function setupAudioAnalysis(track) {
  try {
    const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const stream = new MediaStream([track]);
    const source = audioCtx.createMediaStreamSource(stream);
    audioAnalyser = audioCtx.createAnalyser();
    audioAnalyser.fftSize = 256;
    audioAnalyser.smoothingTimeConstant = 0.5;
    source.connect(audioAnalyser);
    audioDataArray = new Uint8Array(audioAnalyser.frequencyBinCount);
    analyzeMouth();
  } catch (err) {
    console.error("Audio analysis setup error:", err);
  }
}

function analyzeMouth() {
  if (!audioAnalyser) return;
  audioAnalyser.getByteFrequencyData(audioDataArray);

  let sum = 0;
  for (let i = 0; i < audioDataArray.length; i++) {
    sum += audioDataArray[i];
  }
  const avg = sum / audioDataArray.length;
  const openness = Math.min(1, avg / 80);

  if (face && face.state === "talking") {
    face.setMouthOpenness(openness);
  }

  requestAnimationFrame(analyzeMouth);
}
