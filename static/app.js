const state = {
  bootstrap: null,
  vocabulary: [],
  lessons: [],
  reviews: [],
  dashboard: null,
};

const titles = {
  dashboard: ["Dashboard", "Operational overview for lessons, vocabulary, and AI drafts."],
  vocabulary: ["Vocabulary", "Review AI candidates and manage the vocabulary bank."],
  lessons: ["Lessons", "Generate, preview, and deliver daily Markdown lessons."],
  reviews: ["Reviews", "Log recall results and track learning history."],
  settings: ["Settings", "Manage languages and scheduler configuration."],
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok || payload?.error) {
    throw new Error(payload?.error || `Request failed: ${response.status}`);
  }
  return payload;
}

function notice(message, type = "ok") {
  const box = $("#notice");
  box.textContent = message;
  box.className = `notice ${type === "error" ? "error" : ""}`;
  setTimeout(() => box.classList.add("hidden"), 4500);
}

function languageOptions(includeAll = false) {
  const languages = state.bootstrap.languages;
  const options = includeAll ? ['<option value="">All languages</option>'] : [];
  for (const [code, meta] of Object.entries(languages)) {
    options.push(`<option value="${code}">${meta.name}</option>`);
  }
  if (!includeAll && options.length === 0) {
    options.push('<option value="">Add a language in Settings first</option>');
  }
  return options.join("");
}

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatLanguage(code) {
  return state.bootstrap.languages[code]?.name || code;
}

function wordCard(item, controls = true) {
  const actionLabel = item.status === "active" ? "Archive" : item.source === "ai" && item.status === "draft" ? "Approve" : "Activate";
  return `
    <article class="word-card">
      <header>
        <div>
          <div class="word-title">${escapeHtml(item.word)}${item.reading ? ` · ${escapeHtml(item.reading)}` : ""}</div>
          <div class="word-meta">${formatLanguage(item.language)} · ${escapeHtml(item.level)} · ${escapeHtml(item.part_of_speech)} · ${escapeHtml(item.source)}</div>
        </div>
        <span class="badge ${item.status === "draft" ? "warm" : ""}">${escapeHtml(item.status)}</span>
      </header>
      <p class="word-meta">${escapeHtml(item.meaning_zh)} · ${escapeHtml(item.meaning_en)}</p>
      <p>${escapeHtml(item.example_sentence)}</p>
      <p class="word-meta">${escapeHtml(item.example_translation_zh)}</p>
      ${controls ? `<button class="ghost status-toggle" data-id="${item.id}" data-status="${item.status === "active" ? "archived" : "active"}">${actionLabel}</button>` : ""}
    </article>
  `;
}

async function loadBootstrap() {
  state.bootstrap = await api("/api/bootstrap");
  $("#lesson-date").value = state.bootstrap.today;
  $("#filter-language").innerHTML = languageOptions(true);
  $('[name="language"]').innerHTML = languageOptions(false);
  $('[name="review_date"]').value = state.bootstrap.today;
}

async function loadDashboard() {
  state.dashboard = await api("/api/dashboard");
  renderDashboard();
}

async function loadVocabulary() {
  const language = $("#filter-language").value;
  const status = $("#filter-status").value;
  const source = $("#filter-source").value;
  const query = new URLSearchParams();
  if (language) query.set("language", language);
  if (status) query.set("status", status);
  if (source) query.set("source", source);
  state.vocabulary = await api(`/api/vocabulary?${query}`);
  renderVocabulary();
  renderReviewVocabularyOptions();
}

async function loadLessons() {
  state.lessons = await api("/api/lessons");
  renderLessons();
}

async function loadReviews() {
  state.reviews = await api("/api/reviews");
  renderReviews();
}

