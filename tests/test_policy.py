"""Policy authorization, strict configuration and audit redaction regressions."""

# JSON test cases include deliberately invalid Python values.
# ruff: noqa: ANN401

import copy
import dataclasses
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from mcp_proxy.policy import Policy, PolicyError, schema_digest


@pytest.fixture
def schema() -> dict[str, Any]:
    """Verify schema."""
    return {
        "type": "object",
        "properties": {
            "repository": {"type": "string"},
            "title": {"type": "string"},
            "labels": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["repository", "title", "labels"],
        "additionalProperties": False,
    }


@pytest.fixture
def config(schema: dict[str, Any]) -> dict[str, Any]:
    """Verify config."""
    return {
        "version": 1,
        "rules": [
            {
                "id": "demo-issues",
                "tool": "create_issue",
                "input_schema_sha256": schema_digest(schema),
                "arguments": {
                    "repository": {"equals": "grishahq/demo"},
                    "title": {"type": "string"},
                    "labels": {"items_in": ["bug", "docs"]},
                },
            }
        ],
    }


@pytest.fixture
def arguments() -> dict[str, Any]:
    """Verify arguments."""
    return {"repository": "grishahq/demo", "title": "Private issue title", "labels": ["bug"]}


def test_load_and_allow(
    tmp_path: Path,
    config: dict[str, Any],
    schema: dict[str, Any],
    arguments: dict[str, Any],
) -> None:
    """Verify load and allow."""
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(config))
    policy = Policy.load(path)
    assert policy.visible("create_issue")
    decision = policy.evaluate("create_issue", arguments, schema)
    assert decision.allowed
    assert decision.reason == "allowed"
    assert decision.rule_id == "demo-issues"


def test_default_deny_does_not_log_unmatched_names(schema: dict[str, Any]) -> None:
    """Verify default deny does not log unmatched names."""
    policy = Policy.from_dict({"version": 1, "rules": []})
    assert not policy.visible("create_issue")
    decision = policy.evaluate("PRIVATE-SECRET", {"secret": "PRIVATE-SECRET"}, schema)
    assert not decision.allowed
    assert decision.reason == "tool_not_allowed"
    assert "PRIVATE-SECRET" not in json.dumps(decision.as_dict())


@pytest.mark.parametrize("name", ["Create_issue", "create_issue ", "create_issue.extra", "*"])
def test_tool_match_is_exact(config: dict[str, Any], schema: dict[str, Any], name: str) -> None:
    """Verify tool match is exact."""
    policy = Policy.from_dict(config)
    assert not policy.visible(name)
    assert policy.evaluate(name, {}, schema).reason == "tool_not_allowed"


@pytest.mark.parametrize("value", [True, "1", 1.0, 2, None])
def test_version_is_strict(config: dict[str, Any], value: Any) -> None:
    """Verify version is strict."""
    config["version"] = value
    with pytest.raises(PolicyError, match="Invalid version 1"):
        Policy.from_dict(config)


@pytest.mark.parametrize("level", ["config", "rule", "constraint"])
def test_unknown_fields_rejected(config: dict[str, Any], level: str) -> None:
    """Verify unknown fields rejected."""
    target = config
    if level == "rule":
        target = config["rules"][0]
    elif level == "constraint":
        target = config["rules"][0]["arguments"]["repository"]
    target["typo_with_private_value"] = "SECRET-CONFIG"
    with pytest.raises(PolicyError) as error:
        Policy.from_dict(config)
    assert "SECRET" not in str(error.value)
    assert "typo" not in str(error.value)


@pytest.mark.parametrize(
    "mutation",
    [
        {"input_schema_sha256": "a" * 63},
        {"input_schema_sha256": "A" * 64},
        {"tool": "create_*"},
        {"tool": ""},
        {"id": ""},
        {"id": "line\nbreak"},
        {"arguments": {"repository": {}}},
        {"arguments": {"repository": {"type": "str"}}},
        {"arguments": {"repository": {"type": None}}},
        {"arguments": {"repository": {"items_in": None}}},
        {"arguments": {"repository": {"items_in": "bug"}}},
        {"arguments": {"repository": {"type": "string", "items_in": ["bug"]}}},
        {"arguments": {"repository": {"type": "string", "equals": 4}}},
        {"arguments": {"repository": {"items_in": ["bug"], "equals": ["other"]}}},
    ],
)
def test_invalid_rule_rejected(config: dict[str, Any], mutation: dict[str, Any]) -> None:
    """Verify invalid rule rejected."""
    config["rules"][0].update(mutation)
    with pytest.raises(PolicyError):
        Policy.from_dict(config)


