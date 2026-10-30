import { apiRequest } from "./api.js";

let cachedUser = null;
let hasLoadedUser = false;
let currentUserRequest = null;

const workspacePaths = {
  STUDENT: "/pages/workspace.html#student",
  FACULTY: "/pages/workspace.html#faculty",
  ADMIN: "/pages/workspace.html#admin",
};

export function getWorkspacePath(accountType) {
  return workspacePaths[accountType] || "/pages/login.html";
}

export function clearAuthState() {
  cachedUser = null;
  hasLoadedUser = false;
  currentUserRequest = null;
}

export async function getCurrentUser({ force = false } = {}) {
  if (force) clearAuthState();
  if (hasLoadedUser) return cachedUser;
  if (currentUserRequest) return currentUserRequest;

  currentUserRequest = apiRequest("auth/me/")
    .then((response) => {
      cachedUser = response?.user || null;
      hasLoadedUser = true;
      return cachedUser;
    })
    .catch((error) => {
      if (error.status === 401 || error.status === 403) {
        cachedUser = null;
        hasLoadedUser = true;
        return null;
      }
      throw error;
    })
    .finally(() => {
      currentUserRequest = null;
    });

  return currentUserRequest;
}

export async function login(credentials) {
  await apiRequest("auth/login/", { method: "POST", body: credentials });
  return getCurrentUser({ force: true });
}

export function registerStudent(profile) {
  return apiRequest("auth/register/student/", { method: "POST", body: profile });
}

export function registerFaculty(profile) {
  return apiRequest("auth/register/faculty/", { method: "POST", body: profile });
}

export async function logout() {
  await apiRequest("auth/logout/", { method: "POST" });
  clearAuthState();
}
