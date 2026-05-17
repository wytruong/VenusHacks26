from __future__ import annotations

import os
from dataclasses import dataclass
from math import isfinite
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

TARGET_NAMES = [
    "normal_or_sinus_reference",
    "atrial_fibrillation_or_flutter",
    "bradycardia_or_tachycardia",
    "other_abnormal",
]

REQUIRED_CHECKPOINT_KEYS = {
    "model_state_dict",
    "model_config",
    "target_names",
    "target_samples",
    "sampling_rate_hz",
    "duration_sec",
}

DEFAULT_CHECKPOINT_PATH = Path(__file__).resolve().parents[2] / "models" / "lead1_dataset_invariance" / "best_kept_adversarial.pt"


class GradientReverse(torch.autograd.Function):
    @staticmethod
    def forward(ctx: Any, x: torch.Tensor, strength: float) -> torch.Tensor:
        ctx.strength = strength
        return x.view_as(x)

    @staticmethod
    def backward(ctx: Any, grad_output: torch.Tensor) -> tuple[torch.Tensor, None]:
        return -ctx.strength * grad_output, None


def gradient_reverse(x: torch.Tensor, strength: float) -> torch.Tensor:
    return GradientReverse.apply(x, strength)


def mixstyle_1d(
    x: torch.Tensor,
    dataset_targets: torch.Tensor | None,
    *,
    prob: float,
    alpha: float,
    training: bool,
) -> torch.Tensor:
    if not training or prob <= 0.0 or x.shape[0] < 2:
        return x
    if float(torch.rand(1, device=x.device).item()) > prob:
        return x
    mu = x.mean(dim=2, keepdim=True)
    var = x.var(dim=2, keepdim=True, unbiased=False)
    sigma = (var + 1e-6).sqrt()
    x_norm = (x - mu) / sigma

    perm = torch.randperm(x.shape[0], device=x.device)
    if dataset_targets is not None and len(torch.unique(dataset_targets)) > 1:
        perm_list: list[int] = []
        for idx in range(x.shape[0]):
            candidates = torch.where(dataset_targets != dataset_targets[idx])[0]
            if len(candidates) == 0:
                perm_list.append(int(perm[idx].item()))
            else:
                sample_idx = candidates[torch.randint(len(candidates), (1,), device=x.device)]
                perm_list.append(int(sample_idx.item()))
        perm = torch.tensor(perm_list, device=x.device, dtype=torch.long)

    if alpha <= 0.0:
        lam = torch.full((x.shape[0], 1, 1), 0.5, device=x.device)
    else:
        beta = torch.distributions.Beta(alpha, alpha)
        lam = beta.sample((x.shape[0], 1, 1)).to(x.device)
    mu_mix = (lam * mu) + ((1.0 - lam) * mu[perm])
    sigma_mix = (lam * sigma) + ((1.0 - lam) * sigma[perm])
    return (x_norm * sigma_mix) + mu_mix


