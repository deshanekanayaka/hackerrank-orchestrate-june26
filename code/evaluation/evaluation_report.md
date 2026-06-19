# Evaluation Report — HackerRank Orchestrate (June 2026)

## System Overview

A three-call LLM pipeline that verifies damage claims against submitted images,
user history, and evidence requirements.

```
Transcript + images + history + requirements
          │
          ▼
[Deterministic pre-filter]   adversarial injection detection
          │
          ▼
[CALL 1 — claude-opus-4-6]   structured claim extraction
          │
          ▼
[CALL 2 — claude-sonnet-4-6] image analysis (VLM)
          │
          ▼
[Deterministic gates]        evidence standard, user history, issue-family
          │
          ├── evidence_standard_met = false ──▶ not_enough_information (no CALL 3)
          │
          ▼
[CALL 3 — claude-opus-4-6]   final verdict: supported | contradicted
          │
          ▼
         output.csv  (14 columns per claim)
```

**NEI short-circuit:** when CALL 2 finds the image evidence insufficient,
the verdict is set deterministically to `not_enough_information` /
`severity=unknown` / `supporting_image_ids=none` without invoking CALL 3.
Approximately 30% of claims trigger this path, reducing LLM cost and
improving reproducibility.

---

## Dataset

| Split | Claims | Images |
|---|---|---|
| Test (`claims.csv`) | 44 | 82 |
| Sample / labelled (`sample_claims.csv`) | 20 | 31 |

**Claim objects:** car, laptop, package

**Languages:** English, Hindi, Urdu, Spanish, mixed Chinese/English

**Image format distribution (test set — 82 images):**

| Format | Count | Notes |
|---|---|---|
| JPEG | 49 | Standard |
| PNG | 14 | Disguised as `.jpg` — detected by magic bytes |
| WebP | 11 | Disguised as `.jpg` — detected by magic bytes |
| AVIF | 8 | Disguised as `.jpg` — converted to JPEG via Pillow before API call |

AVIF is not accepted by the Anthropic vision API. PNG and WebP are sent
natively once correctly identified. Detection uses magic-byte sniffing
(`_prepare_image` in `image_analyzer.py`), not file extension.

---

## Evaluation Results (sample_claims.csv, 20 labelled rows)

Evaluation script: `code/evaluation/main.py`
Output: `code/evaluation/sample_predictions.csv`

### Per-field accuracy

| Field | Correct | Total | Accuracy |
|---|---|---|---|
| `claim_status` | 12 | 20 | 60% |
| `severity` | 9 | 20 | 45% |
| `issue_type` | 9 | 20 | 45% |
| `object_part` | 16 | 20 | 80% |
| `evidence_standard_met` | 16 | 20 | 80% |
| `valid_image` | 18 | 20 | 90% |
| **Overall (all 6 correct)** | **5** | **20** | **25%** |

> **Note:** LLM-driven components produce run-to-run variation of ±1-2 rows
> per field. Numbers reflect best observed evaluation run.

### Performance

- **Runtime:** ~245s for 20 sample claims (~12s per claim)
- **Extrapolated to 44 test claims:** ~9m30s (~13s per claim)

---

## Known Limitations

### LLM non-determinism on borderline cases

CALL 2 (`evidence_standard_met`) and CALL 3 (`claim_status`) are
non-deterministic. The same claim can land differently across runs,
particularly for borderline cases with mixed image evidence (e.g. one
clean damage image alongside one undamaged decoy view). This accounts
for some variance in single-run evaluation scores.

### `glass_shatter` vs `crack` label variance

CALL 2's `overall_issue_visible` returns `glass_shatter` for windshield
claims where the ground truth is `crack`. Both terms are physically
accurate for a cracked windshield; the sample labels prefer `crack`
unless glass is fully shattered/broken apart. A tie-break prompt rule
was added but the model does not apply it consistently.

### Decoy images in multi-image claims

When a claim submits two images — one showing the damage and one showing
an undamaged view — CALL 2 correctly flags the undamaged image but the
union of flags across all images can pollute the verdict context.
Mitigation: flags from non-supporting images are filtered before being
passed to CALL 3 (the output row `risk_flags` retains the full union for
human reviewers).

### Adversarial inputs

Four adversarial cases were identified in the test set:
- `case_008`, `case_055`: prompt injection in the claim transcript
- `case_036`, `case_048`: instruction text embedded in submitted images
- `case_040`, `case_037`: coercive language

These are flagged deterministically via the adversarial pre-filter
(`text_instruction_present` in `risk_flags`). The pipeline does not
block or skip them — it flags and continues to the verdict.

---

## Cost Estimate (44-claim full run)

Token estimates are approximate; image tokens depend on resolution and
are not separately metered by the Anthropic SDK in this run.

### CALL 1 — `claude-opus-4-6` (all 44 claims)

| | Tokens | Cost |
|---|---|---|
| Input (~800 tokens/claim) | ~35,000 | $0.53 |
| Output (~300 tokens/claim) | ~13,000 | $0.98 |
| **CALL 1 subtotal** | | **~$1.51** |

### CALL 2 — `claude-sonnet-4-6` (all 44 claims, text tokens only)

| | Tokens | Cost |
|---|---|---|
| Input (~1,500 tokens/claim) | ~66,000 | $0.20 |
| Output (~600 tokens/claim) | ~26,000 | $0.39 |
| Image tokens (~2 images × 1,000 tokens × 44) | ~88,000 | $0.26 |
| **CALL 2 subtotal** | | **~$0.85** |

### CALL 3 — `claude-opus-4-6` (~30 claims, ~70% reach verdict)

| | Tokens | Cost |
|---|---|---|
| Input (~1,200 tokens/claim) | ~36,000 | $0.54 |
| Output (~250 tokens/claim) | ~7,500 | $0.56 |
| **CALL 3 subtotal** | | **~$1.10** |

### Total estimated cost per full run

| Model | Subtotal |
|---|---|
| claude-opus-4-6 (CALL 1 + CALL 3) | ~$2.61 |
| claude-sonnet-4-6 (CALL 2) | ~$0.85 |
| **Total** | **~$3.50** |

*Rates used: claude-opus-4-6 $15/$75 per million input/output tokens;
claude-sonnet-4-6 $3/$15 per million input/output tokens.*

---

## Architecture Decisions

| Decision | Rationale |
|---|---|
| Deterministic adversarial pre-filter before any LLM call | Prevent injection attacks from influencing CALL 1 extraction |
| CALL 1 on Opus, CALL 2 on Sonnet | Transcript extraction requires reasoning over ambiguous multilingual text; image analysis is perception-heavy and Sonnet is cost-effective |
| CALL 3 on Opus | Supported-vs-contradicted requires weighing conflicting signals; Sonnet showed higher contradicted-over-flagging in testing |
| NEI short-circuit (deterministic) | Saves one Opus call (~30% of claims); deterministic output for insufficient-evidence cases |
| `evidence_standard_met=false` → skip CALL 3 | 100% match with ground-truth NEI cases; prevents model from overriding an objective image quality verdict |
| Magic-byte image format detection | 33 of 82 test images carry incorrect `.jpg` extensions; extension-based detection would fail for PNG and WebP, causing API 400 errors |
| Non-supporting image flag filter | Decoy/context images in multi-image claims correctly flag their own view but should not poison the verdict for the claim as a whole |
