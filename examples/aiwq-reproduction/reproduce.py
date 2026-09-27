#!/usr/bin/env python3
"""Offline, bounded reproduction of two published AI Weather Quest tas slices.

RPSS follows the public ECMWF definition; observation classification calls the
official AI-WQ-package. This example is separate from the receipt verifier API.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path, PurePosixPath
import platform
import tarfile
import tempfile

import numpy as np
import xarray as xr
from AI_WQ_package.forecast_evaluation import conditional_obs_probs

HERE = Path(__file__).resolve().parent
TOLERANCE = 0.0005
CASES = (("20251127", 1, 44), ("20251120", 2, 49))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def unpack_verified(archive, manifest, destination):
    """Extract only declared regular files, checking paths, size and SHA-256."""
    all_records = {entry["path"]: entry for entry in manifest["files"]}
    if len(all_records) != len(manifest["files"]) or len(all_records) != 96:
        raise ValueError("Expected 96 unique input files")
    for name, entry in all_records.items():
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or str(path) != name:
            raise ValueError("Unsafe input path")
        if not 0 < entry["bytes"] <= 4_000_000:
            raise ValueError("Unexpected input size")
    records = {name: entry for name, entry in all_records.items() if entry.get("archive_member", True)}
    seen = set()
    with tarfile.open(archive, "r:gz") as stream:
        for member in stream:
            if not member.isfile() or member.name not in records or member.name in seen:
                raise ValueError("Unexpected, duplicate or non-regular archive member")
            entry = records[member.name]
            if member.size != entry["bytes"]:
                raise ValueError("Input size mismatch: " + member.name)
            payload = stream.extractfile(member).read(entry["bytes"] + 1)
            if hashlib.sha256(payload).hexdigest() != entry["sha256"]:
                raise ValueError("Input SHA-256 mismatch: " + member.name)
            target = destination / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            seen.add(member.name)
    if seen != set(records):
        raise ValueError("Missing declared archive inputs")


def read_field(path):
    with xr.open_dataset(path, engine="netcdf4") as dataset:
        fields = [name for name in dataset.data_vars if name != "time_bnds"
                  and np.issubdtype(dataset[name].dtype, np.number)]
        if len(fields) != 1:
            raise ValueError("Expected one numeric field: " + path.name)
        field = dataset[fields[0]].load()
    if "time" in field.dims:
        if field.sizes["time"] != 1:
            raise ValueError("Expected a single verification interval")
        field = field.squeeze("time", drop=True)
    field = field.rename({a: b for a, b in (("lat", "latitude"), ("lon", "longitude"))
                          if a in field.dims})
    for dimension, expected in (("latitude", np.arange(90, -90.1, -1.5)),
                                ("longitude", np.arange(0, 360, 1.5))):
        if dimension not in field.coords or not np.array_equal(field[dimension], expected):
            raise ValueError("Unexpected coordinate grid: " + path.name)
    return field


def as_cube(field):
    dimensions = [name for name in field.dims if name in ("quintile", "quantile")]
    if len(dimensions) != 1:
        raise ValueError("Expected one ordered quintile dimension")
    q = dimensions[0]
    if not np.all(np.diff(field[q].values) > 0):
        raise ValueError("Unordered quintile coordinate")
    result = np.asarray(field.transpose(q, "latitude", "longitude"), dtype=np.float64)
    if result.shape != (5, 121, 240):
        raise ValueError("Unexpected probability grid")
    return result


def calculate_rpss(forecast, observation, land_mask):
    """1 - area-weighted forecast RPS / area-weighted uniform-reference RPS.

    Preserve submitted probabilities, including NaNs and normalization drift.
    ECMWF uses a skip-NaN category sum and land >= 0.5 for tas. Float32 latitude
    weights match the official mask's coordinate precision.
    """
    if np.isinf(forecast).any():
        raise ValueError("Infinite probabilities")
    finite = forecast[np.isfinite(forecast)]
    if not finite.size or finite.min() < -1e-4 or finite.max() > 1.0001:
        raise ValueError("Invalid probability range")
    cumulative_observation = np.cumsum(observation, axis=0)
    forecast_rps = np.nansum((np.cumsum(forecast, axis=0) - cumulative_observation) ** 2, axis=0)
    reference_cdf = np.cumsum(np.full(5, 0.2))[:, None, None]
    reference_rps = np.nansum((reference_cdf - cumulative_observation) ** 2, axis=0)
    selected = (np.asarray(land_mask) >= 0.5) & ~np.isnan(observation).all(axis=0)
    if not selected.any():
        raise ValueError("Empty scoring domain")
    if not np.isfinite(forecast[:, selected]).any():
        raise ValueError("Forecast entirely missing on the scoring domain")
    latitude_weights = np.cos(np.deg2rad(np.asarray(land_mask.latitude, dtype=np.float32)))
    weights = np.broadcast_to(latitude_weights[:, None], selected.shape)
    weights = weights / weights.mean()
    numerator = np.sum((weights * forecast_rps)[selected])
    denominator = np.sum((weights * reference_rps)[selected])
    if not np.isfinite(denominator) or denominator <= 0:
        raise ValueError("Invalid climatological reference")
    value = float(1 - numerator / denominator)
    if not math.isfinite(value):
        raise ValueError("Non-finite score")
    return value


def compare(computed, reference, expected_count):
    """Use full precision, exact coverage, and finite values; never a silent join."""
    missing_computed = sorted(set(reference) - set(computed))
    missing_reference = sorted(set(computed) - set(reference))
    rows = []
    for model in sorted(set(computed) & set(reference)):
        ours, theirs = float(computed[model]), float(reference[model])
        if not math.isfinite(ours) or not math.isfinite(theirs):
            raise ValueError("Non-finite score in comparison")
        rows.append({"model": model, "computed": ours, "published": theirs,
                     "absolute_difference": abs(ours - theirs)})
    maximum = max((row["absolute_difference"] for row in rows), default=None)
    coverage = (len(computed) == len(reference) == len(rows) == expected_count
                and expected_count > 0 and not missing_computed and not missing_reference)
    accepted = coverage and maximum is not None and maximum <= TOLERANCE
    return {"accepted": accepted, "coverage_complete": coverage,
            "expected_count": expected_count, "compared": len(rows),
            "missing_computed": missing_computed, "missing_reference": missing_reference,
            "max_absolute_difference": maximum, "tolerance": TOLERANCE, "rows": rows}


def run(archive, manifest_path, references_path, auxiliary_dir):
    manifest = json.loads(manifest_path.read_text())
    references = json.loads(references_path.read_text())
    reports, values = [], {}
    with tempfile.TemporaryDirectory(prefix="aiwq-reproduction-") as temporary:
        root = Path(temporary)
        unpack_verified(archive, manifest, root)
        auxiliaries = [entry for entry in manifest["files"] if entry["role"] != "forecast"]
        if len(auxiliaries) != 3 or {entry["role"] for entry in auxiliaries} != {"climatology", "observation", "land_mask"}:
            raise ValueError("Expected exactly three auxiliary roles")
        roles = {}
        for entry in auxiliaries:
            path = auxiliary_dir / Path(entry["path"]).name
            if not path.is_file() or path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
                raise ValueError("Missing or mismatched authorized auxiliary input: " + path.name)
            roles[entry["role"]] = path
        climatology, observed = read_field(roles["climatology"]), read_field(roles["observation"])
        observed_categories = as_cube(conditional_obs_probs(observed, climatology))
        mask = read_field(roles["land_mask"]).transpose("latitude", "longitude")
        quality = []
        for date, window, count in CASES:
            key = f"{date}-p{window}"
            scores = {}
            for entry in manifest["files"]:
                if (entry.get("initialization"), entry.get("window")) != (date, window):
                    continue
                if entry.get("target_week") != "20251215" or entry.get("variable") != "tas":
                    raise ValueError("Unexpected case metadata")
                if entry["model"] in scores:
                    raise ValueError("Duplicate model in case")
                forecast = as_cube(read_field(root / entry["path"]))
                valid = ~np.isnan(forecast).all(axis=0)
                drift = float(np.max(np.abs(np.nansum(forecast, axis=0)[valid] - 1))) if valid.any() else None
                if drift is not None and drift > 1e-4:
                    quality.append({"case": key, "model": entry["model"], "max_normalization_drift": drift})
                scores[entry["model"]] = calculate_rpss(forecast, observed_categories, mask)
            values[key] = scores
            reports.append({"case": key, "target_week": "20251215",
                            **compare(scores, references["scores"][key], count)})
    negative = compare(values["20251120-p2"], references["scores"]["20251120-p1"], 49)
    negative["case"] = "20251120-p2 compared with 20251120-p1 reference"
    negative["expected_rejection_observed"] = (negative["coverage_complete"] and not negative["accepted"]
                                               and negative["max_absolute_difference"] > TOLERANCE)
    passed = all(row["accepted"] for row in reports) and negative["expected_rejection_observed"]
    return {"status": "PASS" if passed else "FAIL", "cases": reports, "negative_control": negative,
            "normalization_notes_scored_without_modification": quality,
            "scope": "Two historical tas slices sharing one target week; no Omytea predictive skill claim.",
            "data_access": "Three unchanged ECMWF auxiliary files are bundled under CC BY 4.0; the 93 participant forecasts are downloaded from ECMWF. All input bytes are hash-verified.",
            "observation_classification": "Official AI-WQ-package conditional_obs_probs; not independent of that helper.",
            "environment": {"python": platform.python_version(), "platform": platform.platform(),
                            "packages": {name: importlib.metadata.version(name)
                                         for name in ("numpy", "xarray", "netCDF4", "AI-WQ-package")}},
            "sha256": {"code": sha256(__file__), "archive": sha256(archive),
                       "manifest": sha256(manifest_path), "references": sha256(references_path)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("reproduction-result.json"))
    parser.add_argument("--auxiliary-dir", type=Path, default=HERE / "auxiliary",
                        help="Directory containing the three hash-pinned official files; defaults to the bundled auxiliary directory.")
    args = parser.parse_args()
    try:
        report = run(HERE / "inputs.tar.gz", HERE / "input-manifest.json", HERE / "references.json", args.auxiliary_dir)
    except (ValueError, OSError, KeyError, tarfile.TarError) as error:
        report = {"status": "FAIL", "error": f"{type(error).__name__}: {error}"}
    args.out.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(report["status"] + ": " + str(args.out))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
