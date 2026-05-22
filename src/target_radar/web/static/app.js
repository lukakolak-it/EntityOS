const state = {
  selectedTargetId: null,
  selectedUseCaseSlug: null,
  useCaseTab: "basis",
  queue: [],
  useCases: [],
  searchProfiles: [],
  providerStatus: null,
  localSettings: null,
  domainPolicies: null,
  selectedSearchProfileId: null,
  previewTimer: null,
  defaultsApplied: false,
};

const USE_CASE_TABS = (
  ["basis", "fields", "queries", "sources", "rating", "output", "review"]
);
const PAGE_IDS = new Set(["review", "use-cases", "profiles", "runs", "secrets"]);
const RUN_DEFAULTS_KEY = "target-radar-run-defaults-v1";

const elements = {
  serverStatus: document.querySelector("#serverStatus"),
  navLinks: Array.from(document.querySelectorAll("[data-nav-page]")),
  pages: Array.from(document.querySelectorAll("[data-page]")),
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
  targetSourceQuality: document.querySelector("#targetSourceQuality"),
  ratingsList: document.querySelector("#ratingsList"),
  draftsList: document.querySelector("#draftsList"),
  evidenceList: document.querySelector("#evidenceList"),
  pagesList: document.querySelector("#pagesList"),
  statusLogList: document.querySelector("#statusLogList"),
  runsList: document.querySelector("#runsList"),
  providerStatusList: document.querySelector("#providerStatusList"),
  secretsProviderStatusList: document.querySelector("#secretsProviderStatusList"),
  runSearchProfileSelect: document.querySelector("#runSearchProfileSelect"),
  runProviderMode: document.querySelector("#runProviderMode"),
  runLlmMode: document.querySelector("#runLlmMode"),
  runLightModelSelect: document.querySelector("#runLightModelSelect"),
  runFetchMode: document.querySelector("#runFetchMode"),
  runPhaseMode: document.querySelector("#runPhaseMode"),
  runDraftEnabled: document.querySelector("#runDraftEnabled"),
  runRequestBudget: document.querySelector("#runRequestBudget"),
  runResultsPerQuery: document.querySelector("#runResultsPerQuery"),
  runMaxPages: document.querySelector("#runMaxPages"),
  runAttributeFields: document.querySelector("#runAttributeFields"),
  runPreview: document.querySelector("#runPreview"),
  runConfiguredButton: document.querySelector("#runConfiguredButton"),
  saveRunDefaultsButton: document.querySelector("#saveRunDefaultsButton"),
  runStatus: document.querySelector("#runStatus"),
  useCaseCount: document.querySelector("#useCaseCount"),
  useCaseList: document.querySelector("#useCaseList"),
  useCaseDetail: document.querySelector("#useCaseDetail"),
  importConflict: document.querySelector("#importConflict"),
  importUseCaseFile: document.querySelector("#importUseCaseFile"),
  importUseCaseJson: document.querySelector("#importUseCaseJson"),
  importUseCaseStatus: document.querySelector("#importUseCaseStatus"),
  importUseCaseButton: document.querySelector("#importUseCaseButton"),
  searchProfilesList: document.querySelector("#searchProfilesList"),
  newSearchProfileButton: document.querySelector("#newSearchProfileButton"),
  profileEditorMode: document.querySelector("#profileEditorMode"),
  profileProfileName: document.querySelector("#profileProfileName"),
  profileSearchName: document.querySelector("#profileSearchName"),
  profileUseCaseSelect: document.querySelector("#profileUseCaseSelect"),
  profileRoles: document.querySelector("#profileRoles"),
  profileRegions: document.querySelector("#profileRegions"),
  profileTechKeywords: document.querySelector("#profileTechKeywords"),
  profileIndustryKeywords: document.querySelector("#profileIndustryKeywords"),
  profileExcludeKeywords: document.querySelector("#profileExcludeKeywords"),
  profileDraftLanguage: document.querySelector("#profileDraftLanguage"),
  profileAttributesJson: document.querySelector("#profileAttributesJson"),
  profileEditorStatus: document.querySelector("#profileEditorStatus"),
  saveSearchProfileButton: document.querySelector("#saveSearchProfileButton"),
  deleteSearchProfileButton: document.querySelector("#deleteSearchProfileButton"),
  domainPolicyInput: document.querySelector("#domainPolicyInput"),
  addBlacklistDomainButton: document.querySelector("#addBlacklistDomainButton"),
  domainPolicyStatus: document.querySelector("#domainPolicyStatus"),
  domainPolicyList: document.querySelector("#domainPolicyList"),
  localSettingsEnvFile: document.querySelector("#localSettingsEnvFile"),
  localSettingsCount: document.querySelector("#localSettingsCount"),
  localSettingsGroups: document.querySelector("#localSettingsGroups"),
  localSettingsStatus: document.querySelector("#localSettingsStatus"),
  saveLocalSettingsButton: document.querySelector("#saveLocalSettingsButton"),
};

