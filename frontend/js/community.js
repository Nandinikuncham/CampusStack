import "../css/input.css";
import { apiRequest } from "./api.js";
import { clearAuthState, getCurrentUser, logout } from "./auth.js";
import { setButtonLoading, setFormMessage } from "./form-utils.js";

const searchForm = document.querySelector("[data-question-search-form]");
const searchInput = searchForm.elements.search;
const tagSelect = document.querySelector("[data-tag-filter]");
const orderSelect = document.querySelector("[data-order-filter]");
const clearFiltersButton = document.querySelector("[data-clear-filters]");
const feed = document.querySelector("[data-question-feed]");
const feedMessage = document.querySelector("[data-feed-message]");
const resultSummary = document.querySelector("[data-result-summary]");
const activeFilter = document.querySelector("[data-active-filter]");
const pagination = document.querySelector("[data-pagination]");
const previousButton = document.querySelector("[data-page-previous]");
const nextButton = document.querySelector("[data-page-next]");
const pageSummary = document.querySelector("[data-page-summary]");
const accountToggle = document.querySelector("[data-account-toggle]");
const accountMenu = document.querySelector("[data-account-menu]");
const logoutButton = document.querySelector("[data-logout]");
const PAGE_SIZE = 20;
const supportedOrdering = new Set(["-created_at", "created_at", "-updated_at", "title"]);
const initialParams = new URLSearchParams(window.location.search);

const state = {
  search: initialParams.get("search") || "",
  tag: initialParams.get("tag") || "",
  ordering: supportedOrdering.has(initialParams.get("ordering"))
    ? initialParams.get("ordering")
    : "-created_at",
  page: Math.max(1, Number.parseInt(initialParams.get("page"), 10) || 1),
  requestId: 0,
  debounceTimer: null,
  tagsUnavailable: false,
  next: null,
  previous: null,
  tagsBySlug: new Map(),
};

searchInput.value = state.search;
tagSelect.value = state.tag;
orderSelect.value = state.ordering;

function showMessage(message, kind = "error") {
  if (!message) {
    feedMessage.hidden = true;
    feedMessage.textContent = "";
    feedMessage.className = "";
    return;
  }
  feedMessage.className = `alert ${kind === "error" ? "form-message-error" : kind === "success" ? "form-message-success" : ""}`;
  setFormMessage(feedMessage, message, kind);
}

function updateAddress() {
  const params = new URLSearchParams();
  if (state.search) params.set("search", state.search);
  if (state.tag) params.set("tag", state.tag);
  if (state.ordering !== "-created_at") params.set("ordering", state.ordering);
  if (state.page > 1) params.set("page", String(state.page));
  const query = params.toString();
  window.history.replaceState(null, "", `${window.location.pathname}${query ? `?${query}` : ""}`);
}

function extractPage(url, fallback) {
  if (!url) return fallback;
  try {
    const parsed = new URL(url, window.location.origin);
    return Math.max(1, Number.parseInt(parsed.searchParams.get("page"), 10) || fallback);
  } catch {
    return fallback;
  }
}

function friendlyError(error) {
  if (error.status === 400) return "The question filters were not accepted. Adjust them and try again.";
  if (error.status === 404) return "The question service could not be found. Try again later.";
  if (error.status >= 500) return "CampusStack could not load questions right now. Please try again shortly.";
  return error.message || "Questions could not be loaded. Please try again.";
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(date);
}

function excerpt(value, maximum = 280) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  if (text.length <= maximum) return text;
  return `${text.slice(0, maximum).trimEnd()}…`;
}

function makeTagButton(slug) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "tag transition-colors hover:border-brand-500 hover:bg-brand-100";
  button.textContent = state.tagsBySlug.get(slug)?.name || slug;
  button.setAttribute("aria-label", `Filter questions by ${button.textContent}`);
  button.addEventListener("click", () => {
    state.tag = state.tag === slug ? "" : slug;
    state.page = 1;
    tagSelect.value = state.tag;
    loadQuestions();
  });
  return button;
}

