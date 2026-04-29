"""
Event transformation pipeline.

Applies a tenant's configured transformations to a raw event payload
before delivery. Transformations run in order; if any step fails the
event is rejected with a descriptive error.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TransformResult:
    payload: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


class PipelineError(Exception):
    pass


def run_pipeline(
    payload: dict[str, Any],
    steps: list[dict[str, Any]],
    tenant_id: str,
) -> TransformResult:
    """Apply a sequence of transformation steps to an event payload.

    Each step is a dict with a 'type' key and type-specific config.
    Steps run in order; the output of one step is the input to the next.

    Raises PipelineError if a required step fails.
    """
    result = TransformResult(payload=dict(payload))

    for i, step in enumerate(steps):
        step_type = step.get("type")
        try:
            result = _apply_step(result, step, tenant_id)
        except PipelineError:
            raise
        except Exception as exc:
            raise PipelineError(
                f"Step {i} ({step_type!r}) raised an unexpected error: {exc}"
            ) from exc

        logger.debug(
            "tenant=%s step=%d type=%s warnings=%d",
            tenant_id,
            i,
            step_type,
            len(result.warnings),
        )

    return result


def _apply_step(
    result: TransformResult,
    step: dict[str, Any],
    tenant_id: str,
) -> TransformResult:
    step_type = step.get("type")

    match step_type:
        case "field_rename":
            return _rename_fields(result, step)
        case "field_drop":
            return _drop_fields(result, step)
        case "field_add_static":
            return _add_static_field(result, step)
        case "field_coerce_type":
            return _coerce_type(result, step)
        case _:
            raise PipelineError(f"Unknown transformation type: {step_type!r}")


def _rename_fields(result: TransformResult, step: dict) -> TransformResult:
    """Rename fields according to a mapping dict."""
    mapping: dict[str, str] = step.get("mapping", {})
    payload = dict(result.payload)
    warnings = list(result.warnings)

    for old_name, new_name in mapping.items():
        if old_name in payload:
            payload[new_name] = payload.pop(old_name)
        elif step.get("required", False):
            raise PipelineError(
                f"field_rename: required field {old_name!r} not found in payload"
            )
        else:
            warnings.append(f"field_rename: field {old_name!r} not present, skipped")

    return TransformResult(payload=payload, warnings=warnings)


def _drop_fields(result: TransformResult, step: dict) -> TransformResult:
    """Remove specified fields from the payload."""
    fields: list[str] = step.get("fields", [])
    payload = {k: v for k, v in result.payload.items() if k not in fields}
    return TransformResult(payload=payload, warnings=result.warnings)


def _add_static_field(result: TransformResult, step: dict) -> TransformResult:
    """Add a field with a static value. Fails if the field already exists and overwrite=False."""
    key: str = step["key"]
    value: Any = step["value"]
    overwrite: bool = step.get("overwrite", False)

    payload = dict(result.payload)
    warnings = list(result.warnings)

    if key in payload and not overwrite:
        raise PipelineError(
            f"field_add_static: field {key!r} already exists and overwrite=False"
        )

    payload[key] = value
    return TransformResult(payload=payload, warnings=warnings)


def _coerce_type(result: TransformResult, step: dict) -> TransformResult:
    """Coerce a field's value to a target type. Supported: str, int, float, bool."""
    field_name: str = step["field"]
    target_type: str = step["target_type"]

    payload = dict(result.payload)

    if field_name not in payload:
        if step.get("required", True):
            raise PipelineError(
                f"field_coerce_type: field {field_name!r} not found in payload"
            )
        return result

    value = payload[field_name]

    try:
        match target_type:
            case "str":
                payload[field_name] = str(value)
            case "int":
                payload[field_name] = int(value)
            case "float":
                payload[field_name] = float(value)
            case "bool":
                if isinstance(value, str):
                    payload[field_name] = value.lower() in ("true", "1", "yes")
                else:
                    payload[field_name] = bool(value)
            case _:
                raise PipelineError(
                    f"field_coerce_type: unsupported target_type {target_type!r}"
                )
    except (ValueError, TypeError) as exc:
        raise PipelineError(
            f"field_coerce_type: cannot coerce {field_name!r} value {value!r} to {target_type}: {exc}"
        ) from exc

    return TransformResult(payload=payload, warnings=result.warnings)
