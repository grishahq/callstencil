"""Independent expectations for the packaged real-transport demonstration."""

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

from mcp_proxy.demo_server import ISSUE_SCHEMA, demo_policy, schema_sha256
from mcp_proxy.scenarios import _exercise, _scenarios


def test_packaged_scenarios_over_real_transports(tmp_path: Path) -> None:
    """Run real subprocesses and independently inspect per-call receipt evidence."""
    output = tmp_path / "evidence"
    environment = os.environ.copy()
    source = str(Path(__file__).resolve().parents[1] / "src")
    environment["PYTHONPATH"] = source + os.pathsep + environment.get("PYTHONPATH", "")
    completed = subprocess.run(
        [sys.executable, "-m", "mcp_proxy.scenarios", "--output", str(output)],
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    report = json.loads((output / "report.json").read_text())
    assert report["passed"] is True
    assert report["baseline_receipts"] == 10
    assert report["guarded_receipts"] == 2
    assert report["blocked_calls"] == 8
    scenarios = {row["id"]: row for row in report["scenarios"]}
    assert set(scenarios) == {
        "allowed",
        "wrong_repository",
        "forbidden_label",
        "hidden_direct_call",
        "extra_argument",
        "missing_argument",
        "wrong_type",
        "upstream_error",
        "schema_drift",
        "default_deny",
        "invalid_policy_startup",
    }
    for scenario_id, row in scenarios.items():
        observations = {item["mode"]: item for item in row["observations"]}
        guarded = observations["guarded"]
        expected = 1 if scenario_id in {"allowed", "upstream_error"} else 0
        assert guarded["receipt_delta"] == expected
        assert guarded["is_error"] == (scenario_id != "allowed")
        if scenario_id != "invalid_policy_startup":
            assert observations["baseline"]["receipt_delta"] == 1
    assert not scenarios["hidden_direct_call"]["observations"][0]["tool_advertised"]
    receipts = [json.loads(line) for line in (output / "receipts.jsonl").read_text().splitlines()]
    assert len(receipts) == 12
    assert len([item for item in receipts if item["tool"] == "delete_repository"]) == 1
    assert {item["outcome"] for item in receipts} == {
        "simulated_only",
        "invalid_arguments",
        "upstream_error",
    }
    decisions_text = (output / "decisions.jsonl").read_text()
    receipts_text = (output / "receipts.jsonl").read_text()
    assert len(decisions_text.splitlines()) == 10
    for secret in ("Demonstration issue", "SIMULATE_ERROR", "other/private", "urgent"):
        assert secret not in decisions_text
        assert secret not in receipts_text
    page = (output / "report.html").read_text()
    assert "Streamable HTTP" in page
    assert "no repository is created, changed, or deleted" in page
    assert "invalid_policy_startup" in page


async def test_receipt_mismatch_fails_even_when_tool_succeeds(tmp_path: Path) -> None:
    """A successful HTTP response cannot satisfy a false zero-receipt expectation."""
    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps(demo_policy()))
    allowed_but_expected_blocked = replace(_scenarios()[0], guarded_receipts=0)
    results, receipts = await _exercise(
        [allowed_but_expected_blocked],
        mode="guarded",
        suffix="negative-check",
        output=tmp_path,
        policy=policy,
    )
    assert len(receipts) == 1
    assert results[0]["receipt_delta"] == 1
    assert results[0]["expected_receipt_delta"] == 0
    assert results[0]["passed"] is False


def test_shipped_policy_pins_actual_demo_schema() -> None:
    """The copyable policy must match the fixture actually used by the runner."""
    policy = Path(__file__).resolve().parents[1] / "examples" / "issue-policy.json"
    assert json.loads(policy.read_text()) == demo_policy()
    assert demo_policy()["rules"][0]["input_schema_sha256"] == schema_sha256(ISSUE_SCHEMA)
