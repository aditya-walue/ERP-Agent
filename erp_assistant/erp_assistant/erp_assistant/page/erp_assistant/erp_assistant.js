// Desk page controller. Builds a single-page wrapper and mounts the Vue chat
// app (exposed globally by erp_assistant.bundle.js via app_include_js).
frappe.pages["erp-assistant"].on_page_load = function (wrapper) {
  const page = frappe.ui.make_app_page({
    parent: wrapper,
    title: "ERP Implementation Assistant",
    single_column: true,
  });

  const mount = document.createElement("div");
  mount.id = "erp-assistant-app";
  page.main.append(mount);

  const start = () => {
    if (window.mountErpAssistant) {
      window.mountErpAssistant("#erp-assistant-app");
    } else {
      // Bundle not loaded yet (first paint after build); retry briefly.
      setTimeout(start, 150);
    }
  };
  start();
};
