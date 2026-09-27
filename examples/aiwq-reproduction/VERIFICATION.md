# Verification record

## Historical verification — 2026-09-22

The records in this section describe the original release, whose three auxiliary files required separate authorized access. The data-access revision of 2026-09-27 bundles those same three files unchanged and updates the input manifest and acquisition metadata. The historical hashes below identify the original release, not the revised files. Current execution evidence is recorded separately below; old test results are not evidence that a new revision ran.

**Original delivery:** forecast binaries were not committed to Git. `download_inputs.py` retrieved the 93 pinned public files from ECMWF and built `inputs.tar.gz` locally. After the initial archive exceeded the repository's content-scanner file-size limit, the archive-containing local commit was preserved and a new candidate used this downloader; the scanner and numerical acceptance criteria were not changed. The actual downloader fetched all 93 files successfully and reconstructed the identical archive hash listed below.

## Replays

The author created a fresh Python 3.12.12 virtual environment and installed the numerical dependencies. A separate reviewer agent created another fresh environment on the same macOS 15.8 arm64 host, installed the published `requirements.lock` with `--require-hashes --only-binary=:all:`, and independently ran:

```bash
python -m pip check
python -m unittest -v test_acceptance
python reproduce.py --auxiliary-dir /path/to/authorized/files --out independent-result.json
```

Both environments passed the dependency check and all five test methods. The independent replay passed the two positive cases and the expected negative-control rejection. Its complete JSON output was byte-identical to `result.json`, SHA-256 `a102f070bc7d746a7fa8902082ae69d485486ccdf31065f235a7e8c11c858773`.

| Checked file | SHA-256 |
|---|---|
| `reproduce.py` | `7dcda18bbf0f53771b65563a3e217e0f089c25960e7ccbbdd980c2449454a57a` |
| `test_acceptance.py` | `c652625b37d3cccfb96596b6b1f867d3d1c5b3b2b3762cd0ba76fd46a47a3610` |
| `requirements.lock` | `83e0e0e69a1a688ace5030ac2fa49774e7c906e0d5b8a2e23d520f2c5e4ec182` |
| `input-manifest.json` | `1171b582fa8932706c3a8778458747b6239283ffad29541a5f5be08778b4f05d` |
| `references.json` | `dbf8cdb2c694e15c0f0759226bce600ae43b3e71a158a0d85375755087193259` |
| `inputs.tar.gz` | `0f9204ae0900569043adde1f32a22b78095fb10f21ee579abb927caf59941dd7` |
| `download_inputs.py` | `b0fef039cd7e80f0c677672205af73cfe02dee8ef3a6d242cddef167e81590da` |
| `test_download_inputs.py` | `dfdf659e9d9d93e58eeb8c682a33f2144e6a64d1f020dd07fde188b609266e79` |

The independent reviewer also inspected the archive: 93 regular forecast files, 91,938,476 uncompressed bytes, exact manifest membership, matching sizes/hashes, and no auxiliary files. The three included raw leaderboard slices independently project to the stored 44/49/49 participant maps. The root protocol tests passed separately: **41 pytest tests**, plus the specimen verifier's five checks. The pytest run emitted pre-existing temporary-directory cleanup warnings, with no assertion failures.

The downloader adds two test methods, for **seven** in the final example suite (`python -m unittest -v test_acceptance test_download_inputs`). Independent incremental review passed these tests, rejected off-origin URLs, query-bearing URLs, traversal paths, redirects and changed/oversized input bytes, and checked that both a pre-existing archive and a concurrently created archive are preserved. Downloading is an explicit network operation; scoring remains offline. The original scorer, five acceptance tests, manifest, references, lock and result hashes remain unchanged.

After the actual downloader finished, the reviewer verified the regenerated archive's identical hash and performed one further isolated, offline replay in its separate environment. The full result JSON again matched `result.json` exactly; no Python socket-network attempt was observed during scoring.

## Rejection checks and a corrected defect

The comparison check rejects empty or incomplete joins, nonfinite score values and differences just above 0.0005 even if their display-rounding would hide the excess. Missing negative-control rows cannot count as a successful negative control.

Independent archive probes rejected absolute/traversal paths, duplicate manifest names and archive members, mismatched or oversized lengths, changed hashes, missing/extra members, symbolic/hard links, FIFOs and directory members. This is bounded testing of this extraction implementation, not a claim about every possible archive.

The reviewer identified an initial edge case: a forecast with finite ocean values but entirely missing land values could receive an apparently valid score under a skip-NaN reduction. The implementation now rejects a forecast entirely missing on the scoring domain, and a regression test covers it. Partially missing probabilities retain the official scoring convention. This example does not certify arbitrary forecasts as complete probability distributions.

A concrete remaining limitation was measured: setting the first of five categories to NaN while leaving the other four finite can produce RPSS 1.0 through the preserved cumulative-sum/skip-NaN behavior. Such an altered input fails this capsule's frozen file hashes, but the scoring function is therefore unsuitable as a general customer-input validity check. That use requires a separate missing-probability policy and acceptance tests.

