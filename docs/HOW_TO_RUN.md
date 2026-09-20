# How to run MountainSentinel (step by step)

Written for Windows. Mac and Linux users: the same steps work, but use `./run.sh` instead of `run.bat`.
Time needed: about 10 minutes.

---

## Step 1. Install Python (once)

1. Go to https://www.python.org/downloads/ and download Python 3.10, 3.11 or 3.12.
2. Run the installer. **Tick the box "Add python.exe to PATH"** at the bottom of the first screen, then click Install.
3. Check it worked. Open the Start menu, type `cmd`, press Enter, and type:
   ```
   python --version
   ```
   You should see something like `Python 3.12.x`.

## Step 2. Open the project folder in a terminal

1. Unzip `MountainSentinel.zip`. You get a folder called `MountainSentinel`.
2. Open the folder in File Explorer. Click the address bar at the top, type `cmd`, press Enter.
   A black terminal window opens **inside the project folder**.
   (If you use VS Code: File, Open Folder, choose `MountainSentinel`, then Terminal, New Terminal.)

## Step 3. Start it

In the terminal, type:

```
run.bat
```

The first time it creates a private Python environment and installs the libraries (2 to 4 minutes).
It also trains the machine-learning models automatically (about 10 seconds).
Wait until you see this line:

```
Uvicorn running on http://0.0.0.0:8000
```

**Leave this window open.** Closing it stops the system.

