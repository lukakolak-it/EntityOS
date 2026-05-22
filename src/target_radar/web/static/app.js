const state = {
  selectedTargetId: null,
  selectedUseCaseSlug: null,
  useCaseTab: "basis",
  queue: [],
  useCases: [],
};

const USE_CASE_TABS = (
  ["basis", "fields", "queries", "sources", "rating", "output", "review"]
);

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
  importConflict: document.querySelector("#importConflict"),
  importUseCaseJson: document.querySelector("#importUseCaseJson"),
  importUseCaseStatus: document.querySelector("#importUseCaseStatus"),
  importUseCaseButton: document.querySelector("#importUseCaseButton"),
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
elements.importUseCaseButton.addEventListener("click", importUseCaseFromTextarea);

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
        <button type="button" data-use-case-export="${escapeAttribute(useCase.slug)}">Export</button>
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
    item.querySelector("[data-use-case-export]").addEventListener("click", async () => {
      const data = await api(`/api/use-cases/${useCase.slug}/export`);
      elements.importUseCaseJson.value = jsonText(data);
      elements.importUseCaseStatus.textContent = `Export ready: ${useCase.slug}`;
    });
    elements.useCaseList.appendChild(item);
  }

  renderUseCaseDetail(selected);
}

function renderUseCaseDetail(useCase) {
  elements.useCaseDetail.classList.remove("hidden");
  const selectedTab = USE_CASE_TABS.includes(state.useCaseTab) ? state.useCaseTab : "basis";
  elements.useCaseDetail.innerHTML = `
    <div class="tabbar">
      ${USE_CASE_TABS.map((tab) => `
        <button type="button" class="${tab === selectedTab ? "active-tab" : ""}" data-use-case-tab="${tab}">
          ${escapeHtml(tabLabel(tab))}
        </button>
      `).join("")}
    </div>
    <form id="useCaseEditor" class="editor-form">
      ${renderUseCaseTab(useCase, selectedTab)}
      <div id="useCaseEditorStatus" class="editor-status"></div>
      <div id="useCasePreview" class="item preview-item"></div>
      <div class="actions">
        <button type="button" class="primary" id="saveUseCaseButton">Save Use Case</button>
        <button type="button" id="resetUseCaseButton">Reset</button>
      </div>
    </form>
  `;

  elements.useCaseDetail.querySelectorAll("[data-use-case-tab]").forEach((button) => {
    button.addEventListener("click", () => {
      state.useCaseTab = button.dataset.useCaseTab;
      renderUseCaseDetail(useCase);
    });
  });
  elements.useCaseDetail.querySelector("#saveUseCaseButton").addEventListener("click", async () => {
    await saveUseCaseFromEditor(useCase);
  });
  elements.useCaseDetail.querySelector("#resetUseCaseButton").addEventListener("click", () => {
    renderUseCaseDetail(useCase);
  });
  elements.useCaseDetail.querySelector("#useCaseEditor").addEventListener("input", () => {
    updateUseCasePreview(useCase);
  });
  updateUseCasePreview(useCase);
}

function renderUseCaseTab(useCase, tab) {
  if (tab === "basis") return renderBasisTab(useCase);
  if (tab === "fields") return renderFieldsTab(useCase);
  if (tab === "queries") return renderQueriesTab(useCase);
  if (tab === "sources") return renderSourcesTab(useCase);
  if (tab === "rating") return renderRatingTab(useCase);
  if (tab === "output") return renderOutputTab(useCase);
  return renderReviewTab(useCase);
}

function renderBasisTab(useCase) {
  return `
    <div class="form-grid">
      <div>
        <label>Slug</label>
        <input id="uc-slug" value="${escapeAttribute(useCase.slug)}" disabled>
      </div>
      <div>
        <label>Name</label>
        <input id="uc-name" value="${escapeAttribute(useCase.name)}">
      </div>
      <div>
        <label>Status</label>
        <select id="uc-status">
          ${selectOptions(["template", "active", "inactive", "archived"], useCase.status)}
        </select>
      </div>
      <div>
        <label>Version</label>
        <input id="uc-version" type="number" min="1" value="${escapeAttribute(useCase.version)}">
      </div>
    </div>
    <label>Description</label>
    <textarea id="uc-description" class="short-textarea">${escapeHtml(useCase.description || "")}</textarea>
  `;
}

