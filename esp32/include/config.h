/**
 * ESP32 Sensor Monitoring Hardware Configuration
 */

#ifndef CONFIG_H
#define CONFIG_H

// Wi-Fi Credentials
#define WIFI_SSID         "YOUR_WIFI_SSID"
#define WIFI_PASSWORD     "YOUR_WIFI_PASSWORD"

// Backend REST API Ingestion Endpoint
#define SERVER_INGEST_URL "http://192.168.1.100:8080/api/v1/sensor-data"
#define API_KEY           "ESP32_SECURE_KEY_2026"
#define DEVICE_ID         "ESP32_01"

// I2C Pinout (Standard ESP32 Default)
#define I2C_SDA_PIN       21
#define I2C_SCL_PIN       22
#define I2C_CLOCK_SPEED   400000

// Sampling & Telemetry Intervals
#define SENSOR_SAMPLE_INTERVAL_MS 1000
#define MAX_RING_BUFFER_SIZE      30

// MAX30102 Optical Contact Threshold
#define MAX30102_IR_CONTACT_THRESHOLD 40000

#endif // CONFIG_H
