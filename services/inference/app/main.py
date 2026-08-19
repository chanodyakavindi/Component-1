from __future__ import annotations

import hashlib
import time
from pathlib import Path

import numpy as np
import yaml
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

CONTRACTS = Path("/contracts") if Path("/contracts").exists() else Path(__file__).resolve().parents[3] / "packages" / "contracts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")
    model_mode: str = "demo"
    model_artifact_path: str = "/artifacts/active"
    embedding_dim: int = 128


settings = Settings()
app = FastAPI(title="CNIP Inference Service", version="0.1.0")


class PredictRequest(BaseModel):
    child_pseudonymous_id: str
    visit_number: int = 0
    visit_date: str | None = None
    anthropometric: dict = Field(default_factory=dict)
    socioeconomic: dict = Field(default_factory=dict)
    dietary: dict = Field(default_factory=dict)
    maternal_child_health: dict = Field(default_factory=dict)
    model_mode: str | None = None


class PredictionResult(BaseModel):
    status: str
    severity: str
    raw_probabilities: dict
    calibrated_probabilities: dict
    risk_score: float
    confidence: str
    latent_embedding: list[float]
    model_version: str
    calibration_version: str
    feature_schema_version: str
    inference_ms: float
    mode: str


DEMO_LOOKUP = {
    ("C-1042", 0): ("wasting", "severe", 0.82),
    ("C-1042", 1): ("wasting", "moderate", 0.61),
    ("C-1042", 2): ("wasting", "moderate", 0.59),
    ("C-1001", 0): ("underweight", "moderate", 0.74),
    ("C-1001", 1): ("underweight", "mild", 0.58),
    ("C-1001", 2): ("normal", "none", 0.41),
    ("C-1001", 3): ("normal", "none", 0.28),
    ("C-1002", 0): ("stunting", "mild", 0.38),
    ("C-1002", 1): ("stunting", "moderate", 0.47),
    ("C-1002", 2): ("stunting", "moderate", 0.62),
    ("C-1002", 3): ("wasting", "moderate", 0.71),
    ("C-1005", 0): ("wasting", "severe", 0.78),
    ("C-1005", 1): ("wasting", "moderate", 0.49),
    ("C-1005", 2): ("underweight", "mild", 0.33),
    ("C-1005", 3): ("wasting", "moderate", 0.58),
}


def _embedding(pid: str, visit_number: int, risk: float, dim: int) -> list[float]:
    seed = sum(ord(c) for c in pid) + visit_number * 17
    return [round(((seed * (i + 3)) % 1000) / 1000.0 - 0.5 + (1 - risk) * 0.2, 4) for i in range(dim)]


def _temperature_scale(prob: float, temperature: float = 1.2) -> float:
    # Simple calibration stand-in for the demo adapter.
    prob = min(max(prob, 1e-6), 1 - 1e-6)
    logit = np.log(prob / (1 - prob)) / temperature
    calibrated = 1 / (1 + np.exp(-logit))
    return float(np.clip(calibrated, 0.01, 0.99))


