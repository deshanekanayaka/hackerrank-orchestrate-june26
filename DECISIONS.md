# Decisions & Bug Log

## Architecture Decisions

**CALL split: 3 separate LLM calls per claim**
Chose split pipeline (extraction → image analysis → verdict) over single call.
Reason: easier to debug, each stage has a clear job, failure is isolatable.

**Deterministic NEI short-circuit**
When evidence_standard_met=false, return not_enough_information without calling CALL 3.
Reason: rule is 100% consistent in sample data, saves ~30% API calls.

**issue_family derived deterministically**
After CALL 1, map issue_type → issue_family via Python dict, not LLM.
Reason: mapping is fully knowable upfront, removes one failure mode.

**Opus for CALL 1 + CALL 3, Sonnet for CALL 2**
Reason: CALL 1 and 3 require reasoning over ambiguous text. CALL 2 is
high-volume vision — Sonnet is cost-efficient and vision-capable.

**User history flags copied directly**
Copy history_flags column verbatim, never infer from counts.
Reason: values already match allowed output values exactly.

---

## Bugs Found & Fixed

**BUG 1 — Image paths missing dataset/ prefix**
File: code/utils.py → resolve_image_paths()
Found: images/test/case_001/img_1.jpg resolved to MISSING.
Fix: prepend dataset/ to all paths in resolve_image_paths().

**BUG 2 — AVIF images disguised as .jpg**
File: code/image_analyzer.py → _prepare_image(), _is_avif()
Found: Anthropic API rejected images with .jpg extension that were actually AVIF.
Fix: magic-byte detection at bytes 4-12, convert AVIF to JPEG via Pillow on the fly.

**BUG 3 — PNG and WebP also disguised as .jpg**
File: code/image_analyzer.py → _prepare_image(), _is_png(), _is_webp()
Found during full 44-claim run: 14 PNG and 11 WebP files also carried .jpg extension.
Fix: added _is_png() (magic bytes 0-8) and _is_webp() (RIFF header) detectors.
Dataset breakdown: 49 JPEG, 14 PNG, 11 WebP, 8 AVIF (all 82 carry .jpg extension).

**BUG 4 — Sonnet wraps JSON in markdown fences despite prompt instruction**
Files: code/extractor.py → _strip_fences()
       code/image_analyzer.py → _strip_fences()
Found: claude-sonnet-4-6 returns ```json ... ``` even with explicit "no fences" instruction.
Fix: _strip_fences() applied before json.loads() in both modules.

**BUG 5 — CSV loaders duplicated between entry points**
Files: code/utils.py (created)
       code/main.py (loaders removed, import added)
       code/evaluation/main.py (loaders removed, import added)
Found: load_user_history, load_requirements, resolve_image_paths defined twice.
Fix: extracted to utils.py, both entry points import from there.

**BUG 6 — Evidence standard too strict (7/20 false negatives)**
File: code/image_analyzer.py → SYSTEM_PROMPT_TEMPLATE
Found: CALL 2 over-flagged professional images as non_original_image.
Evaluation: evidence_standard_met 13/20 → target 18+/20.
Fix: softened 4 prompt sections:
  - "true ONLY if / judge strictly" → "true if reasonable / judge reasonably"
  - valid_image: professional photos of right object stay true
  - non_original_image: requires irrelevance, not just professional appearance
  - Added issue-type tie-breaks: crack vs glass_shatter, stain vs water_damage

**BUG 7 — Quality flag union poisons CALL 3 verdict**
File: code/agent.py → process_claim() context assembly
Found: image_quality_flags is union of ALL images including non-supporting ones.
A decoy/context image with damage_not_visible or claim_mismatch caused CALL 3
to return contradicted even when a valid supporting image existed.
Root cause: per-image flags correct, but union hoisted decoy flags to claim level.
Fix: split per_image_analysis into supporting vs non-supporting groups.
Only pass flags from non-supporting images to CALL 3 context.
Full flag union preserved in risk_flags output for human reviewers.

---

## Data Quality Findings

- 44 test claims, 20 labeled sample claims
- 82 test images, 31 sample images
- Zero missing files, zero duplicates, zero corrupt files
- All 82 images carry .jpg extension regardless of actual format
- Multilingual transcripts: Hindi, Urdu, Spanish, mixed Chinese/English
- Adversarial inputs: case_008, case_036, case_048, case_055 (injection),
  case_037, case_040 (coercive language)
