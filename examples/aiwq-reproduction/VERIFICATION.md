# Verification record

Executed 2026-09-22. Scope: this historical scoring example and the unchanged base receipt verifier. The case has **conditional data access**, because three auxiliary files are not redistributed.

**Current delivery:** forecast binaries are not committed to Git. `download_inputs.py` retrieves the 93 pinned public files from ECMWF and builds `inputs.tar.gz` locally. After the initial archive exceeded the repository's content-scanner file-size limit, the archive-containing local commit was preserved and a new candidate used this downloader; the scanner and numerical acceptance criteria were not changed. The actual downloader fetched all 93 files successfully and reconstructed the identical archive hash listed below.

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
