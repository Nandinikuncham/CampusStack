import "../css/input.css";
import { apiRequest } from "./api.js";
import { clearAuthState, getCurrentUser } from "./auth.js";
import { setButtonLoading } from "./form-utils.js";

const loading = document.querySelector("[data-following-loading]");
const content = document.querySelector("[data-following-content]");
const message = document.querySelector("[data-following-message]");
const usersBox = document.querySelector("[data-following-users]");
const followedTagsBox = document.querySelector("[data-followed-tags]");
const tagDirectory = document.querySelector("[data-tag-directory]");
const state = {
  user: null,
  followedTagIds: new Set(),
  usersPage: 1,
  followedPage: 1,
  tagsPage: 1,
};

function node(tag, className, text) {
  const value = document.createElement(tag);
  if (className) value.className = className;
  if (text !== undefined) value.textContent = text;
  return value;
}

function showMessage(text, kind = "error") {
  message.replaceChildren();
  message.hidden = !text;
  if (!text) return;
  message.className = `alert ${kind === "error" ? "form-message-error" : ""}`;
  message.setAttribute("role", kind === "error" ? "alert" : "status");
  message.textContent = text;
}

function errorText(error) {
  if (typeof error.data?.detail === "string") return error.data.detail;
  const details = Object.entries(error.data || {}).flatMap(([field, values]) =>
    (Array.isArray(values) ? values : [values]).map((value) => `${field}: ${String(value)}`),
  );
  return details.join(" ") || error.message || "The request could not be completed.";
}

function handleError(error) {
  if (error.status === 403 && error.isCsrfError) {
    showMessage(error.message || "The security token was rejected. Refresh the page and try again.");
    return;
  }
  if (error.status === 401 || error.status === 403) {
    clearAuthState();
    window.location.replace("/pages/login.html?expired=1");
  } else if (error.status === 404) {
    showMessage("That community member or tag could not be found.");
  } else if (error.status >= 500) {
    showMessage("CampusStack could not complete that request. Please try again.");
  } else {
    showMessage(errorText(error));
  }
}

function pageFrom(url, fallback) {
  if (!url) return fallback;
  return Math.max(1, Number.parseInt(new URL(url, window.location.origin).searchParams.get("page"), 10) || fallback);
}

async function fetchAll(path) {
  const result = [];
  let next = path;
  while (next) {
    const response = await apiRequest(next);
    if (Array.isArray(response)) return [...result, ...response];
    result.push(...(Array.isArray(response.results) ? response.results : []));
    if (!response.next) break;
    const url = new URL(response.next, window.location.origin);
    next = `${url.pathname.replace(/^\/api\/v1\//, "")}${url.search}`;
  }
  return result;
}

function setPagination(selector, response, page, onPrevious, onNext) {
  const nav = document.querySelector(selector);
  const prev = nav.querySelector("button:first-child");
  const next = nav.querySelector("button:last-child");
  const label = nav.querySelector("span");
  const paginated = response && !Array.isArray(response);
  const hasPages = paginated && (response.next || response.previous);
  nav.hidden = !hasPages;
  if (!hasPages) return;
  prev.disabled = !response.previous;
  next.disabled = !response.next;
  label.textContent = `Page ${page} · ${response.count} total`;
  prev.onclick = () => onPrevious(pageFrom(response.previous, page - 1));
  next.onclick = () => onNext(pageFrom(response.next, page + 1));
}

function profileLink(user) {
  const link = node("a", "font-semibold text-brand-700 hover:underline", user.display_name || "Campus member");
  link.href = `/pages/profile.html?id=${encodeURIComponent(user.id)}`;
  return link;
}

async function loadUsers(page = 1) {
  state.usersPage = page;
  usersBox.setAttribute("aria-busy", "true");
  usersBox.replaceChildren(node("p", "loading-state", "Loading people you follow…"));
  try {
    const response = await apiRequest(`users/${state.user.id}/following/?page=${page}&page_size=20`);
    const users = Array.isArray(response) ? response : response.results || [];
    usersBox.replaceChildren();
    document.querySelector("[data-following-count]").textContent = Array.isArray(response) ? `${users.length} people` : `${response.count} people`;
    if (!users.length) usersBox.append(node("p", "empty-state", "You are not following any members yet. Visit a profile to follow someone."));
    users.forEach((user) => {
      const row = node("article", "flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line p-4");
      const identity = node("div", "flex items-center gap-3");
      const avatar = node("span", "avatar", String(user.display_name || "CS").split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase() || "").join(""));
      avatar.setAttribute("aria-hidden", "true");
      const details = node("div");
      details.append(profileLink(user), node("p", "mt-1 text-xs text-muted", (user.account_type || "member").toLowerCase()));
      identity.append(avatar, details);
      const unfollow = node("button", "btn btn-secondary", "Unfollow");
      unfollow.type = "button";
      unfollow.addEventListener("click", async () => {
        setButtonLoading(unfollow, true, "Unfollowing…");
        try {
          await apiRequest(`users/${user.id}/follow/`, { method: "DELETE" });
          await loadUsers(page);
          showMessage(`You unfollowed ${user.display_name || "this member"}.`, "success");
        } catch (error) {
          handleError(error);
          setButtonLoading(unfollow, false);
        }
      });
      row.append(identity, unfollow);
      usersBox.append(row);
    });
    setPagination("[data-users-pagination]", response, page, loadUsers, loadUsers);
  } catch (error) {
    usersBox.replaceChildren(node("p", "alert form-message-error", errorText(error)));
    handleError(error);
  } finally {
    usersBox.setAttribute("aria-busy", "false");
  }
}

