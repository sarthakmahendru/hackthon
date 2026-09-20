"""Train the hazard models.

    python -m ml.train

WHAT THIS IS (and is not)
-------------------------
We do not have years of labelled landslide / flood / fire sensor data, and nobody
can collect that in a 24-hour hackathon. So the training set is SYNTHETIC but
physically informed:

  * Landslide: driven by rainfall vs. the Caine (1980) intensity-duration threshold,
    soil saturation, ground tilt and tilt speed, with a rain x soil interaction
    (rain on already-wet soil is far more dangerous than rain on dry soil).
  * Flash flood: stream level, how fast it is rising, and rainfall, with interaction.
  * Forest fire: smoke, heat and dryness, with interaction.

Labels are sampled from a noisy logistic function, not a hard rule, so the model has
to learn a probability surface instead of memorising thresholds. The reported metrics
therefore show the model learned those relationships. They are NOT real-world accuracy.
In production the same pipeline is retrained on real historical events
(e.g. NASA Global Landslide Catalog, IMD rainfall, CWC river gauges, FIRMS fire history).
"""
import json
import time
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split

from ml.features import FEATURES, ML_HAZARDS

MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_PATH = MODEL_DIR / "hazard_models.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"

CAINE_1H_MM = 14.82  # Caine (1980): I = 14.82 * D^-0.39 (mm/h), D = 1 h
CAINE_24H_MM = 14.82 * 24 ** -0.39 * 24  # about 103 mm over 24 h


def _ramp(x, lo, hi):
    return np.clip((x - lo) / (hi - lo), 0.0, 1.0)


def _sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def sample_features(rng: np.random.Generator, n: int) -> dict:
    """Draw plausible sensor conditions: mostly calm, with stormy / hot / unstable spells."""
    wet = rng.random(n) < 0.40
    stress = rng.random(n) < 0.35
    hot = rng.random(n) < 0.30
    quake = rng.random(n) < 0.05

    rain_1h = np.where(wet, rng.gamma(2.0, 7.0, n), rng.gamma(0.6, 1.0, n))
    rain_24h = rain_1h * rng.uniform(1.5, 8.0, n) + np.where(
        wet, rng.gamma(2.0, 20.0, n), rng.gamma(1.0, 3.0, n)
    )
    soil = np.clip(np.where(wet, rng.normal(72, 14, n), rng.normal(38, 12, n)), 5, 100)
    tilt = np.where(stress, rng.gamma(2.0, 1.0, n), rng.gamma(1.2, 0.15, n))
    tilt_trend = np.where(stress, rng.gamma(1.5, 0.2, n), np.abs(rng.normal(0, 0.03, n)))
    vibration = np.where(quake, rng.gamma(2.0, 0.03, n), np.abs(rng.normal(0.001, 0.0008, n)))
    temp = np.where(hot, rng.normal(38, 6, n), rng.normal(18, 7, n))
    humidity = np.clip(np.where(hot, rng.normal(25, 12, n), rng.normal(65, 18, n)), 5, 100)
    smoke = np.where(hot & (rng.random(n) < 0.4), rng.gamma(2.0, 80.0, n), np.abs(rng.normal(12, 8, n)))
    water = np.clip(np.where(wet, rng.normal(150, 60, n), rng.normal(60, 15, n)), 10, 600)
    water_trend = np.where(wet, rng.normal(10, 12, n), rng.normal(0, 2, n))

    return {
        "rain_1h_mm": rain_1h,
        "rain_24h_mm": rain_24h,
        "soil_moisture_pct": soil,
        "tilt_deg": tilt,
        "tilt_trend": tilt_trend,
        "vibration_g": vibration,
        "temperature_c": temp,
        "humidity_pct": humidity,
        "smoke_ppm": smoke,
        "water_level_cm": water,
        "water_trend": water_trend,
    }


