let currentPageSize = 10;
let currentOffset = 0;
let currentRunDetail = null;
let latestGeneratedDraft = '';
const workspaceStorageKey = 'paper_writer_agent_workspace_draft';

function authHeaders() {
  const key = document.getElementById('apiKey').value.trim();
  return key ? { 'X-API-Key': key } : {};
}

function showStatus(message, tone = 'info') {
  const banner = document.getElementById('statusBanner');
  banner.textContent = message;
  banner.className = `status status-${tone} show`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function renderPaperMarkup(markdownText) {
  if (!markdownText) {
    return '<p class="muted">No paper content available.</p>';
  }

  const lines = markdownText.split('\n');
  const parts = [];
  let inList = false;
  let paragraph = [];

  function flushParagraph() {
    if (!paragraph.length) return;
    parts.push(`<p>${escapeHtml(paragraph.join(' '))}</p>`);
    paragraph = [];
  }

  function closeList() {
    if (!inList) return;
    parts.push('</ul>');
    inList = false;
  }

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      flushParagraph();
      closeList();
      continue;
    }
    if (line.startsWith('### ')) {
      flushParagraph();
      closeList();
      parts.push(`<h4>${escapeHtml(line.slice(4))}</h4>`);
      continue;
    }
    if (line.startsWith('## ')) {
      flushParagraph();
      closeList();
      parts.push(`<h3>${escapeHtml(line.slice(3))}</h3>`);
      continue;
    }
    if (line.startsWith('# ')) {
      flushParagraph();
      closeList();
      parts.push(`<h2>${escapeHtml(line.slice(2))}</h2>`);
      continue;
    }
    if (line.startsWith('- ')) {
      flushParagraph();
      if (!inList) {
        parts.push('<ul>');
        inList = true;
      }
      parts.push(`<li>${escapeHtml(line.slice(2))}</li>`);
      continue;
    }
    closeList();
    paragraph.push(line);
  }

  flushParagraph();
  closeList();
  return parts.join('');
}

function renderReviewMarkup(reviewText) {
  if (!reviewText) {
    return '<p class="muted">No review available.</p>';
  }
  const items = reviewText
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean);
  return `<ul>${items.map(item => `<li>${escapeHtml(item.replace(/^- /, ''))}</li>`).join('')}</ul>`;
}

function renderEvidenceLinks(researchSources) {
  const sources = Array.isArray(researchSources) ? researchSources : [];
  if (!sources.length) {
    return '<p class="muted">No evidence links available.</p>';
  }
  return `<ul>${sources.map((source) => {
    const citation = source.citation_id ?? '?';
    const title = source.title || 'Untitled source';
    const excerpt = source.excerpt || source.locator || 'No evidence excerpt.';
    return `<li><strong>[${escapeHtml(citation)}]</strong> ${escapeHtml(title)}<br/><span class="muted">${escapeHtml(excerpt)}</span></li>`;
  }).join('')}</ul>`;
}

function renderRunSummary(body) {
  return `
    <div class="summary-grid">
      <div><span class="summary-label">Run ID</span><span class="summary-value">${escapeHtml(body.run_id ?? '-')}</span></div>
      <div><span class="summary-label">Parent Run</span><span class="summary-value">${escapeHtml(body.parent_run_id || 'N/A')}</span></div>
      <div><span class="summary-label">Root Run</span><span class="summary-value">${escapeHtml(body.root_run_id || body.run_id || 'N/A')}</span></div>
      <div><span class="summary-label">Created At</span><span class="summary-value">${escapeHtml(body.created_at ?? '-')}</span></div>
      <div><span class="summary-label">Quality</span><span class="summary-value">${escapeHtml(body.quality_score ?? '-')}</span></div>
      <div><span class="summary-label">Duration</span><span class="summary-value">${escapeHtml(body.duration_ms ?? '-')} ms</span></div>
      <div><span class="summary-label">Stop Reason</span><span class="summary-value">${escapeHtml(body.stop_reason ?? '-')}</span></div>
      <div><span class="summary-label">Iterations Used</span><span class="summary-value">${escapeHtml(body.iterations_used ?? '-')}</span></div>
      <div><span class="summary-label">Revision Notes</span><span class="summary-value">${escapeHtml(body.revision_notes || 'N/A')}</span></div>
    </div>
  `;
}


