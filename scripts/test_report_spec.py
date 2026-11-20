#!/usr/bin/env python3
"""The report guide and every route that points at it: scripts/skillgen/report_spec.py is the one source of the
report's voice and layout. Run: python3 scripts/test_report_spec.py  (stdlib unittest; no model is ever called)."""
import ast, re, sys, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/skillgen"))
import explainer_text, grouping, importance, paper_only_audit as poa, report_spec  # noqa: E402

EM, EN = chr(0x2014), chr(0x2013)
MARK = "<!-- end of model-facing instructions -->"


def first_existing(*rels):
    """The internal-repo layout (public/...) or the public export's (root)."""
    return next(ROOT / r for r in rels if (ROOT / r).exists())


AMICUS = first_existing("public/AMICUS.md", "AMICUS.md")
PLUGIN = first_existing("public/plugins/amicus", "plugins/amicus")
ROUTES = {"AMICUS.md": AMICUS, "chat SKILL.md": ROOT / "chat/amicus-audit/SKILL.md",
          "portable instructions": ROOT / "chat/portable/AMICUS_INSTRUCTIONS.md",
          "plugin SKILL.md": PLUGIN / "skills/amicus-audit/SKILL.md", "plugin command": PLUGIN / "commands/amicus.md"}
GUIDES = {"chat": ROOT / "chat/amicus-audit/REPORT_GUIDE.md", "plugin": PLUGIN / "skills/amicus-audit/REPORT_GUIDE.md"}
# Phrases of the report spec every route used to carry itself; the guide is now the only home for them.
OLD_SPEC = ("Hardest calls", "Ask for the full table", "Advice (single-source", "What this audit is and is not",
            "audit measures what the paper reports", "Header: paper title", '"Passed:"',
            "How much it matters here", "What I noticed:", "merge or drop", "HIGH severity first", "severity first")


class GuideTests(unittest.TestCase):
    def test_last_instruction_is_the_disclaimer_verbatim(self):
        last = report_spec.guide_markdown().rstrip().splitlines()[-1]
        self.assertTrue(last.endswith(f'"{report_spec.DISCLAIMER}"'), last)
        self.assertIn("word for word", last)
        self.assertEqual(report_spec.guide_markdown().count(report_spec.DISCLAIMER), 1)

    def test_closing_line_comes_before_the_disclaimer(self):
        g = report_spec.guide_markdown()
        self.assertLess(g.index(report_spec.CLOSING_LINE), g.index(report_spec.DISCLAIMER))

    def test_no_em_or_en_dash_in_the_guide(self):
        g = report_spec.guide_markdown()
        self.assertNotIn(EM, g); self.assertNotIn(EN, g)

    def test_table_header_and_legend_are_in_the_guide_word_for_word(self):
        g = report_spec.guide_markdown()
        self.assertIn("\n| Matters | Issue | Where | Checks |\n|---|---|---|---|\n", g)
        self.assertEqual(g.count(report_spec.LEGEND), 1)
        self.assertIn(f'word for word: "{report_spec.LEGEND}"', g)
        self.assertLess(g.index("| Matters | Issue | Where | Checks |"), g.index(report_spec.LEGEND))

    def test_grouping_prompt_has_its_placeholders_and_no_dashes(self):
        for k in ("{paper}", "{flags}", "{out}"):
            self.assertEqual(grouping.PROMPT.count(k), 1, k)
        self.assertNotIn(EM, grouping.PROMPT); self.assertNotIn(EN, grouping.PROMPT)
        grouping.PROMPT.format(paper="p", flags="f", out="o")  # the JSON braces are escaped

    def test_grouping_flags_keep_one_tag_per_flag_when_a_note_has_a_newline(self):
        flags = [{"req": "R1", "note": "line one\nline two"}, {"req": "R2", "note": "n2", "may_exist_elsewhere": True}, {"req": "R3", "note": "n3"}]
        text = grouping.format_flags(flags)
        self.assertEqual(len(re.findall(r"^F\d+ Requirement: ", text, re.M)), 3)  # no flag dropped
        self.assertEqual(text.count("may exist elsewhere"), 1)
        self.assertIn("F2 Requirement: R2 | Auditor note: n2 | Auditor tag: may exist elsewhere", text)
        self.assertTrue(text.startswith(importance.format_flags(flags)[:30]))

    def test_generated_guides_are_the_spec_and_nothing_else(self):
        for name, p in GUIDES.items():
            self.assertEqual(p.read_text(), report_spec.guide_markdown(), f"{name}: regenerate with the build scripts, never hand-edit")


