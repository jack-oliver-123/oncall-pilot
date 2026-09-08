"""从 contracts OpenAPI 生成协议声明；未知 schema 语义必须显式失败。"""

from __future__ import annotations

import argparse
import json
import sys
from io import TextIOWrapper
from pathlib import Path
from pprint import pformat

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "packages/api-contracts/openapi/foundation.openapi.json"
KEYS = {
    "$ref", "const", "enum", "type", "properties", "required", "additionalProperties",
    "oneOf", "anyOf", "discriminator", "items", "minLength", "pattern", "format", "default",
    "description",
}


def validate_schema(schema: dict, names: set[str]) -> None:
    unknown = set(schema) - KEYS
    if unknown:
        raise ValueError(f"不支持的 schema 关键字: {sorted(unknown)}")
    annotations = {"description", "default"}
    if "$ref" in schema and set(schema) - {"$ref", "description"}:
        raise ValueError("不支持带兄弟约束的 $ref")
    if "enum" in schema or "const" in schema:
        if set(schema) - ({"enum", "const", "type"} | annotations):
            raise ValueError("不支持枚举与额外约束组合")
        if "enum" in schema and "const" in schema:
            raise ValueError("不支持 enum 与 const 同时出现")
        values = schema.get("enum", [schema.get("const")])
        if not values or any(type(v) not in (str, int, float, bool, type(None)) for v in values):
            raise ValueError("枚举只支持非空 JSON 标量目录")
        expected = {"string": str, "integer": int, "number": float, "boolean": bool, "null": type(None)}
        kind = schema.get("type")
        if kind and any(type(v) is not expected.get(kind) for v in values):
            raise ValueError("枚举值与 type 不一致")
    if "oneOf" in schema or "anyOf" in schema:
        if set(schema) - {"oneOf", "anyOf", "discriminator", "description"}:
            raise ValueError("不支持联合与额外约束组合")
        if "oneOf" in schema and "anyOf" in schema:
            raise ValueError("联合只能选择一种语义")
        if "oneOf" in schema and "discriminator" not in schema:
            raise ValueError("oneOf 必须声明判别字段以保证跨语言一致")
    if not any(key in schema for key in ("$ref", "enum", "const", "oneOf", "anyOf")):
        constraints = {
            "string": {"minLength", "pattern", "format"},
            "object": {"properties", "required", "additionalProperties"},
            "array": {"items"}, "integer": set(), "number": set(),
            "boolean": set(), "null": set(), None: set(),
        }
        kind = schema.get("type")
        if kind not in constraints or set(schema) - ({"type"} | annotations | constraints[kind]):
            raise ValueError("不支持的 schema 关键字组合")
        if schema.get("format") and ({"pattern", "minLength"} & set(schema)):
            raise ValueError("format 与字符串约束的组合需要显式实现")
    if "$ref" in schema:
        if schema["$ref"] not in {f"#/components/schemas/{name}" for name in names}:
            raise ValueError(f"无法解析引用: {schema['$ref']}")
    if schema.get("format") not in (None, "date-time"):
        raise ValueError("不支持的 format")
    if schema.get("type") == "object":
        if schema.get("additionalProperties") not in (True, False):
            raise ValueError("object 必须明确 additionalProperties")
        if schema.get("properties") and schema["additionalProperties"]:
            raise ValueError("固定字段对象不得允许额外属性")
        if not set(schema.get("required", [])) <= set(schema.get("properties", {})):
            raise ValueError("required 引用了不存在的字段")
    children = list(schema.get("properties", {}).values()) + schema.get("oneOf", []) + schema.get("anyOf", [])
    if "items" in schema:
        children.append(schema["items"])
    for child in children:
        validate_schema(child, names)