function renderQuestion(question) {
  const article = document.createElement("article");
  article.className = "card p-5 transition-shadow hover:shadow-card sm:p-6";

  const headingRow = document.createElement("div");
  headingRow.className = "flex flex-wrap items-start justify-between gap-3";
  const title = document.createElement("h2");
  title.className = "min-w-0 flex-1 text-lg font-semibold leading-7 tracking-tight text-ink sm:text-xl";
  const detailLink = document.createElement("a");
  detailLink.className = "rounded-sm hover:text-brand-700 focus-visible:outline-2 focus-visible:outline-brand-600";
  detailLink.href = `/pages/question.html?id=${encodeURIComponent(question.id)}`;
  detailLink.textContent = question.title || "Untitled question";
  title.append(detailLink);
  const status = document.createElement("span");
  status.className = "badge shrink-0";
  status.textContent = question.status === "CLOSED" ? "Closed" : "Open";
  headingRow.append(title, status);
  article.append(headingRow);

  const description = document.createElement("p");
  description.className = "mt-3 whitespace-pre-line text-sm leading-6 text-muted";
  description.textContent = excerpt(question.description);
  article.append(description);

  if (Array.isArray(question.tags) && question.tags.length) {
    const tags = document.createElement("div");
    tags.className = "mt-4 flex flex-wrap gap-2";
    question.tags.forEach((slug) => tags.append(makeTagButton(slug)));
    article.append(tags);
  }

  const footer = document.createElement("div");
  footer.className = "mt-5 flex flex-col gap-3 border-t border-line pt-4 text-sm text-muted sm:flex-row sm:items-center sm:justify-between";
  const author = document.createElement("p");
  author.className = "min-w-0 truncate";
  const authorName = question.author?.name || "Campus member";
  const authorType = question.author?.account_type
    ? ` · ${question.author.account_type.toLowerCase()}`
    : "";
  author.append(document.createTextNode("Asked by "));
  if (question.author?.id) {
    const profileLink = document.createElement("a");
    profileLink.className = "font-semibold text-brand-700 hover:underline";
    profileLink.href = `/pages/profile.html?id=${encodeURIComponent(question.author.id)}`;
    profileLink.textContent = authorName;
    author.append(profileLink);
  } else {
    author.append(document.createTextNode(authorName));
  }
  author.append(document.createTextNode(authorType));
  const metadata = document.createElement("div");
  metadata.className = "flex flex-wrap items-center gap-x-4 gap-y-1";
  const created = document.createElement("time");
  created.dateTime = question.created_at || "";
  created.textContent = formatDate(question.created_at);
  const score = document.createElement("span");
  score.className = "font-semibold text-ink";
  score.textContent = `${Number(question.score) || 0} ${Number(question.score) === 1 ? "vote" : "votes"}`;
  metadata.append(created, score);
  footer.append(author, metadata);
  article.append(footer);
  return article;
}

function renderQuestions(data) {
  feed.replaceChildren();
  const questions = Array.isArray(data.results) ? data.results : [];
  if (!questions.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    const heading = document.createElement("p");
    heading.className = "font-semibold text-ink";
    heading.textContent = state.search || state.tag ? "No questions match these filters." : "No questions yet.";
    const hint = document.createElement("p");
    hint.className = "mt-2";
    hint.textContent = state.search || state.tag
      ? "Try a different search or clear the filters."
      : "When your community asks questions, they will appear here.";
    empty.append(heading, hint);
    feed.append(empty);
  } else {
    questions.forEach((question) => feed.append(renderQuestion(question)));
  }

  const first = questions.length ? (state.page - 1) * PAGE_SIZE + 1 : 0;
  const last = Math.min(state.page * PAGE_SIZE, Number(data.count) || questions.length);
  resultSummary.textContent = Number(data.count) > 0
    ? `Showing ${first}–${last} of ${data.count} questions`
    : "";
  activeFilter.textContent = state.tag
    ? `Tag: ${state.tagsBySlug.get(state.tag)?.name || state.tag}`
    : "";
  state.next = data.next;
  state.previous = data.previous;
  const hasPages = Boolean(data.next || data.previous);
  pagination.hidden = !hasPages;
  previousButton.disabled = !data.previous;
  nextButton.disabled = !data.next;
  pageSummary.textContent = hasPages ? `Page ${state.page}` : "";
}

