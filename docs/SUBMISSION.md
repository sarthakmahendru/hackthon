# Submission form: ready to paste

The Google Form has more questions (problem, solution, uniqueness, tech stack). Those answers are in **docs/FORM_ANSWERS.md**.

The form asks for: Project Title, Project Description, GitHub Repository Link. Deployment link and PPT are optional.

## Project title

MountainSentinel: AI Early-Warning System for Mountain Disasters

## Project description (long version, about 230 words)

MountainSentinel is an AI-powered early-warning platform for mountain regions that face landslides, flash floods, forest fires, ground shaking and lost hikers, often in places with no monitoring at all.

Low-cost solar sensor nodes measure rainfall, soil moisture, ground tilt, vibration, temperature, smoke and stream level, and stream the data to our FastAPI backend. A hybrid risk engine combines physics-based rules (including the Caine 1980 global rainfall threshold for landslides) with Random Forest models and live context, and outputs a 0 to 100 risk score, a level (Normal, Watch, Warning, Critical), the reasons in plain language, and a recommended action. It links hazards: shaking on wet soil raises landslide risk, and a rain forecast or NASA satellite fire hotspot raises the score before conditions worsen.

A live map dashboard shows every node in real time. Any laptop webcam can act as a camera node that detects flames (colour plus flicker analysis) and people (TensorFlow.js) and sends a photo alert. Hikers check in, and a missed check-in raises an alert with the last position and the danger level around it. Anyone can enter a mobile number to receive SMS or WhatsApp alerts (Twilio), and alerts also go to Telegram.

The demo uses a simulated sensor network; the same API accepts real ESP32 and LoRa hardware. We include 24 automated tests, Docker support and a clear hardware roadmap.

## Short version (about 60 words)

MountainSentinel warns mountain communities before landslides, floods and forest fires. Solar sensors and a laptop camera feed a hybrid physics-and-AI risk engine that explains every score. A live map shows risk in real time, and residents get SMS, WhatsApp or Telegram alerts. Lost hikers trigger alerts when they miss check-ins. Built with FastAPI, scikit-learn, Leaflet and TensorFlow.js.

## Tech stack

Python, FastAPI, WebSocket, scikit-learn (Random Forest), SQLite, Leaflet, TensorFlow.js (COCO-SSD), Twilio, Telegram Bot API, Open-Meteo, USGS, NASA FIRMS, Docker, pytest.

## GitHub link

https://github.com/YOUR-USERNAME/MountainSentinel   (replace with yours)

## Optional fields

* Live demo link: deploy with Docker on Render or Railway (docs/HOW_TO_RUN.md, step 12), or leave empty.
* PPT: use docs/PITCH_SCRIPT.md (slide outline at the bottom).

## Before you press submit

- [ ] Repository is **public** and the link opens in a private browser window
- [ ] README renders, with 2 or 3 screenshots in `docs/screenshots/`
- [ ] Your team names are in the README
- [ ] `.env` is NOT in the repo (only `.env.example`)
- [ ] You have pushed your latest commit
- [ ] You submitted at least 1 hour before the deadline
