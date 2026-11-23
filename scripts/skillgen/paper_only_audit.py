#!/usr/bin/env python3
"""Paper-only audit runner.

Runs the shipping method-module checklists against a single paper, with no replication
data or code: route (which modules' methods does the paper itself use) -> code (one
independent coder per routed module, using the same `coder.md` protocol every
decidability measurement ran under) -> report (author-facing markdown; every flag cites
its methods-literature backing).

The universal checklist (universal_module.py; the 28-check list the working paper applies to every
scored paper) is coded on every paper as one more module, `universal`, after the routed ones, and the
report's header counts it as "my general checks". --no-universal leaves it out (research batch
launchers pass it, as they pass --no-importance); --modules may also name it.

Grounding for the mode: of the 270 shipping checks, none requires opening replication
materials -- every `observable` is defined on the paper text, and `verdict_when_silent`
makes the paper's silence itself a verdict. All published decidability numbers were
measured in exactly this paper-only configuration. A paper-only FLAG therefore reads
"the paper does not report X"; a later replication pass can confirm or upgrade verdicts,
it is not a prerequisite.

Usage:
  python3 scripts/skillgen/paper_only_audit.py --paper <pdf|txt> \
      [--modules did,panel] [--out runs/paper_audits/<slug>] [--agent claude|codex] [--model M] [--effort E] \
      [--no-importance] [--no-universal]

After coding, two report-only calls run with the same agent, model and effort. The importance call
rates every FLAG for how much it matters to this paper's main result (critical / major / minor /
negligible; the prompt is shared with flag_severity.py) and writes flag_severity.json. The grouping call
(grouping.py) then groups the FLAGs that share one underlying gap into issues and says where the paper
deals with each, and writes issues.json. Neither changes a verdict or drops a flag. --no-importance skips
both calls (research batch scripts pass it); grouping never runs without importance. If a call fails, the
report says so: without importance it has no main issues and every issue is unrated; without grouping
each flag is its own issue.

Exit codes: 0 = every module coded; 1 = bad arguments; 2 = at least one module's coder failed
(the report names the failed modules at the top and omits their rows).

Outputs in --out are trusted on rerun only if they parse, validate against the expected
check ids, and match the provenance recorded in run_manifest.json (paper hash, model, agent,
instrument, blind flag). Anything else is renamed to <name>.stale and redone. The coder runs
with cwd = --out and writes confined there (see agent_call.py).
Outputs: AUDIT_REPORT.md, summary first in the layout of report_spec.py (what the paper does well, the main
issues, one table of every issue with report_spec.LEGEND under it, details for Critical and Major issues, not
completed, hardest calls; it ends with report_spec.DISCLAIMER) and AUDIT_DETAILS.md (the full per-check table,
with each flag's issue). The text is deterministic: no model writes it.
"""
import argparse, hashlib, json, os, re, sys, time, zipfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from agent_call import run_agent, sh_claude, AGENTS, DEFAULT_AGENT, default_model, default_effort  # noqa: E402,F401  (sh_claude re-exported)
import importance  # noqa: E402  (the prompt shared with flag_severity.py)
import doi_links, explainer_text, grouping, report_spec  # noqa: E402
import universal_module as UM  # noqa: E402

# Shipping artifact per module (the released production set; kept inline so the runner is
# self-contained). Since 2026-11-11 every module ships its v0_15 consensus artifact (three draws, two-of-three
# consensus); the eight modules that had shipped a single v0_13 draw were switched to the consensus artifacts built
# from the same corpora on 2026-08-06.
SHIPPING = {
    "iv": "20260806_iv_v0_15_consensus", "did": "20260806_did_v0_15_consensus",
    "rdd": "20260806_rdd_v0_15_consensus", "conjoint": "20260806_conjoint_v0_15_consensus",
    "survey_exp": "20260806_survey_exp_v0_15_consensus", "field_exp": "20260806_field_exp_v0_15_consensus",
    "text": "20260806_text_v0_15_consensus", "matching": "20260806_matching_v0_15_consensus",
    "mediation": "20260806_mediation_v0_15_consensus", "multilevel": "20260806_multilevel_v0_15_consensus",
    "panel": "20260806_panel_v0_15_consensus", "synth": "20260806_synth_v0_15_consensus",
    "measurement": "20260914_measurement_v0_15_consensus", "hte": "20260915_hte_v0_15_consensus",
}
try:  # internal research only (other instruments, parked modules); absent from the public repo
    from instruments_internal import PENDING, PENDING_ROSTER, EXTRA_INSTRUMENTS, HISTORICAL_INSTRUMENTS
except ImportError:
    PENDING, PENDING_ROSTER, EXTRA_INSTRUMENTS, HISTORICAL_INSTRUMENTS = {}, {}, {}, set()
RELEASE = "AMICUS 0.1"  # stamped in every report header
CODER_ATTEMPTS = 3  # a coder call that writes no output is retried before the module is recorded as failed

SHIPPING_BY_INSTRUMENT = {"2025": SHIPPING, **EXTRA_INSTRUMENTS}
# One-line routing descriptions: the METHOD the paper itself must use for the module to apply.
ROSTER = {
    "iv": "instrumental variables / 2SLS estimation",
    "did": "difference-in-differences or event-study designs",
    "rdd": "regression discontinuity designs",
    "conjoint": "conjoint experiments",
    "survey_exp": "survey experiments (vignette, list, framing, endorsement)",
    "field_exp": "field experiments / randomized interventions in the field",
    "text": "text-as-data: quantitative measures built from text",
    "matching": "matching or selection-on-observables adjustment strategies",
    "mediation": "causal mediation analysis (direct/indirect effect decomposition)",
    "multilevel": "multilevel / hierarchical (mixed-effects) models as an analysis choice",
    "panel": "panel / TSCS analysis with unit or time fixed effects",
    "synth": "synthetic control methods",
    "measurement": "constructing or validating a measure (index, scale, latent variable, coded content)",
    "hte": "declared analysis of heterogeneous treatment effects (subgroups, interactions, moderation)",
}
ROSTER_ALL = {**ROSTER, **PENDING_ROSTER}  # validates earlier routing.json files
# Plain display names, for the site and for the sentence in the report header ("I read your paper against
# the methods literature for ..."), which uses them lower-cased.
MODULE_NAMES = {
    "iv": "Instrumental variables", "did": "Difference-in-differences", "rdd": "Regression discontinuity",
    "conjoint": "Conjoint experiments", "survey_exp": "Survey experiments", "field_exp": "Field experiments",
    "text": "Text as data", "matching": "Matching", "mediation": "Mediation",
    "multilevel": "Multilevel models", "panel": "Panel data", "synth": "Synthetic control",
    "measurement": "Measurement", "hte": "Heterogeneous treatment effects",
}


