#!/usr/bin/env python3
"""Check public/AMICUS.md: checklist links, the importance-prompt link and the report-guide link resolve, routing table matches SHIPPING plus universal,
model-facing length, no em dashes."""
import re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from paper_only_audit import SHIPPING as _DESIGNS  # noqa: E402
import universal_module as UM  # noqa: E402

SHIPPING = {**_DESIGNS, UM.MODULE: UM.RUN}  # 14 design modules plus the universal checklist

# AMICUS.md has no length limit. (The 8,000-character cap is ChatGPT's for pasted custom-GPT
# instructions; it applies to chat/portable, not to this file.)
MARK = "<!-- end of model-facing instructions -->"
# public/AMICUS.md in the internal repo; AMICUS.md at the root of the public export.
text = next(p for p in (ROOT / "public" / "AMICUS.md", ROOT / "AMICUS.md") if p.exists()).read_text()
ok = True

head = text.split(MARK)[0]
print(f"model-facing characters: {len(head)}")
if MARK not in text:
    ok = False; print("FAIL: end-of-instructions marker missing")

# {{RAW_URL}} in the source; a raw.githubusercontent.com/<owner>/<repo>/<ref> URL once exported.
links = re.findall(r"(?:\{\{RAW_URL\}\}|https://raw\.githubusercontent\.com/[^/\s]+/[^/\s]+/[^/\s]+)/(\S+?_CHECKLIST\.md)", head)
missing = [l for l in links if not (ROOT / l).is_file()]
print(f"checklist links: {len(links)}; missing files: {missing or 'none'}")
ok &= not missing

imp = re.findall(r"(?:\{\{RAW_URL\}\}|https://raw\.githubusercontent\.com/[^/\s]+/[^/\s]+/[^/\s]+)/(chat/amicus-audit/IMPORTANCE_PROMPT\.md)", head)
imp_ok = len(imp) == 1 and (ROOT / imp[0]).is_file()
print(f"importance prompt link: {len(imp)}; resolves: {imp_ok}")
ok &= imp_ok

rg = re.findall(r"(?:\{\{RAW_URL\}\}|https://raw\.githubusercontent\.com/[^/\s]+/[^/\s]+/[^/\s]+)/(chat/amicus-audit/REPORT_GUIDE\.md)", head)
rg_ok = len(rg) == 1 and (ROOT / rg[0]).is_file()
print(f"report guide link: {len(rg)}; resolves: {rg_ok}")
ok &= rg_ok

rows = re.findall(r"^\| `(\w+)` \|", head, re.M)
print(f"routing modules: {len(rows)}")
if sorted(rows) != sorted(SHIPPING) or len(rows) != len(set(rows)):
    ok = False
    print("FAIL: routing vs SHIPPING plus universal; extra", set(rows) - set(SHIPPING), "absent", set(SHIPPING) - set(rows))
else:
    print("routing table matches SHIPPING plus universal exactly")
bad = [m for m in rows if f"chat/amicus-audit/checklists/{m.upper()}_CHECKLIST.md" not in " ".join(links)]
ok &= not bad
if bad: print("FAIL: row without matching link", bad)

dashes = [i + 1 for i, l in enumerate(text.splitlines()) if "—" in l or "–" in l]
print(f"em/en dash lines: {dashes or 'none'}")
ok &= not dashes
print("OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
