"""Live public data that makes predictions earlier and the project real.

  * Open-Meteo   : rainfall forecast for the next 24 h (free, no key)
  * USGS         : recent earthquakes near the network (free, no key)
  * NASA FIRMS   : satellite active-fire hotspots (free key: FIRMS_MAP_KEY)

Everything is cached and every call fails softly. If the internet is down at the
demo, the system keeps working with sensor data alone.
"""
import asyncio
import csv
import io
import logging
import math
import time
from datetime import datetime, timedelta, timezone

import httpx

from . import config

log = logging.getLogger("mountainsentinel.external")

REFRESH_S = 600


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = p2 - p1
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class ExternalData:
    def __init__(self):
        self.forecast = {}  # node_id -> mm in next 24 h
        self.fire_km = {}  # node_id -> distance (km) to nearest hotspot
        self.earthquakes = []
        self.fire_hotspots = []
        self.status_info = {
            "forecast": "waiting",
            "earthquakes": "waiting",
            "fires": "not configured" if not config.FIRMS_MAP_KEY else "waiting",
        }
        self.last_refresh = None

    # ----------------------------------------------------------- lookups
    def context_for(self, node_id: str) -> dict:
        return {
            "forecast_24h_mm": self.forecast.get(node_id),
            "nearest_fire_km": self.fire_km.get(node_id),
        }

    def status(self) -> dict:
        return {
            "forecast": self.status_info["forecast"],
            "earthquakes": self.status_info["earthquakes"],
            "earthquake_count": len(self.earthquakes),
            "fires": self.status_info["fires"],
            "fire_count": len(self.fire_hotspots),
            "last_refresh": self.last_refresh,
        }

    # ----------------------------------------------------------- fetchers
    async def _forecast(self, client: httpx.AsyncClient, node: dict):
        r = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": node["lat"],
                "longitude": node["lon"],
                "hourly": "precipitation",
                "forecast_days": 2,
                "timezone": "UTC",
            },
        )
        r.raise_for_status()
        data = r.json()["hourly"]
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00")
        times, rain = data["time"], data["precipitation"]
        start = next((i for i, t in enumerate(times) if t >= now), 0)
        return float(sum(v or 0 for v in rain[start : start + 24]))

    async def _earthquakes(self, client: httpx.AsyncClient, lat: float, lon: float):
        start = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
        r = await client.get(
            "https://earthquake.usgs.gov/fdsnws/event/1/query",
            params={
                "format": "geojson",
                "latitude": lat,
                "longitude": lon,
                "maxradiuskm": 400,
                "minmagnitude": 2.5,
                "starttime": start,
                "orderby": "time",
                "limit": 30,
            },
        )
        r.raise_for_status()
        out = []
        for feat in r.json().get("features", []):
            lon_, lat_, depth = feat["geometry"]["coordinates"][:3]
            p = feat["properties"]
            out.append(
                {
                    "id": feat.get("id"),
                    "mag": p.get("mag"),
                    "place": p.get("place"),
                    "time": (p.get("time") or 0) / 1000,
                    "lat": lat_,
                    "lon": lon_,
                    "depth_km": depth,
                }
            )
        return out

    async def _fires(self, client: httpx.AsyncClient, nodes: list):
        lats = [n["lat"] for n in nodes]
        lons = [n["lon"] for n in nodes]
        west, east = min(lons) - 0.6, max(lons) + 0.6
        south, north = min(lats) - 0.6, max(lats) + 0.6
        url = (
            f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/{config.FIRMS_MAP_KEY}"
            f"/VIIRS_SNPP_NRT/{west},{south},{east},{north}/1"
        )
        r = await client.get(url)
        r.raise_for_status()
        spots = []
        for row in csv.DictReader(io.StringIO(r.text)):
            try:
                spots.append(
                    {
                        "lat": float(row["latitude"]),
                        "lon": float(row["longitude"]),
                        "confidence": row.get("confidence"),
                        "date": row.get("acq_date"),
                    }
                )
            except (KeyError, ValueError):
                continue
        return spots

    # ----------------------------------------------------------- refresh
    async def refresh(self, nodes: list) -> None:
        """Refresh all feeds. `nodes` = [{"node_id", "name", "lat", "lon"}]."""
        if not nodes:
            return
        async with httpx.AsyncClient(timeout=10) as client:
            results = await asyncio.gather(*(self._forecast(client, n) for n in nodes), return_exceptions=True)
            ok = 0
            for n, res in zip(nodes, results):
                if isinstance(res, Exception):
                    continue
                self.forecast[n["node_id"]] = res
                ok += 1
            self.status_info["forecast"] = "live" if ok else "offline"

            clat = sum(n["lat"] for n in nodes) / len(nodes)
            clon = sum(n["lon"] for n in nodes) / len(nodes)
            try:
                self.earthquakes = await self._earthquakes(client, clat, clon)
                self.status_info["earthquakes"] = "live"
            except Exception as exc:
                log.info("USGS unavailable: %s", exc)
                self.status_info["earthquakes"] = "offline"

            if config.FIRMS_MAP_KEY:
                try:
                    self.fire_hotspots = await self._fires(client, nodes)
                    self.status_info["fires"] = "live"
                    for n in nodes:
                        d = [haversine_km(n["lat"], n["lon"], s["lat"], s["lon"]) for s in self.fire_hotspots]
                        if d:
                            self.fire_km[n["node_id"]] = min(d)
                        else:
                            self.fire_km.pop(n["node_id"], None)
                except Exception as exc:
                    log.info("FIRMS unavailable: %s", exc)
                    self.status_info["fires"] = "offline"
        self.last_refresh = time.time()
