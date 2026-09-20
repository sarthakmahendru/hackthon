"""Core service: receives readings, scores risk, raises alerts, pushes live updates."""
import asyncio
import logging
import time
from collections import defaultdict, deque

from ml.predict import HazardModels

from . import config
from . import database as db
from .alerts import Alerter, camera_alert, hazard_alert, hiker_alert, resolved_alert
from .external_data import ExternalData, haversine_km
from .risk_engine import ACTIONS, HAZARD_LABELS, LEVEL_RANK, assess
from .notifier import Notifier, mask_phone, normalize_phone, sms_text
from .schemas import CameraEvent, SensorReading

log = logging.getLogger("mountainsentinel")

DANGEROUS_SPECIES = {"elephant", "bear"}
MISSING_MATCH_KM = 5.0  # a sighting this close to a missing hiker's last position is a possible match

SERIES_KEYS = [
    "rain_1h_mm",
    "soil_moisture_pct",
    "tilt_deg",
    "water_level_cm",
    "temperature_c",
    "humidity_pct",
    "smoke_ppm",
    "vibration_g",
]


class Hub:
    """Tracks connected dashboards and pushes JSON events to them."""

    def __init__(self):
        self.clients = set()

    async def connect(self, ws) -> None:
        await ws.accept()
        self.clients.add(ws)

    def disconnect(self, ws) -> None:
        self.clients.discard(ws)

    async def broadcast(self, message: dict) -> None:
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


