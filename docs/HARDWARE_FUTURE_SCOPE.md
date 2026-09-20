# Hardware plan (future scope, not built in the hackathon)

Costs below are rough estimates. Check current prices before quoting them.

## One node

| Part | Purpose |
|---|---|
| ESP32 microcontroller | Reads sensors, low power, Wi-Fi for testing |
| LoRa module (SX1276) | Long range radio to a gateway, works without mobile network |
| Tipping-bucket rain gauge | `rain_1h_mm`, `rain_24h_mm` |
| Capacitive soil-moisture sensor | `soil_moisture_pct` |
| MPU6050 (accelerometer + gyroscope) | `tilt_deg` and `vibration_g` |
| BME280 | temperature, humidity |
| Smoke / particulate sensor | `smoke_ppm` |
| Waterproof ultrasonic sensor (JSN-SR04T) | `water_level_cm` (stream level) |
| Solar panel, Li-ion cell, charge controller | Runs without mains power |
| Weatherproof box | Protection |

Rough cost: the order of a few thousand rupees per node.

## Network

Node -> LoRa -> village gateway -> internet (or satellite) -> `POST /api/readings`. No change is needed in the backend.

## Thermal / 360 camera (from the original idea)

Add a Raspberry Pi with a camera at high-value sites. The same `POST /api/camera/event` endpoint is used, and a YOLO smoke and fire model replaces the browser heuristic.

## Calibration plan

1. Deploy 3 nodes in one district with a history of landslides.
2. Log data for one monsoon.
3. Retrain the models on real events and tune the rainfall threshold for the local geology.
4. Measure precision, recall and false-alarm rate, and publish them.

## Reference firmware

`firmware/esp32_node/esp32_node.ino` is a starting point that posts a reading over Wi-Fi. It is **untested on hardware**.
