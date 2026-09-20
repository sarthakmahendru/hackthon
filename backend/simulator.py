"""Simulated sensor network for demos and development.

Six solar-powered nodes across Uttarakhand send readings every few seconds, exactly like real
hardware would through POST /api/readings. Click a scenario in the dashboard (or call
POST /api/demo/scenario) and the affected nodes drift towards disaster conditions, so judges
watch the risk engine react live.

Nothing here touches the risk engine: the simulator only produces sensor values. To use real
hardware, set SIMULATE=false and post readings to /api/readings.
"""
import asyncio
import base64
import logging
import math
import random
import time

from . import config

log = logging.getLogger("mountainsentinel.sim")

KEYS = [
    "rain_1h_mm",
    "rain_24h_mm",
    "soil_moisture_pct",
    "tilt_deg",
    "temperature_c",
    "humidity_pct",
    "smoke_ppm",
    "water_level_cm",
]
NOISE = {
    "rain_1h_mm": 0.15,
    "rain_24h_mm": 0.4,
    "soil_moisture_pct": 0.3,
    "tilt_deg": 0.01,
    "temperature_c": 0.15,
    "humidity_pct": 0.4,
    "smoke_ppm": 1.0,
    "water_level_cm": 0.6,
}

NODE_DEFS = [
    {"node_id": "node-joshimath", "name": "Joshimath ridge", "lat": 30.5550, "lon": 79.5644},
    {"node_id": "node-uttarkashi", "name": "Uttarkashi river bend", "lat": 30.7268, "lon": 78.4354},
    {"node_id": "node-nainital", "name": "Nainital forest belt", "lat": 29.3919, "lon": 79.4542},
    {"node_id": "node-mussoorie", "name": "Mussoorie hill road", "lat": 30.4598, "lon": 78.0644},
    {"node_id": "node-gopeshwar", "name": "Gopeshwar valley", "lat": 30.4050, "lon": 79.3170},
    {"node_id": "node-pithoragarh", "name": "Pithoragarh slope", "lat": 29.5829, "lon": 80.2182},
]

# Where each scenario drifts to. Values are the sensor readings the node moves towards.
SCENARIOS = {
    "landslide": {
        "label": "Landslide",
        "default_nodes": ["node-joshimath"],
        "targets": {"rain_1h_mm": 32, "rain_24h_mm": 150, "soil_moisture_pct": 93, "tilt_deg": 5.0, "water_level_cm": 90},
    },
    "flood": {
        "label": "Flash flood",
        "default_nodes": ["node-uttarkashi"],
        "targets": {"rain_1h_mm": 48, "rain_24h_mm": 130, "soil_moisture_pct": 85, "water_level_cm": 270},
    },
    "wildfire": {
        "label": "Forest fire",
        "default_nodes": ["node-nainital"],
        "targets": {"temperature_c": 47, "humidity_pct": 13, "smoke_ppm": 340},
    },
    "earthquake": {
        "label": "Earthquake shaking",
        "default_nodes": ["node-joshimath", "node-gopeshwar"],
        # Recent rain has soaked the slope; the shaking itself is added on top (see _step).
        "targets": {"rain_24h_mm": 90, "soil_moisture_pct": 82, "tilt_deg": 1.5},
    },
}
SCENARIO_MAX_TICKS = 90  # scenarios end by themselves after ~3 minutes


# A simulated patrol drone with a camera. It roams, sends its GPS position and photos, exactly like a
# real drone, rover or phone running the camera page would (POST /api/camera/event).
PATROL_ID = "cam-patrol-d1"
PATROL_NAME = "Patrol drone D1"
CAMERA_SCENARIOS = {"rescue_drone": "Drone finds the missing group", "injured": "Injured trekker on trail", "animals": "Elephant herd near Nainital"}