BLIND_LINE = re.compile(r"""(
    \b10\.\d{4,9}/\S+                                   # any DOI
  | https?://\S*(doi\.org|journals\.|tandfonline|cambridge\.org|sagepub|wiley|springer|oup\.com|elsevier|sciencedirect|osf\.io|socarxiv|ssrn|apsanet)\S*
  | \bdoi\s*[:=]                                        # 'doi:' prefixes
  | ©|\(c\)\s*20\d\d|copyright|all rights reserved
  | published (online )?by|publisher|university press|sage publications|taylor\s*&\s*francis|wiley|springer|elsevier
  | \b(received|accepted|revised|first published|published online|available online|last revised|posted)\b[^\n]{0,40}\b(19|20)\d\d\b
  | \bforthcoming\b|\bin press\b|\baccepted (for publication|manuscript)\b|\bthis is a (pre|post)print|\bworking paper\b|\bpreprint\b|\bsocarxiv\b|\bssrn\b|\bapsa[ ]preprints?\b|\bopen[ ]engage\b
  | \bdownloaded from\b|\bcorresponding author\b|\bopen access\b|\bcreative commons\b|\blicense\b|\bissn\b|\bvol(ume)?\.?[ ]?\d+[^\n]{0,20}\b(no|issue)\b
  | \bvolume[ ]\d+|\bvol\.[ ]?\d+|\bnumber[ ]\d+,|\bpp\.[ ]?\d+|\(20\d\d\)[ ]\d+:[ ]?\d+|\|[ ]volume|for[ ]permissions|permissions@|\bjournal[ ]homepage|to[ ]cite[ ]this|to[ ]link[ ]to[ ]this
  | article[ ]reuse|sagepub\.com|journals-permissions|\b(anonymous[ ])?(reviewers?|referees?)\b|\bthe[ ]editors?\b|\beditorial[ ](team|board|office)\b
)""", re.I | re.X)
JOURNALISH = re.compile(r"\b(journal|review|quarterly|studies|politics|analysis|science|research|comparative|behavior|opinion|organization|affairs|methods)\b", re.I)

def blind_text(body, venue=None):
    """Symmetric blinding of version cues: drops lines that carry a DOI, a publisher or licence
    line, received/accepted dates, preprint-server names, or that read like a running journal
    header (short, title-case, journal-word line repeated 3+ times). Applied identically to first
    drafts and published versions so neither side keeps a cue the other lacks."""
    lines = body.split("\n"); n = len(lines)
    short = [l.strip() for l in lines]
    rep = {}
    for l in short:
        if 6 <= len(l) <= 90 and JOURNALISH.search(l) and sum(ch.isdigit() for ch in l) <= 12: rep[l] = rep.get(l, 0) + 1
    headers = {l for l, c in rep.items() if c >= 3}
    vrx = None
    if venue and len(venue.strip()) >= 6:
        v = re.sub(r"\s+", " ", venue.strip()).replace("&amp;", "&")
        vrx = re.compile(r"\s+".join("(&|and)" if t.lower() in ("&", "and") else re.escape(t) for t in v.split()), re.I)
    drop = [bool(l) and (bool(BLIND_LINE.search(l)) or l in headers or bool(vrx and vrx.search(l))) for l in short]
    if vrx:  # a journal header wrapped over two short lines
        for i in range(n - 1):
            if not drop[i] and len(short[i]) < 60 and len(short[i + 1]) < 60 and vrx.search(short[i] + " " + short[i + 1]):
                drop[i] = drop[i + 1] = True
    kept = [raw for raw, d in zip(lines, drop) if not d]
    return "\n".join(kept), sum(drop), n

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def read_docx(path):
    """Plain text of a .docx from its word/document.xml (stdlib only): one line per
    paragraph, tabs and line breaks kept, tables flattened cell by cell."""
    with zipfile.ZipFile(path) as z:
        root = ET.fromstring(z.read("word/document.xml"))
    paras = []
    for p in root.iter(W_NS + "p"):
        buf = []
        for el in p.iter():
            if el.tag == W_NS + "t":
                buf.append(el.text or "")
            elif el.tag == W_NS + "tab":
                buf.append("\t")
            elif el.tag in (W_NS + "br", W_NS + "cr"):
                buf.append("\n")
        paras.append("".join(buf))
    return "\n".join(paras)


def input_sha256(paths):
    """Hash of the raw input files in order: the paper identity recorded in provenance."""
    h = hashlib.sha256()
    for p in paths:
        h.update(hashlib.sha256(Path(p).read_bytes()).digest())
    return h.hexdigest()


def stage_paper(srcs, out_dir, blind=False, venue=None):
    """Concatenate main text + any appendix/SI files into one coder input, with named
    section markers and a provenance record -- the evidence-location rule counts a
    practice reported in an appendix, so appendices belong in the staged text, and a
    WP-vs-published comparison is only fair when both sides stage the same components."""
    dst = out_dir / "paper.txt"
    parts, prov = [], []
    for i, one in enumerate(srcs):
        one = Path(one)
        if one.suffix.lower() == ".pdf":
            from extract_columns import extract
            tmp = out_dir / f"_component_{i}.txt"
            extract(str(one), str(tmp))
            body = tmp.read_text(errors="replace")
            tmp.unlink()
        elif one.suffix.lower() == ".docx":
            body = read_docx(one)
        else:
            body = one.read_text(errors="replace")
        label = "MAIN TEXT" if i == 0 else f"SUPPLEMENT: {one.name}"
        rec = {"file": str(one), "role": "main" if i == 0 else "supplement", "chars": len(body)}
        if blind:
            body, dropped, total = blind_text(body, venue)
            rec.update({"blinded": True, "venue_masked": bool(venue), "lines_dropped": dropped, "lines_total": total, "chars_blinded": len(body)})
        parts.append(f"===== {label} =====\n\n{body}")
        prov.append(rec)
    dst.write_text("\n\n".join(parts))
    json.dump(prov, open(out_dir / "staging.json", "w"), indent=1)
    return dst, prov


# ---- provenance manifest: which invocation produced each output in out_dir ----
MANIFEST = "run_manifest.json"


def expected_prov(paper_sha, model, agent, instrument, blind, venue=None):
    return {"paper_sha256": paper_sha, "model": model, "agent": agent, "instrument": instrument,
            "blind": bool(blind), "venue": venue or None}


