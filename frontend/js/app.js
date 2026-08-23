/**
 * ESP32 Sensor Monitoring - Main Dashboard Controller
 * Synchronizes WebSocket/SSE streams, REST mutations, threshold modal, and alert triage.
 */

class DashboardApp {
  constructor() {
    this.eventSource = null;
    this.lastPacketTime = 0;
    this.envType = "BME280";
    this.activeTimeRange = "5m";
    this.alertFilter = "ALL";
    this.isMuted = false;
    this.audioCtx = null;
    this.knownAlertIds = new Set();

    document.addEventListener("DOMContentLoaded", () => this.init());
  }

  init() {
    this.setupEventListeners();
    this.startStreaming();
    this.fetchHistory();
    this.fetchAlerts();
    this.fetchDeviceStatus();

    // Periodic tasks
    setInterval(() => this.updateHeartbeatTimer(), 1000);
    setInterval(() => this.fetchHistory(), 4000);
    setInterval(() => this.fetchAlerts(), 3000);

    // Audio init on user gesture
    document.body.addEventListener("click", () => {
      if (!this.audioCtx) {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (AudioContext) this.audioCtx = new AudioContext();
      }
    }, { once: true });
  }

  setupEventListeners() {
    // Time range buttons
    document.querySelectorAll(".time-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".time-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        this.activeTimeRange = btn.dataset.range;
        if (window.multiSensorCharts) window.multiSensorCharts.setRange(this.activeTimeRange);
        this.fetchHistory();
      });
    });

    // Alert filter buttons
    document.querySelectorAll(".filter-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        this.alertFilter = btn.dataset.filter;
        this.fetchAlerts();
      });
    });

    // Modal triggers (Thresholds)
    const thBtn = document.getElementById("openThresholdsBtn");
    const thModal = document.getElementById("thresholdModal");
    const closeThBtn = document.getElementById("closeThresholdModal");
    const saveThBtn = document.getElementById("saveThresholdsBtn");

    if (thBtn && thModal) {
      thBtn.addEventListener("click", () => {
        this.loadThresholdsForm();
        thModal.classList.add("active");
      });
    }
    if (closeThBtn && thModal) {
      closeThBtn.addEventListener("click", () => thModal.classList.remove("active"));
    }
    if (saveThBtn) {
      saveThBtn.addEventListener("click", () => this.saveThresholdsForm());
    }

    // Modal triggers (Calibration)
    const calBtn = document.getElementById("openCalibrationBtn");
    const calModal = document.getElementById("calibrationModal");
    const closeCalBtn = document.getElementById("closeCalibrationModal");
    const saveCalBtn = document.getElementById("saveCalibrationBtn");

    if (calBtn && calModal) {
      calBtn.addEventListener("click", () => {
        this.loadCalibrationForm();
        calModal.classList.add("active");
      });
    }
    if (closeCalBtn && calModal) {
      closeCalBtn.addEventListener("click", () => calModal.classList.remove("active"));
    }
    if (saveCalBtn) {
      saveCalBtn.addEventListener("click", () => this.saveCalibrationForm());
    }

    // Simulator Scenario Buttons
    document.querySelectorAll(".sim-scenario-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        const scenario = btn.dataset.scenario;
        this.setSimulationScenario(scenario);
      });
    });

    // Audio mute toggle
    const muteBtn = document.getElementById("muteToggleBtn");
    if (muteBtn) {
      muteBtn.addEventListener("click", () => {
        this.isMuted = !this.isMuted;
        muteBtn.textContent = this.isMuted ? "🔇 Audio Muted" : "🔊 Audio On";
        muteBtn.classList.toggle("muted", this.isMuted);
      });
    }
  }

  startStreaming() {
    if (this.eventSource) this.eventSource.close();

    this.eventSource = new EventSource("/api/stream");

    this.eventSource.onopen = () => {
      this.setOnlineStatus(true);
    };

    this.eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.renderTelemetry(data);
      } catch (err) {
        console.error("Stream parse error:", err);
      }
    };

    this.eventSource.onerror = () => {
      this.setOnlineStatus(false);
      // Fallback polling
      setTimeout(() => this.fallbackPoll(), 2000);
    };
  }

  fallbackPoll() {
    fetch("/api/sensor-data/latest")
      .then(res => res.json())
      .then(data => {
        if (data.status !== "NO_DATA") {
          this.renderTelemetry(data);
        }
      })
      .catch(() => this.setOnlineStatus(false));
  }

  renderTelemetry(data) {
    this.lastPacketTime = Date.now();
    this.setOnlineStatus(data.is_online !== false);

    // Update Environmental Sensor Type (BME280 vs BMP280)
    const envType = data.env_sensor_type || "BME280";
    this.envType = envType;
    this.updateEnvLayout(envType);

    // 1. Render MAX30102
    if (data.max30102) {
      const m = data.max30102;
      const hrEl = document.getElementById("valHeartRate");
      const hrPill = document.getElementById("pillHeartRate");
      const spo2El = document.getElementById("valSpO2");
      const spo2Pill = document.getElementById("pillSpO2");
      const sigEl = document.getElementById("valSigQuality");
      const contactEl = document.getElementById("valContactStatus");
      const rawOpticalEl = document.getElementById("valRawOptical");

      if (m.finger_detected && m.heart_rate !== null) {
        if (hrEl) hrEl.textContent = Math.round(m.heart_rate);
        if (hrPill) {
          hrPill.textContent = m.status || "NORMAL";
          hrPill.className = `status-pill ${m.status || "NORMAL"}`;
        }
      } else {
        if (hrEl) hrEl.textContent = "--";
        if (hrPill) {
          hrPill.textContent = "NO CONTACT";
          hrPill.className = "status-pill INVALID";
        }
      }

      if (m.finger_detected && m.spo2 !== null) {
        if (spo2El) spo2El.textContent = m.spo2.toFixed(1);
        if (spo2Pill) {
          spo2Pill.textContent = m.status || "NORMAL";
          spo2Pill.className = `status-pill ${m.status || "NORMAL"}`;
        }
      } else {
        if (spo2El) spo2El.textContent = "--";
        if (spo2Pill) {
          spo2Pill.textContent = "NO CONTACT";
          spo2Pill.className = "status-pill INVALID";
        }
      }

      if (sigEl) sigEl.textContent = `${Math.round(m.signal_quality || 0)}%`;
      if (contactEl) {
        contactEl.textContent = m.finger_detected ? "Finger Detected" : "No Finger Contact";
        contactEl.style.color = m.finger_detected ? "#34d399" : "#f87171";
      }
      if (rawOpticalEl) {
        rawOpticalEl.textContent = `IR: ${m.raw_ir || 0} | Red: ${m.raw_red || 0}`;
      }
    }

    // 2. Render MPU6050
    if (data.mpu6050) {
      const mpu = data.mpu6050;
      const axEl = document.getElementById("valAx");
      const ayEl = document.getElementById("valAy");
      const azEl = document.getElementById("valAz");
      const amagEl = document.getElementById("valAccelMag");

      const gxEl = document.getElementById("valGx");
      const gyEl = document.getElementById("valGy");
      const gzEl = document.getElementById("valGz");
      const gmagEl = document.getElementById("valGyroMag");

      const actEl = document.getElementById("valActivity");
      const fallBanner = document.getElementById("fallEventBanner");

      if (axEl) axEl.textContent = mpu.accel_x.toFixed(2);
      if (ayEl) ayEl.textContent = mpu.accel_y.toFixed(2);
      if (azEl) azEl.textContent = mpu.accel_z.toFixed(2);
      if (amagEl) amagEl.textContent = mpu.accel_magnitude.toFixed(2);

      if (gxEl) gxEl.textContent = mpu.gyro_x.toFixed(1);
      if (gyEl) gyEl.textContent = mpu.gyro_y.toFixed(1);
      if (gzEl) gzEl.textContent = mpu.gyro_z.toFixed(1);
      if (gmagEl) gmagEl.textContent = Math.round(mpu.gyro_magnitude);

      if (actEl) {
        actEl.textContent = mpu.activity || "STATIONARY";
        actEl.className = `status-pill ${mpu.activity === "HIGH ACTIVITY" ? "HIGH" : "NORMAL"}`;
      }

      if (fallBanner) {
        if (mpu.fall_event) {
          fallBanner.classList.remove("hidden");
        } else {
          fallBanner.classList.add("hidden");
        }
      }
    }

    // 3. Render Environment (BME280 / BMP280)
    if (data.environment) {
      const env = data.environment;
      const tempEl = document.getElementById("valTemperature");
      const tempPill = document.getElementById("pillTemperature");
      const pressEl = document.getElementById("valPressure");
      const pressPill = document.getElementById("pillPressure");
      const humEl = document.getElementById("valHumidity");
      const humPill = document.getElementById("pillHumidity");

      if (tempEl) tempEl.textContent = env.temperature !== null ? env.temperature.toFixed(1) : "--";
      if (tempPill) {
        tempPill.textContent = env.temp_status || "NORMAL";
        tempPill.className = `status-pill ${env.temp_status || "NORMAL"}`;
      }

      if (pressEl) pressEl.textContent = env.pressure !== null ? Math.round(env.pressure) : "--";
      if (pressPill) {
        pressPill.textContent = env.pressure_status || "NORMAL";
        pressPill.className = `status-pill ${env.pressure_status || "NORMAL"}`;
      }

      if (envType === "BME280" && env.humidity !== null) {
        if (humEl) humEl.textContent = env.humidity.toFixed(1);
        if (humPill) {
          humPill.textContent = env.humidity_status || "NORMAL";
          humPill.className = `status-pill ${env.humidity_status || "NORMAL"}`;
        }
      }
    }

    // 4. Update Sensor Connection List
    if (data.sensor_statuses) {
      this.renderSensorStatuses(data.sensor_statuses);
    }
  }

  updateEnvLayout(envType) {
    const badge = document.getElementById("envSensorChipTag");
    const humCard = document.getElementById("envHumidityCard");
    const envGrid = document.getElementById("envGridContainer");

    if (badge) {
      badge.textContent = envType === "BME280" ? "BME280 (Temp/Hum/Press)" : "BMP280 (Temp/Press)";
    }

    if (envType === "BMP280") {
      if (humCard) humCard.classList.add("hidden");
      if (envGrid) envGrid.classList.add("bmp280-mode");
    } else {
      if (humCard) humCard.classList.remove("hidden");
      if (envGrid) envGrid.classList.remove("bmp280-mode");
    }

    if (window.multiSensorCharts) {
      window.multiSensorCharts.setEnvType(envType);
    }
  }

  setOnlineStatus(isOnline) {
    const pill = document.getElementById("deviceStatusPill");
    const text = document.getElementById("deviceStatusText");
    if (pill && text) {
      if (isOnline) {
        pill.className = "device-status-pill";
        text.textContent = "ESP32: ONLINE";
      } else {
        pill.className = "device-status-pill offline";
        text.textContent = "ESP32: OFFLINE";
      }
    }
  }

  updateHeartbeatTimer() {
    const timerEl = document.getElementById("lastUpdateTimer");
    if (!timerEl || !this.lastPacketTime) return;

    const diffSec = Math.floor((Date.now() - this.lastPacketTime) / 1000);
    if (diffSec < 2) {
      timerEl.textContent = "Last update: Just now";
    } else {
      timerEl.textContent = `Last update: ${diffSec}s ago`;
    }

    if (diffSec > 6) {
      this.setOnlineStatus(false);
    }
  }

  fetchHistory() {
    fetch(`/api/sensor-data/history?range=${this.activeTimeRange}`)
      .then(res => res.json())
      .then(res => {
        if (window.multiSensorCharts && res.data) {
          window.multiSensorCharts.updateData(res.data, this.envType);
        }
      })
      .catch(err => console.error("History fetch error:", err));
  }

  fetchAlerts() {
    const url = this.alertFilter === "ALL" ? "/api/alerts" : `/api/alerts?status=${this.alertFilter}`;
    fetch(url)
      .then(res => res.json())
      .then(res => {
        this.renderAlertsList(res.alerts || []);
      })
      .catch(err => console.error("Alerts fetch error:", err));
  }

  renderAlertsList(alerts) {
    const feed = document.getElementById("alertsFeedContainer");
    const badge = document.getElementById("activeAlertsBadge");
    if (!feed) return;

    const activeCount = alerts.filter(a => a.status === "ACTIVE").length;
    if (badge) {
      badge.textContent = `${activeCount} Active`;
      badge.className = activeCount > 0 ? "status-pill CRITICAL" : "status-pill NORMAL";
    }

    if (alerts.length === 0) {
      feed.innerHTML = `<div style="text-align:center; padding: 2rem; color: var(--text-muted); font-size: 0.82rem;">No alerts matching filter '${this.alertFilter}'.</div>`;
      return;
    }

    // Audio trigger on new alert
    alerts.forEach(a => {
      if (a.status === "ACTIVE" && !this.knownAlertIds.has(a.id)) {
        this.knownAlertIds.add(a.id);
        this.playAlertTone(a.severity);
      }
    });

    feed.innerHTML = alerts.map(a => {
      const dt = new Date(a.timestamp * 1000).toLocaleTimeString();
      return `
        <div class="alert-row ${a.severity}">
          <div class="alert-row-header">
            <div style="display:flex; align-items:center; gap: 0.5rem;">
              <span class="status-pill ${a.severity}">${a.severity}</span>
              <span style="font-weight:600; font-size:0.85rem;">${a.sensor} • ${a.parameter.toUpperCase()}</span>
            </div>
            <div style="font-size:0.72rem; color:var(--text-muted); font-family:var(--font-mono);">${dt}</div>
          </div>
          <div style="font-size:0.8rem; color:var(--text-primary);">${a.message}</div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;">
            <span style="font-size:0.7rem; color:var(--text-muted);">Status: <strong>${a.status}</strong></span>
            <div class="alert-actions">
              ${a.status === "ACTIVE" ? `<button class="btn-alert-action" onclick="window.dashboardApp.updateAlert('${a.id}', 'ACKNOWLEDGED')">Acknowledge</button>` : ""}
              ${a.status !== "RESOLVED" ? `<button class="btn-alert-action" onclick="window.dashboardApp.updateAlert('${a.id}', 'RESOLVED')">Resolve</button>` : ""}
            </div>
          </div>
        </div>
      `;
    }).join("");
  }

  updateAlert(alertId, newStatus) {
    const action = newStatus === "ACKNOWLEDGED" ? "acknowledge" : "resolve";
    fetch(`/api/v1/alerts/${alertId}/${action}`, {
      method: "POST"
    }).then(() => this.fetchAlerts());
  }

  fetchDeviceStatus() {
    fetch("/api/device/status")
      .then(res => res.json())
      .then(data => {
        if (data.sensors) this.renderSensorStatuses(data.sensors);
      });
  }

  renderSensorStatuses(statuses) {
    const list = document.getElementById("sensorStatusList");
    if (!list) return;

    const sensorKeys = ["MAX30102", "MPU6050", this.envType];
    list.innerHTML = sensorKeys.map(k => {
      const info = statuses[k] || { status: "CONNECTED", last_valid_reading: Date.now() / 1000 };
      const isConn = info.status === "CONNECTED";
      const dt = info.last_valid_reading ? new Date(info.last_valid_reading * 1000).toLocaleTimeString() : "--";
      return `
        <div class="sensor-status-item">
          <div class="sensor-name-group">
            <div class="sensor-dot ${isConn ? "" : "disconnected"}"></div>
            <span>${k}</span>
          </div>
          <div style="text-align:right;">
            <div style="font-size:0.75rem; font-weight:600; color:${isConn ? "#34d399" : "#f87171"};">${info.status}</div>
            <div style="font-size:0.65rem; color:var(--text-muted);">Last: ${dt}</div>
          </div>
        </div>
      `;
    }).join("");
  }

  loadThresholdsForm() {
    fetch("/api/thresholds")
      .then(res => res.json())
      .then(data => {
        const cfgs = data.configurable_thresholds;
        if (!cfgs) return;

        this.setInputValue("th_hr_low", cfgs.heart_rate?.low_threshold);
        this.setInputValue("th_hr_high", cfgs.heart_rate?.high_threshold);
        this.setInputValue("th_spo2_norm", cfgs.spo2?.normal_min);
        this.setInputValue("th_spo2_caut", cfgs.spo2?.caution_min);
        this.setInputValue("th_temp_low", cfgs.temperature?.low_threshold);
        this.setInputValue("th_temp_high", cfgs.temperature?.high_threshold);
        this.setInputValue("th_hum_low", cfgs.humidity?.low_threshold);
        this.setInputValue("th_hum_high", cfgs.humidity?.high_threshold);
        this.setInputValue("th_press_low", cfgs.pressure?.low_threshold);
        this.setInputValue("th_press_high", cfgs.pressure?.high_threshold);
      });
  }

  setInputValue(id, val) {
    const el = document.getElementById(id);
    if (el && val !== undefined) el.value = val;
  }

  saveThresholdsForm() {
    const payload = {
      heart_rate: {
        low_threshold: parseFloat(document.getElementById("th_hr_low").value),
        high_threshold: parseFloat(document.getElementById("th_hr_high").value),
        hysteresis: 2.0,
        debounce_samples: 4
      },
      spo2: {
        normal_min: parseFloat(document.getElementById("th_spo2_norm").value),
        caution_min: parseFloat(document.getElementById("th_spo2_caut").value),
        hysteresis: 1.0,
        debounce_samples: 3
      },
      temperature: {
        low_threshold: parseFloat(document.getElementById("th_temp_low").value),
        high_threshold: parseFloat(document.getElementById("th_temp_high").value),
        hysteresis: 0.5,
        debounce_samples: 3
      },
      humidity: {
        low_threshold: parseFloat(document.getElementById("th_hum_low").value),
        high_threshold: parseFloat(document.getElementById("th_hum_high").value),
        hysteresis: 2.0,
        debounce_samples: 3
      },
      pressure: {
        low_threshold: parseFloat(document.getElementById("th_press_low").value),
        high_threshold: parseFloat(document.getElementById("th_press_high").value),
        hysteresis: 5.0,
        debounce_samples: 3
      }
    };

    fetch("/api/thresholds", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    }).then(() => {
      document.getElementById("thresholdModal").classList.remove("active");
    });
  }

  loadCalibrationForm() {
    fetch("/api/v1/calibration")
      .then(res => res.json())
      .then(data => {
        const cal = data.calibration;
        if (!cal) return;

        this.setInputValue("cal_max_red_offset", cal.max30102?.red_offset);
        this.setInputValue("cal_max_red_scale", cal.max30102?.red_scale);
        this.setInputValue("cal_max_ir_offset", cal.max30102?.ir_offset);
        this.setInputValue("cal_max_ir_scale", cal.max30102?.ir_scale);

        this.setInputValue("cal_mpu_ax_offset", cal.mpu6050?.ax_offset);
        this.setInputValue("cal_mpu_ax_scale", cal.mpu6050?.ax_scale);

        this.setInputValue("cal_env_temp_offset", cal.bme280_bmp280?.temp_offset);
        this.setInputValue("cal_env_temp_scale", cal.bme280_bmp280?.temp_scale);
        this.setInputValue("cal_env_press_offset", cal.bme280_bmp280?.press_offset);
        this.setInputValue("cal_env_press_scale", cal.bme280_bmp280?.press_scale);
      });
  }

  saveCalibrationForm() {
    const p1 = fetch("/api/v1/calibration/max30102", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        red_offset: parseFloat(document.getElementById("cal_max_red_offset").value) || 0.0,
        red_scale: parseFloat(document.getElementById("cal_max_red_scale").value) || 1.0,
        ir_offset: parseFloat(document.getElementById("cal_max_ir_offset").value) || 0.0,
        ir_scale: parseFloat(document.getElementById("cal_max_ir_scale").value) || 1.0
      })
    });

    const p2 = fetch("/api/v1/calibration/mpu6050", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ax_offset: parseFloat(document.getElementById("cal_mpu_ax_offset").value) || 0.0,
        ax_scale: parseFloat(document.getElementById("cal_mpu_ax_scale").value) || 1.0
      })
    });

    const p3 = fetch("/api/v1/calibration/bme280_bmp280", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        temp_offset: parseFloat(document.getElementById("cal_env_temp_offset").value) || 0.0,
        temp_scale: parseFloat(document.getElementById("cal_env_temp_scale").value) || 1.0,
        press_offset: parseFloat(document.getElementById("cal_env_press_offset").value) || 0.0,
        press_scale: parseFloat(document.getElementById("cal_env_press_scale").value) || 1.0
      })
    });

    Promise.all([p1, p2, p3]).then(() => {
      document.getElementById("calibrationModal").classList.remove("active");
    });
  }

  setSimulationScenario(scenarioName) {
    document.querySelectorAll(".sim-scenario-btn").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.scenario === scenarioName);
    });

    fetch("/api/v1/simulator/scenario", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario: scenarioName })
    });
  }

  playAlertTone(severity) {
    if (this.isMuted || !this.audioCtx) return;
    if (this.audioCtx.state === "suspended") this.audioCtx.resume();

    const now = this.audioCtx.currentTime;
    const osc = this.audioCtx.createOscillator();
    const gain = this.audioCtx.createGain();

    const freq = severity === "CRITICAL" ? 880 : 660;
    osc.frequency.setValueAtTime(freq, now);
    osc.type = severity === "CRITICAL" ? "sawtooth" : "sine";

    gain.gain.setValueAtTime(0.001, now);
    gain.gain.exponentialRampToValueAtTime(0.3, now + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.25);

    osc.connect(gain);
    gain.connect(this.audioCtx.destination);

    osc.start(now);
    osc.stop(now + 0.26);
  }
}

window.dashboardApp = new DashboardApp();
