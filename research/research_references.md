# Research References & Literature Bibliography

This document provides formal, evidence-based citations and technical references for the signal processing algorithms, calibration formulas, and physiological/environmental thresholds implemented in the **ESP32 Sensor Processing Pipeline & Health Dashboard**.

---

## 1. MAX30102 — Pulse Oximetry & Photoplethysmography (PPG)

### 1.1 Sensor Hardware & Optical Measurement Principle
* **Source**: Maxim Integrated / Analog Devices. (2018). *MAX30102: High-Sensitivity Pulse Oximeter and Heart-Rate Sensor for Wearable Health*. Datasheet 19-8664; Rev 1.
* **Implementation Role**:
  - Defines 18-bit ADC register limits ($0 - 262,143$).
  - Specifies dual-wavelength optical absorption: Red ($660\,\text{nm}$) and Infrared ($880\,\text{nm}$).
  - Establishes DC baseline threshold ($\ge 40,000$) for valid skin contact detection.

### 1.2 Pulse Rate & SpO₂ Ratio-of-Ratios Algorithm
* **Reference**: Webster, J. G. (1997). *Design of Pulse Oximeters*. Medical Science Series, CRC Press. ISBN: 978-0750304672.
* **Reference**: Tamura, T., Maeda, Y., Sekine, M., & Yoshida, M. (2014). Wearable photoplethysmographic sensors—past and present. *Electronics*, 3(2), 282-302. DOI: `10.3390/electronics3020282`.
* **Implementation Role**:
  - Implements Ratio of Ratios:
    $$R = \frac{(AC_{red} / DC_{red})}{(AC_{ir} / DC_{ir})}$$
  - Implements empirical calibration formula for non-invasive blood oxygen saturation:
    $$\text{SpO}_2 = 110 - 25 \times R$$

### 1.3 PPG Signal Quality Index (SQI) & Motion Artifact Handling
* **Reference**: Elgendi, M. (2016). Optimal signal quality index for photoplethysmogram signals. *Bioengineering*, 3(4), 21. DOI: `10.3390/bioengineering3040021`.
* **Implementation Role**:
  - Guides optical signal-to-noise ratio (SNR) calculation and DC baseline tracking for the Signal Quality Index (SQI $0 - 100\%$).

---

## 2. MPU6050 — 6-DOF Inertial Sensing & Fall Detection

### 2.1 Sensor Operational Specifications
* **Source**: TDK InvenSense. (2013). *MPU-6000 and MPU-6050 Product Specification*. Document Number: PS-MPU-6000A-00, Rev 3.4.
* **Implementation Role**:
  - Accelerometer ranges ($\pm 2g, \pm 4g, \pm 8g, \pm 16g$) and Gyroscope ranges ($\pm 250, \pm 500, \pm 1000, \pm 2000^\circ/\text{s}$).

### 2.2 Multi-Stage Fall Event Detection Methodology
* **Reference**: Bourke, A. K., O'Brien, J. V., & Lyons, G. M. (2007). Evaluation of a threshold-based tri-axial accelerometer fall detection algorithm. *Gait & Posture*, 26(2), 194-199. DOI: `10.1016/j.gaitpost.2006.09.012`.
* **Reference**: Bagalà, F., Becker, C., Cappello, A., et al. (2012). Evaluation of accelerometer-based fall detection algorithms on real-world falls. *PLoS ONE*, 7(5), e37062. DOI: `10.1371/journal.pone.0037062`.
* **Implementation Role**:
  - Defines the 3-stage temporal fall model:
    1. *Stage 1 (Impact)*: Acceleration magnitude vector $|A| > 2.6g$.
    2. *Stage 2 (Rotational Perturbation)*: Angular velocity $|G| > 140^\circ/\text{s}$.
    3. *Stage 3 (Post-Event Inactivity)*: Acceleration returns to $1.0g \pm 0.25g$ with minimal gyro activity ($< 20^\circ/\text{s}$) for $\ge 1.5\,\text{s}$.

---

## 3. BME280 / BMP280 — Environmental Sensing & Calibration

### 3.1 Sensor Datasheets & Compensation Formulas
* **Source**: Bosch Sensortec. (2018). *BME280 Combined humidity and pressure sensor*. Document: BST-BME280-DS002-15.
* **Source**: Bosch Sensortec. (2018). *BMP280 Digital Pressure Sensor*. Document: BST-BMP280-DS001-19.
* **Implementation Role**:
  - Provides calibration offset models and physical limits: Temperature ($-40$ to $+85^\circ\text{C}$), Pressure ($300 - 1100\,\text{hPa}$), Humidity ($0 - 100\%$).

---

## 4. Physiological & Environmental Threshold Reference Baselines

### 4.1 Resting Heart Rate Reference Range (Adults)
* **Standard**: American Heart Association (AHA). (2020). *Target Heart Rates Chart & Resting Heart Rate*.
* **Reference Values**:
  - Normal Resting: $60 - 100\,\text{BPM}$
  - Resting Bradycardia Flag: $< 60\,\text{BPM}$
  - Resting Tachycardia Flag: $> 100\,\text{BPM}$

### 4.2 Pulse Oximetry Oxygen Saturation ($\text{SpO}_2$)
* **Standard**: World Health Organization (WHO). (2011). *Pulse Oximetry Training Manual*. ISBN: 978-92-4-150113-2.
* **Reference Values**:
  - Normal Oxygenation: $\ge 95\%$
  - Caution / Sub-optimal: $90 - 94\%$
  - Critical Hypoxemia Warning: $< 90\%$

### 4.3 Indoor Environmental Comfort Zones
* **Standard**: ANSI/ASHRAE Standard 55-2020. *Thermal Environmental Conditions for Human Occupancy*.
* **Reference Values**:
  - Temperature: $18 - 30^\circ\text{C}$
  - Relative Humidity: $30 - 60\%$

---

## ⚠️ Medical Disclaimer

> [!IMPORTANT]
> **PROTOTYPE MONITORING SYSTEM ONLY**: The thresholds and signal processing algorithms implemented in this system are intended strictly for educational, engineering, and prototype monitoring demonstrations. They do not constitute a medical diagnosis or replace professional medical assessment.
