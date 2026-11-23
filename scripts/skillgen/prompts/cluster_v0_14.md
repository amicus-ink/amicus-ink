# Clustering — {{MODULE_NAME}}: claims -> proposed checklist

You are performing Phase 2 (clustering) of a source-first checklist generation run: turn
a verified claim ledger into a proposed audit checklist. A separate, independent agent
will adversarially verify your proposal — your job is a faithful, well-structured first
pass, not the final word.

## Clean-room rule (absolute)

Read ONLY the claim ledger and, where you need context for a quote, the source texts.
Do NOT read any existing checklist or skill file anywhere in this repository (nothing
under `skills/methods/`, no `*_MODULE_SKILL.md`, no other `runs/skill_generation/`
directory). The checklist must be what THESE claims support — not what you expect a
{{MODULE_NAME}} checklist to contain.

## Inputs

- Claim ledger (every quote already machine-verified verbatim): `{{CLAIMS_FILE}}`
- Source texts, for context reads only: `{{TEXT_DIR}}/`

## Clustering law

1. **Narrowest first.** Propose the most specific checks first, then broader ones from
   the remaining claims. Broad checks must not swallow claims that state a narrower,
   distinct requirement.
2. **Every claim gets exactly one home**: one check, or a PARK. No claim on two checks;
   no claim dropped silently.
3. **Modality governs.** A check may be ESTABLISHED only by `modality: "requirement"`
   claims. `advice` claims may qualify an existing check (support_relation "qualifies")
   or be parked (`PARK:workflow_advice`) — a check resting only on advice is invalid.
4. **A check is decidable from what a paper records, not from what its author did.**
   If the observable is the analyst's process (an order of operations, a sequence of
   model choices) rather than the paper's content, it is not a check — park it.
5. **meta_research sources** may establish only REPORT/ROBUST checks and prevalence
   aggravators; elsewhere they may only qualify.
6. **Park reasons**: `PARK:implementation_detail`, `PARK:motivation_only`,
   `PARK:workflow_advice`, `PARK:new_check_candidate` (real requirement, insufficient
   grounding), `PARK:duplicate` (same requirement, same source, weaker statement).
7. **Triggers key on declarations, not behavior.** Every scope-trigger definition must
   take the form "Does the paper explicitly state / name / adopt X?" and must name at
   least one near-miss behavior that does NOT fire it. Running subgroup analyses is not
   adopting a heterogeneous-effects estimand; clustered standard errors in a table are
   not a declared error structure. Behavior-keyed triggers are the single largest
   measured source of coder instability (a scope flip cascades into every gated check).
8. **Silence polarity follows requirement type.** Tag every check
   `requirement_type: "positive"` (the paper must state/report/do X → silence FLAGs) or
   `"prohibition"` (the paper must not do X → silence PASSes; absence of the bad
   practice is compliance). A prohibition carrying FLAG-when-silent forces coders to
   flag papers that did nothing wrong — this is machine-rejected downstream.
