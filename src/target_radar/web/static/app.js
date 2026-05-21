const state = {
  selectedTargetId: null,
  queue: [],
};

const elements = {
  serverStatus: document.querySelector("#serverStatus"),
  queueBody: document.querySelector("#queueBody"),
  queueCount: document.querySelector("#queueCount"),
  detailEmpty: document.querySelector("#detailEmpty"),
  detailContent: document.querySelector("#detailContent"),
  detailStatus: document.querySelector("#detailStatus"),
  targetDomain: document.querySelector("#targetDomain"),
  targetSource: document.querySelector("#targetSource"),
  targetUpdated: document.querySelector("#targetUpdated"),
  ratingsList: document.querySelector("#ratingsList"),
  draftsList: document.querySelector("#draftsList"),
  evidenceList: document.querySelector("#evidenceList"),
  statusLogList: document.querySelector("#statusLogList"),
  runsList: document.querySelector("#runsList"),
};

document.querySelector("#refreshButton").addEventListener("click", refreshAll);
document.querySelector("#runFakeButton").addEventListener("click", async () => {
  await api("/api/pipeline-runs/fake", { method: "POST", body: {} });
  await refreshAll();
});

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
  elements.serverStatus.textContent = `${health.host} · ${health.status}`;
  await Promise.all([loadQueue(), loadRuns()]);
}

async function loadQueue() {
  const data = await api("/api/review-queue?limit=50");
  state.queue = data.items;
  elements.queueCount.textContent = String(data.items.length);
  elements.queueBody.innerHTML = "";

  for (const item of data.items) {
    const row = document.createElement("tr");
    row.className = item.id === state.selectedTargetId ? "selected" : "";
    row.innerHTML = `
      <td>${escapeHtml(item.domain)}</td>
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
      <p>${escapeHtml(run.mode)} · ${escapeHtml(formatDate(run.created_at))}</p>
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

  elements.detailEmpty.classList.add("hidden");
  elements.detailContent.classList.remove("hidden");
  elements.detailStatus.outerHTML = pill(target.status, "detailStatus");
  elements.detailStatus = document.querySelector("#detailStatus");
  elements.targetDomain.textContent = target.domain;
  elements.targetDomain.href = target.base_url;
  elements.targetSource.textContent = target.source;
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
      <p>Rule ${displayNumber(rating.rule_score)} · AI ${displayNumber(rating.ai_score)} · Confidence ${formatConfidence(rating.confidence)}</p>
      <p>${escapeHtml(JSON.stringify(rating.risks || []))}</p>
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
        <span class="item-title">Draft #${draft.id}</span>
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