function renderDashboard() {
  const counts = state.dashboard.counts;
  const total = counts.reduce((sum, row) => sum + row.total, 0);
  const active = counts.reduce((sum, row) => sum + row.active, 0);
  $("#metrics").innerHTML = [
    metric("Vocabulary", total),
    metric("Active", active),
    metric("AI drafts", state.dashboard.pendingReviewCount),
    metric("Languages", Object.keys(state.bootstrap.languages).length),
  ].join("");

  const lesson = state.dashboard.todayLesson;
  $("#mark-sent").disabled = !lesson || lesson.status === "sent";
  $("#today-lesson").innerHTML = lesson
    ? `<div class="lesson-cards">${lesson.items.map((item) => wordCard(item, false)).join("")}</div><pre class="markdown">${escapeHtml(lesson.generated_message)}</pre>`
    : "No lesson has been generated for today. Open Lessons to generate one.";

  $("#recent-words").innerHTML = state.dashboard.recentWords.length
    ? state.dashboard.recentWords.map((row) => `<div class="log-row"><span>${row.lesson_date} · ${formatLanguage(row.language)}</span><strong>${escapeHtml(row.word)}</strong></div>`).join("")
    : "No recently learned words yet.";
}

function metric(label, value) {
  return `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`;
}

function renderVocabulary() {
  $("#vocab-list").innerHTML = state.vocabulary.length
    ? state.vocabulary.map((item) => wordCard(item)).join("")
    : `<div class="lesson-empty">No vocabulary items match the current filters.</div>`;
}

function renderLessons() {
  $("#lesson-list").innerHTML = state.lessons.length
    ? state.lessons
        .map(
          (lesson) => `
          <article class="lesson-card">
            <header>
              <div>
                <h2>${lesson.lesson_date}</h2>
                <p class="word-meta">${lesson.scheduled_time} · ${lesson.status}</p>
              </div>
              <span class="badge">${lesson.items.length} words</span>
            </header>
            <div class="lesson-cards">${lesson.items.map((item) => wordCard(item, false)).join("")}</div>
            <pre class="markdown">${escapeHtml(lesson.generated_message)}</pre>
          </article>
        `
        )
        .join("")
    : `<section class="panel lesson-empty">No lessons have been generated yet.</section>`;
}

function renderReviewVocabularyOptions() {
  const select = $('[name="vocabulary_item_id"]');
  select.innerHTML = state.vocabulary
    .map((item) => `<option value="${item.id}">${formatLanguage(item.language)} · ${escapeHtml(item.word)} · ${escapeHtml(item.level)}</option>`)
    .join("");
}

function renderReviews() {
  $("#review-list").innerHTML = state.reviews.length
    ? state.reviews.map((review) => `<div class="log-row"><span>${review.review_date} · ${formatLanguage(review.language)} · ${escapeHtml(review.word)}</span><strong>${review.rating}/5</strong></div>`).join("")
    : "No review logs yet.";
}

function renderSettings() {
  const settings = state.bootstrap.settings;
  const languageRows = state.bootstrap.languageList || Object.values(state.bootstrap.languages);
  const rows = [
    ["Daily time", settings.daily_schedule_time],
    ["Duplicate avoidance", `${settings.duplicate_avoidance_days} days`],
    ["AI words need review", settings.require_review_for_ai_words],
    ["Enabled languages", languageRows.filter((language) => language.enabled).map((language) => language.name).join(", ") || "None"],
  ];
  $("#settings-list").innerHTML = rows.map(([key, value]) => `<div class="setting-row"><strong>${key}</strong><span>${value}</span></div>`).join("");
  $("#language-list").innerHTML = languageRows.length
    ? languageRows.map(languageRow).join("")
    : `<div class="lesson-empty">No languages yet. Add one to start building your vocabulary bank.</div>`;
}

function languageRow(language) {
  return `
    <article class="word-card language-row" data-code="${escapeHtml(language.code)}">
      <header>
        <div>
          <div class="word-title">${escapeHtml(language.name)}</div>
          <div class="word-meta">${escapeHtml(language.code)} · minimum ${escapeHtml(language.minimum_level || "any")} · sort ${language.sort_order}</div>
        </div>
        <span class="badge ${language.enabled ? "" : "warm"}">${language.enabled ? "enabled" : "disabled"}</span>
      </header>
      <div class="language-actions">
        <label>Name<input data-field="name" value="${escapeHtml(language.name)}" /></label>
        <label>Minimum<input data-field="minimum_level" value="${escapeHtml(language.minimum_level || "")}" /></label>
        <label>Sort<input data-field="sort_order" type="number" value="${language.sort_order}" /></label>
        <label class="check"><input data-field="enabled" type="checkbox" ${language.enabled ? "checked" : ""} /> Enabled</label>
        <button class="ghost language-save" data-code="${escapeHtml(language.code)}">Save</button>
      </div>
    </article>
  `;
}