class DemoModelAdapter:
    name = "MCA-2026-001"

    def predict(self, req: PredictRequest) -> PredictionResult:
        t0 = time.perf_counter()
        key = (req.child_pseudonymous_id, req.visit_number)
        if key in DEMO_LOOKUP:
            status, severity, risk = DEMO_LOOKUP[key]
        else:
            status, severity, risk = self._from_measurements(req)
        raw_risk = min(0.99, risk + 0.03)
        calibrated = _temperature_scale(risk)
        # Keep seeded demo risks exact so the C-1042 narrative is reproducible.
        if key in DEMO_LOOKUP:
            calibrated = risk
        status_probs = {k: 0.08 for k in ("normal", "stunting", "wasting", "underweight")}
        status_probs[status] = max(0.55, calibrated)
        total = sum(status_probs.values())
        status_probs = {k: round(v / total, 4) for k, v in status_probs.items()}
        dim = settings.embedding_dim
        elapsed = (time.perf_counter() - t0) * 1000
        return PredictionResult(
            status=status,
            severity=severity,
            raw_probabilities={"status": status_probs, "risk": raw_risk},
            calibrated_probabilities={"status": status_probs, "risk": calibrated},
            risk_score=round(calibrated, 4),
            confidence="moderate",
            latent_embedding=_embedding(req.child_pseudonymous_id, req.visit_number, calibrated, dim),
            model_version=self.name,
            calibration_version="demo-temp-v1",
            feature_schema_version="fs-2026-001",
            inference_ms=round(elapsed, 2),
            mode="DEMO",
        )

    def _from_measurements(self, req: PredictRequest) -> tuple[str, str, float]:
        anthro = req.anthropometric
        diet = req.dietary
        mch = req.maternal_child_health
        weight = float(anthro.get("weight_kg") or 8)
        height = float(anthro.get("height_cm") or 70)
        muac = float(anthro.get("muac_cm") or 12)
        diversity = int(diet.get("dietary_diversity_score") or 3)
        diarrhoea = 1 if mch.get("recent_diarrhoea") else 0
        # Deterministic synthetic scoring — not a clinical rule.
        bmi_like = weight / ((height / 100) ** 2) if height else 14
        digest = hashlib.sha256(f"{req.child_pseudonymous_id}:{req.visit_number}:{weight}:{height}:{muac}".encode()).hexdigest()
        noise = int(digest[:4], 16) / 65535 * 0.04
        risk = 0.15 + max(0, (16 - bmi_like) * 0.06) + max(0, (12.5 - muac) * 0.05) + (4 - diversity) * 0.03 + diarrhoea * 0.08 + noise
        risk = float(np.clip(risk, 0.08, 0.92))
        if risk >= 0.75:
            return "wasting", "severe", risk
        if risk >= 0.55:
            return "wasting", "moderate", risk
        if risk >= 0.4:
            return "underweight", "mild", risk
        if risk >= 0.28:
            return "stunting", "mild", risk
        return "normal", "none", risk


class SklearnModelAdapter:
    def __init__(self, path: str):
        self.path = path
        self._model = None

    def predict(self, req: PredictRequest) -> PredictionResult:
        import joblib

        if self._model is None:
            self._model = joblib.load(self.path)
        raise HTTPException(503, "Sklearn adapter loaded but feature vector assembly from visit payload is not bound to a trained artifact yet")


class PyTorchMultimodalAdapter:
    def __init__(self, path: str):
        self.path = path
        self._model = None

    def predict(self, req: PredictRequest) -> PredictionResult:
        import torch
        from models.multimodal import MultimodalCrossAttention  # type: ignore  # noqa: I001

        if self._model is None:
            ckpt = torch.load(self.path, map_location="cpu")
            self._model = MultimodalCrossAttention.from_config(ckpt.get("config", {}))
            self._model.load_state_dict(ckpt["state_dict"])
            self._model.eval()
        # Feature tensors are assembled by the training pipeline schema.
        raise HTTPException(503, "PyTorch artifact is registered but live tensor assembly requires a trained checkpoint bound to MODEL_ARTIFACT_PATH")


class OnnxModelAdapter:
    def __init__(self, path: str):
        self.path = path

    def predict(self, req: PredictRequest) -> PredictionResult:
        raise HTTPException(503, "ONNX adapter has no active artifact")


def get_adapter():
    mode = settings.model_mode.lower()
    path = settings.model_artifact_path
    if mode == "sklearn":
        return SklearnModelAdapter(path)
    if mode == "pytorch":
        return PyTorchMultimodalAdapter(path)
    if mode == "onnx":
        return OnnxModelAdapter(path)
    return DemoModelAdapter()


ADAPTER = get_adapter()


@app.get("/health")
def health():
    return {"status": "ok", "service": "inference", "mode": settings.model_mode}


@app.get("/model-info")
def model_info():
    return {
        "mode": settings.model_mode,
        "adapter": ADAPTER.__class__.__name__,
        "model_version": getattr(ADAPTER, "name", settings.model_mode),
        "embedding_dim": settings.embedding_dim,
        "clinically_validated": False,
        "demo": settings.model_mode.lower() == "demo",
    }


@app.post("/predict", response_model=PredictionResult)
def predict(req: PredictRequest):
    return ADAPTER.predict(req)
