# Judging criteria and where the project answers them

No one can promise first place. This maps your project to what the jury scores, so you can show each point.

| Criterion | What to show | Where |
|---|---|---|
| **Innovation and originality** | Multi-hazard, explainable, fuses sensors + camera + satellite + forecast; lost-hiker link to hazard map | Dashboard reasons; README |
| **Problem-solving approach** | Physics (Caine threshold) + ML + safety floors; compound hazard (quake on wet soil); alerts only on escalation | `backend/risk_engine.py` |
| **Technical implementation** | FastAPI, WebSocket, SQLite, scikit-learn, TensorFlow.js, Twilio; 24 tests; Docker | Repo, `pytest` |
| **Functionality and execution** | Click a scenario, watch it react live; camera alert with photo; message on phone | Live demo |
| **User experience** | One map, colours, reasons in plain language, recommended action, mobile friendly | Dashboard |
| **Real-world impact** | Communities, forest dept, trekkers; works with any sensor via a simple API | Pitch |
| **Scalability and future potential** | LoRa nodes, PostgreSQL, MQTT, per-region calibration, OTP sign-up | README roadmap |

## Things that lose points (avoid them)

* Claiming things you did not build (real hardware, earthquake prediction, real-world AI accuracy).
* A demo that fails on the day: rehearse it 3 times and keep a video backup.
* A messy README or empty GitHub history.
* Submitting in the last 10 minutes.
* Not being able to explain your own code.

## Repository checklist

- [ ] Public repo, clear README with screenshots
- [ ] Many small, honest commits
- [ ] `.env` not committed
- [ ] Tests pass (`python -m pytest`)
- [ ] Demo video (2 minutes) linked in the README
- [ ] Team names and roles listed
