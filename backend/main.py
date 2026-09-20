"""MountainSentinel API.  Run:  uvicorn backend.main:app --reload   then open http://localhost:8000"""
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import config
from . import database as db
from .schemas import CameraEvent, HikerCheckin, ScenarioRequest, SensorReading, SubscribeRequest
from .service import Service
from .simulator import CAMERA_SCENARIOS, SCENARIOS, Simulator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

service = Service()


@asynccontextmanager
async def lifespan(app: FastAPI):
    service.start()
    app.state.sim = None
    tasks = [asyncio.create_task(service.hiker_watchdog())]
    if config.USE_LIVE_DATA:
        tasks.append(asyncio.create_task(service.external_refresher()))
    if config.SIMULATE:
        app.state.sim = Simulator(service)
        tasks.append(asyncio.create_task(app.state.sim.run()))
    yield
    for t in tasks:
        t.cancel()


app = FastAPI(
    title="MountainSentinel",
    description="AI early-warning system for mountain disasters: landslides, flash floods, forest fires, "
    "ground shaking and lost hikers.",
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _check_key(x_api_key: Optional[str]) -> None:
    if config.INGEST_API_KEY and x_api_key != config.INGEST_API_KEY:
        raise HTTPException(status_code=401, detail="Missing or wrong X-API-Key header")


# ---------------------------------------------------------------- health / state
@app.get("/api/health", tags=["system"])
async def health():
    return {
        "status": "ok",
        "nodes": len(service.latest),
        "readings_processed": service.readings_total,
        "alerts_raised": service.alerts_total,
        "ml_models": service.ml.available,
        "simulation": config.SIMULATE,
        "telegram": service.alerter.telegram_enabled,
    }


@app.get("/api/state", tags=["dashboard"])
async def state():
    """Everything the dashboard needs in one call."""
    return service.snapshot()


@app.get("/api/model", tags=["ml"])
async def model_info():
    """Model quality on held-out synthetic data (see ml/train.py for what this means)."""
    return {"available": service.ml.available, "metrics": service.ml.metrics}


# ---------------------------------------------------------------- sensors
@app.post("/api/readings", tags=["sensors"])
async def post_reading(reading: SensorReading, x_api_key: Optional[str] = Header(default=None)):
    """Real hardware (ESP32 + LoRa gateway) posts here. Returns the risk assessment."""
    _check_key(x_api_key)
    return await service.ingest(reading.model_dump())


@app.get("/api/nodes/{node_id}/history", tags=["sensors"])
async def node_history(node_id: str, limit: int = Query(100, ge=1, le=1000)):
    return db.node_history(node_id, limit)


@app.get("/api/alerts", tags=["alerts"])
async def alerts(limit: int = Query(30, ge=1, le=200)):
    return db.recent_alerts(limit)


# ---------------------------------------------------------------- hikers
@app.post("/api/hikers/{hiker_id}/checkin", tags=["hikers"])
async def hiker_checkin(hiker_id: str, body: HikerCheckin, x_api_key: Optional[str] = Header(default=None)):
    """A hiker's phone (or a trail beacon) reports its position. Missing check-ins raise an alert."""
    _check_key(x_api_key)
    return await service.hiker_checkin(hiker_id, body.lat, body.lon, body.name)


@app.post("/api/hikers/{hiker_id}/sos", tags=["hikers"])
async def hiker_sos(hiker_id: str, x_api_key: Optional[str] = Header(default=None)):
    _check_key(x_api_key)
    try:
        return await service.hiker_sos(hiker_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Unknown hiker. Send a check-in first.")


# ---------------------------------------------------------------- cameras
@app.post("/api/camera/event", tags=["camera"])
async def camera_event(ev: CameraEvent, x_api_key: Optional[str] = Header(default=None)):
    """The laptop-camera page (dashboard/camera.html) posts here. Any device with a detector can too."""
    _check_key(x_api_key)
    return await service.camera_event(ev.model_dump())


@app.get("/api/sightings", tags=["camera"])
async def sightings(limit: int = Query(40, ge=1, le=200)):
    """Photos of people and animals with the camera position where they were seen."""
    return db.recent_sightings(limit)


@app.get("/api/wildlife", tags=["camera"])
async def wildlife():
    """Species seen by cameras: count now, maximum count, movement and direction."""
    return service.wildlife_view()


# ---------------------------------------------------------------- phone alerts
@app.post("/api/subscribers", tags=["phone alerts"], status_code=201)
async def subscribe(req: SubscribeRequest):
    """Enter a phone number to receive SMS or WhatsApp alerts."""
    if not req.consent:
        raise HTTPException(status_code=400, detail="Please confirm that this is your number and you want alerts.")
    try:
        return await service.subscribe(req.name, req.phone, req.channel, req.min_level)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except OverflowError as exc:
        raise HTTPException(status_code=429, detail=str(exc))


@app.get("/api/subscribers", tags=["phone alerts"])
async def subscribers():
    """Phone numbers are masked in every response."""
    return service.subscribers_view()


@app.delete("/api/subscribers/{sub_id}", tags=["phone alerts"])
async def unsubscribe(sub_id: int):
    if not await service.unsubscribe(sub_id):
        raise HTTPException(status_code=404, detail="Subscriber not found")
    return {"deleted": True}


@app.post("/api/subscribers/{sub_id}/test", tags=["phone alerts"])
async def subscriber_test(sub_id: int):
    """Send a test message to check the number works."""
    try:
        return await service.send_test(sub_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Subscriber not found")


@app.get("/api/outbox", tags=["phone alerts"])
async def outbox():
    return list(service.notifier.outbox)


# ---------------------------------------------------------------- live data
@app.get("/api/external/earthquakes", tags=["live data"])
async def external_earthquakes():
    return service.external.earthquakes


@app.get("/api/external/fires", tags=["live data"])
async def external_fires():
    return service.external.fire_hotspots


# ---------------------------------------------------------------- demo
@app.post("/api/demo/scenario", tags=["demo"])
async def demo_scenario(req: ScenarioRequest):
    """Trigger a disaster scenario in the simulator: landslide, flood, wildfire, earthquake, hiker_lost, rescue_drone, injured, animals, reset."""
    sim = getattr(app.state, "sim", None)
    if sim is None:
        raise HTTPException(status_code=400, detail="Simulation is off. Set SIMULATE=true.")
    try:
        return sim.trigger(req.scenario, req.node_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.get("/api/demo/scenarios", tags=["demo"])
async def demo_scenarios():
    return {k: v["label"] for k, v in SCENARIOS.items()} | CAMERA_SCENARIOS | {"hiker_lost": "Hiker misses check-in", "reset": "Reset"}


# ---------------------------------------------------------------- live updates
@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await service.hub.connect(ws)
    try:
        await ws.send_json({"type": "snapshot", "data": service.snapshot()})
        while True:
            await ws.receive_text()  # we only push; this keeps the connection open
    except WebSocketDisconnect:
        pass
    finally:
        service.hub.disconnect(ws)


# The dashboard is served at "/" (mounted last so the API routes above win).
app.mount("/", StaticFiles(directory=config.DASHBOARD_DIR, html=True), name="dashboard")
