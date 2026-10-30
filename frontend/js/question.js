import "../css/input.css";
import { apiRequest } from "./api.js";
import { clearAuthState, getCurrentUser } from "./auth.js";
import { setButtonLoading } from "./form-utils.js";

const params = new URLSearchParams(window.location.search);
const questionId = params.get("id");
const pageMessage = document.querySelector("[data-page-message]");
const questionPanel = document.querySelector("[data-question-panel]");
const answersPanel = document.querySelector("[data-answers]");
const answerCount = document.querySelector("[data-answer-count]");
const answerForm = document.querySelector("[data-answer-form]");
const answerLogin = document.querySelector("[data-answer-login]");
const answerError = document.querySelector("[data-answer-error]");
const closedMessage = document.querySelector("[data-closed-message]");

const state = {
  user: null,
  question: null,
  answers: [],
  questionComments: [],
  answerComments: new Map(),
  voteValues: new Map(),
  voteBusy: new Set(),
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function showMessage(message, kind = "error") {
  pageMessage.replaceChildren();
  pageMessage.hidden = !message;
  if (!message) return;
  pageMessage.className = `alert ${kind === "error" ? "form-message-error" : ""}`;
  pageMessage.setAttribute("role", kind === "error" ? "alert" : "status");
  pageMessage.append(document.createTextNode(message));
}

function responseMessage(error) {
  const data = error.data;
  if (typeof data?.detail === "string") return data.detail;
  if (data && typeof data === "object") {
    const messages = Object.entries(data).flatMap(([field, value]) => {
      const items = Array.isArray(value) ? value : [value];
      return items.map((item) => `${field === "non_field_errors" ? "" : `${field}: `}${String(item)}`);
    });
    if (messages.length) return messages.join(" ");
  }
  return error.message || "The request could not be completed. Please try again.";
}

function handleRequestError(error) {
  if (error.status === 401) {
    clearAuthState();
    window.location.replace("/pages/login.html?expired=1");
    return;
  }
  if (error.status === 404) {
    showMessage("This question or discussion item could not be found.");
    return;
  }
  if (error.status === 403) {
    showMessage(state.user
      ? responseMessage(error)
      : "The current backend requires sign-in to view discussions. Sign in to continue.", "info");
    if (!state.user) addLoginLink(pageMessage);
    return;
  }
  if (error.status >= 500) {
    showMessage("CampusStack could not complete that request. Please try again shortly.");
    return;
  }
  showMessage(responseMessage(error));
}

function addLoginLink(container) {
  const link = element("a", "btn btn-primary mt-4", "Log in");
  link.href = "/pages/login.html";
  container.append(link);
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Date unavailable";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(date);
}

function canManage(authorId) {
  return Boolean(state.user && (
    state.user.account_type === "ADMIN" || Number(state.user.id) === Number(authorId)
  ));
}

function authorLine(author) {
  const line = element("p", "text-sm text-muted");
  const name = author?.name || "Campus member";
  const role = author?.account_type ? ` · ${author.account_type.toLowerCase()}` : "";
  line.textContent = `${name}${role}`;
  return line;
}

function makeVoteControls(type, id, item, authorId) {
  const controls = element("div", "flex flex-wrap items-center gap-2");
  const summary = element("span", "min-w-16 text-center text-sm font-semibold text-ink", `${Number(item.score) || 0} score`);
  summary.setAttribute("aria-live", "polite");
  controls.append(summary);

  if (!state.user) {
    const link = element("a", "nav-link", "Log in to vote");
    link.href = "/pages/login.html";
    controls.append(link);
    return controls;
  }

  const buttons = [];
  const updateButtons = (value) => {
    buttons.forEach((button) => {
      const selected = value !== undefined && Number(button.dataset.voteValue) === value;
      button.setAttribute("aria-pressed", String(selected));
      button.classList.toggle("bg-brand-100", selected);
      button.classList.toggle("text-brand-800", selected);
    });
  };

  for (const [value, label] of [[1, "Upvote"], [-1, "Downvote"]]) {
    const button = element("button", "btn btn-secondary min-h-10 px-3", label);
    button.type = "button";
    button.dataset.voteValue = String(value);
    button.setAttribute("aria-label", `${label} this ${type}`);
    button.addEventListener("click", async () => {
      await submitVote(type, id, value, controls, summary, buttons, authorId);
    });
    buttons.push(button);
    controls.append(button);
  }
  const remove = element("button", "nav-link", "Remove vote");
  remove.type = "button";
  remove.addEventListener("click", async () => {
    await submitVote(type, id, null, controls, summary, buttons, authorId);
  });
  controls.append(remove);
  if (Number(state.user.id) === Number(authorId)) {
    controls.querySelectorAll("button").forEach((button) => { button.disabled = true; });
    const note = element("span", "text-xs text-muted", "You cannot vote on your own content.");
    controls.append(note);
  }
  const knownVote = state.voteValues.get(`${type}:${id}`);
  if (knownVote !== undefined) updateButtons(knownVote);
  return controls;
}

async function submitVote(type, id, value, controls, summary, buttons, authorId) {
  const key = `${type}:${id}`;
  if (state.voteBusy.has(key) || Number(state.user.id) === Number(authorId)) return;
  state.voteBusy.add(key);
  controls.querySelectorAll("button").forEach((button) => { button.disabled = true; });
  try {
    const response = await apiRequest(`${type === "question" ? "questions" : "answers"}/${id}/vote/`, {
      method: value === null ? "DELETE" : "POST",
      ...(value === null ? {} : { body: { value } }),
    });
    state.voteValues.set(key, response.vote?.value ?? null);
    summary.textContent = `${Number(response.score) || 0} score`;
    buttons.forEach((button) => {
      const selected = response.vote?.value !== undefined && Number(button.dataset.voteValue) === Number(response.vote.value);
      button.setAttribute("aria-pressed", String(selected));
      button.classList.toggle("bg-brand-100", selected);
      button.classList.toggle("text-brand-800", selected);
    });
    showMessage("Vote updated.", "success");
  } catch (error) {
    handleRequestError(error);
  } finally {
    state.voteBusy.delete(key);
    controls.querySelectorAll("button").forEach((button) => { button.disabled = Number(state.user.id) === Number(authorId); });
  }
}

function makeTag(slug) {
  return element("span", "tag", slug);
}

function renderQuestion() {
  const question = state.question;
  const container = element("div");
  const top = element("div", "flex flex-wrap items-start justify-between gap-4");
  const title = element("h1", "text-2xl font-bold leading-tight tracking-tight sm:text-3xl", question.title);
  title.id = "question-title";
  top.append(title);
  const status = element("span", "badge shrink-0", question.status === "CLOSED" ? "Closed" : "Open");
  top.append(status);
  container.append(top);

  const metadata = element("div", "mt-4 flex flex-wrap items-center gap-x-3 gap-y-1");
  metadata.append(authorLine(question.author));
  const dates = element("div", "flex flex-wrap gap-x-3 text-xs text-muted");
  const created = element("time", "", `Asked ${formatDate(question.created_at)}`);
  created.dateTime = question.created_at || "";
  dates.append(created);
  if (question.updated_at && question.updated_at !== question.created_at) {
    const updated = element("time", "", `Updated ${formatDate(question.updated_at)}`);
    updated.dateTime = question.updated_at;
    dates.append(updated);
  }
  metadata.append(dates);
  container.append(metadata);

  const body = element("div", "prose-campus mt-7 whitespace-pre-wrap break-words text-base leading-8 text-ink", question.description);
  container.append(body);
  if (Array.isArray(question.tags) && question.tags.length) {
    const tags = element("div", "mt-6 flex flex-wrap gap-2");
    question.tags.forEach((slug) => tags.append(makeTag(slug)));
    container.append(tags);
  }

  const actions = element("div", "mt-7 flex flex-wrap items-center justify-between gap-4 border-t border-line pt-5");
  actions.append(makeVoteControls("question", question.id, question, question.author?.id));
  const manage = element("div", "flex flex-wrap gap-2");
  if (canManage(question.author?.id)) {
    const edit = element("button", "btn btn-secondary", "Edit question");
    edit.type = "button";
    edit.addEventListener("click", () => renderQuestionEditor());
    const remove = element("button", "btn btn-secondary text-red-700", "Delete question");
    remove.type = "button";
    remove.addEventListener("click", () => deleteQuestion(remove));
    manage.append(edit, remove);
  }
  actions.append(manage);
  container.append(actions);

  const comments = element("section", "mt-7 border-t border-line pt-5");
  comments.setAttribute("aria-label", "Question comments");
  comments.append(renderCommentsBlock("question", question.id, state.questionComments));
  container.append(comments);

  questionPanel.replaceChildren(container);
  questionPanel.setAttribute("aria-busy", "false");
}

function renderQuestionEditor() {
  const question = state.question;
  const form = element("form", "mt-6 space-y-4 rounded-xl border border-line bg-canvas p-4");
  const titleLabel = element("label", "block text-sm font-medium", "Question title");
  titleLabel.htmlFor = "edit-question-title";
  const title = element("input", "form-field");
  title.id = "edit-question-title";
  title.name = "title";
  title.maxLength = 200;
  title.required = true;
  title.value = question.title;
  const bodyLabel = element("label", "block text-sm font-medium", "Question body");
  bodyLabel.htmlFor = "edit-question-description";
  const body = element("textarea", "form-field min-h-36 resize-y");
  body.id = "edit-question-description";
  body.name = "description";
  body.required = true;
  body.value = question.description;
  const controls = element("div", "flex justify-end gap-2");
  const cancel = element("button", "btn btn-secondary", "Cancel");
  cancel.type = "button";
  cancel.addEventListener("click", renderQuestion);
  const save = element("button", "btn btn-primary", "Save changes");
  save.type = "submit";
  controls.append(cancel, save);
  form.append(titleLabel, title, bodyLabel, body, controls);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    setButtonLoading(save, true, "Saving…");
    try {
      state.question = await apiRequest(`questions/${question.id}/`, {
        method: "PATCH",
        body: { title: title.value.trim(), description: body.value.trim() },
      });
      await refreshDiscussion();
      showMessage("Question updated.", "success");
    } catch (error) {
      handleRequestError(error);
      setButtonLoading(save, false);
    }
  });
  questionPanel.querySelector("[aria-labelledby='question-title']")?.append(form);
  if (!form.isConnected) questionPanel.append(form);
}

