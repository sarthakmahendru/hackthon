import time

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.notifier import mask_phone, normalize_phone


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


CALM = dict(node_id="t-1", node_name="Test ridge", lat=30.5, lon=79.5, rain_1h_mm=0.4, rain_24h_mm=6,
            soil_moisture_pct=42, tilt_deg=0.2, temperature_c=18, humidity_pct=60, smoke_ppm=8, water_level_cm=55)
STORM = dict(CALM, rain_1h_mm=32, rain_24h_mm=150, soil_moisture_pct=93, tilt_deg=5.0)


def test_health(client):
    r = client.get("/api/health").json()
    assert r["status"] == "ok" and r["ml_models"] is True


def test_dashboard_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "MountainSentinel" in r.text
    assert client.get("/camera.html").status_code == 200


def test_post_reading_returns_assessment(client):
    r = client.post("/api/readings", json=CALM)
    assert r.status_code == 200
    assert r.json()["assessment"]["risk_level"] == "safe"


def test_invalid_reading_rejected(client):
    assert client.post("/api/readings", json=dict(CALM, rain_1h_mm=-5)).status_code == 422
    assert client.post("/api/readings", json=dict(CALM, lat=200)).status_code == 422


def test_storm_raises_alert_and_history_is_saved(client):
    for _ in range(3):
        client.post("/api/readings", json=STORM)
    alerts = client.get("/api/alerts").json()
    assert any(a["level"] in ("warning", "critical") and a["node_id"] == "t-1" for a in alerts)
    hist = client.get("/api/nodes/t-1/history?limit=10").json()
    assert len(hist) >= 3 and "risk_score" in hist[-1]


def test_state_has_everything_dashboard_needs(client):
    s = client.get("/api/state").json()
    for key in ("nodes", "levels", "alerts", "hikers", "cameras", "subscribers", "outbox", "phone_channels", "model"):
        assert key in s
    assert any(n["node_id"] == "t-1" and n["series"] for n in s["nodes"])


def test_websocket_sends_snapshot_then_live_updates(client):
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "snapshot"
        client.post("/api/readings", json=CALM)
        seen = set()
        for _ in range(10):  # other tests may leave background events (alerts, message log) in the queue
            seen.add(ws.receive_json()["type"])
            if "node" in seen:
                break
        assert "node" in seen


def test_hiker_sos_and_checkin(client):
    assert client.post("/api/hikers/nobody/sos").status_code == 404
    client.post("/api/hikers/h-9/checkin", json={"lat": 30.5, "lon": 79.5, "name": "Test hiker"})
    r = client.post("/api/hikers/h-9/sos")
    assert r.status_code == 200 and r.json()["status"] == "sos"
    alerts = client.get("/api/alerts").json()
    assert any(a["kind"] == "hiker" and "Test hiker" in a["title"] for a in alerts)


def test_demo_scenario_disabled_when_simulation_off(client):
    assert client.post("/api/demo/scenario", json={"scenario": "landslide"}).status_code == 400


# ------------------------------------------------------------------ camera
def test_camera_fire_and_person_alerts(client):
    ev = dict(camera_id="cam-1", name="Laptop camera", lat=30.5, lon=79.5, fire_score=0.9, person_count=0, motion=0.4,
              snapshot="data:image/jpeg;base64,AAAA")
    assert client.post("/api/camera/event", json=ev).status_code == 200
    alerts = client.get("/api/alerts").json()
    fire = [a for a in alerts if a["kind"] == "camera" and "flames" in a["title"] and a["level"] == "critical"]
    assert fire and fire[0]["image"].startswith("data:image")
    # camera fire is fused into the nearest node's wildfire risk on its next reading
    r = client.post("/api/readings", json=CALM).json()
    assert any("Camera" in x for x in r["assessment"]["hazards"]["wildfire"]["reasons"])
    # person detected -> alert
    client.post("/api/camera/event", json=dict(ev, camera_id="cam-2", fire_score=0, person_count=2))
    assert any(a["kind"] == "camera" and "2 people" in a["title"] for a in client.get("/api/alerts").json())
    # flames gone -> resolved
    client.post("/api/camera/event", json=dict(ev, fire_score=0))
    assert any("no longer sees flames" in a["title"] for a in client.get("/api/alerts").json())
    assert client.get("/api/state").json()["cameras"]


def test_camera_event_validation(client):
    assert client.post("/api/camera/event", json=dict(camera_id="x", lat=1, lon=1, fire_score=3)).status_code == 422


# ------------------------------------------------------------------ phone numbers
def test_phone_normalisation():
    assert normalize_phone("98765 43210") == "+919876543210"
    assert normalize_phone("09876543210") == "+919876543210"
    assert normalize_phone("919876543210") == "+919876543210"
    assert normalize_phone("+91 98765-43210") == "+919876543210"
    assert normalize_phone("+1 (415) 555-2671") == "+14155552671"
    for bad in ("12345", "abcdefghij", "+0123456789", ""):
        with pytest.raises(ValueError):
            normalize_phone(bad)
    assert mask_phone("+919876543210") == "+91•••••••210"


