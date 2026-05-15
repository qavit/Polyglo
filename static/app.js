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

const svg = (path, opts = "") =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" ${opts}>${path}</svg>`;

const icon = {
  archive: svg(`<rect x="2" y="4" width="20" height="5" rx="1"/><path d="M4 9v10a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V9"/><path d="M10 13h4"/>`),
  check:   svg(`<polyline points="20 6 9 17 4 12"/>`, `stroke-width="2.5"`),
  edit:    svg(`<path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4z"/>`),
  trash:   svg(`<polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>`),
  plus:    svg(`<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>`, `stroke-width="2.5"`),
  x:       svg(`<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>`, `stroke-width="2.5"`),
  refresh: svg(`<path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>`),
  send:    svg(`<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>`),
  zap:     svg(`<polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>`, `stroke-width="2.5"`),
  star:    svg(`<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>`),
};

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
  const isActive = item.status === "active";
  const isAiDraft = item.source === "ai" && item.status === "draft";
  const statusIcon = isActive ? icon.archive : icon.check;
  const statusTooltip = isActive ? "Archive" : isAiDraft ? "Approve" : "Activate";
  const statusTarget = isActive ? "archived" : "active";

  const editForm = controls ? `
    <div class="edit-panel hidden" data-id="${item.id}">
      <div class="form-grid" style="margin-top:12px">
        <label>Word<input name="word" value="${escapeHtml(item.word)}" /></label>
        <label>Reading<input name="reading" value="${escapeHtml(item.reading || "")}" /></label>
        <label>Level<input name="level" value="${escapeHtml(item.level)}" /></label>
        <label>Part of speech<input name="part_of_speech" value="${escapeHtml(item.part_of_speech)}" /></label>
        <label class="wide">Chinese meaning<input name="meaning_zh" value="${escapeHtml(item.meaning_zh)}" /></label>
        <label class="wide">English definition<input name="meaning_en" value="${escapeHtml(item.meaning_en)}" /></label>
        <label class="wide">Example<textarea name="example_sentence">${escapeHtml(item.example_sentence)}</textarea></label>
        <label class="wide">Chinese example<textarea name="example_translation_zh">${escapeHtml(item.example_translation_zh)}</textarea></label>
        <label class="wide">Collocation<textarea name="collocation">${escapeHtml(item.collocation || "")}</textarea></label>
        <label class="wide">Note<textarea name="note">${escapeHtml(item.note || "")}</textarea></label>
        <label class="wide">Mnemonic<textarea name="mnemonic">${escapeHtml(item.mnemonic || "")}</textarea></label>
        <button class="primary btn-icon save-vocab-edit" data-id="${item.id}">${icon.check} Save</button>
        <button class="ghost btn-icon cancel-edit">${icon.x} Cancel</button>
      </div>
    </div>
  ` : "";

  return `
    <article class="word-card" data-id="${item.id}">
      <header>
        <div>
          <div class="word-title">${escapeHtml(item.word)}${item.reading ? ` · ${escapeHtml(item.reading)}` : ""}</div>
          <div class="word-meta">${formatLanguage(item.language)} · ${escapeHtml(item.level)} · ${escapeHtml(item.part_of_speech)} · ${escapeHtml(item.source)}</div>
        </div>
        <span class="badge ${item.status === "draft" ? "warm" : ""}">${escapeHtml(item.status)}</span>
      </header>
      <p class="word-meta">${escapeHtml(item.meaning_zh)} · ${escapeHtml(item.meaning_en)}</p>
      <p class="word-example">${escapeHtml(item.example_sentence)}</p>
      <p class="word-meta">${escapeHtml(item.example_translation_zh)}</p>
      ${controls ? `
        <div class="card-actions">
          <button class="icon-btn status-toggle" data-id="${item.id}" data-status="${statusTarget}" data-tooltip="${statusTooltip}">${statusIcon}</button>
          <button class="icon-btn edit-toggle" data-id="${item.id}" data-tooltip="Edit">${icon.edit}</button>
          <button class="icon-btn danger delete-vocab" data-id="${item.id}" data-tooltip="Delete">${icon.trash}</button>
        </div>
      ` : ""}
      ${editForm}
    </article>
  `;
}

async function loadBootstrap() {
  state.bootstrap = await api("/api/bootstrap");
  $("#lesson-date").value = state.bootstrap.today;
  $("#filter-language").innerHTML = languageOptions(true);
  $('[name="language"]').innerHTML = languageOptions(false);
}

async function loadDashboard() {
  state.dashboard = await api("/api/dashboard");
  renderDashboard();
}

