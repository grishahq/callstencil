# CallStencil v0.1.0 — public alpha

CallStencil retains mcp-proxy's useful stdio/SSE/Streamable HTTP bridge and adds explicit per-call policies for a stdio server exposed over HTTP/SSE. For example, a create_issue rule can require a selected repository and allowed labels before the call reaches the server.

## Included

- Strict version 1 JSON policies, exact tool names and argument keys, default deny and pinned input-schema SHA-256.
- Enforcement before tools/call forwarding, including direct calls to undiscovered tools; discovery filtering is supplementary.
- Redacted decision JSONL, denied forwarding on configured audit-write failures, guarded metadata stripping and required-policy callstencil command.
- Packaged controlled issue server and offline scenario runner using real Streamable HTTP, proxy subprocesses and downstream stdio receipts.
- Upstream compatibility commands, attribution, original MIT license and history retained. An inherited broken reverse-command alias is repaired.

## Reproduce

Download the wheel and SHA256SUMS, verify the checksum, then:

```sh
uv venv .venv
uv pip install --python .venv/bin/python ./callstencil-0.1.0-py3-none-any.whl
.venv/bin/callstencil-scenarios --output demo-evidence
```

Open demo-evidence/report.html and inspect report.json, receipts.jsonl, decisions.jsonl and transcript.txt. No model key or GitHub account is needed. Use a separate environment from upstream mcp-proxy because both distributions share the mcp_proxy module. Alternatively clone this repository, checkout v0.1.0, and run uv sync --frozen.

## Validation and limits

179 tests pass locally; mypy passes. GitHub CI passed tests, types, builds and clean wheel scenarios on Python 3.10, 3.11 and 3.13: https://github.com/grishahq/callstencil/actions/runs/40225039440

The fixed demo passes 11 scenarios. Ten paired calls produce 10 baseline receipts and 2 guarded receipts; eight denied calls produce zero downstream receipts. The two guarded receipts are an approved call and an intentionally failing allowed call. Malformed baseline calls arrive before fixture validation. Receipts measure arrival, not successful mutations; all operations are simulated.

Public alpha, not a production security certification. Policy covers tools/call through this proxy. No OS sandbox, direct-server protection, generic filesystem-path guarantee, caller-identity delegation or protection from silently changed server semantics. Schema lookup and forwarding are separate operations. Prompt/resource/other MCP methods remain outside the policy boundary. See docs/POLICY.md, docs/EXPERIMENT.md and docs/REVIEW.md.

## Attribution and assets

Based on sparfenyuk/mcp-proxy at 701a0453487d1b28c8f9806ee4863674c70210dd by Sergey Parfenyuk and contributors (MIT). Per-call authorization has prior art; see ATTRIBUTION.md and upstream issue #270. No category novelty or adoption claims.

Assets: Python wheel, source distribution, offline evidence archive and SHA256SUMS. No PyPI/npm or container registry publication. v0.2 plans JSON/JUnit scenario checks; v0.3 plans policy diffs and documented server drift workflows.
