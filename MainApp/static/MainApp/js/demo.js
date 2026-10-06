(() => {
  const themes = new Set(["light", "dark", "cupcake"]);
  let theme = "light";
  try {
    const saved = localStorage.getItem("starter-theme");
    if (themes.has(saved)) theme = saved;
  } catch (_) {
    // Theme selection still works when browser storage is unavailable.
  }
  document.documentElement.dataset.theme = theme;

  document.addEventListener("DOMContentLoaded", () => {
    const selector = document.getElementById("theme-select");
    if (selector) {
      selector.value = theme;
      selector.disabled = false;
      selector.addEventListener("change", () => {
        if (!themes.has(selector.value)) return;
        document.documentElement.dataset.theme = selector.value;
        try {
          localStorage.setItem("starter-theme", selector.value);
        } catch (_) {
          // Private browsing can disable storage; keep the current selection.
        }
      });
    }
    const form = document.getElementById("preview-form");
    if (form) {
      const heading = document.getElementById("preview-heading");
      form.addEventListener("submit", (event) => {
        event.preventDefault();
        const name = form.elements.display_name.value.trim();
        heading.textContent = name ? `Hello, ${name}.` : "Hello, maker.";
      });
      form.addEventListener("reset", () => { heading.textContent = "Hello, maker."; });
      form.querySelector("fieldset").disabled = false;
    }
  });
})();