function renderLineageRunCard(run, emptyLabel) {
  if (!run) {
    return `<p class="lineage-empty">${escapeHtml(emptyLabel)}</p>`;
  }
  return `
    <div class="lineage-run-card">
      <strong>${escapeHtml(run.run_id)}</strong>
      <p>${escapeHtml(run.task || 'Untitled task')}</p>
      <div class="lineage-meta">Quality ${escapeHtml(run.quality_score ?? '-')} · ${escapeHtml(run.stop_reason ?? '-')} · ${escapeHtml(run.created_at ?? '-')}</div>
      <button class="btn-small btn-secondary" type="button" data-lineage-run-id="${escapeHtml(run.run_id)}">View Run</button>
    </div>
  `;
}

function renderLineageRunList(runs, emptyLabel) {
  if (!(runs || []).length) {
    return `<p class="lineage-empty">${escapeHtml(emptyLabel)}</p>`;
  }
  return `<div class="lineage-run-list">${runs.map(run => renderLineageRunCard(run, '')).join('')}</div>`;
}

function renderRunLineage(lineage) {
  const parentMarkup = renderLineageRunCard(lineage.parent, 'No parent run. This run is the root of its current edit chain.');
  const childMarkup = renderLineageRunList(
    lineage.children,
    'No direct child runs yet. Saving an edited draft from this run will create one.'
  );
  const ancestorMarkup = renderLineageRunList(
    lineage.ancestors,
    'No ancestors found. This run is already the first known version in the chain.'
  );
  const descendantMarkup = renderLineageRunList(
    lineage.descendants,
    'No descendants found. This run has not been revised further yet.'
  );
  return `
    <div class="lineage-grid">
      <section>
        <h4 class="lineage-section-title">Parent</h4>
        ${parentMarkup}
      </section>
      <section>
        <h4 class="lineage-section-title">Direct Children</h4>
        ${childMarkup}
      </section>
      <section>
        <h4 class="lineage-section-title">Ancestor Chain</h4>
        ${ancestorMarkup}
      </section>
      <section>
        <h4 class="lineage-section-title">All Descendants</h4>
        ${descendantMarkup}
      </section>
    </div>
  `;
}

async function loadRunLineage(runId) {
  const lineageEl = document.getElementById('runLineage');
  lineageEl.innerHTML = '<p class="lineage-empty">Loading lineage...</p>';
  try {
    const res = await fetch(`/v1/papers/runs/${runId}/lineage`, { headers: authHeaders() });
    const body = await res.json();
    if (!res.ok) {
      const message = formatError(body, 'Unable to load run lineage.');
      lineageEl.innerHTML = `<p class="lineage-empty">${escapeHtml(message)}</p>`;
      lineageEl.classList.add('empty');
      return;
    }
    lineageEl.innerHTML = renderRunLineage(body);
    lineageEl.classList.remove('empty');
    lineageEl.querySelectorAll('[data-lineage-run-id]').forEach((el) => {
      el.addEventListener('click', () => loadRunDetail(el.getAttribute('data-lineage-run-id')));
    });
  } catch (error) {
    lineageEl.innerHTML = `<p class="lineage-empty">${escapeHtml(`Network error: ${String(error)}`)}</p>`;
    lineageEl.classList.add('empty');
  }
}

function setWorkspaceDraft(text) {
  const workspace = document.getElementById('draftWorkspace');
  workspace.value = text || '';
  persistWorkspaceDraft();
}

function persistWorkspaceDraft() {
  try {
    localStorage.setItem(workspaceStorageKey, document.getElementById('draftWorkspace').value);
  } catch (error) {
    console.warn('Unable to persist workspace draft', error);
  }
}

function restoreWorkspaceDraft() {
  try {
    const saved = localStorage.getItem(workspaceStorageKey);
    if (!saved) return;
    document.getElementById('draftWorkspace').value = saved;
    showStatus('Restored workspace draft from local storage.', 'info');
  } catch (error) {
    console.warn('Unable to restore workspace draft', error);
  }
}

function clearWorkspaceDraft() {
  document.getElementById('draftWorkspace').value = '';
  try {
    localStorage.removeItem(workspaceStorageKey);
  } catch (error) {
    console.warn('Unable to clear workspace draft', error);
  }
  const preview = document.getElementById('workspacePreview');
  preview.innerHTML = '<p class="muted">No workspace preview yet.</p>';
  preview.classList.add('empty');
  showStatus('Workspace cleared.', 'success');
}

async function importWorkspaceFile(event) {
  const file = event.target.files?.[0];
  if (!file) {
    return;
  }
  const text = await file.text();
  setWorkspaceDraft(text);
  previewWorkspaceDraft();
  showStatus(`Imported workspace draft from ${file.name}.`, 'success');
}