document.querySelector("#refreshButton").addEventListener("click", refreshAll);
elements.runConfiguredButton.addEventListener("click", runFromForm);
elements.saveRunDefaultsButton.addEventListener("click", saveRunDefaults);
elements.runUseCaseSelect.addEventListener("change", () => {
  renderRunAttributeFields();
  scheduleRunPreview();
});
elements.runSearchProfileSelect.addEventListener("change", () => {
  applySelectedRunProfile();
  scheduleRunPreview();
});
[
  elements.runProviderMode,
  elements.runLlmMode,
  elements.runLightModelSelect,
  elements.runFetchMode,
  elements.runPhaseMode,
  elements.runDraftEnabled,
  elements.runRequestBudget,
  elements.runResultsPerQuery,
  elements.runMaxPages,
].forEach((element) => element.addEventListener("input", scheduleRunPreview));

elements.queueUseCaseFilter.addEventListener("change", loadQueue);
elements.importUseCaseFile.addEventListener("change", importUseCaseFromFile);
elements.importUseCaseButton.addEventListener("click", importUseCaseFromTextarea);
elements.newSearchProfileButton.addEventListener("click", () => renderSearchProfileEditor(null));
elements.saveSearchProfileButton.addEventListener("click", saveSearchProfileFromEditor);
elements.deleteSearchProfileButton.addEventListener("click", deleteSelectedSearchProfile);
elements.addBlacklistDomainButton.addEventListener("click", addBlacklistDomain);
elements.saveLocalSettingsButton.addEventListener("click", saveLocalSettings);
window.addEventListener("hashchange", renderPage);

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
renderPage();

async function refreshAll() {
  const health = await api("/api/health");
  elements.serverStatus.textContent = `${health.host} - ${health.status}`;
  await loadUseCases();
  await Promise.all([
    loadProviderStatus(),
    loadLocalSettings(),
    loadDomainPolicies(),
    loadQueue(),
    loadRuns(),
    loadSearchProfiles(),
  ]);
  if (!state.defaultsApplied) {
    applyRunDefaults();
    state.defaultsApplied = true;
  }
  renderRunAttributeFields();
  scheduleRunPreview();
  renderPage();
}

function renderPage() {
  const page = currentPage();
  elements.pages.forEach((section) => {
    section.classList.toggle("active-page", section.dataset.page === page);
  });
  elements.navLinks.forEach((link) => {
    link.classList.toggle("active-nav", link.dataset.navPage === page);
  });
}

function currentPage() {
  const raw = window.location.hash.replace("#", "");
  return PAGE_IDS.has(raw) ? raw : "review";
}

function showPage(page) {
  if (!PAGE_IDS.has(page)) return;
  if (window.location.hash !== `#${page}`) {
    window.location.hash = page;
  } else {
    renderPage();
  }
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

  const profileUseCaseValue = elements.profileUseCaseSelect.value;
  elements.profileUseCaseSelect.innerHTML = "";
  for (const useCase of state.useCases) {
    elements.profileUseCaseSelect.appendChild(useCaseOption(useCase));
  }
  elements.profileUseCaseSelect.value = optionExists(elements.profileUseCaseSelect, profileUseCaseValue)
    ? profileUseCaseValue
    : elements.runUseCaseSelect.value;
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
      downloadJson(`${useCase.slug}.target-radar-use-case.json`, data);
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
  const addFieldButton = elements.useCaseDetail.querySelector("#addAttributeFieldButton");
  if (addFieldButton) {
    addFieldButton.addEventListener("click", () => {
      elements.useCaseDetail.querySelector("#uc-field-rows").insertAdjacentHTML(
        "beforeend",
        renderAttributeFieldRow({ type: "text" })
      );
      wireRemoveRowButtons();
      updateUseCasePreview(useCase);
    });
  }
  const addCriterionButton = elements.useCaseDetail.querySelector("#addCriterionButton");
  if (addCriterionButton) {
    addCriterionButton.addEventListener("click", () => {
      elements.useCaseDetail.querySelector("#uc-criterion-rows").insertAdjacentHTML(
        "beforeend",
        renderCriterionRow({ evaluation: "rules", weight: 10 })
      );
      wireRemoveRowButtons();
      updateUseCasePreview(useCase);
    });
  }
  wireRemoveRowButtons();
  elements.useCaseDetail.querySelector("#useCaseEditor").addEventListener("input", () => {
    updateUseCasePreview(useCase);
  });
  updateUseCasePreview(useCase);
}

