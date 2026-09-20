# Pitch script (3 minutes) and slide outline

Speak slowly. Show the live dashboard as soon as you can. Judges remember what they see.

## The script

**0:00 The problem (20 s)**
"In the Himalayas, a landslide, a flash flood or a forest fire can start in minutes. Many of these places have no monitoring, no mobile network, and warnings arrive too late. And when a trekker gets lost in the forest, nobody knows until it is too late."

**0:20 The solution (20 s)**
"We built MountainSentinel: low-cost solar sensor nodes, an AI risk engine, and instant alerts to the phones of the people who need them. It explains why it is worried, and what to do."

**0:40 Live demo: landslide (60 s)**
Open the dashboard. "Six sensor nodes across Uttarakhand. All green." Click **Landslide at Joshimath**.
"Rain is building, soil is saturating, and the ground starts to tilt. Watch the node." (Wait for orange, then red.)
Click the node. "It does not just say danger. It says: rainfall is above the global landslide threshold, soil is 92% saturated, the slope is moving, and it tells the authority to evacuate below the slope."
Point to the message log or your phone. "This alert has just reached my phone."

**1:40 Camera and compound risk (40 s)**
Switch to the camera tab. Show a flame (candle or phone video). "Any laptop or a cheap camera can be a node. It detects flames and people, and sends a photo." Show the alert with the photo on the dashboard.
"It also fuses data: if a satellite hotspot, a camera or a shaking sensor agrees, the risk rises. An earthquake on wet soil raises landslide risk."

**2:20 Lost hiker (15 s)**
"Hikers check in. Trek group A stops. After 40 seconds the system alerts rescuers, gives the last known position, and tells them the area around it is unsafe."

**2:35 Honesty and future (25 s)**
"The sensors in this demo are simulated. The API is the same one real ESP32 and LoRa hardware will use, so the next step is building three real nodes and calibrating with one district's data. The machine learning is trained on physically informed synthetic data, and we say so. Rules and safety floors protect us where ML is unsure. We cannot predict earthquakes. We detect shaking and its effects."

**3:00 Close**
"MountainSentinel: warn early, explain why, reach every phone."

## Slide outline (if you make a PPT)

1. Title and one-line promise
2. The problem (one striking fact you verified, one image)
3. Solution overview (architecture diagram from the README)
4. Live demo screenshot: map with red node + reasons
5. How the risk engine works (physics + ML + context) and why it is explainable
6. Camera node and phone alerts (screenshots)
7. What is real vs simulated (build trust)
8. Impact and users: villages, forest department, disaster authorities, trekking operators
9. Scalability and business model: low cost per node, SaaS for districts, sensor kits
10. Roadmap and team

Verify any fact or figure you quote (for example past disasters). Do not quote numbers you cannot source.
