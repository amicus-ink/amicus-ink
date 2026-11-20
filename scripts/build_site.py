#!/usr/bin/env python3
"""Build and check the AMICUS static site.

  python3 scripts/build_site.py            regenerate site/checklists.html and site/checklists/*.html
  python3 scripts/build_site.py --check    verify every internal link and anchor in site/*.html

Generated pages: checklists.html, an overview (one anatomy card, one card per design with a
stacked bar of checks by category), and checklists/<module>.html, one page per full checklist,
both built from the shipping runs that scripts/skillgen/render_checklists_html.py loads (the
same data the shipped Markdown checklists are rendered from). It also copies
public/AMICUS.md to site/AMICUS.md so the chatbot route can point at amicus.ink/AMICUS.md. The other pages are hand-written. The build is idempotent:
the same inputs give the same bytes. Stdlib only.

The pages keep the repo-URL and raw-URL tokens (double-brace names). scripts/export_public.py
substitutes tokens in .md files only, so the Pages workflow (.github/workflows/pages.yml)
fills them in the HTML at deploy time.
"""
import json
import re
import sys
from html import escape as E
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SITE = ROOT / "site"
sys.path.insert(0, str(HERE / "skillgen"))
import render_checklists_html as R  # noqa: E402
import universal_module as UM  # noqa: E402
from doi_links import cite_with_doi, clean_pages, order_further_reading, source_doi  # noqa: E402
import explainer_text  # noqa: E402
from paper_only_audit import MODULE_NAMES  # noqa: E402

INST = "2025"
TOKEN = re.compile(r"\{\{[A-Z_]+\}\}")


def nav_footer():
    """Take nav and footer from run.html so every page shares one copy."""
    t = (SITE / "run.html").read_text()
    nav = re.search(r'<nav class="topnav">.*?</nav>', t, re.S).group(0).replace(' class="active"', "")
    foot = re.search(r"<footer>.*?</footer>", t, re.S).group(0)
    return nav.replace('<a href="./checklists.html">', '<a href="./checklists.html" class="active">'), foot


NAMES = {**MODULE_NAMES, "universal": "Universal"}
CATS = [("IDENT", "Identification", "ident"), ("EST", "Estimation", "est"), ("INFER", "Inference", "infer"),
        ("ROBUST", "Robustness", "robust"), ("REPORT", "Reporting", "report"), ("DATA", "Data", "data")]
OTHER = ("OTHER", "Other", "other")
CATKEYS = {k for k, _, _ in CATS}
REPO_DOCS = "{{REPO_URL}}/blob/main/chat/amicus-audit/checklists"
ANATOMY_ID = "DID-EST-01"


def clean(s):
    """House style forbids em dashes on the site; the shipped checklist files are not touched."""
    return str(s).replace(" — ", ", ").replace("—", ", ")


def anatomy_card(head, checks, plain=None):
    """The anatomy card for ANATOMY_ID. `plain` is that check's plain-language sentence (explainers.json); when
    given it becomes the row after the requirement, for a reader who does not use the method."""
    c = next(x for x in checks if x["check_id"] == ANATOMY_ID)
    defs = head.get("_scope_definitions", {})
    # same order as the rendered checklist; impossible page values (a stray "p. -10") are dropped, not printed
    srcs = "".join(f"<li>{E(', '.join(x for x in (clean(r['short_cite']), clean(clean_pages(r['pages'])[0])) if x))}</li>"
                   for r in order_further_reading(c))
    silent = {"FLAG": "flag", "NA": "does not apply"}.get(c.get("verdict_when_silent"), str(c.get("verdict_when_silent")).lower())
    sev = (c.get("severity_if_flagged") or "").lower()
    scope_txt = "; ".join(f"<code>{E(n)}</code>: {E(clean(defs[n]))}" for n in c["scope"] if defs.get(n)) or E(", ".join(c["scope"]))
    rows = [
        ("The requirement", f'<span class="check-id">{E(c["check_id"])}</span><p>{E(clean(c["requirement_statement"]))}</p>'),
        *([("In plain words", f"<p>{E(clean(plain))}</p>")] if plain else []),
        ("When it applies", f"<p>{scope_txt}</p>"),
        ("What passes", f'<p>{E(clean(c["pass_condition"]))}</p>'),
        ("What is flagged", f'<p>{E(clean(c["flag_condition"]))}</p><p class="quiet small">Severity if flagged: {E(sev)}.</p>'),
        ("When the paper is silent", f"<p>The check is marked <em>{E(silent)}</em>.</p>"),
        ("Sources, with pages", f"<ul>{srcs}</ul>"),
    ]
    return '<div class="anat-card">' + "".join(
        f'<div class="anat-row"><div class="anat-label">{E(l)}</div><div>{v}</div></div>' for l, v in rows) + "</div>"


