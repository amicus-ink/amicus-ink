"""The universal checklist, shipped beside (not inside) the 14 design modules.

It is deliberately NOT in SHIPPING or ROSTER in paper_only_audit.py: the runner routes and
codes design modules only, and tests there pin SHIPPING to ROSTER. The chat skill, the
plugin, public/AMICUS.md and the site add this module explicitly through this file.

Source: runs/skill_generation/20261113_universal_v1_streamlined/, the 28-check list the working paper
uses. It was built by the procedure in the paper's universal-checklist appendix (works on at least two
graduate syllabi, a model triage for requirements that apply whatever the research design, claim
extraction, three-draw clustering to 137 checks, then a mechanical cut to one check per overlap group
supported by at least three works). It has no consensus grade. The run's
files are not edited, apart from the release removing two cross-references to check ids of an interim list
(docs/SKILL_GENERATION.md section 2.5): the shipped copies add DOI links and explainer lines here.

Its check ids (UNIV-...) also occur, with other meanings, in an earlier 23-check hand-drafted pilot that
stays in the internal repository, so the two lists must never share a file or an output directory.
"""
import json
from pathlib import Path

import explainer_text

ROOT = Path(__file__).resolve().parents[2]
MODULE = "universal"
RUN = "20261113_universal_v1_streamlined"
DESC = "every paper (always fires; method-agnostic checks, each supported by at least three works)"
CHECKLIST = ROOT / "runs/skill_generation" / RUN / "checklists" / "UNIV_CHECKLIST.md"
ANCHORED = ROOT / "runs/skill_generation" / RUN / "checklists" / "verified.anchored.json"
NAME = "UNIVERSAL_CHECKLIST.md"  # the shipped file name (chat, plugin, site links)
# {source_id: DOI} for cited sources whose config.json has no DOI (book chapters), built by check_dois.py
# from Crossref and the ISBNs the source records carry. The shipped copies add these links here.
DOI_MAP = Path(__file__).resolve().parent / "universal_dois.json"
# Display names for the scope triggers whose ids read as internal (a shard suffix from the build). Only the
# site shows them; the checklist files keep the ids the paper's coder saw, so the list stays the paper's list.
DISPLAY_LABELS = {
    "causal_claim__causal_3": "own_causal_effect",
    "quantitative_estimates__causal_3": "numerical_estimate",
    "quant_estimates__inference_1": "estimate_as_finding",
    "all__design_2": "empirical_paper",
}


def label(trigger: str) -> str:
    """The display name of a scope trigger (the id itself unless DISPLAY_LABELS renames it)."""
    return DISPLAY_LABELS.get(trigger, trigger)


def load_dois() -> dict:
    return json.load(open(DOI_MAP, encoding="utf-8")) if DOI_MAP.is_file() else {}


def link_dois(text: str, dois=None, checks=None) -> str:
    """Add ' https://doi.org/<doi>' to each Further reading and Sources line that cites a mapped source,
    where the rendered checklist puts a DOI it has from config.json: after the citation, before ' — <pages>'.
    A line that already carries a DOI link is left as is."""
    dois = load_dois() if dois is None else dois
    checks = load_module()[3] if checks is None else checks
    cite_doi = {fr["cite"]: dois[fr["source_id"]] for c in checks for fr in c.get("further_reading") or []
                if isinstance(fr, dict) and fr.get("source_id") in dois}
    out = []
    for line in text.split("\n"):
        pre = "  - " if line.startswith("  - ") else "- " if line.startswith("- ") else None
        if pre and "https://doi.org/" not in line:
            body, sep, pages = line[len(pre):].partition(" — ")
            if body in cite_doi:
                line = f"{pre}{body} https://doi.org/{cite_doi[body]}{sep}{pages}"
        out.append(line)
    return "\n".join(out)


def load_explainers() -> dict:
    """{check_id: explainer} from the run's explainers.json ({} when absent)."""
    return explainer_text.load_path(CHECKLIST.with_name(explainer_text.FILE))


def shipped_text(text: str, explainers=None) -> str:
    """Shipped checklists say MEDIUM where a source says MODERATE, carry a DOI link on every further-reading
    and source line whose DOI is known, and show each check's In plain words and Why it matters lines (from
    explainers.json, like the 14 rendered checklists) under its Scope line."""
    text = link_dois(text.replace("**Severity if flagged:** MODERATE", "**Severity if flagged:** MEDIUM"))
    return explainer_text.add_to_checklist(text, load_explainers() if explainers is None else explainers)


def load_module():
    """Same (mod, run, head, checks) shape as render_checklists_html.load()."""
    d = json.load(open(ANCHORED, encoding="utf-8"))
    head = d[0] if not d[0].get("check_id") else {}
    return (MODULE, RUN, head, [c for c in d if c.get("check_id")])