def fake_photo(kind: str, caption: str) -> str:
    """A labelled placeholder picture. Real cameras send real JPEG snapshots."""
    shapes = {
        "standing": '<circle cx="160" cy="88" r="12" fill="#E8C9A0"/><rect x="146" y="102" width="28" height="60" rx="8" fill="#C0392B"/>'
                    '<rect x="148" y="160" width="10" height="34" fill="#2C3E50"/><rect x="162" y="160" width="10" height="34" fill="#2C3E50"/>',
        "group": "".join(
            f'<circle cx="{x}" cy="98" r="10" fill="#E8C9A0"/><rect x="{x - 11}" cy="0" y="110" width="22" height="48" rx="7" fill="{c}"/>'
            f'<rect x="{x - 9}" y="156" width="8" height="30" fill="#2C3E50"/><rect x="{x + 1}" y="156" width="8" height="30" fill="#2C3E50"/>'
            for x, c in ((100, "#C0392B"), (140, "#2980B9"), (180, "#F39C12"), (220, "#8E44AD"))),
        "lying": '<circle cx="116" cy="168" r="12" fill="#E8C9A0"/><rect x="128" y="158" width="76" height="22" rx="9" fill="#C0392B"/>'
                 '<rect x="200" y="160" width="40" height="8" fill="#2C3E50"/><rect x="200" y="171" width="38" height="8" fill="#2C3E50"/>',
        "elephants": "".join(
            f'<ellipse cx="{x}" cy="{y}" rx="34" ry="22" fill="#7F8C8D"/><circle cx="{x - 30}" cy="{y - 6}" r="13" fill="#7F8C8D"/>'
            f'<rect x="{x - 46}" y="{y - 4}" width="8" height="26" rx="4" fill="#6C7A7B"/>'
            f'<rect x="{x - 14}" y="{y + 14}" width="9" height="22" fill="#6C7A7B"/><rect x="{x + 12}" y="{y + 14}" width="9" height="22" fill="#6C7A7B"/>'
            for x, y in ((90, 150), (170, 165), (245, 148))),
    }
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="240" viewBox="0 0 320 240">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#9DBFA9"/><stop offset="1" stop-color="#3B5B49"/></linearGradient></defs>'
        '<rect width="320" height="240" fill="url(#g)"/>'
        '<polygon points="10,190 40,90 70,190" fill="#2E4A3A"/><polygon points="250,190 285,70 315,190" fill="#2E4A3A"/>'
        f"{shapes.get(kind, '')}"
        '<rect y="206" width="320" height="34" fill="#000" fill-opacity=".6"/>'
        f'<text x="10" y="228" fill="#fff" font-family="sans-serif" font-size="14">SIMULATED PHOTO: {caption}</text></svg>'
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


HIKER_DEFS = [
    {"id": "H-101", "name": "Trek group A (4 people)", "lat": 30.5330, "lon": 79.5760},
    {"id": "H-102", "name": "Solo trekker Priya", "lat": 29.4080, "lon": 79.4300},
    {"id": "H-103", "name": "Trek group B (6 people)", "lat": 30.7050, "lon": 78.4600},
]
HIKER_CHECKIN_EVERY_S = 8