def load_manifest(out_dir):
    try:
        m = json.loads((out_dir / MANIFEST).read_text())
        return m if isinstance(m, dict) and isinstance(m.get("outputs"), dict) else {"outputs": {}}
    except (OSError, ValueError):
        return {"outputs": {}}


def save_manifest(out_dir, m):
    tmp = out_dir / (MANIFEST + ".tmp")
    tmp.write_text(json.dumps(m, indent=1))
    os.replace(tmp, out_dir / MANIFEST)


def record_output(out_dir, name, prov):
    m = load_manifest(out_dir)
    m["outputs"][name] = prov
    save_manifest(out_dir, m)


def add_rate_limit_waits(out_dir, n, seconds):
    if n:
        m = load_manifest(out_dir)
        m["rate_limit_waits"] = m.get("rate_limit_waits", 0) + n
        m["rate_limit_wait_s"] = m.get("rate_limit_wait_s", 0) + seconds
        save_manifest(out_dir, m)


def coding_rows_ok(path, check_ids):
    """A coding file is usable if it parses as a list of row objects and most rows carry a
    known check id (rows for other modules or papers fail this)."""
    try:
        rows = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return False
    if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
        return False
    hit = sum(1 for r in rows if r.get("check_id") in check_ids)
    return hit > 0 and hit * 2 >= len(rows)


def routing_rows_ok(path, modules):
    try:
        rows = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return False
    return (isinstance(rows, list) and all(isinstance(r, dict) and isinstance(r.get("module"), str) for r in rows)
            and all(r["module"] in modules for r in rows if r.get("module")))


def output_reusable(out_dir, name, expect, content_ok, keys=None):
    """True when out_dir/name exists, passes the content check, and its recorded provenance
    matches `expect` (on `keys` if given, else on every key of `expect`)."""
    path = out_dir / name
    if not path.exists() or not content_ok(path):
        return False
    m = load_manifest(out_dir)
    rec = m["outputs"].get(name)
    legacy_dir = m.get("legacy_dir") or not (out_dir / MANIFEST).exists()
    if rec is None and legacy_dir and os.environ.get("AMICUS_TRUST_LEGACY", "1") == "1":
        # Audit dirs written before provenance tracking have no manifest. Reuse their valid
        # outputs rather than recoding whole cohorts; set AMICUS_TRUST_LEGACY=0 to redo them.
        print(f"  reusing legacy output without provenance: {name}")
        return True
    if not isinstance(rec, dict):
        return False
    return all(rec.get(k) == expect.get(k) for k in (keys or expect))


def mark_legacy_dir(out_dir):
    """A dir holding outputs but no manifest predates provenance tracking. Say so in a new
    manifest, so its unrecorded outputs stay trusted after this run records new ones."""
    if not (out_dir / MANIFEST).exists() and ((out_dir / "routing.json").exists() or any(out_dir.glob("coding_*.json"))):
        save_manifest(out_dir, {"outputs": {}, "legacy_dir": True})


def move_aside(path):
    """Rename a stale or partial output to <name>.stale (replacing an older .stale)."""
    path = Path(path)
    if path.exists():
        os.replace(path, path.with_name(path.name + ".stale"))
        print(f"  moved aside stale/partial output: {path.name} -> {path.name}.stale")


def route(paper_txt, out_dir, call, expect):
    """Route the paper. `call(prompt)` runs the agent. A routing.json from an earlier run is
    reused only if it validates and its provenance matches; otherwise it is moved aside, so
    the file checked after the call was written by that call."""
    roster = "\n".join(f"- {m}: {d}" for m, d in ROSTER.items())
    out = out_dir / "routing.json"
    if output_reusable(out_dir, "routing.json", expect, lambda p: routing_rows_ok(p, ROSTER_ALL)):
        print("routing: reusing validated routing.json")
    else:
        move_aside(out)
        prompt = f"""You are the routing step of a paper-only methods audit. Read the paper at
`{paper_txt}` (full read). For each audit module below, decide whether the PAPER ITSELF
USES that method as part of its own empirical analysis -- a method merely cited,
discussed, or used only by prior work it references does not count.

Modules:
{roster}

Write to `{out}` a JSON array, one object per module that applies:
  {{"module": "<key>", "why": "<one sentence quoting or closely paraphrasing the
  paper's own description of using the method>"}}
Modules that do not apply are simply omitted. Write the file, then reply with the list
of module keys only."""
        r = call(prompt)
        add_rate_limit_waits(out_dir, getattr(r, "rate_limit_waits", 0), getattr(r, "rate_limit_wait_s", 0))
        if not out.exists() or not routing_rows_ok(out, ROSTER):
            move_aside(out)
            raise SystemExit(f"routing agent produced no valid routing.json (exit {r.returncode}): "
                             f"{(r.stdout or '')[-200:]} {(r.stderr or '')[-200:]}")
        record_output(out_dir, "routing.json", expect)
    routed = json.load(open(out))
    return [x["module"] for x in routed if x.get("module") in SHIPPING], routed


def checklist_path(module, run_dir):
    """The run's rendered checklist: <MODULE>_CHECKLIST.md, or UNIV_CHECKLIST.md for the universal list."""
    return UM.CHECKLIST if module == UM.MODULE else run_dir / "checklists" / f"{module.upper()}_CHECKLIST.md"


def coder_checklist(module, run_dir, out_dir):
    """Write out_dir/checklist_<module>.md, the module's rendered checklist as a coder sees it: the shipped file
    minus its plain-language explainer lines (explainer_text.strip). Explainers are for the report's reader; a
    coder works from the check's own conditions only. The copy also records exactly what the coder was given."""
    src = checklist_path(module, run_dir)
    dst = out_dir / f"checklist_{module}.md"
    dst.write_text(explainer_text.strip(src.read_text(encoding="utf-8")), encoding="utf-8")
    return dst


def render_coder_prompt(module, run_dir, paper_txt, out_json, n_checks, out_dir):
    t = (HERE / "prompts" / "coder.md").read_text()
    subs = {
        "MODULE_NAME": checklist_path(module, run_dir).name.removesuffix("_CHECKLIST.md"),  # UNIV for universal, as the paper coded it
        "KIND": "paper-only audit: you are the auditing coder for this module",
        "CHECKLIST_MD": str(coder_checklist(module, run_dir, out_dir)),
        "PAPER_PATH": str(paper_txt),
        "OUT_PATH": str(out_json),
        "N_CHECKS": str(n_checks),
    }
    for k, v in subs.items():
        t = t.replace("{{" + k + "}}", v)
    prov = json.load(open(out_dir / "staging.json"))
    comp = ", ".join(f"{x['role']} ({Path(x['file']).name})" for x in prov)
    t = t.replace(
        "Evidence scope: the provided text only (main text; appendices are not included).",
        f"Evidence scope: the provided text only. Staged components: {comp}. A practice "
        "reported in a staged supplement satisfies a check exactly as main text does.")
    p = out_dir / f"prompt_{module}.md"
    p.write_text(t)
    return p


