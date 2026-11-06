# omytea-protocol

Receipt schema, scoring math, and verifier for machine predictions.

This repository is the **verification half of a settlement layer for machine
predictions**: predictions are frozen before the fact, resolved by independent
sources, mechanically scored, and packaged as **receipts** that anyone can
verify — without trusting the party that issued them.

## Why this is public

"Receipts you verify without trusting us" is only true if the verifier is in
*your* hands, not ours. If the schema, the hash rule, and the scoring math
lived behind our API, "verified" would just mean "we said so." So the entire
verification path is here, self-contained, standard-library-only, and
Apache-2.0 — you can read every line that decides whether a receipt passes.

The prediction *engine* is not in this repository, and does not need to be:
verification is deliberately engine-agnostic. A receipt either checks out or
it does not, regardless of what produced it.

## Quickstart: verify the specimen

No dependencies beyond Python 3.10+.

```bash
git clone <this-repo> && cd omytea-protocol

# Option A: no install
PYTHONPATH=src python3 -m omytea_protocol.verify examples/specimen-receipt.json

# Option B: editable install
pip install -e .
python3 -m omytea_protocol.verify examples/specimen-receipt.json
```

Expected output:

```
Receipt verification: examples/specimen-receipt.json
  [PASS] structure: receipt matches the expected shape
  [PASS] frozen_hash: recomputed sha256 matches (7ee02cec942e823f...)
  [PASS] timeline.frozen_before_deadline: created_at 2026-06-30T18:00:00Z vs resolution_deadline 2026-06-30T18:01:00Z: frozen before its horizon
  [PASS] timeline.resolved_after_freeze: created_at 2026-06-30T18:00:00Z vs outcome.resolved_at 2026-06-30T18:02:11Z: resolved after freezing
  [PASS] scores.brier: recomputed 0.27499999999999997 matches recorded value
  [PASS] scores.log_loss: recomputed 0.5978370007556204 matches recorded value
  [PASS] baseline_scores.uniform: recomputed scores match recorded values
  [WARN] timeline.late_resolution: outcome.resolved_at 2026-06-30T18:02:11Z is 0:01:11 after resolution_deadline 2026-06-30T18:01:00Z; the verifier cannot tell resolver latency from an outcome read outside the declared window
RESULT: PASS (7/7 checks passed, 1 warning)
PROVENANCE: unknown (no provenance label, as on every receipt older than the field; verification alone does not show this is a real prediction); specimen: true (illustrative, not a live track-record entry)
```

Now tamper with any frozen field in the specimen — a probability, the
question, the deadline — and run it again: the hash check fails. Tamper with
a recorded score instead: the score recomputation fails. Date the outcome
before the freeze: the timeline check fails. That is the whole trust model.

