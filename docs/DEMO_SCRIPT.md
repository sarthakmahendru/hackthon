# Demo script and backup plan

## Before the demo (10 minutes before)

1. Start the server (`run.bat`). Open http://localhost:8000 and check "Live" in the top bar.
2. Open http://localhost:8000/camera.html in a second tab. Press Start camera and Allow. Turn on AI person detection (needs internet). Stop the camera until you need it if you want to save the surprise.
3. Add your own phone number in "Get alerts on your phone" (Twilio set up: real messages; otherwise the message log shows the demo).
4. Click **Reset everything**.
5. Close other apps that use the camera (Zoom, Teams).
6. Record a 2-minute screen video of the whole flow. This is your backup and your submission video.

## The 2-minute flow

| Time | Action | Say |
|---|---|---|
| 0:00 | Show the map, all green | "Six solar nodes. All normal." |
| 0:10 | Click **Landslide at Joshimath** | "We simulate a storm on an unstable slope." |
| 0:25 | Node turns orange, banner appears | "First warning. Watch the reasons." |
| 0:40 | Click the node, show reasons | "Rain above the Caine threshold, soil 90% saturated, tilt rising. It also tells people what to do." |
| 0:55 | Show alert and phone message | "The alert is already on my phone." |
| 1:05 | Click **Earthquake near Joshimath** | "Now shaking on a wet slope. Landslide risk goes up: compound hazard." |
| 1:20 | Camera tab: show a flame | "A camera is a node too. Flames detected, photo attached." |
| 1:40 | Back to dashboard: camera alert with photo | "Sensors and camera agree, so the fire score rises." |
| 1:50 | Click **Trek group A goes silent** (start this earlier if you want it to fire during the talk) | "Missed check-in, alert with last position." |
| 2:00 | Close | "Warn early, explain why, reach every phone." |

## If something goes wrong

| Problem | Do this |
|---|---|
| Wi-Fi is bad, map is grey | Say "map tiles need internet". Sensors and alerts still work. Use your phone hotspot. |
| Camera will not start | Use **Send test flames** on the camera page, and say clearly it is a test. |
| Flame is not detected | Use a fire video on a phone at full brightness, or the test button. |
| Server crashed | Restart `run.bat`. Show the backup video meanwhile. |
| Twilio message does not arrive | Show the "Message log" and say what the message contains. Trial accounts only reach verified numbers. |

## Optional extra segment (60 seconds): search and wildlife

| Action | Say |
|---|---|
| Click **Trek group A goes silent**, then **Drone finds the missing group** (the drone needs about a minute) | "A group stops checking in. A patrol drone flies out and photographs a group near their last position." |
| Point to the "Possible match" alert and the photo on the map | "The photo and the GPS position go straight to the rescuers. The photo in this demo is simulated." |
| Click **Injured trekker on trail** | "The camera AI sees a person lying still and sends the photo and position." |
| Click **Elephant herd near Nainital**, then show the Wildlife table | "It counts each species and tracks how they move, on its own." |
