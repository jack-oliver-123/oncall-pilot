import { createApp } from "vue";

import App from "./App.vue";
import { publicConfig } from "./config";
import "./styles.css";

document.title = publicConfig.frontend.title;
createApp(App).mount("#app");
