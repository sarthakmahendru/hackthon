"""Request schemas. Ranges are validated so a faulty sensor cannot poison the risk engine."""
from typing import List, Optional

from pydantic import BaseModel, Field


class SensorReading(BaseModel):
    node_id: str = Field(min_length=1, max_length=64)
    node_name: Optional[str] = Field(default=None, max_length=100)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    ts: Optional[float] = Field(default=None, description="Unix seconds. Server time is used if omitted.")

    rain_1h_mm: float = Field(default=0, ge=0, le=500, description="Rain in the last hour (tipping-bucket gauge)")
    rain_24h_mm: float = Field(default=0, ge=0, le=2000, description="Rain in the last 24 hours")
    soil_moisture_pct: float = Field(default=0, ge=0, le=100, description="Volumetric soil moisture")
    tilt_deg: float = Field(default=0, ge=0, le=90, description="Ground tilt from installation baseline (IMU)")
    vibration_g: float = Field(default=0, ge=0, le=5, description="Peak ground acceleration in g (IMU)")
    temperature_c: float = Field(default=20, ge=-60, le=80)
    humidity_pct: float = Field(default=50, ge=0, le=100)
    smoke_ppm: float = Field(default=0, ge=0, le=5000, description="Smoke / particulate proxy")
    water_level_cm: float = Field(default=0, ge=0, le=2000, description="Stream level (ultrasonic sensor)")
    battery_pct: float = Field(default=100, ge=0, le=100)


class HikerCheckin(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    name: Optional[str] = Field(default=None, max_length=100)


class ScenarioRequest(BaseModel):
    scenario: str
    node_id: Optional[str] = None


class AnimalObs(BaseModel):
    """One species seen by a camera in the last moment."""

    species: str = Field(min_length=1, max_length=30)
    count: int = Field(ge=0, le=500, description="How many of this species are in view now")
    speed: float = Field(default=0, ge=0, le=5, description="Average movement in frame-widths per second")
    direction: str = Field(default="none", max_length=12)
    new_individuals: int = Field(default=0, ge=0, le=100, description="New animals tracked since the last event")


class CameraEvent(BaseModel):
    """Sent by a camera node (the laptop camera page, or any device running a detector)."""

    camera_id: str = Field(min_length=1, max_length=64)
    name: Optional[str] = Field(default=None, max_length=100)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    fire_score: float = Field(default=0, ge=0, le=1, description="0 = no flames, 1 = certain")
    person_count: int = Field(default=0, ge=0, le=200)
    motion: float = Field(default=0, ge=0, le=1)
    ai_active: bool = False
    snapshot: Optional[str] = Field(default=None, max_length=120000, description="Small JPEG data URL")
    person_down: bool = Field(default=False, description="A person seems to be lying still (possible injury)")
    roaming: bool = Field(default=False, description="Camera is moving (drone, rover, phone on patrol)")
    animals: List[AnimalObs] = Field(default_factory=list, max_length=20)


class SubscribeRequest(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    phone: str = Field(min_length=1, max_length=25)
    channel: str = Field(default="sms", pattern="^(sms|whatsapp)$")
    min_level: str = Field(default="warning", pattern="^(warning|critical)$")
    consent: bool = False
