import { API_BASE_URL } from "./config.js";

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export class ApiError extends Error {
  constructor(message, { status = 0, data = null, isCsrfError = false } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.data = data;
    this.isCsrfError = isCsrfError;
  }
}

function apiUrl(path) {
  return `${API_BASE_URL.replace(/\/$/, "")}/${path.replace(/^\//, "")}`;
}

async function readResponse(response) {
  const text = await response.text();
  if (!text) return null;

  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function messageForError(data, status) {
  if (data && typeof data === "object" && typeof data.detail === "string") {
    return data.detail;
  }
  if (status === 0) {
    return "CampusStack could not reach the server. Check your connection and try again.";
  }
  return "The request could not be completed. Please try again.";
}

async function fetchCsrfToken() {
  let response;
  try {
    response = await fetch(apiUrl("auth/csrf/"), {
      method: "GET",
      credentials: "include",
      headers: { Accept: "application/json" },
    });
  } catch {
    throw new ApiError(messageForError(null, 0));
  }

  const data = await readResponse(response);
  if (!response.ok || !data?.csrf_token) {
    throw new ApiError(messageForError(data, response.status), {
      status: response.status,
      data,
    });
  }
  return data.csrf_token;
}

export async function apiRequest(path, { method = "GET", body, headers = {} } = {}) {
  const normalizedMethod = method.toUpperCase();
  const requestHeaders = new Headers({ Accept: "application/json", ...headers });

  if (UNSAFE_METHODS.has(normalizedMethod)) {
    requestHeaders.set("X-CSRFToken", await fetchCsrfToken());
  }

  const options = {
    method: normalizedMethod,
    credentials: "include",
    headers: requestHeaders,
  };
  if (body !== undefined) {
    requestHeaders.set("Content-Type", "application/json");
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(apiUrl(path), options);
  } catch {
    throw new ApiError(messageForError(null, 0));
  }

  const data = await readResponse(response);
  if (!response.ok) {
    const isCsrfError =
      response.status === 403 &&
      data &&
      typeof data === "object" &&
      data.detail === "CSRF verification failed.";
    throw new ApiError(
      isCsrfError
        ? "The security token was rejected. Refresh the page and try again."
        : messageForError(data, response.status),
      { status: response.status, data, isCsrfError },
    );
  }
  return data;
}
