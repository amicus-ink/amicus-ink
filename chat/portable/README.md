# AMICUS in ChatGPT or Gemini

The same audit as the claude.ai skill, packaged for the other chat services. `AMICUS_INSTRUCTIONS.md`
is the instruction text (4,872 characters, under ChatGPT's 8,000 limit); the `*_CHECKLIST.md`
files are the 14 method checklists and the universal checklist (2025 instrument; they sit next to this file inside `amicus-audit-portable.zip`, and in `../amicus-audit/checklists/` in this repository), `IMPORTANCE_PROMPT.md` is the flag-importance step, and `REPORT_GUIDE.md` is the report step.

## ChatGPT: build a Custom GPT once, share the link

1. ChatGPT -> Explore GPTs -> Create -> Configure (needs a paid plan to create; anyone can use it).
2. Name: AMICUS Audit. Instructions: paste the whole of `AMICUS_INSTRUCTIONS.md`.
3. Knowledge: upload the 15 `*_CHECKLIST.md` files, `IMPORTANCE_PROMPT.md` and `REPORT_GUIDE.md`. Turn on Code Interpreter and File Search.
4. Conversation starter: "Audit this paper with AMICUS." Save and share the link.

Then anyone opens the GPT, attaches a PDF, and types the starter. Caveat: ChatGPT reads knowledge
files in retrieved chunks, not whole, so a long checklist (measurement, 62 checks) may come back
incomplete; the instructions ask the model to list every check id first, and the report's
"Not completed" section names any check or module it could not finish.

## Gemini: build a Gem once, share the link

1. Gemini -> Gems -> New Gem. Name: AMICUS Audit. Instructions: paste `AMICUS_INSTRUCTIONS.md`.
2. Add files: upload the 15 `*_CHECKLIST.md` files, `IMPORTANCE_PROMPT.md` and `REPORT_GUIDE.md` (Gemini reads them in full).
3. Save; share the Gem link. Users attach a PDF and type "Audit this paper with AMICUS."

## Any chat, nothing to build

Attach six things to one message: the PDF, `AMICUS_INSTRUCTIONS.md`, `IMPORTANCE_PROMPT.md`, `REPORT_GUIDE.md`, `UNIVERSAL_CHECKLIST.md` (it runs on every paper), and the checklist file for
the paper's method (if unsure, attach the instructions and the PDF first and ask "which AMICUS
modules does this paper fire?", then attach the ones it names). Type "Audit this paper with AMICUS."
This works in ChatGPT, Gemini, and claude.ai without any setup.

## Notes

Fidelity is the model's: the checklists and rules are identical across services, the coder is not,
so verdicts from different services are not interchangeable with the working paper's (which uses
one fixed coder). The audit spends the user's own subscription on that service. Rebuild with
`scripts/skillgen/build_chat_skill.py` when the checklists change.
