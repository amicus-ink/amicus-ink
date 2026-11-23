#!/usr/bin/env python3
"""Render every shipping checklist (each instrument in SHIPPING_BY_INSTRUMENT) as one HTML page.

Each check card shows severity, consensus grade (with the number of contributing sources),
the disputed flag with its basis, scope, silent-verdict rule, and the coding detail.
Usage: render_checklists_html.py OUT.html
"""
import html, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_only_audit import SHIPPING_BY_INSTRUMENT, HISTORICAL_INSTRUMENTS, ROSTER_ALL as MODDESC  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
E = html.escape
CATS = [("IDENT", "Identification", "#6366f1"), ("EST", "Estimation", "#0ea5e9"), ("INFER", "Inference", "#8b5cf6"), ("ROBUST", "Robustness", "#f59e0b"), ("REPORT", "Reporting", "#10b981"), ("DATA", "Data", "#ec4899")]
SEVCOL = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#6b7280"}
GRADECOL = {"high": "#059669", "medium": "#2563eb", "low": "#78716c"}


def load(inst):
    mods = []
    for mod, run in SHIPPING_BY_INSTRUMENT[inst].items():
        d = json.load(open(ROOT / "runs/skill_generation" / run / "checklists/verified.anchored.json"))
        head = d[0] if not d[0].get("check_id") else {}
        checks = [c for c in d if c.get("check_id")]
        mods.append((mod, run, head, checks))
    return mods


def card(c):
    sev = (c.get("severity_if_flagged") or "MEDIUM").upper().replace("MODERATE", "MEDIUM")
    g = c.get("consensus_grade") or "low"; k = c.get("n_contributing_sources") or 0
    scope = ", ".join(c.get("scope") or ["all"])
    silent = c.get("verdict_when_silent")
    disp = c.get("disputed")
    cls = f"check g-{g}" + (" disputed" if disp else "")
    h = [f'<div class="{cls}" data-id="{E(c["check_id"])}">', '  <div class="check-header">',
         f'    <span class="check-id">{E(c["check_id"])}</span>',
         f'    <span class="sev" style="background:{SEVCOL.get(sev, "#6b7280")}">{E(sev)}</span>',
         f'    <span class="grade" style="color:{GRADECOL[g]};border-color:{GRADECOL[g]}">{g} consensus · {k} source{"s" if k != 1 else ""}</span>',
         f'    <span class="scope">{E(scope)}</span>']
    if silent == "FLAG": h.append('    <span class="silent">if silent: FLAG</span>')
    if disp: h.append('    <span class="disp">disputed</span>')
    h += ['  </div>', f'  <p class="req">{E(c.get("requirement_statement") or "")}</p>']
    if disp and c.get("dispute_basis"): h.append(f'  <p class="basis"><strong>Dispute basis:</strong> {E(c["dispute_basis"])}</p>')
    h += ['  <details>', '    <summary>Coding detail</summary>', '    <div class="detail-grid">',
          f'      <div><strong>Observable:</strong> {E(c.get("observable") or "")}</div>',
          f'      <div class="pass"><strong>Pass:</strong> {E(c.get("pass_condition") or "")}</div>',
          f'      <div class="flag"><strong>Flag:</strong> {E(c.get("flag_condition") or "")}</div>']
    if c.get("threshold"): h.append(f'      <div><strong>Threshold:</strong> {E(json.dumps(c["threshold"]) if not isinstance(c["threshold"], str) else c["threshold"])}</div>')
    srcs = c.get("contributing_sources") or []
    if srcs: h.append(f'      <div><strong>Contributing sources:</strong> {E(", ".join(str(s) for s in srcs))}</div>')
    h += ['    </div>', '  </details>', '</div>']
    return "\n".join(h)


