#!/usr/bin/env python3
"""Generate plain-language explainers for every check of every shipped module.

  python3 scripts/skillgen/build_explainers.py --dry-run            prompt size and check count per module
  python3 scripts/skillgen/build_explainers.py                      all 15 modules (14 design modules + universal)
  python3 scripts/skillgen/build_explainers.py --modules did,iv     a subset
  python3 scripts/skillgen/build_explainers.py --review-md PATH     also write the review file for the authors

One agent call per module (Claude, through agent_call.run_agent) writes `plain`, `why` and `done` for each check; the
prompt and its validator are in explainer_prompt.py. Output: runs/skill_generation/<run>/checklists/explainers.json,
beside verified.anchored.json, which this script only reads. The agent's cwd and write permission are a scratch
directory (checklists/.explainers_tmp/) that is removed afterwards, so the call cannot touch the checklist files.

A reply is accepted only if explainer_prompt.validate passes and none of `plain`, `why` or `done` repeats an 8-token
run of any of that check's evidence quotes. Otherwise the call is retried (two more tries, with backoff); a module
that never validates is reported as failed, the rest continue, and the exit status is 1.

An existing explainers.json is kept when it validates, carries the current prompt's sha256 and covers the same
check ids; --force redoes it. Changing explainer_prompt.PROMPT therefore regenerates every module.
"""
import argparse
import hashlib
import json
import re
import shutil
import sys
import time
import unicodedata
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

import explainer_prompt as EP  # noqa: E402
import universal_module  # noqa: E402
from agent_call import run_agent, default_model, default_effort  # noqa: E402
from paper_only_audit import SHIPPING  # noqa: E402

AGENT = "claude"
RUNS = ROOT / "runs" / "skill_generation"
MODULES = {**SHIPPING, universal_module.MODULE: universal_module.RUN}  # design modules, then the universal checklist
ATTEMPTS = 3                 # one try plus two retries
BACKOFF_S = (15, 60)         # sleep before retry 1 and retry 2
LEAK_TOKENS = 8              # the Stage 9 rule: no 8-token window of an evidence quote may reappear
TMP_NAME = ".explainers_tmp"
OUT_NAME = "explainers.json"
FIELDS = ("plain", "why", "done")  # the text fields of each saved entry, after check_id

# Wording only for the prompt's "{module}" slot and the review file; same names as the site (scripts/build_site.py).
LABELS = {
    "iv": "instrumental variables", "did": "difference-in-differences", "rdd": "regression discontinuity",
    "conjoint": "conjoint experiment", "survey_exp": "survey experiment", "field_exp": "field experiment",
    "text": "text as data", "matching": "matching", "mediation": "mediation", "multilevel": "multilevel model",
    "panel": "panel data", "synth": "synthetic control", "measurement": "measurement",
    "hte": "heterogeneous treatment effects", "universal": "universal (method-agnostic)",
}


def _sleep(s):
    time.sleep(s)


def _log(msg):
    print(msg, flush=True)


def label(mod):
    return LABELS.get(mod, mod)


def prompt_sha256():
    return hashlib.sha256(EP.PROMPT.encode()).hexdigest()


def checklist_dir(run):
    return RUNS / run / "checklists"


def load_checks(run):
    """The checks of a shipped run, in file order (the head record, when there is one, is skipped)."""
    with open(checklist_dir(run) / "verified.anchored.json") as f:
        doc = json.load(f)
    return [c for c in doc if c.get("check_id")]


def build_prompt(mod, checks, out):
    return EP.PROMPT.format(module=label(mod), checks=EP.format_checks(checks), out=out)


# ---------------------------------------------------------------- leak gate

def _tokens(s):
    """The Stage 9 normalization (run_skillgen.stage_leak): NFKC, lowercase, every non-word run is a separator."""
    return re.sub(r"\W+", " ", unicodedata.normalize("NFKC", s).lower()).split()