class Simulator:
    def __init__(self, service, seed: int = 7):
        self.service = service
        self.rng = random.Random(seed)
        self.nodes = {}
        for d in NODE_DEFS:
            base = {
                "rain_1h_mm": self.rng.uniform(0.1, 1.0),
                "rain_24h_mm": self.rng.uniform(4, 14),
                "soil_moisture_pct": self.rng.uniform(34, 52),
                "tilt_deg": self.rng.uniform(0.1, 0.3),
                "temperature_c": self.rng.uniform(14, 24),
                "humidity_pct": self.rng.uniform(52, 72),
                "smoke_ppm": self.rng.uniform(6, 14),
                "water_level_cm": self.rng.uniform(45, 65),
            }
            self.nodes[d["node_id"]] = {
                **d,
                "base": base,
                "state": dict(base),
                "scenario": None,
                "quake_t": None,
                "ticks": 0,
            }
        self.hikers = {h["id"]: {**h, "lost": False, "last_sim": 0.0} for h in HIKER_DEFS}
        self.patrol = {"mode": None, "ticks": 0}

    # ------------------------------------------------------------ control
    def trigger(self, scenario: str, node_id: str = None) -> dict:
        if scenario == "reset":
            for n in self.nodes.values():
                n["scenario"] = None
                n["quake_t"] = None
            for h in self.hikers.values():
                h["lost"] = False
                h["last_sim"] = 0.0  # check in right away
            self.patrol = {"mode": None, "ticks": 0}
            return {"scenario": "reset", "nodes": list(self.nodes)}

        if scenario in CAMERA_SCENARIOS:
            mode = {"rescue_drone": "found", "injured": "injured", "animals": "animals"}[scenario]
            if mode == "found":
                self.hikers["H-101"]["lost"] = True  # the drone is searching for a group that went silent
            self.patrol = {"mode": mode, "ticks": 0}
            return {"scenario": scenario, "cameras": [PATROL_ID]}

        if scenario == "hiker_lost":
            hid = node_id if node_id in self.hikers else "H-101"
            self.hikers[hid]["lost"] = True
            return {"scenario": scenario, "hikers": [hid]}

        spec = SCENARIOS.get(scenario)
        if spec is None:
            raise ValueError(f"Unknown scenario '{scenario}'. Use one of: {', '.join(list(SCENARIOS) + list(CAMERA_SCENARIOS) + ['hiker_lost', 'reset'])}")
        targets = [node_id] if node_id else spec["default_nodes"]
        for nid in targets:
            if nid not in self.nodes:
                raise ValueError(f"Unknown node '{nid}'")
            n = self.nodes[nid]
            n["scenario"] = {"name": scenario, "targets": spec["targets"], "ticks": 0}
            if scenario == "earthquake":
                n["quake_t"] = 0
        return {"scenario": scenario, "nodes": targets}

    # ------------------------------------------------------------ physics
    def _step(self, n: dict) -> dict:
        s, base = n["state"], n["base"]
        targets = dict(base)
        sc = n["scenario"]
        if sc:
            targets.update(sc["targets"])
            sc["ticks"] += 1
            if sc["ticks"] > SCENARIO_MAX_TICKS:
                n["scenario"] = None
        n["ticks"] += 1

        for k in KEYS:
            s[k] += (targets[k] - s[k]) * 0.15 + self.rng.gauss(0, NOISE[k])
        s["rain_1h_mm"] = max(0.0, s["rain_1h_mm"])
        s["rain_24h_mm"] = max(0.0, s["rain_24h_mm"])
        s["tilt_deg"] = abs(s["tilt_deg"])
        s["soil_moisture_pct"] = min(100.0, max(0.0, s["soil_moisture_pct"]))
        s["humidity_pct"] = min(100.0, max(5.0, s["humidity_pct"]))
        s["smoke_ppm"] = max(0.0, s["smoke_ppm"])
        s["water_level_cm"] = max(0.0, s["water_level_cm"])

        vib = abs(self.rng.gauss(0.0012, 0.0006))
        if n["quake_t"] is not None:
            vib += 0.16 * math.exp(-0.30 * n["quake_t"])
            n["quake_t"] += 1
            if n["quake_t"] > 40:
                n["quake_t"] = None

        return {
            "node_id": n["node_id"],
            "node_name": n["name"],
            "lat": n["lat"],
            "lon": n["lon"],
            "ts": time.time(),
            "rain_1h_mm": round(s["rain_1h_mm"], 2),
            "rain_24h_mm": round(s["rain_24h_mm"], 1),
            "soil_moisture_pct": round(s["soil_moisture_pct"], 1),
            "tilt_deg": round(s["tilt_deg"], 3),
            "vibration_g": round(min(vib, 5.0), 4),
            "temperature_c": round(s["temperature_c"], 1),
            "humidity_pct": round(s["humidity_pct"], 1),
            "smoke_ppm": round(s["smoke_ppm"], 1),
            "water_level_cm": round(s["water_level_cm"], 1),
            "battery_pct": round(max(20.0, 96 - n["ticks"] * 0.002), 1),
        }

    async def _patrol_tick(self) -> None:
        p = self.patrol
        if p["mode"] is None:
            return
        p["ticks"] += 1
        t = p["ticks"]
        ev = {
            "camera_id": PATROL_ID, "name": PATROL_NAME, "lat": 30.53, "lon": 79.60, "fire_score": 0.0,
            "person_count": 0, "motion": 0.25, "ai_active": True, "roaming": True, "animals": [],
        }
        if p["mode"] == "found":
            hk = self.hikers["H-101"]
            progress = min(1.0, t / 20)
            off = 0.03 * (1 - progress)
            ev["lat"], ev["lon"] = hk["lat"] + 0.8 * off + 0.003, hk["lon"] - off + 0.002
            # The drone spots the group once it has really been reported missing (overdue), so the
            # sighting becomes a "possible match" alert.
            overdue = self.service.hikers.get("H-101", {}).get("status") in ("overdue", "sos")
            if overdue and t >= 20 and "seen_from" not in p:
                p["seen_from"] = t
            if "seen_from" in p:
                k = t - p["seen_from"]
                if k <= 10:
                    ev["person_count"] = 4
                    if k in (0, 5, 10):
                        ev["snapshot"] = fake_photo("group", "4 people seen from the drone")
                else:
                    p["mode"] = None
            if t > 150:
                p["mode"] = None
        elif p["mode"] == "injured":
            ev["lat"], ev["lon"] = 29.4200 + t * 0.00002, 79.4300
            ev["person_count"], ev["motion"] = 1, 0.02
            if t >= 3:
                ev["person_down"] = True
                if t in (3, 11, 19):
                    ev["snapshot"] = fake_photo("lying", "person lying still")
            if t > 22:
                p["mode"] = None
        elif p["mode"] == "animals":
            ev["lat"], ev["lon"] = 29.4000 + t * 0.00003, 79.4700
            herd = 3 + (t // 8) % 3
            ev["animals"] = [
                {"species": "elephant", "count": herd, "speed": 0.06, "direction": "right",
                 "new_individuals": 3 if t == 2 else (1 if t % 8 == 0 and t > 2 else 0)},
                {"species": "bird", "count": 6, "speed": 0.2, "direction": "left", "new_individuals": 6 if t == 2 else 0},
            ]
            if t == 2:
                ev["snapshot"] = fake_photo("elephants", f"elephant herd, {herd} counted")
            if t > 30:
                ev["animals"] = []
                p["mode"] = None
        await self.service.camera_event(ev)

    # ------------------------------------------------------------ loop
    async def _tick(self) -> None:
        for n in self.nodes.values():
            await self.service.ingest(self._step(n))
        now = time.time()
        for h in self.hikers.values():
            if h["lost"] or now - h["last_sim"] < HIKER_CHECKIN_EVERY_S:
                continue
            h["lat"] += self.rng.gauss(0, 0.0006)
            h["lon"] += self.rng.gauss(0, 0.0006)
            h["last_sim"] = now
            await self.service.hiker_checkin(h["id"], h["lat"], h["lon"], h["name"])
        await self._patrol_tick()

    async def run(self) -> None:
        log.info("Simulator started: %d nodes, %d hikers", len(self.nodes), len(self.hikers))
        for _ in range(8):  # warm-up so trend features have history before the first dashboard opens
            await self._tick()
        while True:
            try:
                await self._tick()
            except Exception:
                log.exception("simulator tick failed")
            await asyncio.sleep(config.SIM_INTERVAL_S)
