const THEME_KEY = "infra-auditor-theme";
const SIDEBAR_KEY = "infra-auditor-sidebar";

document.addEventListener("DOMContentLoaded", () => {
  initializeThemeToggle();
  initializeSidebarToggle();
  initializeAsyncContent();
  initializeSyncForms();
  initializeSubmitLoader();
});

document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) {
    return;
  }

  const copyButton = target.closest("[data-copy-target]");
  if (!(copyButton instanceof HTMLElement)) {
    return;
  }

  const targetId = copyButton.dataset.copyTarget;
  if (!targetId) {
    return;
  }

  const source = document.getElementById(targetId);
  if (!source || !navigator.clipboard) {
    return;
  }

  navigator.clipboard.writeText(source.textContent || "");
});

function initializeThemeToggle() {
  const toggle = document.querySelector("[data-theme-toggle]");
  if (!(toggle instanceof HTMLButtonElement)) {
    return;
  }

  applyTheme(readStoredValue(THEME_KEY) || "light");
  toggle.addEventListener("click", () => {
    const currentTheme = document.documentElement.dataset.bsTheme || "light";
    const nextTheme = currentTheme === "dark" ? "light" : "dark";
    applyTheme(nextTheme);
    writeStoredValue(THEME_KEY, nextTheme);
  });
}

function applyTheme(theme) {
  document.documentElement.dataset.bsTheme = theme;
  const icon = document.querySelector("[data-theme-toggle] i");
  if (!(icon instanceof HTMLElement)) {
    return;
  }

  icon.className = theme === "dark" ? "bi bi-sun" : "bi bi-moon-stars";
}

function initializeSidebarToggle() {
  const toggle = document.querySelector("[data-sidebar-toggle]");
  if (!(toggle instanceof HTMLButtonElement)) {
    return;
  }

  applySidebarState(readStoredValue(SIDEBAR_KEY) || "expanded");
  toggle.addEventListener("click", () => {
    const isCollapsed = document.documentElement.classList.toggle("sidebar-collapsed");
    const nextState = isCollapsed ? "collapsed" : "expanded";
    writeStoredValue(SIDEBAR_KEY, nextState);
    applySidebarState(nextState);
  });
}

function applySidebarState(state) {
  const collapsed = state === "collapsed";
  document.documentElement.classList.toggle("sidebar-collapsed", collapsed);
  const toggle = document.querySelector("[data-sidebar-toggle]");
  if (!(toggle instanceof HTMLButtonElement)) {
    return;
  }

  const icon = toggle.querySelector("i");
  if (icon instanceof HTMLElement) {
    icon.className = collapsed ? "bi bi-chevron-right" : "bi bi-chevron-left";
  }
  toggle.setAttribute("aria-label", collapsed ? "Expand sidebar" : "Collapse sidebar");
}

function initializeAsyncContent() {
  const root = document.getElementById("content-root");
  if (!root) {
    return;
  }

  const url = root.dataset.contentUrl;
  if (!url) {
    return;
  }

  fetch(url, {headers: {"X-Infra-Auditor-View": "1"}})
    .then((response) => {
      if (!response.ok) {
        throw new Error(`View request failed with HTTP ${response.status}`);
      }
      return response.text();
    })
    .then((html) => {
      root.innerHTML = html;
    })
    .catch((error) => {
      root.innerHTML = `
        <div class="alert alert-danger py-2">
          Failed to load audit data: ${escapeHtml(error.message)}
        </div>
      `;
    });
}

function initializeSubmitLoader() {
  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (form instanceof HTMLFormElement && form.dataset.syncForm !== undefined) {
      return;
    }

    const root = document.getElementById("content-root");
    if (!root) {
      return;
    }

    root.innerHTML = `
      <div class="loader-panel" role="status" aria-live="polite">
        <div class="spinner-border text-primary" aria-hidden="true"></div>
        <div class="loader-title">Running audit workflow</div>
        <div class="loader-copy">Waiting for the collector and S3 snapshot update.</div>
      </div>
    `;
  });
}