async function deleteQuestion(button) {
  if (!window.confirm("Delete this question and its discussion? This cannot be undone.")) return;
  setButtonLoading(button, true, "Deleting…");
  try {
    await apiRequest(`questions/${state.question.id}/`, { method: "DELETE" });
    window.location.replace("/pages/workspace.html");
  } catch (error) {
    handleRequestError(error);
    setButtonLoading(button, false);
  }
}

function renderCommentsBlock(targetType, targetId, comments) {
  const section = element("div", "space-y-3");
  const heading = element("h3", "text-sm font-semibold text-muted", `Comments${comments.length ? ` · ${comments.length}` : ""}`);
  section.append(heading);
  const list = element("div", "divide-y divide-line");
  if (!comments.length) {
    list.append(element("p", "py-2 text-sm text-muted", "No comments yet."));
  } else {
    comments.forEach((comment) => list.append(renderComment(comment, targetType, targetId)));
  }
  section.append(list);
  if (state.user) {
    const form = commentForm(targetType, targetId, () => refreshComments(targetType, targetId));
    section.append(form);
  } else {
    const login = element("a", "nav-link inline-flex", "Log in to comment");
    login.href = "/pages/login.html";
    section.append(login);
  }
  return section;
}

function renderComment(comment, targetType, targetId) {
  const item = element("article", "py-3 first:pt-1");
  const header = element("div", "flex flex-wrap items-center justify-between gap-2");
  const author = element("p", "text-xs font-semibold text-muted", comment.author?.name || "Campus member");
  const time = element("time", "text-xs text-muted", formatDate(comment.created_at));
  time.dateTime = comment.created_at || "";
  header.append(author, time);
  item.append(header);
  item.append(element("p", "mt-1 whitespace-pre-wrap break-words text-sm leading-6", comment.content));
  if (canManage(comment.author?.id)) {
    const controls = element("div", "mt-2 flex gap-2");
    const edit = element("button", "nav-link px-2 py-1 text-xs", "Edit");
    edit.type = "button";
    edit.addEventListener("click", () => renderCommentEditor(item, comment, targetType, targetId));
    const remove = element("button", "nav-link px-2 py-1 text-xs text-red-700", "Delete");
    remove.type = "button";
    remove.addEventListener("click", async () => {
      if (!window.confirm("Delete this comment? This cannot be undone.")) return;
      setButtonLoading(remove, true, "Deleting…");
      try {
        await apiRequest(`comments/${comment.id}/`, { method: "DELETE" });
        await refreshComments(targetType, targetId);
      } catch (error) {
        handleRequestError(error);
        setButtonLoading(remove, false);
      }
    });
    controls.append(edit, remove);
    item.append(controls);
  }
  return item;
}

