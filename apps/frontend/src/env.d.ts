/// <reference types="vite/client" />

declare module "virtual:public-config" {
  const config: import("../build/project-config").PublicConfig;
  export default config;
}
