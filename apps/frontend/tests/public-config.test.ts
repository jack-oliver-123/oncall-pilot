import { mkdir, mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { afterEach, describe, expect, it } from "vitest";
import { build as viteBuild } from "vite";

import { loadPublicConfig } from "../build/project-config";
import { createViteConfig } from "../vite.config";

const temporaryDirectories: string[] = [];

async function createConfigDir(): Promise<string> {
  const root = await mkdtemp(join(tmpdir(), "oncall-pilot-frontend-"));
  temporaryDirectories.push(root);
  const configDir = join(root, "config");
  await mkdir(configDir);
  return configDir;
}

async function writeJson(configDir: string, filename: string, value: object): Promise<void> {
  await writeFile(join(configDir, filename), JSON.stringify(value), "utf8");
}

async function readDirectoryRecursively(directory: string): Promise<string> {
  const contents: string[] = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) {
      contents.push(await readDirectoryRecursively(path));
    } else {
      contents.push(await readFile(path, "utf8"));
    }
  }
  return contents.join("\n");
}

afterEach(async () => {
  await Promise.all(
    temporaryDirectories
      .splice(0)
      .map((directory) => rm(directory, { recursive: true, force: true })),
  );
});

describe("loadPublicConfig", () => {
  it("递归合并用户配置并只返回浏览器 allowlist", async () => {
    const configDir = await createConfigDir();
    await writeJson(configDir, "project.json", {
      frontend: {
        title: "On-call Pilot",
        apiBaseUrl: "http://127.0.0.1:8000",
        analytics: { publicKey: "" },
      },
      llm: { apiKey: "FOUNDATION_SENTINEL_LLM" },
      cls: { secret: "FOUNDATION_SENTINEL_CLS" },
      mcp: { password: "FOUNDATION_SENTINEL_MCP" },
      minio: { secretKey: "FOUNDATION_SENTINEL_MINIO" },
    });
    await writeJson(configDir, "user.project.json", {
      frontend: { title: "我的值班工作台" },
    });

    expect(await loadPublicConfig(configDir)).toEqual({
      frontend: {
        title: "我的值班工作台",
        apiBaseUrl: "http://127.0.0.1:8000",
        analytics: { publicKey: "" },
      },
    });
  });

  it("缺失必需项目配置时指出 project.json", async () => {
    const configDir = await createConfigDir();

    await expect(loadPublicConfig(configDir)).rejects.toThrow("project.json");
  });

  it.each([
    ["project.json", "not-json"],
    ["project.json", "[]"],
    ["user.project.json", "not-json"],
    ["user.project.json", "[]"],
  ])("无效配置指出来源文件 %s", async (filename, content) => {
    const configDir = await createConfigDir();
    await writeJson(configDir, "project.json", {
      frontend: {
        title: "On-call Pilot",
        apiBaseUrl: "http://127.0.0.1:8000",
        analytics: { publicKey: "" },
      },
    });
    await writeFile(join(configDir, filename), content, "utf8");

    await expect(loadPublicConfig(configDir)).rejects.toThrow(filename);
  });

  it("真实生产构建不会把私有 sentinel 写入 dist", async () => {
    const configDir = await createConfigDir();
    const root = join(configDir, "..", "fixture-app");
    const outDir = join(configDir, "..", "dist");
    await mkdir(root);
    await writeJson(configDir, "project.json", {
      frontend: {
        title: "On-call Pilot 公开标题",
        apiBaseUrl: "http://127.0.0.1:8000",
        analytics: { publicKey: "" },
      },
      llm: { apiKey: "FOUNDATION_SENTINEL_LLM" },
      cls: { secret: "FOUNDATION_SENTINEL_CLS" },
      mcp: { password: "FOUNDATION_SENTINEL_MCP" },
      minio: { secretKey: "FOUNDATION_SENTINEL_MINIO" },
    });
    await writeFile(
      join(root, "index.html"),
      '<div id="app"></div><script type="module" src="/entry.ts"></script>',
      "utf8",
    );
    await writeFile(
      join(root, "entry.ts"),
      [
        'import config from "virtual:public-config";',
        'document.querySelector("#app")!.textContent = config.frontend.title;',
      ].join("\n"),
      "utf8",
    );

    await viteBuild({
      ...createViteConfig(configDir),
      root,
      logLevel: "silent",
      build: { outDir, emptyOutDir: true, minify: false },
    });

    const output = await readDirectoryRecursively(outDir);
    expect(output).toContain("On-call Pilot 公开标题");
    expect(output).not.toContain("FOUNDATION_SENTINEL_LLM");
    expect(output).not.toContain("FOUNDATION_SENTINEL_CLS");
    expect(output).not.toContain("FOUNDATION_SENTINEL_MCP");
    expect(output).not.toContain("FOUNDATION_SENTINEL_MINIO");
  });
});
