# Attribution and baseline

CallStencil is an attributed derivative of [sparfenyuk/mcp-proxy](https://github.com/sparfenyuk/mcp-proxy), originally authored by Sergey Parfenyuk and its contributors, under the MIT license. The original LICENSE is preserved unchanged, as is upstream Git history. CallStencil modifications are maintained by grishahq under MIT.

Immutable upstream baseline: `701a0453487d1b28c8f9806ee4863674c70210dd` (mcp-proxy 0.13.0), inspected 2026-10-25. Local remote `upstream` points to the original repository. The baseline README is preserved in `docs/UPSTREAM_README.md`; original CI/container publishing definitions are archived in `docs/upstream-workflows/` and are not active publication targets.

Upstream already supplies stdio ↔ SSE/Streamable HTTP bridging, named stdio servers, progress forwarding, transport health checks and authentication options for outbound client connections. These are retained capabilities, not new CallStencil inventions.

CallStencil adds strict versioned argument policies, default-deny tools/call enforcement, schema pin checks, redacted decision JSONL, a required-policy command and an offline scenario runner with independent server receipts. The motivating [upstream issue #270](https://github.com/sparfenyuk/mcp-proxy/issues/270) proposes a neutral call authorization hook; its author d8joseph describes a Tenuo demonstration. We did not copy that demonstration or claim to originate per-call authorization. Tools such as ToolPermit, ToolHive and AgentBarrier also address related policy needs; no category novelty is claimed.

The distribution is named `callstencil`; the Python module remains `mcp_proxy` to keep changes focused. Do not co-install it with the original mcp-proxy distribution in the same environment because the modules and compatibility commands overlap.
