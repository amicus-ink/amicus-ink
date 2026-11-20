#!/usr/bin/env python3
"""Tests for the hardened paper-only runner and agent_call.py (internal-only tests live in
test_paper_only_audit_internal.py).
Run: python3 scripts/test_paper_only_audit.py  (stdlib unittest; no model is ever called)."""
import contextlib, io, json, os, re, subprocess, sys, tempfile, unittest, zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/skillgen"))
import agent_call, doi_links, explainer_text, paper_only_audit as poa, report_spec  # noqa: E402

CHECKLIST = ROOT / "runs/skill_generation" / poa.SHIPPING["synth"]
NSYNTH = len(poa.load_checks(CHECKLIST)) if CHECKLIST.exists() else 0  # checks in the shipped synth checklist, as the report header counts them
PAPER_TEXT = "We use the synthetic control method with 24 donor regions.\n"


def proc(out="", err="", rc=0):
    return subprocess.CompletedProcess(["x"], rc, stdout=out, stderr=err)


def synth_ids():
    return [c["check_id"] for c in poa.load_checks(CHECKLIST)]


def good_rows(n=None):
    ids = synth_ids()[:n]
    return [{"check_id": i, "in_scope": True, "verdict": "PASS", "borderline": False, "note": "ok"} for i in ids]


class FakeAgent:
    """Stands in for run_agent: writes the coding file named in the prompt."""
    def __init__(self, rows=None, write=True, text=None):
        self.calls, self.rows, self.write, self.text = [], rows, write, text

    def __call__(self, prompt, **kw):
        self.calls.append(kw)
        m = re.search(r"(\S*coding_\w+\.json)", prompt)
        if self.write and m:
            Path(m.group(1)).write_text(self.text if self.text is not None else json.dumps(self.rows if self.rows is not None else good_rows()))
        return proc("done")


if os.environ.get("CI") and not CHECKLIST.exists():
    sys.exit(f"CI must check out the shipping checklists (see .github/workflows/check.yml); missing {CHECKLIST}")


class RunnerBase(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ, {"AMICUS_TRUST_LEGACY": "0"}); env.start(); self.addCleanup(env.stop)
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.paper = self.tmp / "paper.txt"; self.paper.write_text(PAPER_TEXT)
        self.out = self.tmp / "out"
        p = mock.patch.object(poa, "_backoff", lambda s: None); p.start(); self.addCleanup(p.stop)

    def run_main(self, agent, *extra, out=None, universal=False):
        """Run the runner on synth; the universal list is left out unless `universal` (UniversalRunnerTests)."""
        argv = ["--paper", str(self.paper), "--modules", "synth", "--out", str(out or self.out), *extra, *([] if universal else ["--no-universal"])]
        with mock.patch.object(poa, "run_agent", agent), contextlib.redirect_stdout(io.StringIO()) as buf:
            poa.main(argv)
        return buf.getvalue()


@unittest.skipUnless(CHECKLIST.exists(), "synth checklist not checked out (sparse worktree)")
class RunnerTests(RunnerBase):
    def test_clean_run_and_reuse(self):
        a = FakeAgent(); self.run_main(a)
        self.assertEqual(len(a.calls), 1)
        self.assertEqual(Path(a.calls[0]["cwd"]), self.out); self.assertEqual(Path(a.calls[0]["write_dir"]), self.out)
        b = FakeAgent(); out = self.run_main(b)
        self.assertEqual(len(b.calls), 0); self.assertIn("reusing", out)

    def test_partial_output_moved_aside(self):
        self.out.mkdir(); (self.out / "coding_synth.json").write_text('[{"check_id": "SYNTH-IDE')  # killed mid-write
        a = FakeAgent(); self.run_main(a)
        self.assertEqual(len(a.calls), 1)
        self.assertTrue((self.out / "coding_synth.json.stale").exists())
        json.load(open(self.out / "coding_synth.json"))

    def test_unrecorded_valid_file_is_stale(self):
        self.out.mkdir(); (self.out / "coding_synth.json").write_text(json.dumps(good_rows()))  # no provenance
        with mock.patch.dict(os.environ, {"AMICUS_TRUST_LEGACY": "0"}):
            a = FakeAgent(); self.run_main(a)
        self.assertEqual(len(a.calls), 1); self.assertTrue((self.out / "coding_synth.json.stale").exists())

    def test_legacy_dir_without_manifest_reused_by_default(self):
        self.out.mkdir(); (self.out / "coding_synth.json").write_text(json.dumps(good_rows()))
        (self.out / "routing.json").write_text(json.dumps([{"module": "synth", "why": "legacy"}]))
        with mock.patch.dict(os.environ, {"AMICUS_TRUST_LEGACY": "1"}):
            a = FakeAgent(); out = self.run_main(a)
        self.assertEqual(len(a.calls), 0); self.assertIn("legacy output", out)

    def test_legacy_dir_stays_legacy_after_a_new_output(self):
        # A pre-manifest dir with routing but no coding: the first rerun codes synth and starts
        # a manifest; the second must still trust the unrecorded legacy routing.json.
        self.out.mkdir(); (self.out / "routing.json").write_text(json.dumps([{"module": "synth", "why": "legacy"}]))
        argv = ["--paper", str(self.paper), "--out", str(self.out), "--no-universal"]
        with mock.patch.dict(os.environ, {"AMICUS_TRUST_LEGACY": "1"}):
            for expected_calls in (1, 0):
                a = FakeAgent()
                with mock.patch.object(poa, "run_agent", a), contextlib.redirect_stdout(io.StringIO()):
                    poa.main(argv)
                self.assertEqual(len(a.calls), expected_calls)
        self.assertFalse((self.out / "routing.json.stale").exists())

    def test_foreign_check_ids_rejected(self):
        a = FakeAgent(rows=[{"check_id": "DID-X-01", "verdict": "PASS", "in_scope": True}])
        with self.assertRaises(SystemExit) as cm, mock.patch.object(poa, "run_agent", a), contextlib.redirect_stdout(io.StringIO()):
            poa.main(["--paper", str(self.paper), "--modules", "synth", "--out", str(self.out), "--no-universal"])
        self.assertEqual(cm.exception.code, 2)

    def test_provenance_mismatch_forces_redo(self):
        self.run_main(FakeAgent(), "--model", "model-a")
        same = FakeAgent(); self.run_main(same, "--model", "model-a"); self.assertEqual(len(same.calls), 0)
        other = FakeAgent(); self.run_main(other, "--model", "model-b"); self.assertEqual(len(other.calls), 1)
        self.assertTrue((self.out / "coding_synth.json.stale").exists())
        self.paper.write_text(PAPER_TEXT + "Changed paper.\n")  # paper hash changes
        third = FakeAgent(); self.run_main(third, "--model", "model-b"); self.assertEqual(len(third.calls), 1)
        fourth = FakeAgent(); self.run_main(fourth, "--model", "model-b", "--blind"); self.assertEqual(len(fourth.calls), 1)

    def test_exit_2_when_coder_fails(self):
        a = FakeAgent(write=False)
        with self.assertRaises(SystemExit) as cm, mock.patch.object(poa, "run_agent", a), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            poa.main(["--paper", str(self.paper), "--modules", "synth", "--out", str(self.out), "--no-universal"])
        self.assertEqual(cm.exception.code, 2)
        self.assertEqual(len(a.calls), poa.CODER_ATTEMPTS)
        self.assertEqual(json.load(open(self.out / "coder_failures.json"))[0]["module"], "synth")
        rep = (self.out / "AUDIT_REPORT.md").read_text()
        self.assertIn("INCOMPLETE AUDIT", rep.split("\n", 3)[2]); self.assertIn("SYNTH", rep.split("\n", 3)[2])

    def test_report_denominator_lists_all_missing(self):
        ids = synth_ids()
        self.run_main(FakeAgent(rows=good_rows(2)))
        rep = (self.out / "AUDIT_REPORT.md").read_text()
        self.assertIn(f"(2 of {len(ids)} checks returned)", rep)
        for i in ids[2:]:
            self.assertIn(i, rep)

    def test_bad_module_fails_before_staging(self):
        with self.assertRaises(SystemExit) as cm:
            poa.main(["--paper", str(self.paper), "--modules", "synth,dd", "--out", str(self.out)])
        msg = str(cm.exception.code)
        self.assertIn("dd", msg); self.assertIn("measurement", msg)
        self.assertFalse(self.out.exists())

    def test_relative_out_resolved(self):
        old = os.getcwd(); os.chdir(self.tmp)
        try:
            a = FakeAgent(); self.run_main(a, out="rel_out")
        finally:
            os.chdir(old)
        self.assertEqual(Path(a.calls[0]["cwd"]), self.tmp / "rel_out")
        self.assertTrue((self.tmp / "rel_out" / "coding_synth.json").exists())
        self.assertIn(str(self.tmp / "rel_out"), json.load(open(self.tmp / "rel_out/staging.json"))[0]["file"] + str(self.tmp / "rel_out"))

    def test_stale_routing_not_trusted(self):
        self.out.mkdir(); (self.out / "routing.json").write_text(json.dumps([{"module": "did", "why": "old paper"}]))
        seen = {}
        def agent(prompt, **kw):
            seen["existed"] = (self.out / "routing.json").exists()
            return proc("")  # writes nothing
        with self.assertRaises(SystemExit), mock.patch.object(poa, "run_agent", agent), contextlib.redirect_stdout(io.StringIO()):
            poa.main(["--paper", str(self.paper), "--out", str(self.out), "--no-universal"])
        self.assertFalse(seen["existed"])  # moved aside before the call, so a failed call cannot hide behind it
        self.assertTrue((self.out / "routing.json.stale").exists())


