(() => {
  "use strict";

  const toggleTextSize = document.getElementById("toggle-text-size");
  const helpDialog = document.getElementById("help-dialog");
  const openHelp = document.getElementById("open-help");
  const closeHelp = document.getElementById("close-help");

  toggleTextSize.addEventListener("click", () => {
    const enabled = document.documentElement.classList.toggle("large-text");
    toggleTextSize.setAttribute("aria-pressed", String(enabled));
  });

  openHelp.addEventListener("click", () => helpDialog.showModal());
  closeHelp.addEventListener("click", () => helpDialog.close());

  document.addEventListener("keydown", (event) => {
    const editable = event.target instanceof HTMLElement &&
      event.target.matches("input, textarea, select, [contenteditable='true']");
    if (event.key.toLowerCase() === "h" && !event.altKey && !event.ctrlKey &&
        !event.metaKey && !editable && !helpDialog.open) {
      event.preventDefault();
      helpDialog.showModal();
    }
  });
})();