def leaked_runs(texts, quotes, n=LEAK_TOKENS):
    """The first n-token run, if any, that each text repeats from the quotes (token level, so a quote shorter
    than n tokens cannot leak). Same rule as run_skillgen.stage_leak, which only reads a rendered markdown
    file inside a run directory and so cannot be reused here; unlike it there is no character-length floor."""
    grams = set()
    for q in quotes:
        w = _tokens(q)
        grams.update(tuple(w[i:i + n]) for i in range(len(w) - n + 1))
    hits = []
    for t in texts:
        w = _tokens(t)
        hits.extend(" ".join(w[i:i + n]) for i in range(len(w) - n + 1) if tuple(w[i:i + n]) in grams)
    return hits[:1]


def leak_problems(obj, checks):
    """One problem per `plain`/`why`/`done` that repeats an 8-token run from its own check's evidence quotes."""
    by_id = {c["check_id"]: c for c in checks}
    problems = []
    for e in (obj.get("explainers") or []) if isinstance(obj, dict) else []:
        if not isinstance(e, dict) or e.get("check_id") not in by_id:
            continue
        quotes = [x["quote"] for x in by_id[e["check_id"]].get("evidence", []) if isinstance(x, dict) and isinstance(x.get("quote"), str)]
        for field in FIELDS:
            if isinstance(e.get(field), str):
                for frag in leaked_runs([e[field]], quotes):
                    problems.append(f"{e['check_id']}: {field} repeats {LEAK_TOKENS} source tokens: {frag!r}")
    return problems


def all_problems(obj, checks):
    return EP.validate(obj, [c["check_id"] for c in checks]) + leak_problems(obj, checks)


# ---------------------------------------------------------------- files

def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        return {"_error": f"{type(e).__name__}: {e}"}


def read_explainers(path, checks):
    """The parsed explainers file if it exists and passes validation and the leak gate, else None."""
    if not path.exists():
        return None
    obj = read_json(path)
    return obj if not all_problems(obj, checks) else None


def is_current(path, mod, run, checks):
    obj = read_explainers(path, checks)
    return bool(obj and obj.get("prompt_sha256") == prompt_sha256() and obj.get("module") == mod
                and obj.get("run") == run and [e["check_id"] for e in obj["explainers"]] == [c["check_id"] for c in checks])


def attempt(prompt, model, tmp, out, checks):
    """One call. Returns (parsed object or None, problems)."""
    out.unlink(missing_ok=True)
    r = run_agent(prompt, agent=AGENT, model=model, cwd=tmp, write_dir=tmp, effort=default_effort(AGENT))
    if not out.exists():
        return None, [f"no output file written (exit {r.returncode}; {((r.stderr or '') + (r.stdout or ''))[-200:].strip()!r})"]
    obj = read_json(out)
    if isinstance(obj, dict) and "_error" in obj:
        return None, [f"output is not valid JSON ({obj['_error']})"]
    return obj, all_problems(obj, checks)


def generate(mod, run, checks, model):
    """Call, validate and write one module's explainers.json. Returns None on success, else the last problems."""
    final = checklist_dir(run) / OUT_NAME
    tmp = checklist_dir(run) / TMP_NAME
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    out = tmp / OUT_NAME
    prompt = build_prompt(mod, checks, out)
    problems = []
    try:
        for n in range(1, ATTEMPTS + 1):
            obj, problems = attempt(prompt, model, tmp, out, checks)
            if not problems:
                break
            _log(f"  {mod}: attempt {n}/{ATTEMPTS} rejected: {'; '.join(problems[:3])}" + (f" (+{len(problems) - 3} more)" if len(problems) > 3 else ""))
            if n < ATTEMPTS:
                _sleep(BACKOFF_S[min(n, len(BACKOFF_S)) - 1])
        if problems:
            return problems
        data = {"module": mod, "run": run, "model": model, "prompt_sha256": prompt_sha256(),
                "generated": date.today().isoformat(),
                "explainers": [{"check_id": e["check_id"], **{f: e[f].strip() for f in FIELDS}} for e in obj["explainers"]]}
        part = tmp / "final.json"
        part.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
        part.replace(final)
        return None
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------- review file

def clean(s):
    """House style bans em dashes in published text; same rewrite as scripts/build_site.py."""
    dash = chr(0x2014)
    return str(s).replace(f" {dash} ", ", ").replace(dash, ", ")


