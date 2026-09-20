# Judge questions and honest answers

Learn the ideas, not the exact words. Be honest: judges respect it, and they can check the GitHub repo.

**Is the data real?**
The sensors in the demo are simulated, and we say so. The API is the same one real hardware uses. The live parts are real: Open-Meteo rain forecast, USGS earthquakes, NASA FIRMS fires, and the laptop camera.

**Is the AI model accurate?**
It is trained on synthetic, physically informed data, so the metrics (AUC about 0.91 to 0.96) only show it learned the relationships we encoded. We do not claim real-world accuracy. The rule layer, based on published thresholds, and the override floors are the safety net. With real deployment we retrain on real event history.

**Then why use ML at all?**
Rules are cliff-edges. ML gives a smooth probability and captures interactions such as rain on saturated soil. The hybrid is more explainable than pure ML and more flexible than pure rules.

**Can you predict earthquakes?**
No, nobody can. We detect shaking as it happens (seconds of warning at best, mainly for follow-up hazards) and connect it to landslide risk on wet slopes.

**Where does the 15 mm / 103 mm threshold come from?**
Caine (1980), a widely cited global rainfall intensity-duration threshold for shallow landslides: I = 14.82 D^-0.39. It must be calibrated for each region, which is part of the roadmap.

**How would it work with no mobile network?**
Nodes send data over LoRa to a gateway, which has a link to the server (satellite or a village with connectivity). Our backend only needs the reading in JSON. See docs/HARDWARE_FUTURE_SCOPE.md.

**How does the camera detect fire?**
Two steps in the browser: find flame-coloured pixels (bright orange to yellow, strongly saturated), then check that the region flickers between frames. A still orange object is ignored. It is a heuristic and can be fooled by a flickering orange lamp. Production: a YOLO model trained on fire and smoke.

**What about false alarms?**
Multiple layers: the score needs several signals (for example rain and soil and tilt), alerts fire only on escalation to Warning or Critical with a cooldown, camera events need sustained detection, and phone alerts go only to people who chose a level. Real false-alarm rates need field data.

**Is entering a phone number safe?**
Numbers are validated, stored locally, masked in every response, and removable. In the prototype anyone could subscribe someone else's number. A production version must confirm ownership with a one-time code (OTP) and rate-limit. We list this as a known limitation.

**Who pays and who uses it?**
Users: forest departments, disaster authorities, trekking operators, hill villages. The hardware is low cost (a few thousand rupees per node, to be verified with real quotes). Revenue: district subscriptions and sensor kits.

**How does it scale?**
Stateless API, one reading is a small JSON, SQLite can be swapped for PostgreSQL, and ingest can move to MQTT or LoRaWAN. The dashboard is WebSocket-driven.

**Did you build all of this in 24 hours?**
Answer truthfully about what you did yourself and which tools helped you (including AI assistance if you used it). Be ready to open any file and explain it.

**What would you do with one more week?**
Build three real nodes, collect real data in one district, retrain and calibrate, add OTP sign-up and a local-language voice alert.

**Can it really find injured people?**
It flags a person who is lying down and not moving for 5 seconds and sends a photo for a human to check. It cannot diagnose injury. Someone resting can trigger it, which is why the alert says "possible". A pose model and thermal camera would improve it.

**Which animals can it count?**
The browser AI model (COCO-SSD) knows bird, cat, dog, horse, sheep, cow, elephant, bear, zebra and giraffe. Deer, leopards and tigers need a custom model, for example trained on camera-trap images. The counts are approximate (each animal is tracked between frames, but a group that leaves and returns can be counted twice).

**How does the roaming camera help find lost people?**
It sends its GPS position and a photo of any person it sees. If the sighting is within 5 km of a missing hiker's last position, the system raises a possible-match alert with the photo. In the demo the drone is simulated.
