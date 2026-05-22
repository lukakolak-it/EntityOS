const state = {
  selectedTargetId: null,
  selectedUseCaseSlug: null,
  queue: [],
  useCases: [],
};

const elements = {
  serverStatus: document.querySelector("#serverStatus"),
  queueBody: document.querySelector("#queueBody"),
  queueCount: document.querySelector("#queueCount"),
  queueUseCaseFilter: document.querySelector("#queueUseCaseFilter"),
  runUseCaseSelect: document.querySelector("#runUseCaseSelect"),
  detailEmpty: document.querySelector("#detailEmpty"),
  detailContent: document.querySelector("#detailContent"),
  detailStatus: document.querySelector("#detailStatus"),
  targetDomain: document.querySelector("#targetDomain"),
  targetSource: document.querySelector("#targetSource"),
  targetUseCase: document.querySelector("#targetUseCase"),
  targetUpdated: document.querySelector("#targetUpdated"),
  ratingsList: document.querySelector("#ratingsList"),
  draftsList: document.querySelector("#draftsList"),
  evidenceList: document.querySelector("#evidenceList"),
  statusLogList: document.querySelector("#statusLogList"),
  runsList: document.querySelector("#runsList"),
  useCaseCount: document.querySelector("#useCaseCount"),
  useCaseList: document.querySelector("#useCaseList"),
  useCaseDetail: document.querySelector("#useCaseDetail"),
  searchProfilesList: document.querySelector("#searchProfilesList"),
};

document.querySelector("#refreshButton").addEventListener("click", refreshAll);
document.querySelector("#runFakeButton").addEventListener("click", async () => {
  const useCaseId = selectedNumber(elements.runUseCaseSelect.value);
  await api("/api/pipeline-runs/fake", {
    method: "POST",
    body: fakeRunPayload(useCaseId),
  });
  await refreshAll();
});

elements.queueUseCaseFilter.addEventListener("change", loadQueue);

document.querySelectorAll("[data-action]").forEach((button) => {
  button.addEventListener("click", async () => {
    if (!state.selectedTargetId) return;
    const action = button.dataset.action;
    await api(`/api/targets/${state.selectedTargetId}/${action}`, { method: "POST" });
    await refreshAll();
    await loadTarget(state.selectedTargetId);
  });
});

refreshAll();

async function refreshAll() {
  const health = await api("/api/health");
  elements.serverStatus.textContent = `${health.host} - ${health.status}`;
  await loadUseCases();
  await Promise.all([loadQueue(), loadRuns(), loadSearchProfiles()]);
}

async function loadUseCases() {
  const data = await api("/api/use-cases");
  state.useCases = data.use_cases;
  elements.useCaseCount.textContent = String(state.useCases.length);
  renderUseCaseOptions();
  renderUseCases();
}

function renderUseCaseOptions() {
  const queueValue = elements.queueUseCaseFilter.value;
  elements.queueUseCaseFilter.innerHTML = `<option value="">Alle Use Cases</option>`;
  for (const useCase of state.useCases) {
    elements.queueUseCaseFilter.appendChild(useCaseOption(useCase));
  }
  elements.queueUseCaseFilter.value = optionExists(elements.queueUseCaseFilter, queueValue)
    ? queueValue
    : "";

  const runValue = elements.runUseCaseSelect.value;
  elements.runUseCaseSelect.innerHTML = "";
  for (const useCase of state.useCases) {
    elements.runUseCaseSelect.appendChild(useCaseOption(useCase));
  }
  const defaultUseCase = state.useCases.find((item) => item.slug === "application_student");
  elements.runUseCaseSelect.value = optionExists(elements.runUseCaseSelect, runValue)
    ? runValue
    : String(defaultUseCase?.db_id || state.useCases[0]?.db_id || "");
}

function useCaseOption(useCase) {
  const option = document.createElement("option");
  option.value = String(useCase.db_id);
  option.textContent = useCase.name;
  return option;
}

function optionExists(select, value) {
  return Array.from(select.options).some((option) => option.value === value);
}

