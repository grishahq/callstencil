"""Run the fixed offline demonstration over real stdio and Streamable HTTP.

This is a reproducible demonstration, not a general-purpose scenario framework.
Independent server receipts prove whether each request crossed the policy boundary.
"""

import argparse
import asyncio
import html
import json
import logging
import socket
import sys
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import McpError

from .demo_server import demo_policy


@dataclass(frozen=True)
class Scenario:
    """One fixed request and its independently specified expectations."""

    id: str
    description: str
    tool: str
    arguments: dict[str, Any]
    guarded_receipts: int = 0
    baseline_error: bool = False


def _scenarios() -> list[Scenario]:
    valid = {"repository": "grishahq/demo", "title": "Demonstration issue", "labels": ["bug"]}
    return [
        Scenario("allowed", "Approved issue", "create_issue", valid, guarded_receipts=1),
        Scenario(
            "wrong_repository",
            "Repository outside the rule",
            "create_issue",
            {**valid, "repository": "other/private"},
        ),
        Scenario(
            "forbidden_label",
            "Label outside the allowed set",
            "create_issue",
            {**valid, "labels": ["urgent"]},
        ),
        Scenario(
            "hidden_direct_call",
            "Direct call to an unadvertised destructive-name fixture",
            "delete_repository",
            {"repository": "grishahq/demo"},
        ),
        Scenario(
            "extra_argument",
            "Unexpected argument",
            "create_issue",
            {**valid, "extra": "not permitted"},
            baseline_error=True,
        ),
        Scenario(
            "missing_argument",
            "Required title omitted",
            "create_issue",
            {"repository": "grishahq/demo", "labels": ["bug"]},
            baseline_error=True,
        ),
        Scenario(
            "wrong_type",
            "Labels supplied as a string",
            "create_issue",
            {**valid, "labels": "bug"},
            baseline_error=True,
        ),
        Scenario(
            "upstream_error",
            "Allowed call returning a fixture error",
            "create_issue",
            {**valid, "title": "SIMULATE_ERROR"},
            guarded_receipts=1,
            baseline_error=True,
        ),
    ]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _command(
    port: int,
    receipts: Path,
    *,
    policy: Path | None,
    audit: Path,
    drift: bool,
) -> list[str]:
    command = [sys.executable, "-m", "mcp_proxy.guarded" if policy else "mcp_proxy"]
    if policy is not None:
        command.extend(["--policy", str(policy), "--audit-log", str(audit)])
    command.extend(
        [
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "WARNING",
            "--pass-environment",
            "--",
            sys.executable,
            "-m",
            "mcp_proxy.demo_server",
            "--receipts",
            str(receipts),
        ]
    )
    if drift:
        command.append("--schema-drift")
    return command


@asynccontextmanager
async def _proxy(
    receipts: Path,
    *,
    policy: Path | None,
    audit: Path,
    drift: bool,
) -> AsyncIterator[ClientSession]:
    port = _available_port()
    with tempfile.TemporaryFile() as logs:
        process = await asyncio.create_subprocess_exec(
            *_command(port, receipts, policy=policy, audit=audit, drift=drift),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=logs,
        )
        try:
            async with httpx.AsyncClient(timeout=0.5, trust_env=False) as client:
                for _ in range(200):
                    if process.returncode is not None:
                        raise RuntimeError("The demonstration proxy exited before becoming ready")
                    try:
                        response = await client.get(f"http://127.0.0.1:{port}/healthz")
                        if 200 <= response.status_code < 300:
                            break
                    except httpx.HTTPError:
                        pass
                    await asyncio.sleep(0.1)
                else:
                    raise TimeoutError("The demonstration proxy did not become ready")
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10, read=15),
                trust_env=False,
                follow_redirects=True,
            ) as http_client:
                async with streamable_http_client(
                    f"http://127.0.0.1:{port}/mcp",
                    http_client=http_client,
                ) as (read_stream, write_stream, _):
                    async with ClientSession(read_stream, write_stream) as session:
                        await session.initialize()
                        yield session
        finally:
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=8)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()