def flag_rows(flag_idx=(0,), n=None, mee=()):
    """good_rows with the rows at `flag_idx` flagged (note "Paper does not report item <k>.", row 1 borderline) and
    the rows at `mee` tagged may_exist_elsewhere."""
    rows = good_rows(n)
    for k in flag_idx:
        rows[k] = dict(rows[k], verdict="FLAG", note=f"Paper does not report item {k}.", borderline=(k == 1), may_exist_elsewhere=(k in mee))
    return rows


GROUP_MARK = "Your only task is to group the flags into issues"
SEVERITY_WORDS = re.compile(r"\b(HIGH|MEDIUM|LOW)\b|[Cc]hecklist severity")


class ImportanceAgent(FakeAgent):
    """FakeAgent that also answers the importance call (the prompt opens 'You are a methods referee') and the
    grouping call (grouping.PROMPT). imp and grp: "good", "bad" (invalid output) or "none" (writes nothing).
    Importance levels cycle minor, critical, major, negligible by flag; `groups` lists issues as 1-based flag
    numbers (default: one issue per flag), titled "Issue <k> in plain words" and located at "p.<k>"."""
    LEVELS = ["minor", "critical", "major", "negligible"]

    def __init__(self, rows=None, imp="good", grp="good", groups=None, **kw):
        super().__init__(rows=rows if rows is not None else flag_rows((0, 1)), **kw)
        self.imp, self.grp, self.groups, self.imp_prompts, self.grp_prompts = imp, grp, groups, [], []

    def __call__(self, prompt, **kw):
        if "You are a methods referee" in prompt:
            self.calls.append(kw); self.imp_prompts.append(prompt)
            out = Path(re.search(r"Write to `([^`]+flag_severity\.json)`", prompt).group(1))
            n = len(re.findall(r"^F\d+ Requirement:", prompt, re.M))
            if self.imp == "good":
                out.write_text(json.dumps({"flags": [{"flag": f"F{i+1}", "severity": self.LEVELS[i % 4], "why": f"reason {i+1}"} for i in range(n)]}))
            elif self.imp == "bad":
                out.write_text(json.dumps({"flags": [{"flag": "F1", "severity": "huge", "why": "x"}]}))
            return proc("done")
        if GROUP_MARK in prompt:
            self.calls.append(kw); self.grp_prompts.append(prompt)
            out = Path(re.search(r"Write to `([^`]+issues\.json)`", prompt).group(1))
            n = len(re.findall(r"^F\d+ Requirement:", prompt, re.M))
            if self.grp == "good":
                groups = self.groups or [[i] for i in range(1, n + 1)]
                out.write_text(json.dumps({"issues": [{"title": f"Issue {k+1} in plain words", "where": f"p.{k+1}", "flags": [f"F{i}" for i in g]}
                                                      for k, g in enumerate(groups)]}))
            elif self.grp == "bad":
                out.write_text(json.dumps({"issues": [{"title": "x", "where": "p.1", "flags": ["F1", "F1"]}]}))
            return proc("done")
        return super().__call__(prompt, **kw)


def section(rep, heading):
    """The body of one '## ' section of a report, without its heading."""
    return rep.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]


def table_rows(rep):
    return [l for l in section(rep, "Everything I flagged").splitlines() if l.startswith("| ") and not l.startswith("| Matters")]


