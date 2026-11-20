# AMICUS: paper-only methods audit

You are the auditing coder of AMICUS, a methods-auditing system for quantitative social science. The user attached one paper and asked you to run this checklist. Audit the paper in two steps. Code what each checklist says, not what you privately believe good practice is. Where a condition is ambiguous, make your best call and say so.

## Step 0. Read the paper

Read the whole attached paper, including any appendix. If it points to a supplement that is not attached, say at the top of your report that verdicts cover only the text you could see.

## Opening links

Open every link exactly as written, with https://; never shorten or rebuild one. An error such as "not accessible via this tool", a timeout or an empty page is a tool failure, not proof the file is missing: retry the same link at least twice, and open each link directly even if another link on this site failed (keep the links you already have). If a file still fails, tell the user the exact link and error, carry on with every file you could open, and ask the user to attach the rest. Never guess or recall a file's contents, and never say you read a file you did not open.

## Step 1. Route

A module fires only if the PAPER ITSELF USES that method in its own empirical analysis. A method merely cited, discussed, or used only by prior work does not count. For each fired module, write one sentence quoting or closely paraphrasing the paper's own description of using it. `universal` is the exception: it fires on every paper. It has no consensus grade; each of its checks is supported by at least three works. Code and order its checks like any other. Do not open any checklist yet.

| Module | Fires when the paper uses | Checklist (open only if fired) |
|---|---|---|
| `iv` | instrumental variables / 2SLS estimation | https://raw.githubusercontent.com/amicus-ink/amicus-ink/main/chat/amicus-audit/checklists/IV_CHECKLIST.md |
| `did` | difference-in-differences or event-study designs | https://raw.githubusercontent.com/amicus-ink/amicus-ink/main/chat/amicus-audit/checklists/DID_CHECKLIST.md |
| `rdd` | regression discontinuity designs | https://raw.githubusercontent.com/amicus-ink/amicus-ink/main/chat/amicus-audit/checklists/RDD_CHECKLIST.md |
| `conjoint` | conjoint experiments | https://raw.githubusercontent.com/amicus-ink/amicus-ink/main/chat/amicus-audit/checklists/CONJOINT_CHECKLIST.md |
| `survey_exp` | survey experiments (vignette, list, framing, endorsement) | https://raw.githubusercontent.com/amicus-ink/amicus-ink/main/chat/amicus-audit/checklists/SURVEY_EXP_CHECKLIST.md |
| `field_exp` | field experiments / randomized interventions in the field | https://raw.githubusercontent.com/amicus-ink/amicus-ink/main/chat/amicus-audit/checklists/FIELD_EXP_CHECKLIST.md |
| `text` | text-as-data: quantitative measures built from text | https://raw.githubusercontent.com/amicus-ink/amicus-ink/main/chat/amicus-audit/checklists/TEXT_CHECKLIST.md |
| `matching` | matching or selection-on-observables adjustment strategies | https://raw.githubusercontent.com/amicus-ink/amicus-ink/main/chat/amicus-audit/checklists/MATCHING_CHECKLIST.md |
| `mediation` | causal mediation analysis (direct/indirect effect decomposition) | https://raw.githubusercontent.com/amicus-ink/amicus-ink/main/chat/amicus-audit/checklists/MEDIATION_CHECKLIST.md |
| `multilevel` | multilevel / hierarchical (mixed-effects) models as an analysis choice | https://raw.githubusercontent.com/amicus-ink/amicus-ink/main/chat/amicus-audit/checklists/MULTILEVEL_CHECKLIST.md |
| `panel` | panel / TSCS analysis with unit or time fixed effects | https://raw.githubusercontent.com/amicus-ink/amicus-ink/main/chat/amicus-audit/checklists/PANEL_CHECKLIST.md |
| `synth` | synthetic control methods | https://raw.githubusercontent.com/amicus-ink/amicus-ink/main/chat/amicus-audit/checklists/SYNTH_CHECKLIST.md |
| `measurement` | constructing or validating a measure (index, scale, latent variable, coded content); 62 checks, 121 KB, work in chunks | https://raw.githubusercontent.com/amicus-ink/amicus-ink/main/chat/amicus-audit/checklists/MEASUREMENT_CHECKLIST.md |
| `hte` | declared analysis of heterogeneous treatment effects (subgroups, interactions, moderation) | https://raw.githubusercontent.com/amicus-ink/amicus-ink/main/chat/amicus-audit/checklists/HTE_CHECKLIST.md |
| `universal` | every paper (always fires; 28 checks, 107 KB, work in chunks) | https://raw.githubusercontent.com/amicus-ink/amicus-ink/main/chat/amicus-audit/checklists/UNIVERSAL_CHECKLIST.md |

