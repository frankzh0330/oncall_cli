---
name: oncall-investigation
description: Routes and runs local oncall investigations through the oncall_cli registry. Use when the user reports an oncall, incident, production problem, missing or incorrect data, delay, inconsistency, or asks to investigate a root cause.
---

# Run an oncall investigation

## Workflow

1. Keep the user's original incident description unchanged.
2. From the repository root, run:

   ```bash
   PYTHONPATH=src python3 -m oncall_cli "<original incident description>"
   ```

3. Interpret the CLI status:
   - `needs_user_input`: ask only for the listed fields, append the answers to the original description, and rerun the command.
   - `no_matching_skill`: explain which system or symptom signals are missing and ask the user; do not select a skill manually.
   - `blocked_by_incomplete_skill`: report that routing succeeded but investigation did not run, then stop.
   - executable status: use the selected `skill_id` and `skill_version`; read `skills/<skill_id>/SKILL.md` and only its directly referenced files.
4. Follow the selected business skill exactly. Keep all external operations read-only and collect evidence for every conclusion.
5. Save and report the case path emitted by the CLI.

## Safety boundaries

- The Python registry is the only authority for selecting a business skill.
- Never turn routing evidence into root-cause evidence.
- Never invent metadata, table names, queries, tool results, or conclusions.
- Never execute DDL, DML, or other state-changing operations.
- Stop and ask when required metadata or access is unavailable.
