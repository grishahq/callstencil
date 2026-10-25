"""Transport-level checks for boundary failures beyond predicate matching."""
from unittest.mock import AsyncMock

import pytest
from mcp import types
from mcp_proxy.audit import AuditLog
from mcp_proxy.mcp_server import MCPServerSettings
from mcp_proxy.policy import Policy, schema_digest
from mcp_proxy.proxy_server import create_proxy_server

SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False}


def policy():
    return Policy.from_dict({"version": 1, "rules": [{
        "id": "test", "tool": "allowed", "input_schema_sha256": schema_digest(SCHEMA),
        "arguments": {},
    }]})


def remote():
    client = AsyncMock()
    client.initialize.return_value = types.InitializeResult(
        protocolVersion="2025-03-26", capabilities=types.ServerCapabilities(tools=types.ToolsCapability()),
        serverInfo=types.Implementation(name="controlled", version="1"),
    )
    client.list_tools.return_value = types.ListToolsResult(tools=[types.Tool(name="allowed", inputSchema=SCHEMA)])
    client.call_tool.return_value = types.CallToolResult(content=[])
    return client


async def invoke(client, audit=None, meta=None):
    app = await create_proxy_server(client, policy=policy(), audit=audit)
    return await app.request_handlers[types.CallToolRequest](types.CallToolRequest(
        method="tools/call", params=types.CallToolRequestParams(name="allowed", arguments={}, _meta=meta),
    ))


async def test_audit_failure_prevents_forwarding():
    client = remote()
    audit = AsyncMock()
    # Writer is synchronous; deliberately fail immediately.
    def fail(record):
        raise OSError("sensitive-error")
    audit.write = fail
    result = await invoke(client, audit)
    assert result.root.isError
    assert "audit_unavailable" in result.root.content[0].text
    client.call_tool.assert_not_called()


async def test_schema_lookup_error_prevents_forwarding():
    client = remote()
    client.list_tools.side_effect = RuntimeError("SECRET")
    result = await invoke(client)
    assert result.root.isError
    assert "SECRET" not in str(result)
    client.call_tool.assert_not_called()


async def test_duplicate_schema_and_cursor_cycle_deny():
    for page in [
        types.ListToolsResult(tools=[types.Tool(name="allowed", inputSchema=SCHEMA)] * 2),
        types.ListToolsResult(tools=[], nextCursor="loop"),
    ]:
        client = remote()
        client.list_tools.return_value = page
        result = await invoke(client)
        assert result.root.isError
        client.call_tool.assert_not_called()


async def test_arbitrary_metadata_removed():
    client = remote()
    await invoke(client, meta={"authorization_override": "secret"})
    assert client.call_tool.call_args.kwargs["meta"] == {}


def test_audit_permissions_and_symlink(tmp_path):
    path = tmp_path / "audit.jsonl"
    audit = AuditLog(str(path))
    audit.write({"allowed": False, "reason": "tool_not_allowed"})
    assert path.stat().st_mode & 0o777 == 0o600
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(OSError):
        AuditLog(str(link))


async def test_omitted_arguments_allow_no_argument_tool() -> None:
    """A legal omitted argument object has the same behavior as an empty one."""
    client = remote()
    app = await create_proxy_server(client, policy=policy())
    request = types.CallToolRequest(
        method="tools/call", params=types.CallToolRequestParams(name="allowed"),
    )
    result = await app.request_handlers[types.CallToolRequest](request)
    assert not result.root.isError
    client.call_tool.assert_awaited_once_with(
        "allowed", {}, meta=None, progress_callback=None,
    )


def test_server_settings_preserve_positional_arguments() -> None:
    """Existing positional settings retain their meaning after policy is added."""
    settings = MCPServerSettings(
        "127.0.0.1", 8080, True, ["https://example.com"], ["Mcp-Session-Id"], "WARNING",
    )
    assert settings.stateless is True
    assert settings.allow_origins == ["https://example.com"]
    assert settings.expose_headers == ["Mcp-Session-Id"]
    assert settings.log_level == "WARNING"
    assert settings.policy is None
    assert settings.audit is None