function renderUseCases() {
  elements.useCaseList.innerHTML = "";
  if (state.useCases.length === 0) {
    elements.useCaseList.appendChild(emptyItem("Keine Use Cases."));
    elements.useCaseDetail.classList.add("hidden");
    return;
  }

  if (!state.selectedUseCaseSlug) {
    state.selectedUseCaseSlug = state.useCases[0].slug;
  }
  const selected = state.useCases.find((item) => item.slug === state.selectedUseCaseSlug)
    || state.useCases[0];
  state.selectedUseCaseSlug = selected.slug;

  for (const useCase of state.useCases) {
    const item = document.createElement("article");
    item.className = `item selectable ${useCase.slug === selected.slug ? "selected-card" : ""}`;
    item.innerHTML = `
      <div class="item-header">
        <span class="item-title">${escapeHtml(useCase.name)}</span>
        ${pill(useCase.status)}
      </div>
      <p>${escapeHtml(useCase.slug)} - v${displayNumber(useCase.version)}</p>
      <p>${escapeHtml(useCase.draft_policy.draft_type)} - ${useCase.rating_policy.criteria.length} Kriterien</p>
      <div class="actions">
        <button type="button" data-use-case-detail="${escapeAttribute(useCase.slug)}">Details</button>
        <button type="button" data-use-case-clone="${escapeAttribute(useCase.slug)}">Clone</button>
      </div>
    `;
    item.querySelector("[data-use-case-detail]").addEventListener("click", () => {
      state.selectedUseCaseSlug = useCase.slug;
      renderUseCases();
    });
    item.querySelector("[data-use-case-clone]").addEventListener("click", async () => {
      const data = await api(`/api/use-cases/${useCase.slug}/clone`, { method: "POST", body: {} });
      state.selectedUseCaseSlug = data.use_case.slug;
      await refreshAll();
    });
    elements.useCaseList.appendChild(item);
  }

  renderUseCaseDetail(selected);
}

function renderUseCaseDetail(useCase) {
  elements.useCaseDetail.classList.remove("hidden");
  elements.useCaseDetail.innerHTML = `
    <div class="detail-grid compact">
      <div>
        <label>Name</label>
        <strong>${escapeHtml(useCase.name)}</strong>
      </div>
      <div>
        <label>Draft</label>
        <span>${escapeHtml(useCase.draft_policy.draft_type)}</span>
      </div>
      <div>
        <label>LLM</label>
        <span>${escapeHtml(useCase.rating_policy.llm_mode)}</span>
      </div>
    </div>
    <div class="split">
      <section>
        <h3>Felder</h3>
        ${renderList(useCase.attribute_schema.fields.map((field) => `${field.key}: ${field.type}`))}
      </section>
      <section>
        <h3>Rating</h3>
        ${renderList(useCase.rating_policy.criteria.map((criterion) => (
          `${criterion.key} ${criterion.weight}% ${criterion.evaluation}`
        )))}
      </section>
    </div>
    <div class="split">
      <section>
        <h3>Queries</h3>
        ${renderList(useCase.query_policy.templates)}
      </section>
      <section>
        <h3>Quellen</h3>
        ${renderList([
          `preferred: ${useCase.source_policy.preferred_source_types.join(", ") || "-"}`,
          `context: ${useCase.source_policy.context_source_types.join(", ") || "-"}`,
          `blocked: ${useCase.source_policy.blocked_source_types.join(", ") || "-"}`,
        ])}
      </section>
    </div>
  `;
}

async function loadSearchProfiles() {
  const data = await api("/api/search-profiles?limit=50");
  elements.searchProfilesList.innerHTML = "";
  if (data.search_profiles.length === 0) {
    elements.searchProfilesList.appendChild(emptyItem("Keine Search Profiles."));
    return;
  }
  for (const profile of data.search_profiles) {
    const item = document.createElement("article");
    item.className = "item";
    item.innerHTML = `
      <div class="item-header">
        <span class="item-title">${escapeHtml(profile.name)}</span>
        ${pill(profile.use_case_slug || "none")}
      </div>
      <p>${escapeHtml(profile.profile_name)} - ${escapeHtml(formatSearchTerms(profile))}</p>
      <label>Use Case</label>
      <select data-profile-use-case="${profile.id}">
        ${state.useCases.map((useCase) => `
          <option value="${useCase.db_id}" ${useCase.db_id === profile.use_case_id ? "selected" : ""}>
            ${escapeHtml(useCase.name)}
          </option>
        `).join("")}
      </select>
      <div class="actions">
        <button type="button" data-save-profile="${profile.id}">Save</button>
      </div>
    `;
    item.querySelector("[data-save-profile]").addEventListener("click", async () => {
      const select = item.querySelector(`[data-profile-use-case="${profile.id}"]`);
      await api(`/api/search-profiles/${profile.id}`, {
        method: "PATCH",
        body: { use_case_id: selectedNumber(select.value) },
      });
      await refreshAll();
    });
    elements.searchProfilesList.appendChild(item);
  }
}