9. **Thresholded checks state the verdict in all three regions.** Where a check carries
   a numeric cutoff, its conditions must give the verdict below the cutoff, inside the
   border band, and above it, and the threshold object must carry a `band_rule` (e.g.
   "in band: PASS only if identification-robust inference is also reported; borderline
   flag mandatory"). Hedge words ("may be weak", "in doubt", "adequate") in a
   thresholded check's conditions are machine-rejected — the cutoff decides, not the
   coder's temperament.
10. **One observable per check.** A pass condition joining two distinct observables
    ("reports X together with Y") is presumptively two checks — split it. Where a
    split is genuinely wrong, state the partial-satisfaction verdict explicitly,
    including what happens when one part sits in an appendix the audit cannot see.
11. **Enumerate category membership.** A condition that turns on whether an activity
    "counts as" X (a robustness probe, a validity check) must enumerate the qualifying
    activities, sourced from the corpus. Unenumerated categories are where coders
    split 4-to-1.
12. **Stable `concept_key` per check (v0.14 — reproducibility).** Every check carries a
    `concept_key`: a `snake_case` slug naming the single audit concept it tests, using the
    concept's standard name — the term the SOURCES themselves use most often for it
    (e.g. `instrument_relevance`, `exclusion_restriction`, `weak_instrument_strength`,
    `monotonicity`, `overidentification_test`, `cluster_robust_inference`). The key names
    the *concept*, never the wording: two checklists that test the same concept must land on
    the same key, so keys are comparable across runs and versions even when the prose and the
    positional `check_id` differ. Prefer the shortest widely-used name; never coin a new name
    when a standard one exists in the corpus. One concept per key; one key per check.
13. **Deterministic category (v0.14).** Assign `category` by this order — the check takes the
    FIRST whose description matches its *core* concern:
    (1) **IDENT** — an assumption required for the estimand to be causally identified
    (relevance, exclusion, unconfoundedness, monotonicity, parallel trends);
    (2) **EST** — a property of the estimator itself: bias, consistency, functional form,
    finite-sample behavior, aggregation of heterogeneous effects;
    (3) **INFER** — standard errors, test statistics, confidence intervals, p-values and
    their validity;
    (4) **ROBUST** — sensitivity/falsification: does the result survive alternative
    specifications, placebos, bounds, or assumption violations;
    (5) **REPORT** — what the paper must disclose;
    (6) **DATA** — sample construction, coverage, missingness, measurement, attrition.
    A check about whether a *needed assumption holds* is IDENT even when checked via a test;
    a check about whether *reported uncertainty is valid* is INFER even when it rests on an
    assumption. When two fit, take the earlier. (The same weak-IV check landing in ROBUST one
    run and INFER another was a measured instability this order removes.)
14. **Granularity discipline (v0.14).** A distinct audit concept supported by ≥2 independent
    claims (different sources, or different passages of one source) MUST become its own
    check — do not fold it into a neighbor. PARK a claim only when it is a strict duplicate
    (same requirement, same source, weaker statement), an implementation detail, or
    motivation. Never merge two distinct concepts into one check to shorten the list:
    checklist length follows the corpus, not a target. (A concept present in every ledger
    but dropped from one run's checklist was a measured reproducibility loss this prevents.)

## Item schema (fixed — every field, exactly these names)

Categories: IDENT | EST | INFER | ROBUST | REPORT | DATA. Check ids: `{{ID_PREFIX}}-<CAT>-NN`.

```json
{
  "check_id": "{{ID_PREFIX}}-IDENT-01",
  "concept_key": "instrument_relevance",
  "category": "IDENT",
  "scope": ["all"],
  "claim": "<what the sources assert, in our own words>",
  "observable": "<what a coder looks at in a paper to decide>",
  "pass_condition": "<decidable>",
  "flag_condition": "<decidable>",
  "requirement_type": "positive",
  "verdict_when_silent": "FLAG",
  "severity_if_flagged": "HIGH",
  "severity_basis": "<traceable to a source>",
  "prevalence_aggravator": null,
  "threshold": null,
  "coder_decidable": true,
  "requirement_statement": "<one sentence, our own words>",
  "contributing_sources": ["..."],
  "evidence": [
    {"source_id": "...", "short_cite": "...", "source_lines": "L12-14",
     "quote": "<verbatim, single contiguous passage>", "support_relation": "establishes"}
  ]
}
```

`requirement_type` ∈ {`positive`, `prohibition`}; the silence polarity it implies
(positive → FLAG, prohibition → PASS) is machine-enforced. A non-null threshold with a
`border_band` must also carry `"band_rule": "<verdict rule inside the band>"`.

Rules that are the whole point:

- **`verdict_when_silent` is FLAG or PASS, never NA.** NA is the scope gate's job alone.
  FLAG for positive requirements ("the paper must state/report X"); PASS for
  absence-of-misuse ("the paper must not do Y" — silence means it didn't).
- **Scope triggers are decidable yes/no questions about a paper**, keyed on the paper's
  OWN explicit stance, defaulting OUT on silence. Define every trigger you use in the
  header's `_scope_definitions`. Where a trigger's silence buries a finding worth
  surfacing, add an author-facing **clarity check** instead (an `all`-scope REPORT check
  with `"clarity_check": true` and `author_guidance` telling the author what to state).
- **Thresholds**: where sources give a numeric cutoff, record
  `{"cutoff": ..., "border_band": [lo, hi], "provenance": "theoretical" | "conservative_bound" | "rule_of_thumb"}`.
  Never leave a vague quantifier ("small", "weak", "adequate") deciding a verdict.
- **Our own words everywhere except `evidence[].quote`.** `claim`, `observable`,
  conditions, `requirement_statement` must not carry runs of 8+ verbatim source words —
  that is machine-checked and blocking.
- Every evidence `quote` must be verbatim in its source text file (machine-gated).

## Checkpoint (interruption insurance)

Before drafting checks, write your working topic map (claim groups and the checks you
intend to propose from them) to the run's `cluster_review/topic_map.md`, and update it
as your plan firms up. If that file already exists from an interrupted attempt of THIS
run, you may use it as a starting draft -- verify it against the ledger rather than
trusting it. It is a scratchpad, not a deliverable.

## Outputs

1. `{{OUT_PROPOSED}}` — a JSON array whose FIRST element is a header object:

```json
{"_module": "{{ID_PREFIX}}", "_version": "proposed",
 "_scope_vocabulary": ["all", "..."],
 "_scope_definitions": {"all": "...", "...": "..."},
 "_note": "<anything a reviewer must know>"}
```

followed by the check items.

2. `{{OUT_ASSIGN}}` — JSONL, one row per claim in the ledger (ALL of them):

```json
{"claim_id": "...", "assigned_to": "{{ID_PREFIX}}-IDENT-01", "justification": "<one sentence>"}
```

(`assigned_to` is a check_id or a `PARK:<reason>`.)

## Output discipline

Write your output file(s) BEFORE composing your final message. The file is the
deliverable; the message is a courtesy. Sessions occasionally terminate mid-response --
a written file survives that, an unwritten one does not.

## Final message

Return ONLY: check count by category, park count by reason, and the scope-trigger list.
