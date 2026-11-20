# Coder procedure — {{MODULE_NAME}} checklist ({{KIND}})

You are ONE independent coder applying the {{MODULE_NAME}} audit checklist to ONE
paper. Others are doing the same paper without seeing your work; the exercise measures
whether the checklist's conditions are sharp enough that independent readers land on
the same verdicts. Code what the checklist says, not what you privately believe good
practice is; where a condition is ambiguous, make your best call and say so in the
note — ambiguity findings are the product, not a failure.

## Independence rules

Do NOT read any other coder's or sample's output, any prior decidability run, any
earlier checklist or skill file, or the claim ledger / source texts. Your inputs are
exactly the two files below.

## Inputs

1. The checklist (read in full first, including the Scope triggers section):
   `{{CHECKLIST_MD}}`
2. Your assigned paper (full read): `{{PAPER_PATH}}`

Evidence scope: the provided text only (main text; appendices are not included).

## Coding rules

1. **Scope first.** Decide each check's triggers from the definitions in the
   checklist. Triggers key on the paper's OWN explicit declarations and default OUT on
   silence — behavior that merely resembles a stance (subgroup analyses, clustered SEs
   in a table) does not fire a trigger unless its definition says so. A check is in
   scope only if ALL its triggers fire.
2. **Verdict.** Out of scope → `NA` (NA is ONLY for out-of-scope, never for "the paper
   doesn't say"). In scope: apply the pass/flag conditions; if the paper is silent on
   what the check requires, use the check's stated **When silent** value.
3. **Evidence-scope rule.** Required material absent from the provided text but
   pointed to elsewhere (appendix, supplementary materials, replication package) →
   FLAG with `may_exist_elsewhere: true`, naming the pointer in your note.
4. **Thresholds.** Where a check carries a cutoff with a border band, apply its stated
   band rule exactly; set `borderline: true` whenever the paper's value falls inside
   the band (the verdict still follows the stated rule).
5. **Judgment calls.** Checks marked as judgment calls REQUIRE `borderline: true` on
   every application — record your verdict and reasoning; disagreement is expected and
   tracked separately there.
6. Also set `borderline: true`, with a note, wherever your verdict rests on a reading
   a reasonable second coder could dispute.
7. Work through ALL {{N_CHECKS}} checks in checklist order. Skip none.

## Output

Write a JSON array of exactly {{N_CHECKS}} objects, in checklist order, to:

    {{OUT_PATH}}

```json
{
  "check_id": "...",
  "in_scope": true,
  "triggers_fired": ["all"],
  "verdict": "PASS",
  "borderline": false,
  "may_exist_elsewhere": false,
  "note": "<= 25 words: the deciding observation, with a section/table pointer"
}
```

`verdict` ∈ {PASS, FLAG, NA}; `in_scope: false` ⇔ `verdict: "NA"`.

## Output discipline

Write your output file BEFORE composing your final message. The file is the
deliverable; the message is a courtesy.

## Final message

Return ONLY: counts (PASS/FLAG/NA), the borderline check_ids, and your single hardest
call in one sentence.