function renderCommentEditor(container, comment, targetType, targetId) {
  const form = element("form", "mt-2 space-y-2");
  const textarea = element("textarea", "form-field min-h-20 resize-y");
  textarea.value = comment.content;
  textarea.required = true;
  textarea.setAttribute("aria-label", "Edit comment");
  const actions = element("div", "flex justify-end gap-2");
  const cancel = element("button", "btn btn-secondary", "Cancel");
  cancel.type = "button";
  cancel.addEventListener("click", () => refreshComments(targetType, targetId));
  const save = element("button", "btn btn-primary", "Save");
  save.type = "submit";
  actions.append(cancel, save);
  form.append(textarea, actions);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    setButtonLoading(save, true, "Saving…");
    try {
      await apiRequest(`comments/${comment.id}/`, { method: "PATCH", body: { content: textarea.value.trim() } });
      await refreshComments(targetType, targetId);
    } catch (error) {
      handleRequestError(error);
      setButtonLoading(save, false);
    }
  });
  container.replaceChildren(form);
  textarea.focus();
}

function commentForm(targetType, targetId, onSuccess) {
  const form = element("form", "mt-3 flex flex-col gap-2 sm:flex-row sm:items-start");
  const textarea = element("textarea", "form-field min-h-11 flex-1 resize-y py-2.5");
  textarea.rows = 2;
  textarea.required = true;
  textarea.placeholder = "Add a comment…";
  textarea.setAttribute("aria-label", "Add a comment");
  const submit = element("button", "btn btn-secondary", "Comment");
  submit.type = "submit";
  form.append(textarea, submit);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    setButtonLoading(submit, true, "Posting…");
    try {
      await apiRequest(`${targetType === "question" ? "questions" : "answers"}/${targetId}/comments/`, {
        method: "POST",
        body: { content: textarea.value.trim() },
      });
      await onSuccess();
      showMessage("Comment posted.", "success");
    } catch (error) {
      handleRequestError(error);
      setButtonLoading(submit, false);
    }
  });
  return form;
}