@unittest.skipUnless(CHECKLIST.exists(), "synth checklist not checked out (sparse worktree)")
class ImportanceTests(RunnerBase):
    def test_grouped_report_details_and_reuse(self):
        # F1 minor, F2 critical (borderline), F3 major, F4 negligible; issues: {F1, F3}, {F2}, {F4}
        a = ImportanceAgent(rows=flag_rows((0, 1, 2, 3)), groups=[[1, 3], [2], [4]]); self.run_main(a)
        self.assertEqual((len(a.imp_prompts), len(a.grp_prompts), len(a.calls)), (1, 1, 3))
        knobs = lambda kw: {k: v for k, v in kw.items() if k in ("agent", "model", "effort", "cwd", "write_dir")}
        self.assertEqual(knobs(a.calls[2]), knobs(a.calls[0]))  # the grouping call runs with the coder's settings
        self.assertIn("Write to `" + str(self.out / "issues.json") + "`", a.grp_prompts[0])
        j = json.load(open(self.out / "flag_severity.json"))
        self.assertEqual([f["paper_severity"] for f in j["flags"]], ["minor", "critical", "major", "negligible"])
        g = json.load(open(self.out / "issues.json"))
        ids = synth_ids()
        self.assertEqual(g["n_flags"], 4); self.assertEqual([f["id"] for f in g["flags"]], ids[:4]); self.assertEqual(len(g["issues"]), 3)
        rep = (self.out / "AUDIT_REPORT.md").read_text()
        heads = [rep.index(f"## {h}\n") for h in ("What the paper does well", "The main issues", "Everything I flagged", "Details", "Not completed", "Hardest calls")]
        self.assertEqual(heads, sorted(heads))  # strengths first, then the summary, the table and the details
        self.assertIn(f"I read your paper against the methods literature for synthetic control: {NSYNTH} checks, 4 flagged, 1 critical.\n", rep)
        self.assertEqual(table_rows(rep), [
            f"| Critical | Issue 2 in plain words | p.2 | {ids[1]} |",
            f"| Major | Issue 1 in plain words | p.1 | {ids[0]}, {ids[2]} |",
            f"| Negligible | Issue 3 in plain words | p.3 | {ids[3]} |"])
        self.assertIn("\n| Matters | Issue | Where | Checks |\n|---|---|---|---|\n", rep)
        self.assertIn(f"{table_rows(rep)[-1]}\n\n{report_spec.LEGEND}\n", rep)  # the legend word for word, right under the table
        self.assertEqual(section(rep, "The main issues").strip().splitlines(), [
            "1. **Issue 2 in plain words.** Paper does not report item 1. (Critical, 1 check)",
            "2. **Issue 1 in plain words.** Paper does not report item 2. (Major, 2 checks)"])  # main check: the major F3
        det = section(rep, "Details")
        self.assertEqual(re.findall(r"^### (.+)$", det, re.M), ["Issue 2 in plain words (Critical)", "Issue 1 in plain words (Major)"])  # Critical and Major only
        crit = det.split("### Issue 1")[0]
        self.assertIn("It is a close call.", crit); self.assertNotIn("It is a close call.", det.split("### Issue 1")[1])
        c2 = next(c for c in poa.load_checks(CHECKLIST) if c["check_id"] == ids[1])
        self.assertIn(f"\nRead more: {poa.read_more(c2, CHECKLIST)}\nChecks: {ids[1]}\n", crit)
        self.assertIn(f"Checks: {ids[0]}, {ids[2]}\n", det)
        self.assertEqual(section(rep, "Hardest calls").strip().split("\n\n")[0], "These issues include a check a second reader could judge differently: Issue 2 in plain words.")
        self.assertEqual(section(rep, "Not completed").strip(), "None.")
        tail = rep.rstrip().splitlines()  # encouraging sentence, the AUDIT_DETAILS pointer, then the disclaimer last
        self.assertEqual(tail[-1], report_spec.DISCLAIMER); self.assertIn("AUDIT_DETAILS.md", tail[-3]); self.assertEqual(tail[-5], poa.ENCOURAGEMENT)
        self.assertIsNone(SEVERITY_WORDS.search(rep)); self.assertNotIn("consensus", rep.lower())
        det_file = (self.out / "AUDIT_DETAILS.md").read_text()
        self.assertIn("| Check | Verdict | Checklist severity | Consensus | Importance | Issue | Tags | Coder note |", det_file)
        for i in ids:
            self.assertIn(i, det_file)
        self.assertIn(f"| {ids[2]} | FLAG | ", det_file); self.assertIn("| Issue 1 in plain words |", det_file); self.assertIn("| critical |", det_file)
        # a rerun reuses both report-only outputs
        b = ImportanceAgent(rows=flag_rows((0, 1, 2, 3)), groups=[[1, 3], [2], [4]]); out = self.run_main(b)
        self.assertEqual(len(b.calls), 0); self.assertIn("importance: reusing", out); self.assertIn("grouping: reusing", out)
        self.assertEqual((self.out / "AUDIT_REPORT.md").read_text(), rep)
        # a changed flag set invalidates both
        c = ImportanceAgent(rows=flag_rows((0, 1, 2))); self.paper.write_text(PAPER_TEXT + "More.\n"); self.run_main(c)
        self.assertEqual((len(c.imp_prompts), len(c.grp_prompts)), (1, 1))
        self.assertEqual(json.load(open(self.out / "issues.json"))["n_flags"], 3)

    def test_a_stored_grouping_for_other_flags_is_not_reused(self):
        self.run_main(ImportanceAgent(rows=flag_rows((0, 1))))
        g = json.load(open(self.out / "issues.json")); g["flags"][0]["id"] = "SYNTH-OTHER-99"
        (self.out / "issues.json").write_text(json.dumps(g))
        b = ImportanceAgent(rows=flag_rows((0, 1))); self.run_main(b)
        self.assertEqual((len(b.imp_prompts), len(b.grp_prompts)), (0, 1))
        self.assertTrue((self.out / "issues.json.stale").exists())

    def test_grouping_failure_lists_each_flag_as_its_own_issue(self):
        for grp in ("bad", "none"):
            out = self.tmp / f"out_{grp}"
            a = ImportanceAgent(rows=flag_rows((0, 1, 2)), grp=grp); self.run_main(a, out=out)  # must not raise or exit nonzero
            self.assertEqual((len(a.imp_prompts), len(a.grp_prompts)), (1, poa.CODER_ATTEMPTS), grp)
            self.assertFalse((out / "issues.json").exists(), grp)
            rep = (out / "AUDIT_REPORT.md").read_text()
            notes = [l for l in rep.splitlines() if l.startswith("> ")]
            self.assertEqual(len(notes), 1, grp)
            self.assertIn(f"The flags are not grouped into issues because the grouping call failed after {poa.CODER_ATTEMPTS} attempts", notes[0])
            self.assertIn("so each flag is its own issue", notes[0])
            rows = table_rows(rep)
            self.assertEqual(len(rows), 3, grp)
            checks = {c["check_id"]: c for c in poa.load_checks(CHECKLIST)}
            for r in rows:
                cid = r.rstrip(" |").rsplit("| ", 1)[1]
                self.assertIn(f"| {poa._short_title({'id': cid, 'req': checks[cid]['requirement_statement']})} | not located | {cid} |", r)
            self.assertIn("## The main issues", rep); self.assertIn("## Details", rep)  # importance still orders and selects
            self.assertEqual(rep.rstrip().splitlines()[-1], report_spec.DISCLAIMER)
            self.assertIsNone(SEVERITY_WORDS.search(rep))

    def test_importance_failure_falls_back(self):
        a = ImportanceAgent(imp="bad")
        self.run_main(a)  # must not raise or exit nonzero
        self.assertEqual(len(a.imp_prompts), poa.CODER_ATTEMPTS); self.assertEqual(len(a.grp_prompts), 1)  # grouping still runs
        self.assertFalse((self.out / "flag_severity.json").exists())
        rep = (self.out / "AUDIT_REPORT.md").read_text()
        self.assertIn("Importance ratings are not in this report because the importance call failed", rep)
        self.assertNotIn("## The main issues", rep); self.assertIn(f"synthetic control: {NSYNTH} checks, 2 flagged.\n", rep)
        self.assertTrue(all(r.startswith("| unrated | Issue ") for r in table_rows(rep)))
        self.assertEqual(re.findall(r"^### (.+)$", section(rep, "Details"), re.M), ["Issue 1 in plain words (unrated)", "Issue 2 in plain words (unrated)"])
        self.assertIn(synth_ids()[0], rep)
        a2 = ImportanceAgent(imp="none"); self.run_main(a2, out=self.tmp / "out2")
        self.assertIn("importance call failed", (self.tmp / "out2/AUDIT_REPORT.md").read_text())

    def test_no_importance_skips_both_report_calls(self):
        a = ImportanceAgent(); out = self.run_main(a, "--no-importance")
        self.assertEqual((len(a.imp_prompts), len(a.grp_prompts), len(a.calls)), (0, 0, 1))
        self.assertNotIn("grouping", out)
        self.assertFalse((self.out / "flag_severity.json").exists()); self.assertFalse((self.out / "issues.json").exists())
        rep = (self.out / "AUDIT_REPORT.md").read_text()
        self.assertIn("--no-importance", rep); self.assertTrue((self.out / "AUDIT_DETAILS.md").exists())
        self.assertIn("The flags are not grouped into issues because the grouping pass is skipped with it (--no-importance)", rep)
        self.assertNotIn("## The main issues", rep)
        rows = table_rows(rep)
        self.assertEqual(len(rows), 2); self.assertTrue(all(r.startswith("| unrated | ") for r in rows))
        self.assertEqual(len(re.findall(r"^### .+ \(unrated\)$", rep, re.M)), 2)  # without ratings every issue gets details
        self.assertEqual(rep.rstrip().splitlines()[-1], report_spec.DISCLAIMER)

    def test_no_flags_no_call(self):
        a = ImportanceAgent(rows=good_rows()); self.run_main(a)
        self.assertEqual((len(a.imp_prompts), len(a.grp_prompts)), (0, 0))
        rep = (self.out / "AUDIT_REPORT.md").read_text()
        self.assertIn("No flags.", rep); self.assertIn(f"{NSYNTH} checks, none flagged.", rep)
        self.assertNotIn("## The main issues", rep); self.assertNotIn("## Details", rep); self.assertNotIn(report_spec.LEGEND, rep)

    def test_may_exist_elsewhere_reaches_the_call_and_shows_not_seen(self):
        rows = flag_rows((0, 1, 2), mee=(2,))
        rows[0]["may_exist_elsewhere"] = True; rows[0]["pointer"] = "Appendix C"
        a = ImportanceAgent(rows=rows); self.run_main(a)
        tagged = [l for l in a.grp_prompts[0].splitlines() if re.match(r"F\d+ Requirement:", l)]
        self.assertEqual(["may exist elsewhere" in l for l in tagged], [True, False, True])
        flags = poa.collect_flags({"synth": (poa.load_checks(CHECKLIST), {r["check_id"]: r for r in rows}, [])})
        self.assertEqual([(f["may_exist_elsewhere"], f.get("pointer")) for f in flags], [(True, "Appendix C"), (False, None), (True, None)])
        r = {l.split(" | ")[1]: l for l in table_rows((self.out / "AUDIT_REPORT.md").read_text())}
        self.assertIn("| p.1; not seen (Appendix C) |", r["Issue 1 in plain words"])
        self.assertIn("| p.2 |", r["Issue 2 in plain words"])
        self.assertIn("| p.3; not seen |", r["Issue 3 in plain words"])
        self.run_main(ImportanceAgent(rows=rows), "--no-importance", out=self.tmp / "out_ng")  # ungrouped: the tag alone
        r2 = table_rows((self.tmp / "out_ng/AUDIT_REPORT.md").read_text())
        self.assertEqual([("| not seen (Appendix C) |" in l, "| not located |" in l, "| not seen |" in l) for l in r2],
                         [(True, False, False), (False, True, False), (False, False, True)])

    def test_importers_opt_out(self):
        paths = [ROOT / "scripts/skillgen" / f"{f}.py" for f in ("apsa_cohort", "arxiv_cohort", "code_published_new", "cohort_code_batch",
                                                               "osf_cohort", "recode_new_cohorts", "ssrn_code_batch", "ssrn_code_published")]
        if not any(p.exists() for p in paths):
            self.skipTest("internal batch scripts are not in the public export")
        for p in paths:
            self.assertIn('str(RUNNER), "--no-importance", "--no-universal"', p.read_text(), p.name)


