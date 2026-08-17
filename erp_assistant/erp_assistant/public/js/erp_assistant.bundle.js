// Build entrypoint. `bench build --app erp_assistant` compiles this (and the
// imported .vue SFC) via Frappe's esbuild pipeline into
// erp_assistant/public/dist/js/erp_assistant.bundle.js, loaded on Desk by the
// app_include_js hook. It only exposes a global mount function; the Desk page
// controller decides when/where to mount.
import { createApp } from "vue";
import App from "./App.vue";

window.mountErpAssistant = function (target) {
  const app = createApp(App);
  app.mount(target);
  return app;
};