class RouteTests(unittest.TestCase):
    def test_every_route_links_the_guide_and_has_no_old_report_list(self):
        for name, p in ROUTES.items():
            t = p.read_text()
            self.assertIn("REPORT_GUIDE.md", t, name)
            for phrase in OLD_SPEC:
                self.assertNotIn(phrase, t, f"{name} still carries the old report spec: {phrase!r}")

    def test_amicus_md_links_the_guide_once_and_it_exists(self):
        head = AMICUS.read_text().split(MARK)[0]
        self.assertEqual(head.count("/chat/amicus-audit/REPORT_GUIDE.md"), 1)
        self.assertTrue(GUIDES["chat"].is_file())

    def test_amicus_md_marks_the_end_of_the_model_facing_part(self):
        self.assertIn(MARK, AMICUS.read_text())

    def test_portable_instructions_stay_under_the_chatgpt_limit(self):
        self.assertLess(len(ROUTES["portable instructions"].read_text()), 8000)

    def test_portable_zip_carries_the_guide(self):
        import zipfile
        for z, names in ((ROOT / "chat/amicus-audit-portable.zip", {"REPORT_GUIDE.md"}), (ROOT / "chat/amicus-audit.zip", {"amicus-audit/REPORT_GUIDE.md"})):
            if z.exists():
                self.assertTrue(names <= set(zipfile.ZipFile(z).namelist()), z.name)


class ExplainerLabelTests(unittest.TestCase):
    """The guide tells a model to use the checklist's "In plain words" and "Why it matters" lines when present; the
    labels it quotes must be the ones the checklists carry."""
    CHECKLISTS = {"chat": ROOT / "chat/amicus-audit/checklists", "plugin": PLUGIN / "skills/amicus-audit/checklists"}

    def test_guide_quotes_the_labels_the_checklists_use(self):
        for label in (explainer_text.PLAIN_LABEL, explainer_text.WHY_LABEL):
            self.assertIn(f'"{label}:"', report_spec.REPORT_STEPS)
        self.assertEqual((explainer_text.PLAIN_LABEL, explainer_text.WHY_LABEL), ("In plain words", "Why it matters"))

    def test_every_shipped_checklist_has_the_pair_of_lines_under_each_check(self):
        for where, d in self.CHECKLISTS.items():
            files = sorted(d.glob("*_CHECKLIST.md"))
            self.assertEqual(len(files), 15, where)
            for f in files:
                t = f.read_text()
                n = len(re.findall(r"^### ", t, re.M))
                self.assertGreater(n, 0, f.name)
                self.assertEqual(t.count("\n**In plain words:** "), n, f"{where}/{f.name}")
                self.assertEqual(t.count("\n**Why it matters:** "), n, f"{where}/{f.name}")
                self.assertNotIn(EM + " ", t if where == "plugin" else "")  # the plugin copy keeps the house style