IV = ROOT / "runs/skill_generation" / poa.SHIPPING["iv"]
DID = ROOT / "runs/skill_generation" / poa.SHIPPING["did"]  # a shipped module with a single-source (consensus low) check


@unittest.skipUnless(CHECKLIST.exists() and DID.exists(), "did and synth checklists not checked out (sparse worktree)")
class TwoModuleTests(RunnerBase):
    """did and synth: a duplicate pair across checks, a may_exist_elsewhere flag, and a single-source (consensus low) check."""
    def test_single_source_issue_is_advice_and_the_pair_is_one_issue(self):
        iv = poa.load_checks(DID)
        low = [c["check_id"] for c in iv if c.get("consensus_grade") == "low"]
        self.assertTrue(low)
        flagged = {"DID-IDENT-01", "DID-INFER-01", low[0], "SYNTH-INFER-01"}

        def agent_rows(module):
            run = DID if module == "did" else CHECKLIST
            return [{"check_id": c["check_id"], "in_scope": True, "verdict": "FLAG" if c["check_id"] in flagged else "PASS",
                     "borderline": False, "may_exist_elsewhere": False, "note": f"Note on {c['check_id']}."} for c in poa.load_checks(run)]

        class Two(ImportanceAgent):
            def __call__(self, prompt, **kw):
                m = re.search(r"(\S*coding_(\w+)\.json)", prompt)
                if m and "You are a methods referee" not in prompt and GROUP_MARK not in prompt:
                    self.calls.append(kw); Path(m.group(1)).write_text(json.dumps(agent_rows(m.group(2)))); return proc("done")
                return super().__call__(prompt, **kw)
        order = [c["check_id"] for c in iv if c["check_id"] in flagged] + ["SYNTH-INFER-01"]
        pos = {cid: k + 1 for k, cid in enumerate(order)}
        a = Two(groups=[[pos["DID-IDENT-01"], pos["DID-INFER-01"]], [pos[low[0]]], [pos["SYNTH-INFER-01"]]])
        argv = ["--paper", str(self.paper), "--modules", "did,synth", "--out", str(self.out), "--no-universal"]
        with mock.patch.object(poa, "run_agent", a), contextlib.redirect_stdout(io.StringIO()):
            poa.main(argv)
        rep = (self.out / "AUDIT_REPORT.md").read_text()
        rows = table_rows(rep)
        self.assertEqual(len(rows), 3)
        self.assertTrue(rows[-1].startswith("| Single source | ") and rows[-1].endswith(f"| {low[0]} |"), rows)  # single-source only: Single source, last
        self.assertTrue(any(r.endswith("| DID-IDENT-01, DID-INFER-01 |") for r in rows), rows)
        self.assertIn(f"for {poa._module_phrase(['did', 'synth'])}: ", rep)
        self.assertIsNone(SEVERITY_WORDS.search(rep))
        self.assertEqual(rep.rstrip().splitlines()[-1], report_spec.DISCLAIMER)


UNIV = ROOT / "runs/skill_generation" / poa.UM.RUN


def univ_ids():
    return [c["check_id"] for c in poa.load_checks(UNIV)]


class UniAgent(ImportanceAgent):
    """ImportanceAgent whose coding file for `universal` holds rows for the universal list, every check PASS except
    the ids in `uflags`; synth gets `rows` as before. `prompts` keeps each coder prompt by module."""
    def __init__(self, uflags=(), **kw):
        super().__init__(**kw)
        self.uflags, self.prompts = set(uflags), {}

    def __call__(self, prompt, **kw):
        m = re.search(r"(\S*coding_(\w+)\.json)", prompt)
        coder = m and "You are a methods referee" not in prompt and GROUP_MARK not in prompt
        if coder and m.group(2) == poa.UM.MODULE:
            self.calls.append(kw); self.prompts["universal"] = prompt
            Path(m.group(1)).write_text(json.dumps([
                {"check_id": i, "in_scope": True, "verdict": "FLAG" if i in self.uflags else "PASS", "borderline": False,
                 "note": f"Paper does not report {i}." if i in self.uflags else "ok"} for i in univ_ids()]))
            return proc("done")
        if coder:
            self.prompts[m.group(2)] = prompt
        return super().__call__(prompt, **kw)


@unittest.skipUnless(CHECKLIST.exists() and (UNIV / "checklists/verified.anchored.json").exists(),
                     "synth and universal checklists not checked out (sparse worktree)")
