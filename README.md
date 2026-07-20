# omytea-protocol

<!-- OMYTEA_ORG_SYNC_README_START -->
> **Organization source of truth:** [`Omytea-Almighty/omytea-protocol`](https://github.com/Omytea-Almighty/omytea-protocol). Humans and agents must read [`ORG-SYNC.md`](ORG-SYNC.md) before working. Reviewed commits are queued for fail-closed organization sync; automation never stages or commits dirty work and never changes visibility.
> This repository is public: every intentional commit is a publication decision. Secret scanning is not a privacy, PII, licensing, research, or commercial-sensitivity review.
<!-- OMYTEA_ORG_SYNC_README_END -->

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
  [PASS] scores.brier: recomputed 0.27499999999999997 matches recorded value
  [PASS] scores.log_loss: recomputed 0.5978370007556204 matches recorded value
  [PASS] baseline_scores.uniform: recomputed scores match recorded values
RESULT: PASS (5/5 checks passed)
```

Now tamper with any frozen field in the specimen — a probability, the
question, the deadline — and run it again: the hash check fails. Tamper with
a recorded score instead: the score recomputation fails. That is the whole
trust model.

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
few lines.

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
| `e_value_update` / `e_process_from_losses` | anytime-valid "forecaster beats baseline" evidence via testing-by-betting (Shafer 2021; Ramdas et al. 2023) | track-record comparison that stays valid under optional stopping |

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
outcomes, flattering scores, stripped specimen label, forged hash) fail.

## Status

This repository defines the receipt format and the verification path. The
public ledger and our engine's scored track record will be linked here as
they go public.

## License

Apache-2.0. See [LICENSE](LICENSE).
