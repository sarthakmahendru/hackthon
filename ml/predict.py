"""Load the trained hazard models and score one reading."""
import json
import logging

import joblib
import numpy as np

from ml.features import FEATURES, ML_HAZARDS, to_vector
from ml.train import METRICS_PATH, MODEL_PATH, train

log = logging.getLogger("mountainsentinel.ml")


class HazardModels:
    def __init__(self):
        self.models = {}
        self.metrics = None

    @property
    def available(self) -> bool:
        return bool(self.models)

    def load(self, auto_train: bool = True) -> "HazardModels":
        try:
            bundle = joblib.load(MODEL_PATH)
            if bundle.get("features") != FEATURES:
                raise ValueError("feature list changed")
            self.models = bundle["models"]
        except Exception as exc:  # missing file, sklearn version change, etc.
            log.warning("Could not load models (%s).", exc)
            if not auto_train:
                return self
            log.info("Training models now (takes a few seconds)...")
            train(verbose=False)
            self.models = joblib.load(MODEL_PATH)["models"]
        try:
            self.metrics = json.loads(METRICS_PATH.read_text())
        except Exception:
            self.metrics = None
        return self

    def predict(self, features: dict) -> dict:
        """Return {hazard: probability 0..1}. Empty dict if models are unavailable."""
        if not self.models:
            return {}
        x = np.array([to_vector(features)])
        return {h: float(self.models[h].predict_proba(x)[0, 1]) for h in ML_HAZARDS if h in self.models}
