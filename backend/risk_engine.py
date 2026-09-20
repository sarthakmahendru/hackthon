"""Hybrid risk engine: physics-based rules + machine learning + live context.

For every reading and every hazard we produce:
    score    0-100   (what the dashboard shows)
    level    safe / watch / warning / critical
    reasons  plain-language explanations (why the score is what it is)

Why hybrid?
  * Rules are explainable and safe: they use published science (Caine 1980 rainfall
    threshold for landslides) and hard "active movement" overrides.
  * ML captures non-linear interactions (rain on already-saturated soil) and gives a
    probability instead of a cliff-edge threshold.
  * Context (rain forecast, nearby satellite fire hotspots, shaking on wet slopes) lets
    the system warn earlier and catch compound disasters.

Final score = 0.55 * rule score + 0.45 * ML probability (x100) + context boosts,
never lower than a rule "override floor" (e.g. active slope movement).
"""
from typing import Optional

# Caine (1980) global rainfall intensity-duration threshold for shallow landslides:
#   I = 14.82 * D^-0.39      (I in mm/h, D in hours)
# For D = 1 h  ->  14.8 mm.   For D = 24 h  ->  about 103 mm in total.
# It is a GLOBAL threshold. Real deployments calibrate it per region.
CAINE_1H_MM = 14.82
CAINE_24H_MM = 14.82 * 24 ** -0.39 * 24

RULE_WEIGHT = 0.55
ML_WEIGHT = 0.45

HAZARDS = ["landslide", "flood", "wildfire", "seismic"]
HAZARD_LABELS = {
    "landslide": "Landslide",
    "flood": "Flash flood",
    "wildfire": "Forest fire",
    "seismic": "Ground shaking",
}
LEVEL_RANK = {"safe": 0, "watch": 1, "warning": 2, "critical": 3}

ACTIONS = {
    "landslide": {
        "warning": "Alert local authorities. Restrict road and trail use below the slope. Prepare people to move.",
        "critical": "Evacuate homes and close roads below the slope now.",
    },
    "flood": {
        "warning": "Move people away from the riverbank. Warn villages downstream.",
        "critical": "Evacuate riverside and low-lying areas now. Alert every settlement downstream.",
    },
    "wildfire": {
        "warning": "Alert the forest department and nearby villages. Prepare fire response.",
        "critical": "Send the fire response team. Move people away from the fire front and close trails.",
    },
    "seismic": {
        "warning": "Check for damage. Expect aftershocks and slope failures on wet ground.",
        "critical": "Move to open ground. Inspect roads and slopes before using them.",
    },
}


def ramp(x: float, lo: float, hi: float) -> float:
    """0 at or below lo, 1 at or above hi, linear in between."""
    if hi == lo:
        return 0.0
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))


def level_for(score: float) -> str:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "warning"
    if score >= 25:
        return "watch"
    return "safe"


def derive_features(reading: dict, history: list, window: int = 5) -> dict:
    """Add trend features: change over the last `window` readings."""
    f = dict(reading)
    if history:
        ref = history[-window] if len(history) >= window else history[0]
        f["tilt_trend"] = reading["tilt_deg"] - ref["tilt_deg"]
        f["water_trend"] = reading["water_level_cm"] - ref["water_level_cm"]
    else:
        f["tilt_trend"] = 0.0
        f["water_trend"] = 0.0
    return f


# ---------------------------------------------------------------- rule scores
def landslide_rule(f: dict):
    rain_ratio = max(f["rain_1h_mm"] / CAINE_1H_MM, f["rain_24h_mm"] / CAINE_24H_MM)
    score = 100 * (
        0.40 * ramp(rain_ratio, 0.3, 1.5)
        + 0.25 * ramp(f["soil_moisture_pct"], 55, 90)
        + 0.25 * ramp(f["tilt_deg"], 0.5, 4.0)
        + 0.10 * ramp(f["tilt_trend"], 0.05, 0.5)
    )
    reasons = []
    if rain_ratio >= 1.0:
        reasons.append(
            f"Rainfall is above the global landslide threshold (Caine 1980): "
            f"{f['rain_1h_mm']:.0f} mm in 1 h, {f['rain_24h_mm']:.0f} mm in 24 h "
            f"(limits {CAINE_1H_MM:.0f} mm and {CAINE_24H_MM:.0f} mm)."
        )
    elif rain_ratio >= 0.5:
        reasons.append(f"Heavy rain is building up ({rain_ratio * 100:.0f}% of the landslide rainfall threshold).")
    if f["soil_moisture_pct"] >= 75:
        reasons.append(f"Soil is nearly saturated ({f['soil_moisture_pct']:.0f}%).")
    elif f["soil_moisture_pct"] >= 60:
        reasons.append(f"Soil moisture is high ({f['soil_moisture_pct']:.0f}%).")
    if f["tilt_deg"] >= 1.0:
        reasons.append(f"Ground has tilted {f['tilt_deg']:.1f}° from its baseline.")
    if f["tilt_trend"] >= 0.1:
        reasons.append(f"Tilt is still increasing (+{f['tilt_trend']:.2f}° over the last 5 readings): the slope may be moving.")
    floor = 0.0
    if f["tilt_deg"] >= 3.5 and f["tilt_trend"] >= 0.3:
        floor = 85.0
        reasons.insert(0, "Active slope movement detected: ground is tilting fast.")
    return score, reasons, floor


