# AMICUS

*Version 0.1, alpha (November 2026). Expect rough edges, and please report problems as issues.*

AMICUS is based on a set of source-grounded method checklists for empirical social science. Each checklist is built from the methods literature, either on general research design, or on a specific research design (instrumental variables, difference-in-differences, conjoint experiments, and so on). A language model reads the text of your paper, decides which designs it uses, and works through the matching checklist check by check. The output is an author-facing report. It tells you what the language model thinks you haven't yet done, and gives the citations for the sources.

AMICUS will always be free and open.

AMICUS checks the paper, not (yet) the replication code. It needs only the paper text (and any appendix you supply).

## The name

AMICUS is named for the amicus brief: outside input offered to help get the record right. It is a friend of the paper; you are the judge. It reads your draft, tells you what the methods literature asks of it, and leaves the decisions to you. The name expands to **A**uthor/AI **M**ethods **I**nterlocutor: **C**ompanion to **U**pgrade **S**cholarship. The interlocutor is the author's.

## What it is not

- It is not a referee. There is no score, no recommendation, and no judgment about whether your result is right.
- It is not a replication. Nothing is re-run, and no data or code is opened.
- Its verdicts are model judgments and can be wrong. Some checks are judgment calls; the report marks these "close call".
- The paper's silence is itself a verdict. If a check requires the paper to report something and the text does not, the check's "when silent" rule applies, usually a flag. A flag therefore means "not reported in the text you gave the model". The practice may exist in an appendix you did not supply or in the analysis but not the write-up.

## The modules

The current set has 14 method checklists and 270 checks. One more checklist, `universal`, has 28 checks and applies to every paper. A fifteenth method, causal machine learning, is in development.

| Module | Covers | Checks | Diagnostic | Pilot |
|---|---|---|---|---|
| `iv` | Instrumental variables, 2SLS | 13 | 87.2% | 98.1% |
| `did` | Difference-in-differences, event studies | 16 | 100.0% | 100.0% |
| `rdd` | Regression discontinuity designs | 23 | 85.5% | 92.8% |
| `conjoint` | Conjoint experiments | 14 | 100.0% | 100.0% |
| `survey_exp` | Survey experiments (vignette, list, framing, endorsement) | 24 | 89.6% | 93.8% |
| `field_exp` | Field experiments and randomized interventions | 23 | 92.4% | 98.9% |
| `text` | Text as data: quantitative measures built from text | 17 | 88.2% | 100.0% |
| `matching` | Matching and selection-on-observables adjustment | 12 | 91.7% | 95.8% |
| `mediation` | Causal mediation (direct and indirect effects) | 12 | 91.7% | 100.0% |
| `multilevel` | Multilevel and mixed-effects models | 10 | 97.5% | 97.5% |
| `panel` | Panel and time-series cross-section analysis | 11 | 93.2% | 100.0% |
| `synth` | Synthetic control | 9 | 92.6% | 100.0% |
| `measurement` | Building or validating a measure (index, scale, latent variable, coded content) | 62 | 85.5% | 92.7% |
| `hte` | Heterogeneous treatment effects (subgroups, interactions, moderation) | 24 | 94.2% | 95.8% |

Where the counts come from: each module's shipping checklist is `runs/skill_generation/<run>/checklists/verified.anchored.json`, where `<run>` is the module's entry in the `SHIPPING` table in `scripts/skillgen/paper_only_audit.py`. The counts above are the number of rows with a `check_id` in each file, using the runner's own `load_checks`. They sum to 270. The universal checklist is in `runs/skill_generation/20261113_universal_v1_streamlined`; it has 28 rows with a `check_id`.

The last two columns are the checklist's reliability, measured on political science test papers: **diagnostic** is how stable each verdict is across five independent codings of the same paper, and **pilot** is how often two independent coders agree. The counts behind each figure are in each module's `MANIFEST.json`. Our target is 95% on the diagnostic. It is a target, not a requirement: only `did`, `conjoint` and `multilevel` meet it now. The universal checklist was not measured in this way.

The universal module applies to every paper. A method-specific module fires only if the paper itself uses the method. A method that the paper merely cites, or that only prior work uses, does not count.

## Ways to run it

There are two routes: an online chatbot, or a coding agent on your own computer. Both use the same checklists, and your paper goes only to the model provider you already use.

### 1. In an online chatbot

Nothing to install.

Attach your paper to a chat (Claude, ChatGPT, Gemini or similar) and say: "Run the checklist at https://github.com/amicus-ink/amicus-ink/blob/main/AMICUS.md". That file tells the chatbot how to route your paper to the relevant methods and then fetch only the matching checklist from this repository. It depends on the chatbot being able to open URLs; if yours cannot, `AMICUS.md` says what to paste instead.

This route has no fixed coder and no validation step, so results vary by service and are less consistent than the Python runner in route 2. Treat them as a first pass.

### 2. With a coding agent on your computer (Claude Code, Codex, OpenCode)