## Independence and assurance limits

- The review and replay were performed by a separate AI-agent session, not ECMWF, an outside customer or an independent laboratory. The environments were fresh, but the host and legally held auxiliary-data copies were shared. Cross-host portability and fresh acquisition of auxiliary data were not established.
- The official observation-classification helper remains a shared dependency. Reproducing a rounded reference does not prove scientific independence of the entire processing chain.
- Static safety review was limited to the new offline example, archive handling, dependency/source provenance and public-content checks. No production target, public service, dependency-CVE inventory or native NetCDF parser was comprehensively security-tested. Zero findings in a bounded check is not a security guarantee.
- A fresh-context reader correctly understood the scoring-only claim and auxiliary-data restriction. The requested local-model reader was unavailable; the separate AI reading is a qualitative clarity check, not measured reader comprehension.
- These records demonstrate execution and inspection of this package. They establish neither prospective predictive performance nor customer demand, revenue or external endorsement.

## Reproduction versus measurement

The acceptance criteria were fixed before this public run: exactly 44 and 49 participant comparisons, no missing rows, unrounded differences <= 0.0005, and a complete wrong-window comparison rejected by that same error threshold. Input and code changes require a new result, with a new digest. References and forecasts were re-fetched from public official endpoints on 2026-09-22; the auxiliary-data hashes refer to separately held fixed copies. Git history and these hashes identify the published artifact, not a pre-outcome forecast commitment.


## Auxiliary-data delivery revision — 2026-09-27

This revision includes the three original auxiliary files in `auxiliary/` under the terms described in [DATA-LICENSE.md](DATA-LICENSE.md). Each byte size and SHA-256 matches the original 2026-09-22 manifest. `archive_member` now explicitly identifies the 93 downloaded forecasts; the three bundled files are verified separately before scoring. The default CLI finds them relative to the script, and the explicit `--auxiliary-dir` option still accepts an identical copy. Numerical functions, tolerance, reference scores, dependency lock and the seven original test methods were not changed.

A new Python 3.12.12 environment was created on the same macOS arm64 host. All 34 dependencies were installed from the unchanged lock with `--require-hashes --only-binary :all:`; `uv pip check` passed. The seven example tests passed, and `python reproduce.py --out result.json` passed using the bundled files. Both case reports, the complete negative-control report and normalization observations are exactly equal to the original result; code/manifest hashes and the data-access description have appropriately changed. The base verifier separately passed 41 tests and 5 specimen checks; its pytest run had pre-existing temporary-directory cleanup warnings, without assertion failures.

The downloader was also executed in a new directory without an existing archive. It retrieved all 93 forecast files from the pinned public ECMWF URLs without credentials, verified their sizes/hashes, and produced the original archive SHA-256 `0f9204ae0900569043adde1f32a22b78095fb10f21ee579abb927caf59941dd7`. This acquisition used the existing AIWQ Python environment; the subsequent numerical replay used the new locked environment. These are separate checks, not a claim that every operating system or future upstream state was tested.

Structured NetCDF global and variable metadata of the three auxiliary files were reviewed: CF/CDI/CDO processing provenance and public software URLs were present; no credential, private personal contact or private user path was found. Data bytes were not stripped or rewritten.

Current artifact digests:

| File | SHA-256 |
|---|---|
| `reproduce.py` | `19e834772ef1cdec1049e35a2e09b0f41ae34adaca5f5d0b8bce76dbe713f1ad` |
| `download_inputs.py` | `f6b8320230dfba6e46bfb433084b367c2cc38082d52f86905e66c703b9e5ac58` |
| `input-manifest.json` | `457e38c17c68a78d1b264df9b84fe7a082b18666c50a77b1b21a8c6d079ebe27` |
| `result.json` | `09a026641194c26c40b84e32641a1b224103555c50235b683cedc68400cb6308` |
| `requirements.lock` | `83e0e0e69a1a688ace5030ac2fa49774e7c906e0d5b8a2e23d520f2c5e4ec182` |
| `references.json` | `dbf8cdb2c694e15c0f0759226bce600ae43b3e71a158a0d85375755087193259` |

This is a bounded historical scoring/data-delivery verification. It does not establish prospective predictive skill, production readiness, customer demand or endorsement.

A separate reviewer agent then ran a clean copy of the example from a different working directory, using the new locked environment and without reading the private source-data directory. All seven frozen tests passed. The default CLI passed, while both a missing auxiliary directory and a same-size tampered auxiliary file failed with exit 1. Its full JSON result exactly matched the current `result.json` (SHA-256 `09a026641194c26c40b84e32641a1b224103555c50235b683cedc68400cb6308`). The reviewer independently checked input hashes, numerical-function invariance, metadata and attribution. This was a separate agent and clean artifact copy on the same host using the same newly installed environment; it was not an outside customer, laboratory or ECMWF certification.
