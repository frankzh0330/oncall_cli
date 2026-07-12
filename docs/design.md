# Local oncall agent design

## 1. Goal and boundary

The first version proves one complete control flow: accept a natural-language incident, discover skills, choose the correct skill, collect required context, and produce an evidence-backed report. It does not query ClickHouse or claim a root cause because the investigation workflow is intentionally not defined yet.

This narrow boundary makes routing and interaction testable before production credentials and platform-specific tools are introduced. It also prevents a convincing but unsupported diagnosis.

## 2. Overall flow

```text
User input
  -> normalize case context
  -> scan and validate skill manifests
  -> score routing candidates
  -> request required context
  -> load the selected SKILL.md
  -> produce and persist an evidence report
```

One agent owns this flow. A visible state machine is used instead of several cooperating agents because the initial case is sequential and small. This keeps decisions reproducible and makes failures easy to locate. Specialist agents can be added later behind the same evidence and state interfaces if parallel investigation becomes useful.

## 3. Skill contract and progressive loading

Each skill has two entry points:

- `skill.yaml` is the program contract. It declares identity, routing signals, required context, lifecycle status, and risk.
- `SKILL.md` is the agent procedure. It will contain investigation steps, evidence requirements, stop conditions, and tool instructions.

Scripts and reference material live in separate directories and are loaded only when a procedure needs them. This avoids parsing free-form Markdown during routing and prevents every schema or script from consuming context for unrelated incidents.

The example skill is marked `draft`. Its Markdown deliberately contains no invented tables, queries, or workflow. Selecting it proves routing only. The engine then stops with `blocked_by_incomplete_skill`, which distinguishes an unfinished procedure from a failed investigation.

## 4. Registry and routing

The registry scans `skills/*/skill.yaml`, validates required fields, checks that the directory and skill ID match, and records invalid entries without crashing the CLI. It stores the path to `SKILL.md` but does not read all procedures during discovery. Manifests intentionally use a small YAML subset containing only top-level strings and string lists. A short standard-library parser keeps the local CLI offline and dependency-free; nested YAML should be introduced only when the contract actually needs it.

The first router is deterministic. System matches carry three points and symptom matches carry two. A candidate needs both kinds of evidence to reach the threshold of five. This prevents a generic phrase such as "data is wrong" from being routed to ClickHouse without a CK signal.

Only one candidate above the threshold is selected. Equal top scores produce an ambiguity result instead of an arbitrary choice. Every score retains human-readable reasons, so routing can be tested and audited. When the skill set grows, semantic retrieval can supply candidates and a model can rerank them without changing `RouteDecision`.

## 5. Context collection and interaction

Routing and execution readiness are separate decisions. A user can identify a ClickHouse issue without initially knowing the environment or time range. The agent therefore selects the skill first, then asks only for required fields that remain missing.

Answers are stored both in typed case fields and in `user_supplied`. Re-running the engine with the same case preserves its ID and continues the same investigation. If a database, table, RDS location, or repository cannot be discovered later, the same rule applies: stop and ask rather than infer it.

## 6. State, evidence, and reports

The minimal states are intake, normalization, routing, context check, skill loading, user-input required, no matching skill, and incomplete skill. Explicit states solve two problems: the CLI can explain why work stopped, and later tool steps can be inserted without hiding control flow inside prompts.

Evidence is a first-class record with an ID, type, summary, source, and timestamp. The current case produces only routing evidence. A report separately records its conclusion and confidence. This prevents the statement "routed to a CK skill" from becoming the unsupported statement "CK data is wrong."

Each case is saved as JSON. Local persistence supports audit, replay, and later skill improvement without requiring a service or database. The runtime directory is ignored by Git so incident data is not committed accidentally.

## 7. Future tool gateway

MySQL, ClickHouse, TCC, and repository access should enter through one tool gateway. Each call should declare its purpose, target, timeout, result limit, and evidence output. SQL must be parsed as read-only rather than accepted by a string-prefix check. ClickHouse queries also need scan limits. Responses should redact secrets and sensitive columns.

This boundary stops skills from opening arbitrary connections and gives every source the same audit shape. The current version does not create empty clients because unused interfaces would encode guesses about internal systems.

## 8. Metadata improvement

Platform metadata will map services to repositories, environments, data sources, CK tables, and TCC namespaces. When a user supplies missing metadata, the current case may use it immediately, but the value should first become a candidate with source, timestamp, and confidence.

A read-only existence check should validate the candidate. Conflicts require user review. Only confirmed candidates enter the versioned catalog. This allows the system to learn from investigations without silently replacing trusted mappings with one-off answers.

## 9. Skill lifecycle

Skills move through `draft`, `validated`, `published`, and `deprecated`. A successful generic investigation may generate a draft, but publication requires removing case-specific values, verifying read-only behavior, testing route examples, and replaying the procedure with safe fixtures.

Human publication is intentional. Automatic drafting reduces repeated work; review prevents a mistaken investigation from becoming permanent operating procedure. Versioned manifests allow reports to identify the exact procedure used and make rollback possible.

## 10. Growth path

1. Complete the CK skill procedure using mock tool results and route cases.
2. Add a read-only ClickHouse adapter behind the tool gateway.
3. Add the metadata catalog and candidate-validation loop.
4. Add more skills and measure routing conflicts before adding semantic retrieval.
5. Add model-assisted planning only where deterministic routing and procedures cannot express the decision.

This order keeps each new capability observable and testable. It also delays infrastructure until a real investigation requires it.
