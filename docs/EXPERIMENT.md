# Receipt experiment — 2026-10-25

Question: do calls denied by the policy reach the controlled stdio server?

## Method specified by the suite

The packaged scenario list declares expected error states and receipt deltas before execution. The runner launches proxy subprocesses on free loopback ports and a separate controlled stdio server behind each proxy. An MCP ClientSession connects through real Streamable HTTP; it does not call the policy predicate directly. After every sequential call, the runner reads the fixture's independent JSONL receipt file and checks its delta. It checks client error state separately. Any mismatch exits nonzero.

The ten paired calls are approved issue, wrong repository, forbidden label, direct hidden tool, extra argument, missing argument, wrong type, intentional upstream error, schema drift and empty-policy default deny. The first eight use the same fixture schema. Schema drift restarts the fixture with a changed title schema while keeping the policy digest fixed; default deny restarts the guard with an empty rule set. An eleventh startup scenario supplies an unknown policy key and requires failure before a server receipt.

Baseline is the fork's retained compatibility `python -m mcp_proxy` path with policy absent, based on immutable upstream commit `701a0453487d1b28c8f9806ee4863674c70210dd`. Guarded is the same bridge with the CallStencil entry point, explicit policy and audit destination. These are controlled modes in the same build, not two independently configured commercial products. Test calls and the server implementation are identical within each pair.

## Observed results

`evidence/demo/report.json` records PASS for all 11 scenarios. Across the 10 paired calls, baseline server receipts total 10 and guarded receipts total 2. The approved issue and intentionally erroring allowed call each arrived. The other eight guard calls returned errors and had zero receipts. Invalid policy startup separately had no receipt. Every per-case observation is included; aggregate totals alone are not the acceptance check.

The fixture writes a receipt before validating its arguments. Thus malformed baseline calls reached the server and then failed schema validation; receipts do not imply successful actions. All destructive-sounding tools are harmless fixtures and make no GitHub mutation. The hidden tool was absent from discovery in both modes, yet the unguarded direct call arrived—showing why hiding names alone is insufficient.

## Reproduce and inspect

```sh
uv sync --frozen
uv run callstencil-scenarios --output .local-demo
```

Use a new empty output directory. Inspect `report.html`, `report.json`, `transcript.txt`, `receipts.jsonl` and `decisions.jsonl`. Original per-process files are preserved beside combined redacted artifacts. No API key, model call or external tool account is involved. Clean installed wheel reproduction is also recorded in `evidence/clean-install.txt`.

`campaign/assets/demo-report.png` is a headless browser screenshot of the generated report, not AI-generated UI. `scripts/render_evidence.cjs` reproduces it with Playwright. `campaign/assets/receipts-comparison.png` plots the ten observed pairs using `scripts/plot_receipts.py` and matplotlib; invalid-policy startup is intentionally excluded because it has no baseline call. Concept illustrations are separately labeled in campaign provenance.

## Limits

This deterministic fixture measures forwarding behavior for these cases, not production attack coverage, human debugging time, latency, throughput or adoption. One controlled server cannot establish correctness for filesystem semantics or third-party issue-server implementations. It does not test external identity management, direct server access or malicious server behavior. Advertised schema pinning cannot bind implementation semantics, and schema lookup plus call is not atomic. Unit/boundary tests add malformed configuration, schema lookup failures, ambiguous/paginated schemas, audit failures, no-argument compatibility and metadata stripping; they are a different layer of evidence from the subprocess experiment.