Warnings (`[WARN]`) are printed but never change the result or the exit
code. The specimen's annotator recorded the outcome 71 seconds after the
deadline, which is reported rather than failed; see
[Timeline checks](#timeline-checks).

The specimen (`examples/specimen-receipt.json`) is clearly labeled
`"specimen": true` — it demonstrates the format and verification flow and is
**not** a live track-record entry.

## Receipt lifecycle

```
freeze ──────────► resolve ──────────► score ──────────► verify
(commit the        (independent        (mechanical        (anyone, offline,
prediction +       source determines   scoring rules      with this repo)
hash it, before    the outcome)        on prediction
the fact)                              + outcome)
```

1. **Freeze.** The prediction — question, distribution, deadline, resolution
   source — is committed at `created_at` and hashed into `frozen_hash`.
   Any later change to any frozen field changes the hash.
2. **Resolve.** The outcome is determined by the declared
   `resolution_source`, independently of the predictor, and recorded under
   `outcome`.
3. **Score.** The frozen prediction is scored against the outcome with
   standard proper scoring rules (below). Scores are pure functions of
   `prediction` + `outcome` — nothing else.
4. **Verify.** You re-run steps 1 and 3 yourself: recompute the hash,
   recompute the scores, compare. `python -m omytea_protocol.verify` does
   exactly this and nothing more.

## Receipt format

The formal schema is [`schema/receipt.schema.json`](schema/receipt.schema.json)
(JSON Schema draft 2020-12). Summary:

| Field | Frozen? | Meaning |
|---|---|---|
| `version` | — | Receipt format version (`"0.1"`). |
| `receipt_id` | yes | Unique identifier. |
| `created_at` | yes | Freeze time (ISO 8601 UTC). |
| `question` | yes | What is being predicted, about what, over what window. |
| `prediction` | yes | `branches` (discrete distribution) **or** `quantiles` (continuous distribution). |
| `resolution_deadline` | yes | When the outcome must be resolvable by. |
| `resolution_source` | yes | How the outcome is determined, independently of the predictor. |
| `specimen` | yes, if present | Marks an illustrative receipt that is not a live entry. |
| `provenance` | yes, if present | Issuer-declared origin: `real`, `synthetic`, or `fixture`. Absent = unknown. |
| `frozen_hash` | — | SHA-256 of the canonical frozen payload (all "yes" rows above). |
| `outcome` | no | Resolved outcome: `label` (branches) or `value` (quantiles), `resolved_at`, `source_url`. |
| `scores` | no | Mechanical scores; recomputable from `prediction` + `outcome`. |
| `baseline_scores` | no | Scores of named reference forecasts (each carrying its own distribution, so equally recomputable). |
| `notes` | no | Free-text annotation. |

### Canonical hashing

The frozen payload is the JSON object containing exactly the frozen fields,
serialized as

```python
json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
```

and hashed with SHA-256 (hex digest). This is the only serialization rule in
the protocol; `omytea_protocol.verify.compute_frozen_hash` implements it in a
few lines. `specimen` and `provenance` join the payload only when present, so
a receipt that omits them hashes exactly as it did before they existed.

### Timeline checks

JSON Schema cannot compare two fields, so the verifier checks ordering itself:

| Check | Result | Rule |
|---|---|---|
| `timeline.frozen_before_deadline` | FAIL | `created_at` must be strictly before `resolution_deadline`. |
| `timeline.resolved_after_freeze` | FAIL | `outcome.resolved_at` must be strictly after `created_at`. |
| `timeline.late_resolution` | WARN | `outcome.resolved_at` is after `resolution_deadline`. |
| `timeline.future_created_at` / `timeline.future_resolved_at` | WARN | A timestamp is more than 5 minutes past the verifier's clock. |

A late resolution is a warning, not a failure: `resolved_at` records when the
outcome was written down, the deadline is when it must be resolvable, and
resolvers lag. The verifier cannot tell lag from an outcome read outside the
declared window, so it prints the lag and leaves the judgement to you.
Future timestamps are warnings because a failure would make the verdict
depend on when you run the check. Timestamps without a UTC offset are read
as UTC.

### Provenance

`provenance` says what kind of receipt this is: `real` (a live prediction
frozen before a real-world outcome), `synthetic` (generated or simulated
data), or `fixture` (a test or demo artifact). The verifier prints it on the
line after the result, because a receipt can verify perfectly and still be
evidence of nothing. The label is the issuer's declaration. Being inside
`frozen_hash` means it cannot be changed after freezing without failing the
hash; it does not make the label true. A receipt without the field is
reported as `unknown`, which is not an error. A specimen cannot declare
`real`.

## Scoring rules

All rules are textbook, strictly proper (or derived from strictly proper
rules), and implemented in [`src/omytea_protocol/scoring.py`](src/omytea_protocol/scoring.py)
with formulas and references in the docstrings. Lower is better throughout.

| Function | Rule | Used for |
|---|---|---|
| `brier_score` | multi-category Brier, `sum_k (p_k - o_k)^2` (Brier 1950) | branch predictions |
| `log_loss` | logarithmic score, `-ln p(outcome)` (Good 1952) | branch predictions |
| `crps_from_quantiles` | CRPS via the pinball-loss quantile decomposition (Gneiting & Ranjan 2011) | quantile predictions |
| `calibration_coverage` | empirical prediction-interval coverage (Vovk et al. 2005) | track-record calibration reading |
| `e_value_update` / `e_process_from_losses` | anytime-valid evidence comparing a forecaster with a baseline, via testing-by-betting (Shafer 2021; Ramdas et al. 2023) | track-record comparison that stays valid under optional stopping |

Two honesty notes baked into the docstrings, worth repeating here:

- **Coverage is not a merit by itself.** Split-conformal intervals hit their
  nominal coverage by construction; what discriminates forecast skill is
  interval width. A track record showing 100% coverage with vacuously wide intervals
  demonstrates nothing.
- **E-values stay valid whenever you look.** Unlike fixed-n confidence
  intervals, the betting e-process tolerates "glance at the growing ledger
  whenever you feel like it" — which is how track records are actually read.

## Running the tests

```bash
pip install pytest
python3 -m pytest
```

The tests pin closed-form scoring values, check that the shipped specimen
verifies, and check that tampered receipts (altered probabilities, altered
outcomes, flattering scores, stripped specimen label, forged hash, outcomes
dated before the freeze, relabelled or stripped provenance) fail.

## Status

This repository defines the receipt format and the verification path. The
public ledger and our engine's scored track record will be linked here as
they go public.

## License

Apache-2.0. See [LICENSE](LICENSE).

---

<!-- OMYTEA_ORG_SYNC_README_START -->
> **Organization source of truth:** [`Omytea-Almighty/omytea-protocol`](https://github.com/Omytea-Almighty/omytea-protocol). Humans and agents must read [`ORG-SYNC.md`](ORG-SYNC.md) before working. Managed commit/rewrite hooks queue reviewed commits; ordinary direct push is denied; registered linked worktrees are supported. Automation never stages or commits dirty work, changes visibility, or bypasses hooks.
> This repository is public: every intentional commit is a publication decision. Secret scanning is not a privacy, PII, licensing, research, or commercial-sensitivity review.
<!-- OMYTEA_ORG_SYNC_README_END -->