class UniversalRunnerTests(RunnerBase):
    """The universal list runs on every paper after the routed modules, unless --no-universal."""
    def test_default_codes_the_universal_list_after_the_routed_modules(self):
        a = UniAgent(rows=good_rows()); self.run_main(a, universal=True)
        self.assertEqual(list(a.prompts), ["synth", "universal"])
        self.assertIn("applying the UNIV audit checklist", a.prompts["universal"])  # the module name the paper's coder saw
        self.assertEqual((self.out / "checklist_universal.md").read_text(), explainer_text.strip(poa.UM.CHECKLIST.read_text()))
        self.assertEqual(json.load(open(self.out / "instrument.json"))["universal"], poa.UM.RUN)
        rep = (self.out / "AUDIT_REPORT.md").read_text()
        n = NSYNTH + len(univ_ids())
        self.assertIn(f"I read your paper against the methods literature for synthetic control, plus my general checks: {n} checks, none flagged.\n", rep)
        self.assertIn("- Universal checklist: runs on every paper\n", rep)
        self.assertIn("## UNIVERSAL\n", (self.out / "AUDIT_DETAILS.md").read_text())
        again = UniAgent(rows=good_rows()); self.run_main(again, universal=True)
        self.assertEqual(len(again.calls), 0)  # both codings are reused

    def test_no_universal_leaves_it_out(self):
        a = UniAgent(rows=good_rows()); self.run_main(a)
        self.assertEqual(list(a.prompts), ["synth"])
        self.assertFalse((self.out / "coding_universal.json").exists())
        self.assertIsNone(json.load(open(self.out / "instrument.json"))["universal"])
        self.assertIn(f"for synthetic control: {NSYNTH} checks, none flagged.\n", (self.out / "AUDIT_REPORT.md").read_text())

    def test_universal_flags_are_rated_grouped_and_read_more_like_any_other(self):
        a = UniAgent(rows=good_rows(), uflags={"UNIV-IDENT-04", "UNIV-IDENT-28"}); self.run_main(a, universal=True)
        self.assertEqual((len(a.imp_prompts), len(a.grp_prompts)), (1, 1))
        self.assertIn("Define the causal contrast", a.imp_prompts[0])
        rep = (self.out / "AUDIT_REPORT.md").read_text()
        self.assertIn(f"plus my general checks: {NSYNTH + len(univ_ids())} checks, 2 flagged, 1 critical.\n", rep)
        rows = table_rows(rep)  # F1 minor, F2 critical (ImportanceAgent's cycle); no consensus grade, so never Single source
        self.assertEqual([r.split(" | ")[0] for r in rows], ["| Critical", "| Minor"])
        self.assertTrue(rows[0].endswith("| UNIV-IDENT-28 |"), rows)
        self.assertIn("Read more: Holland (1986), pp. 946, 951, 954-955, 959, https://doi.org/10.2307/2289064\n", rep)
        self.assertIn(poa.UM.load_explainers()["UNIV-IDENT-28"]["why"], section(rep, "Details"))

    def test_universal_passes_are_not_listed_as_strengths(self):
        a = UniAgent(rows=flag_rows(tuple(range(NSYNTH)))); self.run_main(a, universal=True)  # every synth check flagged
        rep = (self.out / "AUDIT_REPORT.md").read_text()
        self.assertNotIn("## What the paper does well", rep)  # 28 universal passes, none praised
        b = UniAgent(rows=good_rows()); self.run_main(b, universal=True, out=self.tmp / "out2")
        well = section((self.tmp / "out2/AUDIT_REPORT.md").read_text(), "What the paper does well")
        self.assertEqual(len(well.strip().splitlines()), 3)
        self.assertNotIn("UNIV-", well); self.assertNotIn("separate from those used to develop it", well)

    def test_universal_alone_has_its_own_header(self):
        a = UniAgent()
        with mock.patch.object(poa, "run_agent", a), contextlib.redirect_stdout(io.StringIO()):
            poa.main(["--paper", str(self.paper), "--modules", "universal", "--out", str(self.out)])
        self.assertEqual(list(a.prompts), ["universal"])
        rep = (self.out / "AUDIT_REPORT.md").read_text()
        self.assertIn("None of the method checklists applies to this paper, so I read it against my general checks only: "
                      f"{len(univ_ids())} checks, none flagged.\n", rep)

    def test_a_failed_universal_coder_is_reported_like_a_module(self):
        class NoUniversal(UniAgent):
            def __call__(self, prompt, **kw):
                if "coding_universal.json" in prompt and "You are a methods referee" not in prompt and GROUP_MARK not in prompt:
                    self.calls.append(kw)
                    return proc("")
                return super().__call__(prompt, **kw)
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(io.StringIO()):
            self.run_main(NoUniversal(rows=good_rows()), universal=True)
        self.assertEqual(cm.exception.code, 2)
        rep = (self.out / "AUDIT_REPORT.md").read_text()
        self.assertIn("UNIVERSAL", rep.split("\n", 3)[2])
        self.assertIn("- Universal checklist: the coder failed", rep)