function renderFieldsTab(useCase) {
  return `
    <label>Attribute Schema Fields</label>
    <textarea id="uc-fields-json" class="code-input">${escapeHtml(jsonText(useCase.attribute_schema.fields))}</textarea>
  `;
}

function renderQueriesTab(useCase) {
  return `
    <div class="form-grid">
      <div>
        <label>Template Set</label>
        <input id="uc-query-template-set" value="${escapeAttribute(useCase.query_policy.default_template_set)}">
      </div>
      <div>
        <label>Request Budget</label>
        <input id="uc-query-budget" type="number" min="1" value="${escapeAttribute(useCase.query_policy.request_budget_default)}">
      </div>
      <div>
        <label>Results Per Query</label>
        <input id="uc-query-results" type="number" min="1" value="${escapeAttribute(useCase.query_policy.results_per_query_default)}">
      </div>
    </div>
    <label>Templates</label>
    <textarea id="uc-query-templates" class="code-input">${escapeHtml(useCase.query_policy.templates.join("\n"))}</textarea>
    <label>Variable Map</label>
    <textarea id="uc-variable-map" class="code-input">${escapeHtml(jsonText(useCase.query_policy.variable_map))}</textarea>
  `;
}

function renderSourcesTab(useCase) {
  return `
    <div class="form-grid">
      <div>
        <label>Import Threshold</label>
        <input id="uc-source-import-threshold" type="number" min="0" max="100" value="${escapeAttribute(useCase.source_policy.import_threshold)}">
      </div>
      <div>
        <label>Review Threshold</label>
        <input id="uc-source-review-threshold" type="number" min="0" max="100" value="${escapeAttribute(useCase.source_policy.review_threshold)}">
      </div>
    </div>
    <label>Preferred Source Types</label>
    <input id="uc-source-preferred" value="${escapeAttribute(useCase.source_policy.preferred_source_types.join(", "))}">
    <label>Context Source Types</label>
    <input id="uc-source-context" value="${escapeAttribute(useCase.source_policy.context_source_types.join(", "))}">
    <label>Blocked Source Types</label>
    <input id="uc-source-blocked" value="${escapeAttribute(useCase.source_policy.blocked_source_types.join(", "))}">
    <label>Blocked Domains</label>
    <input id="uc-source-blocked-domains" value="${escapeAttribute(useCase.source_policy.blocked_domains.join(", "))}">
    <label>Preferred Domains</label>
    <input id="uc-source-preferred-domains" value="${escapeAttribute(useCase.source_policy.preferred_domains.join(", "))}">
    <label>Relevant Path Tokens</label>
    <input id="uc-source-relevant-paths" value="${escapeAttribute(useCase.source_policy.relevant_path_tokens.join(", "))}">
    <label>Listing Path Tokens</label>
    <input id="uc-source-listing-paths" value="${escapeAttribute(useCase.source_policy.listing_path_tokens.join(", "))}">
  `;
}

function renderRatingTab(useCase) {
  return `
    <div class="form-grid">
      <div>
        <label>LLM Mode</label>
        <select id="uc-rating-llm-mode">
          ${selectOptions(["off", "light", "heavy"], useCase.rating_policy.llm_mode)}
        </select>
      </div>
      <div>
        <label>Review Score</label>
        <input id="uc-rating-review-score" type="number" min="0" max="100" value="${escapeAttribute(useCase.rating_policy.min_score_for_review)}">
      </div>
      <div>
        <label>Draft Score</label>
        <input id="uc-rating-draft-score" type="number" min="0" max="100" value="${escapeAttribute(useCase.rating_policy.min_score_for_draft)}">
      </div>
    </div>
    <label>Criteria</label>
    <textarea id="uc-rating-criteria" class="code-input">${escapeHtml(jsonText(useCase.rating_policy.criteria))}</textarea>
  `;
}

function renderOutputTab(useCase) {
  return `
    <div class="form-grid">
      <div>
        <label>Draft Type</label>
        <select id="uc-draft-type">
          ${selectOptions(["application_email", "research_summary", "none"], useCase.draft_policy.draft_type)}
        </select>
      </div>
      <div>
        <label>Language</label>
        <input id="uc-draft-language" value="${escapeAttribute(useCase.draft_policy.language)}">
      </div>
      <div>
        <label>Max Length</label>
        <input id="uc-draft-max-length" type="number" min="1" value="${escapeAttribute(useCase.draft_policy.max_length_chars)}">
      </div>
      <div>
        <label>Include Sources</label>
        <select id="uc-draft-include-sources">
          ${selectOptions(["true", "false"], String(Boolean(useCase.draft_policy.include_sources)))}
        </select>
      </div>
    </div>
    <label>Required Sections</label>
    <input id="uc-draft-required-sections" value="${escapeAttribute(useCase.draft_policy.required_sections.join(", "))}">
    <label>Forbidden Claims</label>
    <input id="uc-draft-forbidden-claims" value="${escapeAttribute(useCase.draft_policy.forbidden_claims.join(", "))}">
  `;
}