function wireRemoveRowButtons() {
  elements.useCaseDetail.querySelectorAll("[data-remove-row]").forEach((button) => {
    button.onclick = () => {
      button.closest("[data-uc-field-row], [data-uc-criterion-row]")?.remove();
      const selected = state.useCases.find((item) => item.slug === state.selectedUseCaseSlug);
      if (selected) updateUseCasePreview(selected);
    };
  });
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
    <div id="uc-field-rows" class="editor-form">
      ${useCase.attribute_schema.fields.map(renderAttributeFieldRow).join("")}
    </div>
    <div class="actions">
      <button type="button" id="addAttributeFieldButton">Add Field</button>
    </div>
  `;
}

function renderAttributeFieldRow(field = {}) {
  return `
    <div class="field-row" data-uc-field-row>
      <div>
        <label>Key</label>
        <input data-field-key value="${escapeAttribute(field.key || "")}">
      </div>
      <div>
        <label>Label</label>
        <input data-field-label value="${escapeAttribute(field.label || "")}">
      </div>
      <div>
        <label>Type</label>
        <select data-field-type>
          ${selectOptions(["text", "list", "number", "boolean", "select"], field.type || "text")}
        </select>
      </div>
      <div>
        <label>Required</label>
        <select data-field-required>
          ${selectOptions(["false", "true"], String(Boolean(field.required)))}
        </select>
      </div>
      <div>
        <label>Options</label>
        <input data-field-options value="${escapeAttribute((field.options || []).join(", "))}">
      </div>
      <button type="button" data-remove-row>Remove</button>
    </div>
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
    <div id="uc-criterion-rows" class="editor-form">
      ${useCase.rating_policy.criteria.map(renderCriterionRow).join("")}
    </div>
    <div class="actions">
      <button type="button" id="addCriterionButton">Add Criterion</button>
    </div>
  `;
}

function renderCriterionRow(criterion = {}) {
  return `
    <div class="criterion-row" data-uc-criterion-row>
      <div>
        <label>Key</label>
        <input data-criterion-key value="${escapeAttribute(criterion.key || "")}">
      </div>
      <div>
        <label>Label</label>
        <input data-criterion-label value="${escapeAttribute(criterion.label || "")}">
      </div>
      <div>
        <label>Weight</label>
        <input data-criterion-weight type="number" min="1" max="100" value="${escapeAttribute(criterion.weight || 10)}">
      </div>
      <div>
        <label>Eval</label>
        <select data-criterion-evaluation>
          ${selectOptions(["rules", "llm", "hybrid"], criterion.evaluation || "rules")}
        </select>
      </div>
      <div>
        <label>Rule Set</label>
        <input data-criterion-rule-set value="${escapeAttribute(criterion.rule_set || "")}">
      </div>
      <div>
        <label>LLM Instruction</label>
        <input data-criterion-llm value="${escapeAttribute(criterion.llm_instruction || "")}">
      </div>
      <button type="button" data-remove-row>Remove</button>
    </div>
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
    await importUseCasePayload(payload);
  } catch (error) {
    elements.importUseCaseStatus.textContent = error.message;
  }
}

async function importUseCaseFromFile() {
  const file = elements.importUseCaseFile.files?.[0];
  if (!file) return;
  try {
    const text = await file.text();
    elements.importUseCaseJson.value = text;
    await importUseCasePayload(JSON.parse(text));
    elements.importUseCaseFile.value = "";
  } catch (error) {
    elements.importUseCaseStatus.textContent = error.message;
  }
}

