# CallStencil implementation plan

Base: sparfenyuk/mcp-proxy at 701a0453487d1b28c8f9806ee4863674c70210dd (MIT), inspected 2026-10-25.

1. Preserve upstream history, license and baseline transports. Add the CallStencil distribution and command while retaining upstream bridge commands. Record attribution and exact baseline.
2. Implement strict version 1 JSON policies: exact tool names, required argument constraints, schema fingerprints, default deny, unknown-field rejection, and value-free decision records. Enforce before tools/call forwarding. Scope v0.1 to stdio servers exposed over HTTP/SSE; reject policy use in unsupported reverse mode.
3. Add a packaged controlled issue server and scenario runner. Use actual subprocess stdio and Streamable HTTP, comparing unguarded and guarded calls with independent server receipts. Cover wrong repo/labels, hidden direct calls, malformed arguments, schema drift, server errors, and malformed policy startup.
4. Run upstream and new tests, independent review, clean wheel installation, reproducible scenario evidence and real report screenshots/charts. Fix observed failures.
5. Publish public grishahq/callstencil with v0.1.0 alpha release, immutable annotated tag, wheel/sdist/checksums and evidence bundle; read back public release and verify clean downloaded artifact installation.
6. Finish five English LinkedIn posts and five 3–5-post X threads, two generated concept assets, evidence images and complete metadata. Check character limits. Inspect publishing access, use shared lock/slots only if authenticated scheduling is possible, and record truthful prepared/scheduled/published states.

## v0.1 acceptance
- Upstream transport tests pass and install/run remains useful without policy under the compatibility command.
- CallStencil requires an explicit valid policy; unmatched calls deny before the server; discovery filtering is supplementary.
- Rules pin canonical input-schema SHA-256; changed schemas deny and have understandable reasons.
- Policy and argument errors fail closed; audit logs omit argument values, metadata, server output and arbitrary error strings.
- Offline demo proves allowed receipts and zero blocked receipts through real transport, without external accounts or API keys.
- Attribution, scope limits, quickstart, changelog and downloadable public release verified.
- Complete reviewable campaign; scheduling only if exact account and queue access can be verified.

## Roadmap and maintenance
v0.2: JSON/JUnit scenario checks in CI with configurable suites. v0.3: policy-change diff and schema drift workflows for two documented real servers. v0.1 includes a fixed JSON demonstration report, not the planned general CI suite.

Track upstream security/transport changes monthly and before each release; retain upstream remote, test before merging, pin reproducible release dependencies in uv.lock. Accept focused bug reports with minimal policy/server/schema reproduction. Never promise a security SLA. Release patches for confirmed enforcement bugs with regression tests. No OS sandbox, direct-server protection, identity delegation, generic filesystem-path guarantee or category-novelty claim.
