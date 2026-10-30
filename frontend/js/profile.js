import "../css/input.css";
import { apiRequest } from "./api.js";
import { clearAuthState, getCurrentUser } from "./auth.js";
import { setButtonLoading } from "./form-utils.js";

const requestedId = new URLSearchParams(window.location.search).get("id");
const message = document.querySelector("[data-profile-message]");
const loading = document.querySelector("[data-profile-loading]");
const content = document.querySelector("[data-profile-content]");
const state = { viewer: null, profile: null, isOwn: false, isFollowing: false, relation: null, relationPage: 1 };

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
  const values = Object.entries(error.data || {}).flatMap(([field, errors]) =>
    (Array.isArray(errors) ? errors : [errors]).map((item) => `${field}: ${String(item)}`),
  );
  return values.join(" ") || error.message || "The request could not be completed.";
}

function handleError(error) {
  if (error.status === 401) {
    clearAuthState();
    window.location.replace("/pages/login.html?expired=1");
  } else if (error.status === 403 && error.isCsrfError) {
    showMessage(error.message || "The security token was rejected. Refresh the page and try again.");
  } else if (error.status === 404) {
    showMessage("This profile could not be found.");
  } else if (error.status >= 500) {
    showMessage("CampusStack could not load this profile right now. Please try again.");
  } else {
    showMessage(errorText(error));
  }
}

function formatDate(value) {
  if (!value) return "Not available";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not available" : new Intl.DateTimeFormat(undefined, { dateStyle: "long" }).format(date);
}

