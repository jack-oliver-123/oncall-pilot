import document from "../openapi/foundation.openapi.json";
import type { JsonValue, SchemaTypes } from "./generated";

interface Schema {
  $ref?: string;
  const?: JsonValue;
  enum?: JsonValue[];
  oneOf?: Schema[];
  anyOf?: Schema[];
  type?: string;
  properties?: Record<string, Schema>;
  required?: string[];
  additionalProperties?: boolean;
  items?: Schema;
  minLength?: number;
  pattern?: string;
  format?: string;
}

const schemas: Record<string, Schema> = document.components.schemas;

export class ProtocolError extends Error {
  constructor(message = "响应不符合共享协议") {
    super(message);
    this.name = "ProtocolError";
  }
}

function isJson(value: unknown, depth = 0): value is JsonValue {
  if (depth > 128) return false;
  if (value === null || typeof value === "string" || typeof value === "boolean") return true;
  if (typeof value === "number") return Number.isFinite(value);
  if (Array.isArray(value)) return value.every((v: unknown) => isJson(v, depth + 1));
  if (typeof value !== "object" || Object.getPrototypeOf(value) !== Object.prototype) return false;
  return Object.values(value).every((v: unknown) => isJson(v, depth + 1));
}

function dateTime(value: string): boolean {
  const parts = /^(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(?:\.\d+)?(?:[Zz]|[+-]\d{2}:\d{2})$/.exec(value);
  if (!parts || parts[0] !== value || !Number.isFinite(Date.parse(value))) return false;
  const year = Number(parts[1]);
  const month = Number(parts[2]);
  const day = Number(parts[3]);
  return month >= 1 && month <= 12 && day >= 1 &&
    day <= new Date(Date.UTC(year, month, 0)).getUTCDate() &&
    Number(parts[4]) < 24 && Number(parts[5]) < 60 && Number(parts[6]) < 60;
}

function matches(schema: Schema, value: JsonValue): boolean {
  if (schema.$ref) {
    const target = schemas[schema.$ref.split("/").at(-1) ?? ""];
    return target !== undefined && matches(target, value);
  }
  if ("const" in schema) return value === schema.const;
  if (schema.enum) return schema.enum.includes(value);
  if (schema.oneOf) return schema.oneOf.filter((branch) => matches(branch, value)).length === 1;
  if (schema.anyOf) return schema.anyOf.some((branch) => matches(branch, value));
  if (schema.type === "object") {
    if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
    const properties = schema.properties ?? {};
    if (schema.required?.some((key) => !Object.hasOwn(value, key))) return false;
    return Object.entries(value).every(([key, item]) => {
      const field = Object.hasOwn(properties, key) ? properties[key] : undefined;
      return field ? matches(field, item) : schema.additionalProperties === true;
    });
  }
  if (schema.type === "array") {
    const items = schema.items;
    return Array.isArray(value) && items !== undefined && value.every((item) => matches(items, item));
  }
  if (schema.type === "string") {
    if (typeof value !== "string") return false;
    if (schema.minLength !== undefined && [...value].length < schema.minLength) return false;
    if (schema.pattern) {
      const match = new RegExp(schema.pattern).exec(value);
      if (!match || (schema.pattern.startsWith("^") && schema.pattern.endsWith("$") && match[0] !== value)) return false;
    }
    return schema.format !== "date-time" || dateTime(value);
  }
  if (schema.type === "integer") return typeof value === "number" && Number.isInteger(value);
  if (schema.type === "number") return typeof value === "number";
  if (schema.type === "boolean") return typeof value === "boolean";
  if (schema.type === "null") return value === null;
  return schema.type === undefined;
}

export function parseContract<Name extends keyof SchemaTypes>(name: Name, value: unknown): SchemaTypes[Name] {
  const schema = schemas[name];
  if (!schema || !isJson(value) || !matches(schema, value)) {
    throw new ProtocolError(`响应不符合 ${name} 合同`);
  }
  return value as SchemaTypes[Name];
}