class LeadOneCnn(nn.Module):
    def __init__(
        self,
        num_targets: int,
        num_datasets: int,
        *,
        feature_dim: int = 64,
        dataset_feature_dropout: float = 0.0,
        dataset_feature_noise_std: float = 0.0,
        dataset_feature_layer_norm: bool = False,
        mixstyle_prob: float = 0.0,
        mixstyle_alpha: float = 0.3,
        mixstyle_layer: str = "none",
    ) -> None:
        super().__init__()
        self.block1 = nn.Sequential(
            nn.Conv1d(1, 16, kernel_size=15, stride=2, padding=7),
            nn.BatchNorm1d(16),
            nn.ReLU(),
            nn.MaxPool1d(4),
        )
        self.block2 = nn.Sequential(
            nn.Conv1d(16, 32, kernel_size=9, stride=2, padding=4),
            nn.BatchNorm1d(32),
            nn.ReLU(),
            nn.MaxPool1d(4),
        )
        self.block3 = nn.Sequential(
            nn.Conv1d(32, feature_dim, kernel_size=7, stride=2, padding=3),
            nn.BatchNorm1d(feature_dim),
            nn.ReLU(),
        )
        self.pool = nn.AdaptiveAvgPool1d(1)
        self.disease_head = nn.Linear(feature_dim, num_targets)
        self.dataset_feature_norm = nn.LayerNorm(feature_dim) if dataset_feature_layer_norm else nn.Identity()
        self.dataset_feature_dropout = nn.Dropout(dataset_feature_dropout)
        self.dataset_feature_noise_std = dataset_feature_noise_std
        self.dataset_head = nn.Linear(feature_dim, num_datasets)
        self.clean_probe_dataset_head = nn.Linear(feature_dim, num_datasets)
        self.mixstyle_prob = mixstyle_prob
        self.mixstyle_alpha = mixstyle_alpha
        self.mixstyle_layer = mixstyle_layer

    def encode_with_taps(
        self, x: torch.Tensor, dataset_targets: torch.Tensor | None = None
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        x = self.block1(x)
        if self.mixstyle_layer == "block1":
            x = mixstyle_1d(
                x,
                dataset_targets,
                prob=self.mixstyle_prob,
                alpha=self.mixstyle_alpha,
                training=self.training,
            )
        tap_block1 = self.pool(x).flatten(1)
        x = self.block2(x)
        if self.mixstyle_layer == "block2":
            x = mixstyle_1d(
                x,
                dataset_targets,
                prob=self.mixstyle_prob,
                alpha=self.mixstyle_alpha,
                training=self.training,
            )
        tap_block2 = self.pool(x).flatten(1)
        x = self.block3(x)
        return self.pool(x).flatten(1), {"block1": tap_block1, "block2": tap_block2}

    def encode(self, x: torch.Tensor, dataset_targets: torch.Tensor | None = None) -> torch.Tensor:
        features, _taps = self.encode_with_taps(x, dataset_targets=dataset_targets)
        return features

    def heads_from_features(
        self, features: torch.Tensor, *, adversarial_strength: float = 0.0
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        disease_logits = self.disease_head(features)
        dataset_features = gradient_reverse(features, adversarial_strength) if adversarial_strength else features
        dataset_features = self.dataset_feature_norm(dataset_features)
        dataset_features = self.dataset_feature_dropout(dataset_features)
        if self.training and self.dataset_feature_noise_std > 0.0:
            dataset_features = dataset_features + torch.randn_like(dataset_features) * self.dataset_feature_noise_std
        dataset_logits = self.dataset_head(dataset_features)
        clean_probe_features = gradient_reverse(features, adversarial_strength) if adversarial_strength else features
        clean_probe_dataset_logits = self.clean_probe_dataset_head(clean_probe_features)
        return disease_logits, dataset_logits, clean_probe_dataset_logits

    def forward_with_features(
        self,
        x: torch.Tensor,
        *,
        adversarial_strength: float = 0.0,
        dataset_targets: torch.Tensor | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, dict[str, torch.Tensor]]:
        features, tap_features = self.encode_with_taps(x, dataset_targets=dataset_targets)
        disease_logits, dataset_logits, clean_probe_dataset_logits = self.heads_from_features(
            features, adversarial_strength=adversarial_strength
        )
        return disease_logits, dataset_logits, clean_probe_dataset_logits, features, tap_features

    def forward(self, x: torch.Tensor, *, adversarial_strength: float = 0.0) -> tuple[torch.Tensor, torch.Tensor]:
        disease_logits, dataset_logits, _clean_probe_dataset_logits, _features, _tap_features = self.forward_with_features(
            x, adversarial_strength=adversarial_strength
        )
        return disease_logits, dataset_logits


@dataclass(frozen=True)
class Lead1EcgRuntime:
    model: nn.Module
    target_names: list[str]
    target_samples: int
    sampling_rate_hz: float
    duration_sec: float
    device: torch.device

    def infer(
        self,
        waveform: list[float] | np.ndarray,
        *,
        source_hz: float,
        window_policy: str,
        threshold: float,
    ) -> list[dict[str, Any]]:
        signal = np.asarray(waveform, dtype=np.float32)
        signal = np.where(np.isfinite(signal), signal, 0.0).astype(np.float32)
        resampled = resample_signal(signal, source_hz, self.sampling_rate_hz)
        windows = make_windows(resampled, self.target_samples, window_policy)
        batch = np.stack([normalize_window(window) for window in windows])
        batch_tensor = torch.from_numpy(batch).unsqueeze(1).to(self.device)

        with torch.inference_mode():
            logits = self.model(batch_tensor)[0]
            probs = torch.sigmoid(logits).detach().cpu().numpy()

        predictions: list[dict[str, Any]] = []
        for window_index, prob_vec in enumerate(probs):
            probabilities = {name: float(prob_vec[index]) for index, name in enumerate(self.target_names)}
            prob_any_abnormal = max(probabilities[name] for name in self.target_names)
            labels_above_threshold = [name for name in self.target_names if probabilities[name] >= threshold]
            predictions.append(
                {
                    "window_index": window_index,
                    "window_start_sample": window_index * self.target_samples,
                    "window_end_sample": min((window_index + 1) * self.target_samples, int(resampled.size)),
                    "window_duration_sec": self.duration_sec,
                    "window_target_samples": self.target_samples,
                    "prob_any_abnormal": prob_any_abnormal,
                    "pred_any_abnormal": prob_any_abnormal >= threshold,
                    "labels_above_threshold": labels_above_threshold,
                    "probabilities": probabilities,
                }
            )
        return predictions


def resolve_device(choice: str) -> torch.device:
    if choice == "auto":
        return torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    if choice == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS requested but torch.backends.mps is not available")
    if choice != "cpu" and choice != "mps":
        raise RuntimeError("Unsupported ECG inference device")
    return torch.device(choice)


def extract_voltage_array(values: list[float]) -> np.ndarray:
    if not values:
        raise ValueError("Record has no voltage values")
    return np.asarray([float(value) for value in values], dtype=np.float32)


def resample_signal(signal: np.ndarray, src_hz: float, dst_hz: float) -> np.ndarray:
    if not isfinite(src_hz) or not isfinite(dst_hz) or src_hz <= 0 or dst_hz <= 0:
        raise ValueError("Invalid sampling frequency")
    if signal.size == 0:
        return signal
    if abs(src_hz - dst_hz) < 1e-9:
        return signal.astype(np.float32, copy=False)
    duration_sec = (signal.size - 1) / src_hz if signal.size > 1 else 0.0
    new_len = max(1, int(round(duration_sec * dst_hz)) + 1)
    old_x = np.linspace(0.0, duration_sec, num=signal.size, endpoint=True)
    new_x = np.linspace(0.0, duration_sec, num=new_len, endpoint=True)
    return np.interp(new_x, old_x, signal).astype(np.float32)


def normalize_window(window: np.ndarray) -> np.ndarray:
    arr = window.astype(np.float32, copy=True)
    finite = np.isfinite(arr)
    if not finite.all():
        arr = np.where(finite, arr, 0.0)
    mean = float(arr.mean())
    std = float(arr.std())
    return ((arr - mean) / (std + 1e-6)).astype(np.float32)


def make_windows(signal: np.ndarray, target_samples: int, policy: str) -> list[np.ndarray]:
    if target_samples <= 0:
        raise ValueError("target_samples must be greater than 0")
    if policy == "first":
        window = signal[:target_samples]
        if window.size < target_samples:
            window = np.pad(window, (0, target_samples - window.size), mode="constant")
        return [window.astype(np.float32)]
    if policy != "sliding":
        raise ValueError("Unsupported window policy")

    windows: list[np.ndarray] = []
    total = signal.size
    if total < target_samples:
        padded = np.pad(signal, (0, target_samples - total), mode="constant")
        return [padded.astype(np.float32)]

    for start in range(0, total, target_samples):
        end = min(start + target_samples, total)
        segment = signal[start:end]
        if segment.size == 0:
            continue
        if segment.size < target_samples:
            segment = np.pad(segment, (0, target_samples - segment.size), mode="constant")
        windows.append(segment.astype(np.float32))
    return windows or [np.zeros(target_samples, dtype=np.float32)]


def load_checkpoint(path: Path) -> dict[str, Any]:
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(checkpoint, dict):
        raise RuntimeError("Checkpoint payload is not a dict")
    missing = sorted(REQUIRED_CHECKPOINT_KEYS - set(checkpoint.keys()))
    if missing:
        raise RuntimeError("Checkpoint missing required fields")
    model_config = checkpoint.get("model_config")
    if not isinstance(model_config, dict):
        raise RuntimeError("Checkpoint model_config must be a dict")
    target_names = checkpoint.get("target_names")
    if target_names != TARGET_NAMES:
        raise RuntimeError("Checkpoint target_names do not match runtime target order")
    if int(checkpoint["target_samples"]) <= 0:
        raise RuntimeError("Checkpoint target_samples must be greater than 0")
    if float(checkpoint["sampling_rate_hz"]) <= 0:
        raise RuntimeError("Checkpoint sampling_rate_hz must be greater than 0")
    if float(checkpoint["duration_sec"]) <= 0:
        raise RuntimeError("Checkpoint duration_sec must be greater than 0")
    return checkpoint


def build_model(checkpoint: dict[str, Any], device: torch.device) -> nn.Module:
    model = LeadOneCnn(**checkpoint["model_config"])
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()
    return model


@lru_cache(maxsize=1)
def get_lead1_ecg_runtime(checkpoint_path: str | None = None, device_choice: str | None = None) -> Lead1EcgRuntime:
    configured_path = checkpoint_path or os.getenv("ECG_LEAD1_CHECKPOINT_PATH")
    path = Path(configured_path) if configured_path else DEFAULT_CHECKPOINT_PATH
    device = resolve_device(device_choice or os.getenv("ECG_LEAD1_DEVICE", "cpu"))
    checkpoint = load_checkpoint(path)
    model = build_model(checkpoint, device)
    return Lead1EcgRuntime(
        model=model,
        target_names=list(checkpoint["target_names"]),
        target_samples=int(checkpoint["target_samples"]),
        sampling_rate_hz=float(checkpoint["sampling_rate_hz"]),
        duration_sec=float(checkpoint["duration_sec"]),
        device=device,
    )
