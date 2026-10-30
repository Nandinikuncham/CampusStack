import "../css/input.css";
import { registerFaculty, registerStudent } from "./auth.js";
import {
  bindPasswordToggles,
  clearFieldErrors,
  renderFieldErrors,
  setButtonLoading,
  setFormMessage,
} from "./form-utils.js";

const form = document.querySelector("[data-registration-form]");
const message = document.querySelector("[data-form-message]");
const successLink = document.querySelector("[data-success-login]");
const submitButton = form?.querySelector("[type='submit']");
const registrationType = form?.dataset.registrationType;

bindPasswordToggles();

form?.addEventListener("input", () => {
  clearFieldErrors(form);
  if (message?.classList.contains("form-message-error")) setFormMessage(message, "");
});

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFieldErrors(form);
  setFormMessage(message, "");
  if (successLink) successLink.hidden = true;
  if (!form.reportValidity()) return;

  const fields = form.elements;
  const password = fields.password.value;
  const passwordConfirmation = fields.password_confirmation.value;
  if (password !== passwordConfirmation) {
    const confirmationError = form.querySelector('[data-field-error="password_confirmation"]');
    confirmationError.textContent = "Passwords do not match.";
    confirmationError.hidden = false;
    fields.password_confirmation.setAttribute("aria-invalid", "true");
    fields.password_confirmation.focus();
    return;
  }

  let payload;
  if (registrationType === "student") {
    if (Number(fields.batch_end_year.value) < Number(fields.batch_start_year.value)) {
      showLocalFieldError(form, fields.batch_end_year, "Batch end year must be the same as or later than the start year.");
      return;
    }
    if (fields.expected_graduation_date.value < fields.admission_date.value) {
      showLocalFieldError(form, fields.expected_graduation_date, "Graduation cannot precede admission.");
      return;
    }
    payload = {
      name: fields.name.value.trim(),
      email: fields.email.value.trim(),
      password,
      department: fields.department.value.trim(),
      batch_start_year: Number(fields.batch_start_year.value),
      batch_end_year: Number(fields.batch_end_year.value),
      admission_date: fields.admission_date.value,
      expected_graduation_date: fields.expected_graduation_date.value,
    };
  } else {
    payload = {
      name: fields.name.value.trim(),
      email: fields.email.value.trim(),
      password,
      department: fields.department.value.trim(),
      designation: fields.designation.value.trim(),
    };
  }

  setButtonLoading(submitButton, true, "Creating account…");
  try {
    if (registrationType === "student") {
      await registerStudent(payload);
      form.reset();
      setFormMessage(message, "Your student account has been created. Sign in to continue.", "success");
    } else {
      await registerFaculty(payload);
      form.reset();
      setFormMessage(
        message,
        "Your faculty registration is submitted and awaiting administrator approval. Approved faculty features are unavailable until your account is approved.",
        "success",
      );
    }
    if (successLink) successLink.hidden = false;
  } catch (error) {
    renderFieldErrors(form, error.data);
    setFormMessage(message, error.message || "Registration failed. Please review the form.");
  } finally {
    setButtonLoading(submitButton, false);
  }
});

function showLocalFieldError(formElement, field, errorText) {
  const messageElement = formElement.querySelector(
    `[data-field-error="${CSS.escape(field.name)}"]`,
  );
  if (messageElement) {
    messageElement.textContent = errorText;
    messageElement.hidden = false;
  }
  field.setAttribute("aria-invalid", "true");
  field.focus();
}
