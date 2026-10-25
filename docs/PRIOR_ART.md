# Related work and scope — checked 2026-10-25

Per-call tool policies are established prior art. These primary project sources describe related systems; this is a scope comparison, not a competitive benchmark or an endorsement of untested guarantees.

| Project | Scope described in its own documentation | CallStencil v0.1 scope |
| --- | --- | --- |
| [ToolPermit](https://github.com/sunhao123456sun-svg/toolpermit) | Local stdio tool mediation with allow/ask/deny rules, exact one-time approvals, redacted audit storage and offline policy replay. | No approval workflow or stored-call policy replay. A small stdio-to-HTTP/SSE bridge with strict allow/deny argument rules and a fixed real-transport receipt suite. |
| [ToolHive](https://docs.stacklok.com/toolhive) | MCP server/skills management across desktop, CLI and Kubernetes, with containerized runtime controls, registry and gateway capabilities. | No container isolation, server catalog or enterprise identity platform. Retains the upstream mcp-proxy transport utility. |
| [AgentBarrier](https://pypi.org/project/agentbarrier/) | Policy gateway and approval control plane with durable action state, duplicate-execution controls and audit receipts around Python tools and MCP. | No idempotency or durable approval state. Decisions authorize forwarding; the controlled server receipt independently shows arrival. |

CallStencil's contribution is its focused fork experience: a required-policy entry point, exact-name/argument rules, reviewed input-schema fingerprints, value-free decision JSONL, and a reproducible comparison through the retained bridge. The fixture suite measures selected forwarding paths, not production security superiority. Similar features elsewhere are not claimed as new here.

See [ATTRIBUTION.md](../ATTRIBUTION.md) for upstream history, license and the motivating [mcp-proxy issue #270](https://github.com/sparfenyuk/mcp-proxy/issues/270).
