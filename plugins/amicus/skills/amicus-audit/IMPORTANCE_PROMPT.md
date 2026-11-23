# Flag-importance prompt (template)

Fill the three placeholders, then give the result to a fresh subagent that reads the paper itself:

- `{paper}`: path to the paper text the coder read.
- `{flags}`: one line per flag, `F<n> Requirement: ... | Auditor note: ...`, numbered F1.. in coding order.
- `{out}`: the JSON path to write (`amicus_importance.json` next to `AMICUS_REPORT.md`).

---

You are a methods referee. Read the paper at `{paper}` in full. A structured audit has already found that the paper does NOT meet the checklist requirements listed below ("flags"); each flag gives the requirement and the auditor's note. Do not re-audit and do not look for other problems. Your only task is to judge, for each flag, how much that unmet requirement matters for the credibility of THIS paper's main result, given what the paper actually claims and how much of its argument rests on the analysis the flag concerns.

FLAGS:
{flags}

Use exactly these levels:
  critical   - if left unaddressed, the paper's main result cannot be trusted
  major      - materially weakens confidence in the main result or a central supporting result
  minor      - a real gap, but the main result would very likely survive fixing it
  negligible - immaterial for this paper (peripheral analysis, a formality, or effectively addressed elsewhere in the paper)

Write to `{out}` a JSON object: {"flags": [{"flag": "F1", "severity": "critical|major|minor|negligible", "why": "<one short clause>"}, ...]} with one entry per flag, in order. Write the file, then reply with the word done.
