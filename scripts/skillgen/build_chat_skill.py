#!/usr/bin/env python3
"""Package the paper-only audit as a claude.ai Skill: chat/amicus-audit/ (SKILL.md + the
shipping checklists) and chat/amicus-audit.zip for upload under Settings > Skills.

The instructions mirror scripts/skillgen/prompts/coder.md and the routing prompt in
paper_only_audit.py; the checklists are the rendered markdown of the shipping instrument.
Usage: build_chat_skill.py [--instrument 2025|2020]
"""
import argparse, shutil, sys, zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_only_audit import SHIPPING_BY_INSTRUMENT, ROSTER  # noqa: E402
import universal_module as UM  # noqa: E402
import importance  # noqa: E402
import report_spec  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ap = argparse.ArgumentParser(); ap.add_argument("--instrument", default="2025", choices=list(SHIPPING_BY_INSTRUMENT)); a = ap.parse_args()
OUT = ROOT / "chat" / "amicus-audit"; CK = OUT / "checklists"
SRCS = {mod: ROOT / "runs/skill_generation" / run / "checklists" / f"{mod.upper()}_CHECKLIST.md"
        for mod, run in SHIPPING_BY_INSTRUMENT[a.instrument].items() if mod in ROSTER}
absent = [str(p) for p in [*SRCS.values(), UM.CHECKLIST] if not p.is_file()]
if absent:  # check before deleting anything: a sparse checkout or typo must not wipe the bundle
    sys.exit("error: checklist sources missing, nothing changed:\n  " + "\n  ".join(absent))
if CK.exists(): shutil.rmtree(CK)
CK.mkdir(parents=True)
sizes = {}
for mod, src in SRCS.items():
    dst = CK / f"{mod.upper()}_CHECKLIST.md"; shutil.copy(src, dst); sizes[mod] = dst.stat().st_size
dst = CK / UM.NAME; dst.write_text(UM.shipped_text(UM.CHECKLIST.read_text())); sizes[UM.MODULE] = dst.stat().st_size  # universal checklist, every paper

IMP = OUT / "IMPORTANCE_PROMPT.md"  # generated from importance.PROMPT only; never hand-edit
IMP.write_text("# Step 3: rate each flag's importance\n\nFollow the instructions below for the flags you just coded.\n\n" + importance.chat_prompt() + "\n")

RG = OUT / "REPORT_GUIDE.md"  # generated from report_spec.guide_markdown() only; never hand-edit
RG.write_text(report_spec.guide_markdown())

ROSTER_U = {**ROSTER, UM.MODULE: UM.DESC}  # design modules plus the universal checklist (always fires)
NMOD = len(ROSTER_U)
roster = "\n".join(f"| `{m}` | {d} | `checklists/{m.upper()}_CHECKLIST.md` |" for m, d in ROSTER_U.items())
skill = f"""---
name: amicus-audit
description: Audit a quantitative social-science paper (PDF or pasted text) against AMICUS's method checklists. Use whenever someone asks to audit, check, review or stress-test the methods of a paper, or says "run AMICUS". Routes the paper to the methods it uses, applies each method's checklist item by item, and returns a report of what is missing or unsupported, with evidence pointers.
---

# AMICUS paper-only audit

You are the auditing coder of AMICUS, a methods-auditing system. Given one paper, you decide
which methods checklists apply, apply every check on each of them, and report the verdicts.
Code what the checklist says, not what you privately believe good practice is; where a
condition is ambiguous, make your best call and say so in the note.

The instrument is the {a.instrument} vintage: {NMOD - 1} method checklists and one universal checklist, built from the
methods literature, each check carrying a severity (HIGH / MEDIUM / LOW), a consensus grade
(how many of the module's sources stand behind it: high / medium / low; the universal checklist has none), and a "when silent"
rule. The checklists live in this skill's `checklists/` folder.

## Step 0: get the paper

The paper is the attached PDF, or pasted text, or a link the person gives you (fetch it if you
can; if you cannot fetch it, ask them to attach the file). Read the whole paper including any
appendix that is attached. If a supplement is referenced but not attached, say so at the top
of the report: verdicts cover only the text you could see.

## Step 1: route

Decide, for each module below, whether the PAPER ITSELF USES that method as part of its own
empirical analysis. A method merely cited, discussed, or used only by prior work does not
count. Quote or closely paraphrase the paper's own description of using the method as the
reason. The one exception is `universal`, which fires on every paper. It has no consensus
grade; each of its checks is supported by at least three works. Its checks are coded and
ordered like any other.

| module | fires when the paper uses | checklist |
|---|---|---|
{roster}

## Step 2: code each fired module

For each fired module, read its checklist file in full, including the **Scope triggers**
section, then work through ALL of its checks in checklist order. Skip none.

1. **Scope first.** Decide each check's triggers from the definitions in the checklist.
   Triggers key on the paper's OWN explicit declarations and default OUT on silence:
   behaviour that merely resembles a stance (subgroup analyses, clustered SEs in a table)
   does not fire a trigger unless its definition says so. A check is in scope only if ALL
   its triggers fire.
2. **Verdict.** Out of scope: `NA` (NA is ONLY for out-of-scope, never for "the paper
   doesn't say"). In scope: apply the pass/flag conditions; if the paper is silent on what
   the check requires, use the check's stated **When silent** value.
3. **Evidence scope.** Required material absent from the text but pointed to elsewhere
   (appendix, supplementary materials, replication package): FLAG with
   `may_exist_elsewhere: true`, naming the pointer in your note.
4. **Thresholds.** Where a check carries a cutoff with a border band, apply its stated band
   rule exactly; mark `borderline: true` whenever the paper's value falls inside the band.
5. **Judgment calls.** Checks marked as judgment calls are always `borderline: true`.
6. Also mark `borderline: true`, with a note, wherever your verdict rests on a reading a
   reasonable second coder could dispute.

Keep each note to at most 25 words: the deciding observation, with a section, table or
page pointer.

## Step 3: rate each flag's importance

After coding every fired module, open `IMPORTANCE_PROMPT.md` in this skill's folder and follow it for the flags you just coded. Do not re-audit, drop a flag or change a verdict.

## Step 4: write the report, for the author

After rating importance, open `REPORT_GUIDE.md` in this skill's folder and write the report exactly as it says. Do not re-audit, drop a flag or change a verdict or a rating.
"""
(OUT / "SKILL.md").write_text(skill)

