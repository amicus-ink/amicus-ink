"""Plain-language explainers beside a checklist: load them, render them as two lines, take them out again.
Stdlib only; shared by render_md.py (the shipped checklists), universal_module.py (the universal checklist),
build_site.py and the paper-only runner (paper_only_audit.py).

Each shipped run keeps `checklists/explainers.json` beside `verified.anchored.json`: a list of
{check_id, plain, why, done} written by build_explainers.py. `plain` and `why` are rendered in the checklists
as the two lines "In plain words" and "Why it matters"; `done` is only for reports (a strength). A run without
the file simply has no explainers, so every function here degrades to the old output.

Coders must never see the explainers: they are for the report's reader, and a plain-words restatement is one
more place for a coder's reading to drift from the check's own conditions. The runner and the generation
pipeline therefore hand coders strip(checklist_text), not the shipped file.
"""
import json
from pathlib import Path

FILE = "explainers.json"
PLAIN_LABEL = "In plain words"  # the labels report_spec.REPORT_STEPS quotes; change both together
WHY_LABEL = "Why it matters"
_PLAIN_PREFIX = f"**{PLAIN_LABEL}:** "
_WHY_PREFIX = f"**{WHY_LABEL}:** "


def _one_line(s):
    return " ".join(str(s).split())


def load_path(path):
    """{check_id: {"plain", "why", "done"}} from an explainers.json. {} when the file is absent.
    A present file that is not the expected shape raises ValueError (a shipped file is validated by
    build_explainers.py and tests, so damage should be loud, not a silent loss of the lines)."""
    path = Path(path)
    if not path.is_file():
        return {}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        rows = doc["explainers"]
        return {e["check_id"]: {k: _one_line(e[k]) for k in ("plain", "why", "done") if isinstance(e.get(k), str) and e[k].strip()}
                for e in rows}
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError(f"{path}: not a valid explainers file ({exc})") from exc


def load(run_dir):
    """Explainers of the run at `run_dir` (its checklists/explainers.json), or {} when it has none."""
    return load_path(Path(run_dir) / "checklists" / FILE)


def lines(entry):
    """The checklist lines for one check's explainer entry, 'In plain words' then 'Why it matters'; a part
    the entry lacks is left out. [] for no entry."""
    entry = entry or {}
    out = []
    if entry.get("plain"):
        out.append(_PLAIN_PREFIX + entry["plain"])
    if entry.get("why"):
        out.append(_WHY_PREFIX + entry["why"])
    return out


def _is_explainer_line(line):
    return line.startswith(_PLAIN_PREFIX) or line.startswith(_WHY_PREFIX)


def strip(text):
    """`text` (a rendered checklist) without its explainer lines or the blank line after each: the text a
    checklist had before explainers were added. Identity on a checklist that has none."""
    src = text.split("\n")
    out, i = [], 0
    while i < len(src):
        if _is_explainer_line(src[i]):
            i += 2 if i + 1 < len(src) and src[i + 1] == "" else 1
            continue
        out.append(src[i])
        i += 1
    return "\n".join(out)


def add_to_checklist(text, explainers):
    """Insert each check's explainer lines into an already rendered checklist, as render_md.py places them:
    after the check's **Scope:** line, each in its own paragraph. A check with no explainer is left as is.
    Used for the universal checklist, whose run files are never edited."""
    out, check_id = [], None
    for line in text.split("\n"):
        out.append(line)
        if line.startswith("### "):
            check_id = line[4:].split(" ", 1)[0]
        elif line.startswith("**Scope:**") and check_id in explainers:
            for ln in lines(explainers[check_id]):
                out += ["", ln]
            check_id = None
    return "\n".join(out)