def type_for(schema: dict, language: str) -> str:
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[1]
    if "const" in schema or "enum" in schema:
        values = [schema["const"]] if "const" in schema else schema["enum"]
        if language == "ts":
            return " | ".join(json.dumps(v, ensure_ascii=False) for v in values)
        return "Literal[" + ", ".join(repr(v) for v in values) + "]"
    if "oneOf" in schema or "anyOf" in schema:
        union = " | ".join(type_for(v, language) for v in schema.get("oneOf", schema.get("anyOf", [])))
        if language == "py" and "discriminator" in schema:
            key = schema["discriminator"]["propertyName"]
            return f"Annotated[{union}, Field(discriminator={key!r})]"
        return union
    if not schema or set(schema) <= {"description"}:
        return "JsonValue"
    kind = schema.get("type")
    if kind == "object":
        if "properties" not in schema:
            return "Record<string, JsonValue>" if language == "ts" else "dict[str, JsonValue]"
        if language == "py":
            raise ValueError("内联固定对象请提升为命名 schema")
        required = schema.get("required", [])
        return "{\n" + "\n".join(
            f"  {json.dumps(k)}{'' if k in required else '?'}: {type_for(v, language)};"
            for k, v in schema["properties"].items()
        ) + "\n}"
    if kind == "array":
        item = type_for(schema["items"], language)
        return f"Array<{item}>" if language == "ts" else f"list[{item}]"
    types = {"string": ("string", "str"), "integer": ("number", "int"),
             "number": ("number", "float"), "boolean": ("boolean", "bool"),
             "null": ("null", "None")}
    if kind not in types:
        raise ValueError(f"不支持的 type: {kind}")
    value = types[kind][0 if language == "ts" else 1]
    if language == "py":
        if schema.get("format") == "date-time":
            value = 'Annotated[str, AfterValidator(valid_timestamp), WithJsonSchema({"type": "string", "format": "date-time"})]'
        fields = []
        for source, target in [("minLength", "min_length"), ("pattern", "pattern")]:
            if source in schema:
                fields.append(f"{target}={schema[source]!r}")
        if fields:
            value = f"Annotated[{value}, Field({', '.join(fields)})]"
    return value


