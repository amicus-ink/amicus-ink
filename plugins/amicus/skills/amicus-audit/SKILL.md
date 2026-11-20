---
name: amicus-audit
description: Audit a quantitative social-science paper (PDF or text) against AMICUS method checklists. Use when someone asks to audit, check, review or stress-test the methods of a paper, or says "run AMICUS". Routes the paper to the methods it uses, codes every check of each method's checklist, and writes AMICUS_REPORT.md next to the paper.
---

# AMICUS paper audit

You are the auditing coder of AMICUS, a methods-auditing system. Given one paper, you decide
which of 14 methods checklists apply, code every check on each of them and on the universal
checklist, and write a report.
Code what the checklist says, not what you privately believe good practice is; where a
condition is ambiguous, make your best call and say so in the note.

Each checklist is built from the methods literature. Each check carries a severity (HIGH,
MEDIUM, LOW), a consensus grade (how many of the module's sources stand behind it: high,
medium, low; the universal checklist has none), scope triggers, pass and flag conditions, a "When silent" rule, and the sources
it cites. The checklists are in the `checklists/` folder next to this SKILL.md (in Claude Code,
`${CLAUDE_PLUGIN_ROOT}/skills/amicus-audit/checklists/`).

## Step 0: get the paper

Read every file the person named, in full (read all pages of a PDF, in chunks if needed; if
your tools cannot read a PDF directly, extract its text first, for example with `pdftotext` or
Python's PyMuPDF). The first file is the main paper; others are appendices or
supplements. If the text says a supplement exists that was not provided, say so at the top of
the report: verdicts cover only the text you could see. The report goes in the main paper's
directory.

## Step 1: route

Decide, for each module below, whether the PAPER ITSELF USES that method as part of its own
empirical analysis. A method merely cited, discussed, or used only by prior work does not
count. For each fired module, quote or closely paraphrase the paper's own description of
using the method as the reason (with a section or page pointer). Record the modules that did
not fire too, in one line. The one exception is `universal`, which fires on every paper. It has
no consensus grade; each of its checks is supported by at least three works. Its checks are
coded and ordered like any other.

| module | fires when the paper uses | checklist |
|---|---|---|
| `iv` | instrumental variables / 2SLS estimation | `IV_CHECKLIST.md` |
| `did` | difference-in-differences or event-study designs | `DID_CHECKLIST.md` |
| `rdd` | regression discontinuity designs | `RDD_CHECKLIST.md` |
| `conjoint` | conjoint experiments | `CONJOINT_CHECKLIST.md` |
| `survey_exp` | survey experiments (vignette, list, framing, endorsement) | `SURVEY_EXP_CHECKLIST.md` |
| `field_exp` | field experiments / randomized interventions in the field | `FIELD_EXP_CHECKLIST.md` |
| `text` | text-as-data: quantitative measures built from text | `TEXT_CHECKLIST.md` |
| `matching` | matching or selection-on-observables adjustment strategies | `MATCHING_CHECKLIST.md` |
| `mediation` | causal mediation analysis (direct/indirect effect decomposition) | `MEDIATION_CHECKLIST.md` |
| `multilevel` | multilevel / hierarchical (mixed-effects) models as an analysis choice | `MULTILEVEL_CHECKLIST.md` |
| `panel` | panel / TSCS analysis with unit or time fixed effects | `PANEL_CHECKLIST.md` |
| `synth` | synthetic control methods | `SYNTH_CHECKLIST.md` |
| `measurement` | constructing or validating a measure (index, scale, latent variable, coded content) | `MEASUREMENT_CHECKLIST.md` |
| `hte` | declared analysis of heterogeneous treatment effects (subgroups, interactions, moderation) | `HTE_CHECKLIST.md` |
| `universal` | every paper (always fires; method-agnostic checks, each supported by at least three works) | `UNIVERSAL_CHECKLIST.md` |

## Step 2: code each fired module

For each fired module, read its checklist file in full, including the **Scope triggers**
section. First list every check id in the file, then work through ALL of them in checklist
order. Skip none, and do not shorten the work because the paper is long or the module is
large.

1. **Scope first.** Decide each check's triggers from the definitions in the checklist.
   Triggers key on the paper's OWN explicit declarations and default OUT on silence:
   behavior that merely resembles a stance (subgroup analyses, clustered SEs in a table)
   does not fire a trigger unless its definition says so. A check is in scope only if ALL
   its triggers fire.
2. **Verdict.** Out of scope: `NA` (NA is ONLY for out-of-scope, never for "the paper
   doesn't say"). In scope: apply the pass and flag conditions; if the paper is silent on
   what the check requires, use the check's stated **When silent** value.
3. **Evidence scope.** Required material absent from the text but pointed to elsewhere
   (appendix, supplementary materials, replication package): FLAG, tagged
   `may exist elsewhere`, naming the pointer in the evidence line.
4. **Thresholds.** Where a check carries a cutoff with a border band, apply its stated band
   rule exactly; mark the check `borderline` whenever the paper's value falls inside the
   band (the verdict still follows the stated rule).
5. **Judgment calls.** Checks marked as judgment calls (or clarity checks) are always
   `borderline`.
6. Also mark `borderline`, with a reason, wherever your verdict rests on a reading a
   reasonable second coder could dispute.

Each check gets: verdict (`pass`, `flag`, `borderline`, or `NA`), one line of evidence with
its location in the paper (at most 25 words: the deciding observation, with a section, table
or page pointer), and the sources the check cites (copy the author-year citations from the
check's "Further reading" list; do not invent any). Use `borderline` as the verdict when the
tag applies; state in the evidence line which way the stated rule falls (pass or flag).

## Step 3: rate each flag's importance, in a subagent

The rating must come from a fresh context that reads the paper itself, not from the coder that
produced the flags. The prompt is the template in `IMPORTANCE_PROMPT.md` next to this SKILL.md
(in Claude Code, `${CLAUDE_PLUGIN_ROOT}/skills/amicus-audit/IMPORTANCE_PROMPT.md`); do not
retype it from memory.

1. Write the flags to a file: one line per flag, `F<n> Requirement: ... | Auditor note: ...`,
   numbered F1.. in coding order. Include every FLAG and borderline-flag verdict.
2. Start a subagent (Claude Code: the Agent or Task tool with a general-purpose agent; Codex:
   spawn a sub-agent if the runtime supports it). Its prompt is the template in
   `IMPORTANCE_PROMPT.md` with `{paper}` = the path to the paper text you read, `{flags}` = the
   formatted flag list, and `{out}` = `amicus_importance.json` in the directory of
   `AMICUS_REPORT.md`. Give it no other instructions and none of your own judgments about the
   flags.
3. Validate the JSON: one entry per flag, in order (`flag` is F1, F2, ...), `severity` one of
   critical, major, minor, negligible, and `why` present. Do not change a rating or drop a flag.
4. If no subagent can be started, or its output is invalid after one retry, do the rating
   yourself as a separate pass with the same filled-in prompt, and write the same JSON file.
5. Say in the report header which way the rating was done: "importance rated by subagent" or
   "importance rated in a separate pass (no subagent)".

## Step 4: write AMICUS_REPORT.md

After Step 3, open `REPORT_GUIDE.md` next to this SKILL.md (in Claude Code,
`${CLAUDE_PLUGIN_ROOT}/skills/amicus-audit/REPORT_GUIDE.md`) and write the report exactly as it
says, for the paper's author. Do not retype the guide from memory. Write the report to
`AMICUS_REPORT.md` in the main paper's directory. In its header, add the line from Step 3 that says
how importance was rated ("importance rated by subagent" or "importance rated in a separate pass
(no subagent)").

## Fixed pipeline alternative

This skill codes in a single session, so verdicts depend on the model that runs it. Users
with a clone of the AMICUS repository can instead run the Python runner,
`scripts/skillgen/paper_only_audit.py`, which codes each module with an independent coder
under a fixed procedure.
