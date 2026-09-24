#!/usr/bin/env python3
"""Small dependency-free checks for the shared OpenAPI contract and examples."""

import json
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = json.loads((ROOT / "contracts/openapi.json").read_text())
schemas = spec["components"]["schemas"]
errors = []


def check_schema(value, schema, location):
    if "$ref" in schema:
        name = schema["$ref"].removeprefix("#/components/schemas/")
        if name not in schemas:
            errors.append(f"{location}: missing schema {name}")
            return
        check_schema(value, schemas[name], location)
        return
    if value is None:
        if not schema.get("nullable"):
            errors.append(f"{location}: null is not allowed")
        return
    typ = schema.get("type")
    expected = {"object": dict, "array": list, "string": str, "integer": int, "boolean": bool}
    if typ in expected and (not isinstance(value, expected[typ]) or (typ == "integer" and isinstance(value, bool))):
        errors.append(f"{location}: expected {typ}")
        return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{location}: invalid enum value {value!r}")
    if typ == "object":
        for field in schema.get("required", []):
            if field not in value:
                errors.append(f"{location}: missing {field}")
        for field, item in value.items():
            child = schema.get("properties", {}).get(field)
            if child:
                check_schema(item, child, f"{location}.{field}")
            elif schema.get("additionalProperties") is False:
                errors.append(f"{location}: unknown field {field}")
    elif typ == "array":
        for index, item in enumerate(value):
            check_schema(item, schema["items"], f"{location}[{index}]")
    elif typ == "string":
        if schema.get("format") == "uuid":
            try:
                uuid.UUID(value)
            except ValueError:
                errors.append(f"{location}: invalid UUID")
        if schema.get("format") == "date-time":
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
                if not value.endswith("Z"):
                    raise ValueError
            except ValueError:
                errors.append(f"{location}: expected UTC date-time ending in Z")
        if schema.get("pattern") and not re.search(schema["pattern"], value):
            errors.append(f"{location}: does not match {schema['pattern']}")


def walk_refs(node, location):
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            if not ref.startswith("#/components/"):
                errors.append(f"{location}: unsupported ref {ref}")
            else:
                target = spec
                for part in ref[2:].split("/"):
                    target = target.get(part) if isinstance(target, dict) else None
                    if target is None:
                        errors.append(f"{location}: unresolved ref {ref}")
                        break
        for key, value in node.items():
            walk_refs(value, f"{location}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            walk_refs(value, f"{location}[{index}]")


walk_refs(spec, "openapi")
operation_ids = set()
count = 0
for path, methods in spec["paths"].items():
    for method, operation in methods.items():
        count += 1
        operation_id = operation["operationId"]
        if operation_id in operation_ids:
            errors.append(f"duplicate operationId {operation_id}")
        operation_ids.add(operation_id)
        if method in {"post", "put", "patch", "delete"} and operation.get("x-origin-check") is not True:
            errors.append(f"{method.upper()} {path}: missing Origin-check requirement")
        if path not in {"/auth/register", "/auth/login", "/auth/logout"} and operation.get("security"):
            if not any("accessCookie" in entry for entry in operation["security"]):
                errors.append(f"{method.upper()} {path}: unsupported auth scheme")
        if not operation.get("x-owner") or not operation.get("x-milestone"):
            errors.append(f"{method.upper()} {path}: missing owner or milestone")

manifest = json.loads((ROOT / "contracts/examples/manifest.json").read_text())
for filename, schema_name in manifest.items():
    data = json.loads((ROOT / "contracts/examples" / filename).read_text())
    check_schema(data, schemas[schema_name], filename)

if errors:
    print("Contract check failed:")
    for error in errors:
        print(" -", error)
    sys.exit(1)
print(f"Contract OK: {count} operations, {len(schemas)} schemas, {len(manifest)} examples")