function initializeSyncForms() {
  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.dataset.syncForm === undefined) {
      return;
    }

    event.preventDefault();
    renderSyncPanel({status: "queued", message: "starting sync job", results: []});

    fetch(form.action, {method: "POST", headers: {"Accept": "application/json"}})
      .then((response) => response.json().then((body) => ({ok: response.ok, body})))
      .then(({ok, body}) => {
        if (!ok) {
          throw new Error(body.error || "Failed to start sync job");
        }
        renderSyncPanel(body.job);
        pollSyncJob(body.status_url, body.refresh_url);
      })
      .catch((error) => {
        renderSyncError(error.message);
      });
  });
}

function pollSyncJob(statusUrl, refreshUrl) {
  window.setTimeout(() => {
    fetch(statusUrl, {headers: {"Accept": "application/json"}})
      .then((response) => response.json().then((body) => ({ok: response.ok, body})))
      .then(({ok, body}) => {
        if (!ok) {
          throw new Error(body.error || "Failed to read sync job");
        }
        renderSyncPanel(body);
        if (["queued", "running"].includes(body.status)) {
          pollSyncJob(statusUrl, refreshUrl);
          return;
        }
        window.setTimeout(() => {
          window.location.href = refreshUrl;
        }, 1200);
      })
      .catch((error) => {
        renderSyncError(error.message);
      });
  }, 1500);
}

function renderSyncPanel(job) {
  const root = document.getElementById("content-root");
  if (!root) {
    return;
  }

  const results = Array.isArray(job.results) ? job.results : [];
  const active = ["queued", "running"].includes(job.status);
  const currentAlias = job.current_alias ? `Current: ${escapeHtml(job.current_alias)}` : "";
  const resultRows = results.map((result) => renderSyncResult(result)).join("");
  root.innerHTML = `
    <div class="sync-job-panel" role="status" aria-live="polite">
      <div class="sync-job-header">
        ${active ? '<div class="spinner-border text-primary" aria-hidden="true"></div>' : ""}
        <div>
          <div class="sync-job-title">${escapeHtml(syncTitle(job.status))}</div>
          <div class="sync-job-note">
            ${escapeHtml(job.message || "")}
            ${currentAlias ? `<span class="ms-2">${currentAlias}</span>` : ""}
          </div>
        </div>
      </div>
      <ul class="sync-job-list">
        ${resultRows || '<li class="sync-job-item"><span class="sync-job-note">Waiting for first target...</span><span class="badge text-bg-secondary">queued</span></li>'}
      </ul>
    </div>
  `;
}

function renderSyncResult(result) {
  const badgeClass = syncBadgeClass(result.action);
  const message = result.error || result.message || "";
  const status = result.status ? ` · ${escapeHtml(result.status)}` : "";
  const findingCount = result.finding_count === null || result.finding_count === undefined
    ? ""
    : ` · ${escapeHtml(String(result.finding_count))} findings`;
  return `
    <li class="sync-job-item">
      <div>
        <div class="sync-job-alias">${escapeHtml(result.instance_alias || "unknown")}${status}${findingCount}</div>
        ${message ? `<div class="${result.error ? "sync-job-error" : "sync-job-note"}">${escapeHtml(message)}</div>` : ""}
      </div>
      <span class="badge ${badgeClass}">${escapeHtml(result.action || "queued")}</span>
    </li>
  `;
}

function renderSyncError(message) {
  const root = document.getElementById("content-root");
  if (!root) {
    return;
  }
  root.innerHTML = `
    <div class="alert alert-danger py-2">
      Sync failed: ${escapeHtml(message)}
    </div>
  `;
}

function syncTitle(status) {
  if (status === "success") {
    return "Sync complete";
  }
  if (status === "partial_success") {
    return "Sync completed with errors";
  }
  if (status === "failed") {
    return "Sync failed";
  }
  return "Sync in progress";
}

function syncBadgeClass(action) {
  if (action === "collected") {
    return "text-bg-success";
  }
  if (action === "skipped") {
    return "text-bg-secondary";
  }
  if (action === "failed") {
    return "text-bg-danger";
  }
  return "text-bg-secondary";
}

function readStoredValue(key) {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStoredValue(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    return;
  }
}

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}