async function saveWorkspaceDraftAsRun() {
  if (!currentRunDetail?.run_id) {
    showStatus('Select a run before saving an edited draft back to the service.', 'info');
    return;
  }
  const workspaceValue = document.getElementById('draftWorkspace').value;
  if (!workspaceValue.trim()) {
    showStatus('Workspace is empty; nothing to save.', 'info');
    return;
  }
  try {
    const res = await fetch(`/v1/papers/runs/${encodeURIComponent(currentRunDetail.run_id)}/save-edited`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({
        draft: workspaceValue,
        review: currentRunDetail.review || 'Manual edit saved from workspace.',
        revision_notes: document.getElementById('revisionNotes').value,
      }),
    });
    const body = await res.json();
    if (!res.ok) {
      const message = formatError(body, 'Unable to save edited draft.');
      showStatus(`Save failed: ${message}`, 'error');
      return;
    }
    latestGeneratedDraft = body.draft || '';
    updateGenerationPreview(body);
    await refreshRuns();
    await loadRunDetail(body.run_id);
    await refreshMetrics();
    showStatus(`Edited draft saved as run ${body.run_id}.`, 'success');
  } catch (error) {
    showStatus(`Network error: ${String(error)}`, 'error');
  }
}

function previewWorkspaceDraft() {
  const workspaceValue = document.getElementById('draftWorkspace').value.trim();
  const preview = document.getElementById('workspacePreview');
  if (!workspaceValue) {
    preview.innerHTML = '<p class="muted">No workspace preview yet.</p>';
    preview.classList.add('empty');
    showStatus('Workspace is empty.', 'info');
    return;
  }
  preview.innerHTML = renderPaperMarkup(workspaceValue);
  preview.classList.remove('empty');
  showStatus('Workspace preview refreshed.', 'success');
}

function loadLatestDraftIntoWorkspace() {
  if (!latestGeneratedDraft) {
    showStatus('No generated draft available yet.', 'info');
    return;
  }
  setWorkspaceDraft(latestGeneratedDraft);
  previewWorkspaceDraft();
}

function loadSelectedRunDraftIntoWorkspace() {
  if (!currentRunDetail?.draft) {
    showStatus('No run draft selected yet.', 'info');
    return;
  }
  setWorkspaceDraft(currentRunDetail.draft);
  previewWorkspaceDraft();
}

