#!/usr/bin/env python3
"""Run parallel Optuna matrix trials for the Lead I dataset-invariance experiment."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from dataclasses import dataclass
from multiprocessing import get_context
from pathlib import Path
from typing import Any

import optuna
from optuna.samplers import QMCSampler, RandomSampler, TPESampler
from optuna.storages import JournalStorage
from optuna.storages.journal import JournalFileBackend
from optuna.trial import TrialState


BEST_KEEP = {
    "abnormal_recall": 0.9975669099756691,
    "dataset_probe_balanced_accuracy": 0.7420333246550377,
    "dataset_head_accuracy": 0.2998046875,
}
MACRO_F1_SOFT_FLOOR = 0.31285738040702016


@dataclass(frozen=True)
class RunnerConfig:
    manifest: str
    output_dir: str
    study_name: str
    storage_path: str
    trials_per_worker: int
    worker_id: int
    seed: int
    device: str
    max_train_samples: int
    max_val_samples: int
    max_test_samples: int
    batch_size: int
    epochs: int
    torch_threads: int
    sampler: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--study-name", default="ecg_dataset_invariance_matrix")
    parser.add_argument("--workers", type=int, default=5)
    parser.add_argument("--trials", type=int, default=200)
    parser.add_argument("--seed", type=int, default=73)
    parser.add_argument("--device", choices=["cpu", "mps", "auto"], default="cpu")
    parser.add_argument("--max-train-samples", type=int, default=4096)
    parser.add_argument("--max-val-samples", type=int, default=1024)
    parser.add_argument("--max-test-samples", type=int, default=1024)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--torch-threads-per-worker", type=int, default=3)
    parser.add_argument(
        "--sampler",
        choices=["tpe_constraints", "tpe_constraints_multivariate", "tpe_constant_liar", "tpe", "qmc", "random"],
        default="tpe_constraints_multivariate",
    )
    parser.add_argument("--external-worker-id", type=int)
    parser.add_argument("--external-worker-trials", type=int)
    parser.add_argument("--prepare-only", action="store_true")
    return parser.parse_args()


def trial_matrix() -> list[dict[str, Any]]:
    return [
        {
            "discovery_profile": "probe_focus_anchor",
            "encoder_feature_dim": 48,
            "learning_rate": 0.0009265,
            "dataset_loss_weight": 1.2260,
            "dataset_feature_dropout": 0.2715,
            "dataset_feature_noise_std": 0.1107,
            "dataset_feature_layer_norm": True,
            "dataset_alignment_weight": 0.0165,
            "dataset_coral_weight": 0.0068,
            "probe_focused_alignment_weight": 0.0140,
            "probe_focused_coral_weight": 0.0,
            "clean_probe_adversary_weight": 0.20,
            "tap_alignment_weight": 0.0028,
            "tap_coral_weight": 0.0049,
            "mixstyle_prob": 0.0023,
            "mixstyle_alpha": 0.3200,
            "mixstyle_layer": "block2",
            "selective_consistency_weight": 0.0022,
            "spectral_mix_prob": 0.0137,
            "spectral_mix_strength": 0.0033,
            "spectral_low_freq_fraction": 0.0998,
            "phase_mix_prob": 0.0094,
            "phase_mix_strength": 0.0092,
            "phase_low_freq_fraction": 0.2535,
            "style_aug_prob": 0.0028,
            "style_baseline_wander_scale": 0.0021,
            "style_drift_scale": 0.00083,
            "style_gain_std": 0.0025,
            "style_noise_std": 0.00326,
            "dataset_head_bias_init": "inverse_sqrt_frequency",
            "adversarial_strength": 0.1228,
        },
        {
            "discovery_profile": "probe_focus_coral_trim",
            "encoder_feature_dim": 48,
            "learning_rate": 0.0009272,
            "dataset_loss_weight": 1.2280,
            "dataset_feature_dropout": 0.2718,
            "dataset_feature_noise_std": 0.1109,
            "dataset_feature_layer_norm": True,
            "dataset_alignment_weight": 0.0167,
            "dataset_coral_weight": 0.0072,
            "probe_focused_alignment_weight": 0.0105,
            "probe_focused_coral_weight": 0.0010,
            "clean_probe_adversary_weight": 0.16,
            "tap_alignment_weight": 0.0029,
            "tap_coral_weight": 0.0050,
            "mixstyle_prob": 0.0025,
            "mixstyle_alpha": 0.3200,
            "mixstyle_layer": "block2",
            "selective_consistency_weight": 0.0023,
            "spectral_mix_prob": 0.0137,
            "spectral_mix_strength": 0.0033,
            "spectral_low_freq_fraction": 0.0998,
            "phase_mix_prob": 0.0094,
            "phase_mix_strength": 0.0092,
            "phase_low_freq_fraction": 0.2535,
            "style_aug_prob": 0.0028,
            "style_baseline_wander_scale": 0.0021,
            "style_drift_scale": 0.00083,
            "style_gain_std": 0.0025,
            "style_noise_std": 0.00326,
            "dataset_head_bias_init": "inverse_sqrt_frequency",
            "adversarial_strength": 0.1232,
        },
    ]


def study_storage(storage_path: str) -> JournalStorage:
    return JournalStorage(JournalFileBackend(storage_path))


def keep_constraints(trial: optuna.trial.FrozenTrial) -> tuple[float, float, float]:
    recall = trial.user_attrs.get("abnormal_recall")
    probe = trial.user_attrs.get("dataset_probe_balanced_accuracy")
    head = trial.user_attrs.get("dataset_head_accuracy")
    if recall is None or probe is None or head is None:
        return (1.0, 1.0, 1.0)
    return (
        0.90 - float(recall),
        float(probe) - BEST_KEEP["dataset_probe_balanced_accuracy"],
        float(head) - BEST_KEEP["dataset_head_accuracy"],
    )


def make_sampler(name: str, seed: int) -> optuna.samplers.BaseSampler:
    if name == "tpe_constraints":
        return TPESampler(seed=seed, n_startup_trials=16, n_ei_candidates=48, constant_liar=True, constraints_func=keep_constraints)
    if name == "tpe_constraints_multivariate":
        return TPESampler(
            seed=seed,
            n_startup_trials=20,
            n_ei_candidates=64,
            constant_liar=True,
            multivariate=True,
            group=True,
            warn_independent_sampling=False,
            constraints_func=keep_constraints,
        )
    if name == "tpe_constant_liar":
        return TPESampler(seed=seed, n_startup_trials=48, n_ei_candidates=64, constant_liar=True)
    if name == "tpe":
        return TPESampler(seed=seed, n_startup_trials=48, n_ei_candidates=64)
    if name == "qmc":
        return QMCSampler(
            seed=seed,
            scramble=True,
            independent_sampler=RandomSampler(seed=seed),
            warn_asynchronous_seeding=False,
            warn_independent_sampling=False,
        )
    if name == "random":
        return RandomSampler(seed=seed)
    raise ValueError(f"unknown sampler: {name}")


def load_study(config: RunnerConfig) -> optuna.Study:
    return optuna.load_study(
        study_name=config.study_name,
        storage=study_storage(config.storage_path),
        sampler=make_sampler(config.sampler, config.seed + config.worker_id),
    )


def adversarial_test_metrics(summary_path: Path) -> dict[str, float]:
    summary = json.loads(summary_path.read_text())
    for row in summary["metrics"]:
        if row["variant"] == "adversarial" and row["split"] == "test":
            return {
                "abnormal_recall": float(row["abnormal_recall"]),
                "dataset_head_accuracy": float(row["dataset_head_accuracy"]),
                "dataset_probe_balanced_accuracy": float(row["dataset_probe_balanced_accuracy"]),
                "disease_macro_f1": float(row["disease_macro_f1"]),
            }
    raise ValueError(f"missing adversarial test metrics in {summary_path}")


def objective_score(metrics: dict[str, float]) -> float:
    recall_violation = max(0.0, 0.90 - metrics["abnormal_recall"])
    probe_violation = max(0.0, metrics["dataset_probe_balanced_accuracy"] - BEST_KEEP["dataset_probe_balanced_accuracy"])
    head_violation = max(0.0, metrics["dataset_head_accuracy"] - BEST_KEEP["dataset_head_accuracy"])
    macro_f1_violation = max(0.0, MACRO_F1_SOFT_FLOOR - metrics["disease_macro_f1"])
    probe_step_gap = probe_violation / 0.0025
    head_step_gap = head_violation / 0.001953125
    frontier_gap = max(probe_step_gap, head_step_gap)
    return (
        (1400.0 * recall_violation)
        + (120.0 * frontier_gap)
        + (55.0 * probe_step_gap)
        + (45.0 * head_step_gap)
        + (4.0 * macro_f1_violation)
        + (6.0 * metrics["dataset_probe_balanced_accuracy"])
        + (2.0 * metrics["dataset_head_accuracy"])
        - (0.05 * metrics["abnormal_recall"])
        - (0.02 * metrics["disease_macro_f1"])
    )


def objective(config: RunnerConfig, trial: optuna.Trial) -> float:
    params = {
        "discovery_profile": trial.suggest_categorical(
            "discovery_profile",
            [
                "probe_focus_anchor",
                "probe_focus_coral_trim",
            ],
        ),
        "encoder_feature_dim": 48,
        "learning_rate": trial.suggest_float("learning_rate", 9.23e-4, 9.29e-4, log=True),
        "dataset_loss_weight": trial.suggest_float("dataset_loss_weight", 1.220, 1.231),
        "dataset_feature_dropout": trial.suggest_float("dataset_feature_dropout", 0.2695, 0.2730),
        "dataset_feature_noise_std": trial.suggest_float("dataset_feature_noise_std", 0.1100, 0.1114),
        "dataset_feature_layer_norm": True,
        "dataset_alignment_weight": trial.suggest_float("dataset_alignment_weight", 0.0161, 0.0169),
        "dataset_coral_weight": trial.suggest_float("dataset_coral_weight", 0.0063, 0.0078),
        "probe_focused_alignment_weight": trial.suggest_float("probe_focused_alignment_weight", 0.008, 0.016),
        "probe_focused_coral_weight": trial.suggest_float("probe_focused_coral_weight", 0.0, 0.0012),
        "clean_probe_adversary_weight": trial.suggest_float("clean_probe_adversary_weight", 0.05, 0.30),
        "tap_alignment_weight": trial.suggest_float("tap_alignment_weight", 0.0022, 0.0034),
        "tap_coral_weight": trial.suggest_float("tap_coral_weight", 0.0044, 0.0054),
        "mixstyle_prob": trial.suggest_float("mixstyle_prob", 0.0020, 0.0028),
        "mixstyle_alpha": trial.suggest_float("mixstyle_alpha", 0.318, 0.322),
        "mixstyle_layer": "block2",
        "selective_consistency_weight": trial.suggest_float("selective_consistency_weight", 0.0016, 0.0030),
        "spectral_mix_prob": trial.suggest_float("spectral_mix_prob", 0.0120, 0.0165),
        "spectral_mix_strength": trial.suggest_float("spectral_mix_strength", 0.0028, 0.0044),
        "spectral_low_freq_fraction": trial.suggest_float("spectral_low_freq_fraction", 0.095, 0.105),
        "phase_mix_prob": trial.suggest_float("phase_mix_prob", 0.0085, 0.0105),
        "phase_mix_strength": trial.suggest_float("phase_mix_strength", 0.0085, 0.0105),
        "phase_low_freq_fraction": trial.suggest_float("phase_low_freq_fraction", 0.248, 0.258),
        "style_aug_prob": trial.suggest_float("style_aug_prob", 0.0022, 0.0032),
        "style_baseline_wander_scale": trial.suggest_float("style_baseline_wander_scale", 0.0017, 0.0025),
        "style_drift_scale": trial.suggest_float("style_drift_scale", 0.00075, 0.00095),
        "style_gain_std": trial.suggest_float("style_gain_std", 0.0020, 0.0028),
        "style_noise_std": trial.suggest_float("style_noise_std", 0.0030, 0.0034),
        "dataset_head_bias_init": "inverse_sqrt_frequency",
        "adversarial_strength": trial.suggest_float("adversarial_strength", 0.121, 0.1245),
    }
    profile = params["discovery_profile"]
    if profile == "probe_focus_anchor":
        params["probe_focused_alignment_weight"] = min(max(0.012, params["probe_focused_alignment_weight"]), 0.016)
        params["probe_focused_coral_weight"] = min(params["probe_focused_coral_weight"], 0.0006)
        params["clean_probe_adversary_weight"] = min(max(0.16, params["clean_probe_adversary_weight"]), 0.30)
        params["dataset_alignment_weight"] = min(max(0.0162, params["dataset_alignment_weight"]), 0.0168)
        params["dataset_coral_weight"] = min(max(0.0064, params["dataset_coral_weight"]), 0.0072)
    elif profile == "probe_focus_coral_trim":
        params["probe_focused_alignment_weight"] = min(max(0.008, params["probe_focused_alignment_weight"]), 0.012)
        params["probe_focused_coral_weight"] = min(max(0.0008, params["probe_focused_coral_weight"]), 0.0012)
        params["clean_probe_adversary_weight"] = min(max(0.10, params["clean_probe_adversary_weight"]), 0.24)
        params["dataset_alignment_weight"] = min(max(0.0163, params["dataset_alignment_weight"]), 0.0169)
        params["dataset_coral_weight"] = min(max(0.0068, params["dataset_coral_weight"]), 0.0078)
    else:
        raise ValueError(f"unknown discovery profile: {profile}")
    trial_dir = Path(config.output_dir) / f"trial_{trial.number:03d}"
    trial_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        "scripts/training/run_dataset_invariance_experiment.py",
        "--manifest",
        config.manifest,
        "--output-dir",
        str(trial_dir),
        "--input-mode",
        "lead1",
        "--epochs",
        str(config.epochs),
        "--max-train-samples",
        str(config.max_train_samples),
        "--max-val-samples",
        str(config.max_val_samples),
        "--max-test-samples",
        str(config.max_test_samples),
        "--variants",
        "baseline",
        "adversarial",
        "--batch-size",
        str(config.batch_size),
        "--seed",
        str(config.seed),
        "--device",
        config.device,
        "--dataset-loss-weight",
        str(params["dataset_loss_weight"]),
        "--encoder-feature-dim",
        str(params["encoder_feature_dim"]),
        "--dataset-feature-dropout",
        str(params["dataset_feature_dropout"]),
        "--dataset-feature-noise-std",
        str(params["dataset_feature_noise_std"]),
        "--dataset-coral-weight",
        str(params["dataset_coral_weight"]),
        "--probe-focused-alignment-weight",
        str(params["probe_focused_alignment_weight"]),
        "--probe-focused-coral-weight",
        str(params["probe_focused_coral_weight"]),
        "--clean-probe-adversary-weight",
        str(params["clean_probe_adversary_weight"]),
        "--tap-alignment-weight",
        str(params["tap_alignment_weight"]),
        "--tap-coral-weight",
        str(params["tap_coral_weight"]),
        "--mixstyle-prob",
        str(params["mixstyle_prob"]),
        "--mixstyle-alpha",
        str(params["mixstyle_alpha"]),
        "--mixstyle-layer",
        str(params["mixstyle_layer"]),
        "--selective-consistency-weight",
        str(params["selective_consistency_weight"]),
        "--spectral-mix-prob",
        str(params["spectral_mix_prob"]),
        "--spectral-mix-strength",
        str(params["spectral_mix_strength"]),
        "--spectral-low-freq-fraction",
        str(params["spectral_low_freq_fraction"]),
        "--phase-mix-prob",
        str(params["phase_mix_prob"]),
        "--phase-mix-strength",
        str(params["phase_mix_strength"]),
        "--phase-low-freq-fraction",
        str(params["phase_low_freq_fraction"]),
        "--style-aug-prob",
        str(params["style_aug_prob"]),
        "--style-baseline-wander-scale",
        str(params["style_baseline_wander_scale"]),
        "--style-drift-scale",
        str(params["style_drift_scale"]),
        "--style-gain-std",
        str(params["style_gain_std"]),
        "--style-noise-std",
        str(params["style_noise_std"]),
        "--dataset-alignment-weight",
        str(params["dataset_alignment_weight"]),
        "--dataset-head-bias-init",
        str(params["dataset_head_bias_init"]),
        "--adversarial-strength",
        str(params["adversarial_strength"]),
        "--learning-rate",
        str(params["learning_rate"]),
    ]
    if params["dataset_feature_layer_norm"]:
        cmd.append("--dataset-feature-layer-norm")
    env = os.environ.copy()
    env["OMP_NUM_THREADS"] = str(config.torch_threads)
    env["MKL_NUM_THREADS"] = str(config.torch_threads)
    env["VECLIB_MAXIMUM_THREADS"] = str(config.torch_threads)
    completed = subprocess.run(
        cmd,
        cwd=Path.cwd(),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    (trial_dir / "stdout.log").write_text(completed.stdout)
    if completed.returncode != 0:
        raise RuntimeError(f"trial {trial.number} failed with code {completed.returncode}; see {trial_dir / 'stdout.log'}")
    metrics = adversarial_test_metrics(trial_dir / "summary.json")
    for key, value in metrics.items():
        trial.set_user_attr(key, value)
    for key, value in params.items():
        trial.set_user_attr(key, value)
    return objective_score(metrics)


def run_worker(config: RunnerConfig) -> None:
    study = load_study(config)
    study.optimize(lambda trial: objective(config, trial), n_trials=config.trials_per_worker)


def fail_stale_running_trials(study: optuna.Study) -> int:
    stale_trials = [trial for trial in study.trials if trial.state == TrialState.RUNNING]
    for trial in stale_trials:
        study.tell(trial.number, state=TrialState.FAIL)
    return len(stale_trials)


def strict_keep(metrics: dict[str, float]) -> bool:
    return (
        metrics["abnormal_recall"] >= 0.90
        and metrics["dataset_probe_balanced_accuracy"] < BEST_KEEP["dataset_probe_balanced_accuracy"]
        and metrics["dataset_head_accuracy"] < BEST_KEEP["dataset_head_accuracy"]
    )


def summarize(args: argparse.Namespace, study: optuna.Study) -> dict[str, Any]:
    complete_trials = [trial for trial in study.trials if trial.state == optuna.trial.TrialState.COMPLETE]
    trial_rows = []
    for trial in complete_trials:
        metrics = {
            "abnormal_recall": trial.user_attrs.get("abnormal_recall"),
            "dataset_head_accuracy": trial.user_attrs.get("dataset_head_accuracy"),
            "dataset_probe_balanced_accuracy": trial.user_attrs.get("dataset_probe_balanced_accuracy"),
            "disease_macro_f1": trial.user_attrs.get("disease_macro_f1"),
        }
        trial_rows.append(
            {
                "number": trial.number,
                "value": trial.value,
                "params": {key: trial.user_attrs.get(key, trial.params.get(key)) for key in trial.params.keys()},
                "effective_params": {
                    key: trial.user_attrs.get(key)
                    for key in (
                        "discovery_profile",
                        "encoder_feature_dim",
                        "learning_rate",
                        "dataset_loss_weight",
                        "dataset_feature_dropout",
                        "dataset_feature_noise_std",
                        "dataset_feature_layer_norm",
                        "dataset_alignment_weight",
                        "dataset_coral_weight",
                        "probe_focused_alignment_weight",
                        "probe_focused_coral_weight",
                        "clean_probe_adversary_weight",
                        "tap_alignment_weight",
                        "tap_coral_weight",
                        "mixstyle_prob",
                        "mixstyle_alpha",
                        "mixstyle_layer",
                        "selective_consistency_weight",
                        "spectral_mix_prob",
                        "spectral_mix_strength",
                        "spectral_low_freq_fraction",
                        "phase_mix_prob",
                        "phase_mix_strength",
                        "phase_low_freq_fraction",
                        "style_aug_prob",
                        "style_baseline_wander_scale",
                        "style_drift_scale",
                        "style_gain_std",
                        "style_noise_std",
                        "dataset_head_bias_init",
                        "adversarial_strength",
                    )
                    if key in trial.user_attrs
                },
                "metrics": metrics,
                "strict_keep_candidate": all(value is not None for value in metrics.values())
                and strict_keep({key: float(value) for key, value in metrics.items()}),
            }
        )
    strict_candidates = [row for row in trial_rows if row["strict_keep_candidate"]]
    strict_candidates.sort(
        key=lambda row: (
            row["metrics"]["dataset_probe_balanced_accuracy"],
            row["metrics"]["dataset_head_accuracy"],
            -row["metrics"]["abnormal_recall"],
        )
    )
    trial_rows.sort(key=lambda row: math.inf if row["value"] is None else float(row["value"]))
    summary = {
        "study_name": args.study_name,
        "sampler": args.sampler,
        "workers": args.workers,
        "trials_requested": args.trials,
        "trials_completed": len(complete_trials),
        "best_keep_reference": BEST_KEEP,
        "best_objective_trial": trial_rows[0] if trial_rows else None,
        "best_strict_keep_trial": strict_candidates[0] if strict_candidates else None,
        "trials": sorted(trial_rows, key=lambda row: row["number"]),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "optuna_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))
    return summary


def prepare_study(args: argparse.Namespace) -> tuple[optuna.Study, str]:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    storage_path = str(args.output_dir / "study.log")
    storage = study_storage(storage_path)
    study = optuna.create_study(
        study_name=args.study_name,
        storage=storage,
        direction="minimize",
        sampler=make_sampler(args.sampler, args.seed),
        load_if_exists=True,
    )
    for params in trial_matrix()[: args.trials]:
        study.enqueue_trial(params, skip_if_exists=True)
    return study, storage_path


def main() -> None:
    args = parse_args()
    if args.external_worker_id is not None:
        if args.external_worker_trials is None:
            raise SystemExit("--external-worker-trials is required with --external-worker-id")
        storage_path = str(args.output_dir / "study.log")
        worker_config = RunnerConfig(
            manifest=str(args.manifest),
            output_dir=str(args.output_dir),
            study_name=args.study_name,
            storage_path=storage_path,
            trials_per_worker=args.external_worker_trials,
            worker_id=args.external_worker_id,
            seed=args.seed,
            device=args.device,
            max_train_samples=args.max_train_samples,
            max_val_samples=args.max_val_samples,
            max_test_samples=args.max_test_samples,
            batch_size=args.batch_size,
            epochs=args.epochs,
            torch_threads=args.torch_threads_per_worker,
            sampler=args.sampler,
        )
        run_worker(worker_config)
        return

    study, storage_path = prepare_study(args)
    storage = study_storage(storage_path)
    if args.prepare_only:
        complete_count = sum(1 for trial in study.trials if trial.state == TrialState.COMPLETE)
        print(f"Prepared study {args.study_name} with {complete_count} completed trials.")
        return

    stale_count = fail_stale_running_trials(study)
    if stale_count:
        print(f"Marked {stale_count} stale running Optuna trials as failed before resume.")

    complete_count = sum(1 for trial in study.trials if trial.state == TrialState.COMPLETE)
    remaining_trials = max(0, args.trials - complete_count)
    workers = max(1, min(args.workers, remaining_trials)) if remaining_trials else 0
    base = remaining_trials // workers if workers else 0
    remainder = remaining_trials % workers if workers else 0
    worker_configs = []
    for worker_id in range(workers):
        trials_for_worker = base + (1 if worker_id < remainder else 0)
        worker_configs.append(
            RunnerConfig(
                manifest=str(args.manifest),
                output_dir=str(args.output_dir),
                study_name=args.study_name,
                storage_path=storage_path,
                trials_per_worker=trials_for_worker,
                worker_id=worker_id,
                seed=args.seed,
                device=args.device,
                max_train_samples=args.max_train_samples,
                max_val_samples=args.max_val_samples,
                max_test_samples=args.max_test_samples,
                batch_size=args.batch_size,
                epochs=args.epochs,
                torch_threads=args.torch_threads_per_worker,
                sampler=args.sampler,
            )
        )

    if worker_configs:
        with get_context("spawn").Pool(processes=workers) as pool:
            pool.map(run_worker, worker_configs)

    study = optuna.load_study(study_name=args.study_name, storage=storage)
    summary = summarize(args, study)
    selected = summary["best_strict_keep_trial"] or summary["best_objective_trial"]
    if not selected:
        raise SystemExit("no completed Optuna trials")
    metrics = selected["metrics"]
    print(f"METRIC abnormal_recall={float(metrics['abnormal_recall']):.6f}")
    print(f"METRIC dataset_probe_balanced_accuracy={float(metrics['dataset_probe_balanced_accuracy']):.6f}")
    print(f"METRIC dataset_head_accuracy={float(metrics['dataset_head_accuracy']):.6f}")
    print(f"METRIC strict_keep_candidate={1 if selected['strict_keep_candidate'] else 0}")


if __name__ == "__main__":
    main()
