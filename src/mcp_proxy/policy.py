"""Strict, default-deny tool policies and value-free authorization decisions.

Version 1 rules match exact tool names. Every declared argument is required and
undeclared arguments are denied. Constraints are conjunctive; rules cannot share
a tool name. Schema fingerprints cover the entire canonical JSON input schema.
"""

# JSON boundaries intentionally accept arbitrary values for fail-closed validation.
# ruff: noqa: ANN401

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from jsonschema.validators import validator_for
from pydantic import BaseModel, ConfigDict, JsonValue, ValidationError, model_validator


class PolicyError(ValueError):
    """An invalid policy, with a message that never includes policy values."""


JsonType = Literal["object", "array", "string", "number", "integer", "boolean", "null"]
Reason = Literal[
    "allowed",
    "tool_not_allowed",
    "invalid_arguments",
    "schema_mismatch",
    "invalid_schema",
    "argument_names_mismatch",
    "argument_constraint_mismatch",
]


def _is_json(value: Any) -> bool:
    if value is None or type(value) in (str, bool, int):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is list:
        return all(_is_json(item) for item in value)
    if type(value) is dict:
        return all(type(key) is str and _is_json(item) for key, item in value.items())
    return False


def _canonical(value: Any) -> str:
    if not _is_json(value):
        raise ValueError("Expected a finite JSON value")
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    )


def schema_digest(schema: dict[str, Any]) -> str:
    """Return SHA-256 of sorted, compact, UTF-8 JSON (without ASCII escaping)."""
    if type(schema) is not dict:
        raise ValueError("Expected an input schema object")
    return hashlib.sha256(_canonical(schema).encode("utf-8")).hexdigest()


def _has_type(value: Any, kind: JsonType) -> bool:
    return {
        "object": type(value) is dict,
        "array": type(value) is list,
        "string": type(value) is str,
        "number": type(value) in (int, float),
        "integer": type(value) is int or (type(value) is float and value.is_integer()),
        "boolean": type(value) is bool,
        "null": value is None,
    }[kind]


def _equal(left: Any, right: Any) -> bool:
    # JSON Schema equality distinguishes booleans from numbers, unlike Python.
    if type(left) in (int, float) and type(right) in (int, float):
        return bool(left == right)
    if type(left) is not type(right):
        return False
    if type(left) is list:
        return len(left) == len(right) and all(
            _equal(a, b) for a, b in zip(left, right, strict=True)
        )
    if type(left) is dict:
        return left.keys() == right.keys() and all(_equal(left[key], right[key]) for key in left)
    return bool(left == right)


class _StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class _Constraint(_StrictModel):
    equals: JsonValue = None
    items_in: list[JsonValue] | None = None
    type: JsonType | None = None

    @model_validator(mode="after")
    def check_constraints(self) -> _Constraint:
        if not self.model_fields_set:
            raise ValueError("At least one constraint is required")
        if "type" in self.model_fields_set and self.type is None:
            raise ValueError("A type must be specified")
        if "items_in" in self.model_fields_set and self.items_in is None:
            raise ValueError("An allowed-items array must be specified")
        if self.items_in is not None and self.type not in (None, "array"):
            raise ValueError("Allowed-items constraints require arrays")
        if "equals" in self.model_fields_set:
            if self.type is not None and not _has_type(self.equals, self.type):
                raise ValueError("Equality value conflicts with type")
            if self.items_in is not None and (
                type(self.equals) is not list
                or any(
                    not any(_equal(item, option) for option in self.items_in)
                    for item in self.equals
                )
            ):
                raise ValueError("Equality value conflicts with allowed items")
        return self


class _Rule(_StrictModel):
    id: str
    tool: str
    input_schema_sha256: str
    arguments: dict[str, _Constraint]

    @model_validator(mode="after")
    def check_rule(self) -> _Rule:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", self.id):
            raise ValueError("Invalid rule identifier")
        if not self.tool or any(character in self.tool for character in "*?[]"):
            raise ValueError("An exact nonempty tool name is required")
        if not re.fullmatch(r"[0-9a-f]{64}", self.input_schema_sha256):
            raise ValueError("A lowercase SHA-256 fingerprint is required")
        if any(not name for name in self.arguments):
            raise ValueError("Argument names must be nonempty")
        return self


class _Config(_StrictModel):
    version: Literal[1]
    rules: list[_Rule]

    @model_validator(mode="before")
    @classmethod
    def check_version(cls, value: Any) -> Any:
        if isinstance(value, dict) and type(value.get("version")) is not int:
            raise ValueError("Version must be an integer")
        return value

    @model_validator(mode="after")
    def check_unique(self) -> _Config:
        if len({rule.id for rule in self.rules}) != len(self.rules):
            raise ValueError("Duplicate rule identifier")
        if len({rule.tool for rule in self.rules}) != len(self.rules):
            raise ValueError("Duplicate tool name")
        return self