function renderReviewTab(useCase) {
  return `
    <div class="form-grid">
      <div>
        <label>Default Scope</label>
        <select id="uc-review-scope">
          ${selectOptions(["all", "use_case"], useCase.review_policy.default_scope)}
        </select>
      </div>
    </div>
    <label>Actions</label>
    <input id="uc-review-actions" value="${escapeAttribute(useCase.review_policy.actions.join(", "))}">
    <label>Columns</label>
    <input id="uc-review-columns" value="${escapeAttribute(useCase.review_policy.columns.join(", "))}">
  `;
}

async function saveUseCaseFromEditor(useCase) {
  const status = elements.useCaseDetail.querySelector("#useCaseEditorStatus");
  try {
    const config = buildUseCaseConfigFromEditor(useCase);
    const data = await api(`/api/use-cases/${useCase.slug}`, {
      method: "PATCH",
      body: { config },
    });
    state.selectedUseCaseSlug = data.use_case.slug;
    status.textContent = "Saved";
    await loadUseCases();
    await loadSearchProfiles();
    await loadQueue();
  } catch (error) {
    status.textContent = error.message;
  }
}

async function importUseCaseFromTextarea() {
  try {
    const payload = JSON.parse(elements.importUseCaseJson.value);
    const data = await api("/api/use-cases/import", {
      method: "POST",
      body: {
        conflict: elements.importConflict.value,
        ...payload,
      },
    });
    state.selectedUseCaseSlug = data.use_case.slug;
    elements.importUseCaseStatus.textContent = `Imported: ${data.import_status}`;
    elements.importUseCaseJson.value = "";
    await refreshAll();
  } catch (error) {
    elements.importUseCaseStatus.textContent = error.message;
  }
}

function updateUseCasePreview(useCase) {
  const preview = elements.useCaseDetail.querySelector("#useCasePreview");
  const status = elements.useCaseDetail.querySelector("#useCaseEditorStatus");
  if (!preview) return;
  try {
    const config = buildUseCaseConfigFromEditor(useCase);
    status.textContent = "";
    preview.innerHTML = `
      <div class="split">
        <section>
          <h3>Query Preview</h3>
          ${renderList(queryPreview(config))}
        </section>
        <section>
          <h3>Source Policy Preview</h3>
          ${renderList(sourcePolicyPreview(config))}
        </section>
      </div>
    `;
  } catch (error) {
    preview.innerHTML = `<p class="muted">${escapeHtml(error.message)}</p>`;
  }
}

