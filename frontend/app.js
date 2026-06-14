'use strict';

/* ─── Constants ─────────────────────────────────────────── */
const API = '/api/v1';

/* ─── State ──────────────────────────────────────────────── */
let predictions = [];
let stats = null;
let calibrationChart = null;
let activeFilter = 'all';
let detailId = null;

/* ─── Verbal confidence hints ────────────────────────────── */
function probHint(v) {
  if (v <= 5)  return 'almost impossible';
  if (v <= 15) return 'very unlikely';
  if (v <= 30) return 'unlikely';
  if (v <= 45) return 'leans against';
  if (v <= 55) return 'coin-flip';
  if (v <= 65) return 'leans toward';
  if (v <= 75) return 'fairly likely';
  if (v <= 85) return 'likely';
  if (v <= 93) return 'very likely';
  if (v <= 97) return 'near-certain';
  return 'almost certain';
}

/* ─── Date helpers ────────────────────────────────────────── */
function isoToday() {
  return new Date().toISOString().slice(0, 10);
}

function defaultResolveBy() {
  const d = new Date();
  d.setDate(d.getDate() + 30);
  return d.toISOString().slice(0, 10);
}

function fmtDate(s) {
  if (!s) return '—';
  const [y, m, d] = s.split('-');
  return `${d}/${m}/${y}`;
}

/* ─── Status helpers ──────────────────────────────────────── */
function predStatus(p) {
  if (p.status === 'resolved') return p.outcome === 1 ? 'correct' : 'wrong';
  if (p.due) return 'due';
  return 'open';
}

function badgeHTML(status) {
  const map = {
    open:    ['badge-open',    '⏳', 'Open'],
    due:     ['badge-due',     '⏰', 'Due now'],
    correct: ['badge-correct', '✅', 'Correct'],
    wrong:   ['badge-wrong',   '❌', 'Wrong'],
  };
  const [cls, icon, label] = map[status] || ['badge-open', '⏳', 'Open'];
  return `<span class="badge ${cls}" aria-label="${label}"><span aria-hidden="true">${icon}</span> ${label}</span>`;
}

