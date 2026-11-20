# AMICUS in a chat window

Audit a paper's methods from claude.ai, with nothing to install on your computer and no API key.

## One-time setup (about a minute)

1. Download `amicus-audit.zip` from this folder.
2. In claude.ai open **Settings → Capabilities → Skills** and upload the zip.

## Every time

1. Start a new chat and attach the paper (PDF). Attach the online appendix too if it is a
   separate file; the audit can only credit what it can see.
2. Type: **Audit this paper with AMICUS.**
3. Read the report. It opens with what the paper does well and the main issues, then lists
   every flag in one table, grouped into issues, with where in the paper each one sits and the
   check ids behind it; "close call" marks a judgment a second reader could make differently and
   "not seen" marks material the paper points to that was not attached.

A long paper with several methods takes a few minutes. The audit uses your own Claude
subscription.

## If you cannot upload skills

Attach `SKILL.md`, `IMPORTANCE_PROMPT.md`, `REPORT_GUIDE.md`, `checklists/UNIVERSAL_CHECKLIST.md` (it runs on every paper) and the checklist for the paper's method (for example
`checklists/DID_CHECKLIST.md`) alongside the PDF, and type the same sentence.

## What it runs

The 2025-vintage AMICUS instrument: 14 method checklists and one universal checklist, built from the methods literature by the pipeline in `scripts/skillgen/`. Each check carries a
severity, a consensus grade (how many of the module's sources stand behind it; the universal checks have none), and a rule for
what to do when the paper is silent. The same coding rules drive the study in our
working paper (see `CITATION.cff`). The paper's analysis used the 2020-restricted checklists (242 checks
across fifteen methods, 175 in the main set); this folder has the 2025-anchor checklists, so
counts differ from the paper's appendix. The universal checklist is the same 28 checks in both. Rebuild this folder with `scripts/skillgen/build_chat_skill.py`
when the checklists change.