Prefer typing the commands yourself? Run these one by one:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --port 8000
```

## Step 4. Open the dashboard

Open Chrome or Edge and go to:

**http://localhost:8000**

You should see a map of Uttarakhand with 6 green circles (the sensor nodes) and "Live" in the top bar.
Click a circle to see its sensors, its risk per hazard, and the reasons.

## Step 5. Show a disaster (the main demo)

In the right panel, scroll to **Simulate an event** and click **Landslide at Joshimath**.

What you will see over the next 30 seconds:
1. The Joshimath circle turns yellow, then orange, then red and starts pulsing.
2. A banner appears at the top of the map.
3. The panel explains why: rainfall above the Caine threshold, saturated soil, ground tilt.
4. An alert appears in the Alerts list (and on your phone, see steps 7 and 8).

Try the other buttons: flash flood, forest fire, earthquake, and "Trek group A goes silent"
(an alert about the missing hikers appears after 40 seconds). Also try **Drone finds the missing group**,
**Injured trekker on trail** and **Elephant herd near Nainital**. Watch the **Sightings and photos** and **Wildlife** panels. Click **Reset everything** to start again.

## Step 6. Use your laptop camera

1. Keep the dashboard open. Open a **second browser tab** and go to:
   **http://localhost:8000/camera.html**
   (Or click "Open the camera node" in the dashboard.)
2. Click **Start camera**. When the browser asks, click **Allow**.
   The camera only works on `localhost` or `https`. That is why you must use `localhost`.
3. Flame detection works straight away and needs no internet.
   Show a lit candle or lighter to the camera, or play a fire video on your phone and hold it up.
   The "Flames" meter rises. Above 50% a **critical alert with a photo** appears on the dashboard,
   and a camera icon turns red on the map.
4. For people detection click **Turn on AI person detection**. It downloads a small AI model
   (needs internet once). Then stand in front of the camera: a blue box appears and the dashboard raises an alert.
5. No flame handy? Use **Send test flames** or **Send test person**. They are labelled `(TEST)`. Tell the judges they are tests.

Tips: good light helps. Do not point the camera at a bright orange wall or a lamp; the detector also
checks flicker, so a still orange object is ignored, but a flickering lamp may trigger it.

Camera does not start?
- "Blocked": click the camera icon in the address bar and choose Allow.
- "Another app is using the camera": close Zoom, Teams, or the Windows Camera app.
- Windows privacy: Settings, Privacy and security, Camera, allow desktop apps.

### Step 6b. Injured people, animals and lost people with the camera

Turn on **Turn on AI (people and animals)** first (needs internet once).

- **Injured person:** lie on the floor in view of the camera and stay still for 5 seconds. The box turns red and the dashboard shows an alert with a photo.
- **Animals:** hold up a phone showing a video of an elephant, cow, horse, sheep, dog or bird. The page counts each species and tracks its movement. The dashboard **Wildlife** table fills up.
- **Lost people (roaming):** tick **Roaming** on the camera page. The position now follows your GPS, and every person sighting is sent with a photo and the position. To try it outdoors, open the camera page on a phone (it needs `https`, so use a deployed link or a tunnel such as ngrok). If a hiker is missing within 5 km, the dashboard raises a "possible match" alert.
- No animals or injured people handy? Use the **Send test animals** and **Send test injured person** buttons. They are labelled TEST.

## Step 7. Enter your phone number

1. In the dashboard right panel find **Get alerts on your phone**.
2. Type your name and your mobile number. You can type it as `98765 43210` (the system adds +91)
   or with the country code `+91 98765 43210`. Any country works with the `+` code.
3. Choose **SMS** or **WhatsApp**, and choose **Warning and Critical** or **Critical only**.
4. Tick "This is my number and I want mountain alerts on it" and click **Send me alerts**.
5. Click **Send test** next to your number.

Without Twilio keys (the default) nothing is sent. The message appears in the **Message log** with the label
"Demo, not sent". That is enough to show the flow in a demo. To really receive messages, do step 8.

Your number is stored only in the local database file `data/mountainsentinel.db`, and it is shown masked
(`+91•••••••210`) everywhere in the app. Click **Remove** to delete it.

## Step 8. Make phone alerts real (Twilio, about 10 minutes)

Twilio gives free trial credit. Trial accounts can only message numbers you have **verified**.

1. Sign up at https://www.twilio.com/try-twilio and verify your own phone number.
2. In the Twilio Console copy your **Account SID** and **Auth Token**.
3. **For SMS:** get a trial phone number (Console, Phone Numbers, Get a number). Copy it (looks like `+1555...`).
   Note: some countries, including India, restrict SMS from trial numbers. If SMS does not arrive, use WhatsApp.
4. **For WhatsApp (works well for demos):** Console, Messaging, Try it out, Send a WhatsApp message.
   From your phone, send the shown "join ..." word to the Twilio sandbox WhatsApp number once.
5. In the project folder copy `.env.example` to a new file called `.env` (in File Explorer: copy, paste, rename to `.env`).
   Open `.env` in Notepad and fill in:
   ```
   TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   TWILIO_AUTH_TOKEN=your_auth_token
   TWILIO_SMS_FROM=+15551234567
   TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
   ```
6. Stop the server (Ctrl+C in the terminal) and start it again with `run.bat`.
7. In the dashboard, "Data sources" now shows **Phone alerts (Twilio): live**. Add your number and press **Send test**.

Never put your Auth Token in GitHub. `.env` is already in `.gitignore`.

## Step 9. Telegram alerts (free, optional)

1. In Telegram, message **@BotFather**, send `/newbot`, follow the steps, copy the **token**.
2. Send any message to your new bot. Then open this address in a browser (put your token in):
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
   and copy the number after `"chat":{"id":`.
3. Put both in `.env`:
   ```
   TELEGRAM_BOT_TOKEN=123456:ABC...
   TELEGRAM_CHAT_ID=987654321
   ```
4. Restart the server. Alerts now also arrive in Telegram.

## Step 10. Real live data (free, optional)

The system already tries to read the **rain forecast (Open-Meteo)** and **recent earthquakes (USGS)**. No key needed.
They need internet. For **NASA satellite fire hotspots** get a free key at
https://firms.modaps.eosdis.nasa.gov/api/map_key/ and add `FIRMS_MAP_KEY=...` to `.env`.
The dashboard "Data sources" list shows which feeds are live.

## Step 11. Put it on GitHub (required for submission)

1. Create a free account at https://github.com and create a **new repository** named `MountainSentinel` (public).
2. Install Git from https://git-scm.com/download/win.
3. In the project terminal:
   ```
   git init
   git add .
   git commit -m "Initial version of MountainSentinel"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/MountainSentinel.git
   git push -u origin main
   ```
4. Make **small commits as you really work** (`git add .` then `git commit -m "what you changed"` then `git push`).
   The jury may look at the history. Do not fake it.
5. Add 2 or 3 screenshots to `docs/screenshots/` and mention them in the README.

## Step 12. Optional: a public demo link

Full guide: [docs/DEPLOY.md](DEPLOY.md). Short version: push to GitHub, then create a free **Docker Web Service** on https://render.com from your repository (the project includes a `Dockerfile` and `render.yaml`). Render gives you an `https` link, which also makes the camera work on phones. Do not put Twilio keys on the public site.

## Step 13. Run the tests

```
.venv\Scripts\activate
python -m pytest
```
All 28 tests should pass.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `'python' is not recognized` | Reinstall Python and tick "Add python.exe to PATH". Close and reopen the terminal. |
| `run.bat` closes immediately | Open `cmd` in the folder and run it there, so you can read the error. |
| `pip install` fails on scikit-learn | Use Python 3.10 to 3.12 (very new Python versions may lack ready-made packages). |
| Port 8000 already in use | Start with another port: `uvicorn backend.main:app --port 8001` and open `http://localhost:8001`. |
| Map is grey | No internet: the map tiles come from the internet. Sensors and alerts still work. Use a phone hotspot. |
| Dashboard says "Reconnecting…" | The server stopped. Check the terminal window. |
| Camera button does nothing | Use `http://localhost:8000/camera.html` (not your network IP address). |
| No phone messages | Check "Data sources": if it says "demo mode" the Twilio keys are missing (step 8). Trial accounts only reach verified numbers. |
| I want a clean start | Stop the server and delete the file `data\mountainsentinel.db`. |
