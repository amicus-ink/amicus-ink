"""Plain-language explainers for checklist checks, generated once per module and stored in explainers.json.
One agent call per module reads that module's checks and writes, for every check, `plain` (what the check asks the
paper to report or do) and `why` (why that matters for trusting the paper's result), for an applied researcher who
does not use the method. The call sees only each check's own wording and its source-derived `claim`, never evidence
quotes, and must not add to, tighten or loosen a requirement. The authors spot-check the output before it is shown in
checklists and reports, so changing PROMPT means regenerating and re-checking every module: tell the owner first.
"""
import re

MAX_WORDS = 70  # plain + why together
DONE_WORDS = 20  # done, alone

# (key in verified.anchored.json, label shown to the model); `threshold` and `claim` are optional and
# omitted when missing or empty (threshold carries the numeric cutoff some checks keep only there)
FIELDS = (
    ("requirement_statement", "Requirement"),
    ("observable", "What is checked"),
    ("pass_condition", "Passes if"),
    ("flag_condition", "Flagged if"),
    ("threshold", "Cutoff"),
    ("claim", "Reason"),
)

PROMPT = """Below are the {module} checks from AMICUS, a checklist that reviews research papers. Each check says, in methods language, what a paper should report or do. Many readers are applied researchers who do not use this method. For each check, write in plain words:
  plain: one sentence on what the check asks the paper to report or do. Use "should", not "must".
  why: one sentence on why this matters for trusting the paper's result.
  done: a short phrase, starting with a verb, for a paper that does it, completing "The paper ..." (for example "states that the treatment had no effect before it began").

Rules:
- At most 70 words for plain and why together; at most 20 words for done.
- Avoid jargon. If a technical term must stay because the authors need to recognize it, explain it briefly in the same sentence.
- Say only what the check says. Add no requirements, numbers or reasons that are not in it, and make it neither stricter nor looser. If a check has no Reason line, give only the reason that follows directly from the check.
- Do not name or quote any source. Do not write "you" or "your"; refer to the paper. Neutral, friendly tone. American spelling. No em dashes.

CHECKS:
{checks}

Write to `{out}` a JSON object: {{"explainers": [{{"check_id": "...", "plain": "...", "why": "...", "done": "..."}}, ...]}} with one entry per check, in the order given. Write the file, then reply with the word done."""

OPTIONAL = {"threshold", "claim"}
_EM_DASH = chr(0x2014)
_YOU = re.compile(r"\b(you|your|yours|yourself|yourselves)\b", re.IGNORECASE)


def format_checks(checks):
    """Fill {checks}: one block per check, in order, separated by a blank line. Each check is a dict from
    verified.anchored.json; `check_id` and the four wording fields are required (a missing one raises KeyError),
    `claim` is shown as the Reason line only when present. Evidence quotes and sources are never passed."""
    blocks = []
    for c in checks:
        lines = [f"Check ID: {c['check_id']}"]
        for key, label in FIELDS:
            val = c.get(key) if key in OPTIONAL else c[key]
            if key == "threshold" and isinstance(val, dict):  # numbers only; band_rule names sources, so it stays out
                band = val.get("border_band")
                val = f"{val.get('cutoff', val.get('value', ''))}" + (f"; borderline band {band[0]} to {band[1]}" if band else "")
            if isinstance(val, str) and val.strip():
                lines.append(f"{label}: {val.strip()}")
            elif key not in OPTIONAL:
                raise ValueError(f"{c['check_id']}: empty {key}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def validate(obj, check_ids):
    """Problems with an explainers object {"explainers": [...]} for the checks `check_ids`, in order: one entry per
    check with the same id at the same position, `plain` and `why` non-empty strings, at most MAX_WORDS words
    together, no em dash, no "you"/"your". An empty list means valid."""
    if not isinstance(obj, dict) or not isinstance(obj.get("explainers"), list):
        return ["no explainers list"]
    ents, ids = obj["explainers"], list(check_ids)
    problems = [] if len(ents) == len(ids) else [f"{len(ents)} entries for {len(ids)} checks"]
    for i, e in enumerate(ents[:len(ids)]):
        want = ids[i]
        if not isinstance(e, dict):
            problems.append(f"entry {i+1}: not an object"); continue
        if e.get("check_id") != want:
            problems.append(f"entry {i+1}: check_id {e.get('check_id')!r}, expected {want!r}")
        texts = []
        for field in ("plain", "why", "done"):
            v = e.get(field)
            if not isinstance(v, str) or not v.strip():
                problems.append(f"{want}: {field} missing or empty"); continue
            if field != "done":
                texts.append(v)
            elif len(v.split()) > DONE_WORDS:
                problems.append(f"{want}: done has {len(v.split())} words, limit {DONE_WORDS}")
            if _EM_DASH in v:
                problems.append(f"{want}: {field} contains an em dash")
            if _YOU.search(v):
                problems.append(f"{want}: {field} addresses the reader as you")
        words = len(" ".join(texts).split())
        if words > MAX_WORDS:
            problems.append(f"{want}: {words} words, limit {MAX_WORDS}")
    return problems
