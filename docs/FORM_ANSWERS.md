# Google Form answers (copy and paste)

Replace the two placeholders (GitHub link, team names) before you submit.
If a box has a character limit, use the SHORT version under each answer.

---

## Problem Statement

Mountain and forest regions such as the Himalayas face landslides, flash floods, forest fires and earthquakes, often in remote places with no monitoring and weak mobile networks. Warnings arrive too late or never. The people who suffer are hill villagers, trekkers, forest staff and rescue teams.

The same areas have a second problem: trekkers and villagers get lost or injured in dense jungle, and rescuers learn about it hours later and then search blindly. Wildlife movement, such as elephants near villages, is also tracked by hand, which is slow and incomplete.

Solving this matters because most of these disasters give early signs (heavy rain, saturated soil, tilting ground, smoke, dry heat) that low-cost sensors and AI can read. A warning that reaches a phone in time lets people leave before the disaster arrives, and a location and photo of a lost person can cut hours from a rescue.

**SHORT:** Mountain and forest regions face landslides, floods, forest fires and earthquakes with no monitoring, and people get lost or injured in jungle without anyone knowing. Villagers, trekkers, forest staff and rescuers get warnings too late. Early signs exist in cheap sensor data, and a phone alert in time saves lives.

---

## Your Solution

MountainSentinel is an AI early-warning and search platform for mountain and forest regions.

**Workflow:**
1. Solar sensor nodes measure rainfall, soil moisture, ground tilt, vibration, temperature, smoke and stream level, and send JSON to our FastAPI backend.
2. A hybrid risk engine (physics rules, including the Caine 1980 rainfall threshold, plus Random Forest models and live context from a rain forecast, satellite fire hotspots and cameras) scores each hazard from 0 to 100 and gives the reasons in plain language and a recommended action.
3. A live map dashboard shows every node in real time. Alerts go to the dashboard, to Telegram, and by SMS or WhatsApp to any phone number a person enters.
4. Any laptop webcam, drone or phone can act as a camera node.

**Key features:**
- **Forest fire detection:** smoke, heat and dryness sensors, satellite hotspots, and camera flame detection.
- **Injured people:** the camera AI flags a person lying still and sends an alert with a photo.
- **Lost people:** hikers check in and send SOS. A roaming camera sends its GPS position and a photo of any person it sees, and the system matches sightings to missing hikers.
- **Wildlife monitoring:** the camera photographs animals, counts each species, tracks their movement and keeps a wildlife log.
- Landslide, flash-flood and ground-shaking warnings, including compound risk (shaking on wet soil).

The demo runs on a simulated sensor network through the same API that real ESP32 and LoRa hardware will use.

**SHORT:** Solar sensor nodes and cameras send data to a FastAPI backend. A hybrid physics and machine-learning engine scores landslide, flood, fire and shaking risk with plain-language reasons. A live map and SMS, WhatsApp and Telegram alerts warn people. The camera AI detects flames, injured people and animals (with counts and movement), and a roaming camera sends GPS and photos to find lost people.

---

## Uniqueness & Innovation

- **One platform, many jobs.** Most tools handle a single problem (a weather app, a fire map, a river gauge). MountainSentinel combines disaster warning, injured and lost-person search and wildlife monitoring on one map.
- **Explainable AI.** Every score comes with reasons and a recommended action, so authorities can trust and act on it. Physics-based rules and safety floors back up the ML where it is unsure.
- **Data fusion and compound risk.** Sensors, rain forecast, NASA satellite fire hotspots and camera flames are combined. For example, shaking on saturated soil raises landslide risk.
- **Lost-person pipeline.** Missed check-ins raise an alert with the last position and the danger level around it. A roaming camera sends GPS and a photo of any person it sees, and the system flags a possible match with the missing person.
- **Any webcam is a smart node.** Flame detection (colour plus flicker analysis), person, injury and animal detection run in the browser, so no special hardware is needed to try it.
- **Phone-first alerts.** Anyone can enter a mobile number and choose SMS or WhatsApp.
- **Honest and testable.** Hardware-agnostic API, 28 automated tests, clear labels for what is simulated, and a hardware roadmap.

**SHORT:** One explainable platform for disaster warning, injured and lost-person search and wildlife monitoring. It fuses sensors, forecast, satellite and camera data, detects compound risk, and turns any webcam or drone into a smart node. Every alert has reasons, and anyone can get SMS or WhatsApp alerts by entering a phone number.

---

## Technology Stack

**Languages:** Python 3.12 (backend and ML), JavaScript, HTML and CSS (dashboard and camera page), C++ / Arduino (reference ESP32 node firmware).

**Backend and frameworks:** FastAPI, Uvicorn, Pydantic, WebSocket (live updates), SQLite, Docker.

**AI / ML:** scikit-learn Random Forest models (landslide, flood, forest fire), NumPy, joblib; TensorFlow.js with COCO-SSD (people and animal detection in the browser); custom flame detector (colour and flicker analysis); centroid tracker for animal counting and movement.

**Frontend and browser APIs:** Leaflet with OpenTopoMap tiles, WebRTC camera access (getUserMedia), Geolocation API for roaming GPS.

**External APIs and services:** Open-Meteo (rain forecast), USGS Earthquake API, NASA FIRMS (satellite fire hotspots), Twilio (SMS and WhatsApp), Telegram Bot API.

**Tools:** pytest (28 tests), Git and GitHub, Docker.

**Hardware plan (future scope):** ESP32, LoRa, rain gauge, soil-moisture, MPU6050, BME280, smoke and ultrasonic sensors, solar power.

---

## GitHub / Source Code Link

https://github.com/YOUR-USERNAME/MountainSentinel

(Make the repository **public**, then open the link in a private browser window to check that it works.)

---

## Deployment Link (optional)

Leave it empty if you did not deploy. Only paste a link that really opens.
To deploy: docs/HOW_TO_RUN.md, step 12 (Render or Railway with the included Dockerfile).