async function loadQueue() {
  const selectedUseCaseId = selectedNumber(elements.queueUseCaseFilter.value);
  const query = selectedUseCaseId ? `?limit=50&use_case_id=${selectedUseCaseId}` : "?limit=50";
  const data = await api(`/api/review-queue${query}`);
  state.queue = data.items;
  elements.queueCount.textContent = String(data.items.length);
  elements.queueBody.innerHTML = "";

  for (const item of data.items) {
    const row = document.createElement("tr");
    row.className = item.id === state.selectedTargetId ? "selected" : "";
    row.innerHTML = `
      <td>${escapeHtml(item.domain)}</td>
      <td>${pill(item.use_case_slug || "none")}</td>
      <td>${pill(item.status)}</td>
      <td>${pill(item.recommended_action || "none")}</td>
      <td>${displayScore(item.ai_score, item.rule_score)}</td>
      <td>${formatConfidence(item.confidence)}</td>
    `;
    row.addEventListener("click", () => loadTarget(item.id));
    elements.queueBody.appendChild(row);
  }
}

async function loadRuns() {
  const data = await api("/api/pipeline-runs?limit=10");
  elements.runsList.innerHTML = "";
  if (data.runs.length === 0) {
    elements.runsList.appendChild(emptyItem("Keine Runs."));
    return;
  }
  for (const run of data.runs) {
    const item = document.createElement("article");
    item.className = "item";
    item.innerHTML = `
      <div class="item-header">
        <span class="item-title">Run #${run.id}</span>
        ${pill(run.status)}
      </div>
      <p>${escapeHtml(run.use_case_name || "no use case")} - ${escapeHtml(formatDate(run.created_at))}</p>
      <p>${escapeHtml(JSON.stringify(run.stats || {}))}</p>
    `;
    elements.runsList.appendChild(item);
  }
}

async function loadTarget(targetId) {
  state.selectedTargetId = targetId;
  await loadQueue();
  const data = await api(`/api/targets/${targetId}`);
  const target = data.target;
  const queueItem = state.queue.find((item) => item.id === targetId);

  elements.detailEmpty.classList.add("hidden");
  elements.detailContent.classList.remove("hidden");
  elements.detailStatus.outerHTML = pill(target.status, "detailStatus");
  elements.detailStatus = document.querySelector("#detailStatus");
  elements.targetDomain.textContent = target.domain;
  elements.targetDomain.href = target.base_url;
  elements.targetSource.textContent = target.source;
  elements.targetUseCase.textContent = queueItem?.use_case_name || queueItem?.use_case_slug || "-";
  elements.targetUpdated.textContent = formatDate(target.updated_at);

  renderRatings(data.ratings);
  renderDrafts(data.drafts);
  renderEvidence(data.evidence);
  renderStatusLogs(data.status_logs);
}

function renderRatings(ratings) {
  elements.ratingsList.innerHTML = "";
  if (ratings.length === 0) {
    elements.ratingsList.appendChild(emptyItem("Keine Ratings."));
    return;
  }
  for (const rating of ratings) {
    const item = document.createElement("article");
    item.className = "item";
    item.innerHTML = `
      <div class="item-header">
        <span class="item-title">${escapeHtml(rating.rating_version)}</span>
        ${pill(rating.recommended_action)}
      </div>
      <p>Rule ${displayNumber(rating.rule_score)} - AI ${displayNumber(rating.ai_score)} - Confidence ${formatConfidence(rating.confidence)}</p>
      ${rating.error_message ? `<p class="muted">${escapeHtml(rating.error_type || "rating_error")}: ${escapeHtml(rating.error_message)}</p>` : ""}
      ${renderFacts("Reasons", rating.reasons || [])}
      ${renderFacts("Risks", rating.risks || [])}
    `;
    elements.ratingsList.appendChild(item);
  }
}