/* ─── API calls ───────────────────────────────────────────── */
async function apiFetch(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

async function loadAll() {
  const [preds, st] = await Promise.all([
    apiFetch('/predictions'),
    apiFetch('/stats'),
  ]);
  predictions = preds;
  stats = st;
}

/* ─── Stats row ───────────────────────────────────────────── */
function renderStats() {
  const row = document.getElementById('stats-row');
  if (!stats) return;

  const brier = stats.brier != null ? stats.brier.toFixed(3) : null;
  const label = stats.label || '';
  const due = stats.count_due || 0;

  row.innerHTML = `
    <div class="stat-card">
      <span class="text-xs font-medium text-muted uppercase tracking-wide">Brier Score</span>
      <span class="font-mono text-3xl font-semibold text-ink">${brier != null ? brier : '—'}</span>
      ${brier != null ? `<span class="text-xs text-muted">${label}</span>` : '<span class="text-xs text-muted">no resolved yet</span>'}
    </div>
    <div class="stat-card">
      <span class="text-xs font-medium text-muted uppercase tracking-wide">Resolved</span>
      <span class="font-mono text-3xl font-semibold text-ink">${stats.count_resolved ?? 0}</span>
      <span class="text-xs text-muted">predictions</span>
    </div>
    <div class="stat-card">
      <span class="text-xs font-medium text-muted uppercase tracking-wide">Open</span>
      <span class="font-mono text-3xl font-semibold text-ink">${stats.count_open ?? 0}</span>
      <span class="text-xs text-muted">predictions</span>
    </div>
    <div class="stat-card">
      <span class="text-xs font-medium text-muted uppercase tracking-wide">Due to Resolve</span>
      <span class="font-mono text-3xl font-semibold ${due > 0 ? 'text-pending' : 'text-ink'}">${due}</span>
      ${due > 0 ? `<span class="due-pill pulsing"><span aria-hidden="true">⏰</span> ${due} due</span>` : '<span class="text-xs text-muted">none due</span>'}
    </div>
  `;
}

/* ─── Calibration chart ───────────────────────────────────── */
function renderChart() {
  const skeleton = document.getElementById('chart-skeleton');
  const canvas = document.getElementById('calibration-chart');

  skeleton.classList.add('hidden');
  canvas.classList.remove('hidden');

  const calData = (stats && stats.calibration) ? stats.calibration : [];

  const points = calData.map(b => ({
    x: (b.mean_prob * 100),
    y: (b.hit_rate * 100),
    r: Math.max(4, Math.min(18, b.n * 2)),
    _bucket: b.bucket,
    _hitRate: b.hit_rate,
    _n: b.n,
  }));

  const diag = [{ x: 0, y: 0 }, { x: 100, y: 100 }];

  const emptyState = calData.length === 0;

  if (calibrationChart) {
    calibrationChart.destroy();
    calibrationChart = null;
  }

  const ctx = canvas.getContext('2d');
  calibrationChart = new Chart(ctx, {
    type: 'scatter',
    data: {
      datasets: [
        {
          label: 'Perfect calibration',
          data: diag,
          type: 'line',
          borderColor: 'rgba(100, 116, 139, 0.4)',
          borderDash: [6, 4],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
          tension: 0,
        },
        {
          label: 'Your calibration',
          data: points,
          backgroundColor: 'rgba(15, 118, 110, 0.7)',
          borderColor: '#0F766E',
          borderWidth: 1.5,
          pointRadius: points.map(p => p.r),
          pointHoverRadius: points.map(p => p.r + 3),
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: {
        duration: 400,
        easing: 'easeOutCubic',
      },
      scales: {
        x: {
          type: 'linear',
          min: 0,
          max: 100,
          title: { display: true, text: 'Your confidence %', color: '#64748B', font: { family: 'Inter', size: 12 } },
          grid: { color: '#E6E9F0' },
          ticks: { color: '#64748B', font: { family: 'JetBrains Mono', size: 11 }, callback: v => `${v}%` },
        },
        y: {
          type: 'linear',
          min: 0,
          max: 100,
          title: { display: true, text: 'Reality %', color: '#64748B', font: { family: 'Inter', size: 12 } },
          grid: { color: '#E6E9F0' },
          ticks: { color: '#64748B', font: { family: 'JetBrains Mono', size: 11 }, callback: v => `${v}%` },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label(ctx) {
              const d = ctx.raw;
              if (!d._bucket && d._bucket !== 0) return `(${d.x.toFixed(0)}%, ${d.y.toFixed(0)}%)`;
              return [
                `Bucket: ${d._bucket}`,
                `Hit rate: ${(d._hitRate * 100).toFixed(0)}%`,
                `n = ${d._n}`,
              ];
            },
          },
          backgroundColor: '#0F172A',
          titleColor: '#FFFFFF',
          bodyColor: '#94A3B8',
          padding: 10,
          cornerRadius: 10,
        },
      },
    },
  });

  if (emptyState) {
    // Draw placeholder text on canvas
    ctx.save();
    ctx.font = '14px Inter, sans-serif';
    ctx.fillStyle = '#94A3B8';
    ctx.textAlign = 'center';
    ctx.fillText('Your calibration chart will appear here once you resolve predictions.', canvas.width / 2, canvas.height / 2);
    ctx.restore();
  }
}

/* ─── Resolve section ──────────────────────────────────────── */
function renderDueSection() {
  const section = document.getElementById('resolve-section');
  const list = document.getElementById('due-list');
  const due = predictions.filter(p => p.status === 'open' && p.due);

  if (due.length === 0) {
    section.classList.add('hidden');
    return;
  }
  section.classList.remove('hidden');

  list.innerHTML = due.map(p => `
    <div class="due-card fade-in" id="due-card-${p.id}">
      <div class="flex-1 min-w-0">
        <p class="text-ink font-medium text-sm leading-snug truncate">${escHtml(p.claim)}</p>
        <p class="text-muted text-xs mt-0.5">
          <span class="font-mono">${Math.round(p.probability * 100)}%</span> confidence · due ${fmtDate(p.resolve_by)}
        </p>
      </div>
      <div class="flex gap-2 shrink-0">
        <button
          class="resolve-btn resolve-btn-hit"
          onclick="resolveInline('${p.id}', true)"
          aria-label="It happened"
        ><span aria-hidden="true">✅</span> It happened</button>
        <button
          class="resolve-btn resolve-btn-miss"
          onclick="resolveInline('${p.id}', false)"
          aria-label="It didn't happen"
        ><span aria-hidden="true">❌</span> It didn't</button>
      </div>
    </div>
  `).join('');
}

/* ─── History list ─────────────────────────────────────────── */
function filteredPredictions() {
  switch (activeFilter) {
    case 'open':    return predictions.filter(p => p.status === 'open' && !p.due);
    case 'due':     return predictions.filter(p => p.status === 'open' && p.due);
    case 'correct': return predictions.filter(p => p.status === 'resolved' && p.outcome === 1);
    case 'wrong':   return predictions.filter(p => p.status === 'resolved' && p.outcome === 0);
    default:        return predictions;
  }
}

function renderHistory() {
  const list = document.getElementById('history-list');
  const empty = document.getElementById('empty-state');
  const items = filteredPredictions();

  if (predictions.length === 0) {
    list.innerHTML = '';
    empty.classList.remove('hidden');
    return;
  }
  empty.classList.add('hidden');

  if (items.length === 0) {
    list.innerHTML = `<p class="text-muted text-sm text-center py-8">No predictions in this category.</p>`;
    return;
  }

  list.innerHTML = items.map(p => {
    const status = predStatus(p);
    const cat = p.category ? `<span class="text-xs text-muted border border-border rounded-full px-2 py-0.5">${escHtml(p.category)}</span>` : '';
    return `
      <div
        class="prediction-row fade-in"
        role="button"
        tabindex="0"
        aria-label="View prediction: ${escHtml(p.claim)}"
        onclick="openDetail('${p.id}')"
        onkeydown="if(event.key==='Enter'||event.key===' ')openDetail('${p.id}')"
        id="prow-${p.id}"
      >
        <div class="flex-1 min-w-0">
          <p class="text-ink font-medium text-sm leading-snug line-clamp-1">${escHtml(p.claim)}</p>
          <div class="flex items-center gap-2 mt-1 flex-wrap">
            ${badgeHTML(status)}
            ${cat}
            <span class="text-xs text-muted">Resolve by ${fmtDate(p.resolve_by)}</span>
          </div>
        </div>
        <span class="font-mono text-lg font-semibold text-brand shrink-0">${Math.round(p.probability * 100)}%</span>
      </div>
    `;
  }).join('');
}

/* ─── Detail panel ─────────────────────────────────────────── */
function openDetail(id) {
  const p = predictions.find(x => x.id === id);
  if (!p) return;
  detailId = id;
  const status = predStatus(p);

  document.getElementById('detail-title').textContent = 'Prediction detail';
  document.getElementById('detail-body').innerHTML = `
    <div class="space-y-3">
      <p class="text-ink font-medium leading-relaxed">${escHtml(p.claim)}</p>
      <div class="flex flex-wrap gap-3 items-center">
        <span class="font-mono text-2xl font-semibold text-brand">${Math.round(p.probability * 100)}%</span>
        ${badgeHTML(status)}
        ${p.category ? `<span class="text-xs text-muted border border-border rounded-full px-2 py-0.5">${escHtml(p.category)}</span>` : ''}
      </div>
      <p class="text-sm text-muted">Resolve by: <span class="text-ink">${fmtDate(p.resolve_by)}</span></p>
      <p class="text-sm text-muted">Created: <span class="text-ink">${fmtDate(p.created_at ? p.created_at.slice(0,10) : '')}</span></p>
      ${p.resolved_at ? `<p class="text-sm text-muted">Resolved: <span class="text-ink">${fmtDate(p.resolved_at.slice(0,10))}</span></p>` : ''}
    </div>
  `;

  document.getElementById('detail-overlay').classList.remove('hidden');
}

function closeDetail() {
  document.getElementById('detail-overlay').classList.add('hidden');
  detailId = null;
}

/* ─── Resolve inline ───────────────────────────────────────── */
async function resolveInline(id, outcome) {
  const card = document.getElementById(`due-card-${id}`);
  if (card) {
    card.style.opacity = '0.5';
    card.style.pointerEvents = 'none';
  }
  try {
    await apiFetch(`/predictions/${id}/resolve`, {
      method: 'PATCH',
      body: JSON.stringify({ outcome }),
    });
    await refreshData();
    // Celebrate
    const row = document.getElementById(`prow-${id}`);
    if (row) row.classList.add('celebrate');
  } catch (e) {
    if (card) {
      card.style.opacity = '';
      card.style.pointerEvents = '';
    }
    showToast('Couldn\'t resolve — try again');
  }
}

window.resolveInline = resolveInline;
window.openDetail = openDetail;

/* ─── Delete ────────────────────────────────────────────────── */
async function deletePrediction() {
  if (!detailId) return;
  const btn = document.getElementById('delete-btn');
  btn.disabled = true;
  btn.textContent = 'Deleting…';
  try {
    await apiFetch(`/predictions/${detailId}`, { method: 'DELETE' });
    closeDetail();
    await refreshData();
  } catch (e) {
    btn.disabled = false;
    btn.textContent = '🗑 Delete prediction';
    showToast('Couldn\'t delete — try again');
  }
}

/* ─── New prediction modal ─────────────────────────────────── */
function openModal() {
  const modal = document.getElementById('modal-overlay');
  document.getElementById('claim-input').value = '';
  document.getElementById('prob-slider').value = 70;
  document.getElementById('prob-readout').textContent = '70%';
  document.getElementById('prob-hint').textContent = probHint(70);
  document.getElementById('resolve-by').value = defaultResolveBy();
  document.getElementById('selected-category').value = '';
  document.getElementById('claim-error').classList.add('hidden');
  document.getElementById('date-error').classList.add('hidden');
  document.getElementById('submit-error').classList.add('hidden');
  document.querySelectorAll('.cat-chip').forEach(c => c.classList.remove('selected'));
  updateSliderTrack(70);
  modal.classList.remove('hidden');
  setTimeout(() => document.getElementById('claim-input').focus(), 50);
}

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
}

function updateSliderTrack(v) {
  const slider = document.getElementById('prob-slider');
  slider.style.setProperty('--val', `${v}%`);
  slider.style.background = `linear-gradient(to right, #0F766E ${v}%, #E6E9F0 ${v}%)`;
  slider.setAttribute('aria-valuenow', v);
}

/* ─── Filter tabs ───────────────────────────────────────────── */
function setFilter(f) {
  activeFilter = f;
  document.querySelectorAll('.filter-tab').forEach(btn => {
    const isActive = btn.dataset.filter === f;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
  });
  renderHistory();
}

/* ─── Toast ─────────────────────────────────────────────────── */
let toastTimeout;
function showToast(msg) {
  let toast = document.getElementById('toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast';
    toast.className = 'fixed bottom-6 left-1/2 -translate-x-1/2 bg-ink text-white text-sm font-medium px-5 py-3 rounded-control shadow-card z-50 transition-opacity duration-200';
    toast.setAttribute('role', 'status');
    toast.setAttribute('aria-live', 'polite');
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.style.opacity = '1';
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => { toast.style.opacity = '0'; }, 3000);
}

/* ─── Escape HTML ────────────────────────────────────────────── */
function escHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/* ─── Refresh cycle ──────────────────────────────────────────── */
async function refreshData() {
  try {
    await loadAll();
  } catch (e) {
    showToast('Couldn\'t load data — ' + e.message);
    return;
  }
  renderStats();
  renderChart();
  renderDueSection();
  renderHistory();
}

/* ─── Init ───────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {

  // Probability slider
  const slider = document.getElementById('prob-slider');
  slider.addEventListener('input', () => {
    const v = parseInt(slider.value, 10);
    document.getElementById('prob-readout').textContent = `${v}%`;
    document.getElementById('prob-hint').textContent = probHint(v);
    updateSliderTrack(v);
  });

  // Category chips
  document.querySelectorAll('.cat-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const already = chip.classList.contains('selected');
      document.querySelectorAll('.cat-chip').forEach(c => c.classList.remove('selected'));
      if (!already) {
        chip.classList.add('selected');
        document.getElementById('selected-category').value = chip.dataset.cat;
      } else {
        document.getElementById('selected-category').value = '';
      }
    });
  });

  // New prediction button
  document.getElementById('new-prediction-btn').addEventListener('click', openModal);

  // Modal close
  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-overlay').addEventListener('click', e => {
    if (e.target === document.getElementById('modal-overlay')) closeModal();
  });

  // Detail close
  document.getElementById('detail-close').addEventListener('click', closeDetail);
  document.getElementById('detail-overlay').addEventListener('click', e => {
    if (e.target === document.getElementById('detail-overlay')) closeDetail();
  });

  // Delete
  document.getElementById('delete-btn').addEventListener('click', deletePrediction);

  // Filter tabs
  document.querySelectorAll('.filter-tab').forEach(btn => {
    btn.addEventListener('click', () => setFilter(btn.dataset.filter));
  });

  // Keyboard shortcut: n → new prediction
  document.addEventListener('keydown', e => {
    if (e.key === 'n' && !e.ctrlKey && !e.metaKey && !e.altKey) {
      const active = document.activeElement;
      const isInput = active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.tagName === 'SELECT');
      if (!isInput) openModal();
    }
    if (e.key === 'Escape') {
      closeModal();
      closeDetail();
    }
  });

  // Form submission
  document.getElementById('prediction-form').addEventListener('submit', async e => {
    e.preventDefault();
    const claim = document.getElementById('claim-input').value.trim();
    const prob = parseInt(document.getElementById('prob-slider').value, 10);
    const resolveBy = document.getElementById('resolve-by').value;
    const category = document.getElementById('selected-category').value;

    let valid = true;

    const claimErr = document.getElementById('claim-error');
    if (!claim) {
      claimErr.textContent = 'Please describe your prediction.';
      claimErr.classList.remove('hidden');
      valid = false;
    } else {
      claimErr.classList.add('hidden');
    }

    const dateErr = document.getElementById('date-error');
    if (!resolveBy) {
      dateErr.textContent = 'Please pick a resolve-by date.';
      dateErr.classList.remove('hidden');
      valid = false;
    } else if (resolveBy < isoToday()) {
      dateErr.textContent = 'Resolve date must be in the future.';
      dateErr.classList.remove('hidden');
      valid = false;
    } else {
      dateErr.classList.add('hidden');
    }

    if (!valid) return;

    const btn = document.getElementById('submit-btn');
    btn.disabled = true;
    btn.textContent = 'Saving…';

    const submitErr = document.getElementById('submit-error');

    try {
      await apiFetch('/predictions', {
        method: 'POST',
        body: JSON.stringify({
          claim,
          probability: prob,       // send 0-100; backend accepts both
          resolve_by: resolveBy,
          category: category || null,
        }),
      });
      closeModal();
      await refreshData();
    } catch (err) {
      submitErr.textContent = `Couldn't save — ${err.message}`;
      submitErr.classList.remove('hidden');
    } finally {
      btn.disabled = false;
      btn.textContent = 'Log prediction';
    }
  });

  // Initial data load
  refreshData();
});