def load_checks(run_dir):
    doc = json.load(open(run_dir / "checklists" / "verified.anchored.json"))
    return [c for c in doc if c.get("check_id")]


def validate(rows, checks, module):
    ids = {c["check_id"] for c in checks}
    rows = [r for r in rows if r.get("check_id") in ids]  # drop phantoms
    by = {r["check_id"]: r for r in rows}
    problems = [f"missing {i}" for i in ids if i not in by]
    for r in rows:
        if r.get("verdict") not in ("PASS", "FLAG", "NA"):
            problems.append(f"{r['check_id']}: verdict {r.get('verdict')!r}")
        if (r.get("verdict") == "NA") != (not r.get("in_scope", True)):
            problems.append(f"{r['check_id']}: NA/in_scope inconsistent")
    return by, problems


def read_more(check, run_dir):
    """The check's most relevant further-reading entry as one line, '<short_cite>, <pages>, https://doi.org/<doi>'
    (a part is left out when unknown; impossible pages are dropped; a DOI is never guessed). The entry is the
    first one doi_links.order_further_reading puts first, so it is the one the rendered checklist lists first.
    The DOI comes from the entry's own cite, else from source_dois.json (shipped with the runner), else from
    run_dir/config.json by source_id (internal). A plain-string entry (older hand-drafted checklists) gets no DOI.
    '' when there is no entry."""
    fr = doi_links.order_further_reading(check)
    if not fr:
        return ""
    first = fr[0]
    if isinstance(first, str):
        doi = None
    else:
        doi = doi_links.source_doi(run_dir, first.get("source_id"))
    return doi_links.read_more_line(first, doi)


def cite(check, run_dir=None):
    """Further-reading cites for a flag, up to three, as the report has always printed them. With
    `run_dir` (the check's shipping run directory) it is instead the single read_more() line for the
    first entry, with page and DOI link; a check with no further reading falls back to the old output."""
    if run_dir is not None:
        one = read_more(check, run_dir)
        if one:
            return one
    fr = check.get("further_reading") or []
    if fr:
        out = []
        for x in fr[:3]:
            if isinstance(x, dict):
                bit = x.get("short_cite") or x.get("cite", "")
                if x.get("pages"):
                    bit += f", {x['pages']}"
                out.append(bit)
            else:
                out.append(str(x))
        return "; ".join(out)
    ev = check.get("evidence") or []
    return "; ".join(sorted({e.get("short_cite", "") for e in ev if e.get("short_cite")}))


IMPORTANCE_FILE = "flag_severity.json"  # same name and shape flag_severity.py writes
ISSUES_FILE = "issues.json"  # the grouping call's output, beside flag_severity.json
IMPORTANCE_LABEL = {"critical": "Critical", "major": "Major", "minor": "Minor", "negligible": "Negligible"}
SEV_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
# Table order of the Matters column (report_spec step 4): importance levels, "unrated" when importance is
# missing, and "Single source" (every check of the issue single-source) last.
MATTERS_ORDER = ("Critical", "Major", "Minor", "Negligible", "unrated", "Single source")
MAIN_ISSUES_MAX = 5


def collect_flags(results):
    """Every FLAG across modules, in module then checklist order: the list the importance and grouping passes see,
    numbered F1, F2, ... It carries the coder's may_exist_elsewhere tag, and its pointer when the row has one."""
    flags = []
    for module, (checks, by, _problems) in results.items():
        for c in checks:
            r = by.get(c["check_id"])
            if r and r["verdict"] == "FLAG":
                f = dict(id=c["check_id"], module=module, req=c.get("requirement_statement", c.get("claim", "")),
                         note=r.get("note", ""), sev=c.get("severity_if_flagged", ""),
                         grade=c.get("consensus_grade", ""), borderline=r.get("borderline"),
                         may_exist_elsewhere=bool(r.get("may_exist_elsewhere")))
                if isinstance(r.get("pointer"), str) and r["pointer"].strip():
                    f["pointer"] = r["pointer"].strip()
                flags.append(f)
    return flags


def _flags_match(ents, flags):
    """A stored file's flag list ({key, id, module} per flag) is this run's flags, in order."""
    return (isinstance(ents, list) and len(ents) == len(flags) and
            all(isinstance(e, dict) and e.get("key") == f"F{i+1}" and e.get("id") == f["id"] and e.get("module") == f["module"]
                for i, (e, f) in enumerate(zip(ents, flags))))


def importance_ok(path, flags):
    """A flag_severity.json is usable if it is in the merged shape and matches this run's flags, in order."""
    try:
        j = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return False
    ents = j.get("flags") if isinstance(j, dict) else None
    return _flags_match(ents, flags) and not importance.validate({"flags": [{"flag": e["key"], "severity": e.get("paper_severity"), "why": e.get("why")} for e in ents]}, len(flags))


def importance_prov(base, flags):
    """Reuse key: the run's provenance plus this step, the prompt and the exact flag list it rated."""
    h = hashlib.sha256((importance.PROMPT + "\n" + importance.format_flags(flags) + "\n" + "|".join(f["id"] for f in flags)).encode()).hexdigest()
    return {**base, "step": "importance", "importance_sha256": h}


def issues_ok(path, flags):
    """An issues.json is usable if it is in the merged shape, matches this run's flags in order, and its issues
    pass grouping.validate."""
    try:
        j = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return False
    return isinstance(j, dict) and _flags_match(j.get("flags"), flags) and not grouping.validate(j, len(flags))


def grouping_prov(base, flags):
    """Reuse key: the run's provenance plus this step, the prompt and the exact flag list it grouped (with the
    may_exist_elsewhere tags the prompt shows)."""
    h = hashlib.sha256((grouping.PROMPT + "\n" + grouping.format_flags(flags) + "\n" + "|".join(f["id"] for f in flags)).encode()).hexdigest()
    return {**base, "step": "grouping", "grouping_sha256": h}