@pytest.mark.parametrize("duplicate", ["tool", "id"])
def test_ambiguous_rules_rejected(config: dict[str, Any], duplicate: str) -> None:
    """Verify ambiguous rules rejected."""
    second = copy.deepcopy(config["rules"][0])
    second["id" if duplicate == "tool" else "tool"] = "different"
    config["rules"].append(second)
    with pytest.raises(PolicyError):
        Policy.from_dict(config)


@pytest.mark.parametrize(
    "text",
    [
        '{"version":1,"version":1,"rules":[]}',
        '{"version":1,"rules":[],"extra":NaN}',
        '{"version":1,"rules":[],"extra":Infinity}',
        '{"version":1,"rules":[],"extra":-Infinity}',
        '{"version":1,"rules":[],"extra":1e10000}',
        "SECRET malformed JSON",
    ],
)
def test_strict_json_load(tmp_path: Path, text: str) -> None:
    """Verify strict json load."""
    path = tmp_path / "policy.json"
    path.write_text(text)
    with pytest.raises(PolicyError) as error:
        Policy.load(path)
    assert "SECRET" not in str(error.value)


def test_missing_policy_is_safe_error(tmp_path: Path) -> None:
    """Verify missing policy is safe error."""
    with pytest.raises(PolicyError, match="Could not read"):
        Policy.load(tmp_path / "private-path")


@pytest.mark.parametrize("invalid", [None, [], "SECRET", {"title": "SECRET"}, {"labels": "bug"}])
def test_invalid_arguments_fail_closed(
    config: dict[str, Any],
    schema: dict[str, Any],
    invalid: Any,
) -> None:
    """Verify invalid arguments fail closed."""
    decision = Policy.from_dict(config).evaluate("create_issue", invalid, schema)
    assert not decision.allowed
    assert decision.reason == "invalid_arguments"
    assert "SECRET" not in json.dumps(decision.as_dict())


@pytest.mark.parametrize(
    "change",
    [
        {"repository": "other/private"},
        {"labels": ["bug", "secret-label"]},
    ],
)
def test_constraints_deny_values(
    config: dict[str, Any],
    schema: dict[str, Any],
    arguments: dict[str, Any],
    change: dict[str, Any],
) -> None:
    """Verify constraints deny values."""
    arguments.update(change)
    decision = Policy.from_dict(config).evaluate("create_issue", arguments, schema)
    assert decision.reason == "argument_constraint_mismatch"
    record = json.dumps(decision.as_dict())
    assert not decision.allowed
    for value in ["other/private", "secret-label", "Private issue title", "repository", "labels"]:
        assert value not in record


def test_empty_labels_are_permitted_subset(
    config: dict[str, Any],
    schema: dict[str, Any],
    arguments: dict[str, Any],
) -> None:
    """Verify empty labels are permitted subset."""
    arguments["labels"] = []
    assert Policy.from_dict(config).evaluate("create_issue", arguments, schema).allowed


def test_schema_change_denied(
    config: dict[str, Any],
    schema: dict[str, Any],
    arguments: dict[str, Any],
) -> None:
    """Verify schema change denied."""
    schema["description"] = "Changed server contract SECRET"
    decision = Policy.from_dict(config).evaluate("create_issue", arguments, schema)
    assert decision.reason == "schema_mismatch"
    assert not decision.allowed
    assert "SECRET" not in json.dumps(decision.as_dict())