function renderDrafts(drafts) {
  elements.draftsList.innerHTML = "";
  if (drafts.length === 0) {
    elements.draftsList.appendChild(emptyItem("Keine Drafts."));
    return;
  }
  for (const draft of drafts) {
    const item = document.createElement("article");
    item.className = "item";
    item.innerHTML = `
      <div class="item-header">
        <span class="item-title">Draft #${draft.id} - ${escapeHtml(draft.draft_type)}</span>
        ${pill(draft.status)}
      </div>
      <label>Subject</label>
      <input value="${escapeAttribute(draft.subject)}" data-draft-subject="${draft.id}">
      <label>Body</label>
      <textarea data-draft-body="${draft.id}">${escapeHtml(draft.body)}</textarea>
      <div class="actions">
        <button type="button" data-save-draft="${draft.id}">Save</button>
      </div>
    `;
    item.querySelector("[data-save-draft]").addEventListener("click", async () => {
      const id = draft.id;
      await api(`/api/drafts/${id}`, {
        method: "PATCH",
        body: {
          subject: item.querySelector(`[data-draft-subject="${id}"]`).value,
          body: item.querySelector(`[data-draft-body="${id}"]`).value,
        },
      });
      await loadTarget(state.selectedTargetId);
    });
    elements.draftsList.appendChild(item);
  }
}

function renderEvidence(evidence) {
  elements.evidenceList.innerHTML = "";
  if (evidence.length === 0) {
    elements.evidenceList.appendChild(emptyItem("Keine Evidence."));
    return;
  }
  for (const entry of evidence) {
    const item = document.createElement("article");
    item.className = "item";
    item.innerHTML = `
      <div class="item-header">
        <span class="item-title">${escapeHtml(entry.context_type)}</span>
        <a href="${escapeAttribute(entry.source_url)}" target="_blank" rel="noreferrer">open</a>
      </div>
      <p>${escapeHtml(entry.text)}</p>
    `;
    elements.evidenceList.appendChild(item);
  }
}

function renderStatusLogs(logs) {
  elements.statusLogList.innerHTML = "";
  if (logs.length === 0) {
    elements.statusLogList.appendChild(emptyItem("Kein Status Log."));
    return;
  }
  for (const log of logs) {
    const item = document.createElement("article");
    item.className = "item";
    item.innerHTML = `
      <div class="item-header">
        <span class="item-title">${escapeHtml(log.phase)}</span>
        ${pill(log.to_status)}
      </div>
      <p>${escapeHtml(log.from_status || "none")} -> ${escapeHtml(log.to_status)}</p>
      <p>${escapeHtml(log.reason || "")}</p>
    `;
    elements.statusLogList.appendChild(item);
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    method: options.method || "GET",
    headers: options.body ? { "Content-Type": "application/json" } : {},
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || response.statusText);
  }
  return data;
}

function fakeRunPayload(useCaseId) {
  const useCase = state.useCases.find((item) => item.db_id === useCaseId);
  if (useCase?.slug === "company_osint") {
    return {
      use_case_id: useCaseId,
      search_name: "Local OSINT Search",
      attributes: {
        topics: ["Solar Services"],
        industries: ["IT"],
        regions: ["Essen"],
      },
      roles: [],
      regions: ["Essen"],
      tech_keywords: [],
    };
  }
  return { use_case_id: useCaseId };
}

function pill(value, id) {
  const clean = value || "none";
  const idPart = id ? ` id="${id}"` : "";
  return `<span${idPart} class="status-pill ${className(clean)}">${escapeHtml(clean)}</span>`;
}

function emptyItem(text) {
  const item = document.createElement("div");
  item.className = "empty";
  item.textContent = text;
  return item;
}

function renderFacts(label, facts) {
  if (!facts.length) return "";
  const items = facts.slice(0, 4).map((fact) => {
    const text = fact.text || fact.value || fact.evidence || JSON.stringify(fact);
    return `<li>${escapeHtml(String(text))}</li>`;
  }).join("");
  return `<div class="fact-list"><span>${escapeHtml(label)}</span><ul>${items}</ul></div>`;
}

function renderList(items) {
  if (!items.length) return `<div class="empty inline">-</div>`;
  return `<ul class="plain-list">${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function formatSearchTerms(profile) {
  const terms = [
    ...(profile.roles || []),
    ...(profile.tech_keywords || []),
    ...(profile.regions || []),
    ...Object.values(profile.attributes || {}).flat(),
  ].filter(Boolean);
  return terms.length ? terms.join(", ") : "-";
}

function selectedNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

function displayScore(aiScore, ruleScore) {
  if (aiScore !== null && aiScore !== undefined) return String(aiScore);
  return displayNumber(ruleScore);
}

function displayNumber(value) {
  return value === null || value === undefined ? "-" : String(value);
}

function formatConfidence(value) {
  if (value === null || value === undefined) return "-";
  return `${Math.round(value * 100)}%`;
}

function formatDate(value) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function escapeAttribute(value) {
  return escapeHtml(value);
}

function className(value) {
  return String(value ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "_");
}