async function refreshComments(targetType, targetId) {
  const comments = await fetchAll(`${targetType === "question" ? "questions" : "answers"}/${targetId}/comments/?page_size=100`);
  if (targetType === "question") {
    state.questionComments = comments;
    renderQuestion();
  } else {
    state.answerComments.set(Number(targetId), comments);
    renderAnswers();
  }
}

function renderAnswers() {
  answersPanel.replaceChildren();
  answerCount.textContent = state.answers.length ? `(${state.answers.length})` : "(0)";
  if (!state.answers.length) {
    answersPanel.append(element("div", "empty-state", "No answers yet. Be the first to share a helpful response."));
    answersPanel.setAttribute("aria-busy", "false");
    return;
  }
  state.answers.forEach((answer) => answersPanel.append(renderAnswer(answer)));
  answersPanel.setAttribute("aria-busy", "false");
}

function renderAnswer(answer) {
  const card = element("article", `card p-5 sm:p-6 ${answer.is_accepted ? "border-emerald-300 bg-emerald-50/40" : ""}`);
  const top = element("div", "flex flex-wrap items-start justify-between gap-3");
  const heading = element("h3", "text-base font-semibold", `Answer by ${answer.author?.name || "Campus member"}`);
  top.append(heading);
  if (answer.is_accepted) top.append(element("span", "badge border border-emerald-200 bg-emerald-50 text-emerald-800", "Accepted answer"));
  card.append(top);
  const time = element("time", "mt-1 block text-xs text-muted", `Posted ${formatDate(answer.created_at)}`);
  time.dateTime = answer.created_at || "";
  card.append(time);
  card.append(element("div", "mt-4 whitespace-pre-wrap break-words text-sm leading-7 text-ink", answer.body));

  const actions = element("div", "mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4");
  actions.append(makeVoteControls("answer", answer.id, answer, answer.author?.id));
  const controls = element("div", "flex flex-wrap gap-2");
  if (canManage(answer.author?.id)) {
    const edit = element("button", "btn btn-secondary", "Edit answer");
    edit.type = "button";
    edit.addEventListener("click", () => renderAnswerEditor(card, answer));
    const remove = element("button", "btn btn-secondary text-red-700", "Delete answer");
    remove.type = "button";
    remove.addEventListener("click", async () => {
      if (!window.confirm("Delete this answer? This cannot be undone.")) return;
      setButtonLoading(remove, true, "Deleting…");
      try {
        await apiRequest(`answers/${answer.id}/`, { method: "DELETE" });
        state.answers = state.answers.filter((item) => item.id !== answer.id);
        state.answerComments.delete(Number(answer.id));
        renderAnswers();
      } catch (error) {
        handleRequestError(error);
        setButtonLoading(remove, false);
      }
    });
    controls.append(edit, remove);
  }
  if (state.user && state.question?.author?.id === state.user.id && Number(answer.question) === Number(state.question.id)) {
    const accept = element("button", "btn btn-secondary", answer.is_accepted ? "Unaccept answer" : "Accept answer");
    accept.type = "button";
    accept.addEventListener("click", async () => {
      setButtonLoading(accept, true, answer.is_accepted ? "Updating…" : "Accepting…");
      try {
        const updated = await apiRequest(`questions/${state.question.id}/answers/${answer.id}/accept/`, {
          method: answer.is_accepted ? "DELETE" : "POST",
        });
        state.answers = state.answers.map((item) => item.id === updated.id
          ? updated
          : { ...item, is_accepted: false });
        renderAnswers();
        showMessage(updated.is_accepted ? "Answer accepted." : "Answer unaccepted.", "success");
      } catch (error) {
        handleRequestError(error);
        setButtonLoading(accept, false);
      }
    });
    controls.append(accept);
  }
  actions.append(controls);
  card.append(actions);

  const commentArea = element("section", "mt-5 border-t border-line pt-4");
  commentArea.setAttribute("aria-label", "Answer comments");
  const toggle = element("button", "nav-link px-0", "Show comments");
  toggle.type = "button";
  toggle.setAttribute("aria-expanded", "false");
  commentArea.append(toggle);
  const commentsContainer = element("div", "mt-2");
  commentsContainer.hidden = true;
  const loadedComments = state.answerComments.get(Number(answer.id));
  if (loadedComments) commentsContainer.append(renderCommentsBlock("answer", answer.id, loadedComments));
  toggle.addEventListener("click", async () => {
    if (!state.user) {
      window.location.assign("/pages/login.html");
      return;
    }
    const open = commentsContainer.hidden;
    commentsContainer.hidden = !open;
    toggle.setAttribute("aria-expanded", String(open));
    toggle.textContent = open ? "Hide comments" : "Show comments";
    if (open && !state.answerComments.has(Number(answer.id))) {
      toggle.disabled = true;
      commentsContainer.append(element("p", "loading-state", "Loading comments…"));
      try {
        const comments = await fetchAll(`answers/${answer.id}/comments/?page_size=100`);
        state.answerComments.set(Number(answer.id), comments);
        commentsContainer.replaceChildren(renderCommentsBlock("answer", answer.id, comments));
      } catch (error) {
        commentsContainer.replaceChildren();
        handleRequestError(error);
      } finally {
        toggle.disabled = false;
      }
    }
  });
  commentArea.append(commentsContainer);
  card.append(commentArea);
  return card;
}

