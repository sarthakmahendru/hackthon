import pytest

from backend.risk_engine import CAINE_1H_MM, CAINE_24H_MM, assess, level_for, ramp
from ml.predict import HazardModels

BASE = dict(
    node_id="n1", node_name="Test node", lat=30.5, lon=79.5,
    rain_1h_mm=0.5, rain_24h_mm=8, soil_moisture_pct=45, tilt_deg=0.2, vibration_g=0.001,
    temperature_c=20, humidity_pct=60, smoke_ppm=10, water_level_cm=58, battery_pct=90,
)
HISTORY = [dict(BASE) for _ in range(6)]


@pytest.fixture(scope="module")
def ml():
    return HazardModels().load()


def test_ramp_and_levels():
    assert ramp(5, 0, 10) == 0.5
    assert ramp(-1, 0, 10) == 0 and ramp(99, 0, 10) == 1
    assert [level_for(x) for x in (0, 24, 25, 49, 50, 74, 75, 100)] == [
        "safe", "safe", "watch", "watch", "warning", "warning", "critical", "critical"]


def test_caine_threshold_values():
    assert CAINE_1H_MM == pytest.approx(14.82)
    assert CAINE_24H_MM == pytest.approx(103, abs=1)


def test_calm_is_safe(ml):
    a = assess(dict(BASE), HISTORY, ml)
    assert a["risk_level"] == "safe" and a["risk_score"] < 10


def test_landslide_conditions_are_critical(ml):
    r = dict(BASE, rain_1h_mm=32, rain_24h_mm=150, soil_moisture_pct=93, tilt_deg=5.0)
    a = assess(r, HISTORY, ml)
    assert a["top_hazard"] == "landslide" and a["risk_level"] == "critical"
    assert any("Caine" in reason for reason in a["hazards"]["landslide"]["reasons"])


def test_active_slope_movement_floor_works_without_ml():
    hist = [dict(BASE, tilt_deg=t) for t in (0.2, 0.5, 1.0, 2.0, 2.8, 3.2)]
    a = assess(dict(BASE, tilt_deg=3.9, soil_moisture_pct=40, rain_1h_mm=0), hist, ml=None)
    assert a["hazards"]["landslide"]["score"] >= 85


def test_heavy_rain_alone_is_only_warning(ml):
    a = assess(dict(BASE, rain_1h_mm=30, rain_24h_mm=120), HISTORY, ml)
    assert a["risk_level"] in ("watch", "warning")


def test_flood(ml):
    r = dict(BASE, rain_1h_mm=48, rain_24h_mm=130, soil_moisture_pct=85, water_level_cm=270)
    a = assess(r, HISTORY, ml)
    assert a["top_hazard"] == "flood" and a["risk_level"] == "critical"


def test_wildfire_and_hot_dry_day(ml):
    fire = assess(dict(BASE, temperature_c=47, humidity_pct=13, smoke_ppm=340), HISTORY, ml)
    assert fire["top_hazard"] == "wildfire" and fire["risk_level"] == "critical"
    hot = assess(dict(BASE, temperature_c=38, humidity_pct=22), HISTORY, ml)
    assert hot["risk_level"] in ("safe", "watch")  # fire weather without smoke is not an emergency


def test_earthquake_on_wet_slope_is_compound(ml):
    wet = dict(BASE, soil_moisture_pct=82, rain_24h_mm=90, tilt_deg=1.5)
    without = assess(dict(wet), HISTORY, ml)["hazards"]["landslide"]["score"]
    a = assess(dict(wet, vibration_g=0.15), HISTORY, ml)
    assert a["hazards"]["seismic"]["level"] == "critical"
    assert a["hazards"]["landslide"]["score"] > without
    assert any("compound" in r for r in a["hazards"]["landslide"]["reasons"])


def test_context_boosts(ml):
    plain = assess(dict(BASE, rain_24h_mm=60), HISTORY, ml)["hazards"]["landslide"]["score"]
    boosted = assess(dict(BASE, rain_24h_mm=60), HISTORY, ml, {"forecast_24h_mm": 120})["hazards"]["landslide"]["score"]
    assert boosted > plain
    fire = assess(dict(BASE), HISTORY, ml, {"camera_fire": {"name": "Cam", "km": 2.0, "score": 0.9}})
    assert fire["hazards"]["wildfire"]["score"] >= 25
    assert any("Camera" in r for r in fire["hazards"]["wildfire"]["reasons"])