@unittest.skipUnless(CHECKLIST.exists(), "synth checklist not checked out (sparse worktree)")
class ReportVoiceTests(RunnerBase):
    """report(): header, strengths, the main issues, the table, details, closing lines. Text is deterministic."""
    def rep(self, rows, *extra, out=None):
        out = out or self.out
        self.run_main(ImportanceAgent(rows=rows), *extra, out=out)
        return (out / "AUDIT_REPORT.md").read_text()

    def test_header_sentence_and_disclaimer_last(self):
        rep = self.rep(flag_rows((0, 1)))
        self.assertTrue(rep.startswith("# AMICUS report: paper\n"))
        self.assertIn(f"I read your paper against the methods literature for synthetic control: {NSYNTH} checks, 2 flagged, 1 critical.\n", rep)
        self.assertLess(rep.index("I read your paper"), rep.index("- Synthetic control: selected by hand"))
        self.assertIn("What I could read: the main text (paper.txt), not the data or code. A flag means", rep)
        self.assertEqual(rep.rstrip().splitlines()[-1], report_spec.DISCLAIMER)
        self.assertTrue(rep.endswith(report_spec.DISCLAIMER + "\n"))
        self.assertEqual(rep.count(report_spec.DISCLAIMER), 1)
        self.assertIn("none critical.", self.rep(flag_rows((0,)), out=self.tmp / "out_minor"))  # F1 is rated minor

    def test_module_phrase(self):
        self.assertEqual(poa._module_phrase(["did"]), "difference-in-differences")
        self.assertEqual(poa._module_phrase(["did", "panel"]), "difference-in-differences and panel data")
        self.assertEqual(poa._module_phrase(["iv", "text", "hte"]), "instrumental variables, text as data, and heterogeneous treatment effects")
        self.assertEqual(poa._module_phrase(["not_a_module"]), "not_a_module")

    def test_does_well_is_three_passed_checks_high_first(self):
        checks = poa.load_checks(CHECKLIST)
        rep = self.rep(good_rows())
        sec = section(rep, "What the paper does well").strip().splitlines()
        want = sorted(checks, key=lambda c: poa.SEV_RANK.get(c.get("severity_if_flagged", "").upper(), 3))[:3]
        ex = explainer_text.load(CHECKLIST)
        self.assertEqual([x for x in sec if x], [f"- The paper {ex[c['check_id']]['done']}." for c in want])
        self.assertLess(rep.index("## What the paper does well"), rep.index("## Everything I flagged"))

    def test_does_well_skips_flagged_checks_and_is_omitted_when_none_passed(self):
        ids = synth_ids()
        ex = explainer_text.load(CHECKLIST)
        rep = self.rep(flag_rows((0,)))
        self.assertNotIn(ex[ids[0]]["done"], section(rep, "What the paper does well"))
        self.assertEqual(len(re.findall(r"^- The paper ", section(rep, "What the paper does well"), re.M)), 3)
        rep2 = self.rep(flag_rows(range(len(ids))), "--no-importance", out=self.tmp / "out_all_flagged")
        self.assertNotIn("What the paper does well", rep2)

    def test_details_paragraph_from_the_main_check(self):
        rep = self.rep(flag_rows((0, 1)))
        by_id = {c["check_id"]: c for c in poa.load_checks(CHECKLIST)}
        c = by_id[synth_ids()[1]]  # flag index 1: borderline, rated critical by the fake importance agent
        ex = explainer_text.load(CHECKLIST)[c["check_id"]]
        det = section(rep, "Details")
        self.assertEqual(det.count("### "), 1)  # the other flag is rated minor: table row only
        para = det.split("\n\n")[1]
        want = f"Paper does not report item 1. {ex['why']}"
        if c.get("author_guidance"):
            want += f" What you could add: {poa._sentence(c['author_guidance'])}"
        self.assertEqual(para, want + " It is a close call.")
        self.assertNotIn(c["claim"].strip(), det)  # the explainer's why, not the check's claim
        self.assertEqual(det.count("Read more:"), 1)
        self.assertIn(f"Read more: {poa.read_more(c, CHECKLIST)}\nChecks: {c['check_id']}", det)
        for old in ("*What I noticed:*", "How much it matters here", "What to fix", "Checks by module", "Modules audited"):
            self.assertNotIn(old, rep)

    def test_details_paragraph_leaves_out_absent_parts(self):
        c = {"check_id": "X-1", "severity_if_flagged": "HIGH", "requirement_statement": "R"}
        x = {"main": {"id": "X-1", "note": ""}, "borderline": False}
        self.assertEqual(poa._details_paragraph(x, c, {}), "R.")  # no note, no explainer, no claim: the requirement only
        c.update(claim="Because", author_guidance="Do this")
        x = {"main": {"id": "X-1", "note": "N"}, "borderline": True}
        self.assertEqual(poa._details_paragraph(x, c, {}), "N. Because. What you could add: Do this. It is a close call.")
        self.assertEqual(poa._details_paragraph(x, c, {"plain": "P.", "why": "W."}), "N. W. What you could add: Do this. It is a close call.")
        self.assertEqual(poa._details_paragraph({"main": {"note": ""}, "borderline": False}, {"requirement_statement": "R"}, {"plain": "P."}), "P.")

    def test_where_and_short_title(self):
        mee, plain, ptr = {"may_exist_elsewhere": True}, {}, {"may_exist_elsewhere": True, "pointer": "App. B"}
        self.assertEqual(poa._where("Table 3", [plain], True), "Table 3")
        self.assertEqual(poa._where("", [plain], True), "silent")
        self.assertEqual(poa._where("p.4", [plain, mee], True), "p.4; not seen")
        self.assertEqual(poa._where("p.4", [ptr, ptr], True), "p.4; not seen (App. B)")
        self.assertEqual(poa._where("silent", [ptr], True), "not seen (App. B)")
        self.assertEqual(poa._where("p.4; not seen (App. A)", [ptr], True), "p.4; not seen (App. A)")  # the call already said so
        self.assertEqual(poa._where("", [plain], False), "not located")
        self.assertEqual(poa._where("", [mee], False), "not seen")
        self.assertEqual(poa._short_title({"id": "X-1", "req": "The paper must report it."}), "The paper must report it")
        self.assertEqual(poa._short_title({"id": "X-1", "req": "one two three four five six seven eight nine ten, eleven"}),
                         "one two three four five six seven eight nine ten...")
        self.assertEqual(poa._short_title({"id": "X-1", "req": ""}), "X-1")

    def test_no_importance_run_keeps_the_details(self):
        rep = self.rep(flag_rows((0,)), "--no-importance")
        det = section(rep, "Details")
        self.assertIn("Paper does not report item 0.", det); self.assertIn("Read more:", det)
        self.assertIsNone(SEVERITY_WORDS.search(rep))

    def results(self, run_dir_has_explainers):
        """The synth checks with one flag and the rest passed, and the run_dirs to report them against: the shipping
        run, or an empty directory (no explainers.json) standing in for a run that has none."""
        checks = poa.load_checks(CHECKLIST)
        by = {c["check_id"]: {"check_id": c["check_id"], "in_scope": True, "verdict": "PASS", "note": "ok"} for c in checks}
        by[checks[0]["check_id"]] = {"check_id": checks[0]["check_id"], "in_scope": True, "verdict": "FLAG", "note": "Not reported."}
        rd = CHECKLIST if run_dir_has_explainers else self.tmp
        return checks, {"synth": (checks, by, [])}, {"synth": rd}

    def test_explainers_feed_the_strengths_and_details_and_a_run_without_them_falls_back(self):
        checks, results, rds = self.results(True)
        self.out.mkdir()
        poa.report(self.out, "p", [{"module": "synth", "why": "w"}], results, run_dirs=rds)
        with_ex = (self.out / "AUDIT_REPORT.md").read_text()
        ex = explainer_text.load(CHECKLIST)
        first = checks[0]["check_id"]
        self.assertIn(f"Not reported. {ex[first]['why']}", section(with_ex, "Details"))
        strengths = [l for l in section(with_ex, "What the paper does well").splitlines() if l]
        self.assertTrue(strengths and all(re.fullmatch(r"- The paper .+\.", l) for l in strengths), strengths)
        self.assertNotIn("SYNTH-", section(with_ex, "What the paper does well"))  # no check ids in prose
        # a run with no explainers.json (other instruments, a sparse checkout) falls back to the checklist's own text
        _, results2, rds2 = self.results(False)
        out2 = self.tmp / "out2"; out2.mkdir()
        poa.report(out2, "p", [{"module": "synth", "why": "w"}], results2, run_dirs=rds2)
        without = (out2 / "AUDIT_REPORT.md").read_text()
        self.assertIn(f"Not reported. {poa._sentence(checks[0]['claim'])}", section(without, "Details"))
        first_well = poa._does_well(results2)[0]
        req = next(c for c in checks if c["check_id"] == first_well[0])["requirement_statement"]
        self.assertEqual(first_well[1], f"The paper meets this requirement: {req}")
        self.assertIn(f"- {first_well[1]}", without)
        self.assertTrue(without.endswith(report_spec.DISCLAIMER + "\n"))

    def test_a_check_missing_from_a_present_file_falls_back_per_check(self):
        c = {"check_id": "X-1", "severity_if_flagged": "HIGH", "requirement_statement": "R", "claim": "Claim."}
        x = {"main": {"id": "X-1", "note": "N"}, "borderline": False}
        self.assertEqual(poa._details_paragraph(x, c, {}), "N. Claim.")
        self.assertEqual(poa._details_paragraph(x, c, {"plain": "The paper should P.", "why": "W.", "done": "d"}), "N. W.")
        self.assertEqual(poa._details_paragraph(x, c, {"plain": "The paper should P."}), "N. Claim.")  # no why: the claim stays
        res = {"x": ([c], {"X-1": {"verdict": "PASS", "in_scope": True}}, [])}
        self.assertEqual(poa._does_well(res, explainers={"x": {"X-1": {"done": "states it."}}}), [("X-1", "The paper states it.")])
        self.assertEqual(poa._does_well(res, explainers={"x": {"X-1": {"plain": "p"}}}), [("X-1", "The paper meets this requirement: R")])

    def test_a_damaged_explainers_file_does_not_stop_the_report(self):
        (self.tmp / "checklists").mkdir()
        (self.tmp / "checklists" / explainer_text.FILE).write_text("not json")
        with contextlib.redirect_stderr(io.StringIO()) as err:
            self.assertEqual(poa._explainers(self.tmp), {})
        self.assertIn("explainers ignored", err.getvalue())
        self.assertEqual(poa._explainers(None), {})

    def test_coders_never_see_the_explainers(self):
        a = ImportanceAgent(); self.run_main(a)
        prompt = (self.out / "prompt_synth.md").read_text()
        path = Path(re.search(r"`(\S*checklist_synth\.md)`", prompt).group(1))
        self.assertEqual(path, self.out / "checklist_synth.md")  # the coder reads this copy, not the shipped file
        shipped = (CHECKLIST / "checklists/SYNTH_CHECKLIST.md").read_text()
        given = path.read_text()
        self.assertIn("**In plain words:**", shipped)
        for label in (explainer_text.PLAIN_LABEL, explainer_text.WHY_LABEL):
            self.assertNotIn(f"**{label}:**", given)
        self.assertEqual(given, explainer_text.strip(shipped))
        self.assertEqual(given.count("### SYNTH-"), len(synth_ids()))  # every check is still there
        for e in explainer_text.load(CHECKLIST).values():
            self.assertNotIn(e["plain"], prompt + given); self.assertNotIn(e["why"], prompt + given)
        self.assertNotIn("In plain words", prompt)


