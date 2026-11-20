# The Python runner

The runner runs the full pipeline: it routes the paper to the method modules, codes each fired module and the universal checklist with an independent model call, and writes a report. It gives the most consistent results because the coding rules and the output format are fixed by the script. How to read the report is in the [README](../README.md).

## Prerequisites

- Python 3.
- PyMuPDF, for reading PDFs. In a virtual environment (many systems block a global `pip install`): `python3 -m venv .venv && . .venv/bin/activate && pip install PyMuPDF==1.26.5`. The version is pinned in `requirements.txt` because extraction differences changed which source quotes matched when the checklists were built. `.docx` and `.txt` inputs need no extra package.
- One of these agent command-line tools, installed and logged in with your own account:
  - Claude Code (`claude`), or
  - Codex (`codex`).

The runner calls your installed agent as a subprocess, so the run uses your own subscription or API access.

## Run one paper

From the repository root:

```
# Claude Code
python3 scripts/skillgen/paper_only_audit.py --paper path/to/paper.pdf --out runs/paper_audits/my_paper

# Codex
python3 scripts/skillgen/paper_only_audit.py --paper path/to/paper.pdf --agent codex --out runs/paper_audits/my_paper_codex
```

Options:

- `--paper FILE [FILE ...]`: the main text first, then any appendix or supplement files (PDF, `.docx` or `.txt`). Supplements are appended to the main text, so a practice reported in the appendix is credited.
- `--modules did,panel`: skip routing and run only the named modules. Omit it to let the model route the paper. An unknown name fails immediately and lists the valid names.
- `--agent claude|codex`: which command-line tool runs the model calls. Default `claude`.
- `--model NAME` and `--effort LEVEL`: override the per-agent defaults. The defaults are set in `scripts/skillgen/agent_call.py` (currently `claude-opus-5-5` for Claude and `gpt-6.1-sol` at effort `high` for Codex).
- `--no-universal`: do not code the universal checklist, which otherwise runs on every paper after the method modules.
- `--out DIR`: output directory. If omitted, the runner writes to `runs/paper_audits/<date>_<paper name>/`.

The routing step makes one model call. Each fired module and the universal checklist make at least one more. Two more calls rate how much each flag matters and group the flags into issues for the report. A paper that uses three methods therefore costs about seven calls, more if a call is retried. `--no-importance` skips the last two, and `--no-universal` skips the universal checklist.

## Where the output lands

Everything is written to the `--out` directory:

| File | Contents |
|---|---|
| `AUDIT_REPORT.md` | The report to read |
| `AUDIT_DETAILS.md` | Every check with its verdict, importance, issue and coder note |
| `routing.json` | Which modules fired and why |
| `coding_<module>.json` | One row per check: verdict, scope, borderline flag, note |
| `flag_severity.json` | How much each flag matters for the paper's main result |
| `issues.json` | Which flags were grouped into each issue, and where the paper deals with it |
| `paper.txt` | The staged text the model saw (main text plus supplements) |
| `run_manifest.json` | Paper hash, agent, model and checklist version for each output |
| `coder_failures.json` | Written only if a module failed |

If you rerun into the same directory, outputs that still parse, validate, and match the recorded paper, model and agent are reused without calling the model. Anything else is renamed to `<name>.stale` and redone.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Every module was coded and the report is complete |
| 1 | Bad arguments: unknown module, missing paper file |
| 2 | At least one module's coder failed, or Python rejected an option value (for example an unknown `--agent`); the report opens with an INCOMPLETE AUDIT banner and omits that module |

A coder call that writes no valid output is retried up to three times before the module is recorded as failed. If the agent reports a usage limit, the runner sleeps 15 minutes and retries, for up to 10 hours per call. Set `AMICUS_RATE_LIMIT_SLEEP` (seconds) to change the wait.

**Safety.** The coder runs with its working directory set to the output directory and is permitted to write only there. The paper's text is untrusted input, and the sandbox is meant to keep instructions embedded in a paper from writing elsewhere.
