const THEME_KEY = "infra-auditor-theme";
const SIDEBAR_KEY = "infra-auditor-sidebar";

document.addEventListener("DOMContentLoaded", () => {
  initializeThemeToggle();
  initializeSidebarToggle();
  initializeAsyncContent();
  initializeSyncForms();
  initializeFilterCascade();
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
      if (!syncActive) root.innerHTML = html;
    })
    .catch((error) => {
      if (syncActive) return;
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

    if (event.defaultPrevented) return;
    if (form instanceof HTMLFormElement && form.method === "get") {
      event.preventDefault();
      const url = new URL(form.action, window.location.href);
      url.search = new URLSearchParams(new FormData(form)).toString();
      window.location.assign(url.href);
    }
    const root = document.getElementById("content-root");
    if (!root) {
      return;
    }

    root.innerHTML = `
      <div class="loader-panel" role="status" aria-live="polite">
        <div class="spinner-border text-primary" aria-hidden="true"></div>
        <div class="loader-title">Loading selected audit data</div>
        <div class="loader-copy">Reading the selected snapshot.</div>
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
    if (syncActive) return;
    syncActive = true;
    document.querySelectorAll("[data-sync-form] button").forEach((button) => { button.disabled = true; });
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
          window.location.href = refreshUrl.replace(/^\/view\?/, "/?");
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
  syncActive = false;
  document.querySelectorAll("[data-sync-form] button").forEach((button) => { button.disabled = false; });
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

let syncActive = false;

function initializeFilterCascade() {
  let pending;
  document.addEventListener("change", async (event) => {
    const field = event.target;
    if (!(field instanceof HTMLSelectElement)) return;
    const form = field.closest("[data-filter-form]");
    if (!form || !["instance", "subservice", "date"].includes(field.name)) return;
    if (pending) pending.abort();
    const request = new AbortController();
    pending = request;
    const date = form.elements.namedItem("date");
    const timestamp = form.elements.namedItem("timestamp");
    const apply = form.querySelector('[type="submit"]');
    const status = form.querySelector("[data-filter-status]");
    if (!(date instanceof HTMLSelectElement) ||
        !(timestamp instanceof HTMLSelectElement) ||
        !(apply instanceof HTMLButtonElement) ||
        !(status instanceof HTMLElement)) return;

    const params = new URLSearchParams();
    for (const name of ["section", "instance", "subservice"]) {
      const control = form.elements.namedItem(name);
      if (!control || !("value" in control)) return;
      params.set(name, control.value);
    }
    const affected = field.name === "date" ? [timestamp] : [date, timestamp];
    if (field.name === "date") params.set("date", date.value);
    const database = form.elements.namedItem("database");
    if (database) database.replaceChildren(new Option("All databases", "all"));
    updateInstanceSyncUrl(form);
    const previous = new Map(affected.map((select) => [select, {
      options: [...select.options].map((option) => ({text: option.text, value: option.value})),
      value: select.value,
      disabled: select.disabled,
    }]));
    affected.forEach((select) => {
      select.replaceChildren(new Option("Loading…", ""));
      select.disabled = true;
      form.querySelector(`[data-filter-loader="${select.name}"]`).hidden = false;
    });
    apply.disabled = true;
    status.textContent = "Loading available snapshots…";
    try {
      const response = await fetch(`/api/filter-options?${params}`, {
        cache: "no-store",
        headers: {"Accept": "application/json"},
        signal: request.signal,
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "Could not load filter options");
      if (!Array.isArray(body.dates) || !Array.isArray(body.timestamps)) {
        throw new Error("Filter response has an invalid format");
      }
      if (request !== pending || !form.isConnected) return;
      for (const [select, values, selected] of [
        [date, body.dates, body.date], [timestamp, body.timestamps, body.timestamp],
      ]) {
        select.replaceChildren(...values.map((value) => new Option(value, value)));
        if (!values.length) select.add(new Option("No data available", ""));
        select.value = selected || "";
        select.disabled = !values.length;
      }
      apply.disabled = !body.timestamps.length;
      status.textContent = body.timestamps.length ? "Ready to apply" : "No data for this selection.";

    } catch (error) {
      if (error.name === "AbortError" || request !== pending) return;
      affected.forEach((select) => {
        const saved = previous.get(select);
        select.replaceChildren(...saved.options.map((option) => new Option(option.text, option.value)));
        select.value = saved.value;
        select.disabled = saved.disabled;
      });
      apply.disabled = true;
      status.textContent = `${error.message}. Change a selection to retry.`;
    } finally {
      if (request === pending) {
        form.querySelectorAll("[data-filter-loader]").forEach((loader) => { loader.hidden = true; });
      }
    }
  });
  document.addEventListener("submit", (event) => {
    if (event.target.matches("[data-filter-form]") &&
        event.target.querySelector('[type="submit"]').disabled) event.preventDefault();
  });
}

function updateInstanceSyncUrl(filterForm) {
  const syncForm = document.querySelector("[data-instance-sync-form]");
  if (!(syncForm instanceof HTMLFormElement)) return;
  const url = new URL(syncForm.action, window.location.href);
  for (const name of ["section", "instance", "subservice", "database"]) {
    const control = filterForm.elements.namedItem(name);
    if (control && "value" in control && control.value) {
      url.searchParams.set(name, control.value);
    } else {
      url.searchParams.delete(name);
    }
  }
  syncForm.action = url.href;
}