def _flag_pass(out_dir, name, label, flags, prompt, problems_of, merge, content_ok, call, expect, fallback):
    """One report-only agent call over this run's flags (importance or grouping), with the coder's retries, backoff,
    provenance and reuse rules. `problems_of(obj)` lists what is wrong with the agent's JSON, `merge(obj)` gives
    the object stored in out_dir/name, `content_ok(path)` checks a stored file before reuse. Returns (stored object
    or None, reason or None). Never raises on a bad call: the caller reports the reason and falls back."""
    out = out_dir / name
    if not flags:
        move_aside(out)  # an earlier run's output no longer describes this directory
        return None, None
    if output_reusable(out_dir, name, expect, content_ok):
        print(f"{label}: reusing validated {name}")
        return json.loads(out.read_text()), None
    move_aside(out)
    print(f"{label}: {len(flags)} flags...")
    reason = "no output"
    for attempt in range(1, CODER_ATTEMPTS + 1):
        r = call(prompt)
        add_rate_limit_waits(out_dir, getattr(r, "rate_limit_waits", 0), getattr(r, "rate_limit_wait_s", 0))
        reason = f"exit {getattr(r, 'returncode', '?')}, no output"
        if out.exists():
            try:
                j = json.loads(out.read_text())
                problems = problems_of(j)
            except ValueError as e:
                problems = [f"not JSON ({e})"]
            if not problems:
                merged = merge(j)
                out.write_text(json.dumps(merged, indent=1))
                record_output(out_dir, name, expect)
                return merged, None
            reason = "invalid output: " + "; ".join(problems[:3])
        move_aside(out)
        print(f"  {label}: no valid output on attempt {attempt}/{CODER_ATTEMPTS} ({reason})")
        if attempt < CODER_ATTEMPTS:
            _backoff(20 * attempt)
    print(f"  {label}: FAILED; {fallback}")
    return None, reason


def rate_importance(out_dir, paper_txt, flags, call, expect):
    """One agent call rating every flag with the shared prompt. Returns (entries or None, reason or None).
    Reuses a validated flag_severity.json whose provenance matches. Never raises on a bad call: the
    caller reports the reason and the report has no importance."""
    def merge(j):
        by = j["flags"]
        return {"flags": [dict(flags[i], key=f"F{i+1}", paper_severity=by[i]["severity"], why=by[i]["why"]) for i in range(len(flags))],
                "n_flags": len(flags)}
    out = out_dir / IMPORTANCE_FILE
    j, reason = _flag_pass(out_dir, IMPORTANCE_FILE, "importance", flags,
                           importance.PROMPT.format(paper=paper_txt, flags=importance.format_flags(flags), out=out),
                           lambda j: importance.validate(j, len(flags)), merge, lambda p: importance_ok(p, flags), call, expect,
                           "the report has no importance ratings")
    return (j["flags"] if j else None), reason


def group_flags(out_dir, paper_txt, flags, call, expect):
    """One agent call grouping the flags into issues with grouping.PROMPT, with the same machinery as
    rate_importance. Returns (issues or None, reason or None); each issue is {title, where, flags: [F keys]}.
    issues.json also records which check each F key stands for, so a reader can follow it."""
    def merge(j):
        return {"issues": [{"title": g["title"].strip(), "where": g["where"].strip(), "flags": list(g["flags"])} for g in j["issues"]],
                "flags": [{"key": f"F{i+1}", "id": f["id"], "module": f["module"]} for i, f in enumerate(flags)],
                "n_flags": len(flags)}
    out = out_dir / ISSUES_FILE
    j, reason = _flag_pass(out_dir, ISSUES_FILE, "grouping", flags,
                           grouping.PROMPT.format(paper=paper_txt, flags=grouping.format_flags(flags), out=out),
                           lambda j: grouping.validate(j, len(flags)), merge, lambda p: issues_ok(p, flags), call, expect,
                           "the report lists each flag as its own issue")
    return (j["issues"] if j else None), reason


def _plain_list(items):
    """'a', 'a and b', 'a, b, and c'."""
    items = list(items)
    return items[0] if len(items) == 1 else " and ".join(items) if len(items) == 2 else ", ".join(items[:-1]) + ", and " + items[-1]


UNIVERSAL_NAME = "Universal checklist"
UNIVERSAL_WHY = "runs on every paper"


def _module_name(module):
    """A module's plain display name ("Synthetic control"); the key itself when it has none."""
    if module == UM.MODULE:
        return UNIVERSAL_NAME
    return MODULE_NAMES.get(module) or ROSTER_ALL.get(module) or module


def _module_phrase(modules):
    """The coded design modules in plain lower-case words, for the header sentence (the universal list is not one)."""
    return _plain_list([n[0].lower() + n[1:] for n in map(_module_name, (m for m in modules if m != UM.MODULE))])


def _does_well(results, limit=3, explainers=None):
    """Up to `limit` passed in-scope checks, as (check id, text) pairs: severity HIGH first, then checklist order
    (modules in run order). Only a PASS verdict on an in-scope check of a method module is praised. The text is "The paper <done>."
    from the check's explainer (`explainers` is {module: {check_id: explainer}}) and, without one, "The paper meets
    this requirement: <requirement>"."""
    explainers = explainers or {}
    passed = [(m, c) for m, (checks, by, _p) in results.items() for c in checks
              if m != UM.MODULE  # universal `done` phrases await author review: several overstate what a pass shows
              and by.get(c["check_id"], {}).get("verdict") == "PASS" and by[c["check_id"]].get("in_scope", True)]
    passed.sort(key=lambda mc: SEV_RANK.get(str(mc[1].get("severity_if_flagged", "")).upper(), 3))  # stable: checklist order inside a rank
    out = []
    for m, c in passed[:limit]:
        done = (explainers.get(m, {}).get(c["check_id"]) or {}).get("done")
        out.append((c["check_id"], f"The paper {done.rstrip('.')}." if done else
                    "The paper meets this requirement: " + c.get("requirement_statement", c.get("claim", ""))))
    return out


def _explainers(run_dir):
    """The run's explainers ({check_id: {plain, why, done}}), or {} when it has none (a missing file is normal:
    other instruments, a sparse checkout). A damaged file is reported on stderr and treated as absent, so the
    report is still written from the checklist's own text."""
    if run_dir is None:
        return {}
    try:
        return explainer_text.load(run_dir)
    except (ValueError, OSError) as exc:
        print(f"warning: explainers ignored: {exc}", file=sys.stderr)
        return {}


def _cell(x):
    return str(x if x is not None else "").replace("|", "/").replace("\n", " ").strip()


def _sentence(s):
    """s stripped, ending in a full stop unless it already ends a sentence; '' stays ''."""
    s = (s or "").strip()
    return s if not s or s[-1] in ".!?" else s + "."


def _short_title(f):
    """An ungrouped flag's issue title: its requirement in short form (the first ten words), else its check id."""
    words = (f.get("req") or "").split()
    if not words:
        return f["id"]
    return " ".join(words).rstrip(".") if len(words) <= 10 else " ".join(words[:10]).rstrip(",;:.") + "..."


