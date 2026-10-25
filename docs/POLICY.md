# Version 1 policy reference

```json
{
  "version": 1,
  "rules": [{
    "id": "demo-issue",
    "tool": "create_issue",
    "input_schema_sha256": "REPLACE_WITH_REVIEWED_SCHEMA_SHA256",
    "arguments": {
      "repository": {"equals": "grishahq/demo"},
      "title": {"type": "string"},
      "labels": {"items_in": ["bug", "docs"]}
    }
  }]
}
```

The placeholder digest intentionally makes this example invalid until replaced. Use the fixture policy emitted by the scenario command for a runnable example.

- Top-level `version` must be integer 1. `rules: []` is a valid deny-all policy.
- Rule `id` is a unique 1–128 character alphanumeric/dot/underscore/hyphen identifier. Each tool may have only one rule. `tool` is an exact name, with no wildcard syntax.
- `input_schema_sha256` is lowercase SHA-256 of the entire schema encoded as compact sorted-key UTF-8 JSON, `ensure_ascii=False`, finite values only. Compute with `mcp_proxy.policy.schema_digest`. Review schemas before approving a changed fingerprint; never automatically trust the latest digest.
- All keys in `arguments` are required; all other argument keys deny. Constraints on one argument are combined with AND. Each constraint must include at least one check.
- `equals` compares exact JSON values; booleans differ from numbers. Object equality is independent of key order.
- `items_in` requires an array, every item equal to an allowed JSON value. It permits an empty array; minimum lengths must be in the pinned server schema. It is not a string substring test.
- `type` is one of `object`, `array`, `string`, `number`, `integer`, `boolean`, `null`. Numeric booleans do not pass. JSON Schema integer semantics include integral floats.
- The server input schema also validates arguments. Unknown policy keys, duplicate JSON keys, duplicate tools/IDs, nonfinite numbers, conflicting constraints and bad fingerprints fail startup. Remote schema references are rejected; valid local references are permitted.

## Decision records

Fixed reasons: `allowed`, `tool_not_allowed`, `invalid_arguments`, `schema_mismatch`, `invalid_schema`, `argument_names_mismatch`, `argument_constraint_mismatch`. Integration failures report `schema_unavailable` or `audit_unavailable`. Records include the configured rule/tool identifier and observed schema hash where available, never argument content. Unknown requested tools appear as null. Use non-secret policy identifiers.

`allowed` means authorization passed, not execution succeeded. Only the downstream receipt demonstrates forwarding in the controlled scenario. A server can return an error after receipt. Application results are returned to the caller, including server-produced content; they are not copied into decision logs. There is no implicit content redaction on tool results.

Audit JSONL files are opened with append and restrictive 0600 permissions; final-component symlinks are rejected on platforms with O_NOFOLLOW. Keep their directories private. A missing/unwritable configured audit destination blocks calls. No configured audit path means no persisted decisions. Records do not include caller identity or time; this release does not provide centralized/tamper-resistant audit infrastructure.
