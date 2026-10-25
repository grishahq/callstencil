"""Offline, deliberately permissive issue server for the CallStencil demonstration.

Every received tools/call is recorded before server-side validation. A receipt proves
forwarding, not a real repository mutation. This fixture never accesses a repository.
"""

import argparse
import asyncio
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

ISSUE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "repository": {"type": "string"},
        "title": {"type": "string"},
        "labels": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["repository", "title", "labels"],
    "additionalProperties": False,
}


def schema_sha256(schema: dict[str, Any]) -> str:
    """Return the canonical JSON fingerprint used by the demo policy."""
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode()).hexdigest()


def demo_policy() -> dict[str, Any]:
    """Build the fixed policy shipped with this offline demonstration."""
    return {
        "version": 1,
        "rules": [
            {
                "id": "demo-issue",
                "tool": "create_issue",
                "input_schema_sha256": schema_sha256(ISSUE_SCHEMA),
                "arguments": {
                    "repository": {"equals": "grishahq/demo"},
                    "labels": {"items_in": ["bug", "docs"]},
                    "title": {"type": "string"},
                },
            }
        ],
    }


def create_server(receipts: Path, *, schema_drift: bool = False) -> Server[object]:
    """Create a recording server; the hidden tool remains callable directly."""
    app: Server[object] = Server("callstencil-offline-issues", version="1.0")
    schema = copy.deepcopy(ISSUE_SCHEMA)
    if schema_drift:
        schema["properties"]["title"]["maxLength"] = 120
    validator = Draft202012Validator(schema)
    sequence = 0

    @app.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_tools() -> list[types.Tool]:
        return [types.Tool(name="create_issue", inputSchema=schema)]

    async def call_tool(request: types.CallToolRequest) -> types.ServerResult:
        nonlocal sequence
        sequence += 1
        name = request.params.name
        arguments = request.params.arguments or {}
        if name == "delete_repository":
            outcome = "simulated_only"
        elif name != "create_issue":
            outcome = "unknown_tool"
        elif not validator.is_valid(arguments):
            outcome = "invalid_arguments"
        elif arguments["title"] == "SIMULATE_ERROR":
            outcome = "upstream_error"
        else:
            outcome = "simulated_only"
        # Values, metadata, and arbitrary upstream error strings never enter receipts.
        receipt = {"sequence": sequence, "tool": name, "outcome": outcome}
        receipts.parent.mkdir(parents=True, exist_ok=True)
        with receipts.open("a", encoding="utf-8") as output:
            output.write(json.dumps(receipt, sort_keys=True) + "\n")
        return types.ServerResult(
            types.CallToolResult(
                content=[types.TextContent(type="text", text=json.dumps(receipt, sort_keys=True))],
                isError=outcome in {"unknown_tool", "invalid_arguments", "upstream_error"},
            )
        )

    # Register the raw handler so malformed and unadvertised calls are observable.
    # Server.call_tool() would validate and reject them before our recording function.
    app.request_handlers[types.CallToolRequest] = call_tool
    return app


async def _run(receipts: Path, *, schema_drift: bool) -> None:
    app = create_server(receipts, schema_drift=schema_drift)
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def main() -> None:
    """Run the deterministic, local-only stdio issue fixture."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--schema-drift", action="store_true")
    args = parser.parse_args()
    asyncio.run(_run(args.receipts, schema_drift=args.schema_drift))


if __name__ == "__main__":
    main()
