"""Flag grouping for the AMICUS runner (paper_only_audit.py): one agent call, separate from the importance call
(importance.py, whose PROMPT is held word for word and is not touched here), that groups the run's FLAGs into
issues for the summary-first report (report_spec.py). Chatbots and coding agents group in the report step
itself, following report_spec.VOICE; the deterministic runner cannot, so it asks for the grouping here.
The call only groups: it never re-audits, drops a flag or rates importance. The runner gives each issue the
highest importance among its checks that are not single-source, or "Single source" if all are (report_spec step 4).
"""
import re

import importance

PROMPT = """Read the paper at `{paper}`. An audit found that the paper does NOT meet the checklist requirements listed below ("flags"); each gives the requirement and the auditor's note. Do not re-audit, add or remove flags, or judge how much they matter. Your only task is to group the flags into issues for a short report to the author.

FLAGS:
{flags}

Rules:
- An issue is one underlying gap in this paper: the same missing evidence, statement or analysis, even when different checklists word it differently or ask for different fixes. Group flags only when they describe the same gap; flags that merely share a topic stay apart.
- Every flag appears in exactly one issue. Drop nothing; a flag that matches no other is an issue of its own.
- title: a plain name for the gap in 6 to 10 words, with no check ids, no jargon where a plain word works, and no verdict on the paper.
- where: where the paper deals with it, as page, table or footnote (for example "Table 3, p.12; fn 11"); add "not seen (<what the paper points to>)" when the material is in an appendix or supplement you do not have; write "silent" if the paper never addresses it. Under 12 words.

Write to `{out}` a JSON object: {{"issues": [{{"title": "...", "where": "...", "flags": ["F1", "F4"]}}, ...]}} with every flag in exactly one issue. Write the file, then reply with the word done."""

TITLE_MAX_WORDS = 12


def format_flags(flags):
    """Fill {flags}: importance.format_flags (one line per flag, F1.., requirement and auditor note; checklist
    severity and consensus withheld), plus a tag on a flag the coder marked may_exist_elsewhere, so the call
    can write "not seen (...)" for it. Each flag is a dict with `req`, `note` and optionally `may_exist_elsewhere`."""
    lines = re.split(r"\n(?=F\d+ Requirement: )", importance.format_flags(flags)) if flags else []  # one chunk per flag, even if a note has a newline
    return "\n".join(ln + (" | Auditor tag: may exist elsewhere (material not in the text)" if f.get("may_exist_elsewhere") else "")
                     for ln, f in zip(lines, flags))


def validate(obj, n):
    """Problems with a grouping object {"issues": [...]} for n flags: every F1..Fn in exactly one issue, no other
    flag ids, each issue with a non-empty title under TITLE_MAX_WORDS words, a non-empty `where` and a non-empty
    flags list. An empty list means valid."""
    if not isinstance(obj, dict) or not isinstance(obj.get("issues"), list) or not obj["issues"]:
        return ["no issues list"]
    problems, seen = [], {}
    for i, iss in enumerate(obj["issues"], 1):
        if not isinstance(iss, dict):
            problems.append(f"issue {i}: not an object"); continue
        title = iss.get("title")
        if not isinstance(title, str) or not title.strip():
            problems.append(f"issue {i}: empty title")
        elif len(title.split()) >= TITLE_MAX_WORDS:
            problems.append(f"issue {i}: title has {len(title.split())} words")
        if not isinstance(iss.get("where"), str) or not iss["where"].strip():
            problems.append(f"issue {i}: no where")
        fl = iss.get("flags")
        if not isinstance(fl, list) or not fl:
            problems.append(f"issue {i}: no flags"); continue
        for f in fl:
            if isinstance(f, str):
                seen.setdefault(f, []).append(i)
            else:
                problems.append(f"issue {i}: flag {f!r} is not a string")
    want = {f"F{k}" for k in range(1, n + 1)}
    problems += [f"{f} missing" for f in sorted(want - set(seen), key=lambda x: int(x[1:]))]
    problems += [f"{f} in issues {v}" for f, v in seen.items() if f in want and len(v) > 1]
    problems += [f"unknown flag {f!r}" for f in seen if f not in want]
    return problems
