# Integration review — 2026-10-25

This is a separate implementation review by another agent working on CallStencil, not an external audit or a claim of complete security coverage. The reviewer authored the policy engine, so this review concentrates on integration code written by the parent agent.

## Scope and method

Reviewed `src/mcp_proxy/proxy_server.py`, `audit.py`, `__main__.py`, `mcp_server.py`, and `guarded.py`, together with boundary, CLI, proxy, transport and progress-forwarding tests. Read the complete request-forwarding paths, checked the upstream diff, ran focused tests and directly reproduced the issues below without changing runtime source.

The focused integration run passed **99 tests**, with three existing MCP client deprecation warnings. Checks covered audit-write failure, schema lookup errors, duplicate schemas, cursor cycles, metadata filtering, private audit-file permissions and symlink rejection, plus baseline transport behavior. An earlier run overlapped a metadata-filter fix and failed its existing regression; the rerun against the corrected code passed.

## Findings at initial review

1. **P2 — omitted arguments deny valid no-argument tools.** In `proxy_server.py`, `_call_tool` passes `req.params.arguments` directly into policy evaluation but later normalizes it to `{}` for forwarding. MCP models omitted arguments as `None`. An allowed no-argument tool with object schema and policy `arguments: {}` therefore returns `CallStencil denied: invalid_arguments`, with zero upstream calls, when a client omits arguments. Normalize the optional argument object once before evaluation and forwarding. Add an integration regression using `CallToolRequestParams(name="allowed")`.

2. **P2 — new settings fields change existing positional constructor meaning.** `MCPServerSettings` places `policy` and `audit` before the existing `stateless` field. The formerly valid `MCPServerSettings("127.0.0.1", 8080, True)` now sets `policy=True` and `stateless=False`; tool requests enter the policy path with a boolean and fail. Append the new fields after existing fields or make only the new fields keyword-only, and test the old positional constructor.

3. **P2 — inherited reverse-command entry point remains broken.** The retained `mcp-reverse-proxy` console script points to `mcp_proxy.__main__:client`, but that function is absent. Running `uv run mcp-reverse-proxy --help` raises `ImportError`. This predates the fork, but the new distribution still exposes the broken command. Point the compatibility entry point at `main` or implement a wrapper, then exercise the installed console command.

All three findings were fixed by the parent agent and rechecked on 2026-10-25. `test_omitted_arguments_allow_no_argument_tool` verifies omission forwards exactly one authorized call with `{}`; `test_server_settings_preserve_positional_arguments` verifies the six original positional fields and absence of a policy/audit by default. The focused integration suite including these regressions passed 99 tests. `uv run mcp-reverse-proxy --help` now exits successfully and displays help after its entry point was changed to `main`. No review finding remains open within this scope.

## Enforcement and redaction observations

No concrete fail-open tool forwarding path was found in the reviewed integration. Calls resolve fresh tool schema pages before evaluation; missing schemas, duplicate names, lookup errors and cyclic pagination deny. Calls denied by policy and calls encountering audit-write failures return before the upstream `call_tool` invocation. Discovery filtering is supplementary: direct calls still pass through the same enforcement handler.

The guarded entry point requires an explicit policy, rejects unsupported reverse transport mode and named-server mode, and loads policy/audit configuration before starting the server. The compatibility entry point preserves intentional unguarded operation when no policy is requested. Arbitrary tool-call metadata is removed in guarded mode, apart from a non-null protocol progress token. Decision audit records contain fixed reason codes, policy-owned identifiers and schema digests; exception text is not copied into these records. Guarded tool-call exceptions return a fixed error message.

## Limits

This review did not establish protection against a malicious upstream server, tool implementation behavior changes behind an identical schema, schema-check/call races, direct access to the upstream process, OS-level access, authentication or authorization of clients, or denial of service. Policy covers `tools/call`; prompt, resource, completion and notification forwarding remain outside that policy boundary. Server results, stdio stderr and ordinary diagnostic logs are not covered by the decision-audit redaction guarantee. Audit writes are flushed before forwarding but are not an fsync-backed transactional execution ledger. No external service, credentialed account, production deployment, release artifact or published security scan was assessed here.
