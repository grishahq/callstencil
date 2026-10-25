# CallStencil

**An MCP bridge with permissions you can test.** Public alpha v0.1.0.

CallStencil is an attributed fork of [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy). It retains the useful stdio/SSE/Streamable HTTP bridge and adds strict per-call policies for a stdio server exposed over HTTP or SSE. Rules check tool names, argument values and input-schema fingerprints **before** forwarding `tools/call`.

The included issue server is a controlled, offline fixture. It records receipt of calls; it never creates issues or deletes repositories on GitHub. No model key or external account is needed.

## Install and reproduce

Python 3.10+ and [uv](https://docs.astral.sh/uv/) are supported. Use an isolated environment: this fork and upstream share the `mcp_proxy` module.

```sh
git clone https://github.com/grishahq/callstencil.git
cd callstencil
git checkout v0.1.0
uv sync --frozen
uv run callstencil-scenarios --output .local-demo
```

Open `.local-demo/report.html`. Inspect `report.json`, `receipts.jsonl`, `decisions.jsonl` and `transcript.txt` to distinguish proxy denials, server receipt and server errors. The command exits nonzero if a receipt or error assertion fails. Scenarios use local subprocesses and real Streamable HTTP connections on loopback; no remote tool account is touched.

For a clean installation from the release wheel, download `callstencil-0.1.0-py3-none-any.whl` and `SHA256SUMS` from the [GitHub release](https://github.com/grishahq/callstencil/releases/tag/v0.1.0), verify the checksum, then:

```sh
uv venv .venv
uv pip install --python .venv/bin/python ./callstencil-0.1.0-py3-none-any.whl
.venv/bin/callstencil-scenarios --output demo-evidence
```

The wheel is self-contained for the fixture and runner. Registry publication is not required.

## Run the guarded bridge

The scenario run emits a validated `policy.json` pinned to the packaged fixture schema:

```sh
uv run callstencil --policy .local-demo/policy.json \
  --audit-log .local-demo/live-decisions.jsonl --host 127.0.0.1 --port 8096 -- \
  .venv/bin/python -m mcp_proxy.demo_server --receipts .local-demo/live-receipts.jsonl
```

Point an MCP client at `http://127.0.0.1:8096/mcp` (Streamable HTTP) or `/sse`. `callstencil` requires `--policy`; omitted, malformed or unknown configuration fails before server launch. Policies are loaded once at startup; restart to apply edits. The v0.1 command supports one stdio server per process. [Policy reference](docs/POLICY.md) explains the language and decision codes.

The compatibility `mcp-proxy` and `mcp-reverse-proxy` commands retain upstream transport behavior. **Without `--policy`, the compatibility bridge forwards calls without CallStencil policy enforcement.** See the preserved [upstream guide](docs/UPSTREAM_README.md) for bridge directions, named servers and outbound authentication. Policy use in URL/reverse mode is rejected by the CLI in v0.1.

## What the boundary covers

- Default deny for tools without an exact rule, even if called directly without discovery.
- Every declared argument is required; undeclared arguments deny. Allowed values and array items are explicit.
- Fresh input-schema lookup on every call; mismatched, unavailable or ambiguous schemas deny. This adds a round trip and a compatibility tradeoff.
- Value-free decision records: no argument values, arbitrary request tool names, metadata, server output or exception strings. A configured audit-write failure denies forwarding.
- Guarded calls strip arbitrary `_meta` and retain only a non-null protocol progress token. Discovery filtering helps usability; it is not the enforcement boundary.

This is **not an OS sandbox**. It does not protect direct access to the server, bind a rule to a human identity, restrict resources/prompts/other MCP methods, guarantee pathname safety, or establish that the server implements its advertised semantics. An input-schema digest detects declared schema changes, not a malicious or silently changed implementation. Schema lookup and forwarding are separate protocol operations: pin/review the actual server build as well. Audit files are local records, not tamper-proof logs. Third-party server stdout/stderr and upstream debug logs are outside the redacted decision-record contract. Bind to loopback by default; do not expose an unauthenticated bridge to untrusted networks.

## Evidence and development

```sh
uv sync --frozen
uv run pytest
uv run mypy src
uv build
```

[Recorded demo](evidence/demo/report.html), [methodology](docs/EXPERIMENT.md), [independent code review](docs/REVIEW.md), [changelog](CHANGELOG.md), and [implementation/roadmap](PLAN.md). Results describe a deterministic controlled fixture, not production security coverage or a latency benchmark.

v0.2 plans general JSON/JUnit scenario suites for CI. v0.3 plans policy diffs and schema-drift workflows for two documented servers. Monthly upstream checks and focused regression fixes are described in the plan. No security SLA is promised.

## Credits and license

MIT. Original copyright and Git history are preserved. Upstream baseline: `701a0453487d1b28c8f9806ee4863674c70210dd`. See [ATTRIBUTION.md](ATTRIBUTION.md) for precise prior art, retained behavior and modifications. Per-call MCP policy tools already exist; this project focuses on a small bridge and independently inspectable receipts, not category novelty.