class Service:
    def __init__(self):
        self.hub = Hub()
        self.ml = HazardModels()
        self.external = ExternalData()
        self.alerter = Alerter()
        self.notifier = Notifier()
        self.notifier.on_log = self._broadcast_outbox
        self.cameras = {}  # camera_id -> latest camera state
        self.cam_alert_ts = {}
        self.sightings = deque(maxlen=40)  # newest first
        self.wildlife = {}  # species -> registry record
        self.history = defaultdict(lambda: deque(maxlen=20))  # readings used for trends
        self.series = defaultdict(lambda: deque(maxlen=60))  # points shown as sparklines
        self.latest = {}  # node_id -> {"reading", "assessment"}
        self.last_level = {}  # (node_id, hazard) -> level rank
        self.last_alert_ts = {}  # (node_id, hazard) -> time of last alert
        self.alert_rank = {}  # (node_id, hazard) -> highest level alerted in the current episode
        self.hikers = {}
        self.started_at = time.time()
        self.readings_total = 0
        self.alerts_total = 0

    def start(self) -> None:
        db.init()
        self.sightings = deque(db.recent_sightings(40), maxlen=40)
        self.ml.load(auto_train=True)

    # ------------------------------------------------------------ ingest
    async def ingest(self, data: dict) -> dict:
        reading = SensorReading(**data).model_dump()
        reading["ts"] = reading.get("ts") or time.time()
        node_id = reading["node_id"]
        reading["node_name"] = reading.get("node_name") or node_id

        ctx = self.external.context_for(node_id)
        ctx["camera_fire"] = self._camera_fire_near(reading["lat"], reading["lon"])
        assessment = assess(reading, list(self.history[node_id]), self.ml, ctx)
        self.history[node_id].append(reading)

        point = {"ts": reading["ts"], "risk_score": assessment["risk_score"]}
        point.update({k: reading[k] for k in SERIES_KEYS})
        self.series[node_id].append(point)

        self.latest[node_id] = {"reading": reading, "assessment": assessment}
        self.readings_total += 1
        db.insert_reading(
            node_id,
            reading["ts"],
            {
                "reading": reading,
                "risk_score": assessment["risk_score"],
                "risk_level": assessment["risk_level"],
                "top_hazard": assessment["top_hazard"],
            },
        )

        await self._raise_alerts(reading, assessment)
        view = self.node_view(node_id, with_series=False)
        view["point"] = point
        await self.hub.broadcast({"type": "node", "data": view})
        return view

    async def _emit(self, alert: dict) -> None:
        alert["id"] = db.insert_alert(alert)
        self.alerts_total += 1
        await self.hub.broadcast({"type": "alert", "data": alert})
        asyncio.create_task(self.alerter.send(alert))  # never block ingestion on the network
        asyncio.create_task(self.notifier.notify(alert))  # SMS / WhatsApp to subscribed phones

    async def _raise_alerts(self, reading: dict, assessment: dict) -> None:
        """Alert when risk escalates to Warning or Critical. A higher level than the one already
        alerted always fires immediately; repeats of the same level respect the cooldown."""
        now = time.time()
        node = {"node_id": reading["node_id"], "name": reading["node_name"]}
        for hazard, h in assessment["hazards"].items():
            key = (reading["node_id"], hazard)
            rank = LEVEL_RANK[h["level"]]
            prev = self.last_level.get(key, 0)
            self.last_level[key] = rank
            alerted_rank = self.alert_rank.get(key, 0)  # highest level alerted in this episode

            escalated = rank >= 2 and rank > alerted_rank
            repeated = rank >= 2 and rank > prev and now - self.last_alert_ts.get(key, 0) >= config.ALERT_COOLDOWN_S
            if escalated or repeated:
                self.last_alert_ts[key] = now
                self.alert_rank[key] = max(alerted_rank, rank)
                action = ACTIONS.get(hazard, {}).get(h["level"], "")
                await self._emit(
                    hazard_alert(node, HAZARD_LABELS[hazard], hazard, h["level"], h["score"], h["reasons"], action)
                )
            elif rank == 0 and alerted_rank > 0:
                self.alert_rank[key] = 0
                await self._emit(resolved_alert(node, HAZARD_LABELS[hazard], hazard))

    # ------------------------------------------------------------ views
    def node_view(self, node_id: str, with_series: bool = True) -> dict:
        item = self.latest[node_id]
        r = item["reading"]
        view = {
            "node_id": node_id,
            "name": r["node_name"],
            "lat": r["lat"],
            "lon": r["lon"],
            "reading": r,
            "assessment": item["assessment"],
        }
        if with_series:
            view["series"] = list(self.series[node_id])
        return view

    def hikers_view(self) -> list:
        now = time.time()
        return [{**h, "seconds_since_checkin": round(now - h["last_checkin"])} for h in self.hikers.values()]

    def snapshot(self) -> dict:
        levels = {"safe": 0, "watch": 0, "warning": 0, "critical": 0}
        nodes = []
        for nid in self.latest:
            v = self.node_view(nid)
            levels[v["assessment"]["risk_level"]] += 1
            nodes.append(v)
        return {
            "nodes": nodes,
            "levels": levels,
            "alerts": db.recent_alerts(30),
            "hikers": self.hikers_view(),
            "earthquakes": self.external.earthquakes,
            "fire_hotspots": self.external.fire_hotspots,
            "external": self.external.status(),
            "server_time": time.time(),
            "simulation": config.SIMULATE,
            "telegram": self.alerter.telegram_enabled,
            "cameras": self.cameras_view(),
            "sightings": list(self.sightings),
            "wildlife": self.wildlife_view(),
            "subscribers": self.subscribers_view(),
            "outbox": list(self.notifier.outbox),
            "phone_channels": self.notifier.status(),
            "model": {"available": self.ml.available, "metrics": self.ml.metrics},
        }

    def nearest_node(self, lat: float, lon: float):
        best, best_d = None, None
        for nid, item in self.latest.items():
            r = item["reading"]
            d = haversine_km(lat, lon, r["lat"], r["lon"])
            if best_d is None or d < best_d:
                best, best_d = item, d
        return best, best_d

    # ------------------------------------------------------------ hikers
    async def hiker_checkin(self, hiker_id: str, lat: float, lon: float, name: str = None) -> dict:
        prev = self.hikers.get(hiker_id)
        was_bad = prev is not None and prev["status"] in ("overdue", "sos")
        h = {
            "id": hiker_id,
            "name": name or (prev["name"] if prev else hiker_id),
            "lat": lat,
            "lon": lon,
            "last_checkin": time.time(),
            "status": "ok",
            "alerted": False,
        }
        self.hikers[hiker_id] = h
        if was_bad:
            await self._emit(
                hiker_alert(h, "safe", f"{h['name']} has checked in again and is safe", [], "Stand down the search.")
            )
        await self.hub.broadcast({"type": "hiker", "data": h})
        return h

    async def hiker_sos(self, hiker_id: str) -> dict:
        h = self.hikers.get(hiker_id)
        if h is None:
            raise KeyError(hiker_id)
        h["status"] = "sos"
        await self._hiker_emergency(h, "SOS pressed")
        await self.hub.broadcast({"type": "hiker", "data": h})
        return h

    async def _hiker_emergency(self, h: dict, why: str) -> None:
        node, dist = self.nearest_node(h["lat"], h["lon"])
        reasons = [f"Last known position: {h['lat']:.4f}, {h['lon']:.4f}."]
        priority = "normal"
        if node is not None:
            a = node["assessment"]
            reasons.append(
                f"Nearest sensor node: {node['reading']['node_name']}, {dist:.1f} km away, "
                f"risk {a['risk_level']} ({a['top_hazard_label']})."
            )
            if LEVEL_RANK[a["risk_level"]] >= 2:
                priority = "HIGH"
                reasons.append("Search priority HIGH: the area around the last known position is unsafe.")
        action = f"Send the rescue team to the last known position. Search priority: {priority}."
        h["alerted"] = True
        await self._emit(hiker_alert(h, "critical", f"{h['name']}: {why}", reasons, action))

    async def hiker_watchdog(self) -> None:
        """Every 2 s: raise an alert when a hiker misses check-ins."""
        while True:
            try:
                now = time.time()
                for h in list(self.hikers.values()):
                    if h["status"] == "ok" and now - h["last_checkin"] > config.HIKER_OVERDUE_S:
                        h["status"] = "overdue"
                        await self._hiker_emergency(h, f"missed check-in for {config.HIKER_OVERDUE_S:.0f} s")
                        await self.hub.broadcast({"type": "hiker", "data": h})
            except Exception:
                log.exception("hiker watchdog error")
            await asyncio.sleep(2)

    # ------------------------------------------------------------ external
    async def external_refresher(self) -> None:
        await asyncio.sleep(3)  # let the first readings arrive so we know where the nodes are
        while True:
            try:
                nodes = [
                    {"node_id": nid, "name": i["reading"]["node_name"], "lat": i["reading"]["lat"], "lon": i["reading"]["lon"]}
                    for nid, i in self.latest.items()
                ]
                await self.external.refresh(nodes)
                await self.hub.broadcast(
                    {
                        "type": "external",
                        "data": {
                            "external": self.external.status(),
                            "earthquakes": self.external.earthquakes,
                            "fire_hotspots": self.external.fire_hotspots,
                        },
                    }
                )
            except Exception:
                log.exception("external refresh error")
            await asyncio.sleep(600)

    # ------------------------------------------------------------ cameras
    def cameras_view(self) -> list:
        now = time.time()
        return [{**c, "online": now - c["ts"] < config.CAMERA_STALE_S} for c in self.cameras.values()]

    def _camera_fire_near(self, lat: float, lon: float, max_km: float = 25.0):
        now, best = time.time(), None
        for c in self.cameras.values():
            if not c.get("fire_active") or now - c["ts"] > config.CAMERA_STALE_S:
                continue
            d = haversine_km(lat, lon, c["lat"], c["lon"])
            if d <= max_km and (best is None or d < best["km"]):
                best = {"name": c["name"], "km": d, "score": c["fire_score"]}
        return best

    async def _sighting(self, kind: str, label: str, cam: dict, count: int, image, note: str = "") -> dict:
        rec = {
            "ts": time.time(), "kind": kind, "label": label, "count": count, "lat": cam["lat"], "lon": cam["lon"],
            "camera": cam["name"], "image": image, "note": note,
        }
        rec["id"] = db.insert_sighting(rec)
        self.sightings.appendleft(rec)
        await self.hub.broadcast({"type": "sighting", "data": rec})
        return rec

    def _missing_near(self, lat: float, lon: float) -> list:
        """Missing (overdue or SOS) hikers whose last known position is close to (lat, lon)."""
        out = []
        for h in self.hikers.values():
            if h["status"] in ("overdue", "sos"):
                d = haversine_km(lat, lon, h["lat"], h["lon"])
                if d <= MISSING_MATCH_KM:
                    out.append((h, d))
        return sorted(out, key=lambda x: x[1])

    def wildlife_view(self) -> list:
        now = time.time()
        out = []
        for r in self.wildlife.values():
            active = now - r["last_seen"] < 30
            speed = r["speed"] if active else 0
            out.append({
                "species": r["species"],
                "count_now": r["count_now"] if active else 0,
                "max_count": r["max_count"],
                "total_seen": r["total_seen"],
                "movement": "still" if speed < 0.02 else ("slow" if speed < 0.08 else "fast"),
                "direction": r["direction"] if active and speed >= 0.02 else "none",
                "first_seen": r["first_seen"],
                "last_seen": r["last_seen"],
                "camera": r["camera"],
                "lat": r["lat"],
                "lon": r["lon"],
                "series": list(r["series"]),
            })
        return sorted(out, key=lambda r: -r["last_seen"])

    async def camera_event(self, ev: dict) -> dict:
        """A camera node reports what it sees: flames, people, injured people, animals.
        Roaming cameras (drone, rover, phone on patrol) send their GPS position with every event."""
        ev = CameraEvent(**ev).model_dump()
        now = time.time()
        cid = ev["camera_id"]
        prev = self.cameras.get(cid, {})
        fire = ev["fire_score"] >= 0.5
        person = ev["person_count"] > 0
        down = bool(ev["person_down"]) and person
        animals = ev["animals"]
        cam = {
            "id": cid,
            "name": ev.get("name") or cid,
            "lat": ev["lat"],
            "lon": ev["lon"],
            "fire_score": round(ev["fire_score"], 2),
            "person_count": ev["person_count"],
            "motion": round(ev["motion"], 2),
            "ai_active": ev["ai_active"],
            "roaming": ev["roaming"],
            "person_down": down,
            "animal_count": sum(a["count"] for a in animals),
            "fire_active": fire,
            "person_active": person,
            "ts": now,
        }
        self.cameras[cid] = cam
        image = ev.get("snapshot")

        node, dist = self.nearest_node(cam["lat"], cam["lon"])
        near = []
        node_rank = 0
        if node is not None:
            a = node["assessment"]
            node_rank = LEVEL_RANK[a["risk_level"]]
            near.append(
                f"Nearest sensor node: {node['reading']['node_name']}, {dist:.1f} km away "
                f"(risk {a['risk_level']}, {a['top_hazard_label'].lower()})."
            )
        where = f"Camera position: {cam['lat']:.4f}, {cam['lon']:.4f}."

        # ---- fire
        if fire and not prev.get("fire_active") and now - self.cam_alert_ts.get((cid, "fire"), 0) >= 20:
            self.cam_alert_ts[(cid, "fire")] = now
            level = "critical" if ev["fire_score"] >= 0.75 else "warning"
            await self._emit(
                camera_alert(
                    cam, level, f"Camera '{cam['name']}' sees flames (confidence {ev['fire_score'] * 100:.0f}%)",
                    ["Flame-coloured, flickering region detected in the live video.", where] + near,
                    "Check the live view. If the fire is real, alert the forest department and nearby villages.",
                    image,
                )
            )
        elif not fire and prev.get("fire_active"):
            await self._emit(camera_alert(cam, "safe", f"Camera '{cam['name']}' no longer sees flames", [], ""))

        # ---- people, injured people, missing hikers
        n = ev["person_count"]
        who = "1 person" if n == 1 else f"{n} people"
        unsafe = node_rank >= 2
        matches = self._missing_near(cam["lat"], cam["lon"]) if person else []

        if person and not prev.get("person_active") and now - self.cam_alert_ts.get((cid, "person"), 0) >= 20 and not down:
            self.cam_alert_ts[(cid, "person")] = now
            reasons = [f"AI detected {who} in the camera view.", where] + near
            if unsafe:
                reasons.append("The area is under a Warning or Critical risk level: people should leave.")
            await self._emit(
                camera_alert(
                    cam, "warning" if unsafe else "watch",
                    f"Camera '{cam['name']}' detected {who}" + (" in an unsafe area" if unsafe else ""),
                    reasons, "Warn them by loudspeaker or call the local rescue team." if unsafe else "", image,
                )
            )

        if down and not prev.get("person_down") and now - self.cam_alert_ts.get((cid, "down"), 0) >= 30:
            self.cam_alert_ts[(cid, "down")] = now
            reasons = ["AI sees a person lying on the ground who has not moved for several seconds.", where] + near
            if matches:
                reasons.append(f"This is {matches[0][1]:.1f} km from the last known position of missing {matches[0][0]['name']}.")
            await self._emit(
                camera_alert(
                    cam, "critical" if (unsafe or matches) else "warning",
                    f"Possible injured person seen by '{cam['name']}'",
                    reasons,
                    "Look at the photo. If they need help, send the rescue team to the camera position now.", image,
                )
            )

        if person and image and now - self.cam_alert_ts.get((cid, "sight"), 0) >= 8:
            self.cam_alert_ts[(cid, "sight")] = now
            await self._sighting("injured" if down else "person", "Possible injured person" if down else who.capitalize(), cam, n, image, where)

        for h, km in matches:
            if now - self.cam_alert_ts.get((cid, "match", h["id"]), 0) >= 60:
                self.cam_alert_ts[(cid, "match", h["id"])] = now
                await self._emit(
                    camera_alert(
                        cam, "critical", f"Possible match: {who} seen {km:.1f} km from where {h['name']} went missing",
                        [f"'{cam['name']}' sees {who}.", where, f"Missing since the last check-in near {h['lat']:.4f}, {h['lon']:.4f}.",
                         "Open the photo and confirm whether it is the missing person."],
                        "Confirm with the photo, then send rescuers to the camera position.", image,
                    )
                )

        # ---- animals: registry with counts and movement
        present = set()
        for a in animals:
            sp = a["species"].strip().lower()
            present.add(sp)
            rec = self.wildlife.get(sp)
            if rec is None:
                rec = {"species": sp, "first_seen": now, "max_count": 0, "total_seen": 0, "series": deque(maxlen=40), "last_sighting": 0}
                self.wildlife[sp] = rec
            rec.update(count_now=a["count"], speed=a["speed"], direction=a["direction"], last_seen=now,
                       camera=cam["name"], lat=cam["lat"], lon=cam["lon"])
            rec["max_count"] = max(rec["max_count"], a["count"])
            rec["total_seen"] += a["new_individuals"]
            rec["series"].append(a["count"])
            if image and now - rec["last_sighting"] >= 120:
                rec["last_sighting"] = now
                label = f"{sp.capitalize()} x{a['count']}" if a["count"] > 1 else sp.capitalize()
                await self._sighting("animal", label, cam, a["count"], image, where)
            if sp in DANGEROUS_SPECIES and a["count"] > 0 and now - self.cam_alert_ts.get((cid, "animal", sp), 0) >= 300:
                self.cam_alert_ts[(cid, "animal", sp)] = now
                with_people = person
                reasons = [f"{a['count']} {sp}(s) in view, movement: {'still' if a['speed'] < 0.02 else 'moving'}.", where] + near
                if with_people:
                    reasons.append("People are in the same view. Keep them apart.")
                await self._emit(
                    camera_alert(
                        cam, "warning" if with_people else "watch", f"{sp.capitalize()} near camera '{cam['name']}'",
                        reasons, "Warn nearby villages and trekkers. Keep a safe distance." if with_people else "", image,
                    )
                )
        cleared = False
        for sp, rec in self.wildlife.items():
            if sp not in present and rec.get("camera") == cam["name"] and rec.get("count_now", 0) != 0:
                rec["count_now"] = 0
                rec["series"].append(0)
                cleared = True
        if animals or cleared:
            await self.hub.broadcast({"type": "wildlife", "data": self.wildlife_view()})

        await self.hub.broadcast({"type": "camera", "data": {**cam, "online": True}})
        return {**cam, "online": True}

    # ------------------------------------------------------------ phone alerts
    async def _broadcast_outbox(self, entry: dict) -> None:
        await self.hub.broadcast({"type": "outbox", "data": entry})

    def subscribers_view(self) -> list:
        return [
            {"id": s["id"], "name": s["name"], "phone": mask_phone(s["phone"]), "channel": s["channel"], "min_level": s["min_level"]}
            for s in db.list_subscribers()
        ]

    async def subscribe(self, name: str, phone: str, channel: str, min_level: str) -> dict:
        number = normalize_phone(phone)  # raises ValueError on bad input
        existing = db.list_subscribers()
        if len(existing) >= config.MAX_SUBSCRIBERS and not any(s["phone"] == number and s["channel"] == channel for s in existing):
            raise OverflowError(f"Subscriber limit reached ({config.MAX_SUBSCRIBERS}).")
        sub_id = db.add_subscriber(name.strip(), number, channel, min_level, time.time())
        await self.hub.broadcast({"type": "subscribers", "data": self.subscribers_view()})
        return {"id": sub_id, "name": name.strip(), "phone": mask_phone(number), "channel": channel, "min_level": min_level}

    async def unsubscribe(self, sub_id: int) -> bool:
        ok = db.delete_subscriber(sub_id)
        if ok:
            await self.hub.broadcast({"type": "subscribers", "data": self.subscribers_view()})
        return ok

    async def send_test(self, sub_id: int) -> dict:
        sub = db.get_subscriber(sub_id)
        if sub is None:
            raise KeyError(sub_id)
        body = "MountainSentinel test message: you will receive mountain disaster alerts on this number."
        return await self.notifier.send(sub, body)