class ExplainerTextTests(unittest.TestCase):
    def test_load_tolerates_absence_and_rejects_damage(self):
        d = Path(tempfile.mkdtemp())
        self.assertEqual(explainer_text.load(d), {}); self.assertEqual(explainer_text.load_path(d / "nope.json"), {})
        (d / "checklists").mkdir()
        f = d / "checklists" / explainer_text.FILE
        f.write_text(json.dumps({"explainers": [{"check_id": "A-1", "plain": " The paper\nshould x. ", "why": "Because.", "done": "does x"}]}))
        self.assertEqual(explainer_text.load(d), {"A-1": {"plain": "The paper should x.", "why": "Because.", "done": "does x"}})
        for bad in ("not json", "[]", '{"explainers": [{"plain": "x"}]}'):
            f.write_text(bad)
            with self.assertRaises(ValueError):
                explainer_text.load(d)

    def test_lines_strip_and_add_are_inverse(self):
        self.assertEqual(explainer_text.lines(None), [])
        self.assertEqual(explainer_text.lines({"plain": "P.", "why": "W.", "done": "d"}), ["**In plain words:** P.", "**Why it matters:** W."])
        self.assertEqual(explainer_text.lines({"why": "W."}), ["**Why it matters:** W."])
        base = "# T\n\n### A-1 \u2014 R\n\n**Scope:** `all` \u00b7 **Severity if flagged:** HIGH\n\n**Check:** o\n\n### A-2 \u2014 R2\n\n**Scope:** `all`\n\n**Check:** o2\n"
        added = explainer_text.add_to_checklist(base, {"A-1": {"plain": "P.", "why": "W."}})
        self.assertIn("**Scope:** `all` \u00b7 **Severity if flagged:** HIGH\n\n**In plain words:** P.\n\n**Why it matters:** W.\n\n**Check:** o", added)
        self.assertEqual(added.count("In plain words"), 1)  # A-2 has no entry
        self.assertEqual(explainer_text.strip(added), base)
        self.assertEqual(explainer_text.strip(base), base)
        self.assertEqual(explainer_text.add_to_checklist(base, {}), base)


class SourceOrderTests(unittest.TestCase):
    """doi_links.order_further_reading and the DOI map: the entry read_more() picks is the one the checklist lists first."""
    @staticmethod
    def fr(sid, pages="p. 1"):
        return {"source_id": sid, "cite": f"{sid}. (2001). T. J.", "short_cite": sid, "pages": pages, "pagination": "printed", "pdf_pages": [1]}

    @staticmethod
    def ev(sid, score):
        return {"source_id": sid, "short_cite": sid, "anchor_score": score}

    def test_evidence_rows_then_anchor_score_then_current_order(self):
        c = {"further_reading": [self.fr(x) for x in ("a", "b", "c", "d", "e")],
             "evidence": [self.ev("a", 0.9), self.ev("b", 0.9), self.ev("b", 0.8), self.ev("c", 1.0), self.ev("d", 0.7), self.ev("e", 0.7)]}
        self.assertEqual([f["source_id"] for f in doi_links.order_further_reading(c)], ["b", "c", "a", "d", "e"])
        self.assertEqual([f["source_id"] for f in c["further_reading"]], list("abcde"))  # the check itself is not reordered

    def test_missing_scores_and_sources_without_evidence_keep_their_place(self):
        c = {"further_reading": [self.fr("a"), self.fr("b"), self.fr("c")], "evidence": [{"source_id": "c"}]}
        self.assertEqual([f["source_id"] for f in doi_links.order_further_reading(c)], ["c", "a", "b"])
        self.assertEqual(doi_links.order_further_reading({"further_reading": [self.fr("a"), self.fr("b")]}), [self.fr("a"), self.fr("b")])
        self.assertEqual(doi_links.order_further_reading({}), [])

    def test_universal_strings_keep_their_order(self):
        s = ["Z. (2001). Zed.", "A. (2002). Ay."]
        self.assertEqual(doi_links.order_further_reading({"further_reading": s, "evidence": []}), s)

    def test_read_more_picks_the_most_relevant_entry(self):
        run = Path(tempfile.mkdtemp()).resolve()
        c = {"further_reading": [self.fr("a", "p. 4"), self.fr("b", "p. 9")], "evidence": [self.ev("b", 1.0)]}
        self.assertTrue(poa.read_more(c, run).startswith("b, p. 9"))

    def test_map_wins_over_config_and_covers_a_run_without_config(self):
        run = Path(tempfile.mkdtemp()).resolve() / "run_x"; run.mkdir()
        c = {"further_reading": [self.fr("a")]}
        with mock.patch.object(doi_links, "mapped_dois", return_value={"run_x/a": "10.1000/map"}):
            self.assertEqual(poa.read_more(c, run), "a, p. 1, https://doi.org/10.1000/map")
            (run / "config.json").write_text(json.dumps({"sources": [{"source_id": "a", "doi": "10.1000/cfg"}]}))
            self.assertEqual(poa.read_more(c, run), "a, p. 1, https://doi.org/10.1000/map")
        with mock.patch.object(doi_links, "mapped_dois", return_value={}):
            self.assertEqual(poa.read_more(c, run), "a, p. 1, https://doi.org/10.1000/cfg")

    def test_shipped_map_is_keyed_by_run_and_source(self):
        m = doi_links.mapped_dois()
        self.assertTrue(m)
        import universal_module as UM
        runs = set(poa.SHIPPING.values()) | {UM.RUN}
        for k, v in m.items():
            run, _, sid = k.partition("/")
            self.assertIn(run, runs, k); self.assertTrue(sid and v.startswith("10."), k)

    def test_every_shipped_check_reads_with_a_link_from_the_map_alone(self):
        """The public export has no config.json: with run_dois() empty, the map alone must give each check's first source its link."""
        for mod, run in poa.SHIPPING.items():
            rd = ROOT / "runs/skill_generation" / run
            if not (rd / "checklists/verified.anchored.json").exists():
                continue
            with mock.patch.object(doi_links, "run_dois", return_value={}):
                for c in poa.load_checks(rd):
                    line = poa.read_more(c, rd)
                    self.assertIn("https://doi.org/10.", line, c["check_id"])
                    self.assertNotRegex(line, r"p+\. -", c["check_id"])

    def test_universal_checks_read_with_the_same_link_from_the_map_alone(self):
        """The universal list ships beside SHIPPING: its read-more lines must not need the run's config.json either."""
        import universal_module as UM
        rd = ROOT / "runs/skill_generation" / UM.RUN
        if not (rd / "checklists/verified.anchored.json").exists():
            self.skipTest("universal checklist not checked out")
        checks = poa.load_checks(rd)
        self.assertEqual(len(checks), 28)
        linked = 0
        with mock.patch.object(doi_links, "run_dois", return_value={}):
            for c in checks:
                line = poa.read_more(c, rd)
                self.assertTrue(line, c["check_id"])
                linked += "https://doi.org/10." in line
        self.assertGreaterEqual(linked, 24)  # 24 of 28 on 20 Nov 2026; the other four first sources are books Crossref has no DOI for


class DocxTests(unittest.TestCase):
    def test_docx_text(self):
        d = Path(tempfile.mkdtemp()); f = d / "s.docx"
        w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        body = (f'<w:document xmlns:w="{w}"><w:body><w:p><w:r><w:t>First para</w:t></w:r></w:p>'
                f'<w:p><w:r><w:t>Second</w:t></w:r><w:r><w:tab/><w:t xml:space="preserve"> para</w:t></w:r></w:p></w:body></w:document>')
        with zipfile.ZipFile(f, "w") as z:
            z.writestr("word/document.xml", body)
        self.assertEqual(poa.read_docx(f), "First para\nSecond\t para")
        out, _ = poa.stage_paper([d / "m.txt" if (d / "m.txt").write_text("main") else None, f], d)
        self.assertIn("First para", out.read_text()); self.assertIn("SUPPLEMENT: s.docx", out.read_text())


