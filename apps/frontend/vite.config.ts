import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig, type Plugin, type UserConfig } from "vite";

import { loadPublicConfig } from "./build/project-config";

const publicConfigId = "virtual:public-config";
const resolvedPublicConfigId = `\0${publicConfigId}`;
const defaultConfigDir = fileURLToPath(new URL("../../config/", import.meta.url));

export function publicConfigPlugin(configDir: string): Plugin {
  return {
    name: "oncall-pilot-public-config",
    resolveId(id) {
      return id === publicConfigId ? resolvedPublicConfigId : undefined;
    },
    async load(id) {
      if (id !== resolvedPublicConfigId) {
        return undefined;
      }
      const publicConfig = await loadPublicConfig(configDir);
      return `export default ${JSON.stringify(publicConfig)};`;
    },
  };
}

export function createViteConfig(configDir = defaultConfigDir): UserConfig {
  return {
    plugins: [vue(), publicConfigPlugin(configDir)],
  };
}

export default defineConfig(createViteConfig());
