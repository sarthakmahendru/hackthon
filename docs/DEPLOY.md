# Deploy MountainSentinel and get a public link

## What the links mean

* **GitHub / Source Code link** = your repository, for example `https://github.com/YOUR-USERNAME/MountainSentinel`. It exists as soon as you push your code (step A).
* **Deployment link** = a running website judges can open. GitHub itself cannot run this project: **GitHub Pages only hosts static pages**, and MountainSentinel needs a Python server with WebSockets. So you deploy the repo on a hosting service (step B).

## A. Put the code on GitHub

1. Create a free account at https://github.com and click **New repository**. Name it `MountainSentinel`, choose **Public**, and do not add a README (you already have one).
2. Install Git (https://git-scm.com/download/win).
3. In the project folder (open `cmd` there):
   ```
   git init
   git add .
   git commit -m "MountainSentinel: first version"
   git branch -M main
   git remote add origin https://github.com/YOUR-USERNAME/MountainSentinel.git
   git push -u origin main
   ```
4. When Git asks you to sign in, a browser window opens. GitHub no longer accepts your account password on the command line, so sign in through that window, or install **GitHub Desktop** and use it instead.
5. Open the repository URL in a private browser window to check that it is public. Confirm that `.env` is **not** in the file list.

## B. Deploy on Render (free, recommended)

1. Go to https://render.com and sign up with your GitHub account.
2. Click **New > Web Service** and choose your `MountainSentinel` repository. (Or **New > Blueprint**, which reads the `render.yaml` in this project.)
3. Settings: **Runtime: Docker**. **Instance type: Free**. Render finds the Dockerfile by itself.
4. Under **Environment variables** add `SIMULATE` = `true` and `USE_LIVE_DATA` = `true`. Do **not** add Twilio keys (see the warning below).
5. Click **Create Web Service**. The first build takes a few minutes (it installs the libraries and trains the models).
6. When the log says the service is live, open the URL Render shows at the top, like `https://mountainsentinel-xxxx.onrender.com`. **That is your Deployment link.**
7. Check that it works: the map loads, the top bar says "Live", and **Landslide at Joshimath** turns a node red. Open `/camera.html` on the same address. The camera works because the link is `https`.

Things to know about the free plan:
* The service **falls asleep** after about 15 minutes without visitors, and wakes in about a minute. Open the link 5 minutes before judges might look, and again before your demo.
* The database file is wiped on every deploy or restart. That is fine for a demo.
* Free instances have limited memory. If the build or start fails with a memory error, check the logs and try again, or use another host below.

## Other ways to get a link

| Option | Good for | Notes |
|---|---|---|
| **Railway** (railway.app) | Easy Docker deploys | Trial credit only, then paid. New Project > Deploy from GitHub repo. |
| **Hugging Face Spaces** (Docker Space) | Free, no sleep for a while | Needs `app_port: 7860` in a README header and the app to listen on 7860. |
| **ngrok tunnel from your laptop** | A demo in the next 5 minutes | Run the app, then `ngrok http 8000`. You get an `https` link that works only while your laptop and the app are running. Camera and GPS work on phones through it. |
| **GitHub Codespaces** | A temporary link without another account | Open the repo in a Codespace, run `run.sh`, and in the Ports tab set port 8000 to **Public**. The link works only while the Codespace runs. |

For the form, a permanent Render link is best. A tunnel link is fine for a live demo but stops working when you close your laptop.

## Safety warning for a public deployment

* **Do not put your Twilio keys on the public site.** Anyone could type any phone number into the form and make your account send messages to them. Leave Twilio empty so the site stays in demo mode ("Demo, not sent"). Show real SMS only in your local demo.
* Anyone can also post readings to a public site. For a demo that is fine. To lock it, set `INGEST_API_KEY` in Render, and type the same key into the camera page ("Server needs a key?").
* Never commit `.env` or any key to GitHub.

## Update the site after a change

```
git add .
git commit -m "what you changed"
git push
```
Render redeploys by itself after every push.

## If something fails

| Problem | Fix |
|---|---|
| Build fails | Open the **Logs** tab in Render and read the last red lines. Check that `requirements.txt` and `Dockerfile` are at the top level of the repo. |
| "Application failed to respond" | The app must listen on the port in `$PORT`. The Dockerfile already does this. Check the logs for a Python error. |
| Map is grey | Map tiles need the visitor's internet. Sensors and alerts still work. |
| Camera does not start | Use the `https` link, click **Allow**, and close other apps that use the camera. |
| Very slow first load | The free instance was asleep. Wait a minute. |
