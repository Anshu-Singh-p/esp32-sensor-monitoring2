/**
 * ESP32 Sensor Monitoring - Canvas Charting Engine
 * Renders multi-series live and historical charts for MAX30102, MPU6050, and BME280/BMP280.
 */

class MultiSensorCharts {
  constructor() {
    this.activeRange = "5m";
    this.historyData = [];
    this.envType = "BME280";

    this.physioCanvas = document.getElementById("physioChartCanvas");
    this.motionCanvas = document.getElementById("motionChartCanvas");
    this.envCanvas = document.getElementById("envChartCanvas");

    this.initCanvas(this.physioCanvas);
    this.initCanvas(this.motionCanvas);
    this.initCanvas(this.envCanvas);

    window.addEventListener("resize", () => this.renderAll());
  }

  initCanvas(canvas) {
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = (rect.width || 380) * dpr;
    canvas.height = (rect.height || 170) * dpr;
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
  }

  setRange(rangeStr) {
    this.activeRange = rangeStr;
  }

  setEnvType(typeStr) {
    this.envType = typeStr;
  }

  updateData(dataList, envType) {
    this.historyData = dataList || [];
    if (envType) this.envType = envType;
    this.renderAll();
  }

  renderAll() {
    this.renderPhysio();
    this.renderMotion();
    this.renderEnvironment();
  }

  renderPhysio() {
    if (!this.physioCanvas) return;
    const ctx = this.physioCanvas.getContext("2d");
    const rect = this.physioCanvas.getBoundingClientRect();
    const w = rect.width || 380;
    const h = rect.height || 170;

    this.drawBackground(ctx, w, h);
    if (!this.historyData || this.historyData.length < 2) {
      this.drawEmpty(ctx, w, h, "Awaiting MAX30102 Telemetry...");
      return;
    }

    const pad = { top: 20, right: 15, bottom: 25, left: 40 };
    const chartW = w - pad.left - pad.right;
    const chartH = h - pad.top - pad.bottom;

    // Filter valid HR & SpO2 points
    const hrPoints = this.historyData.map(d => d.heart_rate).filter(v => v !== null && v !== undefined);
    const spo2Points = this.historyData.map(d => d.spo2).filter(v => v !== null && v !== undefined);

    if (hrPoints.length > 1) {
      this.drawSeries(ctx, hrPoints, 40, 160, "#f43f5e", "rgba(244, 63, 94, 0.12)", pad, chartW, chartH);
    }
    if (spo2Points.length > 1) {
      this.drawSeries(ctx, spo2Points, 80, 100, "#06b6d4", "rgba(6, 182, 212, 0.12)", pad, chartW, chartH);
    }

    // Legend / Labels
    ctx.font = "10px monospace";
    ctx.fillStyle = "#f43f5e";
    const lastHR = hrPoints.length ? Math.round(hrPoints[hrPoints.length - 1]) : "--";
    ctx.fillText(`HR: ${lastHR} BPM`, pad.left, pad.top - 6);

    ctx.fillStyle = "#06b6d4";
    const lastSpO2 = spo2Points.length ? spo2Points[spo2Points.length - 1].toFixed(1) : "--";
    ctx.fillText(`SpO₂: ${lastSpO2}%`, pad.left + 110, pad.top - 6);

    ctx.fillStyle = "#64748b";
    ctx.fillText("140", 8, pad.top + 15);
    ctx.fillText("60", 8, pad.top + chartH);
  }

  renderMotion() {
    if (!this.motionCanvas) return;
    const ctx = this.motionCanvas.getContext("2d");
    const rect = this.motionCanvas.getBoundingClientRect();
    const w = rect.width || 380;
    const h = rect.height || 170;

    this.drawBackground(ctx, w, h);
    if (!this.historyData || this.historyData.length < 2) {
      this.drawEmpty(ctx, w, h, "Awaiting MPU6050 Telemetry...");
      return;
    }

    const pad = { top: 20, right: 15, bottom: 25, left: 40 };
    const chartW = w - pad.left - pad.right;
    const chartH = h - pad.top - pad.bottom;

    const accelMag = this.historyData.map(d => d.accel_magnitude).filter(v => v !== null && v !== undefined);
    const gyroMag = this.historyData.map(d => d.gyro_magnitude).filter(v => v !== null && v !== undefined);

    if (accelMag.length > 1) {
      this.drawSeries(ctx, accelMag, 0.0, 3.5, "#38bdf8", "rgba(56, 189, 248, 0.12)", pad, chartW, chartH);
    }
    if (gyroMag.length > 1) {
      this.drawSeries(ctx, gyroMag, 0.0, 300.0, "#a855f7", "rgba(168, 85, 247, 0.08)", pad, chartW, chartH);
    }

    ctx.font = "10px monospace";
    ctx.fillStyle = "#38bdf8";
    const lastA = accelMag.length ? accelMag[accelMag.length - 1].toFixed(2) : "--";
    ctx.fillText(`|A|: ${lastA}g`, pad.left, pad.top - 6);

    ctx.fillStyle = "#a855f7";
    const lastG = gyroMag.length ? Math.round(gyroMag[gyroMag.length - 1]) : "--";
    ctx.fillText(`|G|: ${lastG}°/s`, pad.left + 100, pad.top - 6);

    ctx.fillStyle = "#64748b";
    ctx.fillText("3.0g", 8, pad.top + 15);
    ctx.fillText("0.0g", 8, pad.top + chartH);
  }

