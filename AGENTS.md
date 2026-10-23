# Repository Agent Guidance

## Blackboard Learn API Work

Apply this section whenever a task validates, changes, or tests Blackboard Learn REST API behavior. The specialized [Blackboard API Expert](.github/agents/blackboard-api-expert.agent.md) follows the same workflow; these instructions make its core context available to any agent.

### Sources of Truth

- Published OpenAPI document: https://devportal-docstore.s3.amazonaws.com/learn-swagger.json
- Local integration: the installed `bblearn` dependency, especially `blackboard.api_extended`, its models, exceptions, and request implementation.
- Application behavior and tests in `blackboard_sync/` and `tests/`.
- The OpenAPI document is authoritative for documented endpoints and schemas. The installed client is authoritative for the behavior this project actually invokes. Do not assume the published spec, a particular Blackboard tenant, and the installed client version are interchangeable.

### Validation and Changes

1. Trace the relevant application call through `bblearn`. Establish the HTTP method, path, parameters, authentication expectations, response shape, pagination behavior, and relevant errors.
2. Inspect the relevant operation and schema in the OpenAPI document. If it cannot be accessed or does not describe the operation, state that limitation and do not invent contract details. Separate confirmed facts from assumptions and tenant-specific behavior.
3. Compare the contract and client behavior with application models, parsing, filtering, error handling, and existing tests. Determine whether the mismatch belongs to this project or the external dependency before editing.
4. Make the smallest justified correction in the owning application layer. Keep changes limited to API integration and directly related tests. Mock network calls in tests rather than contacting real Blackboard instances.
5. Run the narrowest relevant tests first, for example `pipenv run pytest tests/test_content.py -q`, then broaden testing when shared API behavior is affected.
6. Report the contract checked, local behavior found, changes made, tests run, and unresolved uncertainty. Cite the relevant OpenAPI operation/schema and local code where practical.

### Boundaries

- Do not claim behavior is documented unless it was verified in the OpenAPI source.
- Do not make speculative changes to `bblearn` or university-specific settings to mask an application bug. Explain upstream dependency mismatches and prefer a safe application-side remedy; do not change dependency versions without the user's direction.
- Do not expose, log, or request real credentials, cookies, tokens, or student data. Do not run authenticated or mutating requests against a live Blackboard instance without explicit user direction.
- If the OpenAPI document and installed client disagree, explain the discrepancy and impact before choosing a workaround. Do not silently redefine the API contract.