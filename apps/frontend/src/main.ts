import { createApplication } from "./application";
import { publicConfig } from "./config";
import "./styles.css";

document.title = publicConfig.frontend.title;
const { app, router } = createApplication({
  baseUrl: publicConfig.frontend.apiBaseUrl,
  storage: window.localStorage,
});
app.use(router);
app.mount("#app");