def section(inst, mod, head, checks):
    n = len(checks); gr = {g: sum(1 for c in checks if (c.get("consensus_grade") or "low") == g) for g in ("high", "medium", "low")}
    nd = sum(1 for c in checks if c.get("disputed"))
    s = [f'<section id="{inst}-{mod}" class="module" data-inst="{inst}">', f'  <h2>{E(mod)} <span class="mod-count">{n} checks · {gr["high"]} high / {gr["medium"]} medium / {gr["low"]} low consensus' + (f' · {nd} disputed' if nd else '') + '</span></h2>',
         f'  <p class="method-desc">{E(MODDESC.get(mod, mod))}</p>']
    defs = head.get("_scope_definitions") or {}
    if defs: s.append('  <details class="scope-defs"><summary>Scope definitions</summary><dl>' + "".join(f'<dt><code>{E(k)}</code></dt><dd>{E(v)}</dd>' for k, v in defs.items()) + '</dl></details>')
    for cat, name, col in CATS:
        cs = [c for c in checks if c.get("category") == cat]
        if not cs: continue
        s.append(f'  <h3 style="color:{col}">{name} ({len(cs)})</h3>')
        s += [card(c) for c in cs]
    s.append('</section>')
    return "\n".join(s)


def render(out):
    insts = {i: load(i) for i in SHIPPING_BY_INSTRUMENT if i not in HISTORICAL_INSTRUMENTS}
    first = next(iter(insts))
    nmods = {i: len(insts[i]) for i in insts}
    tot = {i: sum(len(m[3]) for m in insts[i]) for i in insts}
    grades = {i: {g: sum(1 for m in insts[i] for c in m[3] if (c.get("consensus_grade") or "low") == g) for g in ("high", "medium", "low")} for i in insts}
    disputed = {i: sum(1 for m in insts[i] for c in m[3] if c.get("disputed")) for i in insts}
    tocs = {i: "".join(f'<a href="#{i}-{m}">{E(m)} <span class="toc-count">{len(cs)}</span></a>' for m, _, _, cs in insts[i]) for i in insts}
    body = "\n".join(section(i, m, h, cs) for i in insts for m, _, h, cs in insts[i])
    tabs = "\n".join(f'  <button role="tab" id="tab-{i}" aria-selected="{str(i == first).lower()}" data-inst="{i}">{i} instrument · {tot[i]} checks</button>' for i in insts)
    navs = "\n".join(f'<nav class="toc{"" if i == first else " hidden"}" id="toc-{i}">{tocs[i]}</nav>' for i in insts)
    page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Amicus Checklists</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root {{
  --bg: #fafaf9; --fg: #1c1917; --muted: #78716c; --border: #d6d3d1;
  --card-bg: #ffffff; --card-shadow: 0 1px 2px rgba(0,0,0,0.06);
  --green: #059669; --red: #dc2626; --blue: #2563eb; --amber: #b45309; --amber-bg: #fffbeb;
  --pass-bg: #ecfdf5; --flag-bg: #fef2f2; --detail-bg: #f5f5f4; --low-bg: #fafaf9;
}}
@media(prefers-color-scheme:dark) {{ :root:not([data-theme="light"]) {{
  --bg: #1c1917; --fg: #e7e5e4; --muted: #a8a29e; --border: #44403c;
  --card-bg: #292524; --card-shadow: 0 1px 2px rgba(0,0,0,0.3);
  --green: #34d399; --red: #f87171; --blue: #60a5fa; --amber: #fbbf24; --amber-bg: #3a2e12;
  --pass-bg: #052e16; --flag-bg: #450a0a; --detail-bg: #292524; --low-bg: #221f1c;
}} }}
:root[data-theme="dark"] {{
  --bg: #1c1917; --fg: #e7e5e4; --muted: #a8a29e; --border: #44403c;
  --card-bg: #292524; --card-shadow: 0 1px 2px rgba(0,0,0,0.3);
  --green: #34d399; --red: #f87171; --blue: #60a5fa; --amber: #fbbf24; --amber-bg: #3a2e12;
  --pass-bg: #052e16; --flag-bg: #450a0a; --detail-bg: #292524; --low-bg: #221f1c;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'IBM Plex Sans',system-ui,sans-serif; background:var(--bg); color:var(--fg); padding:env(safe-area-inset-top,0) 16px env(safe-area-inset-bottom,0); line-height:1.5; max-width:900px; margin:0 auto; }}
h1 {{ font-size:1.5rem; font-weight:600; margin:2rem 0 0.25rem; }}
.subtitle {{ color:var(--muted); font-size:0.9rem; margin-bottom:1rem; }}
.legend {{ font-size:0.82rem; color:var(--muted); margin-bottom:1rem; max-width:72ch; }}
.legend b {{ color:var(--fg); font-weight:600; }}
.tabs {{ display:flex; gap:6px; margin-bottom:1rem; }}
.tabs button {{ font:inherit; font-size:0.85rem; padding:6px 14px; border:1px solid var(--border); background:var(--card-bg); color:var(--fg); border-radius:6px; cursor:pointer; }}
.tabs button[aria-selected="true"] {{ border-color:var(--blue); color:var(--blue); font-weight:600; }}
.tabs button:focus-visible {{ outline:2px solid var(--blue); outline-offset:2px; }}
.filters {{ display:flex; flex-wrap:wrap; gap:12px; font-size:0.82rem; margin-bottom:1rem; align-items:center; }}
.filters label {{ display:flex; gap:5px; align-items:center; cursor:pointer; }}
.toc {{ display:flex; flex-wrap:wrap; gap:6px; margin-bottom:2rem; padding-bottom:1rem; border-bottom:1px solid var(--border); }}
.toc a {{ font-family:'IBM Plex Mono',monospace; font-size:0.8rem; padding:4px 10px; background:var(--card-bg); border:1px solid var(--border); border-radius:4px; text-decoration:none; color:var(--fg); display:flex; align-items:center; gap:6px; }}
.toc a:hover {{ border-color:var(--blue); }}
.toc-count {{ color:var(--muted); font-size:0.7rem; }}
.search {{ width:100%; padding:8px 12px; font-size:0.9rem; font-family:inherit; border:1px solid var(--border); border-radius:6px; background:var(--card-bg); color:var(--fg); margin-bottom:1rem; }}
section {{ margin-bottom:3rem; }}
h2 {{ font-size:1.2rem; font-weight:600; border-bottom:2px solid var(--border); padding-bottom:0.3rem; margin-bottom:0.5rem; }}
.mod-count {{ font-weight:400; color:var(--muted); font-size:0.8rem; }}
.method-desc {{ color:var(--muted); font-size:0.85rem; font-style:italic; margin-bottom:0.75rem; }}
h3 {{ margin:1.5em 0 0.5em; font-size:0.85rem; text-transform:uppercase; letter-spacing:0.08em; }}
.scope-defs {{ margin-bottom:1rem; font-size:0.82rem; }}
.scope-defs summary {{ cursor:pointer; color:var(--muted); font-size:0.8rem; }}
.scope-defs dl {{ margin:0.5rem 0 0 1rem; }}
.scope-defs dt {{ font-weight:600; margin-top:0.5rem; }}
.scope-defs dd {{ color:var(--muted); margin-left:0; }}
.check {{ background:var(--card-bg); border:1px solid var(--border); border-radius:6px; padding:12px 14px; margin-bottom:8px; box-shadow:var(--card-shadow); }}
.check.g-low {{ background:var(--low-bg); border-style:dashed; }}
.check.g-low .req {{ color:var(--muted); }}
.check.disputed {{ border-left:3px solid var(--amber); }}
.check-header {{ display:flex; align-items:center; gap:8px; flex-wrap:wrap; margin-bottom:6px; }}
.check-id {{ font-family:'IBM Plex Mono',monospace; font-size:0.8rem; font-weight:600; }}
.sev {{ font-size:0.65rem; font-weight:600; color:white; padding:1px 6px; border-radius:3px; text-transform:uppercase; letter-spacing:0.04em; }}
.grade {{ font-size:0.68rem; font-weight:600; padding:0 6px; border:1px solid; border-radius:10px; letter-spacing:0.02em; }}
.scope {{ font-size:0.72rem; color:var(--muted); font-family:'IBM Plex Mono',monospace; }}
.silent {{ font-size:0.7rem; color:var(--red); font-family:'IBM Plex Mono',monospace; }}
.disp {{ font-size:0.68rem; font-weight:600; color:var(--amber); background:var(--amber-bg); padding:0 6px; border-radius:10px; text-transform:uppercase; letter-spacing:0.04em; }}
.req {{ font-size:0.88rem; line-height:1.5; }}
.basis {{ font-size:0.8rem; color:var(--amber); margin-top:6px; }}
details {{ margin-top:8px; }}
details summary {{ font-size:0.78rem; color:var(--muted); cursor:pointer; }}
.detail-grid {{ display:grid; gap:6px; margin-top:8px; font-size:0.82rem; padding:10px; background:var(--detail-bg); border-radius:4px; }}
.detail-grid .pass {{ color:var(--green); }}
.detail-grid .flag {{ color:var(--red); }}
.detail-grid strong {{ font-weight:600; }}
.hidden {{ display:none !important; }}
</style>
</head>
<body>
<h1>Amicus Method Checklists</h1>
<p class="subtitle" id="subtitle"></p>
<p class="legend">Every check carries a <b>severity</b> (HIGH / MEDIUM / LOW: how much a failure matters) and, since 2026-09-24, a <b>consensus grade</b> read off the number of the module's sources whose mined claims were attached to it: <b>high</b> = three or more sources (two in a corpus of six or fewer), <b>medium</b> = two, <b>low</b> = a single source. Low-consensus checks stay on the list as advice (dashed cards) but are left out of the main empirical analysis. A <b>disputed</b> check (amber edge) is one where an attached claim argues the practice is unnecessary or counterproductive; the basis is printed on the card so you can disagree with the classifier. "If silent: FLAG" marks checks where saying nothing counts as a failure.</p>
<div class="tabs{"" if len(insts) > 1 else " hidden"}" role="tablist">
{tabs}
</div>
<div class="filters">
  <label><input type="checkbox" id="f-high" checked> high</label>
  <label><input type="checkbox" id="f-medium" checked> medium</label>
  <label><input type="checkbox" id="f-low" checked> low consensus</label>
  <label><input type="checkbox" id="f-disp"> disputed only</label>
</div>
<input type="text" class="search" id="search" placeholder="Search checks…" autocomplete="off">
{navs}
{body}
<script>
(function() {{
  var META = {json.dumps({i: dict(total=tot[i], modules=nmods[i], **grades[i], disputed=disputed[i]) for i in insts})};
  var inst = '{first}';
  function sub() {{
    var m = META[inst];
    document.getElementById('subtitle').textContent = m.total + ' checks across ' + m.modules + ' modules · ' + inst + ' instrument (sources through ' + inst + ') · ' + m.high + ' high / ' + m.medium + ' medium / ' + m.low + ' low consensus · ' + m.disputed + ' disputed';
  }}
  function apply() {{
    var q = document.getElementById('search').value.toLowerCase();
    var show = {{ high: document.getElementById('f-high').checked, medium: document.getElementById('f-medium').checked, low: document.getElementById('f-low').checked }};
    var dispOnly = document.getElementById('f-disp').checked;
    document.querySelectorAll('section.module').forEach(function(sec) {{
      if (sec.dataset.inst !== inst) {{ sec.classList.add('hidden'); return; }}
      var any = false;
      sec.querySelectorAll('.check').forEach(function(c) {{
        var g = c.classList.contains('g-high') ? 'high' : c.classList.contains('g-medium') ? 'medium' : 'low';
        var ok = show[g] && (!dispOnly || c.classList.contains('disputed')) && (!q || c.textContent.toLowerCase().indexOf(q) >= 0);
        c.classList.toggle('hidden', !ok); if (ok) any = true;
      }});
      sec.classList.toggle('hidden', !any);
    }});
    Object.keys(META).forEach(function(i) {{ document.getElementById('toc-' + i).classList.toggle('hidden', inst !== i); }});
  }}
  document.querySelectorAll('.tabs button').forEach(function(b) {{
    b.addEventListener('click', function() {{
      inst = b.dataset.inst;
      document.querySelectorAll('.tabs button').forEach(function(x) {{ x.setAttribute('aria-selected', x === b ? 'true' : 'false'); }});
      sub(); apply();
    }});
  }});
  ['search', 'f-high', 'f-medium', 'f-low', 'f-disp'].forEach(function(id) {{ document.getElementById(id).addEventListener('input', apply); }});
  try {{ var h = /^#(\\d{{4}})-/.exec(location.hash); if (h && META[h[1]] && h[1] !== inst) {{ document.getElementById('tab-' + h[1]).click(); }} }} catch (e) {{}}
  sub(); apply();
}})();
</script>
</body>
</html>
'''
    Path(out).write_text(page)
    print("wrote", out, Path(out).stat().st_size, tot, grades, disputed)


if __name__ == "__main__":
    render(sys.argv[1] if len(sys.argv) > 1 else "amicus_checklists.html")
