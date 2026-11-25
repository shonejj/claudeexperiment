"""JSON Schema validation for Odoo Master files (schemas/*.schema.json).

Uses `jsonschema` when installed; otherwise falls back to a minimal structural check (required keys
and top-level types) and says so in the result, so callers never mistake a partial check for a full one.
"""
from __future__ import annotations

import json
from pathlib import Path

from .util import PLUGIN_ROOT, load_yaml


def schema_path(name: str) -> Path:
    return PLUGIN_ROOT / "schemas" / f"{name}.schema.json"


def load_schema(name: str) -> dict:
    return json.loads(schema_path(name).read_text())


def validate_data(name: str, data) -> dict:
    schema = load_schema(name)
    try:
        import jsonschema  # type: ignore
        v = jsonschema.Draft202012Validator(schema)
        errors = [f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in v.iter_errors(data)]
        return {"schema": name, "valid": not errors, "errors": errors, "validator": "jsonschema"}
    except ImportError:
        errors = []
        if schema.get("type") == "object" and not isinstance(data, dict):
            errors.append("<root>: expected object")
        for k in schema.get("required", []):
            if not isinstance(data, dict) or k not in data:
                errors.append(f"<root>: missing required '{k}'")
        return {"schema": name, "valid": not errors, "errors": errors, "validator": "minimal (install jsonschema for full validation)"}


def validate_file(name: str, path: Path) -> dict:
    data = load_yaml(path) if path.suffix in (".yaml", ".yml") else json.loads(path.read_text())
    res = validate_data(name, data)
    res["file"] = str(path)
    return res
