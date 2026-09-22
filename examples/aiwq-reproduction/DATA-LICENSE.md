# Data and software provenance

Checked on 2026-09-22. This notice concerns this example, not every asset in the repository.

## Public participant forecasts

Source: [ECMWF AI Weather Quest dataset](https://www.ecmwf.int/en/forecasts/dataset/ai-weather-quest-sub-seasonal-forecasts), [data portal](https://data.ecmwf.int/ai-weatherquest/), [portal licence](https://data.ecmwf.int/ai-weatherquest/LICENCE_AI_Weather_Quest.txt), and [portal documentation](https://data.ecmwf.int/ai-weatherquest/README_AI_Weather_Quest.txt).

The 93 NetCDF files listed in `input-manifest.json` are participant-submitted forecasts, with original team/model names and per-file URLs. They are retrieved directly from ECMWF by the included downloader; binaries are not committed to this repository. They were produced as part of the AI Weather Quest competition organized by ECMWF (2025–2026). The subset selection and local archive packaging are ours; forecast file bytes are unchanged. No claim of ownership of participants' models is made.

Copyright © 2025–2026 European Centre for Medium-Range Weather Forecasts (ECMWF), with original participant rights retained as applicable. Source: [ECMWF](https://www.ecmwf.int/). This data is published under a [Creative Commons Attribution 4.0 International licence](https://creativecommons.org/licenses/by/4.0/), together with the [ECMWF general terms](https://apps.ecmwf.int/datasets/licences/general/).

These results are based on data and products of the European Centre for Medium-Range Weather Forecasts (ECMWF). ECMWF does not accept any liability whatsoever for any error or omission in the data, their availability, or for any loss or damage arising from their use. The data are provided as-is without a warranty of accuracy, completeness or uninterrupted availability. Please retain the source, licence, disclaimer, original participant credit and modification indications when reusing this material; the full linked terms govern.

Dataset reference: ECMWF, *AI Weather Quest sub-seasonal forecasts*, accessed 2026-09-22 at the dataset URL above. A separate dataset DOI was not located; it is not replaced by the paper DOI. Associated paper: Loegel, O., Talib, J., Vitart, F., Hoffmann, J. and Chantry, M. (2025), *The AI Weather Quest: an international competition for sub-seasonal forecasting with AI*, Machine Learning: Earth, 1(1), 010701, [doi:10.1088/3049-4753/adf649](https://doi.org/10.1088/3049-4753/adf649).

## Public leaderboard references

`references.json` contains three selected raw slices and derived participant-to-score maps from the official [leaderboard JSON](https://aiweatherquest.ecmwf.int/wp-content/themes/picostrap5-child-base/js/results_page/response.json). Its metadata records the actual acquisition timestamp and SHA-256 of the complete downloaded source document. Extraction, formatting and exclusion of separately identified unranked reference systems are the only changes; participant scores are unmodified. The [website terms](https://aiweatherquest.ecmwf.int/terms-of-use/) license its publicly accessible content under CC BY 4.0. ECMWF/AI Weather Quest attribution and the non-endorsement boundary apply here too.

## Auxiliary files are not included

The land-sea mask, temperature quintile thresholds and observation file are described by their names, sizes and hashes only. Their exact-file redistribution permission has not been established. This is an unresolved permission question, not a claim that redistribution is prohibited. The participant-forecast portal licence is not assumed to cover these separate files.

Use your own authorized access through the [official evaluation-data documentation](https://ecmwf-ai-weather-quest.readthedocs.io/en/latest/forecast_evaluation.html). We distribute no registration password, credential-bearing URL or auxiliary NetCDF bytes. The code reads them only when the user supplies `--auxiliary-dir`, and rejects versions that differ from the documented hashes. ERA5/ERA5T origin alone is not used as authorization to mirror these precise preprocessed files.

## Official observation-classification dependency

The code imports the unmodified `conditional_obs_probs` function from [AI-WQ-package 3.31](https://pypi.org/project/AI-WQ-package/3.31/), maintained by ECMWF. The release wheel's actual LICENSE and source SPDX headers state Apache-2.0 (copyright ECMWF 2024); an MIT classifier in the release metadata is inconsistent with those files. We follow the actual Apache-2.0 licence, not that classifier. No upstream function is vendored in this repository; installation retrieves the package and its licence from PyPI.

The 3.31 wheel SHA-256 is `209c32d20a5b2b22b58319b33573242e24ff4371fd0d345e605c233f31d9a341`. Its `forecast_evaluation.py` SHA-256 is `e932a92e16efff37f797e3884dc5b498d7f7fd8229673919953d0c031a84e5ab`. Dependency versions and permitted wheel hashes are recorded in `requirements.lock`; third-party wheels and complete environments are not redistributed here.