The report is written to `AMICUS_REPORT.md` next to your paper. The quickest way is the plugin or skill, which needs no Python and no clone. For the most consistent results, use the Python runner described after it.

**Claude Code.** Install the plugin once:

```
/plugin marketplace add amicus-ink/amicus-ink
/plugin install amicus@amicus
```

Then, in any Claude Code session:

```
/amicus path/to/paper.pdf [path/to/appendix.pdf]
```

**Codex.** Install the plugin once from the command line:

```
codex plugin marketplace add amicus-ink/amicus-ink
codex plugin add amicus@amicus
```

Then, in a Codex session in the paper's folder, ask: "Run AMICUS on paper.pdf".

**OpenCode and other agents.** Any agent that reads [Agent Skills](https://agentskills.io) can use the same skill. Copy its folder into the agent's skills folder and ask the same thing:

```
git clone --depth 1 https://github.com/amicus-ink/amicus-ink /tmp/amicus-ink
mkdir -p ~/.agents/skills && cp -R /tmp/amicus-ink/plugins/amicus/skills/amicus-audit ~/.agents/skills/
```

In each case the plugin routes the paper, codes every check of each fired module from the checklists bundled with the plugin, and writes `AMICUS_REPORT.md` next to the paper. In Claude Code, if another plugin also defines `/amicus`, use `/amicus:amicus`. The coding happens inside your session. It has neither the separate call per module nor the output validation of the Python runner.

#### The Python runner (Claude Code or Codex)

The runner runs the full pipeline: route the paper to modules, code each module with an independent model call, and write a report. It gives the most consistent results because the coding rules and the output format are fixed by the script.

Setup, the commands, the options, the output files and the exit codes are in [docs/RUNNER.md](https://github.com/amicus-ink/amicus-ink/blob/main/docs/RUNNER.md).

**How to read the report**

- The top gives the counts (checks, flags, and how many are critical) and lists the modules that fired, each with the model's one-sentence reason. Check that these match the methods you actually use.
- Then come what the paper does well and the main issues, the three to five that matter most for your main result.
- One table lists every flag, grouped into issues: how much each matters, where the paper deals with it, and its check ids. The legend under the table explains "not seen" (material the paper points to that the model could not read) and "Single source" (a check that rests on a single source).
- Critical and Major issues get a short paragraph each and a source.
- "Close call" means a reasonable second reader could disagree.
- Every check, including passes and out-of-scope rows, is in `AUDIT_DETAILS.md` and `coding_<module>.json`.
- A flag means the text does not report the practice. Before acting on one, search your paper and appendix yourself.

### Planned: browser app

A browser app where you paste your own OpenRouter key and upload a paper is planned. It is not yet available.

## Cost and model notes

- The checklists were generated with Claude Opus models (`claude-opus-4-8`, `claude-opus-5` for the measurement module, and `claude-opus-5-5` for the universal checklist). Reliability was measured by having independent model coders code the same test papers and comparing their verdicts (see the generation document below).
- We run AMICUS with Claude Opus 5.5 in Claude Code and GPT-6.1 Sol (effort high) in Codex. These are the runner's per-agent defaults. The results in our working paper use Claude Sonnet 5.5.
- You pay for the model calls through your own agent account. Cost grows with paper length and with the number of modules that fire; the `measurement` module alone has 62 checks.

## How the checklists were made

The full description is in [docs/SKILL_GENERATION.md](https://github.com/amicus-ink/amicus-ink/blob/main/docs/SKILL_GENERATION.md); the source lists are in [docs/METHOD_SOURCES.md](https://github.com/amicus-ink/amicus-ink/blob/main/docs/METHOD_SOURCES.md).

In brief: the sources for each module are chosen by fixed rules, not by hand. The candidate pool comes from what current research cites and teaches: research articles published in 2010, 2015, 2020 and 2025 in eight general political science and economics journals, and the reading lists of graduate methods courses. A work is admitted to a module by one of three recorded rules: at least two of those articles that use the module's method cite it; it appears on at least two graduate syllabi; or, only for a module that the first two rules leave with fewer than ten sources, it ranks high by age-adjusted citation count among methods-journal articles whose abstracts name the method. The syllabus rule is only partly in use: we have not yet sorted most of the works on two syllabi by method. Our working paper uses versions of these checklists limited to sources published by 2020.

## Citing

Chau, Tak-Huen, and Andrew T Little. 2026. "Peer Review and the Technical Soundness of Research: Evidence from Automated Audits of Political Science Working Papers". https://osf.io/preprints/socarxiv/zk26u.

GitHub's "Cite this repository" button reads the same details from `CITATION.cff`. If you report results from an audit, also give the date you ran it and the model, which `run_manifest.json` records.

## License

The code is licensed under [GPL-3.0](LICENSE). The checklists and documentation are licensed under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). [LICENSE-CONTENT.md](LICENSE-CONTENT.md) says which files fall under which.

## Authors and contact

Tak-Huen Chau and Andrew T. Little.

Contact: open an issue at https://github.com/amicus-ink/amicus-ink/issues.