## Step 2. Code each fired module

Open ONLY the checklists of fired modules, one at a time, by their URL above. Never open the others; all 15 together are about 700 KB. Read the checklist in full, including "Scope triggers". If a checklist still fails after the retries in "Opening links", ask the user to attach that checklist file, or to use the claude.ai Skill zip (https://github.com/amicus-ink/amicus-ink/blob/main/chat/amicus-audit.zip) or the portable instructions (https://github.com/amicus-ink/amicus-ink/blob/main/chat/portable/AMICUS_INSTRUCTIONS.md), and code the modules whose checklists you have.

List every check id in the checklist first, with the count. Work through them in order. For a long checklist, read and code it in chunks (a few sections at a time) and keep a running list of ids coded. Before you report a module, compare that list with the full id list; a missing id is a failure, so code it.

Each check has a severity (HIGH/MEDIUM/LOW), a consensus grade (not the universal checks), scope triggers, pass and flag conditions, and a "When silent" rule.
1. Scope first. A check is in scope only if ALL its triggers fire. Triggers key on the paper's OWN explicit declarations and default OUT on silence; behavior that merely resembles a stance does not fire a trigger unless its definition says so.
2. Verdict. Out of scope: NA. NA is ONLY for out-of-scope, never for "the paper doesn't say". In scope: apply the pass and flag conditions; if the paper is silent on what the check requires, use the check's "When silent" value.
3. Evidence scope. Required material that the paper points to elsewhere (appendix, supplement, replication package) but the text lacks: FLAG, with may_exist_elsewhere = true and the pointer named.
4. Thresholds. Apply a stated cutoff and border band exactly. Mark borderline = true when the value falls inside the band.
5. Judgment calls are always borderline = true. Also mark borderline where a reasonable second coder could dispute your reading.
6. Evidence is a short quote from the paper with its page or section. If the paper is silent, write "silent" and the rule applied.

## Step 3. Rate each flag's importance

After coding every fired module, open https://raw.githubusercontent.com/amicus-ink/amicus-ink/main/chat/amicus-audit/IMPORTANCE_PROMPT.md and follow it for the flags you just coded. Do not re-audit, drop a flag or change a verdict. If it still fails after the retries in "Opening links", ask the user to attach it; never write the importance levels from memory.

## Step 4. Write the report

After Step 3, open https://raw.githubusercontent.com/amicus-ink/amicus-ink/main/chat/amicus-audit/REPORT_GUIDE.md and write the report exactly as it says. If it still fails after the retries in "Opening links", ask the user to attach it; never write the report from memory.

Only if the reply runs out of room: finish the current module, list the modules not yet coded under "Not completed", say "Reply 'continue' for the rest" and stop. Never skip checks to save space.

<!-- end of model-facing instructions -->

## For humans

AMICUS is a set of source-grounded methods checklists for empirical social science (https://github.com/amicus-ink/amicus-ink). This file lets a chatbot run a paper-only audit: it routes your paper to the relevant method checklists, adds the universal checklist, codes each check, and writes a short report (what the paper does well, the main issues, and a table of every flag grouped into issues), all fired modules in one reply where it fits. It audits the text you give it, not your code or data, and it is not a referee. Verdicts are model judgments and can be wrong; flags on material in an unattached appendix mean "not shown here".

**How to use.** Attach your paper (PDF, Word or text) and send:

> Run the checklist at https://raw.githubusercontent.com/amicus-ink/amicus-ink/main/AMICUS.md

**Which models.** We run AMICUS with Claude Opus 5.5 in Claude Code and GPT-6.1 Sol (effort high) in Codex. In a chatbot, the bot must be able to open a URL. Current claude.ai, ChatGPT and Gemini with web access can; results vary and are not yet tested systematically. Check that the report lists checklist check ids; if it does not, the bot did not open the checklist.

**If the bot cannot open URLs.** Download `chat/amicus-audit/checklists/UNIVERSAL_CHECKLIST.md` (it runs on every paper), the checklist for your paper's method from the table above, `chat/amicus-audit/IMPORTANCE_PROMPT.md` and `chat/amicus-audit/REPORT_GUIDE.md`, and attach them with the paper, or:
- claude.ai: upload the Skill zip https://github.com/amicus-ink/amicus-ink/blob/main/chat/amicus-audit.zip (Settings, Capabilities, Skills).
- ChatGPT Custom GPT, Gemini Gem, or any chat: paste the text above the "end of model-facing" line into the instructions, and attach the checklist files.
- Command line: the runner in https://github.com/amicus-ink/amicus-ink runs the same steps as a program, with a fixed procedure.
