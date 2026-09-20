"""Feature definitions shared by training and live prediction.

Every sensor node reports raw values. The risk engine derives two trend features
(tilt_trend, water_trend) from the last few readings. The ML models use all of them.
"""

FEATURES = [
    "rain_1h_mm",
    "rain_24h_mm",
    "soil_moisture_pct",
    "tilt_deg",
    "tilt_trend",
    "vibration_g",
    "temperature_c",
    "humidity_pct",
    "smoke_ppm",
    "water_level_cm",
    "water_trend",
]

# Hazards that have an ML model. Ground shaking is detected directly from
# the accelerometer, so it uses physics thresholds only.
ML_HAZARDS = ["landslide", "flood", "wildfire"]


def to_vector(features: dict) -> list:
    return [float(features.get(name, 0.0)) for name in FEATURES]
