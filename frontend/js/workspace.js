import "../css/input.css";
import { clearAuthState, getCurrentUser, getWorkspacePath, logout } from "./auth.js";
import { setButtonLoading, setFormMessage } from "./form-utils.js";

const message = document.querySelector("[data-workspace-message]");
const logoutButton = document.querySelector("[data-logout]");
const nameElement = document.querySelector("[data-user-name]");
const roleElement = document.querySelector("[data-user-role]");
const heading = document.querySelector("[data-workspace-heading]");
const description = document.querySelector("[data-workspace-description]");

const roleCopy = {
  STUDENT: {
    label: "Student",
    heading: "Your campus workspace",
    description: "You are signed in. The student workspace and community features will arrive in a later phase.",
  },
  FACULTY: {
    label: "Faculty",
    heading: "Your faculty workspace",
    description: "Your account is approved. Faculty workspace tools will arrive in a later phase.",
  },
  ADMIN: {
    label: "Administrator",
    heading: "Your administrator workspace",
    description: "You are signed in. Administrator tools will arrive in a later phase.",
  },
};

try {
  const user = await getCurrentUser();
  if (!user) {
    window.location.replace("/pages/login.html?expired=1");
  } else {
    const role = roleCopy[user.account_type];
    if (!role) {
      clearAuthState();
      window.location.replace("/pages/login.html");
    } else {
      const expectedPath = getWorkspacePath(user.account_type);
      if (window.location.pathname + window.location.hash !== expectedPath) {
        window.history.replaceState(null, "", expectedPath);
      }
      nameElement.textContent = user.name || `${user.first_name} ${user.last_name}`.trim() || "CampusStack member";
      roleElement.textContent = role.label;
      heading.textContent = role.heading;

      if (
        user.account_type === "FACULTY" &&
        user.profile?.approval_status === "PENDING"
      ) {
        description.textContent =
          "Your faculty registration is awaiting administrator approval. Faculty-only features remain unavailable until approval.";
      } else {
        description.textContent = role.description;
      }
    }
  }
} catch {
  setFormMessage(message, "We could not verify your session. Refresh the page or sign in again.");
}

logoutButton?.addEventListener("click", async () => {
  setFormMessage(message, "");
  setButtonLoading(logoutButton, true, "Signing out…");
  try {
    await logout();
    window.location.replace("/pages/login.html?logged_out=1");
  } catch (error) {
    if (error.status === 401 || (error.status === 403 && !error.isCsrfError)) {
      clearAuthState();
      window.location.replace("/pages/login.html?expired=1");
      return;
    }
    setFormMessage(message, error.message || "Could not sign out. Please try again.");
  } finally {
    setButtonLoading(logoutButton, false);
  }
});