def write_review_md(path, mods):
    """One Markdown file for the authors: every check's requirement, then plain, why and done, from the files on disk."""
    parts, n_checks, n_mods = [], 0, 0
    for mod in mods:
        run = MODULES[mod]
        checks = load_checks(run)
        obj = read_explainers(checklist_dir(run) / OUT_NAME, checks)
        parts.append(f"## {label(mod).capitalize()} (`{mod}`)\n")
        if obj is None:
            parts.append("No explainers generated for this module yet.\n")
            continue
        n_mods += 1
        for c, e in zip(checks, obj["explainers"]):
            n_checks += 1
            parts.append(f"### {c['check_id']}\n\n**Requirement:** {clean(c['requirement_statement'])}\n\n"
                         f"**Plain:** {e['plain']}\n\n**Why:** {e['why']}\n\n**Done:** {e['done']}\n")
    head = ("# AMICUS check explainers, for review\n\n"
            "Reviewers: mark any fix inline, next to the sentence it concerns (for example, \"FIX: ...\"); "
            "leave a sentence as is if it is right.\n\n"
            f"{n_checks} checks across {n_mods} modules.\n")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([head] + parts))


# ---------------------------------------------------------------- main

def select_modules(arg):
    if not arg:
        return list(MODULES)
    mods = [m.strip() for m in arg.split(",") if m.strip()]
    bad = [m for m in mods if m not in MODULES]
    if bad or not mods:
        raise SystemExit(f"error: unknown module(s) {', '.join(bad) or '(none given)'}; valid modules: {', '.join(MODULES)}")
    return list(dict.fromkeys(mods))


def dry_run(mods):
    print(f"{'module':<12} {'run':<36} {'checks':>6} {'prompt chars':>13} {'prompt words':>13}  file")
    tot_checks = tot_chars = 0
    for mod in mods:
        run = MODULES[mod]
        checks = load_checks(run)
        p = build_prompt(mod, checks, checklist_dir(run) / TMP_NAME / OUT_NAME)
        state = "current" if is_current(checklist_dir(run) / OUT_NAME, mod, run, checks) else "to generate"
        print(f"{mod:<12} {run:<36} {len(checks):>6} {len(p):>13} {len(p.split()):>13}  {state}")
        tot_checks += len(checks)
        tot_chars += len(p)
    print(f"{len(mods)} modules, {tot_checks} checks, {tot_chars} prompt characters; no call made")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--modules", help="comma-separated module names (default: all %d)" % len(MODULES))
    ap.add_argument("--model", default=None, help=f"default: {AGENT} model in agent_call.py ({default_model(AGENT)})")
    ap.add_argument("--dry-run", action="store_true", help="print each module's prompt size and check count; no call")
    ap.add_argument("--force", action="store_true", help="regenerate even when a valid, current explainers.json exists")
    ap.add_argument("--review-md", metavar="PATH", help="write one Markdown review file from the explainers on disk")
    a = ap.parse_args(argv)
    mods = select_modules(a.modules)
    model = a.model or default_model(AGENT)
    failed = []

    if a.dry_run:
        dry_run(mods)
    else:
        for mod in mods:
            run = MODULES[mod]
            try:
                checks = load_checks(run)
                if not a.force and is_current(checklist_dir(run) / OUT_NAME, mod, run, checks):
                    _log(f"{mod}: current {OUT_NAME} kept ({len(checks)} checks)")
                    continue
                _log(f"{mod}: generating {len(checks)} explainers with {model}...")
                problems = generate(mod, run, checks, model)
            except (KeyError, ValueError, OSError) as e:
                problems = [f"{type(e).__name__}: {e}"]
            if problems:
                failed.append(mod)
                _log(f"{mod}: FAILED after {ATTEMPTS} attempts: {'; '.join(problems[:5])}")
            else:
                _log(f"{mod}: wrote {checklist_dir(run) / OUT_NAME}")
        if failed:
            _log(f"failed modules: {', '.join(failed)}")
    if a.review_md:
        write_review_md(a.review_md, mods)
        _log(f"review file: {a.review_md}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
