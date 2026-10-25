# Offline issue-server demonstration

Install CallStencil and run this fixed demonstration without an external account or API key:

```console
callstencil-scenarios --output ./demo-evidence
```

Choose a new or empty output directory. Open `demo-evidence/report.html` for the scenario
table and observed terminal transcript. `report.json` contains the individual expectations
and observations. A failed expectation exits with status 1; setup failure exits with status 2.

The runner starts real Python subprocesses. An MCP client speaks Streamable HTTP to
the compatibility proxy (`python -m mcp_proxy`) and to the guarded proxy
(`python -m mcp_proxy.guarded --policy ... --audit-log ...`). Both proxies start the same
packaged stdio fixture (`python -m mcp_proxy.demo_server --receipts ...`). Every paired
scenario sends identical tool names and arguments through both bridges. The drift case
starts a new server with an altered schema; the default-deny case starts a guard with
an empty rule list. A separate startup check supplies an unknown policy field.

The fixed suite expects **10 baseline server receipts, 2 guarded server receipts, and
8 blocked calls**. The two guarded receipts are the allowed issue and the deliberately
failing upstream call. The runner checks each call's receipt delta and error state,
so an aggregate count cannot hide a wrong forwarding decision.

The fixture deliberately records calls **before** validating their input schema.
Malformed baseline calls therefore produce a receipt and an upstream error. Wrong
repository and label values are valid schema inputs and the permissive baseline accepts
them. `delete_repository` is deliberately absent from discovery but callable directly
on the fixture, demonstrating why discovery filtering alone does not authorize calls.
All operations are simulated, including this hidden tool. A receipt proves the
server received a call; it does not represent a real repository mutation.

Receipts and decision logs omit argument values. `receipts.jsonl` combines server-written
records with their run/mode labels; `decisions.jsonl` combines the guard's actual audit
records. Per-process originals remain alongside them. `policy.json`,
`deny-all-policy.json`, and `invalid-policy.json` preserve the exact demonstration inputs.
The demonstration is fixed; a configurable CI/JUnit scenario framework is roadmap work.

To inspect the advertised schema or use the fixture manually:

```console
callstencil --policy examples/issue-policy.json --audit-log decisions.jsonl --port 8080 -- \
  python -m mcp_proxy.demo_server --receipts receipts.jsonl
```

Connect an MCP Streamable HTTP client to `http://127.0.0.1:8080/mcp`. The policy pins
the canonical schema digest, permits only `create_issue`, requires exactly `repository`,
`title`, and `labels`, restricts the repository to `grishahq/demo`, and permits label
items `bug` and `docs`. It does not authenticate clients, sandbox the child process,
or protect direct access to another server.