async function importUseCasePayload(payload) {
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
  if (elements.useCaseDetail.querySelector("[data-uc-field-row]")) {
    config.attribute_schema.fields = Array.from(
      elements.useCaseDetail.querySelectorAll("[data-uc-field-row]")
    ).map((row) => {
      const field = {
        key: row.querySelector("[data-field-key]").value.trim(),
        label: row.querySelector("[data-field-label]").value.trim(),
        type: row.querySelector("[data-field-type]").value,
        required: row.querySelector("[data-field-required]").value === "true",
      };
      const options = parseCsv(row.querySelector("[data-field-options]").value);
      if (options.length) field.options = options;
      return field;
    }).filter((field) => field.key || field.label);
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
  if (elements.useCaseDetail.querySelector("[data-uc-criterion-row]")) {
    config.rating_policy.llm_mode = get("uc-rating-llm-mode").value;
    config.rating_policy.min_score_for_review = numberValue(get("uc-rating-review-score").value);
    config.rating_policy.min_score_for_draft = numberValue(get("uc-rating-draft-score").value);
    config.rating_policy.criteria = Array.from(
      elements.useCaseDetail.querySelectorAll("[data-uc-criterion-row]")
    ).map((row) => {
      const criterion = {
        key: row.querySelector("[data-criterion-key]").value.trim(),
        label: row.querySelector("[data-criterion-label]").value.trim(),
        weight: numberValue(row.querySelector("[data-criterion-weight]").value),
        evaluation: row.querySelector("[data-criterion-evaluation]").value,
      };
      const ruleSet = row.querySelector("[data-criterion-rule-set]").value.trim();
      const llmInstruction = row.querySelector("[data-criterion-llm]").value.trim();
      if (ruleSet) criterion.rule_set = ruleSet;
      if (llmInstruction) criterion.llm_instruction = llmInstruction;
      return criterion;
    }).filter((criterion) => criterion.key || criterion.label);
    const weightSum = config.rating_policy.criteria.reduce((sum, item) => sum + Number(item.weight || 0), 0);
    if (weightSum !== 100) {
      throw new Error(`Criteria weights must sum to 100, currently ${weightSum}`);
    }
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
  return parseJsonObjectValue(value, label);
}

function parseJsonObjectValue(value, label) {
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
  const policy = config.source_policy || {};
  return [
    `import >= ${displayNumber(policy.import_threshold)}`,
    `review >= ${displayNumber(policy.review_threshold)}`,
    `preferred: ${(policy.preferred_source_types || []).join(", ") || "-"}`,
    `context: ${(policy.context_source_types || []).join(", ") || "-"}`,
    `blocked: ${(policy.blocked_source_types || []).join(", ") || "-"}`,
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

function setSelectValue(select, value) {
  if (value === undefined || value === null) return;
  if (optionExists(select, String(value))) {
    select.value = String(value);
  }
}

function jsonText(value) {
  return JSON.stringify(value, null, 2);
}

async function loadSearchProfiles() {
  const data = await api("/api/search-profiles?limit=50");
  state.searchProfiles = data.search_profiles;
  renderRunProfileOptions();
  elements.searchProfilesList.innerHTML = "";
  if (data.search_profiles.length === 0) {
    elements.searchProfilesList.appendChild(emptyItem("Keine Search Profiles."));
    renderSearchProfileEditor(null);
    return;
  }
  if (state.selectedSearchProfileId === null) {
    state.selectedSearchProfileId = data.search_profiles[0].id;
  }
  for (const profile of data.search_profiles) {
    const item = document.createElement("article");
    item.className = `item selectable ${profile.id === state.selectedSearchProfileId ? "selected-card" : ""}`;
    item.innerHTML = `
      <div class="item-header">
        <span class="item-title">${escapeHtml(profile.name)}</span>
        ${pill(profile.use_case_slug || "none")}
      </div>
      <p>${escapeHtml(profile.profile_name)} - ${escapeHtml(formatSearchTerms(profile))}</p>
      <div class="actions">
        <button type="button" data-edit-profile="${profile.id}">Edit</button>
        <button type="button" data-run-profile="${profile.id}">Use in Run</button>
      </div>
    `;
    item.querySelector("[data-edit-profile]").addEventListener("click", () => {
      state.selectedSearchProfileId = profile.id;
      renderSearchProfileEditor(profile);
      loadSearchProfiles();
    });
    item.querySelector("[data-run-profile]").addEventListener("click", () => {
      elements.runSearchProfileSelect.value = String(profile.id);
      applySelectedRunProfile();
      showPage("runs");
    });
    elements.searchProfilesList.appendChild(item);
  }
  const selected = state.searchProfiles.find((item) => item.id === state.selectedSearchProfileId) || null;
  renderSearchProfileEditor(selected);
}

function renderSearchProfileEditor(profile) {
  elements.profileEditorMode.textContent = profile ? `#${profile.id}` : "new";
  elements.deleteSearchProfileButton.disabled = !profile;
  elements.profileProfileName.value = profile?.profile_name || "Local Profile";
  elements.profileSearchName.value = profile?.name || "Local Search";
  elements.profileUseCaseSelect.value = String(profile?.use_case_id || elements.runUseCaseSelect.value || "");
  elements.profileRoles.value = (profile?.roles || []).join(", ");
  elements.profileRegions.value = (profile?.regions || []).join(", ");
  elements.profileTechKeywords.value = (profile?.tech_keywords || []).join(", ");
  elements.profileIndustryKeywords.value = (profile?.industry_keywords || []).join(", ");
  elements.profileExcludeKeywords.value = (profile?.exclude_keywords || []).join(", ");
  elements.profileDraftLanguage.value = profile?.draft_language || "de";
  elements.profileAttributesJson.value = jsonText(profile?.attributes || {});
  elements.profileEditorStatus.textContent = "";
}

async function saveSearchProfileFromEditor() {
  try {
    const payload = profilePayloadFromEditor();
    const selected = state.searchProfiles.find((item) => item.id === state.selectedSearchProfileId);
    const data = selected
      ? await api(`/api/search-profiles/${selected.id}`, { method: "PATCH", body: payload })
      : await api("/api/search-profiles", { method: "POST", body: payload });
    state.selectedSearchProfileId = data.search_profile.id;
    elements.profileEditorStatus.textContent = "Saved";
    await refreshAll();
  } catch (error) {
    elements.profileEditorStatus.textContent = error.message;
  }
}

async function deleteSelectedSearchProfile() {
  const selected = state.searchProfiles.find((item) => item.id === state.selectedSearchProfileId);
  if (!selected) return;
  try {
    await api(`/api/search-profiles/${selected.id}`, { method: "DELETE" });
    state.selectedSearchProfileId = null;
    await refreshAll();
  } catch (error) {
    elements.profileEditorStatus.textContent = error.message;
  }
}

function profilePayloadFromEditor() {
  return {
    profile_name: elements.profileProfileName.value.trim(),
    search_name: elements.profileSearchName.value.trim(),
    name: elements.profileSearchName.value.trim(),
    use_case_id: selectedNumber(elements.profileUseCaseSelect.value),
    roles: parseCsv(elements.profileRoles.value),
    regions: parseCsv(elements.profileRegions.value),
    tech_keywords: parseCsv(elements.profileTechKeywords.value),
    industry_keywords: parseCsv(elements.profileIndustryKeywords.value),
    exclude_keywords: parseCsv(elements.profileExcludeKeywords.value),
    draft_language: elements.profileDraftLanguage.value.trim() || "de",
    attributes: parseJsonObjectValue(elements.profileAttributesJson.value, "Profile Attributes"),
  };
}

async function loadProviderStatus() {
  const data = await api("/api/provider-status");
  state.providerStatus = data;
  renderLightModelOptions(data.llm.light.models || [], data.llm.light.model);
  renderProviderStatus(data);
}

async function loadLocalSettings() {
  const data = await api("/api/local-settings");
  state.localSettings = data;
  renderLocalSettings(data);
}

function renderLocalSettings(data) {
  const fields = data.groups.flatMap((group) => group.fields);
  elements.localSettingsEnvFile.textContent = data.env_file || "";
  elements.localSettingsCount.textContent = String(fields.length);
  elements.localSettingsGroups.innerHTML = "";

  for (const group of data.groups) {
    const section = document.createElement("section");
    section.className = "settings-group";
    const configuredCount = group.fields.filter((field) => (
      field.secret ? field.configured : field.value !== ""
    )).length;
    section.innerHTML = `
      <div class="settings-group-head">
        <h3>${escapeHtml(group.name)}</h3>
        <span class="count">${configuredCount}/${group.fields.length}</span>
      </div>
      <div class="settings-grid"></div>
    `;
    const grid = section.querySelector(".settings-grid");
    for (const field of group.fields) {
      const row = document.createElement("div");
      row.className = "settings-field";
      const status = field.secret
        ? (field.configured ? "configured" : "missing")
        : field.source;
      row.innerHTML = `
        <div class="settings-field-head">
          <label for="${settingInputId(field.key)}">${escapeHtml(field.label)}</label>
          ${pill(status)}
        </div>
        ${renderLocalSettingControl(field)}
        <span class="setting-key">${escapeHtml(field.key)}</span>
      `;
      grid.appendChild(row);
    }
    elements.localSettingsGroups.appendChild(section);
  }
}

function renderLocalSettingControl(field) {
  const id = settingInputId(field.key);
  const dataAttrs = `data-local-setting="${escapeAttribute(field.key)}" data-local-secret="${field.secret ? "true" : "false"}"`;
  if (field.options?.length) {
    const values = ["", ...field.options];
    if (field.value && !values.includes(field.value)) {
      values.push(field.value);
    }
    return `
      <select id="${id}" ${dataAttrs}>
        ${selectOptions(values, field.value)}
      </select>
    `;
  }
  if (field.secret) {
    return `
      <input id="${id}" ${dataAttrs} type="password" autocomplete="off" placeholder="${field.configured ? "configured" : ""}">
    `;
  }
  return `
    <input id="${id}" ${dataAttrs} value="${escapeAttribute(field.value || "")}">
  `;
}

async function saveLocalSettings() {
  elements.localSettingsStatus.textContent = "Saving...";
  elements.saveLocalSettingsButton.disabled = true;
  try {
    const values = {};
    elements.localSettingsGroups.querySelectorAll("[data-local-setting]").forEach((control) => {
      const key = control.dataset.localSetting;
      const value = control.value.trim();
      if (control.dataset.localSecret === "true" && !value) return;
      values[key] = value;
    });
    await api("/api/local-settings", { method: "POST", body: { values } });
    elements.localSettingsStatus.textContent = "Saved";
    await Promise.all([loadLocalSettings(), loadProviderStatus()]);
  } catch (error) {
    elements.localSettingsStatus.textContent = error.message;
  } finally {
    elements.saveLocalSettingsButton.disabled = false;
  }
}

function settingInputId(key) {
  return `setting-${className(key)}`;
}

function renderLightModelOptions(models, configuredModel) {
  const previous = elements.runLightModelSelect.value;
  const values = models.length ? models : [configuredModel].filter(Boolean);
  elements.runLightModelSelect.innerHTML = "";
  for (const model of values) {
    const option = document.createElement("option");
    option.value = model;
    option.textContent = model;
    elements.runLightModelSelect.appendChild(option);
  }
  elements.runLightModelSelect.value = optionExists(elements.runLightModelSelect, previous)
    ? previous
    : configuredModel || values[0] || "";
}

function renderRunProfileOptions() {
  const previous = elements.runSearchProfileSelect.value;
  elements.runSearchProfileSelect.innerHTML = `<option value="">Quick Run</option>`;
  for (const profile of state.searchProfiles) {
    const option = document.createElement("option");
    option.value = String(profile.id);
    option.textContent = `${profile.name} - ${profile.use_case_name || "no use case"}`;
    elements.runSearchProfileSelect.appendChild(option);
  }
  elements.runSearchProfileSelect.value = optionExists(elements.runSearchProfileSelect, previous)
    ? previous
    : "";
}

function renderProviderStatus(status) {
  renderProviderStatusCards(status, elements.providerStatusList);
  renderProviderStatusCards(status, elements.secretsProviderStatusList);
}

function renderProviderStatusCards(status, container) {
  if (!container) return;
  container.innerHTML = "";
  const cards = [
    {
      title: "Search",
      state: status.search.configured_ready ? "ready" : "missing",
      lines: [
        `configured: ${status.search.configured_provider}`,
        `brave: ${status.search.brave_ready ? "ready" : "missing key"}`,
        `mock: ${status.search.mock_ready ? "ready" : "missing"}`,
      ],
    },
    {
      title: "Light LLM",
      state: status.llm.light.configured ? "ready" : "missing",
      lines: [
        `${status.llm.light.provider} / ${status.llm.light.model}`,
        `reachable: ${status.llm.light.reachable === null ? "n/a" : String(status.llm.light.reachable)}`,
        `model available: ${status.llm.light.model_available === null ? "n/a" : String(status.llm.light.model_available)}`,
      ],
    },
    {
      title: "Heavy LLM",
      state: status.llm.heavy.enabled_in_ui ? "ready" : "optional",
      lines: [
        `${status.llm.heavy.provider} / ${status.llm.heavy.model}`,
        "in UI disabled",
      ],
    },
  ];
  for (const card of cards) {
    const item = document.createElement("article");
    item.className = "item provider-card";
    item.innerHTML = `
      <div class="item-header">
        <span class="item-title">${escapeHtml(card.title)}</span>
        ${pill(card.state)}
      </div>
      ${renderList(card.lines)}
    `;
    container.appendChild(item);
  }
}

async function runFromForm() {
  elements.runStatus.textContent = "Run startet...";
  elements.runConfiguredButton.disabled = true;
  try {
    const payload = runPayloadFromForm();
    const preview = await api("/api/run-preview", { method: "POST", body: payload });
    if (!preview.valid) {
      throw new Error(`Missing required fields: ${preview.missing_required.join(", ")}`);
    }
    const data = await api("/api/pipeline-runs", {
      method: "POST",
      body: payload,
    });
    elements.runStatus.textContent = data.error
      ? `Run #${data.run.id}: ${data.error}`
      : `Run #${data.run.id}: ${data.run.status}`;
    await refreshAll();
    showPage("review");
  } catch (error) {
    elements.runStatus.textContent = error.message;
  } finally {
    elements.runConfiguredButton.disabled = false;
  }
}

function runPayloadFromForm() {
  const useCaseId = selectedNumber(elements.runUseCaseSelect.value);
  const values = runAttributeValues();
  return {
    provider_mode: elements.runProviderMode.value,
    llm_mode: elements.runLlmMode.value,
    light_model: elements.runLightModelSelect.value,
    fetch_mode: elements.runFetchMode.value,
    phase_mode: elements.runPhaseMode.value,
    draft_enabled: elements.runDraftEnabled.value === "true",
    search_profile_id: selectedNumber(elements.runSearchProfileSelect.value),
    use_case_id: useCaseId,
    request_budget: numberValue(elements.runRequestBudget.value),
    results_per_query: numberValue(elements.runResultsPerQuery.value),
    max_pages_per_target: numberValue(elements.runMaxPages.value),
    roles: values.roles || [],
    regions: values.regions || [],
    tech_keywords: values.tech_keywords || [],
    industry_keywords: values.industry_keywords || [],
    exclude_keywords: values.exclude_keywords || [],
    attributes: values,
  };
}

function runAttributeValues() {
  const values = {};
  elements.runAttributeFields.querySelectorAll("[data-run-field]").forEach((input) => {
    const key = input.dataset.runField;
    const type = input.dataset.runFieldType;
    if (type === "boolean") {
      values[key] = input.checked;
    } else if (type === "number") {
      values[key] = input.value === "" ? null : numberValue(input.value);
    } else if (type === "list") {
      values[key] = parseCsv(input.value);
    } else {
      values[key] = input.value.trim();
    }
  });
  return values;
}

function renderRunAttributeFields() {
  const useCase = selectedRunUseCase();
  elements.runAttributeFields.innerHTML = "";
  if (!useCase) return;
  const profile = selectedRunProfile();
  const values = {
    ...(profile?.attributes || {}),
    roles: profile?.roles || ["Werkstudent IT"],
    regions: profile?.regions || ["Essen"],
    tech_keywords: profile?.tech_keywords || ["Python"],
    industry_keywords: profile?.industry_keywords || [],
    exclude_keywords: profile?.exclude_keywords || [],
  };
  for (const field of useCase.attribute_schema.fields) {
    const wrapper = document.createElement("div");
    const value = values[field.key] ?? field.default ?? "";
    wrapper.innerHTML = renderRunField(field, value);
    const input = wrapper.querySelector("[data-run-field]");
    input.addEventListener("input", scheduleRunPreview);
    input.addEventListener("change", scheduleRunPreview);
    elements.runAttributeFields.appendChild(wrapper);
  }
}

function renderRunField(field, value) {
  const required = field.required ? " *" : "";
  if (field.type === "boolean") {
    return `
      <label>${escapeHtml(field.label)}${required}</label>
      <input data-run-field="${escapeAttribute(field.key)}" data-run-field-type="boolean" type="checkbox" ${value ? "checked" : ""}>
    `;
  }
  if (field.type === "select") {
    return `
      <label>${escapeHtml(field.label)}${required}</label>
      <select data-run-field="${escapeAttribute(field.key)}" data-run-field-type="select">
        ${selectOptions(field.options || [], value)}
      </select>
    `;
  }
  const inputType = field.type === "number" ? "number" : "text";
  const displayValue = Array.isArray(value) ? value.join(", ") : value;
  return `
    <label>${escapeHtml(field.label)}${required}</label>
    <input data-run-field="${escapeAttribute(field.key)}" data-run-field-type="${escapeAttribute(field.type)}" type="${inputType}" value="${escapeAttribute(displayValue || "")}">
  `;
}

function selectedRunUseCase() {
  const useCaseId = selectedNumber(elements.runUseCaseSelect.value);
  return state.useCases.find((item) => item.db_id === useCaseId) || null;
}

function selectedRunProfile() {
  const profileId = selectedNumber(elements.runSearchProfileSelect.value);
  return state.searchProfiles.find((item) => item.id === profileId) || null;
}

function applySelectedRunProfile() {
  const profile = selectedRunProfile();
  if (profile?.use_case_id) {
    elements.runUseCaseSelect.value = String(profile.use_case_id);
  }
  renderRunAttributeFields();
}

function scheduleRunPreview() {
  window.clearTimeout(state.previewTimer);
  state.previewTimer = window.setTimeout(loadRunPreview, 150);
}

async function loadRunPreview() {
  try {
    const data = await api("/api/run-preview", {
      method: "POST",
      body: runPayloadFromForm(),
    });
    elements.runPreview.innerHTML = `
      <div class="split">
        <section>
          <h3>Query Preview</h3>
          ${renderList(data.queries.slice(0, 8).map((query) => query.text))}
        </section>
        <section>
          <h3>Source Policy</h3>
          ${renderList(sourcePolicyPreview({ source_policy: data.source_policy }))}
          ${data.missing_required.length ? `<p class="muted">Missing: ${escapeHtml(data.missing_required.join(", "))}</p>` : ""}
        </section>
      </div>
    `;
  } catch (error) {
    elements.runPreview.innerHTML = `<p class="muted">${escapeHtml(error.message)}</p>`;
  }
}

function saveRunDefaults() {
  localStorage.setItem(RUN_DEFAULTS_KEY, JSON.stringify({
    provider_mode: elements.runProviderMode.value,
    llm_mode: elements.runLlmMode.value,
    light_model: elements.runLightModelSelect.value,
    fetch_mode: elements.runFetchMode.value,
    phase_mode: elements.runPhaseMode.value,
    draft_enabled: elements.runDraftEnabled.value,
    request_budget: elements.runRequestBudget.value,
    results_per_query: elements.runResultsPerQuery.value,
    max_pages: elements.runMaxPages.value,
  }));
  elements.runStatus.textContent = "Defaults saved";
}

function applyRunDefaults() {
  const raw = localStorage.getItem(RUN_DEFAULTS_KEY);
  if (!raw) return;
  try {
    const defaults = JSON.parse(raw);
    setSelectValue(elements.runProviderMode, defaults.provider_mode);
    setSelectValue(elements.runLlmMode, defaults.llm_mode);
    setSelectValue(elements.runLightModelSelect, defaults.light_model);
    setSelectValue(elements.runFetchMode, defaults.fetch_mode);
    setSelectValue(elements.runPhaseMode, defaults.phase_mode);
    setSelectValue(elements.runDraftEnabled, defaults.draft_enabled);
    if (defaults.request_budget) elements.runRequestBudget.value = defaults.request_budget;
    if (defaults.results_per_query) elements.runResultsPerQuery.value = defaults.results_per_query;
    if (defaults.max_pages) elements.runMaxPages.value = defaults.max_pages;
  } catch {
    localStorage.removeItem(RUN_DEFAULTS_KEY);
  }
}

async function loadDomainPolicies() {
  const data = await api("/api/domain-policies");
  state.domainPolicies = data;
  renderDomainPolicies(data);
}

function renderDomainPolicies(data) {
  elements.domainPolicyList.innerHTML = "";
  const blacklisted = data.blacklisted || [];
  const suggestions = data.rejected_suggestions || [];
  if (!blacklisted.length && !suggestions.length) {
    elements.domainPolicyList.appendChild(emptyItem("Keine Domain Policies."));
    return;
  }
  for (const item of blacklisted) {
    const card = document.createElement("article");
    card.className = "item";
    card.innerHTML = `
      <div class="item-header">
        <span class="item-title">${escapeHtml(item.domain)}</span>
        ${pill("blacklisted")}
      </div>
      <p>${escapeHtml(item.base_url || "")}</p>
      <div class="actions">
        <button type="button" data-unblock-domain="${escapeAttribute(item.domain)}">Unblock</button>
      </div>
    `;
    card.querySelector("[data-unblock-domain]").addEventListener("click", async () => {
      await api("/api/domain-policies/unblock", {
        method: "POST",
        body: { domain: item.domain },
      });
      await refreshAll();
    });
    elements.domainPolicyList.appendChild(card);
  }
  for (const item of suggestions) {
    const card = document.createElement("article");
    card.className = "item";
    card.innerHTML = `
      <div class="item-header">
        <span class="item-title">${escapeHtml(item.domain)}</span>
        ${pill(`rejects:${item.reject_count}`)}
      </div>
      <p>${escapeHtml(item.base_url || "")}</p>
      <div class="actions">
        <button type="button" data-blacklist-suggestion="${escapeAttribute(item.domain)}">Blacklist</button>
      </div>
    `;
    card.querySelector("[data-blacklist-suggestion]").addEventListener("click", async () => {
      await api("/api/domain-policies/blacklist", {
        method: "POST",
        body: { domain: item.domain },
      });
      await refreshAll();
    });
    elements.domainPolicyList.appendChild(card);
  }
}

async function addBlacklistDomain() {
  try {
    const domain = elements.domainPolicyInput.value.trim();
    await api("/api/domain-policies/blacklist", {
      method: "POST",
      body: { domain },
    });
    elements.domainPolicyInput.value = "";
    elements.domainPolicyStatus.textContent = "Blacklisted";
    await refreshAll();
  } catch (error) {
    elements.domainPolicyStatus.textContent = error.message;
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
      <p>${escapeHtml(run.use_case_name || "no use case")} - ${escapeHtml(run.mode)} - ${escapeHtml(formatDate(run.created_at))}</p>
      ${renderMetricChips(run.stats || {})}
      ${run.error_message ? `<p class="muted">${escapeHtml(run.error_message)}</p>` : ""}
    `;
    elements.runsList.appendChild(item);
  }
}

async function loadTarget(targetId) {
  showPage("review");
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
  elements.targetSourceQuality.textContent = sourceQualitySummary(target.metadata);

  renderRatings(data.ratings);
  renderDrafts(data.drafts);
  renderEvidence(data.evidence);
  renderPages(data.pages);
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
      <p>Rule ${displayNumber(rating.rule_score)} - AI ${displayNumber(rating.ai_score)} - Confidence ${formatConfidence(rating.confidence)} - ${escapeHtml(rating.rating_status)}</p>
      ${rating.source_quality ? `<p>${escapeHtml(rating.source_quality)}</p>` : ""}
      ${rating.error_message ? `<p class="muted">${escapeHtml(rating.error_type || "rating_error")}: ${escapeHtml(rating.error_message)}</p>` : ""}
      ${renderCriterionBreakdown(rating.reasons || [])}
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
        ${pill(`p${entry.priority}`)}
        <a href="${escapeAttribute(entry.source_url)}" target="_blank" rel="noreferrer">open</a>
      </div>
      ${entry.metadata?.title ? `<p>${escapeHtml(entry.metadata.title)}</p>` : ""}
      <p>${escapeHtml(entry.text)}</p>
      ${entry.metadata?.emails?.length ? renderFacts("Emails", entry.metadata.emails.map((value) => ({ value }))) : ""}
    `;
    elements.evidenceList.appendChild(item);
  }
}

function renderPages(pages) {
  elements.pagesList.innerHTML = "";
  if (pages.length === 0) {
    elements.pagesList.appendChild(emptyItem("Keine Pages."));
    return;
  }
  for (const page of pages) {
    const item = document.createElement("article");
    item.className = "item";
    item.innerHTML = `
      <div class="item-header">
        <span class="item-title">${escapeHtml(page.title || page.url)}</span>
        ${pill(page.page_type)}
      </div>
      <p>${escapeHtml(page.url)}</p>
      <p>${escapeHtml(page.error_message || `${displayNumber(page.http_status)} - ${displayNumber(page.metadata?.bytes_read)} bytes`)}</p>
    `;
    elements.pagesList.appendChild(item);
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
      ${log.error_message ? `<p class="muted">${escapeHtml(log.error_message)}</p>` : ""}
      ${Object.keys(log.metadata || {}).length ? renderFacts("Metadata", objectFacts(log.metadata)) : ""}
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
    const text = fact.text || fact.value || fact.evidence || fact.weighted_score || JSON.stringify(fact);
    return `<li>${escapeHtml(String(text))}</li>`;
  }).join("");
  return `<div class="fact-list"><span>${escapeHtml(label)}</span><ul>${items}</ul></div>`;
}

function renderCriterionBreakdown(reasons) {
  const criteria = reasons.filter((reason) => reason.type === "criterion_score");
  if (!criteria.length) return "";
  const rows = criteria.map((item) => `
    <li>
      ${escapeHtml(item.criterion)}:
      ${displayNumber(item.score)} x ${displayNumber(item.weight)}%
      = ${displayNumber(item.weighted_score)}
    </li>
  `).join("");
  return `<div class="fact-list"><span>Criteria</span><ul>${rows}</ul></div>`;
}

function renderMetricChips(stats) {
  const keys = [
    "candidate_count",
    "imported_count",
    "existing_count",
    "fetched_count",
    "evidence_count",
    "rated_count",
    "drafted_count",
    "review_target_count",
    "error_count",
  ];
  const chips = keys
    .filter((key) => stats[key] !== undefined)
    .map((key) => `<span class="metric-chip">${escapeHtml(key.replaceAll("_", " "))}: ${escapeHtml(stats[key])}</span>`);
  const importCounts = stats.import_status_counts
    ? Object.entries(stats.import_status_counts).map(([key, value]) => `<span class="metric-chip">${escapeHtml(key)}: ${escapeHtml(value)}</span>`)
    : [];
  const sourceCounts = stats.source_type_counts
    ? Object.entries(stats.source_type_counts).map(([key, value]) => `<span class="metric-chip">${escapeHtml(key)}: ${escapeHtml(value)}</span>`)
    : [];
  return `<div class="metric-grid">${chips.concat(importCounts, sourceCounts).join("")}</div>`;
}

function objectFacts(value) {
  return Object.entries(value || {}).map(([key, item]) => ({
    value: `${key}: ${typeof item === "object" ? JSON.stringify(item) : item}`,
  }));
}

function sourceQualitySummary(metadata) {
  const sourceQuality = metadata?.lead_metadata?.source_quality;
  if (!sourceQuality) return "-";
  const parts = [
    sourceQuality.source_type,
    sourceQuality.source_quality_score,
    sourceQuality.source_quality_action,
  ].filter((item) => item !== undefined && item !== null && item !== "");
  return parts.length ? parts.join(" / ") : "-";
}

function renderList(items) {
  if (!items.length) return `<div class="empty inline">-</div>`;
  return `<ul class="plain-list">${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`;
}

function downloadJson(filename, value) {
  const blob = new Blob([jsonText(value)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
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