CATEGORY_BLURB = {
    "IDENT": "The assumptions the causal claim rests on.", "EST": "Whether the estimator recovers the target parameter.",
    "INFER": "Standard errors, tests, and their validity.", "ROBUST": "Sensitivity, diagnostics, and alternative specifications.",
    "REPORT": "What the paper must state for a reader to evaluate it.", "DATA": "Sample construction and measurement.",
}
CATNAME = {k: lab for k, lab, _ in CATS + [OTHER]}
DOI = re.compile(r"https?://doi\.org/\S+")


def linkify(text):
    """Escape, then turn a DOI URL into a link."""
    out, i = [], 0
    for m in DOI.finditer(text):
        url = m.group(0).rstrip(".,;)")
        out.append(E(text[i:m.start()]) + f'<a href="{E(url)}">{E(url)}</a>' + E(m.group(0)[len(url):]))
        i = m.end()
    out.append(E(text[i:]))
    return "".join(out)


def sub_nav(nav, foot):
    """The shared nav and footer, with page-relative links one directory up."""
    return (nav.replace('href="./', 'href="../').replace(' class="active"', "")
               .replace('<a href="../checklists.html">', '<a href="../checklists.html" class="active">'),
            foot.replace('href="./', 'href="../'))


def check_card(c, expl=None, doi_of=None, label=None):
    """One check as a card. `expl` is its explainer entry ({plain, why}); `doi_of(entry)` gives a DOI for a
    further-reading entry, or None; `label(trigger)` gives a scope trigger's display name (default: the id)."""
    expl, doi_of, label = expl or {}, doi_of or (lambda fr: None), label or (lambda t: t)
    cid = c["check_id"]
    sev = (c.get("severity_if_flagged") or "").upper().replace("MODERATE", "MEDIUM").lower()
    grade = (c.get("consensus_grade") or "").lower()
    n = c.get("n_contributing_sources")
    if grade:
        grade_txt = f"{grade} consensus" + (f", {n} source{'s' if n != 1 else ''}" if n else "")
    else:
        grade_txt = ""
    silent = {"FLAG": "flag", "PASS": "pass", "NA": "does not apply"}.get(c.get("verdict_when_silent"), str(c.get("verdict_when_silent") or "").lower())
    scope = c.get("scope") or ["all"]
    head = [f'<span class="check-id">{E(cid)}</span>', f'<span class="sev">severity if flagged: {E(sev)}</span>']
    if grade_txt:
        head.append(f"<span>{E(grade_txt)}</span>")
    head.append("<span>applies to: " + ", ".join(f"<code>{E(label(x))}</code>" for x in scope) + "</span>")
    head.append(f'<span class="silent">silent: {E(silent)}</span>')
    rows = [("In plain words", expl.get("plain")), ("Why it matters", expl.get("why")),
            ("Check", c.get("observable")), ("Pass", c.get("pass_condition")), ("Flag", c.get("flag_condition"))]
    th = c.get("threshold")
    if isinstance(th, dict):
        bits = [f"cutoff {th.get('cutoff', th.get('value', ''))}"]
        if th.get("provenance"):
            bits.append(f"provenance: {str(th['provenance']).replace('_', ' ')}")
        if th.get("border_band"):
            bits.append(f"borderline band: {th['border_band']}")
        rows.append(("Threshold", "; ".join(str(b) for b in bits)))
        if th.get("band_rule"):
            rows.append(("Inside the band", th["band_rule"]))
    elif th:
        rows.append(("Threshold", th))
    pa = c.get("prevalence_aggravator")
    if pa:
        rows.append(("Prevalence", pa if isinstance(pa, str) else pa.get("note", "")))
    if c.get("disputed"):
        rows.append(("Disputed", c.get("dispute_basis") or "a contributing source argues against this practice"))
    if c.get("author_guidance"):
        rows.append(("If flagged, the author can fix it by", c["author_guidance"]))
    detail = "".join(f'<div class="detail-row"><span class="detail-label">{E(l)}</span><span>{E(clean(v))}</span></div>' for l, v in rows if v)
    frs = []
    for fr in order_further_reading(c):  # most relevant source first, as in the shipped checklist
        if isinstance(fr, str):
            frs.append(f"<li>{linkify(clean(cite_with_doi(fr, doi_of(fr))))}</li>")
        else:
            pages = clean_pages(fr.get("pages") or "")[0]  # impossible page values are dropped, not printed
            pages = f", {clean(pages)}" if pages else ""
            tag = "" if fr.get("pagination", "printed") == "printed" else " (PDF pagination)"
            frs.append(f"<li>{linkify(clean(cite_with_doi(fr['cite'], doi_of(fr))))}{E(pages)}{E(tag)}</li>")
    fr_html = f'<div class="fr"><span class="detail-label">Further reading</span><ul>{"".join(frs)}</ul></div>' if frs else ""
    cls = "check" + (" disputed" if c.get("disputed") else "")
    return (f'<article class="{cls}" id="{E(cid)}"><div class="check-header">{"".join(head)}</div>'
            f'<p class="req"><a class="plain" href="#{E(cid)}">{E(clean(c.get("requirement_statement") or c.get("claim") or ""))}</a></p>'
            f'<div class="detail-grid">{detail}</div>{fr_html}</article>')


PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}: AMICUS checklist</title>
<meta name="description" content="{desc}">
<script src="../theme.js"></script>
<link rel="stylesheet" href="../fonts/newsreader.css">
<link rel="stylesheet" href="../style.css">
<link rel="icon" href="../favicon.svg" type="image/svg+xml">
</head>
<body>

{nav}

<header class="pagehead wrap narrow">
  <p class="crumb"><a href="../checklists.html">The checklists</a></p>
  <h1>{title}</h1>
  <p class="lede">{lede}</p>
  <nav class="toc" aria-label="Categories">{toc}</nav>
</header>

<main>
<section class="wrap narrow howto">
  <h2>How to read a verdict</h2>
  <p><em>Pass</em> and <em>flag</em> are decided by the stated conditions. A check that is out of scope for the paper is marked <em>does not apply</em>; that is never a verdict on what the paper said. When a check applies and the paper says nothing, the verdict is the one given under <em>silent</em>.</p>
  <p>A verdict covers only the text the audit could see. A flag on material the paper says is in an appendix or replication package means "not shown here", not "not done", and such flags carry that caveat in the report.{thresholds}</p>
</section>
{scope}
{cats}
{sources}
<section class="wrap narrow">
  <p><a href="{md}">The same checklist as Markdown</a>, which is what the chatbot and coding-agent routes read.</p>
</section>
</main>

