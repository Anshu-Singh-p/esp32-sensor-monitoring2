/**
 * Edge AI Health Companion - Web Audio API Synthesizer
 * Generates synthetic telemetry blips, cardiac pulse clicks, and alert tones with zero external media files.
 */

class HealthAudioSynth {
  constructor() {
    this.ctx = null;
    this.isMuted = false;
    this.volume = 0.25;
    this.lastBeepTime = 0;
  }

  init() {
    if (!this.ctx) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        this.ctx = new AudioContext();
      }
    }
  }

  ensureContext() {
    if (!this.ctx) {
      this.init();
    }
    if (this.ctx && this.ctx.state === "suspended") {
      this.ctx.resume();
    }
  }

  toggleMute() {
    this.isMuted = !this.isMuted;
    return this.isMuted;
  }

  setVolume(vol) {
    this.volume = Math.max(0, Math.min(1, vol));
  }

  /**
   * Generates a realistic hospital monitor cardiac pulse blip.
   * Pitch is slightly higher for higher heart rate or lower SpO2.
   */
  playPulseBeep(hr = 72, spo2 = 98) {
    if (this.isMuted) return;
    this.ensureContext();
    if (!this.ctx) return;

    const now = this.ctx.currentTime;
    // Throttle beeps to at most once per 350ms
    if (now - this.lastBeepTime < 0.35) return;
    this.lastBeepTime = now;

    // Pitch rises slightly if oxygen saturation drops below 95%
    const baseFreq = 880 + (hr - 70) * 2;
    const freq = spo2 < 92 ? baseFreq * 1.25 : baseFreq;

    const osc = this.ctx.createOscillator();
    const gain = this.ctx.createGain();

    osc.type = "sine";
    osc.frequency.setValueAtTime(freq, now);
    osc.frequency.exponentialRampToValueAtTime(freq * 0.9, now + 0.07);

    gain.gain.setValueAtTime(0.001, now);
    gain.gain.exponentialRampToValueAtTime(this.volume * 0.4, now + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.08);

    osc.connect(gain);
    gain.connect(this.ctx.destination);

    osc.start(now);
    osc.stop(now + 0.085);
  }

  /**
   * Dual-tone cautionary chime for warning alerts.
   */
  playWarningChime() {
    if (this.isMuted) return;
    this.ensureContext();
    if (!this.ctx) return;

    const now = this.ctx.currentTime;
    const notes = [659.25, 880.0]; // E5 to A5

    notes.forEach((freq, idx) => {
      const startTime = now + idx * 0.12;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = "triangle";
      osc.frequency.setValueAtTime(freq, startTime);

      gain.gain.setValueAtTime(0.001, startTime);
      gain.gain.exponentialRampToValueAtTime(this.volume * 0.6, startTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, startTime + 0.22);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start(startTime);
      osc.stop(startTime + 0.25);
    });
  }

  /**
   * Urgent tri-tone alarm siren for critical medical / environmental alerts.
   */
  playCriticalAlarm() {
    if (this.isMuted) return;
    this.ensureContext();
    if (!this.ctx) return;

    const now = this.ctx.currentTime;
    const notes = [987.77, 783.99, 987.77]; // B5, G5, B5

    notes.forEach((freq, idx) => {
      const startTime = now + idx * 0.15;
      const osc = this.ctx.createOscillator();
      const gain = this.ctx.createGain();

      osc.type = "sawtooth";
      osc.frequency.setValueAtTime(freq, startTime);

      gain.gain.setValueAtTime(0.001, startTime);
      gain.gain.exponentialRampToValueAtTime(this.volume * 0.7, startTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, startTime + 0.18);

      osc.connect(gain);
      gain.connect(this.ctx.destination);

      osc.start(startTime);
      osc.stop(startTime + 0.2);
    });
  }
}

window.audioSynth = new HealthAudioSynth();