@dataclass(frozen=True)
class Decision:
    """A decision containing only policy identifiers, a digest and fixed reasons.

    The tool is populated only from an existing rule, never from an unmatched
    request. No argument names, values, schema content or arbitrary errors enter
    this record.
    """

    allowed: bool
    reason: Reason
    tool: str | None = None
    rule_id: str | None = None
    schema_sha256: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return the redacted, JSON-serializable audit record."""
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "tool": self.tool,
            "rule_id": self.rule_id,
            "schema_sha256": self.schema_sha256,
        }


@dataclass(frozen=True)
class _CompiledConstraint:
    kind: JsonType | None
    equals_json: str | None
    items_json: str | None

    def accepts(self, value: Any) -> bool:
        if self.kind is not None and not _has_type(value, self.kind):
            return False
        if self.equals_json is not None and not _equal(value, json.loads(self.equals_json)):
            return False
        if self.items_json is not None:
            choices = json.loads(self.items_json)
            if type(value) is not list or any(
                not any(_equal(item, choice) for choice in choices) for item in value
            ):
                return False
        return True


@dataclass(frozen=True)
class _CompiledRule:
    id: str
    tool: str
    digest: str
    arguments: tuple[tuple[str, _CompiledConstraint], ...]


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PolicyError("Policy contains duplicate JSON keys")
        result[key] = value
    return result


def _reject_constant(_value: str) -> None:
    raise PolicyError("Policy contains a non-finite JSON number")


def _local_references(value: Any) -> bool:
    if type(value) is dict:
        return all(
            (
                key not in ("$ref", "$dynamicRef", "$recursiveRef")
                or (type(item) is str and item.startswith("#"))
            )
            and _local_references(item)
            for key, item in value.items()
        )
    if type(value) is list:
        return all(_local_references(item) for item in value)
    return True


def _argument_error(arguments: Any, schema: dict[str, Any]) -> Reason | None:
    try:
        if type(arguments) is not dict or not _is_json(arguments):
            return "invalid_arguments"
        if not _local_references(schema):
            return "invalid_schema"
        validator_class = validator_for(schema)
        validator_class.check_schema(schema)
        validator = validator_class(schema)
        return None if validator.is_valid(arguments) else "invalid_arguments"
    except Exception:  # noqa: BLE001
        # Resolver failures, recursion and invalid regexes fail closed. Their
        # potentially value-bearing exception strings must never be exposed.
        return "invalid_schema"


@dataclass(frozen=True)
class Policy:
    """An immutable, validated version 1 policy; unmatched tools always deny."""

    _rules: tuple[_CompiledRule, ...]

    @classmethod
    def load(cls, path: str | Path) -> Policy:
        """Load strict JSON, rejecting duplicate keys and non-finite numbers."""
        try:
            value = json.loads(
                Path(path).read_text(encoding="utf-8"),
                object_pairs_hook=_unique_object,
                parse_constant=_reject_constant,
            )
        except PolicyError:
            raise
        except (OSError, ValueError, UnicodeError, RecursionError):
            raise PolicyError("Could not read a valid JSON policy") from None
        return cls.from_dict(value)

    @classmethod
    def from_dict(cls, value: Any) -> Policy:
        """Validate configuration, copying it into immutable compiled rules."""
        try:
            if not _is_json(value):
                raise ValueError("Expected JSON")  # noqa: TRY301
            config = _Config.model_validate(value)
            return cls(
                tuple(
                    _CompiledRule(
                        rule.id,
                        rule.tool,
                        rule.input_schema_sha256,
                        tuple(
                            (
                                name,
                                _CompiledConstraint(
                                    constraint.type,
                                    _canonical(constraint.equals)
                                    if "equals" in constraint.model_fields_set
                                    else None,
                                    _canonical(constraint.items_in)
                                    if constraint.items_in is not None
                                    else None,
                                ),
                            )
                            for name, constraint in rule.arguments.items()
                        ),
                    )
                    for rule in config.rules
                )
            )
        except (ValidationError, ValueError, TypeError, RecursionError):
            raise PolicyError("Invalid version 1 policy configuration") from None

    def visible(self, name: str) -> bool:
        """Whether an exact tool name has a rule (discovery is supplementary)."""
        return any(rule.tool == name for rule in self._rules)

    def evaluate(self, name: str, arguments: Any, schema: Any) -> Decision:
        """Authorize against the pinned server schema and all argument constraints."""
        rule = next((rule for rule in self._rules if rule.tool == name), None)
        if rule is None:
            return Decision(allowed=False, reason="tool_not_allowed")
        digest: str | None = None

        def result(allowed: bool, reason: Reason) -> Decision:
            return Decision(allowed, reason, rule.tool, rule.id, digest)

        try:
            digest = schema_digest(schema)
        except (ValueError, TypeError, UnicodeError, RecursionError):
            return result(allowed=False, reason="invalid_schema")
        if digest != rule.digest:
            return result(allowed=False, reason="schema_mismatch")
        reason = _argument_error(arguments, schema)
        if reason is None and set(arguments) != {key for key, _ in rule.arguments}:
            reason = "argument_names_mismatch"
        if reason is None and any(
            not constraint.accepts(arguments[key]) for key, constraint in rule.arguments
        ):
            reason = "argument_constraint_mismatch"
        return result(allowed=reason is None, reason=reason or "allowed")