class AgentCallTests(unittest.TestCase):
    def setUp(self):
        self.sleeps = []
        for p in (mock.patch.object(agent_call, "_sleep", self.sleeps.append), mock.patch.object(agent_call, "_log", lambda m: None)):
            p.start(); self.addCleanup(p.stop)

    def run_with(self, results, **env):
        it = iter(results); calls = []
        def once(cmd, prompt, cwd, timeout): calls.append(cmd); return next(it)
        with mock.patch.object(agent_call, "_once", once), mock.patch.dict(os.environ, env):
            r = agent_call.run_agent("p", agent="codex", cwd=Path("/tmp"), write_dir=Path("/tmp"))
        return r, calls

    def test_rate_limit_waits_and_retries_without_attempts(self):
        lim = proc("", "You've hit your usage limit. Try again at 3:15 PM.", 1)
        r, calls = self.run_with([lim, proc("", "HTTP 429 Too Many Requests", 1), proc("ok done")], AMICUS_RATE_LIMIT_SLEEP="7")
        self.assertEqual(r.stdout, "ok done"); self.assertEqual(len(calls), 3)
        self.assertEqual(self.sleeps, [7.0, 7.0]); self.assertEqual(r.rate_limit_waits, 2)

    def test_default_sleep_is_15_minutes(self):
        os.environ.pop("AMICUS_RATE_LIMIT_SLEEP", None)
        r, _ = self.run_with([proc("", "Claude AI usage limit reached|1760000000", 1), proc("fine")])
        self.assertEqual(self.sleeps, [900.0])

    def test_cap(self):
        lim = proc("", "rate limit exceeded", 1)
        r, calls = self.run_with([lim] * 50, AMICUS_RATE_LIMIT_SLEEP="3600")
        self.assertEqual(len(self.sleeps), 10); self.assertEqual(r.returncode, 1)

    def test_ordinary_failures_not_matched(self):
        for out, err, rc in [("", "Error: file not found", 1), ("", "timeout after 1800s", -9), ("x" * 900 + " rate limit", "", 0),
                             ("", "Traceback ... KeyError: 'verdict'", 1), ("Counts: PASS 10, FLAG 4, NA 2", "", 0)]:
            self.assertFalse(agent_call.is_rate_limited(proc(out, err, rc)), (out, err))
        for err in ["You've hit your limit · resets 3pm", "5-hour limit reached", "rate_limit_error", "You've hit your usage limit. Try again at 4:05 PM"]:
            self.assertTrue(agent_call.is_rate_limited(proc("", err, 1)), err)

    def test_commands(self):
        c = agent_call.build_command("claude", "claude-sonnet-5-5", "/o", "/o", None)
        self.assertNotIn("--add-dir", c); self.assertIn("Edit(//o/**)", c[c.index("--allowedTools") + 1])
        x = agent_call.build_command("codex", "gpt-6-luna", "/o", "/o", "high")
        self.assertEqual(x[:3], ["codex", "exec", "--ephemeral"]); self.assertIn("workspace-write", x)
        self.assertEqual(x[x.index("-C") + 1], "/o"); self.assertIn("model_reasoning_effort=high", x); self.assertEqual(x[-1], "-")


class ReadMoreTests(unittest.TestCase):
    """read_more(): the first further-reading entry as '<short_cite>, <pages>, https://doi.org/<doi>'.
    Fixtures are synthetic so the tests also pass where the runs carry no config.json."""
    def setUp(self):
        self.run = Path(tempfile.mkdtemp()).resolve()
        (self.run / "config.json").write_text(json.dumps({"sources": [
            {"source_id": "m_a_2001", "doi": "10.1000/cfg"}, {"source_id": "m_none", "doi": ""},
            {"source_id": "m_url", "doi": "https://doi.org/10.1000/url-form"}]}))

    @staticmethod
    def entry(sid="m_a_2001", cite="A. B. (2001) Title. Journal.", pages="pp. 532, 537"):
        return {"source_id": sid, "cite": cite, "short_cite": "A (2001)", "pages": pages, "pagination": "printed", "pdf_pages": [4]}

    def one(self, **kw):
        return poa.read_more({"further_reading": [self.entry(**kw)]}, self.run)

    def test_doi_from_config_by_source_id(self):
        self.assertEqual(self.one(), "A (2001), pp. 532, 537, https://doi.org/10.1000/cfg")
        self.assertEqual(self.one(sid="m_url"), "A (2001), pp. 532, 537, https://doi.org/10.1000/url-form")

    def test_doi_in_the_cite_wins_and_bare_doi_becomes_a_link(self):
        self.assertTrue(self.one(cite="A. (2001). T. https://doi.org/10.1000/incite").endswith(", https://doi.org/10.1000/incite"))
        self.assertTrue(self.one(cite='A et al. (2001). "T." DOI 10.1000/bare.').endswith(", https://doi.org/10.1000/bare"))

    def test_no_doi_known_means_no_link_and_none_is_invented(self):
        self.assertEqual(self.one(sid="m_none"), "A (2001), pp. 532, 537")
        self.assertEqual(self.one(sid="not_in_config"), "A (2001), pp. 532, 537")
        (self.run / "config.json").unlink()  # the public export has no config.json
        self.assertEqual(self.one(sid="m_a_2001"), "A (2001), pp. 532, 537")

    def test_impossible_pages_are_dropped(self):
        for pages, shown in [("p. -10", ""), ("pp. -21, -19", ""), ("pp. -3--2", ""), ("p. 0", ""), ("pp. -8, 61", "p. 61, "),
                             ("pp. -8, 61\u201364", "pp. 61\u201364, "), ("p. 445", "p. 445, "), ("pp. 436, 442", "pp. 436, 442, ")]:
            self.assertEqual(self.one(pages=pages), f"A (2001), {shown}https://doi.org/10.1000/cfg", pages)

    def test_first_entry_only_and_empty_when_none(self):
        two = {"further_reading": [self.entry(), self.entry(sid="m_url", pages="p. 9")]}
        self.assertEqual(poa.read_more(two, self.run), "A (2001), pp. 532, 537, https://doi.org/10.1000/cfg")
        self.assertEqual(poa.read_more({"further_reading": []}, self.run), "")

    def test_cite_is_unchanged_without_run_dir(self):
        c = {"further_reading": [self.entry(), self.entry(sid="m_url", pages="p. 9")]}
        self.assertEqual(poa.cite(c), "A (2001), pp. 532, 537; A (2001), p. 9")
        self.assertEqual(poa.cite(c, self.run), "A (2001), pp. 532, 537, https://doi.org/10.1000/cfg")
        ev = {"evidence": [{"short_cite": "B (2002)"}, {"short_cite": "A (2001)"}]}  # no further reading: old fallback
        self.assertEqual(poa.cite(ev), "A (2001); B (2002)")
        self.assertEqual(poa.cite(ev, self.run), "A (2001); B (2002)")

    def test_plain_string_entries_get_a_short_cite_and_no_link(self):
        art = "Joseph P. Simmons, Leif D. Nelson, & Uri Simonsohn. (2011). False-positive psychology. Psychological Science, 22(11), 1359\u20131366."
        book = "Gary King, Robert O. Keohane, & Sidney Verba. (1994). Designing Social Inquiry. Princeton University Press, chapters 2 and 4."
        self.assertEqual(poa.read_more({"further_reading": [art]}, self.run), "Simmons et al. (2011)")
        self.assertEqual(poa.read_more({"further_reading": [book]}, self.run), "King et al. (1994), chapters 2 and 4")

    def test_clean_pages(self):
        import doi_links
        for given, want in [("p. 445", "p. 445"), ("pp. 436, 442", "pp. 436, 442"), ("pp. 12\u201315", "pp. 12\u201315"), ("p. xii", "p. xii"),
                            ("p. -1", ""), ("p. 0", ""), ("pp. -3--2", ""), ("pp. 9\u20135", ""), ("pp. 3, 0, 7", "pp. 3, 7"), ("p. n/a", ""), ("", "")]:
            self.assertEqual(doi_links.clean_pages(given)[0], want, given)

    @unittest.skipUnless((ROOT / "runs/skill_generation" / poa.SHIPPING["measurement"] / "config.json").exists(), "run configs not checked out")
    def test_every_shipped_measurement_check_reads_with_a_link_and_sane_pages(self):
        run = ROOT / "runs/skill_generation" / poa.SHIPPING["measurement"]
        checks = poa.load_checks(run)
        for c in checks:
            line = poa.read_more(c, run)
            self.assertIn("https://doi.org/10.", line, c["check_id"])
            self.assertNotRegex(line, r"p+\. -", c["check_id"])


if __name__ == "__main__":
    unittest.main(verbosity=1)
