# Claim mining — {{MODULE_NAME}}, group {{GROUP_ID}}

You are performing Phase 1 (claim mining) of a source-first checklist generation run.

## Clean-room rule (absolute)

Derive claims ONLY from the source texts listed below. Do NOT read, search for, or
consult any existing checklist, skill file, module skill, claim ledger, or prior
generation run anywhere in this repository — in particular nothing under
`skills/methods/`, no `*_MODULE_SKILL.md`, no `*_CHECKLIST*.json`, and no other
directory under `runs/skill_generation/` except your own output path. If you catch
yourself trying to match a claim to something you expect a checklist to contain, stop:
your job is to record what THESE papers say, blind to everything downstream.

## Sources (read each IN FULL)

{{SOURCE_LIST}}

Each text file is a column-aware extraction: lines are prefixed `L<n>: ` and PDF pages
are marked `=== PDF PAGE n ===`.

## What to extract

Every **normative claim**: any statement that a researcher using these methods
should/must do something, that some practice is invalid/biased/misleading, or that an
assumption is required for a result to hold. Include claims about assumptions, estimator
validity, diagnostics/tests, inference/uncertainty, and reporting. A claim that an
estimator is inconsistent under stated conditions IS normative (it implies "check this").
Be exhaustive — err toward recording; the clustering pass parks, it cannot recover what
you never wrote down.

Do NOT record pure motivation ("method X is popular"), software implementation trivia,
or descriptions of a paper's empirical examples, unless they carry a normative
requirement.

## The modal test (applied AT MINING TIME)

Sources speak in two moods and you must record which one each claim is in:

- `"modality": "requirement"` — stated as necessary: "must", "requires", "rests on",
  "is invalid unless", "is inconsistent when", "cannot be interpreted as ... without".
- `"modality": "advice"` — stated as recommendation or practice: "we recommend",
  "researchers may choose", "there is little need for", "the best practice would be",
  "one strategy is", "it is useful to".

Beware papers whose closing pages are a practical checklist or user guide for the
authors' own software: those bullets are workflow advice, not requirements, however
imperative they sound. Record them as `advice` — do not skip them, the ledger must be
complete — but do not dress them as requirements. Also: a claim about what THE ANALYST
should do in sequence (try X first, then Y) is advice about process; a claim about what
A PAPER must state or satisfy is a requirement candidate.

## Source-type rules

Each source's `source_type` is given above and must be copied into every claim row.
`meta_research` sources (reviews/audits of practice) may establish only
reporting/robustness expectations and prevalence evidence — still record everything they
say, with honest `strength`, and clustering will apply the rule.

## Output

Write JSONL to:

    {{CLAIMS_OUT}}

One row per claim, exactly this schema:

```json
{
  "claim_id": "<source_id>-C-01",
  "source_id": "<source_id>",
  "short_cite": "<as given above>",
  "source_lines": "L123-125",
  "quote": "...",
  "claim_text": "...",
  "strength": "establishes",
  "modality": "requirement",
  "source_type": "methodological",
  "scope_conditions": "..."
}
```

- `claim_id`: the source_id, then `-C-`, then a zero-padded 2-digit sequence per source.
- `quote`: a VERBATIM substring of the source text — a single contiguous passage. Copy
  exactly; do not paraphrase, fix typos, or join fragments with ellipses. Every quote is
  machine-verified against the file; one failure blocks the whole run.
- `claim_text`: the normative content in YOUR OWN words, one sentence. Never reuse the
  source's phrasing — runs of 8+ verbatim words in our own prose are a blocking defect.
- `strength`: `establishes` | `qualifies` | `mentions`.
- `scope_conditions`: when the claim applies (e.g. "overidentified models only",
  "all IV designs", "conditional-on-covariates validity arguments").

## Output discipline

Write your output file(s) BEFORE composing your final message. The file is the
deliverable; the message is a courtesy. Sessions occasionally terminate mid-response --
a written file survives that, an unwritten one does not.

## Final message

Return ONLY: the claim count per source, and one line listing the topic areas covered.