def test_subscribe_flow_demo_mode(client):
    body = {"name": "Asha", "phone": "98765 43210", "channel": "sms", "min_level": "warning", "consent": True}
    assert client.post("/api/subscribers", json=dict(body, consent=False)).status_code == 400
    assert client.post("/api/subscribers", json=dict(body, phone="123")).status_code == 400
    r = client.post("/api/subscribers", json=body)
    assert r.status_code == 201
    sub = r.json()
    assert sub["phone"] == "+91•••••••210" and "9876543210" not in str(client.get("/api/subscribers").json())
    # the same number again does not create a duplicate
    assert client.post("/api/subscribers", json=body).json()["id"] == sub["id"]

    t = client.post(f"/api/subscribers/{sub['id']}/test").json()
    assert t["status"] == "demo" and t["to"] == "+91•••••••210"

    # a Critical alert reaches the subscriber (demo mode: written to the message log)
    client.post("/api/readings", json=dict(STORM, node_id="t-2", node_name="Second ridge"))
    client.post("/api/readings", json=dict(STORM, node_id="t-2", node_name="Second ridge"))
    time.sleep(0.3)
    log = client.get("/api/outbox").json()
    assert any("Second ridge" in m["preview"] for m in log)

    assert client.delete(f"/api/subscribers/{sub['id']}").status_code == 200
    assert client.delete(f"/api/subscribers/{sub['id']}").status_code == 404


def test_resolved_alerts_never_notify():
    import asyncio
    from backend.notifier import Notifier
    n = Notifier()
    resolved = {"kind": "resolved", "level": "safe", "title": "x", "message": "x", "reasons": [], "action": ""}
    asyncio.run(n.notify(resolved))
    assert len(n.outbox) == 0


# ------------------------------------------------------------------ injured people, lost people, animals
IMG = "data:image/jpeg;base64,AAAA"


def _cam(**kw):
    base = dict(camera_id="drone-1", name="Patrol drone", lat=30.60, lon=79.60, fire_score=0, person_count=0,
                motion=0.1, ai_active=True, roaming=True)
    base.update(kw)
    return base


def test_injured_person_alert_and_sighting(client):
    r = client.post("/api/camera/event", json=_cam(camera_id="drone-inj", person_count=1, person_down=True, snapshot=IMG))
    assert r.status_code == 200 and r.json()["person_down"] is True
    alerts = client.get("/api/alerts").json()
    inj = [a for a in alerts if "injured person" in a["title"]]
    assert inj and inj[0]["level"] in ("warning", "critical") and inj[0]["image"] == IMG
    sightings = client.get("/api/sightings").json()
    assert any(s["kind"] == "injured" and s["lat"] == 30.60 and s["image"] == IMG for s in sightings)


def test_sighting_near_missing_hiker_is_a_possible_match(client):
    # a hiker who pressed SOS, last seen at 30.7000, 79.7000
    client.post("/api/hikers/h-lost/checkin", json={"lat": 30.70, "lon": 79.70, "name": "Missing group"})
    client.post("/api/hikers/h-lost/sos")
    far = client.post("/api/camera/event", json=_cam(camera_id="drone-far", lat=31.5, lon=79.7, person_count=1, snapshot=IMG))
    assert far.status_code == 200
    assert not any("Possible match" in a["title"] and "Missing group" in a["title"] for a in client.get("/api/alerts").json())
    client.post("/api/camera/event", json=_cam(camera_id="drone-near", lat=30.71, lon=79.70, person_count=1, snapshot=IMG))
    match = [a for a in client.get("/api/alerts").json() if "Possible match" in a["title"] and "Missing group" in a["title"]]
    assert match and match[0]["level"] == "critical" and match[0]["image"] == IMG


def test_animals_are_counted_with_movement(client):
    animals = [{"species": "Elephant", "count": 4, "speed": 0.05, "direction": "right", "new_individuals": 4}]
    client.post("/api/camera/event", json=_cam(camera_id="trap-1", name="Trail camera", animals=animals, snapshot=IMG))
    animals[0].update(count=5, new_individuals=1, speed=0.12)
    client.post("/api/camera/event", json=_cam(camera_id="trap-1", name="Trail camera", animals=animals))
    w = {x["species"]: x for x in client.get("/api/wildlife").json()}
    e = w["elephant"]
    assert e["count_now"] == 5 and e["max_count"] == 5 and e["total_seen"] == 5
    assert e["movement"] == "fast" and e["direction"] == "right" and e["series"][-2:] == [4, 5]
    assert any(s["kind"] == "animal" and "Elephant" in s["label"] for s in client.get("/api/sightings").json())
    assert any("Elephant near camera" in a["title"] for a in client.get("/api/alerts").json())
    # animals leave -> count returns to zero
    client.post("/api/camera/event", json=_cam(camera_id="trap-1", name="Trail camera", animals=[]))
    assert {x["species"]: x for x in client.get("/api/wildlife").json()}["elephant"]["count_now"] == 0
    assert "sightings" in client.get("/api/state").json() and "wildlife" in client.get("/api/state").json()


def test_animal_validation(client):
    bad = _cam(animals=[{"species": "", "count": 1}])
    assert client.post("/api/camera/event", json=bad).status_code == 422
    assert client.post("/api/camera/event", json=_cam(animals=[{"species": "cow", "count": -1}])).status_code == 422