function renderAnswerEditor(card, answer) {
  const form = element("form", "mt-4 space-y-3");
  const textarea = element("textarea", "form-field min-h-36 resize-y");
  textarea.value = answer.body;
  textarea.required = true;
  textarea.setAttribute("aria-label", "Edit answer");
  const actions = element("div", "flex justify-end gap-2");
  const cancel = element("button", "btn btn-secondary", "Cancel");
  cancel.type = "button";
  cancel.addEventListener("click", renderAnswers);
  const save = element("button", "btn btn-primary", "Save answer");
  save.type = "submit";
  actions.append(cancel, save);
  form.append(textarea, actions);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    setButtonLoading(save, true, "Saving…");
    try {
      const updated = await apiRequest(`answers/${answer.id}/`, { method: "PATCH", body: { body: textarea.value.trim() } });
      state.answers = state.answers.map((item) => item.id === updated.id ? updated : item);
      renderAnswers();
      showMessage("Answer updated.", "success");
    } catch (error) {
      handleRequestError(error);
      setButtonLoading(save, false);
    }
  });
  card.append(form);
  textarea.focus();
}

async function fetchAll(path) {
  const items = [];
  let next = path;
  while (next) {
    const data = await apiRequest(next);
    if (Array.isArray(data)) {
      items.push(...data);
      break;
    }
    items.push(...(Array.isArray(data.results) ? data.results : []));
    if (!data.next) break;
    const url = new URL(data.next, window.location.origin);
    next = `${url.pathname.replace(/^\/api\/v1\//, "")}${url.search}`;
  }
  return items;
}