async function loadVocabulary() {
  const language = $("#filter-language").value;
  const status = $("#filter-status").value;
  const source = $("#filter-source").value;
  const q = $("#filter-search").value.trim();
  const query = new URLSearchParams();
  if (language) query.set("language", language);
  if (status) query.set("status", status);
  if (source) query.set("source", source);
  if (q) query.set("q", q);
  state.vocabulary = await api(`/api/vocabulary?${query}`);
  renderVocabulary();
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
            <div class="markdown-wrap">
              <button class="icon-btn copy-md" data-text="${escapeHtml(lesson.generated_message)}" data-tooltip="Copy Markdown">${svg('<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>')}</button>
              <pre class="markdown">${escapeHtml(lesson.generated_message)}</pre>
            </div>
          </article>
        `
        )
        .join("")
    : `<section class="panel lesson-empty">No lessons have been generated yet.</section>`;
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
      <div class="card-actions" style="margin-top:10px">
        <button class="ghost btn-icon danger language-delete" data-code="${escapeHtml(language.code)}" data-name="${escapeHtml(language.name)}">${icon.trash} Delete language</button>
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

  $("#filter-search").addEventListener("input", loadVocabulary);
  $("#filter-language").addEventListener("change", loadVocabulary);
  $("#filter-status").addEventListener("change", loadVocabulary);
  $("#filter-source").addEventListener("change", loadVocabulary);
  $("#show-ai-drafts").addEventListener("click", () => {
    $("#filter-status").value = "draft";
    $("#filter-source").value = "ai";
    loadVocabulary();
  });
  $("#reload-vocab").addEventListener("click", loadVocabulary);

  $("#show-add-word").addEventListener("click", () => {
    const panel = $("#add-word-panel");
    panel.classList.toggle("hidden");
    const isOpen = !panel.classList.contains("hidden");
    const btn = $("#show-add-word");
    btn.innerHTML = isOpen ? `${icon.x} Close` : `${icon.plus} Add Word`;
  });

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
    const statusBtn = event.target.closest(".status-toggle");
    if (statusBtn) {
      try {
        await api(`/api/vocabulary/${statusBtn.dataset.id}`, {
          method: "PATCH",
          body: JSON.stringify({ status: statusBtn.dataset.status }),
        });
        await refreshAll();
        notice("Vocabulary status updated.");
      } catch (error) {
        notice(error.message, "error");
      }
      return;
    }

    const editBtn = event.target.closest(".edit-toggle");
    if (editBtn) {
      const panel = document.querySelector(`.edit-panel[data-id="${editBtn.dataset.id}"]`);
      if (panel) panel.classList.toggle("hidden");
      return;
    }

    const cancelBtn = event.target.closest(".cancel-edit");
    if (cancelBtn) {
      cancelBtn.closest(".edit-panel").classList.add("hidden");
      return;
    }

    const saveBtn = event.target.closest(".save-vocab-edit");
    if (saveBtn) {
      const panel = saveBtn.closest(".edit-panel");
      const payload = {};
      panel.querySelectorAll("[name]").forEach((input) => {
        payload[input.name] = input.value;
      });
      try {
        await api(`/api/vocabulary/${saveBtn.dataset.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        await refreshAll();
        notice("Vocabulary updated.");
      } catch (error) {
        notice(error.message, "error");
      }
      return;
    }

    const deleteBtn = event.target.closest(".delete-vocab");
    if (deleteBtn) {
      if (!confirm("Delete this vocabulary item? This cannot be undone.")) return;
      try {
        await api(`/api/vocabulary/${deleteBtn.dataset.id}`, { method: "DELETE" });
        await refreshAll();
        notice("Vocabulary item deleted.");
      } catch (error) {
        notice(error.message, "error");
      }
      return;
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
    const saveBtn = event.target.closest(".language-save");
    if (saveBtn) {
      const row = event.target.closest(".language-row");
      const payload = {};
      row.querySelectorAll("[data-field]").forEach((input) => {
        payload[input.dataset.field] = input.type === "checkbox" ? input.checked : input.value;
      });
      try {
        await api(`/api/languages/${saveBtn.dataset.code}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        await loadBootstrap();
        await refreshAll();
        notice("Language updated.");
      } catch (error) {
        notice(error.message, "error");
      }
      return;
    }

    const deleteBtn = event.target.closest(".language-delete");
    if (deleteBtn) {
      const { code, name } = deleteBtn.dataset;
      if (!confirm(`Delete "${name}"? This will also delete all vocabulary for this language. This cannot be undone.`)) return;
      try {
        await api(`/api/languages/${code}`, { method: "DELETE" });
        await loadBootstrap();
        await refreshAll();
        notice(`Language "${name}" deleted.`);
      } catch (error) {
        notice(error.message, "error");
      }
      return;
    }
  });

  $("#lesson-list").addEventListener("click", async (event) => {
    const copyBtn = event.target.closest(".copy-md");
    if (!copyBtn) return;
    try {
      await navigator.clipboard.writeText(copyBtn.dataset.text);
      const prev = copyBtn.innerHTML;
      copyBtn.innerHTML = svg('<polyline points="20 6 9 17 4 12"/>');
      copyBtn.dataset.tooltip = "Copied!";
      setTimeout(() => {
        copyBtn.innerHTML = prev;
        copyBtn.dataset.tooltip = "Copy Markdown";
      }, 1500);
    } catch {
      notice("Clipboard access denied.", "error");
    }
  });
}

async function boot() {
  bindEvents();
  await loadBootstrap();
  await refreshAll();
}

boot().catch((error) => notice(error.message, "error"));