def sample_labels(rng: np.random.Generator, f: dict) -> dict:
    """Noisy logistic ground truth per hazard (see module docstring)."""
    n = len(f["rain_1h_mm"])

    r = np.maximum(f["rain_1h_mm"] / CAINE_1H_MM, f["rain_24h_mm"] / CAINE_24H_MM)
    s = _ramp(f["soil_moisture_pct"], 50, 95)
    t = _ramp(f["tilt_deg"], 0.3, 4.0)
    tt = _ramp(f["tilt_trend"], 0.0, 0.6)
    quake_boost = 1.5 * _ramp(f["vibration_g"], 0.02, 0.1) * s
    z_land = -5.0 + 3.0 * r + 2.5 * s + 2.0 * t + 1.5 * tt + 3.0 * r * s + quake_boost
    z_land += rng.normal(0, 0.5, n)

    w = _ramp(f["water_level_cm"], 70, 250)
    wt = _ramp(f["water_trend"], 0, 30)
    rr = _ramp(f["rain_1h_mm"], 5, 50)
    z_flood = -5.0 + 3.5 * w + 2.5 * wt + 2.0 * rr + 2.0 * w * rr
    z_flood += rng.normal(0, 0.5, n)

    sm = _ramp(f["smoke_ppm"], 30, 300)
    tp = _ramp(f["temperature_c"], 25, 48)
    dr = 1.0 - _ramp(f["humidity_pct"], 10, 60)
    z_fire = -5.5 + 4.0 * sm + 1.5 * tp + 1.5 * dr + 2.5 * sm * dr
    z_fire += rng.normal(0, 0.5, n)

    return {
        "landslide": (rng.random(n) < _sigmoid(z_land)).astype(int),
        "flood": (rng.random(n) < _sigmoid(z_flood)).astype(int),
        "wildfire": (rng.random(n) < _sigmoid(z_fire)).astype(int),
    }


def train(n_samples: int = 15000, seed: int = 42, verbose: bool = True) -> dict:
    rng = np.random.default_rng(seed)
    feats = sample_features(rng, n_samples)
    labels = sample_labels(rng, feats)
    X = np.column_stack([feats[name] for name in FEATURES])

    models, metrics = {}, {
        "note": "Synthetic, physically-informed training data. Metrics show the model learned "
        "the hazard relationships; they are not real-world accuracy.",
        "n_samples": n_samples,
        "trained_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hazards": {},
    }

    for hazard in ML_HAZARDS:
        y = labels[hazard]
        X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.2, random_state=seed, stratify=y)
        clf = RandomForestClassifier(
            n_estimators=80,
            max_depth=9,
            min_samples_leaf=10,
            n_jobs=-1,
            random_state=seed,
        )
        clf.fit(X_tr, y_tr)
        proba = clf.predict_proba(X_te)[:, 1]
        pred = (proba >= 0.5).astype(int)
        top = sorted(zip(FEATURES, clf.feature_importances_), key=lambda kv: -kv[1])[:4]
        metrics["hazards"][hazard] = {
            "positive_rate": round(float(y.mean()), 3),
            "roc_auc": round(float(roc_auc_score(y_te, proba)), 3),
            "accuracy": round(float(accuracy_score(y_te, pred)), 3),
            "precision": round(float(precision_score(y_te, pred)), 3),
            "recall": round(float(recall_score(y_te, pred)), 3),
            "f1": round(float(f1_score(y_te, pred)), 3),
            "top_features": [{"feature": k, "importance": round(float(v), 3)} for k, v in top],
        }
        clf.n_jobs = 1
        models[hazard] = clf
        if verbose:
            m = metrics["hazards"][hazard]
            print(f"{hazard:9s} AUC={m['roc_auc']}  acc={m['accuracy']}  P={m['precision']}  R={m['recall']}")

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump({"models": models, "features": FEATURES}, MODEL_PATH, compress=3)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    if verbose:
        print(f"Saved {MODEL_PATH.name} and {METRICS_PATH.name}")
    return metrics


if __name__ == "__main__":
    train()
