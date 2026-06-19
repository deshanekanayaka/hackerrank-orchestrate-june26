# HackerRank Orchestrate — Damage Claim Verification

A three-call LLM pipeline that verifies damage claims by combining transcript
extraction, VLM image analysis, and deterministic rule gates. Reads
`dataset/claims.csv` and writes structured verdicts to `output.csv`.

---

## Use Case

```mermaid
flowchart LR
    C([Customer]) -->|transcript + images| CS
    CS[Claims System]
    CS --> E[Extract claim\nfrom transcript]
    CS --> I[Analyse\nsubmitted images]
    CS --> H[Check user\nhistory & rules]
    E & I & H --> V[Produce verdict]
    V -->|supported / contradicted /\nnot_enough_information| R([Reviewer])
```

---

## Data Flow

```mermaid
flowchart TD
    A[(claims.csv)] --> M
    B[(images/)] --> M
    C[(user_history.csv)] --> M
    D[(evidence_requirements.csv)] --> M

    M[main.py\nload & route] --> X[CALL 1\nclaim extraction]
    X --> IA[CALL 2\nimage analysis]
    IA --> G{evidence\nstandard met?}
    G -->|false| NEI[not_enough_information\ndeterministic]
    G -->|true| V[CALL 3\nverdict]
    NEI & V --> O[(output.csv\n14 fields)]
```

---

## Architecture

```mermaid
flowchart TD
    main([main.py]) --> utils([utils.py])
    main --> agent([agent.py])
    main --> output([output.py])

    agent --> extractor[extractor.py\nclaude-opus-4-6]
    agent --> image_analyzer[image_analyzer.py\nclaude-sonnet-4-6]
    agent --> escalation([escalation.py])
    agent --> call3[agent.py · _finalize_verdict\nclaude-opus-4-6]

    style utils          fill:#1a5c38,color:#ffffff,stroke:#0d3d24
    style escalation     fill:#1a5c38,color:#ffffff,stroke:#0d3d24
    style output         fill:#1a5c38,color:#ffffff,stroke:#0d3d24
    style main           fill:#1a5c38,color:#ffffff,stroke:#0d3d24
    style extractor      fill:#1a3a6b,color:#ffffff,stroke:#0d2444
    style image_analyzer fill:#1a3a6b,color:#ffffff,stroke:#0d2444
    style call3          fill:#1a3a6b,color:#ffffff,stroke:#0d2444
    style agent          fill:#7a5c00,color:#ffffff,stroke:#4a3800
```

**Legend:**
- Green rounded — deterministic, no AI (`utils.py`, `escalation.py`, `output.py`, `main.py`)
- Blue rectangle — LLM call (`extractor.py` / Opus, `image_analyzer.py` / Sonnet, `_finalize_verdict` / Opus)
- Yellow — orchestrator (`agent.py` coordinates all three calls and the deterministic gates)

---

## How to Run

```bash
# Install dependencies
pip install -r code/requirements.txt

# Run on test set (44 claims → output.csv)
python3 code/main.py

# Run evaluation against labelled sample (20 claims)
python3 code/evaluation/main.py
```

Requires `ANTHROPIC_API_KEY` in a `.env` file at the repo root or in the environment.

---

## Key Decisions

- **Three-call split** — Opus for reasoning (CALL 1 transcript extraction, CALL 3 verdict); Sonnet for perception (CALL 2 image analysis). Separates concerns and controls cost.
- **Deterministic NEI short-circuit** — when `evidence_standard_met=false`, the verdict is forced without a CALL 3 invocation. Reproducible on ~57% of test claims.
- **Magic-byte image detection** — 33 of 82 test images carry incorrect `.jpg` extensions (14 PNG, 11 WebP, 8 AVIF). Format is sniffed from file headers; AVIF is converted to JPEG via Pillow before the API call.
- **Non-supporting image flag filter** — in multi-image claims, quality flags from decoy/context images are excluded from the CALL 3 verdict context. The full flag union is retained in `risk_flags` for human reviewers.
- **Adversarial pre-filter** — deterministic pattern match runs before any LLM call; flags `text_instruction_present` for injection attempts in transcripts and images.

---

## Evaluation Results

Evaluated against `dataset/sample_claims.csv` (20 labelled rows).

| Field | Accuracy |
|---|---|
| `valid_image` | 85% (17/20) |
| `object_part` | 75% (15/20) |
| `evidence_standard_met` | 65% (13/20) |
| `claim_status` | 55% (11/20) |
| `issue_type` | 55% (11/20) |
| `severity` | 45% (9/20) |
| **Overall (all 6 correct)** | **30% (6/20)** |

Runtime: ~13s per claim. Estimated cost per full 44-claim run: **~$3.50**.
See `evaluation/evaluation_report.md` for full analysis and known limitations.
