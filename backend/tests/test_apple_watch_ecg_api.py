from typing import Any

import numpy as np
import torch
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.lead1_ecg_runtime import Lead1EcgRuntime, TARGET_NAMES

client = TestClient(app)


class FakeRuntime:
    target_names = TARGET_NAMES
    target_samples = 5000
    sampling_rate_hz = 500.0
    duration_sec = 10.0

    def infer(
        self,
        waveform: Any,
        *,
        source_hz: float,
        window_policy: str,
        threshold: float,
    ) -> list[dict[str, Any]]:
        return [
            {
                "window_index": 0,
                "window_start_sample": 0,
                "window_end_sample": min(len(waveform), self.target_samples),
                "window_duration_sec": self.duration_sec,
                "window_target_samples": self.target_samples,
                "prob_any_abnormal": 0.6,
                "pred_any_abnormal": threshold <= 0.6,
                "labels_above_threshold": ["other_abnormal"],
                "probabilities": {
                    "normal_or_sinus_reference": 0.4,
                    "atrial_fibrillation_or_flutter": 0.2,
                    "bradycardia_or_tachycardia": 0.3,
                    "other_abnormal": 0.6,
                },
            }
        ]


class FakeModel(torch.nn.Module):
    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        batch_size = x.shape[0]
        return torch.zeros((batch_size, len(TARGET_NAMES))), torch.zeros((batch_size, 1))


def ecg_record(*, heart_rate: int = 66, sample_count: int = 8) -> dict[str, Any]:
    return {
        "start": "2026-05-17T10:00:00Z",
        "end": "2026-05-17T10:00:30Z",
        "classification": "Sinus Rhythm",
        "averageHeartRate": heart_rate,
        "samplingFrequency": 512,
        "numberOfVoltageMeasurements": sample_count,
        "source": "ECG",
        "voltageMeasurements": [{"date": index, "voltage": float(index), "units": "mcV"} for index in range(sample_count)],
    }


def test_full_health_export_payload_returns_prediction_shape(monkeypatch: Any) -> None:
    monkeypatch.setattr("backend.services.apple_watch_ecg.get_lead1_ecg_runtime", lambda: FakeRuntime())

    response = client.post(
        "/api/ecg/apple-watch/infer",
        json={
            "healthExport": {"data": {"ecg": [ecg_record(heart_rate=66), ecg_record(heart_rate=88)]}},
            "recordIndex": 1,
            "windowPolicy": "sliding",
            "threshold": 0.5,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["record_index"] == 1
    assert body["record_metadata"]["averageHeartRate"] == 88
    assert "voltageMeasurements" not in body["record_metadata"]
    assert body["window_policy"] == "sliding"
    assert body["target_samples"] == 5000
    assert body["checkpoint_sampling_rate_hz"] == 500.0
    assert body["predictions"][0]["probabilities"]["other_abnormal"] == 0.6
    assert body["predictions"][0]["labels_above_threshold"] == ["other_abnormal"]
    assert body["caveat"] == "Predictions are experimental and not clinically validated."
    assert "voltageMeasurements" not in response.text


def test_single_ecg_record_payload_returns_prediction_shape(monkeypatch: Any) -> None:
    monkeypatch.setattr("backend.services.apple_watch_ecg.get_lead1_ecg_runtime", lambda: FakeRuntime())

    response = client.post(
        "/api/ecg/apple-watch/infer",
        json={"ecgRecord": ecg_record(), "windowPolicy": "first", "threshold": 0.5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["record_index"] == 0
    assert len(body["predictions"]) == 1
    assert body["caveat"] == "Predictions are experimental and not clinically validated."


def test_missing_data_ecg_is_rejected() -> None:
    response = client.post(
        "/api/ecg/apple-watch/infer",
        json={"healthExport": {"data": {}}, "recordIndex": 0},
    )

    assert response.status_code == 422


def test_missing_voltage_measurements_is_rejected() -> None:
    payload = ecg_record()
    payload["voltageMeasurements"] = []

    response = client.post(
        "/api/ecg/apple-watch/infer",
        json={"ecgRecord": payload},
    )

    assert response.status_code == 422


def test_invalid_record_index_is_rejected() -> None:
    response = client.post(
        "/api/ecg/apple-watch/infer",
        json={"healthExport": {"data": {"ecg": [ecg_record()]}}, "recordIndex": 1},
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "Invalid recordIndex for ECG data."}


def test_model_failure_returns_controlled_error(monkeypatch: Any) -> None:
    def fake_infer(payload: Any) -> dict[str, Any]:
        raise RuntimeError("/private/model/path failed")

    monkeypatch.setattr("backend.routers.ecg.infer_apple_watch_ecg", fake_infer)

    response = client.post(
        "/api/ecg/apple-watch/infer",
        json={"ecgRecord": ecg_record()},
    )

    assert response.status_code == 503
    assert response.json() == {"detail": "Apple Watch ECG inference service is unavailable."}
    assert "/private/model/path" not in response.text


def test_short_ecg_pads_to_one_window() -> None:
    runtime = Lead1EcgRuntime(
        model=FakeModel(),
        target_names=TARGET_NAMES,
        target_samples=5,
        sampling_rate_hz=5.0,
        duration_sec=1.0,
        device=torch.device("cpu"),
    )

    predictions = runtime.infer(np.asarray([1.0, 2.0, 3.0], dtype=np.float32), source_hz=5.0, window_policy="sliding", threshold=0.5)

    assert len(predictions) == 1
    assert predictions[0]["window_start_sample"] == 0
    assert predictions[0]["window_end_sample"] == 3


def test_non_finite_voltage_values_do_not_crash_inference() -> None:
    runtime = Lead1EcgRuntime(
        model=FakeModel(),
        target_names=TARGET_NAMES,
        target_samples=5,
        sampling_rate_hz=5.0,
        duration_sec=1.0,
        device=torch.device("cpu"),
    )

    predictions = runtime.infer(
        np.asarray([np.nan, np.inf, -np.inf, 1.0, 2.0], dtype=np.float32),
        source_hz=5.0,
        window_policy="first",
        threshold=0.5,
    )

    assert len(predictions) == 1
    assert predictions[0]["prob_any_abnormal"] == 0.5


def test_thirty_second_512hz_sliding_ecg_produces_three_windows() -> None:
    runtime = Lead1EcgRuntime(
        model=FakeModel(),
        target_names=TARGET_NAMES,
        target_samples=5000,
        sampling_rate_hz=500.0,
        duration_sec=10.0,
        device=torch.device("cpu"),
    )

    predictions = runtime.infer(np.zeros(15360, dtype=np.float32), source_hz=512.0, window_policy="sliding", threshold=0.5)

    assert len(predictions) == 3
    assert predictions[0]["window_start_sample"] == 0
    assert predictions[1]["window_start_sample"] == 5000
    assert predictions[2]["window_start_sample"] == 10000
    assert predictions[2]["window_end_sample"] == 15000


def test_payload_too_large_returns_413(monkeypatch: Any) -> None:
    monkeypatch.setenv("ECG_MAX_REQUEST_BYTES", "100")

    response = client.post(
        "/api/ecg/apple-watch/infer",
        json={"ecgRecord": ecg_record(sample_count=50)},
    )

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body is too large."}


def test_route_is_registered() -> None:
    routes = {getattr(route, "path", None) for route in app.routes}

    assert "/api/ecg/apple-watch/infer" in routes
