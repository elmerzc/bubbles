class BubblesFace {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.state = "idle"; // idle, listening, thinking, talking
    this.mouthOpenness = 0;
    this.targetMouthOpenness = 0;
    this.blinkTimer = 0;
    this.blinkState = 0; // 0 = open, 1 = closing, 2 = closed, 3 = opening
    this.pupilOffsetX = 0;
    this.pupilOffsetY = 0;
    this.targetPupilX = 0;
    this.targetPupilY = 0;
    this.pupilDriftTimer = 0;
    this.bouncePhase = 0;
    this.time = 0;

    this.resize();
    window.addEventListener("resize", () => this.resize());
    this.animate();
  }

  resize() {
    const rect = this.canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.ctx.scale(dpr, dpr);
    this.w = rect.width;
    this.h = rect.height;
    this.cx = this.w / 2;
    this.cy = this.h / 2;
    this.size = Math.min(this.w, this.h) * 0.4;
  }

  setState(state) {
    this.state = state;
  }

  setMouthOpenness(value) {
    this.targetMouthOpenness = Math.min(1, Math.max(0, value));
  }

  animate() {
    const dt = 1 / 60;
    this.time += dt;
    this.bouncePhase += dt;

    this.updateBlink(dt);
    this.updatePupils(dt);
    this.mouthOpenness += (this.targetMouthOpenness - this.mouthOpenness) * 0.3;

    if (this.state !== "talking") {
      this.targetMouthOpenness = 0;
    }

    this.draw();
    requestAnimationFrame(() => this.animate());
  }

  updateBlink(dt) {
    this.blinkTimer -= dt;
    if (this.blinkTimer <= 0 && this.blinkState === 0) {
      this.blinkState = 1;
      this.blinkTimer = 0.08;
    } else if (this.blinkTimer <= 0 && this.blinkState === 1) {
      this.blinkState = 2;
      this.blinkTimer = 0.05;
    } else if (this.blinkTimer <= 0 && this.blinkState === 2) {
      this.blinkState = 3;
      this.blinkTimer = 0.08;
    } else if (this.blinkTimer <= 0 && this.blinkState === 3) {
      this.blinkState = 0;
      this.blinkTimer = 2 + Math.random() * 4;
    }
  }

  updatePupils(dt) {
    this.pupilDriftTimer -= dt;
    if (this.pupilDriftTimer <= 0) {
      if (this.state === "thinking") {
        this.targetPupilX = -0.3 + Math.random() * 0.2;
        this.targetPupilY = -0.4;
      } else if (this.state === "listening") {
        this.targetPupilX = 0;
        this.targetPupilY = 0;
      } else {
        this.targetPupilX = (Math.random() - 0.5) * 0.4;
        this.targetPupilY = (Math.random() - 0.5) * 0.3;
      }
      this.pupilDriftTimer = 1 + Math.random() * 2;
    }
    this.pupilOffsetX += (this.targetPupilX - this.pupilOffsetX) * 0.05;
    this.pupilOffsetY += (this.targetPupilY - this.pupilOffsetY) * 0.05;
  }

  getBlinkScale() {
    if (this.blinkState === 0) return 1;
    if (this.blinkState === 1) return Math.max(0.05, this.blinkTimer / 0.08);
    if (this.blinkState === 2) return 0.05;
    if (this.blinkState === 3) return 1 - (this.blinkTimer / 0.08);
    return 1;
  }

  draw() {
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.w, this.h);

    const bounce = Math.sin(this.bouncePhase * 1.5) * this.size * 0.02;
    const bodyY = this.cy + bounce;

    // Body
    ctx.beginPath();
    ctx.arc(this.cx, bodyY, this.size, 0, Math.PI * 2);
    const bodyGrad = ctx.createRadialGradient(
      this.cx - this.size * 0.3, bodyY - this.size * 0.3, this.size * 0.1,
      this.cx, bodyY, this.size
    );
    bodyGrad.addColorStop(0, "#a78bfa");
    bodyGrad.addColorStop(1, "#7c3aed");
    ctx.fillStyle = bodyGrad;
    ctx.fill();

    // Cheeks
    ctx.beginPath();
    ctx.arc(this.cx - this.size * 0.55, bodyY + this.size * 0.15, this.size * 0.15, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(251, 191, 207, 0.4)";
    ctx.fill();
    ctx.beginPath();
    ctx.arc(this.cx + this.size * 0.55, bodyY + this.size * 0.15, this.size * 0.15, 0, Math.PI * 2);
    ctx.fill();

    // Eyes
    const eyeSpacing = this.size * 0.3;
    const eyeY = bodyY - this.size * 0.1;
    const eyeW = this.size * 0.22;
    const eyeH = this.size * 0.28;
    const blinkScale = this.getBlinkScale();

    this.drawEye(ctx, this.cx - eyeSpacing, eyeY, eyeW, eyeH * blinkScale);
    this.drawEye(ctx, this.cx + eyeSpacing, eyeY, eyeW, eyeH * blinkScale);

    // Mouth
    this.drawMouth(ctx, this.cx, bodyY + this.size * 0.35);
  }

  drawEye(ctx, x, y, w, h) {
    // White
    ctx.beginPath();
    ctx.ellipse(x, y, w, Math.max(h, 1), 0, 0, Math.PI * 2);
    ctx.fillStyle = "#fff";
    ctx.fill();

    if (h > w * 0.2) {
      // Pupil
      const pupilR = w * 0.5;
      const px = x + this.pupilOffsetX * w * 0.5;
      const py = y + this.pupilOffsetY * h * 0.3;
      ctx.beginPath();
      ctx.arc(px, py, pupilR, 0, Math.PI * 2);
      ctx.fillStyle = "#1a1a2e";
      ctx.fill();

      // Shine
      ctx.beginPath();
      ctx.arc(px + pupilR * 0.3, py - pupilR * 0.3, pupilR * 0.3, 0, Math.PI * 2);
      ctx.fillStyle = "#fff";
      ctx.fill();
    }
  }

  drawMouth(ctx, x, y) {
    const mouthW = this.size * 0.3;
    const open = this.mouthOpenness;

    if (this.state === "thinking") {
      // Small o shape
      ctx.beginPath();
      ctx.arc(x + this.size * 0.1, y, this.size * 0.06, 0, Math.PI * 2);
      ctx.fillStyle = "#4c1d95";
      ctx.fill();
    } else if (open > 0.05) {
      // Open mouth (talking)
      const mouthH = mouthW * 0.6 * open;
      ctx.beginPath();
      ctx.ellipse(x, y, mouthW, mouthH, 0, 0, Math.PI * 2);
      ctx.fillStyle = "#4c1d95";
      ctx.fill();
      // Tongue hint
      if (open > 0.3) {
        ctx.beginPath();
        ctx.ellipse(x, y + mouthH * 0.4, mouthW * 0.5, mouthH * 0.4, 0, 0, Math.PI);
        ctx.fillStyle = "#e879a0";
        ctx.fill();
      }
    } else {
      // Smile
      ctx.beginPath();
      ctx.arc(x, y - this.size * 0.05, mouthW, 0.1 * Math.PI, 0.9 * Math.PI);
      ctx.strokeStyle = "#4c1d95";
      ctx.lineWidth = this.size * 0.04;
      ctx.lineCap = "round";
      ctx.stroke();
    }
  }
}