readme = f"""# AMICUS in a chat window

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

The {a.instrument}-vintage AMICUS instrument: {NMOD - 1} method checklists and one universal checklist, \
built from the methods literature by the pipeline in `scripts/skillgen/`. Each check carries a
severity, a consensus grade (how many of the module's sources stand behind it; the universal checks have none), and a rule for
what to do when the paper is silent. The same coding rules drive the study in our
working paper (see `CITATION.cff`). The paper's analysis used the 2020-restricted checklists (242 checks
across fifteen methods, 175 in the main set); this folder has the {a.instrument}-anchor checklists, so
counts differ from the paper's appendix. The universal checklist is the same 28 checks in both. Rebuild this folder with `scripts/skillgen/build_chat_skill.py`
when the checklists change.
"""
(ROOT / "chat" / "README.md").write_text(readme)

zp = ROOT / "chat" / "amicus-audit.zip"
with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUT.rglob("*")):
        if p.is_file(): z.write(p, p.relative_to(OUT.parent))
print("wrote", OUT, "and", zp, f"({zp.stat().st_size//1024} KB);", "checklists:", {k: f"{v//1024}K" for k, v in sizes.items()})

# ---------- portable bundle for ChatGPT (Custom GPT) and Gemini (Gem), and plain chats ----------
PORT = ROOT / "chat" / "portable"; PORT.mkdir(exist_ok=True)
roster_plain = "\n".join(f"- {m}: {d} -> {m.upper()}_CHECKLIST.md" for m, d in ROSTER_U.items())
instr = f"""You are the auditing coder of AMICUS, a methods-auditing system for quantitative social science. Given one paper (attached PDF, pasted text, or a link you can open), decide which methods checklists apply, apply every check on each, and report the verdicts. Code what the checklist says, not what you privately believe good practice is; where a condition is ambiguous, make your best call and say so.

The checklists are the files named *_CHECKLIST.md (attached, or in your knowledge files). Each check has a severity (HIGH/MEDIUM/LOW), a consensus grade (high/medium/low: how many of the module's sources stand behind it; the universal checks have none), scope triggers, pass and flag conditions, and a "When silent" rule.

STEP 0. Read the whole paper, including any attached appendix. If a supplement is referenced but not attached, say at the top of the report that verdicts cover only the text you could see.

STEP 1. ROUTE. For each module below decide whether the PAPER ITSELF USES that method in its own empirical analysis. A method merely cited, discussed, or used only by prior work does not count. Give one sentence per fired module quoting or closely paraphrasing the paper's own description of using it. The one exception is `universal`, which fires on every paper. It has no consensus grade; each of its checks is supported by at least three works. Its checks are coded and ordered like any other.
{roster_plain}

STEP 2. CODE each fired module. Open its checklist file and read it IN FULL, including "Scope triggers". First list every check id in the file so none is skipped, then work through them in order.
1. Scope first. Decide each check's triggers from the definitions in the checklist. Triggers key on the paper's OWN explicit declarations and default OUT on silence; behaviour that merely resembles a stance does not fire a trigger unless its definition says so. A check is in scope only if ALL its triggers fire.
2. Verdict. Out of scope: NA (NA is ONLY for out-of-scope, never for "the paper doesn't say"). In scope: apply the pass/flag conditions; if the paper is silent on what the check requires, use the check's "When silent" value.
3. Evidence scope. Required material absent from the text but pointed to elsewhere (appendix, supplement, replication package): FLAG with may_exist_elsewhere = true, naming the pointer.
4. Thresholds. Where a check has a cutoff with a border band, apply the stated band rule exactly and mark borderline = true when the paper's value falls inside the band.
5. Judgment calls are always borderline = true. Also mark borderline where a reasonable second coder could dispute your reading.
Notes are at most 25 words: the deciding observation with a section, table or page pointer.

STEP 3. RATE EACH FLAG'S IMPORTANCE. After coding every fired module, open IMPORTANCE_PROMPT.md (attached, or in your knowledge files) and follow it for the flags you just coded. Do not re-audit, drop a flag or change a verdict. If you cannot see the file, say so plainly and ask the user to attach it; never write the importance levels from memory.

STEP 4. WRITE THE REPORT, for the author. After step 3, open REPORT_GUIDE.md (attached, or in your knowledge files) and write the report exactly as it says. If you cannot see the file, say so plainly and ask the user to attach it; never write the report from memory.

If the reply would be too long for one turn, finish the current module, then say "Reply 'continue' for the next module" and stop; never skip checks to save space.
"""
(PORT / "AMICUS_INSTRUCTIONS.md").write_text(instr)
port_readme = f"""# AMICUS in ChatGPT or Gemini

The same audit as the claude.ai skill, packaged for the other chat services. `AMICUS_INSTRUCTIONS.md`
is the instruction text ({len(instr):,} characters, under ChatGPT's 8,000 limit); the `*_CHECKLIST.md`
files are the {NMOD - 1} method checklists and the universal checklist ({a.instrument} instrument; they sit next to this file inside `amicus-audit-portable.zip`, and in `../amicus-audit/checklists/` in this repository), `IMPORTANCE_PROMPT.md` is the flag-importance step, and `REPORT_GUIDE.md` is the report step.

## ChatGPT: build a Custom GPT once, share the link

1. ChatGPT -> Explore GPTs -> Create -> Configure (needs a paid plan to create; anyone can use it).
2. Name: AMICUS Audit. Instructions: paste the whole of `AMICUS_INSTRUCTIONS.md`.
3. Knowledge: upload the {NMOD} `*_CHECKLIST.md` files, `IMPORTANCE_PROMPT.md` and `REPORT_GUIDE.md`. Turn on Code Interpreter and File Search.
4. Conversation starter: "Audit this paper with AMICUS." Save and share the link.

Then anyone opens the GPT, attaches a PDF, and types the starter. Caveat: ChatGPT reads knowledge
files in retrieved chunks, not whole, so a long checklist (measurement, 62 checks) may come back
incomplete; the instructions ask the model to list every check id first, and the report's
"Not completed" section names any check or module it could not finish.

## Gemini: build a Gem once, share the link

1. Gemini -> Gems -> New Gem. Name: AMICUS Audit. Instructions: paste `AMICUS_INSTRUCTIONS.md`.
2. Add files: upload the {NMOD} `*_CHECKLIST.md` files, `IMPORTANCE_PROMPT.md` and `REPORT_GUIDE.md` (Gemini reads them in full).
3. Save; share the Gem link. Users attach a PDF and type "Audit this paper with AMICUS."

## Any chat, nothing to build

Attach six things to one message: the PDF, `AMICUS_INSTRUCTIONS.md`, `IMPORTANCE_PROMPT.md`, `REPORT_GUIDE.md`, `UNIVERSAL_CHECKLIST.md` (it runs on every paper), and the checklist file for
the paper's method (if unsure, attach the instructions and the PDF first and ask "which AMICUS
modules does this paper fire?", then attach the ones it names). Type "Audit this paper with AMICUS."
This works in ChatGPT, Gemini, and claude.ai without any setup.

## Notes

Fidelity is the model's: the checklists and rules are identical across services, the coder is not,
so verdicts from different services are not interchangeable with the working paper's (which uses
one fixed coder). The audit spends the user's own subscription on that service. Rebuild with
`scripts/skillgen/build_chat_skill.py` when the checklists change.
"""
(PORT / "README.md").write_text(port_readme)
zp2 = ROOT / "chat" / "amicus-audit-portable.zip"
with zipfile.ZipFile(zp2, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(PORT / "AMICUS_INSTRUCTIONS.md", "AMICUS_INSTRUCTIONS.md"); z.write(PORT / "README.md", "README.md"); z.write(IMP, IMP.name); z.write(RG, RG.name)
    for p in sorted(CK.glob("*_CHECKLIST.md")): z.write(p, p.name)
print("portable:", len(instr), "chars;", zp2, f"({zp2.stat().st_size//1024} KB)")
