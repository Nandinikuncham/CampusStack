import "../css/input.css";
import { getCurrentUser, getWorkspacePath, login } from "./auth.js";
import {
  bindPasswordToggles,
  clearFieldErrors,
  renderFieldErrors,
  setButtonLoading,
  setFormMessage,
} from "./form-utils.js";

const form = document.querySelector("[data-login-form]");
const message = document.querySelector("[data-form-message]");
const submitButton = form?.querySelector("[type='submit']");

bindPasswordToggles();

const search = new URLSearchParams(window.location.search);
if (search.get("expired") === "1") {
  setFormMessage(message, "Your session has expired. Sign in again to continue.");
} else if (search.get("registered") === "student") {
  setFormMessage(message, "Your student account is ready. Sign in to continue.", "success");
} else if (search.get("logged_out") === "1") {
  setFormMessage(message, "You have been signed out.", "success");
}

getCurrentUser()
  .then((user) => {
    if (user) window.location.replace(getWorkspacePath(user.account_type));
  })
  .catch(() => {
    setFormMessage(message, "We could not check your session. Please try again.");
  });

form?.addEventListener("input", () => {
  clearFieldErrors(form);
  if (message?.classList.contains("form-message-error")) setFormMessage(message, "");
});

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFieldErrors(form);
  setFormMessage(message, "");
  if (!form.reportValidity()) return;

  setButtonLoading(submitButton, true, "Signing in…");
  try {
    const user = await login({
      email: form.elements.email.value.trim(),
      password: form.elements.password.value,
    });
    if (!user) {
      setFormMessage(message, "We could not confirm your session. Please sign in again.");
      return;
    }
    window.location.replace(getWorkspacePath(user.account_type));
  } catch (error) {
    renderFieldErrors(form, error.data);
    setFormMessage(message, error.message || "Sign in failed. Please try again.");
  } finally {
    setButtonLoading(submitButton, false);
  }
});