def _where(where, fl, grouped):
    """The Where cell of one issue: the grouping call's location ("silent" if it gave none; "not located" when the
    flags were not grouped), plus "not seen (<pointer>)" when a flag carries the coder's may_exist_elsewhere tag
    and the location does not already say not seen ("not seen" alone when the coder row names no pointer)."""
    w = where.strip() if grouped else ""
    mee = [f for f in fl if f.get("may_exist_elsewhere")]
    if mee and "not seen" not in w.lower():
        ptrs = list(dict.fromkeys(f["pointer"] for f in mee if f.get("pointer")))
        seen = f"not seen ({'; '.join(ptrs)})" if ptrs else "not seen"
        w = seen if not w or w.lower() == "silent" else f"{w}; {seen}"
    return w or ("silent" if grouped else "not located")


def _issues(flags, imp_by, grouped=None):
    """The report's issues, in table order. `grouped` is the grouping call's list ({title, where, flags: [F keys]}),
    or None, when each flag is its own issue. Each issue has its title, where, flags (collect_flags dicts, as
    listed), matters, main (the flag its details come from) and borderline (any of its checks borderline).
    Matters is the highest importance among its checks that are not single-source (consensus "low"), "Single source" when
    all are, and "unrated" without importance. The main check is the highest importance, then checklist severity,
    then first listed, among the checks Matters counts. Rows: Matters, then the main check's importance (orders the
    Single source rows) and checklist severity, then the order the grouping call gave."""
    def lrank(f):
        lv = (imp_by.get((f["module"], f["id"])) or {}).get("paper_severity")
        return importance.LEVELS.index(lv) if lv in importance.LEVELS else len(importance.LEVELS)

    def srank(f):
        return SEV_RANK.get(str(f.get("sev", "")).upper(), 3)
    if grouped:
        raw = [(g["title"].strip(), g.get("where") or "", [flags[int(k[1:]) - 1] for k in g["flags"]]) for g in grouped]
    else:
        raw = [(_short_title(f), "", [f]) for f in flags]
    out = []
    for i, (title, where, fl) in enumerate(raw):
        counted = [f for f in fl if f.get("grade") != "low"]
        main = min(counted or fl, key=lambda f: (lrank(f), srank(f)))  # min keeps the first listed among ties
        if not counted:
            matters = "Single source"
        elif lrank(main) < len(importance.LEVELS):
            matters = IMPORTANCE_LABEL[importance.LEVELS[lrank(main)]]
        else:
            matters = "unrated"
        out.append(dict(title=title, where=_where(where, fl, bool(grouped)), flags=fl, matters=matters, main=main,
                        borderline=any(f.get("borderline") for f in fl),
                        order=(MATTERS_ORDER.index(matters), lrank(main), srank(main), i)))
    return sorted(out, key=lambda x: x["order"])


def _noticed(f, c, e):
    """What I noticed, for one flag: the coder's note, else the explainer's plain sentence, else the requirement."""
    return (f.get("note") or "").strip() or e.get("plain") or c.get("requirement_statement", "")


def _details_paragraph(x, c, e):
    """The Details paragraph of one issue, built from its main check: the coder's note (what I noticed), the
    explainer's why (else the check's claim), the checklist's author guidance as what you could add when present,
    and "It is a close call." when any check of the issue is borderline."""
    parts = [_sentence(_noticed(x["main"], c, e)), _sentence(e.get("why") or c.get("claim"))]
    if (c.get("author_guidance") or "").strip():
        parts.append("What you could add: " + _sentence(c["author_guidance"]))
    if x["borderline"]:
        parts.append("It is a close call.")
    return " ".join(p for p in parts if p)


def _what_i_read(out_dir):
    """The staged components from out_dir/staging.json ("the main text (a.pdf) and 1 supplement (b.pdf)"), or
    "the paper's text" when there is no readable record."""
    try:
        prov = json.loads((Path(out_dir) / "staging.json").read_text())
        main = [Path(x["file"]).name for x in prov if x.get("role") == "main"]
        sup = [Path(x["file"]).name for x in prov if x.get("role") == "supplement"]
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return "the paper's text"
    if not main:
        return "the paper's text"
    text = f"the main text ({main[0]})"
    if sup:
        text += f" and {len(sup)} supplement{'s' if len(sup) > 1 else ''} ({', '.join(sup)})"
    return text


ENCOURAGEMENT = "I hope these notes help with the revision; you are the judge of what to change."