{foot}
</body>
</html>
"""


def build_checklist_pages(mods, nav, foot):
    outdir = SITE / "checklists"
    outdir.mkdir(exist_ok=True)
    nav, foot = sub_nav(nav, foot)
    written = []
    for mod, run, head, cs in mods:
        name = NAMES.get(mod, mod)
        defs = head.get("_scope_definitions", {})
        universal = mod == UM.MODULE
        run_dir = ROOT / "runs/skill_generation" / run
        expl = explainer_text.load(run_dir)
        doi_of = lambda fr: source_doi(run_dir, fr["source_id"]) if isinstance(fr, dict) else None  # noqa: E731
        label = UM.label if universal else None  # display names for the universal list's internal-looking trigger ids
        sources = {}
        for c in cs:
            for fr in c.get("further_reading") or []:
                if isinstance(fr, dict):
                    sources[fr["source_id"]] = cite_with_doi(fr["cite"], doi_of(fr))
                else:
                    sources[fr] = cite_with_doi(fr, doi_of(fr))
        by_cat = {}
        for c in cs:
            k = c["check_id"].split("-")[1]
            by_cat.setdefault(k if k in CATKEYS else "OTHER", []).append(c)
        order = [k for k, _, _ in CATS + [OTHER] if k in by_cat]
        if universal:
            lede = (f"{len(cs)} checks that apply to every paper, whatever its research design. The {len(sources)} chapters and articles "
                    "listed at the end are cited as further reading for them; they come from works on at least two graduate syllabi that state requirements for any research design. "
                    "The checks were built from them by the same procedure as the method checklists. Each is supported by at least "
                    "three works, and the list carries no consensus grade. Each check says when it applies, what passes, what is "
                    "flagged, and where to read more.")
        else:
            lede = (f"{len(cs)} checks, each resting on claims from the methods literature. The {len(sources)} sources listed at the end are the ones cited as further reading. "
                    "Each check says when it applies, what passes, what is flagged, and where to read more.")
        toc = "".join(f'<a href="#{E(k.lower())}">{E(CATNAME[k])}<span class="toc-count"> {len(by_cat[k])}</span></a>' for k in order)
        scope_html = ""
        if defs:
            scope_html = ('<section class="wrap narrow" id="scope"><h2>When a check applies</h2>'
                          "<p>A check applies only when its scope trigger fires. Triggers key on the paper's own explicit stance and default to out of scope when the paper is silent.</p>"
                          '<dl class="scope-dl">' + "".join(f"<dt><code>{E((label or str)(k))}</code></dt><dd>{E(clean(v))}</dd>" for k, v in defs.items()) + "</dl></section>")
        cats_html = ""
        for k in order:
            blurb = CATEGORY_BLURB.get(k, "")
            cats_html += (f'<section class="wrap narrow cat" id="{E(k.lower())}"><h2>{E(CATNAME[k])}<span class="mod-count">{len(by_cat[k])}</span></h2>'
                          + (f'<p class="method-desc">{E(blurb)}</p>' if blurb else "")
                          + "".join(check_card(c, expl.get(c["check_id"]), doi_of, label) for c in sorted(by_cat[k], key=lambda x: x["check_id"])) + "</section>")
        src_html = ""
        if sources:
            src_html = ('<section class="wrap narrow" id="sources"><h2>Sources</h2>'
                        f"<p>These {len(sources)} {'chapters and articles are' if universal else 'sources are'} the ones cited in the further-reading lines above. {'' if universal else 'A check’s consensus grade counts every source with a claim assigned to it, so it can count more sources than are listed here. '}Page references point to the passage a check rests on; they are printed-journal pages unless marked as PDF pagination.</p>"
                        '<ul class="sources">' + "".join(f"<li>{linkify(clean(v))}</li>" for _, v in sorted(sources.items(), key=lambda kv: kv[1])) + "</ul></section>")
        page = PAGE.format(
            title=E(name), lede=E(lede), toc=toc, nav=nav, foot=foot, scope=scope_html, cats=cats_html, sources=src_html,
            md=f"{REPO_DOCS}/{mod.upper()}_CHECKLIST.md",
            desc=E(f"The AMICUS {name.lower()} checklist: {len(cs)} checks, each with its scope, pass and flag conditions, and sources."),
            thresholds=" Thresholds are rules of thumb unless marked otherwise, and near-threshold values are reported as borderline rather than rounded to a verdict.")
        out = outdir / f"{mod}.html"
        old = out.read_text() if out.exists() else None
        if old != page:
            out.write_text(page)
        written.append(f"{mod}{'' if old == page else '*'}")
    print(f"checklist pages in site/checklists/: {' '.join(written)} (* = changed)")


def build_checklists():
    mods = R.load(INST) + [UM.load_module()]  # 14 designs plus the universal checklist (no MANIFEST)
    total = sum(len(m[3]) for m in mods)
    did = next(m for m in mods if m[0] == "did")
    ndesign = len(mods) - 1
    cards, has_other = [], False
    for mod, run, _, cs in mods:
        counts = {}
        for c in cs:
            k = c["check_id"].split("-")[1]
            k = k if k in CATKEYS else "OTHER"
            has_other = has_other or k == "OTHER"
            counts[k] = counts.get(k, 0) + 1
        present = [x for x in CATS + [OTHER] if counts.get(x[0])]
        segs = "".join(f'<span class="cat-{cls}" style="--w:{counts[k]}" title="{E(lab)}: {counts[k]}"></span>'
                       for k, lab, cls in present)
        desc = "; ".join(f"{lab} {counts[k]}" for k, lab, _ in present)
        mp = ROOT / "runs/skill_generation" / run / "MANIFEST.json"
        mf = json.loads(mp.read_text()) if mp.is_file() else {}
        agree = ((mf.get("promotion") or {}).get("decidability") or {}).get("diagnostic_core_stability_pct")
        diag = (mf.get("decidability") or {}).get("diagnostic") or {}  # topline as in docs/SKILL_GENERATION.md section 6.4
        stable = (diag.get("core_stability") or "").split(" = ")[0]
        meta = f'<div class="mod-meta">{E(desc)}</div>'
        if agree is not None and diag.get("papers") and diag.get("codings_per_paper") and stable:
            n, k = diag["papers"], diag["codings_per_paper"]
            meta += (f'<div class="mod-meta">Agreement across {k} codings: {n} paper{"s" if n != 1 else ""} × {k} codings, '
                     f'{stable} ({agree:g}%)</div>')
        cards.append(
            f'<div class="mod-card"><h3>{E(NAMES.get(mod, mod))}</h3>'
            f'<div class="mod-n"><b>{len(cs)}</b>checks</div>'
            f'<div class="bar" role="img" aria-label="Checks by category: {E(desc)}">{segs}</div>{meta}'
            f'<a href="./checklists/{mod}.html">Full checklist</a></div>')
    legend = "".join(f'<li><i class="cat-{cls}"></i>{E(lab)}</li>' for _, lab, cls in CATS + ([OTHER] if has_other else []))
    anat = anatomy_card(did[2], did[3], explainer_text.load(ROOT / "runs/skill_generation" / did[1]).get(ANATOMY_ID, {}).get("plain"))
    nav, foot = nav_footer()
    build_checklist_pages(mods, nav, foot)
    summary = (f"The system has checklists for {ndesign} methods plus a universal checklist, with {total} checks in total. Each check is one thing that "
               "at least some of the methods literature says that papers should do. Checks include a rule for when it applies and what counts as meeting it.")
    cards_html = "\n".join(cards)
    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AMICUS checklists</title>
<meta name="description" content="An overview of the AMICUS checklists: {total} checks across {ndesign} methods and a universal checklist, how a check is built, and a link to each full checklist.">
<script src="./theme.js"></script>
<link rel="stylesheet" href="./fonts/newsreader.css">
<link rel="stylesheet" href="./style.css">
<link rel="icon" href="./favicon.svg" type="image/svg+xml">
</head>
<body>

{nav}

<header class="pagehead wrap narrow">
  <h1>The checklists</h1>
  <p class="lede">{summary}</p>
</header>

<main>
<section class="wrap narrow">
  <h2>Anatomy of a check</h2>
  <p>Here is one example, from the difference-in-differences checklist.</p>
  {anat}
</section>

<section class="wrap">
  <h2>The methods</h2>
  <p>Each bar shows how a method's checks divide by category.</p>
  <ul class="legend" aria-label="Categories">{legend}</ul>
  <div class="mod-grid">
{cards_html}
  </div>
</section>

<section class="wrap narrow">
  <p>Each full checklist is also in <a href="{{{{REPO_URL}}}}">the repository</a> as Markdown, which is what the chatbot and coding-agent routes read.</p>
</section>
</main>

{foot}
</body>
</html>
'''
    out = SITE / "checklists.html"
    old = out.read_text() if out.exists() else None
    if old != page:
        out.write_text(page)
    print(f"{'wrote' if old != page else 'unchanged'} {out.relative_to(ROOT)} ({len(page.encode())} bytes; "
          f"{total} checks, {ndesign} methods + universal)")


class Collect(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.ids, self.links = set(), []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            self.ids.add(a["id"])
        if tag == "a" and a.get("name"):
            self.ids.add(a["name"])
        for k in ("href", "src"):
            if a.get(k) is not None and tag in ("a", "link", "script", "img"):
                self.links.append((tag, a[k]))


def check():
    pages = sorted(SITE.glob("*.html")) + sorted(SITE.glob("checklists/*.html"))
    if not pages:
        print("no pages in site/")
        return 1
    info = {}
    for p in pages:
        c = Collect()
        c.feed(p.read_text())
        info[str(p.relative_to(SITE))] = c
    bad = []
    for name, c in info.items():
        here = (SITE / name).parent
        for tag, href in c.links:
            if TOKEN.match(href) or re.match(r"[a-z][a-z0-9+.-]*:", href, re.I):
                if href.startswith(("http://", "https://")) and tag != "a":
                    bad.append(f"{name}: external resource {href}")
                continue  # token-prefixed or absolute URL: resolved at deploy time or external
            path, _, frag = href.partition("#")
            target = name if not path else str((here / path).resolve().relative_to(SITE))
            if path and not (here / path).resolve().is_file():
                bad.append(f"{name}: {href} (file missing)")
                continue
            if frag:
                if target.endswith(".html") and target in info:
                    if frag not in info[target].ids:
                        bad.append(f"{name}: {href} (anchor missing)")
                else:
                    bad.append(f"{name}: {href} (cannot verify anchor)")
    navs = {n: re.search(r'<nav class="topnav">.*?</nav>', (SITE / n).read_text(), re.S).group(0).replace(' class="active"', "").replace('href="../', 'href="./')
            for n in info}
    if len(set(navs.values())) != 1:
        bad.append("nav differs between pages: " + ", ".join(sorted(navs)))
    if not (SITE / "CNAME").is_file():
        bad.append("site/CNAME missing")
    nlinks = sum(len(c.links) for c in info.values())
    nanch = sum(1 for c in info.values() for _, h in c.links if "#" in h and not TOKEN.match(h) and not h.startswith("http"))
    if bad:
        print("\n".join(bad))
        print(f"FAIL: {len(bad)} problem(s) in {len(pages)} pages")
        return 1
    print(f"OK: {len(pages)} pages, {nlinks} links, {nanch} internal anchor links, all resolve")
    return 0


def main():
    if "--check" in sys.argv[1:]:
        sys.exit(check())
    if len(sys.argv) > 1:
        sys.exit(__doc__)
    build_checklists()
    copy_entry_point()


def copy_entry_point():
    """Serve the chatbot entry point from the site, so users can type amicus.ink/AMICUS.md."""
    src, dst = ROOT / "public" / "AMICUS.md", SITE / "AMICUS.md"
    text = src.read_text()
    old = dst.read_text() if dst.exists() else None
    if old != text:
        dst.write_text(text)
    print(f"{'wrote' if old != text else 'unchanged'} {dst.relative_to(ROOT)} (from public/AMICUS.md)")


if __name__ == "__main__":
    main()