  renderEnvironment() {
    if (!this.envCanvas) return;
    const ctx = this.envCanvas.getContext("2d");
    const rect = this.envCanvas.getBoundingClientRect();
    const w = rect.width || 380;
    const h = rect.height || 170;

    this.drawBackground(ctx, w, h);
    if (!this.historyData || this.historyData.length < 2) {
      this.drawEmpty(ctx, w, h, "Awaiting Environmental Telemetry...");
      return;
    }

    const pad = { top: 20, right: 15, bottom: 25, left: 40 };
    const chartW = w - pad.left - pad.right;
    const chartH = h - pad.top - pad.bottom;

    const tempSeries = this.historyData.map(d => d.temperature).filter(v => v !== null && v !== undefined);
    const pressSeries = this.historyData.map(d => d.pressure).filter(v => v !== null && v !== undefined);
    const humSeries = this.historyData.map(d => d.humidity).filter(v => v !== null && v !== undefined);

    if (tempSeries.length > 1) {
      this.drawSeries(ctx, tempSeries, 10.0, 45.0, "#f59e0b", "rgba(245, 158, 11, 0.12)", pad, chartW, chartH);
    }
    if (this.envType === "BME280" && humSeries.length > 1) {
      this.drawSeries(ctx, humSeries, 0.0, 100.0, "#10b981", "rgba(16, 185, 129, 0.10)", pad, chartW, chartH);
    }

    ctx.font = "10px monospace";
    ctx.fillStyle = "#f59e0b";
    const lastT = tempSeries.length ? tempSeries[tempSeries.length - 1].toFixed(1) : "--";
    ctx.fillText(`Temp: ${lastT}°C`, pad.left, pad.top - 6);

    if (this.envType === "BME280") {
      ctx.fillStyle = "#10b981";
      const lastH = humSeries.length ? humSeries[humSeries.length - 1].toFixed(1) : "--";
      ctx.fillText(`Hum: ${lastH}%`, pad.left + 110, pad.top - 6);
    } else {
      ctx.fillStyle = "#94a3b8";
      ctx.fillText("(BMP280: No Hum)", pad.left + 110, pad.top - 6);
    }

    ctx.fillStyle = "#64748b";
    ctx.fillText("40°C", 8, pad.top + 15);
    ctx.fillText("15°C", 8, pad.top + chartH);
  }

  drawBackground(ctx, w, h) {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = "rgba(10, 16, 30, 0.85)";
    ctx.fillRect(0, 0, w, h);

    // Subtle grid lines
    ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
    ctx.lineWidth = 1;
    for (let y = 30; y < h - 20; y += 35) {
      ctx.beginPath();
      ctx.moveTo(35, y);
      ctx.lineTo(w - 10, y);
      ctx.stroke();
    }
  }

  drawEmpty(ctx, w, h, msg) {
    ctx.fillStyle = "#64748b";
    ctx.font = "12px sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(msg, w / 2, h / 2);
    ctx.textAlign = "left";
  }

  drawSeries(ctx, data, minVal, maxVal, strokeColor, fillColor, pad, chartW, chartH) {
    const n = data.length;
    if (n < 2) return;
    const stepX = chartW / (n - 1);

    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const val = Math.max(minVal, Math.min(maxVal, data[i]));
      const normY = (val - minVal) / (maxVal - minVal);
      const x = pad.left + i * stepX;
      const y = pad.top + chartH - normY * chartH;

      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }

    ctx.lineWidth = 1.8;
    ctx.strokeStyle = strokeColor;
    ctx.stroke();

    ctx.lineTo(pad.left + (n - 1) * stepX, pad.top + chartH);
    ctx.lineTo(pad.left, pad.top + chartH);
    ctx.closePath();
    ctx.fillStyle = fillColor;
    ctx.fill();
  }
}

window.multiSensorCharts = new MultiSensorCharts();
