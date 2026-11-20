"""Flag-importance rating shared by the AMICUS runner (paper_only_audit.py) and the research script
flag_severity.py, so the product and the paper's analysis rate flags with the identical prompt.
For each checklist FLAG, one agent call judges how much the unmet requirement matters for THIS paper's main
result: critical / major / minor / negligible. The pass never changes a verdict and drops nothing.
Do not edit PROMPT without telling the owner: it is held word for word on purpose.
"""
LEVELS = ("critical", "major", "minor", "negligible")

PROMPT = """You are a methods referee. Read the paper at `{paper}` in full. A structured audit has already found that the paper does NOT meet the checklist requirements listed below ("flags"); each flag gives the requirement and the auditor's note. Do not re-audit and do not look for other problems. Your only task is to judge, for each flag, how much that unmet requirement matters for the credibility of THIS paper's main result, given what the paper actually claims and how much of its argument rests on the analysis the flag concerns.

FLAGS:
{flags}

Use exactly these levels:
  critical   - if left unaddressed, the paper's main result cannot be trusted
  major      - materially weakens confidence in the main result or a central supporting result
  minor      - a real gap, but the main result would very likely survive fixing it
  negligible - immaterial for this paper (peripheral analysis, a formality, or effectively addressed elsewhere in the paper)

Write to `{out}` a JSON object: {{"flags": [{{"flag": "F1", "severity": "critical|major|minor|negligible", "why": "<one short clause>"}}, ...]}} with one entry per flag, in order. Write the file, then reply with the word done."""

_CHAT_PAPER = ("Read the paper at `{paper}` in full.", "Read the attached paper, and any appendix, in full.")
_CHAT_FLAGS = ("List the FLAGs you just coded as F1, F2, ... in the order you coded them, each with its requirement "
               "and your note on it, and judge each one.")
_CHAT_OUT = ("Give one line per flag: the flag id, its level, and one short clause on why. "
             "Then use the ratings to group the flags in the report.")


def chat_prompt():
    """PROMPT adapted for a chatbot that cannot read or write files, by string operations on PROMPT only:
    {paper} becomes the attached paper, {flags} an instruction to list the flags just coded, and only the final
    output paragraph (write `{out}` ... reply done) is replaced. Every other sentence, including the level
    definitions, is PROMPT's own text."""
    head, sep, _ = PROMPT.partition("Write to `{out}`")
    if not sep or _CHAT_PAPER[0] not in head or "{flags}" not in head:
        raise ValueError("PROMPT changed shape; update chat_prompt()")
    return head.replace(*_CHAT_PAPER).replace("{flags}", _CHAT_FLAGS) + _CHAT_OUT


def format_flags(flags):
    """Fill {flags}: one line per flag, numbered F1.. in order. The checklist's own severity and consensus
    labels are withheld on purpose, so the judgment is about the paper, not the requirement.
    Each flag is a dict with `req` (requirement statement) and `note` (the coder's note)."""
    return "\n".join(f"F{i+1} Requirement: {f['req']} | Auditor note: {f['note']}" for i, f in enumerate(flags))


def validate(obj, n):
    """Problems with an importance object {"flags": [...]} for n flags: one entry per flag, in order,
    `severity` in LEVELS, `why` a string. An empty list means valid."""
    if not isinstance(obj, dict) or not isinstance(obj.get("flags"), list):
        return ["no flags list"]
    ents = obj["flags"]
    problems = [] if len(ents) == n else [f"{len(ents)} entries for {n} flags"]
    for i, e in enumerate(ents[:n]):
        if not isinstance(e, dict):
            problems.append(f"F{i+1}: not an object"); continue
        if e.get("flag") != f"F{i+1}":
            problems.append(f"entry {i+1}: flag {e.get('flag')!r}, expected 'F{i+1}'")
        if e.get("severity") not in LEVELS:
            problems.append(f"F{i+1}: severity {e.get('severity')!r}")
        if not isinstance(e.get("why"), str):
            problems.append(f"F{i+1}: why is not a string")
    return problems