function buildUseCaseConfigFromEditor(useCase) {
  const config = editableUseCaseConfig(useCase);
  const get = (id) => elements.useCaseDetail.querySelector(`#${id}`);

  if (get("uc-name")) {
    config.name = get("uc-name").value.trim();
    config.description = get("uc-description").value.trim();
    config.status = get("uc-status").value;
    config.version = numberValue(get("uc-version").value);
  }
  if (get("uc-fields-json")) {
    config.attribute_schema.fields = parseJsonField("uc-fields-json", "Attribute Schema Fields");
  }
  if (get("uc-query-templates")) {
    config.query_policy.default_template_set = get("uc-query-template-set").value.trim();
    config.query_policy.request_budget_default = numberValue(get("uc-query-budget").value);
    config.query_policy.results_per_query_default = numberValue(get("uc-query-results").value);
    config.query_policy.templates = parseLines(get("uc-query-templates").value);
    config.query_policy.variable_map = parseJsonObject("uc-variable-map", "Variable Map");
  }
  if (get("uc-source-preferred")) {
    config.source_policy.import_threshold = numberValue(get("uc-source-import-threshold").value);
    config.source_policy.review_threshold = numberValue(get("uc-source-review-threshold").value);
    config.source_policy.preferred_source_types = parseCsv(get("uc-source-preferred").value);
    config.source_policy.context_source_types = parseCsv(get("uc-source-context").value);
    config.source_policy.blocked_source_types = parseCsv(get("uc-source-blocked").value);
    config.source_policy.blocked_domains = parseCsv(get("uc-source-blocked-domains").value);
    config.source_policy.preferred_domains = parseCsv(get("uc-source-preferred-domains").value);
    config.source_policy.relevant_path_tokens = parseCsv(get("uc-source-relevant-paths").value);
    config.source_policy.listing_path_tokens = parseCsv(get("uc-source-listing-paths").value);
  }
  if (get("uc-rating-criteria")) {
    config.rating_policy.llm_mode = get("uc-rating-llm-mode").value;
    config.rating_policy.min_score_for_review = numberValue(get("uc-rating-review-score").value);
    config.rating_policy.min_score_for_draft = numberValue(get("uc-rating-draft-score").value);
    config.rating_policy.criteria = parseJsonField("uc-rating-criteria", "Criteria");
  }
  if (get("uc-draft-type")) {
    config.draft_policy.draft_type = get("uc-draft-type").value;
    config.draft_policy.language = get("uc-draft-language").value.trim();
    config.draft_policy.max_length_chars = numberValue(get("uc-draft-max-length").value);
    config.draft_policy.include_sources = get("uc-draft-include-sources").value === "true";
    config.draft_policy.required_sections = parseCsv(get("uc-draft-required-sections").value);
    config.draft_policy.forbidden_claims = parseCsv(get("uc-draft-forbidden-claims").value);
  }
  if (get("uc-review-actions")) {
    config.review_policy.default_scope = get("uc-review-scope").value;
    config.review_policy.actions = parseCsv(get("uc-review-actions").value);
    config.review_policy.columns = parseCsv(get("uc-review-columns").value);
  }
  return config;
}

function editableUseCaseConfig(useCase) {
  const config = JSON.parse(JSON.stringify(useCase));
  delete config.db_id;
  delete config.slug;
  return config;
}

function parseJsonField(id, label) {
  const value = elements.useCaseDetail.querySelector(`#${id}`).value;
  const parsed = JSON.parse(value);
  if (!Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON array`);
  }
  return parsed;
}

function parseJsonObject(id, label) {
  const value = elements.useCaseDetail.querySelector(`#${id}`).value;
  const parsed = JSON.parse(value);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON object`);
  }
  return parsed;
}

function parseLines(value) {
  return value.split("\n").map((item) => item.trim()).filter(Boolean);
}

function parseCsv(value) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function numberValue(value) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) {
    throw new Error("number field is invalid");
  }
  return parsed;
}

function queryPreview(config) {
  return config.query_policy.templates.slice(0, 6).map((template) => {
    let rendered = template;
    for (const variable of templateVariables(template)) {
      const fieldKey = config.query_policy.variable_map[variable] || variable;
      rendered = rendered.replaceAll(`{${variable}}`, sampleValue(fieldKey));
    }
    return rendered;
  });
}

function sourcePolicyPreview(config) {
  return [
    `import >= ${config.source_policy.import_threshold}`,
    `review >= ${config.source_policy.review_threshold}`,
    `preferred: ${config.source_policy.preferred_source_types.join(", ") || "-"}`,
    `context: ${config.source_policy.context_source_types.join(", ") || "-"}`,
    `blocked: ${config.source_policy.blocked_source_types.join(", ") || "-"}`,
  ];
}

function templateVariables(template) {
  const variables = new Set();
  for (const match of template.matchAll(/\{([a-z][a-z0-9_]*)\}/g)) {
    variables.add(match[1]);
  }
  return Array.from(variables);
}

function sampleValue(fieldKey) {
  const samples = {
    roles: "Werkstudent IT",
    role: "Werkstudent IT",
    tech_keywords: "Python",
    tech: "Python",
    regions: "Essen",
    region: "Essen",
    industry_keywords: "IT",
    industries: "IT",
    industry: "IT",
    topics: "Solar Services",
    topic: "Solar Services",
  };
  return samples[fieldKey] || fieldKey;
}

function tabLabel(tab) {
  return {
    basis: "Basis",
    fields: "Felder",
    queries: "Queries",
    sources: "Quellen",
    rating: "Rating",
    output: "Output",
    review: "Review",
  }[tab] || tab;
}

function selectOptions(values, selected) {
  return values.map((value) => (
    `<option value="${escapeAttribute(value)}" ${String(value) === String(selected) ? "selected" : ""}>${escapeHtml(value)}</option>`
  )).join("");
}

function jsonText(value) {
  return JSON.stringify(value, null, 2);
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