def flood_rule(f: dict):
    score = 100 * (
        0.40 * ramp(f["water_level_cm"], 80, 250)
        + 0.30 * ramp(f["water_trend"], 2, 25)
        + 0.30 * ramp(f["rain_1h_mm"], 10, 50)
    )
    reasons = []
    if f["water_level_cm"] >= 120:
        reasons.append(f"Stream level is high ({f['water_level_cm']:.0f} cm).")
    if f["water_trend"] >= 5:
        reasons.append(f"Stream is rising fast (+{f['water_trend']:.0f} cm over the last 5 readings).")
    if f["rain_1h_mm"] >= 15:
        reasons.append(f"Intense rain right now ({f['rain_1h_mm']:.0f} mm in the last hour).")
    floor = 0.0
    if f["water_level_cm"] >= 220 and f["water_trend"] >= 15:
        floor = 85.0
        reasons.insert(0, "Stream is rising quickly towards flood stage.")
    return score, reasons, floor


def wildfire_rule(f: dict):
    dryness = 1.0 - ramp(f["humidity_pct"], 15, 50)
    score = 100 * (
        0.50 * ramp(f["smoke_ppm"], 50, 300) + 0.25 * ramp(f["temperature_c"], 30, 48) + 0.25 * dryness
    )
    reasons = []
    if f["smoke_ppm"] >= 100:
        reasons.append(f"Smoke detected at {f['smoke_ppm']:.0f} ppm.")
    if f["temperature_c"] >= 38:
        reasons.append(f"Air temperature is very high ({f['temperature_c']:.0f} °C).")
    if f["humidity_pct"] <= 30:
        reasons.append(f"Air is very dry (humidity {f['humidity_pct']:.0f}%), so fire spreads fast.")
    floor = 0.0
    if f["smoke_ppm"] >= 250 and f["humidity_pct"] <= 35:
        floor = 85.0
        reasons.insert(0, "Dense smoke in dry air: a forest fire is very likely burning nearby.")
    return score, reasons, floor


def seismic_rule(f: dict):
    """Detects shaking as it happens. It does NOT predict earthquakes (nobody can)."""
    score = 100 * ramp(f["vibration_g"], 0.004, 0.12)
    reasons = []
    if f["vibration_g"] >= 0.005:
        reasons.append(
            f"Ground shaking detected: peak acceleration {f['vibration_g']:.3f} g. "
            "This detects shaking in real time; earthquakes cannot be predicted."
        )
    return score, reasons, 0.0


# ------------------------------------------------------------------- assess
def assess(reading: dict, history: list, ml=None, context: Optional[dict] = None) -> dict:
    """Score one reading. `history` = earlier readings of the same node, oldest first."""
    f = derive_features(reading, history)
    ctx = context or {}

    rules = {
        "landslide": landslide_rule(f),
        "flood": flood_rule(f),
        "wildfire": wildfire_rule(f),
        "seismic": seismic_rule(f),
    }
    probs = ml.predict(f) if ml is not None and getattr(ml, "available", False) else {}

    boosts = {h: 0.0 for h in HAZARDS}
    extra_reasons = {h: [] for h in HAZARDS}
    context_used = []

    forecast = ctx.get("forecast_24h_mm")
    if forecast is not None and forecast >= 30:
        b = 12 * ramp(forecast, 30, 120)
        boosts["landslide"] += b
        boosts["flood"] += b
        msg = f"Forecast: about {forecast:.0f} mm more rain expected in the next 24 h (Open-Meteo)."
        extra_reasons["landslide"].append(msg)
        extra_reasons["flood"].append(msg)
        context_used.append(msg)

    fire_km = ctx.get("nearest_fire_km")
    if fire_km is not None and fire_km <= 15:
        boosts["wildfire"] += 15
        msg = f"NASA satellite hotspot detected {fire_km:.0f} km away."
        extra_reasons["wildfire"].append(msg)
        context_used.append(msg)

    cam = ctx.get("camera_fire")
    if cam:
        boosts["wildfire"] += 25
        msg = f"Camera '{cam['name']}' ({cam['km']:.0f} km away) sees flames."
        extra_reasons["wildfire"].append(msg)
        context_used.append(msg)

    # Compound hazard: shaking on wet slopes can trigger landslides.
    if f["vibration_g"] >= 0.02 and f["soil_moisture_pct"] >= 65:
        boosts["landslide"] += 20 * ramp(f["vibration_g"], 0.02, 0.10)
        extra_reasons["landslide"].append("Shaking on saturated soil raises landslide risk (compound hazard).")

    hazards = {}
    for h in HAZARDS:
        rule_score, reasons, floor = rules[h]
        p = probs.get(h)
        if p is None:
            blended = rule_score
        else:
            blended = RULE_WEIGHT * rule_score + ML_WEIGHT * 100 * p
        final = max(min(100.0, blended + boosts[h]), floor)
        final = int(round(final))
        hazards[h] = {
            "label": HAZARD_LABELS[h],
            "score": final,
            "level": level_for(final),
            "rule_score": int(round(rule_score)),
            "ml_probability": None if p is None else round(p, 3),
            "reasons": reasons + extra_reasons[h],
        }

    top = max(HAZARDS, key=lambda h: hazards[h]["score"])
    top_level = hazards[top]["level"]
    action = ACTIONS.get(top, {}).get(top_level)
    if action is None:
        action = "Keep monitoring. No action needed yet." if top_level == "watch" else "All readings are normal."

    return {
        "risk_score": hazards[top]["score"],
        "risk_level": top_level,
        "top_hazard": top,
        "top_hazard_label": HAZARD_LABELS[top],
        "recommended_action": action,
        "hazards": hazards,
        "features": {k: round(float(v), 3) for k, v in f.items() if k in ("tilt_trend", "water_trend")},
        "context_used": context_used,
    }