async def _exercise(
    scenarios: list[Scenario],
    *,
    mode: str,
    suffix: str,
    output: Path,
    policy: Path | None,
    drift: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    receipts = output / f"receipts-{mode}-{suffix}.jsonl"
    audit = output / f"decisions-{mode}-{suffix}.jsonl"
    results = []
    async with _proxy(receipts, policy=policy, audit=audit, drift=drift) as session:
        listed = await session.list_tools()
        discovered = [tool.name for tool in listed.tools]
        for scenario in scenarios:
            before = len(_read_jsonl(receipts))
            try:
                result = await session.call_tool(scenario.tool, scenario.arguments)
                is_error = bool(result.isError)
            except McpError:
                is_error = True
            after = len(_read_jsonl(receipts))
            expected_receipts = 1 if mode == "baseline" else scenario.guarded_receipts
            expected_error = (
                scenario.baseline_error
                if mode == "baseline"
                else (scenario.guarded_receipts == 0 or scenario.baseline_error)
            )
            results.append(
                {
                    "id": scenario.id,
                    "description": scenario.description,
                    "mode": mode,
                    "receipt_delta": after - before,
                    "expected_receipt_delta": expected_receipts,
                    "is_error": is_error,
                    "expected_error": expected_error,
                    "passed": after - before == expected_receipts and is_error == expected_error,
                    "tool_advertised": scenario.tool in discovered,
                }
            )
    return results, _read_jsonl(receipts)


async def _invalid_policy_startup(output: Path) -> dict[str, Any]:
    policy = output / "invalid-policy.json"
    policy.write_text('{"version": 1, "rules": [], "unexpected": true}\n', encoding="utf-8")
    receipts = output / "receipts-invalid-startup.jsonl"
    with tempfile.TemporaryFile() as logs:
        process = await asyncio.create_subprocess_exec(
            *_command(
                _available_port(),
                receipts,
                policy=policy,
                audit=output / "decisions-invalid-startup.jsonl",
                drift=False,
            ),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=logs,
        )
        try:
            returncode = await asyncio.wait_for(process.wait(), timeout=15)
        except asyncio.TimeoutError:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
            returncode = 0
    count = len(_read_jsonl(receipts))
    return {
        "id": "invalid_policy_startup",
        "description": "Unknown policy field fails startup",
        "mode": "guarded",
        "receipt_delta": count,
        "expected_receipt_delta": 0,
        "is_error": returncode != 0,
        "expected_error": True,
        "passed": returncode != 0 and count == 0,
        "tool_advertised": False,
    }


def _render_html(report: dict[str, Any], transcript: str) -> str:
    rows = []
    for scenario in report["scenarios"]:
        observations = {item["mode"]: item for item in scenario["observations"]}
        baseline = observations.get("baseline")
        guarded = observations["guarded"]
        passed = all(item["passed"] for item in observations.values())
        baseline_text = str(baseline["receipt_delta"]) if baseline else "—"
        rows.append(
            f"<tr><td><strong>{html.escape(scenario['id'])}</strong><small>"
            f"{html.escape(scenario['description'])}</small></td>"
            f"<td>{baseline_text}</td><td>{guarded['receipt_delta']}</td>"
            f'<td class="{"pass" if passed else "fail"}">{"PASS" if passed else "FAIL"}</td></tr>'
        )
    status = "PASS" if report["passed"] else "FAIL"
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>CallStencil | Offline transport evidence</title>
<style>
:root{{color-scheme:dark;font:16px/1.5 system-ui,sans-serif;background:#0c1423;color:#edf3fd}}
body{{max-width:1100px;margin:auto;padding:48px 28px}}h1{{font-size:46px;line-height:1.1;margin:12px 0}}
h2{{font-size:22px;margin-top:40px}}p{{color:#afc0d8;max-width:850px}}.eyebrow{{color:#66dfb2;letter-spacing:.13em;font-size:12px;font-weight:700}}
.metrics{{display:flex;gap:16px;margin:30px 0;flex-wrap:wrap}}.metric{{background:#16243a;padding:20px 26px;border-radius:12px;flex:1;min-width:160px}}
.metric strong{{display:block;font-size:34px}}.metric span{{font-size:13px;color:#afc0d8}}table{{width:100%;border-collapse:collapse;background:#111e31;border-radius:12px;overflow:hidden}}
th,td{{text-align:left;padding:14px 18px;border-bottom:1px solid #26354b}}th{{font-size:12px;text-transform:uppercase;letter-spacing:.07em;color:#afc0d8}}
td:first-child{{width:60%}}small{{display:block;color:#afc0d8;font-size:12px;margin-top:3px}}.pass{{color:#66dfb2;font-weight:700}}.fail{{color:#ff9b9b;font-weight:700}}
pre{{background:#070e18;border:1px solid #26354b;border-radius:12px;padding:24px;overflow:auto;font:12px/1.8 ui-monospace,monospace}}
.note{{font-size:13px;border-left:3px solid #6d9afa;padding-left:16px}}a{{color:#98b9ff}}
</style><main><div class="eyebrow">CALLSTENCIL · REAL TRANSPORT EVIDENCE</div>
<h1>Calls checked.<br>Forwarding measured.</h1>
<p>A fixed, offline comparison of the compatibility bridge and the guarded bridge.
Each call traverses a Streamable HTTP client, a proxy subprocess, and a stdio issue-server subprocess.</p>
<div class="metrics"><div class="metric"><strong class="{"pass" if report["passed"] else "fail"}">{status}</strong><span>Independent expectations</span></div>
<div class="metric"><strong>{report["baseline_receipts"]}</strong><span>Baseline server receipts</span></div>
<div class="metric"><strong>{report["guarded_receipts"]}</strong><span>Guarded server receipts</span></div>
<div class="metric"><strong>{report["blocked_calls"]}</strong><span>Calls blocked before forwarding</span></div></div>
<p class="note">Receipts prove that the controlled server received a call. All operations are simulated;
no repository is created, changed, or deleted. Baseline malformed calls reach the fixture and then fail
its schema validation. Guarded denials must return an error and produce zero server receipts.</p>
<h2>Scenario results</h2><table><thead><tr><th>Scenario</th><th>Baseline receipts</th><th>Guarded receipts</th><th>Check</th></tr></thead>
<tbody>{"".join(rows)}</tbody></table>
<h2>Observed terminal transcript</h2><pre>{html.escape(transcript)}</pre>
<p class="note">The upstream error is allowed through and remains an error. Schema drift uses a new
server process with a changed input schema. The hidden direct call is deliberately absent from
discovery. Invalid-policy startup is tested separately and has no baseline call.</p>
<p>Artifacts: <a href="report.json">report.json</a> · <a href="transcript.txt">transcript.txt</a> ·
<a href="receipts.jsonl">redacted server receipts</a> · <a href="decisions.jsonl">redacted policy decisions</a></p>
</main></html>"""


async def run_scenarios(output: Path) -> dict[str, Any]:
    """Execute identical requests in both modes and write independently checked evidence."""
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise FileExistsError("Choose an empty output directory to preserve previous evidence")
    policy = output / "policy.json"
    policy.write_text(json.dumps(demo_policy(), indent=2) + "\n", encoding="utf-8")
    empty_policy = output / "deny-all-policy.json"
    empty_policy.write_text('{"version": 1, "rules": []}\n', encoding="utf-8")
    normal = _scenarios()
    drift = Scenario(
        "schema_drift",
        "Pinned schema differs after server restart",
        "create_issue",
        normal[0].arguments,
    )
    default_deny = Scenario(
        "default_deny", "Empty rules deny a known tool", "create_issue", normal[0].arguments
    )
    observations = []
    all_receipts: list[dict[str, Any]] = []
    transcript = [
        "$ callstencil-scenarios --output <empty-directory>",
        "transport: Streamable HTTP client -> proxy subprocess -> stdio fixture subprocess",
        "baseline: python -m mcp_proxy ... -- python -m mcp_proxy.demo_server ...",
        "guarded:  python -m mcp_proxy.guarded --policy <policy> --audit-log <decisions> ...",
        "receipt = received by the fixture; all repository operations are simulated",
        "",
    ]
    for suffix, scenarios, guard_policy, schema_drift in [
        ("main", normal, policy, False),
        ("drift", [drift], policy, True),
        ("default-deny", [default_deny], empty_policy, False),
    ]:
        for mode in ("baseline", "guarded"):
            results, receipts = await _exercise(
                scenarios,
                mode=mode,
                suffix=suffix,
                output=output,
                policy=guard_policy if mode == "guarded" else None,
                drift=schema_drift,
            )
            observations.extend(results)
            all_receipts.extend({"mode": mode, "run": suffix, **item} for item in receipts)
            for result in results:
                transcript.append(
                    f"{mode:8} {result['id']:22} receipts={result['receipt_delta']} "
                    f"expected={result['expected_receipt_delta']} "
                    f"error={str(result['is_error']).lower()} "
                    f"{'PASS' if result['passed'] else 'FAIL'}"
                )
    startup = await _invalid_policy_startup(output)
    observations.append(startup)
    transcript.append(
        f"guarded  invalid_policy_startup receipts=0 rejected={startup['is_error']} "
        f"{'PASS' if startup['passed'] else 'FAIL'}"
    )
    grouped: dict[str, dict[str, Any]] = {}
    for observation in observations:
        key = observation["id"]
        grouped.setdefault(
            key,
            {
                "id": key,
                "description": observation["description"],
                "observations": [],
            },
        )["observations"].append(observation)
    report = {
        "format_version": 1,
        "suite": "callstencil-fixed-offline-demo",
        "transport": "streamable-http-to-stdio",
        "receipt_semantics": "Forwarded call received; no real repository mutation",
        "passed": all(item["passed"] for item in observations),
        "baseline_receipts": sum(item["mode"] == "baseline" for item in all_receipts),
        "guarded_receipts": sum(item["mode"] == "guarded" for item in all_receipts),
        "blocked_calls": sum(
            item["mode"] == "guarded"
            and item["id"] != "invalid_policy_startup"
            and item["expected_receipt_delta"] == 0
            and item["passed"]
            for item in observations
        ),
        "scenarios": list(grouped.values()),
    }
    decisions = []
    for path in sorted(output.glob("decisions-*.jsonl")):
        decisions.extend(_read_jsonl(path))
    for filename, records in [("receipts.jsonl", all_receipts), ("decisions.jsonl", decisions)]:
        (output / filename).write_text(
            "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
            encoding="utf-8",
        )
    transcript.append("\nOverall: " + ("PASS" if report["passed"] else "FAIL"))
    transcript_text = "\n".join(transcript) + "\n"
    (output / "transcript.txt").write_text(transcript_text, encoding="utf-8")
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    (output / "report.html").write_text(_render_html(report, transcript_text), encoding="utf-8")
    return report


def main() -> None:
    """Run the packaged scenario suite; any evidence mismatch exits nonzero."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="An empty evidence directory")
    parser.add_argument("--timeout", type=float, default=120, help="Overall timeout in seconds")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    try:
        report = asyncio.run(asyncio.wait_for(run_scenarios(args.output), timeout=args.timeout))
    except (OSError, RuntimeError, TimeoutError, asyncio.TimeoutError) as error:
        parser.exit(2, f"Scenario run failed: {type(error).__name__}\n")
    print(
        f"{'PASS' if report['passed'] else 'FAIL'}: "
        f"{len(report['scenarios'])} scenarios; baseline receipts={report['baseline_receipts']}; "
        f"guarded receipts={report['guarded_receipts']}"
    )
    print(f"Report: {args.output.resolve() / 'report.html'}")
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
