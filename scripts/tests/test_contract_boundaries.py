"""仓库层检查私有事件结构及生成器 fail-closed 行为。"""
from __future__ import annotations

import ast
import importlib.util
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCHEMAS = json.loads((ROOT / "packages/api-contracts/openapi/foundation.openapi.json").read_text(encoding="utf-8"))["components"]["schemas"]
EVENT_TYPES = {s["properties"]["type"]["const"] for s in SCHEMAS.values() if "type" in s.get("properties", {})}


def python_violations(source: str) -> list[int]:
    errors = []

    def event_fields(fields):
        event_type = fields.get("type")
        return event_type is not None and (
            any(isinstance(n, ast.Constant) and n.value in EVENT_TYPES for n in ast.walk(event_type))
            or "channel" in fields or "timestamp" in fields
        )

    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Dict):
            fields = {key.value: value for key, value in zip(node.keys, node.values) if isinstance(key, ast.Constant)}
            if event_fields(fields):
                errors.append(node.lineno)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict":
            if event_fields({kw.arg: kw.value for kw in node.keywords if kw.arg is not None}):
                errors.append(node.lineno)
        if isinstance(node, ast.ClassDef):
            fields = {n.target.id: n.annotation for n in node.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)}
            if "type" in fields and (
                any(isinstance(v, ast.Constant) and v.value in EVENT_TYPES for v in ast.walk(fields["type"]))
                or "channel" in fields or "timestamp" in fields
            ):
                errors.append(node.lineno)
    return errors


class ContractBoundaryTests(unittest.TestCase):
    def test_backend_event_declarations_are_generated(self) -> None:
        for file in (ROOT / "apps/backend/src").rglob("*.py"):
            if file.name == "generated_contracts.py":
                continue
            with self.subTest(file=file):
                self.assertEqual(python_violations(file.read_text(encoding="utf-8")), [])

    def test_python_gate_rejects_private_payload_and_model(self) -> None:
        for source in [
            'event = {"type": "content.delta", "delta": "x"}',
            'event = {"type": "new.kind", "channel": "chat"}',
            'class PrivateEvent:\n    type: Literal["error"]\n    error: dict',
            'event = dict(type="content.delta", delta="x")',
            'PrivateEvent = TypedDict("PrivateEvent", {"type": Literal["content.delta"], "delta": str})',
        ]:
            self.assertTrue(python_violations(source))
        self.assertEqual(python_violations('from oncall_pilot.generated_contracts import SseEvent'), [])

    def test_typescript_ast_gate_and_negative_probes(self) -> None:
        probe = r'''
import assert from "node:assert/strict";
import { violations } from "./scripts/check_contract_boundaries.mjs";
for (const source of [
  'type Private = { type: "content.delta"; delta: string };',
  'interface Private { type: "error"; error: unknown }',
  'const event = {type: "new.kind", channel: "chat"};',
  'const event = {type: "complete", finishReason: "stop"};'
  , 'class PrivateEvent { type = "content.delta"; delta = "x"; }'
]) assert.ok(violations(source).length);
assert.equal(violations('import type { SseEvent } from "@oncall-pilot/api-contracts"; type View = SseEvent;').length, 0);
'''
        subprocess.run(["node", "--input-type=module", "-e", probe], cwd=ROOT, check=True)
        subprocess.run(["node", "scripts/check_contract_boundaries.mjs"], cwd=ROOT, check=True)

    def test_generator_rejects_unknown_schema_constraints(self) -> None:
        spec = importlib.util.spec_from_file_location("generate_contracts", ROOT / "scripts/generate_contracts.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for schema in [
            {"type": "string", "maxLength": 1}, {"format": "custom"},
            {"$ref": "https://external.invalid/schema"},
            {"type": "string", "enum": ["a", "b"], "pattern": "^a$"},
            {"$ref": "#/components/schemas/RequestId", "pattern": "^must-match$"},
            {"type": "string", "enum": [1]}, {"type": "integer", "pattern": "x"},
        ]:
            with self.assertRaises(ValueError):
                module.validate_schema(schema, set(SCHEMAS))

    def test_generated_files_are_current(self) -> None:
        subprocess.run(["python", "scripts/generate_contracts.py", "--check"], cwd=ROOT, check=True)


if __name__ == "__main__":
    unittest.main()
