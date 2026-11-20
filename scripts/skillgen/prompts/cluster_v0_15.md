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
12. **Adjacency does not fire, and ambiguity resolves OUT (v0.13).** Strengthens rule 7.
    A scope trigger fires only on the paper's own explicit language — the term, method, or
    design it names or adopts. A merely *adjacent* practice does NOT fire it: random
    intercepts used as a nuisance are not a declared multilevel analysis; grid-cell or
    repeated observations are not a declared clustered-error structure; comparing the
    author's own two studies is not a declared replication. When it is genuinely unclear
    whether the paper declared the trigger, the check is **out of scope (NA)** — the coder
    never resolves the ambiguity by inferring what the paper "really is." Consequence to
    state in each gated check's scope definition: a coder decides fired-vs-not from the
    paper's words alone, so there is never a choice between NA and FLAG for the same paper
    — a fired trigger on a silent paper takes `verdict_when_silent`; an unfired-or-ambiguous
    trigger is NA. (This NA-vs-FLAG coin-flip is the single largest source of instability
    in the matching/mediation/multilevel/survey_exp diagnostics.)
13. **Evidence location is immaterial (v0.13).** A required practice reported anywhere in
    the paper OR its appendices, supplementary information, footnotes, or replication
    materials satisfies the check exactly as if it were in the main text. Pass/flag
    conditions must turn on whether the practice is present and findable, never on where it
    sits or how prominently. Do not write a condition that requires main-text placement.

14. **Scope-trigger definitions are crisp paper-observable tests (v0.15).** Operationalizes
    rule 12. Write each `_scope_definitions` entry so two coders reading the same paper reach
    the same fired/not-fired decision. Define a trigger by a concrete feature the paper states
    about itself — the term it uses, the design it declares, the data structure it describes —
    never by an abstract category a coder must sort the paper into. The trigger fires only on
    that explicit self-description; a paper that does not describe itself in the trigger's terms
    is out of scope, and the coder does not infer the category from surrounding detail.
    `panel_tscs` fires when the paper says it observes the same units over multiple periods and
    models them across time, not when a coder judges the data "panel-like"; `covariate_adjusted`
    fires when the paper states it conditions its estimate on covariates, not when a coder
    decides adjustment was warranted. A declared trigger whose definition still leaves a
    borderline paper undecided is the largest remaining source of NA-vs-fires instability — a
    self-description test removes the borderline.

15. **Verdict bars are concrete and countable, never degree words (v0.15).** Extends the
    threshold rule to `pass_condition` and `flag_condition`. A verdict turns on a specific
    paper-observable artifact or an explicit count. A degree word as the deciding term —
    "a range of", "several", "many", "adequately", "sufficiently", "appropriate", "robust to",
    "some" — is not decidable. Replace it: "reports the estimate across a range of bandwidths"
    becomes "reports the estimate at two or more distinct bandwidths"; "runs many tests" becomes
    a scope trigger keyed on the paper's own stated count. Where the sources fix no number, name
    the minimal concrete observable that settles PASS versus FLAG — a named table, a stated
    procedure — so the same paper yields the same verdict for any coder.

## Item schema (fixed — every field, exactly these names)

Categories: IDENT | EST | INFER | ROBUST | REPORT | DATA. Check ids: `{{ID_PREFIX}}-<CAT>-NN`.

```json
{
  "check_id": "{{ID_PREFIX}}-IDENT-01",
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
