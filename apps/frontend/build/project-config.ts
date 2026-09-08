import { readFile } from "node:fs/promises";
import { join } from "node:path";

type JsonObject = Record<string, unknown>;

export interface PublicConfig {
  frontend: {
    title: string;
    apiBaseUrl: string;
    analytics: {
      publicKey: string;
    };
  };
}

function isJsonObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

async function readJsonObject(path: string, required: boolean): Promise<JsonObject> {
  let content: string;
  try {
    content = await readFile(path, "utf8");
  } catch (error: unknown) {
    if (!required && error instanceof Error && "code" in error && error.code === "ENOENT") {
      return {};
    }
    throw new Error(`无法读取配置文件 ${path}`, { cause: error });
  }

  let value: unknown;
  try {
    value = JSON.parse(content) as unknown;
  } catch (error: unknown) {
    throw new Error(`配置文件不是有效 JSON: ${path}`, { cause: error });
  }
  if (!isJsonObject(value)) {
    throw new Error(`配置文件根节点必须是 JSON object: ${path}`);
  }
  return value;
}

function deepMerge(project: JsonObject, user: JsonObject): JsonObject {
  const merged: JsonObject = { ...project };
  for (const [key, userValue] of Object.entries(user)) {
    const projectValue = merged[key];
    merged[key] =
      isJsonObject(projectValue) && isJsonObject(userValue)
        ? deepMerge(projectValue, userValue)
        : userValue;
  }
  return merged;
}

function requiredObject(parent: JsonObject, key: string, source: string): JsonObject {
  const value = parent[key];
  if (!isJsonObject(value)) {
    throw new Error(`${source} 缺少 ${key} object`);
  }
  return value;
}

function requiredString(parent: JsonObject, key: string, source: string): string {
  const value = parent[key];
  if (typeof value !== "string") {
    throw new Error(`${source} 缺少 ${key} string`);
  }
  return value;
}

export async function loadPublicConfig(configDir: string): Promise<PublicConfig> {
  const project = await readJsonObject(join(configDir, "project.json"), true);
  const user = await readJsonObject(join(configDir, "user.project.json"), false);
  const merged = deepMerge(project, user);
  const frontend = requiredObject(merged, "frontend", "项目配置");
  const analytics = requiredObject(frontend, "analytics", "frontend");

  return Object.freeze({
    frontend: Object.freeze({
      title: requiredString(frontend, "title", "frontend"),
      apiBaseUrl: requiredString(frontend, "apiBaseUrl", "frontend"),
      analytics: Object.freeze({
        publicKey: requiredString(analytics, "publicKey", "frontend.analytics"),
      }),
    }),
  });
}