def test_digest_is_canonical_and_unicode_explicit() -> None:
    """Verify digest is canonical and unicode explicit."""
    first = {"type": "object", "description": "café"}
    second = {"description": "café", "type": "object"}
    expected = hashlib.sha256('{"description":"café","type":"object"}'.encode()).hexdigest()
    assert schema_digest(first) == schema_digest(second) == expected
    with pytest.raises(ValueError, match="finite JSON"):
        schema_digest({"bad": float("nan")})


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "unknown"},
        {"type": "object", "$ref": "https://example.invalid/SECRET"},
        {"type": "object", "$dynamicRef": "https://example.invalid/SECRET"},
        {"type": "object", "$ref": "#/missing"},
    ],
)
def test_invalid_or_remote_schema_denied(config: dict[str, Any], schema: dict[str, Any]) -> None:
    """Verify invalid or remote schema denied."""
    config["rules"][0]["input_schema_sha256"] = schema_digest(schema)
    decision = Policy.from_dict(config).evaluate("create_issue", {}, schema)
    assert decision.reason == "invalid_schema"
    assert not decision.allowed
    assert "SECRET" not in json.dumps(decision.as_dict())


def test_local_schema_references_supported(
    config: dict[str, Any], arguments: dict[str, Any]
) -> None:
    """Verify local schema references supported."""
    schema = {
        "type": "object",
        "$defs": {"title": {"type": "string"}},
        "properties": {
            "title": {"$ref": "#/$defs/title"},
        },
    }
    config["rules"][0]["input_schema_sha256"] = schema_digest(schema)
    assert Policy.from_dict(config).evaluate("create_issue", arguments, schema).allowed


def test_policy_requires_exact_argument_set(config: dict[str, Any]) -> None:
    """Verify policy requires exact argument set."""
    schema = {"type": "object"}
    config["rules"][0]["input_schema_sha256"] = schema_digest(schema)
    policy = Policy.from_dict(config)
    assert policy.evaluate("create_issue", {}, schema).reason == "argument_names_mismatch"
    assert (
        policy.evaluate("create_issue", {"extra": "SECRET"}, schema).reason
        == "argument_names_mismatch"
    )


@pytest.mark.parametrize("value", [True, 1, 1.0, "1", None])
def test_json_equality_distinguishes_booleans(config: dict[str, Any], value: Any) -> None:
    """Verify json equality distinguishes booleans."""
    schema = {"type": "object"}
    config["rules"][0]["input_schema_sha256"] = schema_digest(schema)
    config["rules"][0]["arguments"] = {"value": {"equals": 1}}
    decision = Policy.from_dict(config).evaluate("create_issue", {"value": value}, schema)
    assert decision.allowed is (type(value) in (int, float))


def test_null_equality_and_conjunctive_constraints(config: dict[str, Any]) -> None:
    """Verify null equality and conjunctive constraints."""
    schema = {"type": "object"}
    config["rules"][0]["input_schema_sha256"] = schema_digest(schema)
    config["rules"][0]["arguments"] = {
        "null": {"equals": None, "type": "null"},
        "labels": {"items_in": ["bug", "docs"], "equals": ["bug"], "type": "array"},
    }
    policy = Policy.from_dict(config)
    assert policy.evaluate("create_issue", {"null": None, "labels": ["bug"]}, schema).allowed
    assert not policy.evaluate("create_issue", {"null": None, "labels": ["docs"]}, schema).allowed


def test_non_json_arguments_denied(config: dict[str, Any], schema: dict[str, Any]) -> None:
    """Verify non json arguments denied."""
    policy = Policy.from_dict(config)
    for arguments in [{"value": float("nan")}, {1: "SECRET"}, {"value": (1, 2)}]:
        assert policy.evaluate("create_issue", arguments, schema).reason == "invalid_arguments"


def test_policy_and_decisions_are_immutable(
    config: dict[str, Any],
    schema: dict[str, Any],
    arguments: dict[str, Any],
) -> None:
    """Verify policy and decisions are immutable."""
    policy = Policy.from_dict(config)
    config["rules"][0]["arguments"]["repository"]["equals"] = "other/repo"
    assert policy.evaluate("create_issue", arguments, schema).allowed
    with pytest.raises(dataclasses.FrozenInstanceError):
        policy._rules = ()  # noqa: SLF001
    decision = policy.evaluate("create_issue", arguments, schema)
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.allowed = False