def render(doc: dict) -> dict[Path, str]:
    schemas = doc["components"]["schemas"]

    def tags(schema, key):
        if "$ref" in schema:
            return tags(schemas[schema["$ref"].rsplit("/", 1)[1]], key)
        if "oneOf" in schema:
            return set().union(*(tags(branch, key) for branch in schema["oneOf"]))
        return {schema["properties"][key]["const"]}

    for schema in schemas.values():
        validate_schema(schema, set(schemas))
        if "discriminator" in schema:
            key = schema["discriminator"]["propertyName"]
            mapping = {}
            for branch in schema["oneOf"]:
                for tag in tags(branch, key):
                    if tag in mapping:
                        raise ValueError("判别联合的 tag 不得重叠")
                    mapping[tag] = branch["$ref"]
            if schema["discriminator"].get("mapping") != mapping:
                raise ValueError("discriminator mapping 必须与实际 tag 和分支完全一致")
    ts = ["// 由 scripts/generate_contracts.py 生成，请修改 OpenAPI 源文件。",
          "export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };", ""]
    py = ['"""由 scripts/generate_contracts.py 生成，请修改 OpenAPI 源文件。"""',
          "# ruff: noqa: E501", "from __future__ import annotations", "",
          "import json", "import re",
          "from typing import Annotated, Any, Literal, TypeAlias, cast, get_args, get_origin", "",
          "from pydantic import (", "    AfterValidator,", "    AwareDatetime,", "    BaseModel,", "    ConfigDict,",
          "    Field,", "    JsonValue,", "    TypeAdapter,", "    WithJsonSchema,", "    model_validator,", ")", "",
          "", "def valid_timestamp(value: str) -> str:",
          r'    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})", value):',
          '        raise ValueError("时间必须是带时区的 RFC3339")',
          '    TypeAdapter[AwareDatetime](AwareDatetime).validate_json(json.dumps(value))',
          '    return value', "",
          "", "class WireModel(BaseModel):", '    """严格公共 wire 模型。"""',
          '    model_config = ConfigDict(extra="forbid", strict=True, revalidate_instances="always", allow_inf_nan=False)', "",
          '    @model_validator(mode="before")', '    @classmethod',
          '    def strict_literals(cls, value: object) -> object:',
          '        if isinstance(value, dict):',
          '            fields = cast(dict[str, object], value)',
          '            for key, field in cls.model_fields.items():',
          '                annotation = field.annotation',
          '                if get_origin(annotation) is Literal and key in fields:',
          '                    allowed = get_args(annotation)',
          '                    if not any(type(fields[key]) is type(v) and fields[key] == v for v in allowed):',
          '                        raise ValueError("literal 字段不允许类型转换")',
          '        return cast(object, value)', ""]
    for name, schema in schemas.items():
        ts.append(f"export type {name} = {type_for(schema, 'ts')};\n")
        if schema.get("properties"):
            py += ["", f"class {name}(WireModel):", f'    """{name} 合同。"""']
            for key, value in schema["properties"].items():
                suffix = ""
                if key not in schema.get("required", []):
                    if value.get("type") != "object" or "properties" in value:
                        raise ValueError("当前可选字段只支持自由 JSON 对象")
                    suffix = " = Field(default_factory=dict)"
                py.append(f"    {key}: {type_for(value, 'py')}{suffix}")
            py.append("")
        else:
            py += ["", f"{name}: TypeAlias = {type_for(schema, 'py')}", ""]
    catalog = {}
    for branch in schemas["ApiError"]["oneOf"]:
        fields = schemas[branch["$ref"].rsplit("/", 1)[1]]["properties"]
        code = fields["code"]["const"]
        if not code.startswith(fields["category"]["const"] + "_"):
            raise ValueError("错误码前缀与 category 不一致")
        catalog[code] = {k: fields[k]["const"] for k in ("code", "category", "httpStatus")}
        catalog[code]["message"] = fields["message"]["default"]
    ts += [f"export const errorCatalog = {json.dumps(catalog, ensure_ascii=False, indent=2)} as const;",
           "export type ErrorCode = keyof typeof errorCatalog;"]
    py += ["ErrorCode: TypeAlias = " + type_for({"enum": list(catalog)}, "py"), "",
           "ERROR_CATALOG: dict[ErrorCode, dict[str, JsonValue]] = " + pformat(catalog, width=95, sort_dicts=False), ""]
    operations = {}
    operation_docs = {}
    result_types = []
    for path, methods in doc["paths"].items():
        for method, op in methods.items():
            success = op["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[1]
            operations[op["operationId"]] = {"path": path, "method": method.upper(), "responseSchema": success}
            operation_docs[op["operationId"]] = {
                "parameters": op.get("parameters", []),
                "responses": {status: {"headers": response.get("headers", {})}
                              for status, response in op["responses"].items()},
            }
            result_types.append(f'  {op["operationId"]}: {success};')
    def inline(value):
        if isinstance(value, list):
            return [inline(v) for v in value]
        if not isinstance(value, dict):
            return value
        if "$ref" in value:
            return inline(schemas[value["$ref"].rsplit("/", 1)[1]])
        return {k: inline(v) for k, v in value.items()}
    py += ["OPERATION_DOCS: dict[str, dict[str, Any]] = " + pformat(inline(operation_docs), width=95, sort_dicts=False), ""]
    ts += [f"export const operations = {json.dumps(operations, indent=2)} as const;",
           "export interface OperationResponses {", *result_types, "}",
           "export interface SchemaTypes {", *[f"  {n}: {n};" for n in schemas], "}", ""]
    return {
        ROOT / "packages/api-contracts/src/generated.ts": "\n".join(ts),
        ROOT / "apps/backend/src/oncall_pilot/generated_contracts.py": "\n".join(py),
    }


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    outputs = render(json.loads(SOURCE.read_text(encoding="utf-8")))
    for path, content in outputs.items():
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                raise SystemExit(f"合同生成物漂移，请运行 npm run contracts:generate：{path}")
        else:
            path.write_text(content, encoding="utf-8", newline="\n")
    print("合同生成物检查通过" if args.check else "合同生成完成")


if __name__ == "__main__":
    main()