def report(out_dir, paper_name, routed_why, results, failed=(), importance_flags=None, importance_note=None, run_dirs=None,
           issues=None, grouping_note=None):
    """Write AUDIT_REPORT.md, summary first in the layout of report_spec.REPORT_STEPS: header with counts, module
    lines and what I could read; what the paper does well; the main issues; one table of every issue with
    report_spec.LEGEND under it; details for Critical and Major issues; not completed; hardest calls; a closing
    note ending with report_spec.DISCLAIMER. `importance_flags` are the importance pass's entries (None: every issue
    is unrated, there are no main issues, and every issue gets details); `issues` the grouping call's issues (None:
    each flag is its own issue); the two notes say why either is missing. Checklist severity only orders rows and
    never appears in the text. Also writes AUDIT_DETAILS.md (every check, with its flag's issue). `run_dirs` maps
    module to its shipping run directory, where each check's source is looked up; it defaults to the 2025
    instrument's SHIPPING runs."""
    imp_by = {(f["module"], f["id"]): f for f in (importance_flags or [])}
    run_dirs = run_dirs or {m: ROOT / "runs" / "skill_generation" / {**SHIPPING, UM.MODULE: UM.RUN}[m]
                            for m in results if m in SHIPPING or m == UM.MODULE}
    expl = {m: _explainers(run_dirs.get(m)) for m in results}  # per module, {check_id: explainer}; {} when the run has none
    checks_by = {(m, c["check_id"]): c for m, (checks, _by, _p) in results.items() for c in checks}
    flags = collect_flags(results)  # F1.. in the order the importance and grouping calls saw them
    if issues and grouping.validate({"issues": issues}, len(flags)):
        issues, grouping_note = None, grouping_note or "the stored grouping does not match this run's flags"
    iss = _issues(flags, imp_by, issues)
    rated = bool(imp_by)
    detailed = [x for x in iss if x["matters"] in ("Critical", "Major")] if rated else iss

    L = [f"# AMICUS report: {paper_name}", ""]
    if failed:
        L += [f"> **INCOMPLETE AUDIT: the coder failed for {len(failed)} module(s): "
              f"{', '.join(m.upper() for m in failed)}.** Their results are not in this report; "
              "absence of a module below does not mean it passed. See coder_failures.json.", ""]
    if flags and importance_note:
        L += [f"> **Importance ratings are not in this report because {importance_note}, so I list no main issues, "
              "every issue is unrated, and every issue has details.**", ""]
    if flags and grouping_note:
        L += [f"> **The flags are not grouped into issues because {grouping_note}, so each flag is its own issue.**", ""]
    L += [f"*{date.today().isoformat()} · {RELEASE}*", ""]
    if results:
        n = sum(1 for _c, by, _p in results.values() for r in by.values() if r["verdict"] in ("PASS", "FLAG"))
        counts = f"{n} check{'' if n == 1 else 's'}, " + (f"{len(flags)} flagged" if flags else "none flagged")
        if flags and rated:
            k = sum(1 for f in flags if f.get("grade") != "low" and imp_by.get((f["module"], f["id"]), {}).get("paper_severity") == "critical")
            counts += f", {k} critical" if k else ", none critical"
        designs = [m for m in results if m != UM.MODULE]
        if designs and UM.MODULE in results:
            L += [f"I read your paper against the methods literature for {_module_phrase(results)}, plus my general checks: {counts}.", ""]
        elif designs:
            L += [f"I read your paper against the methods literature for {_module_phrase(results)}: {counts}.", ""]
        else:
            L += [f"None of the method checklists applies to this paper, so I read it against my general checks only: {counts}.", ""]
    elif not failed:
        L += ["None of the methods checklists applies to this paper, so I have nothing to report.", ""]
    if routed_why:
        L += [f"- {_module_name(x['module'])}: {x.get('why', '')}" + (" (not completed)" if x["module"] in failed else "")
              for x in routed_why] + [""]
    L += [f"What I could read: {_what_i_read(out_dir)}, not the data or code. A flag means the paper does not "
          "report something, which may be a gap in the write-up rather than the analysis.", ""]

    well = _does_well(results, explainers=expl)
    if well:
        L += ["## What the paper does well", ""] + [f"- {text}" for _i, text in well] + [""]

    if flags and rated:
        L += ["## The main issues", ""]
        top = [x for x in iss if x["matters"] in ("Critical", "Major")][:MAIN_ISSUES_MAX]
        for k, x in enumerate(top, 1):
            f = x["main"]
            noticed = _noticed(f, checks_by[(f["module"], f["id"])], expl[f["module"]].get(f["id"]) or {})
            L.append(f"{k}. **{_sentence(x['title'])}** {_sentence(noticed)} "
                     f"({x['matters']}, {len(x['flags'])} check{'' if len(x['flags']) == 1 else 's'})")
        L += ([] if top else ["None of the issues is rated Critical or Major."]) + [""]

    if results:
        L += ["## Everything I flagged", ""]
        if iss:
            L += ["| Matters | Issue | Where | Checks |", "|---|---|---|---|"]
            L += [f"| {x['matters']} | {_cell(x['title'])} | {_cell(x['where'])} | {', '.join(f['id'] for f in x['flags'])} |" for x in iss]
            L += ["", report_spec.LEGEND, ""]
        else:
            L += ["No flags.", ""]

    if detailed:
        L += ["## Details", ""]
        for x in detailed:
            f = x["main"]
            c = checks_by[(f["module"], f["id"])]
            L += [f"### {x['title']} ({x['matters']})", "", _details_paragraph(x, c, expl[f["module"]].get(f["id"]) or {}), ""]
            src = cite(c, run_dirs.get(f["module"]))
            L += ([f"Read more: {src}"] if src else []) + [f"Checks: {', '.join(g['id'] for g in x['flags'])}", ""]

    L += ["## Not completed", ""]
    nc = [f"- {_module_name(m)}: the coder failed, so none of its checks are in this report (see coder_failures.json)." for m in failed]
    for module, (checks, by, problems) in results.items():
        missing = [c["check_id"] for c in checks if c["check_id"] not in by]
        if missing:
            nc.append(f"- {_module_name(module)}: {len(missing)} check{'' if len(missing) == 1 else 's'} without a verdict "
                      f"({len(by)} of {len(checks)} checks returned): {', '.join(missing)}.")
        other = [p for p in problems if not p.startswith("missing ")]
        if other:
            nc.append(f"- {_module_name(module)}, coding problems: {'; '.join(other)}.")
    L += (nc or ["None."]) + [""]

    hard = [x["title"] for x in detailed if x["borderline"]]
    L += ["## Hardest calls", "",
          f"These issues include a check a second reader could judge differently: {'; '.join(hard)}." if hard else "None.", ""]
    L += [ENCOURAGEMENT, "", "The full per-check table is in AUDIT_DETAILS.md in this directory.", "", report_spec.DISCLAIMER]
    p = out_dir / "AUDIT_REPORT.md"
    p.write_text("\n".join(L) + "\n")

    issue_of = {(f["module"], f["id"]): x["title"] for x in iss for f in x["flags"]}
    D = [f"# Per-check details: {paper_name}", "",
         f"*{date.today().isoformat()} · {RELEASE}. Every check the audit covered, with its verdict. "
         "The summary is in AUDIT_REPORT.md.*", ""]
    for module, (checks, by, _p) in results.items():
        D += [f"## {module.upper()}", "",
              "| Check | Verdict | Checklist severity | Consensus | Importance | Issue | Tags | Coder note |", "|---|---|---|---|---|---|---|---|"]
        for c in checks:
            r = by.get(c["check_id"])
            imp = imp_by.get((module, c["check_id"]))
            tags = ", ".join(t for t, on in (("borderline", r and r.get("borderline")), ("may exist elsewhere", r and r.get("may_exist_elsewhere"))) if on)
            D.append("| " + " | ".join([c["check_id"], r["verdict"] if r else "no row", _cell(c.get("severity_if_flagged")), _cell(c.get("consensus_grade")),
                                        imp["paper_severity"] if imp else "", _cell(issue_of.get((module, c["check_id"]))), tags,
                                        _cell(r.get("note") if r else "")]) + " |")
        D.append("")
    (out_dir / "AUDIT_DETAILS.md").write_text("\n".join(D) + "\n")
    return p