def static_strings(path, funcs, names):
    """Every string literal written in the named functions, and in the named module-level assignments."""
    tree = ast.parse(Path(path).read_text())
    out = []
    for node in tree.body:
        hit = (isinstance(node, ast.FunctionDef) and node.name in funcs) or \
              (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets))
        if hit:
            out += [n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    return out


class RunnerReportTests(unittest.TestCase):
    def test_static_strings_have_no_em_or_en_dash(self):
        found = static_strings(ROOT / "scripts/skillgen/paper_only_audit.py",
                               {"report", "_details_paragraph", "_noticed", "_where", "_short_title", "_issues", "_what_i_read",
                                "_plain_list", "_module_name", "_module_phrase", "_does_well", "_explainers", "coder_checklist",
                                "read_more", "cite", "_flag_pass", "rate_importance", "group_flags"},
                               {"ENCOURAGEMENT", "MODULE_NAMES", "IMPORTANCE_LABEL", "MATTERS_ORDER"})
        self.assertGreater(len(found), 20)  # the walk found the report's strings
        for s in found:
            self.assertNotIn(EM, s); self.assertNotIn(EN, s)
        self.assertNotIn(EM + EN, poa.ENCOURAGEMENT)

    def write(self, results, **kw):
        out = Path(tempfile.mkdtemp())
        poa.report(out, "paper", [{"module": m, "why": "w"} for m in results] or [], results, run_dirs={m: out for m in results}, **kw)
        return (out / "AUDIT_REPORT.md").read_text()

    @staticmethod
    def results(verdicts):
        checks = [{"check_id": f"X-{i}", "requirement_statement": f"R{i}", "severity_if_flagged": "HIGH", "claim": "c", "consensus_grade": "high"}
                  for i in range(len(verdicts))]
        by = {c["check_id"]: {"check_id": c["check_id"], "verdict": v, "in_scope": v != "NA", "note": "n"} for c, v in zip(checks, verdicts)}
        return {"did": (checks, by, [])}

    def test_report_ends_with_the_disclaimer_in_every_shape(self):
        shapes = {"flags": self.write(self.results(["FLAG", "PASS"])), "no flags": self.write(self.results(["PASS", "NA"])),
                  "nothing coded": self.write({}), "coder failed": self.write({}, failed=["did"]),
                  "importance note": self.write(self.results(["FLAG"]), importance_note="the call failed")}
        for name, rep in shapes.items():
            self.assertEqual(rep.rstrip().splitlines()[-1], report_spec.DISCLAIMER, name)
            self.assertTrue(rep.endswith(report_spec.DISCLAIMER + "\n"), name)
            self.assertEqual(rep.count(report_spec.DISCLAIMER), 1, name)
        rep = shapes["flags"]
        self.assertIn("I read your paper against the methods literature for difference-in-differences: 2 checks, 1 flagged.", rep)
        self.assertNotIn("I read your paper", shapes["nothing coded"])  # nothing was read against any module
        self.assertIn(poa.ENCOURAGEMENT, rep)
        self.assertLess(rep.index(poa.ENCOURAGEMENT), rep.index("AUDIT_DETAILS.md"))
        self.assertLess(rep.index("AUDIT_DETAILS.md"), rep.index(report_spec.DISCLAIMER))

    @staticmethod
    def graded(grades_and_verdicts):
        """did checks X-0.. with the given (consensus grade, verdict, severity) and a note per flag."""
        checks = [{"check_id": f"X-{i}", "requirement_statement": f"The paper must report R{i}.", "severity_if_flagged": sev, "claim": f"Claim {i}.",
                   "consensus_grade": g} for i, (g, _v, sev) in enumerate(grades_and_verdicts)]
        by = {c["check_id"]: {"check_id": c["check_id"], "verdict": v, "in_scope": v != "NA", "note": f"Note {i}.", "borderline": i == 1}
              for i, (c, (_g, v, _s)) in enumerate(zip(checks, grades_and_verdicts))}
        return {"did": (checks, by, [])}

    @staticmethod
    def imp(results, levels):
        return [dict(f, key=f"F{i+1}", paper_severity=lv, why="w") for i, (f, lv) in enumerate(zip(poa.collect_flags(results), levels))]

    def test_matters_skips_single_source_checks_and_advice_goes_last(self):
        # F1 low/critical + F2 high/minor grouped; F3 low/major alone; F4 high/major alone; F5 high/negligible alone
        res = self.graded([("low", "FLAG", "HIGH"), ("high", "FLAG", "LOW"), ("low", "FLAG", "HIGH"), ("high", "FLAG", "MEDIUM"),
                           ("high", "FLAG", "HIGH"), ("high", "PASS", "HIGH")])
        issues = [{"title": "Mixed issue", "where": "p.1", "flags": ["F1", "F2"]}, {"title": "Single-source issue", "where": "p.2", "flags": ["F3"]},
                  {"title": "Major issue", "where": "p.3", "flags": ["F4"]}, {"title": "Small issue", "where": "silent", "flags": ["F5"]}]
        rep = self.write(res, importance_flags=self.imp(res, ["critical", "minor", "major", "major", "negligible"]), issues=issues)
        table = rep.split("\n## Everything I flagged\n", 1)[1].split("\n## ", 1)[0]
        rows = [l for l in table.splitlines() if l.startswith("| ") and not l.startswith("| Matters")]
        self.assertEqual(rows, ["| Major | Major issue | p.3 | X-3 |", "| Minor | Mixed issue | p.1 | X-0, X-1 |",
                                "| Negligible | Small issue | silent | X-4 |", "| Single source | Single-source issue | p.2 | X-2 |"])
        self.assertIn("6 checks, 5 flagged, none critical.", rep)  # the critical flag is single-source: Single source, not Critical
        self.assertIn("1. **Major issue.** Note 3. (Major, 1 check)", rep)
        self.assertEqual(re.findall(r"^### (.+)$", rep, re.M), ["Major issue (Major)"])  # details for Critical and Major only
        self.assertIn("Hardest calls\n\nNone.", rep)  # the borderline check sits in a Minor issue
        self.assertIn(f"\n\n{report_spec.LEGEND}\n", rep)
        self.assertIsNone(re.search(r"\b(HIGH|MEDIUM|LOW)\b", rep))
        self.assertLess(rep.index("## The main issues"), rep.index("## Everything I flagged"))
        self.assertEqual(rep.rstrip().splitlines()[-1], report_spec.DISCLAIMER)

    def test_no_major_issue_is_said_and_a_stale_grouping_is_not_used(self):
        res = self.graded([("high", "FLAG", "HIGH"), ("high", "FLAG", "HIGH")])
        rep = self.write(res, importance_flags=self.imp(res, ["minor", "negligible"]), issues=[{"title": "T", "where": "p.1", "flags": ["F1"]}])
        self.assertIn("## The main issues\n\nNone of the issues is rated Critical or Major.\n", rep)
        self.assertNotIn("## Details", rep)
        self.assertIn("The flags are not grouped into issues because the stored grouping does not match this run's flags", rep)
        self.assertEqual(rep.count("| Minor |") + rep.count("| Negligible |"), 2)  # one issue per flag


if __name__ == "__main__":
    unittest.main(verbosity=1)
