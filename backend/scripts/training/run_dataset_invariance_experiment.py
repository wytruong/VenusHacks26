#!/usr/bin/env python3
"""Run the first Lead I dataset-invariance ECG experiment.

This is intentionally small enough for Autoresearch iteration while preserving
the important contracts: patient-level manifest splits, source-dataset monitor,
and an adversarial variant using a gradient reversal layer.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import wfdb
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from torch.utils.data import DataLoader, TensorDataset
from tqdm import tqdm


NORMAL_REFERENCE_LABELS = {"normal", "sinus_rhythm"}
AF_LABELS = {"atrial_fibrillation_or_flutter", "atrial_fibrillation", "atrial_flutter"}
BRADY_TACHY_LABELS = {"bradycardia", "tachycardia"}
TARGET_NAMES = [
    "normal_or_sinus_reference",
    "atrial_fibrillation_or_flutter",
    "bradycardia_or_tachycardia",
    "other_abnormal",
]
LEAD1_DATASETS = {"ptb-xl", "ecg-arrhythmia"}


@dataclass
class VariantMetrics:
    variant: str
    split: str
    abnormal_recall: float
    abnormal_false_negative_rate: float
    abnormal_precision: float
    disease_macro_f1: float
    disease_macro_auroc: float | None
    dataset_head_accuracy: float | None
    dataset_probe_accuracy: float | None
    dataset_probe_balanced_accuracy: float | None
    disease_loss: float
    dataset_loss: float | None
    total_objective_loss: float
    samples: int


class GradientReverse(torch.autograd.Function):
    @staticmethod
    def forward(ctx, x: torch.Tensor, strength: float) -> torch.Tensor:
        ctx.strength = strength
        return x.view_as(x)

    @staticmethod
    def backward(ctx, grad_output: torch.Tensor) -> tuple[torch.Tensor, None]:
        return -ctx.strength * grad_output, None


def gradient_reverse(x: torch.Tensor, strength: float) -> torch.Tensor:
    return GradientReverse.apply(x, strength)


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

    def forward(
        self, x: torch.Tensor, *, adversarial_strength: float = 0.0
    ) -> tuple[torch.Tensor, torch.Tensor]:
        disease_logits, dataset_logits, _clean_probe_dataset_logits, _features, _tap_features = self.forward_with_features(
            x, adversarial_strength=adversarial_strength
        )
        return disease_logits, dataset_logits


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--input-mode", choices=["lead1"], default="lead1")
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--max-train-samples", type=int, default=4096)
    parser.add_argument("--max-val-samples", type=int, default=1024)
    parser.add_argument("--max-test-samples", type=int, default=1024)
    parser.add_argument("--variants", nargs="+", choices=["baseline", "adversarial"], default=["baseline", "adversarial"])
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--seed", type=int, default=73)
    parser.add_argument("--sampling-rate-hz", type=int, default=500)
    parser.add_argument("--duration-sec", type=int, default=10)
    parser.add_argument("--adversarial-strength", type=float, default=0.05)
    parser.add_argument("--dataset-loss-weight", type=float, default=1.0)
    parser.add_argument("--encoder-feature-dim", type=int, default=64)
    parser.add_argument("--dataset-feature-dropout", type=float, default=0.0)
    parser.add_argument("--dataset-feature-noise-std", type=float, default=0.0)
    parser.add_argument("--dataset-feature-layer-norm", action="store_true")
    parser.add_argument("--dataset-alignment-weight", type=float, default=0.0)
    parser.add_argument("--dataset-coral-weight", type=float, default=0.0)
    parser.add_argument("--probe-focused-alignment-weight", type=float, default=0.0)
    parser.add_argument("--probe-focused-coral-weight", type=float, default=0.0)
    parser.add_argument("--clean-probe-adversary-weight", type=float, default=0.0)
    parser.add_argument("--tap-alignment-weight", type=float, default=0.0)
    parser.add_argument("--tap-coral-weight", type=float, default=0.0)
    parser.add_argument("--mixstyle-prob", type=float, default=0.0)
    parser.add_argument("--mixstyle-alpha", type=float, default=0.3)
    parser.add_argument(
        "--mixstyle-layer",
        choices=["none", "block1", "block2"],
        default="none",
    )
    parser.add_argument("--selective-consistency-weight", type=float, default=0.0)
    parser.add_argument("--spectral-mix-prob", type=float, default=0.0)
    parser.add_argument("--spectral-mix-strength", type=float, default=0.0)
    parser.add_argument("--spectral-low-freq-fraction", type=float, default=0.1)
    parser.add_argument("--phase-mix-prob", type=float, default=0.0)
    parser.add_argument("--phase-mix-strength", type=float, default=0.0)
    parser.add_argument("--phase-low-freq-fraction", type=float, default=0.1)
    parser.add_argument("--style-aug-prob", type=float, default=0.0)
    parser.add_argument("--style-baseline-wander-scale", type=float, default=0.0)
    parser.add_argument("--style-drift-scale", type=float, default=0.0)
    parser.add_argument("--style-gain-std", type=float, default=0.0)
    parser.add_argument("--style-noise-std", type=float, default=0.0)
    parser.add_argument(
        "--dataset-head-bias-init",
        choices=["none", "inverse_frequency", "inverse_sqrt_frequency"],
        default="none",
    )
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--device", choices=["auto", "cpu", "mps"], default="auto")
    return parser.parse_args()


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def parse_json_list(value: object) -> list[str]:
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data]


def lead_index(lead_order: str, desired: str = "I") -> int | None:
    leads = [item.strip() for item in str(lead_order).replace(",", "|").split("|") if item.strip()]
    normalized = [lead.upper() for lead in leads]
    try:
        return normalized.index(desired.upper())
    except ValueError:
        return None


def derive_targets(row: pd.Series) -> np.ndarray:
    labels = set(parse_json_list(row.get("normalized_labels", "")))
    balance_group = str(row.get("split_balance_group", ""))
    normal_reference = balance_group == "normal_or_sinus_reference" or (
        bool(labels) and labels.issubset(NORMAL_REFERENCE_LABELS)
    )
    af = bool(labels & AF_LABELS)
    brady_tachy = bool(labels & BRADY_TACHY_LABELS)
    abnormal = balance_group != "normal_or_sinus_reference" and not normal_reference
    other_abnormal = abnormal and not af and not brady_tachy
    return np.array([normal_reference, af, brady_tachy, other_abnormal], dtype=np.float32)


def select_manifest_rows(manifest_path: Path, seed: int, limits: dict[str, int]) -> pd.DataFrame:
    manifest = pd.read_csv(manifest_path, dtype=str).fillna("")
    include = bool_series(manifest["include_for_training"])
    selected = manifest[
        include
        & manifest["original_source_dataset"].isin(LEAD1_DATASETS)
        & (manifest["lead_order_source"] == "wfdb_header")
        & (manifest["sampling_rate_hz"].astype(str) == "500")
    ].copy()
    selected["lead_i_index"] = selected["lead_order"].map(lead_index)
    selected = selected[selected["lead_i_index"].notna()].copy()
    selected["target_vector"] = selected.apply(derive_targets, axis=1)
    selected = selected[selected["target_vector"].map(lambda values: bool(np.asarray(values)[1:].any() or values[0]))]

    sampled_parts = []
    for split, limit in limits.items():
        split_rows = selected[selected["split"] == split]
        if limit and len(split_rows) > limit:
            split_rows = split_rows.sample(n=limit, random_state=seed)
        sampled_parts.append(split_rows)
    return pd.concat(sampled_parts, ignore_index=True)


def load_lead_one_signal(row: pd.Series, target_samples: int) -> np.ndarray:
    signal, _ = wfdb.rdsamp(str(row["source_path"]))
    lead = signal[:, int(row["lead_i_index"])].astype(np.float32)
    if len(lead) >= target_samples:
        lead = lead[:target_samples]
    else:
        lead = np.pad(lead, (0, target_samples - len(lead)), mode="constant")
    finite = np.isfinite(lead)
    if not finite.all():
        lead = np.where(finite, lead, 0.0)
    mean = float(lead.mean())
    std = float(lead.std())
    return ((lead - mean) / (std + 1e-6)).astype(np.float32)


def materialize_tensors(rows: pd.DataFrame, target_samples: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, list[str]]:
    dataset_names = sorted(rows["original_source_dataset"].unique())
    dataset_to_id = {name: idx for idx, name in enumerate(dataset_names)}
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    ds: list[int] = []
    for _, row in tqdm(rows.iterrows(), total=len(rows), desc="loading_waveforms"):
        xs.append(load_lead_one_signal(row, target_samples))
        ys.append(np.asarray(row["target_vector"], dtype=np.float32))
        ds.append(dataset_to_id[row["original_source_dataset"]])
    x = torch.from_numpy(np.stack(xs)).unsqueeze(1)
    y = torch.from_numpy(np.stack(ys))
    d = torch.tensor(ds, dtype=torch.long)
    return x, y, d, dataset_names


def validate_target_distribution(rows: pd.DataFrame) -> dict[str, int]:
    counts = np.stack(rows["target_vector"].to_numpy()).sum(axis=0).astype(int)
    result = dict(zip(TARGET_NAMES, counts.tolist()))
    if "atrial_fibrillation_or_flutter" in "|".join(rows["normalized_labels"].tolist()) and not result[
        "atrial_fibrillation_or_flutter"
    ]:
        raise ValueError("target distribution bug: AF/flutter labels exist but target has zero positives")
    if not any(result[name] for name in TARGET_NAMES[1:]):
        raise ValueError("target distribution bug: no abnormal disease target positives selected")
    return result


def build_loaders(
    rows: pd.DataFrame, target_samples: int, batch_size: int
) -> tuple[dict[str, DataLoader], list[str]]:
    loaders: dict[str, DataLoader] = {}
    dataset_names: list[str] | None = None
    for split in ["train", "val", "test"]:
        split_rows = rows[rows["split"] == split].reset_index(drop=True)
        x, y, d, split_dataset_names = materialize_tensors(split_rows, target_samples)
        if dataset_names is None:
            dataset_names = split_dataset_names
        elif dataset_names != split_dataset_names:
            raise ValueError(f"dataset classes differ in {split}: {split_dataset_names} vs {dataset_names}")
        loaders[split] = DataLoader(
            TensorDataset(x, y, d),
            batch_size=batch_size,
            shuffle=False,
        )
    return loaders, dataset_names or []


def positive_weight(loader: DataLoader) -> torch.Tensor:
    y = loader.dataset.tensors[1]
    pos = y.sum(dim=0)
    neg = y.shape[0] - pos
    return torch.clamp(neg / torch.clamp(pos, min=1.0), min=1.0, max=20.0)


def disease_macro_auroc(y_true: np.ndarray, y_prob: np.ndarray) -> float | None:
    scores: list[float] = []
    for idx in range(y_true.shape[1]):
        if len(np.unique(y_true[:, idx])) < 2:
            continue
        scores.append(float(roc_auc_score(y_true[:, idx], y_prob[:, idx])))
    if not scores:
        return None
    return float(np.mean(scores))


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


def spectral_mix_1d(
    x: torch.Tensor,
    dataset_targets: torch.Tensor,
    *,
    prob: float,
    strength: float,
    low_freq_fraction: float,
    training: bool,
) -> torch.Tensor:
    if not training or prob <= 0.0 or strength <= 0.0 or x.shape[0] < 2:
        return x
    if float(torch.rand(1, device=x.device).item()) > prob:
        return x
    perm_list: list[int] = []
    for idx in range(x.shape[0]):
        candidates = torch.where(dataset_targets != dataset_targets[idx])[0]
        if len(candidates) == 0:
            perm_list.append((idx + 1) % x.shape[0])
        else:
            sample_idx = candidates[torch.randint(len(candidates), (1,), device=x.device)]
            perm_list.append(int(sample_idx.item()))
    perm = torch.tensor(perm_list, device=x.device, dtype=torch.long)

    spectrum = torch.fft.rfft(x, dim=-1)
    amp = torch.abs(spectrum)
    phase = torch.angle(spectrum)
    cutoff = max(1, int(amp.shape[-1] * low_freq_fraction))
    donor_amp = amp[perm]
    amp[..., :cutoff] = ((1.0 - strength) * amp[..., :cutoff]) + (strength * donor_amp[..., :cutoff])
    mixed = amp * torch.exp(1j * phase)
    return torch.fft.irfft(mixed, n=x.shape[-1], dim=-1)


def phase_mix_1d(
    x: torch.Tensor,
    dataset_targets: torch.Tensor,
    *,
    prob: float,
    strength: float,
    low_freq_fraction: float,
    training: bool,
) -> torch.Tensor:
    if not training or prob <= 0.0 or strength <= 0.0 or x.shape[0] < 2:
        return x
    if float(torch.rand(1, device=x.device).item()) > prob:
        return x
    perm_list: list[int] = []
    for idx in range(x.shape[0]):
        candidates = torch.where(dataset_targets != dataset_targets[idx])[0]
        if len(candidates) == 0:
            perm_list.append((idx + 1) % x.shape[0])
        else:
            sample_idx = candidates[torch.randint(len(candidates), (1,), device=x.device)]
            perm_list.append(int(sample_idx.item()))
    perm = torch.tensor(perm_list, device=x.device, dtype=torch.long)

    spectrum = torch.fft.rfft(x, dim=-1)
    amp = torch.abs(spectrum)
    phase = torch.angle(spectrum)
    donor_phase = phase[perm]
    cutoff = max(1, int(phase.shape[-1] * low_freq_fraction))

    kept_phase = phase[..., :cutoff]
    phase_tail = phase[..., cutoff:]
    donor_phase_tail = donor_phase[..., cutoff:]
    if phase_tail.shape[-1] == 0:
        return x

    mixed_real = ((1.0 - strength) * torch.cos(phase_tail)) + (strength * torch.cos(donor_phase_tail))
    mixed_imag = ((1.0 - strength) * torch.sin(phase_tail)) + (strength * torch.sin(donor_phase_tail))
    mixed_phase_tail = torch.atan2(mixed_imag, mixed_real)
    mixed_phase = torch.cat([kept_phase, mixed_phase_tail], dim=-1)
    mixed = amp * torch.exp(1j * mixed_phase)
    return torch.fft.irfft(mixed, n=x.shape[-1], dim=-1)


def style_destroy_1d(
    x: torch.Tensor,
    *,
    prob: float,
    baseline_wander_scale: float,
    drift_scale: float,
    gain_std: float,
    noise_std: float,
    training: bool,
) -> torch.Tensor:
    if not training or prob <= 0.0 or x.shape[0] == 0:
        return x
    mask = (torch.rand(x.shape[0], 1, 1, device=x.device) < prob).to(x.dtype)
    if float(mask.sum().item()) == 0.0:
        return x
    t = torch.linspace(-1.0, 1.0, x.shape[-1], device=x.device, dtype=x.dtype).view(1, 1, -1)
    augmented = x
    if gain_std > 0.0:
        gains = torch.exp(torch.randn(x.shape[0], 1, 1, device=x.device, dtype=x.dtype) * gain_std)
        augmented = augmented * (((1.0 - mask) * 1.0) + (mask * gains))
    if baseline_wander_scale > 0.0:
        freqs = torch.empty(x.shape[0], 1, 1, device=x.device, dtype=x.dtype).uniform_(0.05, 0.7)
        phases = torch.empty(x.shape[0], 1, 1, device=x.device, dtype=x.dtype).uniform_(0.0, 2.0 * math.pi)
        amps = torch.randn(x.shape[0], 1, 1, device=x.device, dtype=x.dtype) * baseline_wander_scale
        baseline = amps * torch.sin((2.0 * math.pi * freqs * t) + phases)
        augmented = augmented + (mask * baseline)
    if drift_scale > 0.0:
        drifts = torch.randn(x.shape[0], 1, 1, device=x.device, dtype=x.dtype) * drift_scale
        augmented = augmented + (mask * drifts * t)
    if noise_std > 0.0:
        augmented = augmented + (mask * torch.randn_like(x) * noise_std)
    return augmented


def evaluate(
    model: LeadOneCnn,
    loader: DataLoader,
    disease_loss_fn: nn.Module,
    dataset_loss_fn: nn.Module,
    device: torch.device,
    variant: str,
    split: str,
    include_dataset_head: bool,
    dataset_probe_scores: dict[str, float] | None = None,
) -> VariantMetrics:
    model.eval()
    disease_losses: list[float] = []
    dataset_losses: list[float] = []
    total_losses: list[float] = []
    disease_probs: list[np.ndarray] = []
    disease_targets: list[np.ndarray] = []
    dataset_preds: list[np.ndarray] = []
    dataset_targets: list[np.ndarray] = []
    with torch.no_grad():
        for x, y, d in loader:
            x = x.to(device)
            y = y.to(device)
            d = d.to(device)
            disease_logits, dataset_logits = model(x, adversarial_strength=0.0)
            disease_loss = disease_loss_fn(disease_logits, y)
            dataset_loss = dataset_loss_fn(dataset_logits, d)
            loss = disease_loss
            if include_dataset_head:
                loss = loss + dataset_loss
            disease_losses.append(float(disease_loss.item()))
            dataset_losses.append(float(dataset_loss.item()))
            total_losses.append(float(loss.item()))
            disease_probs.append(torch.sigmoid(disease_logits).cpu().numpy())
            disease_targets.append(y.cpu().numpy())
            dataset_preds.append(dataset_logits.argmax(dim=1).cpu().numpy())
            dataset_targets.append(d.cpu().numpy())

    y_true = np.concatenate(disease_targets, axis=0)
    y_prob = np.concatenate(disease_probs, axis=0)
    y_pred = (y_prob >= 0.5).astype(int)
    abnormal_true = y_true[:, 1:].max(axis=1).astype(int)
    abnormal_pred = (y_prob[:, 1:].max(axis=1) >= 0.5).astype(int)
    abnormal_recall = float(recall_score(abnormal_true, abnormal_pred, zero_division=0))
    abnormal_precision = float(precision_score(abnormal_true, abnormal_pred, zero_division=0))
    dataset_accuracy = None
    if include_dataset_head:
        dataset_accuracy = float(accuracy_score(np.concatenate(dataset_targets), np.concatenate(dataset_preds)))
    return VariantMetrics(
        variant=variant,
        split=split,
        abnormal_recall=abnormal_recall,
        abnormal_false_negative_rate=float(1.0 - abnormal_recall),
        abnormal_precision=abnormal_precision,
        disease_macro_f1=float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        disease_macro_auroc=disease_macro_auroc(y_true, y_prob),
        dataset_head_accuracy=dataset_accuracy,
        dataset_probe_accuracy=dataset_probe_scores.get("accuracy") if dataset_probe_scores else None,
        dataset_probe_balanced_accuracy=dataset_probe_scores.get("balanced_accuracy") if dataset_probe_scores else None,
        disease_loss=float(np.mean(disease_losses)) if disease_losses else math.nan,
        dataset_loss=float(np.mean(dataset_losses)) if include_dataset_head and dataset_losses else None,
        total_objective_loss=float(np.mean(total_losses)) if total_losses else math.nan,
        samples=int(y_true.shape[0]),
    )


def extract_features(model: LeadOneCnn, loader: DataLoader, device: torch.device) -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    features: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    with torch.no_grad():
        for x, _y, d in loader:
            encoded = model.encode(x.to(device))
            features.append(encoded.cpu().numpy())
            targets.append(d.numpy())
    return np.concatenate(features, axis=0), np.concatenate(targets, axis=0)


def dataset_alignment_loss(features: torch.Tensor, dataset_targets: torch.Tensor) -> torch.Tensor:
    unique_targets = torch.unique(dataset_targets)
    if len(unique_targets) < 2:
        return features.new_tensor(0.0)
    global_mean = features.mean(dim=0)
    penalties = []
    for target in unique_targets:
        group_features = features[dataset_targets == target]
        if len(group_features) == 0:
            continue
        penalties.append(torch.mean((group_features.mean(dim=0) - global_mean) ** 2))
    if not penalties:
        return features.new_tensor(0.0)
    return torch.stack(penalties).mean()


def dataset_salience_weights(features: torch.Tensor, dataset_targets: torch.Tensor) -> torch.Tensor:
    unique_targets = torch.unique(dataset_targets)
    if len(unique_targets) < 2:
        return torch.ones(features.shape[1], device=features.device, dtype=features.dtype)
    means = []
    for target in unique_targets:
        group_features = features[dataset_targets == target]
        if len(group_features) == 0:
            continue
        means.append(group_features.mean(dim=0))
    if len(means) < 2:
        return torch.ones(features.shape[1], device=features.device, dtype=features.dtype)
    mean_stack = torch.stack(means, dim=0)
    salience = mean_stack.var(dim=0, unbiased=False)
    salience = salience / torch.clamp(salience.mean(), min=1e-6)
    return torch.clamp(salience.detach(), min=0.25, max=4.0)


def probe_focused_alignment_loss(features: torch.Tensor, dataset_targets: torch.Tensor) -> torch.Tensor:
    unique_targets = torch.unique(dataset_targets)
    if len(unique_targets) < 2:
        return features.new_tensor(0.0)
    weights = dataset_salience_weights(features, dataset_targets)
    global_mean = features.mean(dim=0)
    penalties = []
    for target in unique_targets:
        group_features = features[dataset_targets == target]
        if len(group_features) == 0:
            continue
        diff = group_features.mean(dim=0) - global_mean
        penalties.append(torch.mean(weights * (diff**2)))
    if not penalties:
        return features.new_tensor(0.0)
    return torch.stack(penalties).mean()


def dataset_coral_loss(features: torch.Tensor, dataset_targets: torch.Tensor) -> torch.Tensor:
    unique_targets = torch.unique(dataset_targets)
    if len(unique_targets) < 2:
        return features.new_tensor(0.0)
    covariances = []
    for target in unique_targets:
        group_features = features[dataset_targets == target]
        if group_features.shape[0] < 2:
            continue
        centered = group_features - group_features.mean(dim=0, keepdim=True)
        covariances.append(centered.T.matmul(centered) / float(group_features.shape[0] - 1))
    if len(covariances) < 2:
        return features.new_tensor(0.0)
    penalties = []
    for left_idx in range(len(covariances)):
        for right_idx in range(left_idx + 1, len(covariances)):
            penalties.append(torch.mean((covariances[left_idx] - covariances[right_idx]) ** 2))
    return torch.stack(penalties).mean()


def probe_focused_coral_loss(features: torch.Tensor, dataset_targets: torch.Tensor) -> torch.Tensor:
    unique_targets = torch.unique(dataset_targets)
    if len(unique_targets) < 2:
        return features.new_tensor(0.0)
    covariances = []
    for target in unique_targets:
        group_features = features[dataset_targets == target]
        if group_features.shape[0] < 2:
            continue
        centered = group_features - group_features.mean(dim=0, keepdim=True)
        covariances.append(centered.T.matmul(centered) / float(group_features.shape[0] - 1))
    if len(covariances) < 2:
        return features.new_tensor(0.0)
    weights = dataset_salience_weights(features, dataset_targets)
    weight_matrix = torch.sqrt(torch.outer(weights, weights))
    penalties = []
    for left_idx in range(len(covariances)):
        for right_idx in range(left_idx + 1, len(covariances)):
            diff = covariances[left_idx] - covariances[right_idx]
            penalties.append(torch.mean(weight_matrix * (diff**2)))
    return torch.stack(penalties).mean()


def selective_consistency_loss(
    disease_logits: torch.Tensor, dataset_targets: torch.Tensor, disease_targets: torch.Tensor
) -> torch.Tensor:
    context_targets = (disease_targets[:, 1:].amax(dim=1) > 0.5).long()
    probs = torch.sigmoid(disease_logits)
    penalties = []
    for context in torch.unique(context_targets):
        context_mask = context_targets == context
        if int(context_mask.sum().item()) < 2:
            continue
        context_datasets = dataset_targets[context_mask]
        unique_datasets = torch.unique(context_datasets)
        if len(unique_datasets) < 2:
            continue
        dataset_means = []
        for dataset_id in unique_datasets:
            dataset_mask = context_mask & (dataset_targets == dataset_id)
            if int(dataset_mask.sum().item()) == 0:
                continue
            dataset_means.append(probs[dataset_mask].mean(dim=0))
        for left_idx in range(len(dataset_means)):
            for right_idx in range(left_idx + 1, len(dataset_means)):
                penalties.append(torch.mean((dataset_means[left_idx] - dataset_means[right_idx]) ** 2))
    if not penalties:
        return disease_logits.new_tensor(0.0)
    return torch.stack(penalties).mean()


def initialize_dataset_head_bias(model: LeadOneCnn, loader: DataLoader, mode: str) -> None:
    if mode == "none":
        return
    dataset_targets = loader.dataset.tensors[2]
    counts = torch.bincount(dataset_targets, minlength=model.dataset_head.out_features).float()
    priors = counts / torch.clamp(counts.sum(), min=1.0)
    if mode == "inverse_frequency":
        bias = -torch.log(torch.clamp(priors, min=1e-6))
    elif mode == "inverse_sqrt_frequency":
        bias = -0.5 * torch.log(torch.clamp(priors, min=1e-6))
    else:
        raise ValueError(f"unknown dataset head bias init mode: {mode}")
    bias = bias - bias.mean()
    with torch.no_grad():
        model.dataset_head.bias.copy_(bias.to(model.dataset_head.bias.device))
        model.clean_probe_dataset_head.bias.copy_(bias.to(model.clean_probe_dataset_head.bias.device))


def dataset_probe_scores(
    model: LeadOneCnn, loaders: dict[str, DataLoader], device: torch.device
) -> dict[str, dict[str, float]]:
    train_x, train_y = extract_features(model, loaders["train"], device)
    probe = LogisticRegression(max_iter=500, class_weight="balanced", random_state=0)
    probe.fit(train_x, train_y)
    scores: dict[str, dict[str, float]] = {}
    for split in ["val", "test"]:
        x, y = extract_features(model, loaders[split], device)
        pred = probe.predict(x)
        scores[split] = {
            "accuracy": float(accuracy_score(y, pred)),
            "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        }
    return scores


def scheduled_lambda(max_strength: float, step_index: int, total_steps: int) -> float:
    if max_strength <= 0 or total_steps <= 1:
        return 0.0
    progress = step_index / float(total_steps - 1)
    return float(max_strength * progress)


def train_variant(
    variant: str,
    loaders: dict[str, DataLoader],
    num_datasets: int,
    args: argparse.Namespace,
    device: torch.device,
) -> tuple[LeadOneCnn, list[VariantMetrics], list[float]]:
    model = LeadOneCnn(
        num_targets=len(TARGET_NAMES),
        num_datasets=num_datasets,
        feature_dim=args.encoder_feature_dim,
        dataset_feature_dropout=args.dataset_feature_dropout,
        dataset_feature_noise_std=args.dataset_feature_noise_std,
        dataset_feature_layer_norm=args.dataset_feature_layer_norm,
        mixstyle_prob=args.mixstyle_prob,
        mixstyle_alpha=args.mixstyle_alpha,
        mixstyle_layer=args.mixstyle_layer,
    ).to(device)
    model.load_state_dict(args.initial_state_dict)
    if variant == "adversarial":
        initialize_dataset_head_bias(model, loaders["train"], args.dataset_head_bias_init)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=1e-4)
    disease_loss_fn = nn.BCEWithLogitsLoss(pos_weight=positive_weight(loaders["train"]).to(device))
    dataset_loss_fn = nn.CrossEntropyLoss()
    include_dataset_head = variant == "adversarial"

    lambda_values: list[float] = []
    total_steps = max(1, args.epochs * len(loaders["train"]))
    global_step = 0
    for _epoch in range(args.epochs):
        model.train()
        for x, y, d in tqdm(loaders["train"], desc=f"train_{variant}"):
            x = x.to(device)
            y = y.to(device)
            d = d.to(device)
            x = style_destroy_1d(
                x,
                prob=args.style_aug_prob,
                baseline_wander_scale=args.style_baseline_wander_scale,
                drift_scale=args.style_drift_scale,
                gain_std=args.style_gain_std,
                noise_std=args.style_noise_std,
                training=model.training,
            )
            x = spectral_mix_1d(
                x,
                d,
                prob=args.spectral_mix_prob,
                strength=args.spectral_mix_strength,
                low_freq_fraction=args.spectral_low_freq_fraction,
                training=model.training,
            )
            x = phase_mix_1d(
                x,
                d,
                prob=args.phase_mix_prob,
                strength=args.phase_mix_strength,
                low_freq_fraction=args.phase_low_freq_fraction,
                training=model.training,
            )
            optimizer.zero_grad(set_to_none=True)
            strength = scheduled_lambda(args.adversarial_strength, global_step, total_steps) if include_dataset_head else 0.0
            lambda_values.append(strength)
            disease_logits, dataset_logits, clean_probe_dataset_logits, features, tap_features = model.forward_with_features(
                x,
                adversarial_strength=strength,
                dataset_targets=d,
            )
            loss = disease_loss_fn(disease_logits, y)
            if include_dataset_head:
                loss = loss + (args.dataset_loss_weight * dataset_loss_fn(dataset_logits, d))
                if args.clean_probe_adversary_weight > 0.0:
                    loss = loss + (args.clean_probe_adversary_weight * dataset_loss_fn(clean_probe_dataset_logits, d))
                if args.dataset_alignment_weight > 0.0:
                    loss = loss + (args.dataset_alignment_weight * dataset_alignment_loss(features, d))
                if args.dataset_coral_weight > 0.0:
                    loss = loss + (args.dataset_coral_weight * dataset_coral_loss(features, d))
                if args.probe_focused_alignment_weight > 0.0:
                    loss = loss + (args.probe_focused_alignment_weight * probe_focused_alignment_loss(features, d))
                if args.probe_focused_coral_weight > 0.0:
                    loss = loss + (args.probe_focused_coral_weight * probe_focused_coral_loss(features, d))
                if args.tap_alignment_weight > 0.0 and tap_features:
                    tap_alignment = torch.stack(
                        [dataset_alignment_loss(tap_feature, d) for tap_feature in tap_features.values()]
                    ).mean()
                    loss = loss + (args.tap_alignment_weight * tap_alignment)
                if args.tap_coral_weight > 0.0 and tap_features:
                    tap_coral = torch.stack(
                        [dataset_coral_loss(tap_feature, d) for tap_feature in tap_features.values()]
                    ).mean()
                    loss = loss + (args.tap_coral_weight * tap_coral)
                if args.selective_consistency_weight > 0.0:
                    loss = loss + (args.selective_consistency_weight * selective_consistency_loss(disease_logits, d, y))
            loss.backward()
            optimizer.step()
            global_step += 1

    probe_scores = dataset_probe_scores(model, loaders, device)
    metrics = [
        evaluate(
            model,
            loaders[split],
            disease_loss_fn,
            dataset_loss_fn,
            device,
            variant,
            split,
            include_dataset_head,
            dataset_probe_scores=probe_scores[split],
        )
        for split in ["val", "test"]
    ]
    return model, metrics, lambda_values


def write_outputs(
    output_dir: Path,
    metrics: Iterable[VariantMetrics],
    rows: pd.DataFrame,
    dataset_names: list[str],
    target_distribution: dict[str, int],
    lambda_schedule: dict[str, dict[str, float | int | None]],
    args: argparse.Namespace,
) -> float:
    output_dir.mkdir(parents=True, exist_ok=True)
    metric_rows = [asdict(metric) for metric in metrics]
    pd.DataFrame(metric_rows).to_csv(output_dir / "metrics.csv", index=False)
    sample_counts = {
        f"{dataset}:{split}": int(count)
        for (dataset, split), count in rows.groupby(["original_source_dataset", "split"]).size().items()
    }

    test_by_variant = {metric.variant: metric for metric in metrics if metric.split == "test"}
    baseline_test = test_by_variant.get("baseline")
    adversarial_test = test_by_variant.get("adversarial")
    comparison = {}
    if baseline_test and adversarial_test:
        recall_delta = adversarial_test.abnormal_recall - baseline_test.abnormal_recall
        macro_f1_delta = adversarial_test.disease_macro_f1 - baseline_test.disease_macro_f1
        probe_delta = None
        if (
            baseline_test.dataset_probe_balanced_accuracy is not None
            and adversarial_test.dataset_probe_balanced_accuracy is not None
        ):
            probe_delta = adversarial_test.dataset_probe_balanced_accuracy - baseline_test.dataset_probe_balanced_accuracy
        invariance_gate_pass = probe_delta is not None and probe_delta <= 0.0
        comparison = {
            "adversarial_minus_baseline_abnormal_recall": recall_delta,
            "adversarial_minus_baseline_macro_f1": macro_f1_delta,
            "adversarial_minus_baseline_dataset_probe_balanced_accuracy": probe_delta,
            "disease_performance_gate_pass": bool(recall_delta >= -0.03),
            "invariance_gate_pass": bool(invariance_gate_pass),
            "overall_invariance_hypothesis_pass": bool(recall_delta >= -0.03 and invariance_gate_pass),
        }

    summary = {
        "input_mode": args.input_mode,
        "device": args.device,
        "dataset_loss_weight": args.dataset_loss_weight,
        "encoder_feature_dim": args.encoder_feature_dim,
        "dataset_feature_dropout": args.dataset_feature_dropout,
        "dataset_feature_noise_std": args.dataset_feature_noise_std,
        "dataset_feature_layer_norm": args.dataset_feature_layer_norm,
        "dataset_alignment_weight": args.dataset_alignment_weight,
        "dataset_coral_weight": args.dataset_coral_weight,
        "probe_focused_alignment_weight": args.probe_focused_alignment_weight,
        "probe_focused_coral_weight": args.probe_focused_coral_weight,
        "clean_probe_adversary_weight": args.clean_probe_adversary_weight,
        "tap_alignment_weight": args.tap_alignment_weight,
        "tap_coral_weight": args.tap_coral_weight,
        "mixstyle_prob": args.mixstyle_prob,
        "mixstyle_alpha": args.mixstyle_alpha,
        "mixstyle_layer": args.mixstyle_layer,
        "selective_consistency_weight": args.selective_consistency_weight,
        "spectral_mix_prob": args.spectral_mix_prob,
        "spectral_mix_strength": args.spectral_mix_strength,
        "spectral_low_freq_fraction": args.spectral_low_freq_fraction,
        "phase_mix_prob": args.phase_mix_prob,
        "phase_mix_strength": args.phase_mix_strength,
        "phase_low_freq_fraction": args.phase_low_freq_fraction,
        "style_aug_prob": args.style_aug_prob,
        "style_baseline_wander_scale": args.style_baseline_wander_scale,
        "style_drift_scale": args.style_drift_scale,
        "style_gain_std": args.style_gain_std,
        "style_noise_std": args.style_noise_std,
        "dataset_head_bias_init": args.dataset_head_bias_init,
        "adversarial_strength": args.adversarial_strength,
        "learning_rate": args.learning_rate,
        "target_names": TARGET_NAMES,
        "target_distribution": target_distribution,
        "dataset_names": dataset_names,
        "lambda_schedule": lambda_schedule,
        "sample_counts": sample_counts,
        "excluded_from_lead1_v1": {
            "sph-ecg": "lead_order_source is not verified in the unified manifest",
        },
        "primary_metric": "abnormal_recall",
        "primary_metric_variant": "adversarial" if "adversarial" in args.variants else args.variants[-1],
        "primary_metric_split": "test",
        "baseline_vs_adversarial": comparison,
        "metrics": metric_rows,
    }
    primary_variant = summary["primary_metric_variant"]
    primary = next(
        metric.abnormal_recall
        for metric in metrics
        if metric.variant == primary_variant and metric.split == "test"
    )
    summary["primary_metric_value"] = primary
    with (output_dir / "summary.json").open("w") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    slim_columns = [
        "original_source_dataset",
        "record_id",
        "patient_id",
        "split_group_id",
        "source_path",
        "source_format",
        "sampling_rate_hz",
        "num_samples",
        "lead_order",
        "lead_order_source",
        "normalized_labels",
        "split_balance_group",
        "split",
        "lead_i_index",
    ]
    rows[slim_columns].to_csv(output_dir / "selected_manifest_rows.csv", index=False)
    return float(primary)


def main() -> None:
    args = parse_args()
    set_seed(args.seed)
    if args.device == "auto":
        device = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    else:
        if args.device == "mps" and not torch.backends.mps.is_available():
            raise SystemExit("MPS requested but torch.backends.mps is not available")
        device = torch.device(args.device)
    target_samples = args.sampling_rate_hz * args.duration_sec
    rows = select_manifest_rows(
        args.manifest,
        seed=args.seed,
        limits={"train": args.max_train_samples, "val": args.max_val_samples, "test": args.max_test_samples},
    )
    if rows.empty:
        raise SystemExit("no eligible rows selected for Lead I experiment")
    target_distribution = validate_target_distribution(rows)
    loaders, dataset_names = build_loaders(rows, target_samples=target_samples, batch_size=args.batch_size)
    base_model = LeadOneCnn(
        num_targets=len(TARGET_NAMES),
        num_datasets=len(dataset_names),
        feature_dim=args.encoder_feature_dim,
        dataset_feature_dropout=args.dataset_feature_dropout,
        dataset_feature_noise_std=args.dataset_feature_noise_std,
        dataset_feature_layer_norm=args.dataset_feature_layer_norm,
        mixstyle_prob=args.mixstyle_prob,
        mixstyle_alpha=args.mixstyle_alpha,
        mixstyle_layer=args.mixstyle_layer,
    )
    args.initial_state_dict = {key: value.detach().clone() for key, value in base_model.state_dict().items()}
    all_metrics: list[VariantMetrics] = []
    lambda_schedule: dict[str, dict[str, float | int | None]] = {}
    for variant in args.variants:
        _model, variant_metrics, lambda_values = train_variant(variant, loaders, len(dataset_names), args, device)
        all_metrics.extend(variant_metrics)
        lambda_schedule[variant] = {
            "schedule_type": "linear" if variant == "adversarial" else "none",
            "steps": len(lambda_values),
            "max_strength": args.adversarial_strength if variant == "adversarial" else 0.0,
            "min": min(lambda_values) if lambda_values else None,
            "max": max(lambda_values) if lambda_values else None,
            "mean": float(np.mean(lambda_values)) if lambda_values else None,
            "first_values": lambda_values[:5],
            "last_values": lambda_values[-5:],
        }
    primary = write_outputs(
        args.output_dir,
        all_metrics,
        rows,
        dataset_names,
        target_distribution,
        lambda_schedule,
        args,
    )
    print(f"METRIC abnormal_recall={primary:.6f}")


if __name__ == "__main__":
    main()