async function refreshAll() {
  await Promise.all([loadDashboard(), loadVocabulary(), loadLessons(), loadReviews()]);
  renderSettings();
}

function bindEvents() {
  $$(".tab").forEach((button) => {
    button.addEventListener("click", () => {
      $$(".tab").forEach((tab) => tab.classList.remove("active"));
      $$(".view").forEach((view) => view.classList.remove("active"));
      button.classList.add("active");
      $(`#${button.dataset.view}`).classList.add("active");
      const [title, subtitle] = titles[button.dataset.view];
      $("#view-title").textContent = title;
      $("#view-subtitle").textContent = subtitle;
    });
  });

  $("#generate-today").addEventListener("click", async () => {
    try {
      await api("/api/lessons/generate", {
        method: "POST",
        body: JSON.stringify({ date: $("#lesson-date").value, force: true }),
      });
      await refreshAll();
      notice("Lesson generated.");
    } catch (error) {
      notice(error.message, "error");
    }
  });

  $("#mark-sent").addEventListener("click", async () => {
    const lesson = state.dashboard.todayLesson;
    if (!lesson) return;
    await api(`/api/lessons/${lesson.id}/mark-sent`, { method: "POST" });
    await refreshAll();
    notice("Lesson marked as sent.");
  });

  $("#filter-language").addEventListener("change", loadVocabulary);
  $("#filter-status").addEventListener("change", loadVocabulary);
  $("#filter-source").addEventListener("change", loadVocabulary);
  $("#show-ai-drafts").addEventListener("click", () => {
    $("#filter-status").value = "draft";
    $("#filter-source").value = "ai";
    loadVocabulary();
  });
  $("#reload-vocab").addEventListener("click", loadVocabulary);

  $("#vocab-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const el = event.currentTarget;
    const form = new FormData(el);
    const payload = Object.fromEntries(form.entries());
    try {
      await api("/api/vocabulary", { method: "POST", body: JSON.stringify(payload) });
      el.reset();
      $('[name="language"]').innerHTML = languageOptions(false);
      await refreshAll();
      notice("Vocabulary item added.");
    } catch (error) {
      notice(error.message, "error");
    }
  });

  $("#vocab-list").addEventListener("click", async (event) => {
    const button = event.target.closest(".status-toggle");
    if (!button) return;
    await api(`/api/vocabulary/${button.dataset.id}`, {
      method: "PATCH",
      body: JSON.stringify({ status: button.dataset.status }),
    });
    await refreshAll();
    notice("Vocabulary status updated.");
  });

  $("#review-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const el = event.currentTarget;
    const form = new FormData(el);
    const payload = Object.fromEntries(form.entries());
    payload.recall_success = form.has("recall_success");
    try {
      await api("/api/reviews", { method: "POST", body: JSON.stringify(payload) });
      el.reset();
      $('[name="review_date"]').value = state.bootstrap.today;
      await refreshAll();
      notice("Review saved.");
    } catch (error) {
      notice(error.message, "error");
    }
  });

  $("#language-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const el = event.currentTarget;
    const form = new FormData(el);
    const payload = Object.fromEntries(form.entries());
    payload.enabled = form.has("enabled");
    try {
      await api("/api/languages", { method: "POST", body: JSON.stringify(payload) });
      el.reset();
      el.elements.enabled.checked = true;
      await loadBootstrap();
      await refreshAll();
      notice("Language added.");
    } catch (error) {
      notice(error.message, "error");
    }
  });

  $("#language-list").addEventListener("click", async (event) => {
    const button = event.target.closest(".language-save");
    if (!button) return;
    const row = event.target.closest(".language-row");
    const payload = {};
    row.querySelectorAll("[data-field]").forEach((input) => {
      payload[input.dataset.field] = input.type === "checkbox" ? input.checked : input.value;
    });
    try {
      await api(`/api/languages/${button.dataset.code}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      await loadBootstrap();
      await refreshAll();
      notice("Language updated.");
    } catch (error) {
      notice(error.message, "error");
    }
  });
}

async function boot() {
  bindEvents();
  await loadBootstrap();
  await refreshAll();
}

boot().catch((error) => notice(error.message, "error"));
