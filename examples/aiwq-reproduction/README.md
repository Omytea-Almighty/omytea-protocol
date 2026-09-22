# Can we reproduce the published score?

Omytea scoring case · 22 September 2026

**Public code, input manifests and results; three official inputs require separate authorized access.**

We recomputed two historical AI Weather Quest temperature (`tas`) score slices from participant forecasts. Every participant in these two published slices is accounted for, and every recomputed score agrees within the official table's three-decimal rounding interval. A deliberately wrong forecast-window comparison is rejected by the same numerical check.

**This is evidence about our scoring implementation. It is not an Omytea forecast, competition ranking, ECMWF certification, or measured customer benefit.** The two slices share a single verification week; 93 comparisons cover 49 distinct team/model identifiers, not 93 independent forecast events.

| Initialization / window | Participant comparisons | Largest absolute RPSS difference | Result |
|---|---:|---:|---|
| 2025-11-27 / 1 | 44 of 44 | 0.000498224613 | Accept |
| 2025-11-20 / 2 | 49 of 49 | 0.000491796285 | Accept |
| Negative control: second slice against the 2025-11-20 / 1 reference | 49 of 49 | 0.210825792809 | Reject, as intended |

Both positive cases have zero missing participants on either side. The threshold is **0.0005**, evaluated on unrounded numbers. These are historical, selected instrument checks, not a held-out predictive-performance study. See the complete machine-readable [result](result.json), [reference slices](references.json), and [input manifest](input-manifest.json).

## Reproduce

**Data prerequisite:** the included downloader retrieves 93 public participant forecasts directly from ECMWF and checks every file against the manifest. Forecast binaries are not stored in Git. This package does **not** redistribute the three official auxiliary files. You must obtain those through ECMWF's authorized participant channel. Their precise redistribution permission has not been established by this project. This is therefore **not an anonymous, one-command, complete-data reproduction package**.

Follow the official [evaluation-data documentation](https://ecmwf-ai-weather-quest.readthedocs.io/en/latest/forecast_evaluation.html), using your own authorized access, and place these files in one directory:

- `land_sea_mask_1pt5DEG.nc`
- `tas_20yrCLIM_WEEKLYMEAN_quintiles_20251215.nc`
- `tas_obs_WEEKLYMEAN_20251215.nc`

The manifest records exact sizes and SHA-256 values. An upstream revision with different bytes fails verification; it is not silently substituted. We do not promise that the upstream service currently serves the same historical versions. Contact [AI Weather Quest support](mailto:aiweatherquest@ecmwf.int) for authorized access or version questions. Never put access credentials in this repository.

From this directory, with Python 3.12:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --require-hashes --only-binary=:all: -r requirements.lock
.venv/bin/python -m pip check
.venv/bin/python -m unittest -v test_acceptance test_download_inputs
.venv/bin/python download_inputs.py
.venv/bin/python reproduce.py --auxiliary-dir /path/to/authorized/files --out reproduction-result.json
```

The downloader needs about 92 MB of public downloads and creates a roughly 25 MB `inputs.tar.gz`; allow at least 250 MB of free space in addition to the Python environment. It contacts only the manifest's ECMWF HTTPS origin, rejects redirects and changed bytes, and refuses to overwrite an existing archive. Download once; subsequent scoring runs reuse the archive. If upstream files change or become unavailable, acquisition fails visibly.

Expected scoring line: `PASS: reproduction-result.json`, exit 0. Missing, corrupt or mismatched inputs and failed comparisons produce a nonzero exit. The negative control must be rejected for the overall case to pass; missing negative-control rows do not count as a successful rejection. Scoring writes only a result file and temporary extracted inputs, and makes no network requests. Installation and the explicit download step use the network.

The committed [dependency lock](requirements.lock) pins the complete resolved dependency set and PyPI wheel hashes. Author and separate reviewer runs use fresh Python 3.12 environments on macOS arm64; this does not establish Linux/Windows compatibility. The base `omytea-protocol` receipt verifier remains standard-library-only; these numerical dependencies belong to this optional example.

## Method and scope

Each forecast contains five ordered category probabilities on the global 1.5-degree grid. Window 1 starts 18 days after initialization and window 2 starts 25 days after initialization, so both positive cases verify the week starting **2025-12-15**. The wrong-window reference instead verifies the week starting 2025-12-08.

For temperature we retain land-mask values >= 0.5 and observations with a defined category, form cumulative probabilities, and calculate the ranked probability score (RPS). We apply cosine-of-latitude weights and report `RPSS = 1 - RPS_forecast / RPS_uniform`. The uniform climatological reference uses probability 0.2 for each category. It scores 0 by construction; a perfect categorical forecast scores 1.

The NumPy RPSS calculation is written in this example. **Observation classification reuses `AI-WQ-package==3.31`'s `conditional_obs_probs`**, so the whole chain is not independent of official software. Normalization drift and partially missing participant probabilities are preserved and scored using the official skip-NaN convention, not repaired. Entirely missing forecasts on the scoring domain and infinite probabilities are rejected. A pass does not certify arbitrary inputs as complete or statistically valid probability distributions.

The official JSON was fetched anonymously on 2026-09-22. Its full-document hash and the three unmodified source slices are retained in `references.json`; participant maps are derived from those slices. Unranked `Dynamical_S2SDatabase` reference systems are explicitly excluded because their forecasts are absent from the public participant corpus. No participant is removed. The 93 forecast files were independently fetched from their official URLs and checked against their recorded hashes; the downloader creates a local archive preserving the original NetCDF bytes.

The checks cover coverage loss, unrounded tolerance, nonfinite comparison values, an empty scoring domain, wholly missing land forecasts, uniform/perfect baselines, missing and altered input bytes, and unsafe or duplicate archive members. [Verification notes](VERIFICATION.md) distinguish local tests, a separate agent's fresh-environment replay, and outside customer evidence.

**Not covered:** other variables, other verification weeks, period aggregation, forecast calibration, causal or commercial benefit, predictive superiority, and any claim of general production readiness. Input hashes detect changes relative to this published package; they are not third-party timestamps or signatures, and do not authenticate a copy whose code and manifest have both been replaced. Pin a reviewed Git commit when citing or rerunning this case.

## Attribution and reuse

These results are based on data and products of the European Centre for Medium-Range Weather Forecasts (ECMWF). Forecasts belong to the original AI Weather Quest participants identified, with exact source URLs, in the manifest. AI Weather Quest is organized by ECMWF. There is no endorsement or affiliation implied by this reproduction.

Code is Apache-2.0 under the repository [LICENSE](../../LICENSE). Forecast data and the publicly accessible leaderboard content are CC BY 4.0, subject to the applicable ECMWF terms. The archive is a selected subset with no changes to forecast bytes; extracted reference maps and recomputed scores are our transformations. See [DATA-LICENSE.md](DATA-LICENSE.md) for source notices, attribution, software provenance and the auxiliary-file boundary.
