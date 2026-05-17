from typing import Any

from backend.schemas.ecg import AppleWatchEcgInferRequest, AppleWatchEcgRecord
from backend.services.lead1_ecg_runtime import extract_voltage_array, get_lead1_ecg_runtime

ECG_EXPERIMENTAL_CAVEAT = "Predictions are experimental and not clinically validated."


class AppleWatchEcgInputError(ValueError):
    pass


class AppleWatchEcgModelUnavailable(RuntimeError):
    pass


def infer_apple_watch_ecg(payload: AppleWatchEcgInferRequest) -> dict[str, Any]:
    record_index, record = _select_record(payload)
    voltage_values = [measurement.voltage for measurement in record.voltage_measurements]

    try:
        waveform = extract_voltage_array(voltage_values)
    except (TypeError, ValueError) as exc:
        raise AppleWatchEcgInputError("Invalid Apple Watch ECG payload.") from exc

    try:
        runtime = get_lead1_ecg_runtime()
        predictions = runtime.infer(
            waveform,
            source_hz=record.sampling_frequency,
            window_policy=payload.window_policy,
            threshold=payload.threshold,
        )
    except ValueError as exc:
        raise AppleWatchEcgInputError("Invalid Apple Watch ECG payload.") from exc
    except Exception as exc:
        raise AppleWatchEcgModelUnavailable from exc

    return {
        "record_index": record_index,
        "record_metadata": _record_metadata(record),
        "window_policy": payload.window_policy,
        "threshold": payload.threshold,
        "target_samples": runtime.target_samples,
        "checkpoint_sampling_rate_hz": runtime.sampling_rate_hz,
        "duration_sec": runtime.duration_sec,
        "target_names": runtime.target_names,
        "predictions": predictions,
        "caveat": ECG_EXPERIMENTAL_CAVEAT,
    }


def _select_record(payload: AppleWatchEcgInferRequest) -> tuple[int, AppleWatchEcgRecord]:
    if payload.ecg_record is not None:
        return 0, payload.ecg_record

    if payload.health_export is None or payload.record_index is None:
        raise AppleWatchEcgInputError("Invalid Apple Watch ECG payload.")

    records = payload.health_export.data.ecg
    if payload.record_index >= len(records):
        raise AppleWatchEcgInputError("Invalid recordIndex for ECG data.")
    return payload.record_index, records[payload.record_index]


def _record_metadata(record: AppleWatchEcgRecord) -> dict[str, Any]:
    return {
        "start": record.start,
        "end": record.end,
        "classification": record.classification,
        "averageHeartRate": record.average_heart_rate,
        "samplingFrequency": record.sampling_frequency,
        "numberOfVoltageMeasurements": record.number_of_voltage_measurements,
        "source": record.source,
    }