function safeImageUrl(value) {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function initials(value) {
  return String(value || "CampusStack member").trim().split(/\s+/).slice(0, 2)
    .map((part) => part.charAt(0).toUpperCase()).join("") || "CS";
}

function profileImage(profile) {
  const wrapper = node("div", "avatar size-20 text-xl");
  const fallback = node("span", "", initials(profile.display_name));
  fallback.dataset.avatarFallback = "";
  wrapper.append(fallback);
  const url = safeImageUrl(profile.profile_image_url);
  if (url) {
    const image = node("img", "size-20 rounded-full object-cover");
    image.src = url;
    image.alt = `${profile.display_name || "Member"} profile image`;
    image.loading = "lazy";
    image.referrerPolicy = "no-referrer";
    image.addEventListener("load", () => { fallback.hidden = true; }, { once: true });
    image.addEventListener("error", () => image.remove(), { once: true });
    wrapper.append(image);
  }
  return wrapper;
}

function stat(label, value, link) {
  const item = node("div", "rounded-xl border border-line bg-white p-4");
  const number = node(link ? "button" : "p", "text-xl font-bold text-ink", String(value ?? 0));
  if (link) {
    number.type = "button";
    number.classList.add("rounded-sm", "hover:text-brand-700", "focus-visible:outline-2", "focus-visible:outline-brand-600");
    number.addEventListener("click", () => loadRelation(link));
    number.setAttribute("aria-label", `View ${label.toLowerCase()}`);
  }
  item.append(number, node("p", "mt-1 text-xs font-medium text-muted", label));
  return item;
}

function detail(label, value) {
  if (value === null || value === undefined || value === "") return null;
  const item = node("div", "py-3 sm:grid sm:grid-cols-[170px_1fr] sm:gap-4");
  item.append(node("dt", "text-sm font-medium text-muted", label));
  item.append(node("dd", "mt-1 text-sm text-ink sm:mt-0", String(value)));
  return item;
}

function renderProfile() {
  const profile = state.profile;
  content.replaceChildren();
  content.hidden = false;
  loading.hidden = true;

  const card = node("section", "card", undefined);
  card.setAttribute("aria-labelledby", "profile-name");
  const header = node("div", "flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between");
  const identity = node("div", "flex items-center gap-5");
  identity.append(profileImage(profile));
  const identityText = node("div");
  const name = profile.display_name || "CampusStack member";
  const nameHeading = node("h1", "text-2xl font-bold tracking-tight sm:text-3xl", name);
  nameHeading.id = "profile-name";
  identityText.append(nameHeading);
  identityText.append(node("p", "mt-2 text-sm text-muted", (profile.account_type || "Member").toLowerCase()));
  identity.append(identityText);
  header.append(identity);

  if (state.isOwn) {
    const edit = node("button", "btn btn-secondary", "Edit profile");
    edit.type = "button";
    edit.addEventListener("click", () => {
      const form = content.querySelector("[data-profile-edit]");
      form.hidden = !form.hidden;
      edit.setAttribute("aria-expanded", String(!form.hidden));
      if (!form.hidden) form.querySelector("input, textarea")?.focus();
    });
    edit.setAttribute("aria-expanded", "false");
    header.append(edit);
  } else if (state.viewer) {
    const follow = node("button", "btn btn-primary", state.isFollowing ? "Following · Unfollow" : "Follow");
    follow.type = "button";
    follow.addEventListener("click", () => changeFollow(follow));
    header.append(follow);
  } else {
    const login = node("a", "btn btn-secondary", "Log in to follow");
    login.href = "/pages/login.html";
    header.append(login);
  }
  card.append(header);

  const facts = node("dl", "mt-6 divide-y divide-line border-y border-line");
  [
    detail("Department", profile.department),
    detail("Academic status", profile.academic_status),
    detail("Batch", profile.batch_start_year && profile.batch_end_year ? `${profile.batch_start_year}–${profile.batch_end_year}` : null),
    detail("Designation", profile.designation),
    detail("Joined", formatDate(profile.joined_at)),
    detail("Biography", profile.biography || "No biography added."),
  ].filter(Boolean).forEach((item) => facts.append(item));
  if (state.isOwn && profile.email) facts.append(detail("Email", profile.email));
  card.append(facts);
  content.append(card);

  const stats = node("section", "mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6");
  stats.setAttribute("aria-label", "Profile statistics");
  const contribution = profile.contributions || {};
  const reputation = profile.reputation || {};
  stats.append(
    stat("Reputation", reputation.reputation ?? 0),
    stat("Questions", contribution.questions_asked ?? 0),
    stat("Answers", contribution.answers_posted ?? 0),
    stat("Accepted", contribution.accepted_answers ?? 0),
    stat("Comments", contribution.comments_posted ?? 0),
    stat("Followers", profile.follower_count ?? 0, "followers"),
  );
  stats.append(stat("Following", profile.following_count ?? 0, "following"));
  content.append(stats);

  const relations = node("section", "card mt-5", undefined);
  relations.id = "profile-relations";
  relations.setAttribute("aria-label", "Profile connections");
  const actions = node("div", "flex flex-wrap gap-3");
  for (const [kind, label, count] of [
    ["followers", `View followers (${profile.follower_count ?? 0})`],
    ["following", `View following (${profile.following_count ?? 0})`],
  ]) {
    const button = node("button", "btn btn-secondary", label);
    button.type = "button";
    button.addEventListener("click", () => loadRelation(kind, button));
    actions.append(button);
  }
  const list = node("div", "mt-4 space-y-3");
  list.hidden = true;
  list.dataset.relationList = "";
  relations.append(actions, list);
  content.append(relations);

  if (state.isOwn) content.append(renderEditForm(profile));
}

function renderEditForm(profile) {
  const card = node("section", "card mt-5");
  card.hidden = true;
  card.dataset.profileEdit = "";
  const heading = node("h2", "text-lg font-semibold", "Edit your profile");
  const note = node("p", "mt-1 text-sm text-muted", "Academic status, department, and batch information are managed by the college.");
  const form = node("form", "mt-5 grid gap-4 sm:grid-cols-2");
  const fields = [];
  const addField = (key, label, { multiline = false, type = "text", value = "", full = false } = {}) => {
    const wrap = node("div", full ? "sm:col-span-2" : "");
    const input = node(multiline ? "textarea" : "input", "form-field");
    input.name = key;
    input.id = `profile-${key}`;
    if (multiline) {
      input.rows = 4;
      if (key === "biography") input.maxLength = 500;
      input.value = value || "";
    } else {
      input.type = type;
      input.value = value || "";
      const maximums = { first_name: 150, last_name: 150, profile_image_url: 500, designation: 120 };
      if (maximums[key]) input.maxLength = maximums[key];
      if (key === "designation") input.required = true;
    }
    const labelNode = node("label", "mb-2 block text-sm font-medium", label);
    labelNode.htmlFor = input.id;
    const error = node("p", "mt-1 text-sm text-red-700");
    error.hidden = true;
    error.dataset.fieldError = key;
    wrap.append(labelNode, input, error);
    form.append(wrap);
    fields.push(key);
  };
  addField("first_name", "First name", { value: profile.first_name });
  addField("last_name", "Last name", { value: profile.last_name });
  if (Object.hasOwn(profile, "biography")) addField("biography", "Biography", { multiline: true, value: profile.biography, full: true });
  if (Object.hasOwn(profile, "profile_image_url")) addField("profile_image_url", "Profile image URL", { type: "url", value: profile.profile_image_url, full: true });
  if (Object.hasOwn(profile, "designation")) addField("designation", "Faculty designation", { value: profile.designation });
  const formMessage = node("p", "text-sm text-red-700 sm:col-span-2");
  formMessage.hidden = true;
  formMessage.dataset.editMessage = "";
  const submit = node("button", "btn btn-primary sm:col-span-2 sm:justify-self-end", "Save profile");
  submit.type = "submit";
  form.append(formMessage, submit);
  form.addEventListener("input", () => {
    form.querySelectorAll("[data-field-error]").forEach((error) => { error.hidden = true; error.textContent = ""; });
    formMessage.hidden = true;
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    const payload = Object.fromEntries(fields.map((key) => [key, form.elements.namedItem(key).value.trim()]));
    setButtonLoading(submit, true, "Saving…");
    try {
      await apiRequest("profiles/me/", { method: "PATCH", body: payload });
      state.profile = await getOwnProfile(state.viewer.id);
      renderProfile();
      showMessage("Profile saved.", "success");
    } catch (error) {
      const serverErrors = error.data && typeof error.data === "object" ? error.data : {};
      let matched = false;
      for (const [key, values] of Object.entries(serverErrors)) {
        const fieldError = form.querySelector(`[data-field-error="${CSS.escape(key)}"]`);
        if (!fieldError) continue;
        fieldError.textContent = Array.isArray(values) ? values.join(" ") : String(values);
        fieldError.hidden = false;
        matched = true;
      }
      formMessage.textContent = matched ? "Please correct the highlighted fields." : errorText(error);
      formMessage.hidden = false;
      setButtonLoading(submit, false);
      if (error.status === 401) handleError(error);
    }
  });
  card.append(heading, note, form);
  return card;
}

async function fetchAll(path) {
  const items = [];
  let next = path;
  while (next) {
    const response = await apiRequest(next);
    if (Array.isArray(response)) return [...items, ...response];
    items.push(...(Array.isArray(response.results) ? response.results : []));
    if (!response.next) break;
    const url = new URL(response.next, window.location.origin);
    next = `${url.pathname.replace(/^\/api\/v1\//, "")}${url.search}`;
  }
  return items;
}

async function getOwnProfile(userId) {
  const [privateProfile, publicProfile] = await Promise.all([
    apiRequest("profiles/me/"),
    apiRequest(`users/${userId}/profile/`),
  ]);
  return { ...publicProfile, ...privateProfile };
}

async function changeFollow(button) {
  setButtonLoading(button, true, state.isFollowing ? "Unfollowing…" : "Following…");
  try {
    const result = await apiRequest(`users/${state.profile.id}/follow/`, {
      method: state.isFollowing ? "DELETE" : "POST",
    });
    state.isFollowing = result.is_following;
    state.profile.follower_count = result.follower_count;
    state.profile.following_count = result.following_count;
    renderProfile();
    showMessage(result.is_following ? "You are following this member." : "You unfollowed this member.", "success");
  } catch (error) {
    handleError(error);
    setButtonLoading(button, false);
  }
}

async function loadRelation(kind, trigger) {
  const panel = content.querySelector("[data-relation-list]");
  if (panel.hidden && state.relation === kind && panel.childElementCount) {
    panel.hidden = false;
    return;
  }
  state.relation = kind;
  state.relationPage = 1;
  await renderRelationPage(kind, 1, trigger);
}

async function renderRelationPage(kind, page, trigger) {
  const panel = content.querySelector("[data-relation-list]");
  panel.hidden = false;
  panel.replaceChildren(node("p", "loading-state", `Loading ${kind}…`));
  if (trigger) setButtonLoading(trigger, true, "Loading…");
  try {
    const path = `users/${state.profile.id}/${kind}/?page=${page}&page_size=20`;
    const response = await apiRequest(path);
    panel.replaceChildren();
    const users = Array.isArray(response) ? response : (response.results || []);
    if (!users.length) panel.append(node("p", "empty-state", `No ${kind} yet.`));
    users.forEach((user) => {
      const row = node("div", "flex flex-wrap items-center justify-between gap-3 rounded-xl border border-line p-3");
      const link = node("a", "font-semibold text-brand-700 hover:underline", user.display_name || "Campus member");
      link.href = `/pages/profile.html?id=${encodeURIComponent(user.id)}`;
      row.append(link, node("span", "badge", (user.account_type || "member").toLowerCase()));
      panel.append(row);
    });
    if (response && !Array.isArray(response) && (response.next || response.previous)) {
      const nav = node("nav", "flex items-center justify-between gap-3");
      nav.setAttribute("aria-label", `${kind} pages`);
      const previous = node("button", "btn btn-secondary", "Previous");
      previous.type = "button";
      previous.disabled = !response.previous;
      previous.addEventListener("click", () => renderRelationPage(kind, Math.max(1, page - 1)));
      const current = node("span", "text-sm text-muted", `Page ${page} · ${response.count} ${kind}`);
      const next = node("button", "btn btn-secondary", "Next");
      next.type = "button";
      next.disabled = !response.next;
      next.addEventListener("click", () => renderRelationPage(kind, page + 1));
      nav.append(previous, current, next);
      panel.append(nav);
    }
  } catch (error) {
    panel.replaceChildren(node("p", "alert form-message-error", errorText(error)));
  } finally {
    if (trigger) setButtonLoading(trigger, false);
  }
}

async function initialize() {
  const id = requestedId && /^\d+$/.test(requestedId) ? Number(requestedId) : null;
  if (requestedId && !id) {
    loading.hidden = true;
    showMessage("A valid profile ID is required.");
    return;
  }
  try {
    try { state.viewer = await getCurrentUser(); } catch { state.viewer = null; }
    state.isOwn = !id ? Boolean(state.viewer) : Boolean(state.viewer && Number(state.viewer.id) === id);
    if (!id && !state.viewer) {
      window.location.replace("/pages/login.html?expired=1");
      return;
    }
    state.profile = state.isOwn
      ? await getOwnProfile(state.viewer.id)
      : await apiRequest(`users/${id}/profile/`);
    if (state.viewer && !state.isOwn) {
      try {
        const following = await fetchAll(`users/${state.viewer.id}/following/?page_size=100`);
        state.isFollowing = following.some((item) => Number(item.id) === Number(state.profile.id));
      } catch {
        showMessage("Follow status could not be checked. You can still open the profile.", "info");
      }
    }
    renderProfile();
  } catch (error) {
    loading.hidden = true;
    handleError(error);
  }
}

initialize();
