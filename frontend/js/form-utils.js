export function setFormMessage(element, message, kind = "error") {
  if (!element) return;
  element.textContent = message;
  element.hidden = !message;
  element.classList.toggle("form-message-error", kind === "error");
  element.classList.toggle("form-message-success", kind === "success");
  element.setAttribute("role", kind === "error" ? "alert" : "status");
}

export function clearFieldErrors(form) {
  form.querySelectorAll("[data-field-error]").forEach((message) => {
    message.textContent = "";
    message.hidden = true;
  });
  form.querySelectorAll("[aria-invalid='true']").forEach((field) => {
    field.removeAttribute("aria-invalid");
  });
}

export function renderFieldErrors(form, data) {
  if (!data || typeof data !== "object" || Array.isArray(data)) return false;

  let matchedField = false;
  for (const [name, errors] of Object.entries(data)) {
    if (name === "detail" || name === "non_field_errors") continue;
    const field = form.elements.namedItem(name);
    const message = form.querySelector(`[data-field-error="${CSS.escape(name)}"]`);
    if (!message) continue;

    const text = Array.isArray(errors) ? errors.join(" ") : String(errors);
    message.textContent = text;
    message.hidden = !text;
    if (field && "setAttribute" in field) field.setAttribute("aria-invalid", "true");
    matchedField = true;
  }
  return matchedField;
}

export function setButtonLoading(button, loading, loadingText = "Please wait…") {
  if (!button) return;
  if (loading) {
    button.dataset.originalText = button.textContent.trim();
    button.textContent = loadingText;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
  } else {
    button.textContent = button.dataset.originalText || button.textContent;
    button.disabled = false;
    button.removeAttribute("aria-busy");
    delete button.dataset.originalText;
  }
}

export function bindPasswordToggles(root = document) {
  root.querySelectorAll("[data-password-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.getElementById(button.getAttribute("aria-controls"));
      if (!input) return;
      const reveal = input.type === "password";
      input.type = reveal ? "text" : "password";
      button.setAttribute("aria-pressed", String(reveal));
      button.textContent = reveal ? "Hide" : "Show";
    });
  });
}
