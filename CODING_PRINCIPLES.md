# Coding principles

This project follows an adapted, concise version of the [Karpathy-Michaels engineering rules](https://gist.github.com/sanchez314c/903f9ad360014cbdec9d914cf75e93b6). The source remains the authority; this file records the rules used for this repository.

## Before changing code

- Read each file before editing it and follow existing patterns.
- Define the desired outcome and state assumptions before implementation.
- Keep the change within the requested scope. Architectural changes require an explicit decision.
- Prefer the standard library and existing dependencies. Add a dependency only when it removes meaningful complexity.

## While implementing

- Write the smallest complete solution for the current requirement.
- Keep interfaces explicit and names clear. Add comments only for non-obvious constraints.
- Never guess external facts, paths, schemas, or API behavior. Inspect or ask.
- Treat user input, paths, commands, SQL, and secrets as security boundaries.
- Investigate root causes. Do not hide failures with plausible fallbacks.

## Before declaring completion

- Test behavior that matters, including failure and boundary cases. Target at least 80% coverage.
- Run the real entry point, not only unit tests.
- Review first for requirement compliance, then for code quality and security.
- Search changed files for unfinished implementation markers. An intentional product placeholder must be explicit in the report.
- Re-read the original goal and verify the observable outcome.
- Remove temporary artifacts and record functional changes in `CHANGELOG.md` and `IMPLEMENT.md`.