function downloadWorkspaceDraft() {
  const workspaceValue = document.getElementById('draftWorkspace').value;
  if (!workspaceValue.trim()) {
    showStatus('Workspace is empty; nothing to download.', 'info');
    return;
  }
  const blob = new Blob([workspaceValue], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'edited-paper-draft.md';
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  showStatus('Edited draft downloaded.', 'success');
}

function setDraftDownloadLink(elementId, runId) {
  const link = document.getElementById(elementId);
  if (!runId) {
    link.href = '#';
    link.setAttribute('aria-disabled', 'true');
    return;
  }
  link.href = `/v1/papers/runs/${encodeURIComponent(runId)}/draft.md`;
  link.removeAttribute('aria-disabled');
}

function prefillEditorFromRun() {
  if (!currentRunDetail) {
    showStatus('No run selected to reuse.', 'info');
    return;
  }
  document.getElementById('task').value = currentRunDetail.task || '';
  document.getElementById('outline').value = currentRunDetail.outline || '';
  document.getElementById('revisionNotes').value = currentRunDetail.revision_notes || '';
  document.getElementById('iterations').value = String(currentRunDetail.iterations_requested || 2);
  showStatus(`Loaded run ${currentRunDetail.run_id} into the editor.`, 'success');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function getQueryParams(includeOffset = true) {
  syncPageSize();
  const params = new URLSearchParams();
  params.set('limit', String(currentPageSize));
  if (includeOffset) {
    params.set('offset', String(currentOffset));
  }
  const q = document.getElementById('qFilter').value.trim();
  const stopReason = document.getElementById('stopReasonFilter').value.trim();
  const parentRunId = document.getElementById('parentRunFilter').value.trim();
  const rootRunId = document.getElementById('rootRunFilter').value.trim();
  const lineageScope = document.getElementById('lineageScopeFilter').value.trim();
  const createdAfter = document.getElementById('createdAfterFilter').value.trim();
  const createdBefore = document.getElementById('createdBeforeFilter').value.trim();
  const minQuality = document.getElementById('minQualityFilter').value.trim();
  const maxQuality = document.getElementById('maxQualityFilter').value.trim();
  const sortBy = document.getElementById('sortByFilter').value.trim();
  const sortOrder = document.getElementById('sortOrderFilter').value.trim();
  const minDuration = document.getElementById('minDurationFilter').value.trim();
  const maxDuration = document.getElementById('maxDurationFilter').value.trim();
  if (q) params.set('q', q);
  if (stopReason) params.set('stop_reason', stopReason);
  if (parentRunId) params.set('parent_run_id', parentRunId);
  if (rootRunId) params.set('root_run_id', rootRunId);
  if (lineageScope) params.set('lineage_scope', lineageScope);
  if (createdAfter) params.set('created_after', new Date(createdAfter).toISOString());
  if (createdBefore) params.set('created_before', new Date(createdBefore).toISOString());
  if (minQuality) params.set('min_quality_score', minQuality);
  if (maxQuality) params.set('max_quality_score', maxQuality);
  if (sortBy) params.set('sort_by', sortBy);
  if (sortOrder) params.set('sort_order', sortOrder);
  if (minDuration) params.set('min_duration_ms', minDuration);
  if (maxDuration) params.set('max_duration_ms', maxDuration);
  return params;
}

function clearFilters() {
  document.getElementById('qFilter').value = '';
  document.getElementById('stopReasonFilter').value = '';
  document.getElementById('parentRunFilter').value = '';
  document.getElementById('rootRunFilter').value = '';
  document.getElementById('lineageScopeFilter').value = '';
  document.getElementById('createdAfterFilter').value = '';
  document.getElementById('createdBeforeFilter').value = '';
  document.getElementById('minQualityFilter').value = '';
  document.getElementById('maxQualityFilter').value = '';
  document.getElementById('sortByFilter').value = 'created_at';
  document.getElementById('sortOrderFilter').value = 'desc';
  document.getElementById('minDurationFilter').value = '';
  document.getElementById('maxDurationFilter').value = '';
  document.getElementById('pageSizeFilter').value = '10';
  currentPageSize = 10;
  currentOffset = 0;
  updateExportHref();
  refreshRuns();
  refreshMetrics();
}

function syncPageSize() {
  currentPageSize = Number(document.getElementById('pageSizeFilter').value || 10);
}

function updateExportHref() {
  syncPageSize();
  const params = getQueryParams(false);
  const exportBtn = document.getElementById('exportBtn');
  exportBtn.href = `/v1/papers/runs/export.csv?${params.toString()}`;
}

function updatePagination(body) {
  const summary = document.getElementById('pageSummary');
  const prevBtn = document.getElementById('prevPageBtn');
  const nextBtn = document.getElementById('nextPageBtn');
  const total = body.total || 0;
  const pageIndex = Math.floor(currentOffset / currentPageSize) + 1;
  const totalPages = Math.max(1, Math.ceil(total / currentPageSize));
  summary.textContent = `Page ${pageIndex} / ${totalPages} · Total ${total}`;
  prevBtn.disabled = currentOffset <= 0;
  nextBtn.disabled = !body.has_more;
}

function formatError(body, fallback) {
  if (!body) return fallback;
  if (typeof body.detail === 'string') return body.detail;
  return JSON.stringify(body, null, 2);
}

function setButtonBusy(buttonId, busy, busyText) {
  const btn = document.getElementById(buttonId);
  if (!btn) return;
  if (!btn.dataset.defaultText) {
    btn.dataset.defaultText = btn.textContent;
  }
  btn.disabled = busy;
  btn.textContent = busy ? busyText : btn.dataset.defaultText;
}

function updateGenerationPreview(body) {
  document.getElementById('generateResult').textContent = JSON.stringify(body, null, 2);
  document.getElementById('paperPreview').innerHTML = renderPaperMarkup(body.draft);
  document.getElementById('paperPreview').classList.remove('empty');
  document.getElementById('reviewPreview').innerHTML = renderReviewMarkup(body.review);
  document.getElementById('reviewPreview').classList.remove('empty');
  document.getElementById('evidencePreview').innerHTML = renderEvidenceLinks(body.research_sources);
  document.getElementById('evidencePreview').classList.remove('empty');
  latestGeneratedDraft = body.draft || '';
  setDraftDownloadLink('downloadLatestDraftBtn', body.run_id);
}

async function generatePaper() {
  const payload = {
    task: document.getElementById('task').value,
    outline: document.getElementById('outline').value,
    revision_notes: document.getElementById('revisionNotes').value,
    iterations: Number(document.getElementById('iterations').value || 2),
  };
  const resultEl = document.getElementById('generateResult');
  resultEl.textContent = 'Generating...';
  showStatus('Submitting generation request...', 'info');
  try {
    const res = await fetch('/v1/papers/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(payload),
    });
    const body = await res.json();
    if (!res.ok) {
      const message = formatError(body, 'Generation failed.');
      resultEl.textContent = `Error: ${message}`;
      showStatus(`Generation failed: ${message}`, 'error');
      return;
    }
    updateGenerationPreview(body);
    currentOffset = 0;
    updateExportHref();
    await refreshRuns();
    await loadRunDetail(body.run_id);
    await refreshMetrics();
    showStatus(`Generation succeeded. Run ID: ${body.run_id}`, 'success');
  } catch (e) {
    const message = `Network error: ${String(e)}`;
    resultEl.textContent = message;
    showStatus(message, 'error');
  }
}

async function loadRunDetail(runId) {
  const detailEl = document.getElementById('runDetail');
  const summaryEl = document.getElementById('runDetailSummary');
  const draftEl = document.getElementById('runDraftPreview');
  const reviewEl = document.getElementById('runReviewPreview');
  const evidenceEl = document.getElementById('runEvidencePreview');
  const revisionPlanEl = document.getElementById('revisionPlanPanel');
  const diffEl = document.getElementById('runDiffPanel');
  const lineageEl = document.getElementById('runLineage');
  detailEl.textContent = 'Loading run detail...';
  summaryEl.textContent = 'Loading run detail...';
  draftEl.innerHTML = '<p class="muted">Loading draft...</p>';
  reviewEl.innerHTML = '<p class="muted">Loading review...</p>';
  evidenceEl.innerHTML = '<p class="muted">Loading evidence...</p>';
  revisionPlanEl.innerHTML = '<p class="loading-note">Loading revision plan...</p>';
  diffEl.innerHTML = '<p class="loading-note">Diff not loaded yet.</p>';
  lineageEl.innerHTML = '<p class="lineage-empty">Loading lineage...</p>';
  try {
    const res = await fetch(`/v1/papers/runs/${runId}`, { headers: authHeaders() });
    const body = await res.json();
    if (!res.ok) {
      const message = formatError(body, 'Unable to load run detail.');
      detailEl.textContent = `Error: ${message}`;
      summaryEl.textContent = `Error: ${message}`;
      draftEl.innerHTML = `<p class="muted">${escapeHtml(message)}</p>`;
      reviewEl.innerHTML = `<p class="muted">${escapeHtml(message)}</p>`;
      evidenceEl.innerHTML = `<p class="muted">${escapeHtml(message)}</p>`;
      revisionPlanEl.innerHTML = `<p class="muted">${escapeHtml(message)}</p>`;
      diffEl.innerHTML = `<p class="muted">${escapeHtml(message)}</p>`;
      lineageEl.innerHTML = `<p class="lineage-empty">${escapeHtml(message)}</p>`;
      showStatus(`Run detail failed: ${message}`, 'error');
      return;
    }
    detailEl.textContent = JSON.stringify(body, null, 2);
    currentRunDetail = body;
    summaryEl.innerHTML = renderRunSummary(body);
    summaryEl.classList.remove('empty');
    draftEl.innerHTML = renderPaperMarkup(body.draft);
    draftEl.classList.remove('empty');
    reviewEl.innerHTML = renderReviewMarkup(body.review);
    reviewEl.classList.remove('empty');
    evidenceEl.innerHTML = renderEvidenceLinks(body.research_sources);
    evidenceEl.classList.remove('empty');
    setDraftDownloadLink('downloadRunDraftBtn', body.run_id);
    await loadRevisionPlan(body.run_id);
    await loadRunLineage(body.run_id);
    showStatus(`Viewing run: ${runId}`, 'info');
  } catch (e) {
    const message = `Network error: ${String(e)}`;
    detailEl.textContent = message;
    summaryEl.textContent = message;
    draftEl.innerHTML = `<p class="muted">${escapeHtml(message)}</p>`;
    reviewEl.innerHTML = `<p class="muted">${escapeHtml(message)}</p>`;
    evidenceEl.innerHTML = `<p class="muted">${escapeHtml(message)}</p>`;
    revisionPlanEl.innerHTML = `<p class="muted">${escapeHtml(message)}</p>`;
    diffEl.innerHTML = `<p class="muted">${escapeHtml(message)}</p>`;
    lineageEl.innerHTML = `<p class="lineage-empty">${escapeHtml(message)}</p>`;
    setDraftDownloadLink('downloadRunDraftBtn', null);
    showStatus(message, 'error');
  }
}

async function loadRevisionPlan(runId) {
  const panel = document.getElementById('revisionPlanPanel');
  panel.innerHTML = '<p class="loading-note">Loading revision plan...</p>';
  try {
    const res = await fetch(`/v1/papers/runs/${runId}/revision-plan`, { headers: authHeaders() });
    const body = await res.json();
    if (!res.ok) {
      panel.innerHTML = `<p class="muted">${escapeHtml(formatError(body, 'Unable to load revision plan.'))}</p>`;
      panel.classList.add('empty');
      return;
    }
    const items = body.items || [];
    if (!items.length) {
      panel.innerHTML = '<p class="muted">No revision plan items available.</p>';
      panel.classList.add('empty');
      return;
    }
    panel.innerHTML = `<ul class="revision-plan-list">${items.map((item, idx) => `
      <li class="revision-plan-item">
        <input type="checkbox" id="planItem${idx}" data-plan-item="${escapeHtml(item)}" />
        <label for="planItem${idx}">${escapeHtml(item)}</label>
      </li>
    `).join('')}</ul>`;
    panel.classList.remove('empty');
  } catch (error) {
    panel.innerHTML = `<p class="muted">${escapeHtml(`Network error: ${String(error)}`)}</p>`;
    panel.classList.add('empty');
  }
}

async function applySelectedPlanItems() {
  if (!currentRunDetail?.run_id) {
    showStatus('Please select a run first.', 'info');
    return;
  }
  const selected = Array.from(document.querySelectorAll('[data-plan-item]:checked')).map((el) => el.dataset.planItem || '');
  if (!selected.length) {
    showStatus('Select at least one revision plan item to apply.', 'info');
    return;
  }
  setButtonBusy('applyPlanBtn', true, 'Applying...');
  try {
    const res = await fetch(`/v1/papers/runs/${currentRunDetail.run_id}/revision-plan/apply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ selected_items: selected, mode: 'patch' }),
    });
    const body = await res.json();
    if (!res.ok) {
      showStatus(`Apply plan failed: ${formatError(body, 'request failed')}`, 'error');
      return;
    }
    latestGeneratedDraft = body.draft || '';
    updateGenerationPreview(body);
    await refreshRuns();
    await loadRunDetail(body.run_id);
    await refreshMetrics();
    showStatus(`Applied revision plan. New run: ${body.run_id}`, 'success');
  } catch (error) {
    showStatus(`Network error: ${String(error)}`, 'error');
  } finally {
    setButtonBusy('applyPlanBtn', false, 'Applying...');
  }
}

async function loadDiffAgainstParent() {
  const panel = document.getElementById('runDiffPanel');
  if (!currentRunDetail?.run_id) {
    showStatus('Please select a run first.', 'info');
    return;
  }
  if (!currentRunDetail.parent_run_id) {
    panel.innerHTML = '<p class="muted">Current run has no parent; diff unavailable.</p>';
    panel.classList.add('empty');
    return;
  }
  setButtonBusy('loadDiffBtn', true, 'Loading Diff...');
  panel.innerHTML = '<p class="loading-note">Loading diff...</p>';
  try {
    const params = new URLSearchParams({ against: currentRunDetail.parent_run_id });
    const res = await fetch(`/v1/papers/runs/${currentRunDetail.run_id}/diff?${params.toString()}`, { headers: authHeaders() });
    const body = await res.json();
    if (!res.ok) {
      panel.innerHTML = `<p class="muted">${escapeHtml(formatError(body, 'Unable to load diff.'))}</p>`;
      panel.classList.add('empty');
      return;
    }
    panel.innerHTML = `<pre>${escapeHtml(body.diff_preview || 'No diff preview available.')}</pre>`;
    panel.classList.remove('empty');
  } catch (error) {
    panel.innerHTML = `<p class="muted">${escapeHtml(`Network error: ${String(error)}`)}</p>`;
    panel.classList.add('empty');
  } finally {
    setButtonBusy('loadDiffBtn', false, 'Loading Diff...');
  }
}

function renderMetricsSummary(body) {
  document.getElementById('metricTotalRuns').textContent = String(body.total_runs ?? '-');
  document.getElementById('metricAvgQuality').textContent = body.avg_quality_score?.toFixed
    ? body.avg_quality_score.toFixed(2)
    : String(body.avg_quality_score ?? '-');
  document.getElementById('metricAvgDuration').textContent = body.avg_duration_ms?.toFixed
    ? body.avg_duration_ms.toFixed(2)
    : String(body.avg_duration_ms ?? '-');
  document.getElementById('metricSuccessRate').textContent = body.success_rate?.toFixed
    ? `${(body.success_rate * 100).toFixed(2)}%`
    : String(body.success_rate ?? '-');
  document.getElementById('metricReasonCounts').textContent = JSON.stringify(body.stop_reason_counts || {}, null, 2);
}

async function refreshMetrics() {
  const metricsEl = document.getElementById('metricsResult');
  metricsEl.textContent = 'Loading metrics...';
  try {
    const params = getQueryParams(false);
    params.delete('limit');
    const res = await fetch(`/v1/papers/metrics?${params.toString()}`, { headers: authHeaders() });
    const body = await res.json();
    if (!res.ok) {
      const message = formatError(body, 'Unable to load metrics.');
      metricsEl.textContent = `Error: ${message}`;
      showStatus(`Metrics failed: ${message}`, 'error');
      return;
    }
    renderMetricsSummary(body);
    metricsEl.textContent = JSON.stringify(body, null, 2);
  } catch (e) {
    const message = `Network error: ${String(e)}`;
    metricsEl.textContent = message;
    showStatus(message, 'error');
  }
}

function getStrategyDays() {
  const value = Number(document.getElementById('strategyDays').value);
  if (!Number.isFinite(value) || value < 1) return 7;
  return Math.min(90, Math.floor(value));
}

async function refreshStrategyDashboard() {
  const output = document.getElementById('strategyDashboardResult');
  output.textContent = 'Loading strategy dashboard...';
  try {
    const days = getStrategyDays();
    const res = await fetch(`/v1/papers/slo/alerts/strategy-experiments/dashboard?days=${days}`, { headers: authHeaders() });
    const body = await res.json();
    if (!res.ok) {
      const message = formatError(body, 'Unable to load strategy dashboard.');
      output.textContent = `Error: ${message}`;
      showStatus(`Strategy dashboard failed: ${message}`, 'error');
      return;
    }
    document.getElementById('strategyExperimentTotal').textContent = String(body.total_experiments ?? '-');
    document.getElementById('strategyGuardrailPassRate').textContent = body.guardrail_pass_rate != null
      ? `${(Number(body.guardrail_pass_rate) * 100).toFixed(2)}%`
      : '-';

    const canaryRes = await fetch(`/v1/papers/slo/alerts/strategy-canary/status?days=${days}`, { headers: authHeaders() });
    const canaryBody = await canaryRes.json();
    if (canaryRes.ok) {
      document.getElementById('strategyCanaryRecommended').textContent = canaryBody.canary_recommended ? 'Yes' : 'No';
      document.getElementById('strategyCanaryRatio').textContent = String(canaryBody.canary_ratio ?? '-');
    }
    output.textContent = JSON.stringify(body, null, 2);
  } catch (error) {
    output.textContent = `Network error: ${String(error)}`;
    showStatus(`Strategy dashboard network error: ${String(error)}`, 'error');
  }
}

async function autoReplayStrategies() {
  const output = document.getElementById('strategyReplayResult');
  output.textContent = 'Running auto replay...';
  try {
    const days = getStrategyDays();
    const res = await fetch(`/v1/papers/slo/alerts/strategy-experiments/auto-replay?days=${days}`, {
      method: 'POST',
      headers: authHeaders(),
    });
    const body = await res.json();
    if (!res.ok) {
      const message = formatError(body, 'Unable to run auto replay.');
      output.textContent = `Error: ${message}`;
      showStatus(`Auto replay failed: ${message}`, 'error');
      return;
    }
    output.textContent = JSON.stringify(body, null, 2);
    showStatus('Strategy auto replay completed.', 'success');
    await refreshStrategyDashboard();
  } catch (error) {
    output.textContent = `Network error: ${String(error)}`;
    showStatus(`Auto replay network error: ${String(error)}`, 'error');
  }
}

async function toggleCanary(enabled) {
  const output = document.getElementById('strategyReplayResult');
  try {
    const days = getStrategyDays();
    const res = await fetch(`/v1/papers/slo/alerts/strategy-canary/toggle?days=${days}&enabled=${enabled}`, {
      method: 'POST',
      headers: authHeaders(),
    });
    const body = await res.json();
    if (!res.ok) {
      const message = formatError(body, 'Unable to toggle canary.');
      showStatus(`Canary toggle failed: ${message}`, 'error');
      return;
    }
    output.textContent = JSON.stringify(body, null, 2);
    showStatus(`Canary is now ${body.canary_enabled ? 'enabled' : 'disabled'}.`, 'success');
    await refreshStrategyDashboard();
  } catch (error) {
    showStatus(`Canary toggle network error: ${String(error)}`, 'error');
  }
}

async function refreshRuns() {
  const tbody = document.getElementById('runsBody');
  tbody.innerHTML = '<tr><td colspan="8">Loading...</td></tr>';
  updateExportHref();
  try {
    const res = await fetch(`/v1/papers/runs?${getQueryParams(true).toString()}`, { headers: authHeaders() });
    const body = await res.json();
    if (!res.ok) {
      const message = formatError(body, 'Unable to load runs.');
      tbody.innerHTML = `<tr><td colspan="8">Error: ${message}</td></tr>`;
      showStatus(`Run list failed: ${message}`, 'error');
      updatePagination({ total: 0, has_more: false });
      return;
    }
    const items = body.items || [];
    updatePagination(body);
    if (!items.length) {
      tbody.innerHTML = '<tr><td colspan="8">No runs for current filter.</td></tr>';
      showStatus('No runs matched the current filter.', 'info');
      return;
    }
    tbody.innerHTML = items.map((r) => `
      <tr>
        <td>${escapeHtml(r.run_id)}</td>
        <td>${escapeHtml(r.parent_run_id || 'ROOT')}</td>
        <td>${escapeHtml(r.root_run_id || r.run_id || 'ROOT')}</td>
        <td>${escapeHtml(r.quality_score)}</td>
        <td>${escapeHtml(r.stop_reason)}</td>
        <td>${escapeHtml(r.created_at)}</td>
        <td>${escapeHtml(r.duration_ms)}</td>
        <td><button class="btn-small" data-run-id="${escapeHtml(r.run_id)}">View</button></td>
      </tr>
    `).join('');

    document.querySelectorAll('[data-run-id]').forEach((el) => {
      el.addEventListener('click', () => loadRunDetail(el.getAttribute('data-run-id')));
    });
    showStatus(`Loaded ${items.length} run(s).`, 'info');
  } catch (e) {
    const message = `Network error: ${String(e)}`;
    tbody.innerHTML = `<tr><td colspan="8">${message}</td></tr>`;
    showStatus(message, 'error');
    updatePagination({ total: 0, has_more: false });
  }
}

function applyFilters() {
  syncPageSize();
  currentOffset = 0;
  refreshRuns();
  refreshMetrics();
}

document.getElementById('generateBtn').addEventListener('click', generatePaper);
document.getElementById('refreshBtn').addEventListener('click', applyFilters);
document.getElementById('metricsBtn').addEventListener('click', refreshMetrics);
document.getElementById('clearFiltersBtn').addEventListener('click', clearFilters);
document.getElementById('reuseRunBtn').addEventListener('click', prefillEditorFromRun);
document.getElementById('loadPreviewIntoWorkspaceBtn').addEventListener('click', loadLatestDraftIntoWorkspace);
document.getElementById('loadRunIntoWorkspaceBtn').addEventListener('click', loadSelectedRunDraftIntoWorkspace);
document.getElementById('previewWorkspaceBtn').addEventListener('click', previewWorkspaceDraft);
document.getElementById('downloadWorkspaceBtn').addEventListener('click', downloadWorkspaceDraft);
document.getElementById('saveWorkspaceBtn').addEventListener('click', saveWorkspaceDraftAsRun);
document.getElementById('workspaceFileInput').addEventListener('change', importWorkspaceFile);
document.getElementById('clearWorkspaceBtn').addEventListener('click', clearWorkspaceDraft);
document.getElementById('applyPlanBtn').addEventListener('click', applySelectedPlanItems);
document.getElementById('loadDiffBtn').addEventListener('click', loadDiffAgainstParent);
document.getElementById('refreshStrategyDashboardBtn').addEventListener('click', refreshStrategyDashboard);
document.getElementById('autoReplayBtn').addEventListener('click', autoReplayStrategies);
document.getElementById('enableCanaryBtn').addEventListener('click', () => toggleCanary(true));
document.getElementById('disableCanaryBtn').addEventListener('click', () => toggleCanary(false));
document.getElementById('draftWorkspace').addEventListener('input', persistWorkspaceDraft);
document.getElementById('prevPageBtn').addEventListener('click', () => {
  currentOffset = Math.max(0, currentOffset - currentPageSize);
  refreshRuns();
});
document.getElementById('nextPageBtn').addEventListener('click', () => {
  currentOffset += currentPageSize;
  refreshRuns();
});

setDraftDownloadLink('downloadLatestDraftBtn', null);
setDraftDownloadLink('downloadRunDraftBtn', null);
restoreWorkspaceDraft();
updateExportHref();
refreshRuns();
refreshMetrics();
refreshStrategyDashboard();