async function refreshDiscussion() {
  const [question, answers, comments] = await Promise.all([
    apiRequest(`questions/${questionId}/`),
    fetchAll(`questions/${questionId}/answers/?page_size=100`),
    fetchAll(`questions/${questionId}/comments/?page_size=100`),
  ]);
  state.question = question;
  state.answers = answers;
  state.questionComments = comments;
  renderQuestion();
  renderAnswers();
  document.querySelector("[data-closed-message]").hidden = question.status !== "CLOSED";
  answerForm.hidden = !state.user || question.status !== "OPEN";
  answerLogin.hidden = Boolean(state.user) || question.status !== "OPEN";
}

answerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const body = answerForm.elements.body.value.trim();
  answerError.hidden = true;
  if (!body) {
    answerError.textContent = "Write an answer before submitting.";
    answerError.hidden = false;
    answerForm.elements.body.focus();
    return;
  }
  const submit = answerForm.querySelector("[type='submit']");
  setButtonLoading(submit, true, "Posting…");
  try {
    await apiRequest(`questions/${questionId}/answers/`, { method: "POST", body: { body } });
    answerForm.reset();
    await refreshDiscussion();
    showMessage("Answer posted.", "success");
  } catch (error) {
    answerError.textContent = responseMessage(error);
    answerError.hidden = false;
    handleRequestError(error);
  } finally {
    setButtonLoading(submit, false);
  }
});

async function initialize() {
  if (!questionId || !/^\d+$/.test(questionId)) {
    showMessage("A valid question ID is required.");
    questionPanel.replaceChildren(element("div", "empty-state", "Question ID is missing or invalid."));
    answersPanel.replaceChildren(element("div", "empty-state", "Answers are unavailable."));
    questionPanel.setAttribute("aria-busy", "false");
    answersPanel.setAttribute("aria-busy", "false");
    return;
  }
  try {
    state.user = await getCurrentUser();
    if (!state.user) {
      answerLogin.hidden = false;
    }
    answersPanel.setAttribute("aria-busy", "true");
    await refreshDiscussion();
  } catch (error) {
    questionPanel.replaceChildren(element("div", "empty-state", error.status === 404
      ? "This question was not found."
      : "The discussion could not be loaded."));
    answersPanel.replaceChildren(element("div", "empty-state", "Answers could not be loaded."));
    questionPanel.setAttribute("aria-busy", "false");
    answersPanel.setAttribute("aria-busy", "false");
    if (error.status === 404) {
      handleRequestError(error);
    } else if (error.status === 403 && !state.user) {
      showMessage("The current backend requires sign-in to view questions and discussions. Sign in to continue.", "info");
      addLoginLink(pageMessage);
    } else {
      handleRequestError(error);
    }
  }
}

initialize();
