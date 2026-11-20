"""DOI links, page validation and source order for further-reading entries. Stdlib only; shared by
render_md.py (the shipped checklists), universal_module.py (the universal checklist), build_site.py and the
paper-only runner (paper_only_audit.read_more). A DOI is only ever taken from the entry itself, from
source_dois.json (written by check_dois.py --write-map from each run's config.json, which the public
export does not ship), or from the run's own config.json; none is ever guessed."""
import json
import re
from collections import Counter
from pathlib import Path

SOURCE_DOI_MAP = Path(__file__).resolve().parent / 'source_dois.json'  # {"<run>/<source_id>": "<doi>"}

_DOI_URL = re.compile(r'https?://(?:dx\.)?doi\.org/(10\.\S+)', re.I)
_BARE_DOI = re.compile(r'\s*\bDOI:?\s*(10\.\d{4,9}/\S+?)\.?\s*$', re.I)
_PAGE_ONE = re.compile(r'^(\d+)$|^([ivxlcdm]+)$', re.I)
_PAGE_RANGE = re.compile(r'^(\d+)\s*[–-]\s*(\d+)$')


def source_dois(cfg):
    """source_id -> bare DOI from a run's config.json (already parsed). A source with no usable
    DOI is simply absent."""
    out = {}
    for s in cfg.get('sources', []):
        d = (s.get('doi') or '').strip()
        d = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', d, flags=re.I)
        if d.startswith('10.'):
            out[s['source_id']] = d
    return out


def run_dois(run_dir):
    """source_id -> DOI for the run at `run_dir`, or {} when it has no config.json (the public
    export carries none)."""
    p = Path(run_dir) / 'config.json'
    if not p.is_file():
        return {}
    with open(p, encoding='utf-8') as f:
        return source_dois(json.load(f))


def mapped_dois():
    """The committed {"<run>/<source_id>": doi} map, or {} when absent."""
    if not SOURCE_DOI_MAP.is_file():
        return {}
    with open(SOURCE_DOI_MAP, encoding='utf-8') as f:
        return json.load(f)


def source_doi(run_dir, source_id):
    """DOI for a design-module source: the committed map first, then the run's config.json, else None."""
    return mapped_dois().get(f'{Path(run_dir).name}/{source_id}') or run_dois(run_dir).get(source_id)


def order_further_reading(check):
    """The check's further_reading, most relevant source first: by how many of the check's evidence rows
    come from that source (more first), then by its highest anchor_score (higher first), then the
    existing order (the sort is stable). A list with plain strings (older hand-drafted checklists) keeps its order.
    Returns a new list; the check is not changed."""
    fr = list(check.get('further_reading') or [])
    if any(isinstance(x, str) for x in fr):
        return fr
    rows = check.get('evidence') or []
    n = Counter(e.get('source_id') for e in rows)
    best = {}
    for e in rows:
        best[e.get('source_id')] = max(best.get(e.get('source_id'), 0), e.get('anchor_score') or 0)
    return sorted(fr, key=lambda f: (-n[f.get('source_id')], -best.get(f.get('source_id'), 0)))


def doi_in_cite(cite):
    """The DOI already written in a cite, as a link or as a bare 'DOI 10....'; else None."""
    m = _DOI_URL.search(cite)
    if m:
        return m.group(1).rstrip('.,;')
    m = _BARE_DOI.search(cite)
    return m.group(1) if m else None


def cite_with_doi(cite, doi=None):
    """The cite with a https://doi.org/<doi> link: keep one already there; else turn a bare
    'DOI 10....' into the URL form; else append `doi` (from config.json) when one is known."""
    if _DOI_URL.search(cite):
        return cite
    m = _BARE_DOI.search(cite)
    if m:
        return cite[:m.start()] + ' https://doi.org/' + m.group(1)
    if doi:
        return f'{cite.rstrip()} https://doi.org/{doi}'
    return cite


def clean_pages(pages):
    """(pages, dropped): a page value with every impossible token removed. Impossible means
    negative, zero, a reversed range, or anything that is not a number, a range or a roman
    folio. A value with nothing impossible is returned untouched."""
    if not pages:
        return pages, []
    body = re.sub(r'^pp?\.\s*', '', pages.strip())
    keep, dropped = [], []
    for tok in (t.strip() for t in body.split(',')):
        m = _PAGE_RANGE.match(tok)
        if m:
            ok = 0 < int(m.group(1)) <= int(m.group(2))
        else:
            m = _PAGE_ONE.match(tok)
            ok = bool(m) and (m.group(2) is not None or int(m.group(1)) > 0)
        (keep if ok else dropped).append(tok)
    if not dropped:
        return pages, []
    if not keep:
        return '', dropped
    one = len(keep) == 1 and _PAGE_RANGE.match(keep[0]) is None
    return ('p. ' if one else 'pp. ') + ', '.join(keep), dropped


_STR_HEAD = re.compile(r'^(?P<authors>.+?)\. \((?P<year>\d{4})\)\.')
_STR_CHAPTERS = re.compile(r', (?P<where>chapters? [^,]+(?:, [^,]+)*?)\.$')


def short_from_string(s):
    """(short_cite, where) for a plain-string entry as older hand-drafted checklists write them:
    'A, B, & C. (2011). Title. Venue, chapters 2 and 4.' -> ('A et al. (2011)', 'chapters 2 and 4').
    One or two authors are named; three or more give the first and 'et al.'. `where` is the
    chapter pointer when the string has one, else ''."""
    m = _STR_HEAD.match(s)
    if not m:
        return s, ''
    surname = [n.split()[-1] for n in re.split(r',\s+&\s+|,\s+|\s+&\s+', m['authors'])]
    who = surname[0] if len(surname) == 1 else f'{surname[0]} & {surname[1]}' if len(surname) == 2 \
        else f'{surname[0]} et al.'
    c = _STR_CHAPTERS.search(s)
    return f"{who} ({m['year']})", c['where'] if c else ''


def read_more_line(entry, doi=None):
    """One line for a further-reading entry: '<short_cite>, <pages>, https://doi.org/<doi>', each
    part present only when known. `entry` is a dict (every shipped checklist) or a plain string (older
    hand-drafted checklists). A DOI written in the cite wins
    over `doi`. Impossible page values are dropped."""
    if isinstance(entry, str):
        short, where = short_from_string(entry)
        parts = [short, where]
    else:
        short = entry.get('short_cite') or entry.get('cite', '')
        parts = [short, clean_pages(entry.get('pages') or '')[0]]
        doi = doi_in_cite(entry.get('cite', '')) or doi
    if doi:
        parts.append(f'https://doi.org/{doi}')
    return ', '.join(p for p in parts if p)
