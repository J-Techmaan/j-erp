# Project Rules

These are persistent default rules for this repository. Follow them for every future task unless the user's current prompt explicitly overrides a rule.

## Language / UI

- All user-facing UI must be Korean-first.
- Use natural Korean for buttons, labels, menus, messages, validation, errors, dates, and notifications.
- Korean is the default product language even when the user's prompts are written in English.
- Code, identifiers, filenames, APIs, DB fields, comments, and technical internals should normally use English.
- Do not change the Korean-first UI unless explicitly requested.

## Work Style

- Act directly on project files.
- Prefer implementation over explanation.
- Read only files relevant to the current task.
- Do not repeatedly scan the entire repository unless necessary.
- Reuse existing architecture, components, utilities, and patterns.
- Make the smallest correct change needed.
- Do not refactor unrelated code.
- Do not create unnecessary files, docs, examples, or tests.
- Do not add dependencies unless needed.
- Do not ask questions when a safe, reasonable implementation can be inferred.

## Token / Context Efficiency

- Minimize token usage.
- Keep reasoning and progress output minimal.
- Do not paste source files into chat.
- Do not show diffs unless requested.
- Do not repeat code already present in files.
- Avoid unnecessary repository-wide searches.
- Avoid rereading unchanged files when possible.
- Keep terminal output concise.
- Do not run expensive or broad tests when targeted checks are sufficient.

## Implementation

- Modify/create files directly.
- Preserve existing project conventions.
- Keep code simple, modular, and maintainable.
- Avoid overengineering.
- Fix obvious errors caused by your changes.
- For UI changes, preserve responsive behavior and Korean text rendering.

## Validation

- Run only relevant lint/type/build/tests after changes.
- Prefer targeted validation first.
- Expand validation only when necessary.
- Do not repeatedly rerun successful checks without reason.

## Response

After completing a task, do not explain the implementation unless requested.

Reply briefly using Korean:

- 완료
- 변경 파일: ...
- 검증: ...
- 문제: ... (only if applicable)

Keep the response under 5 lines whenever practical.

## Priority

Correct implementation > project consistency > token efficiency > explanation.

<!-- BEGIN AWS Agent Toolkit rules -->
# AWS Guidance
- Where these AWS rules conflict with the project's own instructions, the
  project's instructions take precedence.
- Prefer the AWS MCP Server for AWS interactions — it provides sandboxed
  execution, observability, and audit logging. If unavailable, use the
  AWS CLI directly.
- Before starting a task, check whether a relevant AWS skill is available.
  Load the skill with `retrieve_skill` and prefer its guidance over
  general knowledge.
- When uncertain about specific AWS details (API parameters, permissions,
  limits, error codes), verify against documentation rather than guessing.
  State uncertainty explicitly if you cannot confirm.
- When creating infrastructure, prefer infrastructure-as-code (AWS CDK or
  CloudFormation) over direct CLI commands.
- When working with infrastructure, follow AWS Well-Architected Framework
  principles.
- Do not use em dashes in AWS resource names or descriptions. Use
  hyphens instead.
## Secret Safety

- MUST load the `aws-secrets-manager` skill first for any secret,
  credential, API key, token, or password task. MUST NOT call
  `secretsmanager get-secret-value` or `batch-get-secret-value`, and MUST
  NOT hit the Secrets Manager Agent daemon directly. MUST use
  `{{resolve:secretsmanager:secret-id:SecretString:json-key}}` with
  `asm-exec` so the secret resolves at runtime without entering context.
<!-- END AWS Agent Toolkit rules -->