async function loadFollowedTags(page = 1) {
  state.followedPage = page;
  followedTagsBox.setAttribute("aria-busy", "true");
  followedTagsBox.replaceChildren(node("p", "loading-state", "Loading followed tags…"));
  try {
    const response = await apiRequest(`tags/followed/?page=${page}&page_size=20`);
    const tags = Array.isArray(response) ? response : response.results || [];
    followedTagsBox.replaceChildren();
    document.querySelector("[data-followed-tags-count]").textContent = Array.isArray(response) ? `${tags.length} tags` : `${response.count} tags`;
    if (!tags.length) followedTagsBox.append(node("p", "empty-state", "You are not following any tags yet. Browse the directory below."));
    tags.forEach((tag) => followedTagsBox.append(renderTagRow(tag, true)));
    setPagination("[data-followed-tags-pagination]", response, page, loadFollowedTags, loadFollowedTags);
  } catch (error) {
    followedTagsBox.replaceChildren(node("p", "alert form-message-error", errorText(error)));
    handleError(error);
  } finally {
    followedTagsBox.setAttribute("aria-busy", "false");
  }
}

function renderTagRow(tag, isFollowed) {
  const row = node("article", "flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line p-4");
  const details = node("div", "min-w-0");
  const title = node("a", "font-semibold text-brand-700 hover:underline", tag.name);
  title.href = `/pages/workspace.html?tag=${encodeURIComponent(tag.slug)}`;
  details.append(title);
  if (tag.description) details.append(node("p", "mt-1 text-sm text-muted", tag.description));
  details.append(node("p", "mt-2 text-xs text-muted", `${Number(tag.follower_count) || 0} followers`));
  const button = node("button", "btn btn-secondary shrink-0", isFollowed ? "Unfollow tag" : "Follow tag");
  button.type = "button";
  button.addEventListener("click", async () => {
    setButtonLoading(button, true, isFollowed ? "Unfollowing…" : "Following…");
    try {
      const result = await apiRequest(`tags/${tag.id}/follow/`, { method: isFollowed ? "DELETE" : "POST" });
      tag.follower_count = result.follower_count;
      if (result.is_following) state.followedTagIds.add(Number(tag.id));
      else state.followedTagIds.delete(Number(tag.id));
      await Promise.all([loadFollowedTags(state.followedPage), loadTagDirectory(state.tagsPage)]);
      showMessage(result.is_following ? `You are following ${tag.name}.` : `You unfollowed ${tag.name}.`, "success");
    } catch (error) {
      handleError(error);
      setButtonLoading(button, false);
    }
  });
  row.append(details, button);
  return row;
}

async function loadTagDirectory(page = 1) {
  state.tagsPage = page;
  tagDirectory.setAttribute("aria-busy", "true");
  tagDirectory.replaceChildren(node("p", "loading-state sm:col-span-2", "Loading tags…"));
  try {
    const response = await apiRequest(`tags/?page=${page}&page_size=20`);
    const tags = Array.isArray(response) ? response : response.results || [];
    tagDirectory.replaceChildren();
    document.querySelector("[data-tag-directory-count]").textContent = Array.isArray(response) ? `${tags.length} tags` : `${response.count} tags`;
    if (!tags.length) tagDirectory.append(node("p", "empty-state sm:col-span-2", "No tags are available yet."));
    tags.forEach((tag) => tagDirectory.append(renderTagRow(tag, state.followedTagIds.has(Number(tag.id)))));
    setPagination("[data-tag-directory-pagination]", response, page, loadTagDirectory, loadTagDirectory);
  } catch (error) {
    tagDirectory.replaceChildren(node("p", "alert form-message-error sm:col-span-2", errorText(error)));
    handleError(error);
  } finally {
    tagDirectory.setAttribute("aria-busy", "false");
  }
}

async function initialize() {
  try {
    state.user = await getCurrentUser();
    if (!state.user) {
      window.location.replace("/pages/login.html?expired=1");
      return;
    }
    state.followedTagIds = new Set((await fetchAll("tags/followed/?page_size=100")).map((tag) => Number(tag.id)));
    loading.hidden = true;
    content.hidden = false;
    await Promise.all([loadUsers(), loadFollowedTags(), loadTagDirectory()]);
  } catch (error) {
    loading.hidden = true;
    handleError(error);
  }
}

initialize();
