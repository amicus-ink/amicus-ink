# Adversarial verification — {{MODULE_NAME}} proposed checklist

You are the INDEPENDENT VERIFICATION pass of a two-pass clustering protocol. You are not
the proposer and your job is to be skeptical, not agreeable: on the last run this pass
refuted 5 of 9 proposed checks and converted one refutation into a bug fix. Assume the
proposal contains redundancy, inference leaps, and workflow advice dressed as
requirements until you have checked otherwise.

## Clean-room rule

Read ONLY the inputs below. No existing checklist or skill file anywhere in the repo —
your standard is the sources, not precedent.

## Inputs

- Proposed checklist: `{{PROPOSED}}`
- Proposed assignments: `{{ASSIGN_PROPOSED}}`
- Claim ledger (quotes machine-verified verbatim): `{{CLAIMS_FILE}}`
- Source texts (REQUIRED reading for every quote you rule on): `{{TEXT_DIR}}/`

## What to verify, per check

1. **The reading.** Re-read each evidence quote IN ITS SOURCE CONTEXT (open the text
   file, read around the quoted lines). Is the check's requirement a fair reading of
   what the source establishes — or an inference leap? A verbatim, correctly-cited quote
   can still be misread into a wrong requirement; you are the only gate that catches
   this. Where the requirement overstates the source ("must" where the source says
   "may"; general where the source is conditional), rewrite it down to what the source
   supports, or park the claims.
2. **Modality.** A check established only by advice-modality claims is invalid: demote
   it, re-ground it on a requirement-modality claim, or dissolve it into
   `PARK:workflow_advice`. Watch for checks whose observable is the ANALYST'S process
   (a sequence of operations a published paper does not record) — those are
   NOT-A-CHECK, however sensible the advice.
3. **Redundancy within the proposal.** Merge checks that state one requirement twice.
   Default to merging when in doubt: checklist inflation is the failure mode.
4. **Membership.** Every claim assigned to a check must genuinely establish or qualify
   THAT check's requirement. Reassign or park misfits. Every claim in the ledger must
   end with exactly one home.
5. **Decidability.** Could two independent coders, reading the same paper, reach the
   same PASS/FLAG verdict from the stated conditions? Sharpen vague conditions; give
   scope triggers decidable definitions keyed on the paper's own explicit stance
   (default OUT on silence); park what cannot be made decidable.
6. **Schema law** (blocking downstream, so fix it here): `verdict_when_silent` is FLAG
   or PASS, never NA; every scope trigger used is defined in `_scope_definitions`;
   `requirement_type` present and its silence polarity honored (positive → FLAG,
   prohibition → PASS); thresholds carry cutoff + border_band + provenance + a
   `band_rule`; severity has a source-traceable `severity_basis`; meta_research
   establishes only REPORT/ROBUST; all prose fields in our own words (no 8+ word
   verbatim runs — machine-checked); every evidence quote verbatim (machine-checked).
7. **Decidability pre-mortem.** Before shipping, test EVERY check against the six
   empirically measured wobble modes; each has produced real coder splits:
   1. a scope trigger keyed on inferred behavior rather than an explicit declaration
      (scope flips cascade into every gated check);
   2. wrong silence polarity — a prohibition carrying FLAG-when-silent;
   3. a thresholded condition still containing a hedge ("may be weak"), with no
      explicit in-band verdict rule;
   4. a compound pass condition whose conjuncts can land in different evidence scopes
      (main text vs appendix) with no partial-satisfaction rule;
   5. a condition turning on unenumerated category membership ("counts as a
      robustness probe");
   6. a sufficiency judgment ("does this defense suffice?") shipped as if decidable.
   Fix modes 1–5 by rewording. For mode 6 ONLY, and only after a sharpening attempt
   fails, you may set `"judgment_call": true` with a `judgment_call_rationale` — this
   makes the borderline flag mandatory whenever the check is applied and moves it to a
   separately reported bucket in stability metrics. The judgment-call count is capped
   (~10% of checks, machine-enforced); it is an admission, not an escape hatch.

## Outputs

1. `{{OUT_JSON}}` — the FINAL checklist: same format as the proposal (header object
   first, `"_version": "verified"`), with your corrections applied. This is the artifact
   that ships; do not leave known defects for a later pass.
2. `{{OUT_ASSIGN}}` — final assignments JSONL covering EVERY claim in the ledger exactly
   once: `{"claim_id", "assigned_to", "justification"}` (check_id or `PARK:<reason>`).
3. `{{OUT_REPORT}}` — verification report: for each proposed check, verdict
   (KEPT | REWORDED | MERGED-INTO <id> | DISSOLVED) with one-paragraph reasoning quoting
   the deciding source passage verbatim (with line numbers); plus a section listing any
   inference leaps found (requirement vs what the source actually says).

## Output discipline

Write your output file(s) BEFORE composing your final message. The file is the
deliverable; the message is a courtesy. Sessions occasionally terminate mid-response --
a written file survives that, an unwritten one does not.

## Final message

Return ONLY: proposed -> final check counts; verdict tally (kept/reworded/merged/
dissolved); number of inference leaps found and the worst one in one sentence.