async function loadQuestions() {
  const requestId = ++state.requestId;
  const params = new URLSearchParams({ page: String(state.page), page_size: String(PAGE_SIZE) });
  params.set("ordering", state.ordering);
  if (state.search) params.set("search", state.search);
  if (state.tag) params.set("tag", state.tag);
  updateAddress();
  showMessage("");
  feed.setAttribute("aria-busy", "true");
  feed.innerHTML = '<div class="loading-state">Loading questions…</div>';

  try {
    const data = await apiRequest(`questions/?${params.toString()}`);
    if (requestId !== state.requestId) return;
    renderQuestions(data);
    if (state.tagsUnavailable) {
      showMessage("Tags could not be loaded. You can still search and browse questions.", "info");
    }
  } catch (error) {
    if (requestId !== state.requestId) return;
    if (error.status === 401 || error.status === 403) {
      clearAuthState();
      window.location.replace("/pages/login.html?expired=1");
      return;
    }
    feed.replaceChildren();
    resultSummary.textContent = "";
    activeFilter.textContent = "";
    pagination.hidden = true;
    showMessage(friendlyError(error));
    const retry = document.createElement("button");
    retry.type = "button";
    retry.className = "btn btn-secondary mt-4";
    retry.textContent = "Try again";
    retry.addEventListener("click", loadQuestions);
    feed.append(retry);
  } finally {
    if (requestId === state.requestId) feed.setAttribute("aria-busy", "false");
  }
}

async function loadTags() {
  const tags = [];
  let next = "tags/?page_size=100";
  while (next) {
    const result = await apiRequest(next);
    tags.push(...(Array.isArray(result.results) ? result.results : []));
    next = result.next ? `${new URL(result.next, window.location.origin).pathname.replace(/^\/api\/v1\//, "")}${new URL(result.next, window.location.origin).search}` : null;
  }
  state.tagsBySlug = new Map(tags.map((tag) => [tag.slug, tag]));
  const selectedSlug = state.tag;
  tagSelect.replaceChildren(new Option("All tags", ""));
  tags.forEach((tag) => tagSelect.add(new Option(tag.name, tag.slug)));
  if (selectedSlug && !state.tagsBySlug.has(selectedSlug)) {
    tagSelect.add(new Option(selectedSlug, selectedSlug));
  }
  tagSelect.value = selectedSlug;
}

function initials(name) {
  return String(name || "CampusStack")
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase())
    .join("") || "CS";
}

function toggleAccountMenu(open) {
  accountMenu.hidden = !open;
  accountToggle.setAttribute("aria-expanded", String(open));
}

accountToggle.addEventListener("click", () => toggleAccountMenu(accountMenu.hidden));
document.addEventListener("click", (event) => {
  if (!accountMenu.contains(event.target) && !accountToggle.contains(event.target)) toggleAccountMenu(false);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !accountMenu.hidden) {
    toggleAccountMenu(false);
    accountToggle.focus();
  }
});

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  clearTimeout(state.debounceTimer);
  state.search = searchInput.value.trim();
  state.page = 1;
  loadQuestions();
});
searchInput.addEventListener("input", () => {
  clearTimeout(state.debounceTimer);
  state.debounceTimer = window.setTimeout(() => {
    state.search = searchInput.value.trim();
    state.page = 1;
    loadQuestions();
  }, 350);
});
tagSelect.addEventListener("change", () => {
  state.tag = tagSelect.value;
  state.page = 1;
  loadQuestions();
});
orderSelect.addEventListener("change", () => {
  state.ordering = orderSelect.value;
  state.page = 1;
  loadQuestions();
});
clearFiltersButton.addEventListener("click", () => {
  searchInput.value = "";
  tagSelect.value = "";
  orderSelect.value = "-created_at";
  state.search = "";
  state.tag = "";
  state.ordering = "-created_at";
  state.page = 1;
  loadQuestions();
});
previousButton.addEventListener("click", () => {
  state.page = extractPage(state.previous, Math.max(1, state.page - 1));
  loadQuestions();
});
nextButton.addEventListener("click", () => {
  state.page = extractPage(state.next, state.page + 1);
  loadQuestions();
});

try {
  const user = await getCurrentUser();
  if (!user) {
    window.location.replace("/pages/login.html?expired=1");
  } else {
    const name = user.name || `${user.first_name || ""} ${user.last_name || ""}`.trim() || "CampusStack member";
    document.querySelector("[data-user-name]").textContent = name;
    document.querySelector("[data-user-avatar]").textContent = initials(name);
    document.querySelector("[data-user-role]").textContent = user.account_type || "Member";
    try {
      await loadTags();
    } catch {
      state.tagsUnavailable = true;
    }
    await loadQuestions();
  }
} catch {
  feed.replaceChildren();
  feed.setAttribute("aria-busy", "false");
  showMessage("We could not verify your session. Check your connection, then refresh or sign in again.");
}

logoutButton.addEventListener("click", async () => {
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
    toggleAccountMenu(false);
    showMessage(error.message || "Could not sign out. Please try again.");
  } finally {
    setButtonLoading(logoutButton, false);
  }
});