def _backoff(seconds):
    time.sleep(seconds)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", required=True, nargs="+",
                help="main text first, then any appendix/SI files (pdf, docx or txt)")
    ap.add_argument("--modules", help="comma list; omit to auto-route")
    ap.add_argument("--out")
    ap.add_argument("--agent", default=DEFAULT_AGENT, choices=AGENTS, help="CLI that runs the coder")
    ap.add_argument("--model", default=None, help="default: per-agent model in agent_call.py")
    ap.add_argument("--effort", default=None, help="reasoning effort; default: per-agent default in agent_call.py")
    ap.add_argument("--instrument", default="2025", choices=list(SHIPPING_BY_INSTRUMENT),
                help="checklist instrument (default 2025)")
    ap.add_argument("--no-importance", action="store_true",
                    help="skip both report-only calls: the importance pass (rates each flag for this paper) and the grouping "
                         "pass (groups flags into issues), which never runs without importance; research batch launchers pass it. "
                         "Default is to run both")
    ap.add_argument("--no-universal", action="store_true",
                    help="do not code the universal checklist, which otherwise runs on every paper after the routed modules; "
                         "research batch launchers pass it")
    ap.add_argument("--blind", action="store_true", help="strip DOI/publisher/date/preprint-server cues from the staged text (both versions)")
    ap.add_argument("--venue", default=None, help="with --blind: journal name whose mentions are also dropped (pass for both versions)")
    a = ap.parse_args(argv)
    shipping = SHIPPING_BY_INSTRUMENT[a.instrument]
    runs = {**shipping, UM.MODULE: UM.RUN}  # the universal list has one version for every instrument
    model = a.model or default_model(a.agent)
    effort = a.effort or default_effort(a.agent)
    if a.modules:
        modules_arg = [m.strip() for m in a.modules.split(",") if m.strip()]
        bad = [m for m in modules_arg if m not in runs]
        if bad or not modules_arg:
            raise SystemExit(f"error: unknown module(s) {', '.join(bad) or '(none given)'}; valid modules: {', '.join(runs)}")
    papers = [Path(x).resolve() for x in a.paper]
    missing_in = [str(x) for x in papers if not x.exists()]
    if missing_in:
        raise SystemExit(f"error: paper file(s) not found: {', '.join(missing_in)}")
    slug = re.sub(r"[^a-z0-9]+", "_", papers[0].stem.lower())[:40]
    out_dir = (Path(a.out) if a.out else ROOT / "runs" / "paper_audits" / f"{date.today():%Y%m%d}_{slug}").resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    mark_legacy_dir(out_dir)
    (out_dir / "instrument.json").write_text(json.dumps({"instrument": a.instrument, "shipping": shipping,
                                                         "universal": None if a.no_universal else UM.RUN}, indent=1))

    def call(prompt):
        return run_agent(prompt, agent=a.agent, model=model, cwd=out_dir, write_dir=out_dir, effort=effort)

    paper_txt, prov = stage_paper(papers, out_dir, blind=a.blind, venue=a.venue)
    base = expected_prov(input_sha256(papers), model, a.agent, a.instrument, a.blind, a.venue)
    if a.modules:
        modules = modules_arg
        routed_why = [{"module": m, "why": "selected by hand"} for m in modules]
    else:
        print("routing...")
        modules, routed_why = route(paper_txt, out_dir, call, base)
    print("modules:", modules or "(none fired)")
    if not a.no_universal and UM.MODULE not in modules:
        modules = [*modules, UM.MODULE]
        routed_why = [*routed_why, {"module": UM.MODULE, "why": UNIVERSAL_WHY}]

    results, failures = {}, []
    for m in modules:
        run_dir = ROOT / "runs" / "skill_generation" / runs[m]
        checks = load_checks(run_dir)
        ids = {c["check_id"] for c in checks}
        name = f"coding_{m}.json"
        out_json = out_dir / name
        expect = {**base, "module": m, "checklist": runs[m]}
        if output_reusable(out_dir, name, expect, lambda p: coding_rows_ok(p, ids)):
            print(f"  {m}: reusing validated {name}")
        else:
            move_aside(out_json)
            pr = render_coder_prompt(m, run_dir, paper_txt, out_json, len(checks), out_dir)
            print(f"coding {m} ({len(checks)} checks)...")
            attempts, ok = [], False
            for attempt in range(1, CODER_ATTEMPTS + 1):
                r = call(pr.read_text())
                add_rate_limit_waits(out_dir, getattr(r, "rate_limit_waits", 0), getattr(r, "rate_limit_wait_s", 0))
                attempts.append({"attempt": attempt, "exit": r.returncode, "stderr_tail": (r.stderr or "")[-400:], "stdout_tail": (r.stdout or "")[-400:]})
                ok = out_json.exists() and coding_rows_ok(out_json, ids)
                if ok:
                    break
                move_aside(out_json)  # missing, truncated or foreign: never leave it for the next read
                print(f"  {m}: coder produced no valid output on attempt {attempt}/{CODER_ATTEMPTS} (exit {r.returncode})")
                if attempt < CODER_ATTEMPTS:
                    _backoff(20 * attempt)
            if not ok:
                failures.append({"module": m, "model": model, "agent": a.agent, "instrument": a.instrument, "attempts": attempts})
                print(f"  {m}: FAILED after {CODER_ATTEMPTS} attempts; recorded in coder_failures.json")
                continue
            record_output(out_dir, name, expect)
        by, problems = validate(json.load(open(out_json)), checks, m)
        results[m] = (checks, by, problems)
        print(f"  {m}: {len(by)} of {len(checks)} rows, {len(problems)} validation notes")

    fpath = out_dir / "coder_failures.json"
    if failures:
        json.dump(failures, open(fpath, "w"), indent=1)
    elif fpath.exists():
        move_aside(fpath)  # an earlier run's failures no longer describe this directory
    failed = [f["module"] for f in failures]
    flags = collect_flags(results)
    imp_flags, imp_note, issues, grp_note = None, None, None, None
    if a.no_importance:  # both report-only calls are skipped; grouping never runs without importance
        imp_note = "the importance pass was skipped (--no-importance)"
        grp_note = "the grouping pass is skipped with it (--no-importance)"
    else:
        imp_flags, reason = rate_importance(out_dir, paper_txt, flags, call, importance_prov(base, flags))
        if reason:
            imp_note = f"the importance call failed after {CODER_ATTEMPTS} attempts ({reason})"
        issues, reason = group_flags(out_dir, paper_txt, flags, call, grouping_prov(base, flags))
        if reason:
            grp_note = f"the grouping call failed after {CODER_ATTEMPTS} attempts ({reason})"
    rp = report(out_dir, papers[0].stem, routed_why, results, failed, imp_flags, imp_note,
                run_dirs={m: ROOT / "runs" / "skill_generation" / runs[m] for m in results},
                issues=issues, grouping_note=grp_note)
    print("report:", rp)
    if failed:
        print(f"FAILED modules: {', '.join(failed)}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
