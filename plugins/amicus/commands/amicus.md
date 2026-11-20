---
description: Audit a paper's methods against the AMICUS checklists and write AMICUS_REPORT.md
argument-hint: <paper.pdf> [appendix.pdf ...]
allowed-tools: Read, Write, Glob, Grep, Agent, Task
---

Run the AMICUS paper audit on: $ARGUMENTS

Treat each path in the arguments as part of one paper: the first is the main text, any others
are appendices or supplements. If no path was given, ask for one and stop. If a path cannot
be read, say so and stop; do not audit from memory or from a different file.

Then follow the `amicus-audit` skill from this plugin exactly: Step 1 route, Step 2 code every
check of every fired module from its bundled checklist, Step 3 rate each flag's importance (write the flags to a file and run `IMPORTANCE_PROMPT.md` in a subagent that reads the paper itself, validate its `amicus_importance.json`, and state in the report header whether a subagent or a separate pass did it),
Step 4 write `AMICUS_REPORT.md` in the directory of the main paper, following the bundled `REPORT_GUIDE.md` exactly. Code every check; do not stop early to save space. When the
report is written, give a short summary in the chat (modules fired, the main issues, the
report path, and any "not completed" line).
