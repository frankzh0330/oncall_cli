# Oncall investigation workflow

## Trigger

When the user reports an oncall, production incident, missing or incorrect data, delay, inconsistency, or asks to investigate a cause, use the `oncall-investigation` project skill.

## Required behavior

1. Preserve the user's original incident description verbatim.
2. Follow `.claude/skills/oncall-investigation/SKILL.md`.
3. Run the Python entrypoint so the project registry scans and selects from `skills/*/skill.yaml`:

   ```bash
   PYTHONPATH=src python3 -m oncall_cli "<original incident description>"
   ```

4. Do not choose a business skill by guessing or bypass the Python registry.
5. Ask the user for context that the CLI reports as missing, then rerun with the supplied context included.
6. Read only the selected business skill's `SKILL.md` and directly referenced files.
7. Treat `draft`, `blocked_by_incomplete_skill`, missing tools, and missing metadata as stop conditions. Never invent queries, evidence, or a root cause.
8. External investigation must remain read-only and must preserve evidence. Do not run data-changing SQL or expose credentials.

## Project commands

- One-shot investigation: `PYTHONPATH=src python3 -m oncall_cli "<incident>"`
- Interactive mode: `PYTHONPATH=src python3 -m oncall_cli`
- Tests: `PYTHONPYCACHEPREFIX=/tmp/oncall-cli-pycache PYTHONPATH=src python3 -m pytest -q -p no:cacheprovider`

The CLI report is authoritative for routing state. A successful route does not mean an investigation ran or a root cause was found.
