/**
 * RegChange AI — Frontend Application
 * Handles upload, processing, dashboard, and change exploration.
 */

const API = '/api/v1';

const CATEGORIES = {
    C01: 'Added Requirement', C02: 'Removed Requirement', C03: 'Modified Requirement',
    C04: 'Threshold / Limit', C05: 'Timeline Change', C06: 'Eligibility',
    C07: 'Compliance', C08: 'Reporting', C09: 'Documentation',
    C10: 'Penalty / Consequence', C11: 'Scope Change', C12: 'Definition',
    C13: 'Exception / Exemption', C14: 'Procedural', C15: 'Reference',
    C16: 'Clarification', C17: 'Editorial',
};

const IMPACT_COLORS = {
    CRITICAL: '#ef4444', HIGH: '#f97316', MEDIUM: '#eab308',
    LOW: '#22c55e', INFORMATIONAL: '#64748b',
};

const CATEGORY_COLORS = [
    '#3b82f6', '#8b5cf6', '#ec4899', '#f97316', '#eab308',
    '#22c55e', '#06b6d4', '#f43f5e', '#84cc16', '#a855f7',
    '#14b8a6', '#f59e0b', '#6366f1', '#10b981', '#e11d48',
    '#0ea5e9', '#64748b',
];

class RegChangeApp {
    constructor() {
        this.oldDocId = null;
        this.newDocId = null;
        this.comparisonId = null;
        this.changes = [];
        this.stats = {};
        this.pollInterval = null;

        this.initEventListeners();
        this.checkQueryParams();
    }

    async checkQueryParams() {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.has('comparison_id')) {
            this.comparisonId = urlParams.get('comparison_id');
            this.loadResults();
        } else {
            // Auto-load latest completed comparison if available
            try {
                const res = await fetch(`${API}/comparisons`);
                const data = await res.json();
                if (data.comparisons && data.comparisons.length > 0) {
                    const completed = data.comparisons.find(c => c.status === 'completed') || data.comparisons[0];
                    if (completed) {
                        this.comparisonId = completed.comparison_id;
                        this.loadResults();
                    }
                }
            } catch (e) {
                console.error('Failed to auto-load latest comparison:', e);
            }
        }
    }

    initEventListeners() {
        // File inputs
        document.getElementById('oldDocInput').addEventListener('change', (e) => this.handleFileSelect(e, 'old'));
        document.getElementById('newDocInput').addEventListener('change', (e) => this.handleFileSelect(e, 'new'));

        // Drag and drop
        ['oldDocZone', 'newDocZone'].forEach(id => {
            const zone = document.getElementById(id);
            const version = id === 'oldDocZone' ? 'old' : 'new';

            zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('dragover'); });
            zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
            zone.addEventListener('drop', (e) => {
                e.preventDefault();
                zone.classList.remove('dragover');
                if (e.dataTransfer.files.length) {
                    const input = document.getElementById(version === 'old' ? 'oldDocInput' : 'newDocInput');
                    input.files = e.dataTransfer.files;
                    this.handleFileSelect({ target: input }, version);
                }
            });
        });

        // Navigation
        document.querySelectorAll('.nav-btn[data-view]').forEach(btn => {
            btn.addEventListener('click', () => this.showView(btn.dataset.view));
        });

        // Keyboard
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.closeModal();
        });
    }

    async handleFileSelect(event, version) {
        const file = event.target.files[0];
        if (!file) return;

        const zone = document.getElementById(version === 'old' ? 'oldDocZone' : 'newDocZone');
        const fileLabel = document.getElementById(version === 'old' ? 'oldDocFile' : 'newDocFile');
        const status = document.getElementById('uploadStatus');

        status.textContent = `Uploading ${file.name}...`;

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch(`${API}/documents/upload?version=${version}`, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || 'Upload failed');
            }

            const data = await response.json();

            if (version === 'old') {
                this.oldDocId = data.document_id;
            } else {
                this.newDocId = data.document_id;
            }

            zone.classList.add('has-file');
            fileLabel.textContent = `✓ ${file.name} (${data.total_pages} pages, quality: ${(data.quality_score * 100).toFixed(0)}%)`;
            status.textContent = `${file.name} uploaded successfully`;

            // Enable compare button
            if (this.oldDocId && this.newDocId) {
                document.getElementById('compareBtn').disabled = false;
            }
        } catch (err) {
            status.textContent = `Error: ${err.message}`;
            zone.classList.remove('has-file');
        }
    }

    async startComparison() {
        if (!this.oldDocId || !this.newDocId) return;

        try {
            const response = await fetch(`${API}/comparisons`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    old_document_id: this.oldDocId,
                    new_document_id: this.newDocId,
                }),
            });

            const data = await response.json();
            this.comparisonId = data.comparison_id;

            this.showView('processing');
            this.startPolling();
        } catch (err) {
            document.getElementById('uploadStatus').textContent = `Error: ${err.message}`;
        }
    }

    startPolling() {
        this.pollInterval = setInterval(() => this.pollProgress(), 1500);
    }

    async pollProgress() {
        if (!this.comparisonId) return;

        try {
            const response = await fetch(`${API}/comparisons/${this.comparisonId}`);
            const data = await response.json();

            const pct = Math.round((data.progress || 0) * 100);
            document.getElementById('progressPercent').textContent = `${pct}%`;
            document.getElementById('progressBar').style.width = `${pct}%`;
            document.getElementById('progressStage').textContent = data.current_stage || 'Processing...';

            if (data.status === 'completed') {
                clearInterval(this.pollInterval);
                await this.loadResults();
            } else if (data.status === 'failed') {
                clearInterval(this.pollInterval);
                document.getElementById('progressStage').textContent = `Error: ${data.error_message || 'Analysis failed'}`;
            }
        } catch (err) {
            console.error('Poll error:', err);
        }
    }

    async loadResults() {
        try {
            // Load changes
            const changesRes = await fetch(`${API}/comparisons/${this.comparisonId}/changes`);
            const changesData = await changesRes.json();
            this.changes = changesData.changes || [];

            // Load statistics
            const statsRes = await fetch(`${API}/comparisons/${this.comparisonId}/statistics`);
            this.stats = await statsRes.json();

            // Show nav buttons
            document.querySelectorAll('.nav-btn[data-view="dashboard"], .nav-btn[data-view="explorer"]').forEach(b => b.style.display = '');

            // Populate category filter
            this.populateCategoryFilter();

            this.showView('dashboard');
        } catch (err) {
            console.error('Failed to load results:', err);
        }
    }

    showView(viewName) {
        // Hide all views
        document.querySelectorAll('[id^="view-"]').forEach(v => v.style.display = 'none');

        // Show target
        const target = document.getElementById(`view-${viewName}`);
        if (target) target.style.display = '';

        // Update nav
        document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        const navBtn = document.querySelector(`.nav-btn[data-view="${viewName}"]`);
        if (navBtn) navBtn.classList.add('active');

        // Render views
        if (viewName === 'dashboard') this.renderDashboard();
        if (viewName === 'explorer') this.renderChangeList(this.changes);
    }

    renderDashboard() {
        const s = this.stats;
        if (!s.total) return;

        document.getElementById('dashboardSubtitle').textContent =
            `${s.total} total changes detected • ${s.substantive || 0} substantive • ${s.editorial || 0} editorial • Avg confidence: ${((s.avg_confidence || 0) * 100).toFixed(0)}%`;

        // Stats grid
        document.getElementById('statsGrid').innerHTML = `
            <div class="stat-card total" onclick="app.filterByField('','')"><div class="stat-value">${s.total || 0}</div><div class="stat-label">Total Changes</div></div>
            <div class="stat-card substantive" onclick="app.filterByField('is_substantive','true')"><div class="stat-value">${s.substantive || 0}</div><div class="stat-label">Substantive</div></div>
            <div class="stat-card added" onclick="app.filterByField('change_type','ADDED')"><div class="stat-value">${s.added || 0}</div><div class="stat-label">Added</div></div>
            <div class="stat-card removed" onclick="app.filterByField('change_type','REMOVED')"><div class="stat-value">${s.removed || 0}</div><div class="stat-label">Removed</div></div>
            <div class="stat-card modified" onclick="app.filterByField('change_type','MODIFIED')"><div class="stat-value">${s.modified || 0}</div><div class="stat-label">Modified</div></div>
            <div class="stat-card editorial" onclick="app.filterByField('is_substantive','false')"><div class="stat-value">${s.editorial || 0}</div><div class="stat-label">Editorial</div></div>
            <div class="stat-card critical" onclick="app.filterByField('impact','CRITICAL')"><div class="stat-value">${s.critical || 0}</div><div class="stat-label">Critical</div></div>
            <div class="stat-card high" onclick="app.filterByField('impact','HIGH')"><div class="stat-value">${s.high || 0}</div><div class="stat-label">High Impact</div></div>
        `;

        // Category chart
        this.renderCategoryChart();

        // Heatmap
        this.renderHeatmap();
    }

    renderCategoryChart() {
        const dist = this.stats.category_distribution || {};
        const container = document.getElementById('categoryChart');
        if (!dist || Object.keys(dist).length === 0) {
            container.innerHTML = '<div class="empty-state">No category data</div>';
            return;
        }

        const maxVal = Math.max(...Object.values(dist), 1);
        let html = '';
        let colorIdx = 0;

        const sorted = Object.entries(dist).sort((a, b) => b[1] - a[1]);

        for (const [cat, count] of sorted) {
            const pct = (count / maxVal) * 100;
            const color = CATEGORY_COLORS[colorIdx % CATEGORY_COLORS.length];
            const label = CATEGORIES[cat] || cat;

            html += `
                <div class="bar-row" onclick="app.filterByField('category','${cat}')" style="cursor:pointer">
                    <div class="bar-label">${label}</div>
                    <div class="bar-track">
                        <div class="bar-fill" style="width:${pct}%; background:${color}">${count}</div>
                    </div>
                    <div class="bar-count">${count}</div>
                </div>
            `;
            colorIdx++;
        }

        container.innerHTML = html;
    }

    renderHeatmap() {
        const heatmap = this.stats.impact_heatmap || {};
        const container = document.getElementById('heatmapContainer');

        if (!heatmap || Object.keys(heatmap).length === 0) {
            container.innerHTML = '<div class="empty-state">No heatmap data</div>';
            return;
        }

        const impacts = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];
        const categories = Object.keys(heatmap);

        let html = '<table class="heatmap-table"><thead><tr><th></th>';
        impacts.forEach(i => html += `<th>${i}</th>`);
        html += '</tr></thead><tbody>';

        for (const cat of categories) {
            const label = CATEGORIES[cat] || cat;
            html += `<tr><td class="heatmap-cat">${label}</td>`;
            for (const imp of impacts) {
                const val = (heatmap[cat] || {})[imp] || 0;
                const cls = val > 0 ? imp.toLowerCase() : 'empty';
                html += `<td class="heatmap-cell ${cls}" onclick="app.filterByField('category','${cat}')">${val || '-'}</td>`;
            }
            html += '</tr>';
        }

        html += '</tbody></table>';
        container.innerHTML = html;
    }

    populateCategoryFilter() {
        const select = document.getElementById('filterCategory');
        select.innerHTML = '<option value="">All Categories</option>';
        const dist = this.stats.category_distribution || {};
        for (const [cat, count] of Object.entries(dist).sort((a, b) => b[1] - a[1])) {
            const label = CATEGORIES[cat] || cat;
            select.innerHTML += `<option value="${cat}">${label} (${count})</option>`;
        }
    }

    filterByField(field, value) {
        this.showView('explorer');
        if (field === 'category') document.getElementById('filterCategory').value = value;
        else if (field === 'impact') document.getElementById('filterImpact').value = value;
        else if (field === 'change_type') document.getElementById('filterType').value = value;
        else if (field === 'is_substantive') document.getElementById('filterSubstantive').value = value;
        this.filterChanges();
    }

    filterChanges() {
        const search = document.getElementById('searchInput').value.toLowerCase();
        const category = document.getElementById('filterCategory').value;
        const impact = document.getElementById('filterImpact').value;
        const type = document.getElementById('filterType').value;
        const substantive = document.getElementById('filterSubstantive').value;

        let filtered = this.changes;

        if (search) {
            filtered = filtered.filter(c =>
                (c.change_summary || '').toLowerCase().includes(search) ||
                (c.old_requirement || '').toLowerCase().includes(search) ||
                (c.new_requirement || '').toLowerCase().includes(search)
            );
        }
        if (category) filtered = filtered.filter(c => c.category === category);
        if (impact) filtered = filtered.filter(c => c.impact === impact);
        if (type) filtered = filtered.filter(c => c.change_type === type);
        if (substantive === 'true') filtered = filtered.filter(c => c.is_substantive);
        if (substantive === 'false') filtered = filtered.filter(c => !c.is_substantive);

        this.renderChangeList(filtered);
    }

    renderChangeList(changes) {
        const container = document.getElementById('changeList');

        if (!changes.length) {
            container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">🔍</div><p>No changes match your filters</p></div>`;
            return;
        }

        container.innerHTML = changes.map(c => {
            const conf = c.confidence_overall || (c.confidence_breakdown || {}).overall || 0;
            const confPct = Math.round(conf * 100);
            const confClass = confPct >= 80 ? 'high' : confPct >= 50 ? 'medium' : 'low';
            const catLabel = CATEGORIES[c.category] || c.category;

            return `
                <div class="change-card" onclick="app.showChangeDetail('${c.change_id}')">
                    <div class="change-id">${c.change_id}</div>
                    <div class="change-content">
                        <div class="change-summary">${this.escapeHtml(c.change_summary || 'Change detected')}</div>
                        <div class="change-meta">
                            <span class="badge badge-type-${c.change_type}">${c.change_type}</span>
                            <span class="badge badge-impact-${c.impact}">${c.impact}</span>
                            <span class="badge badge-category">${catLabel}</span>
                            ${c.is_substantive
                                ? '<span class="badge badge-substantive">Substantive</span>'
                                : '<span class="badge badge-editorial">Editorial</span>'
                            }
                            <div class="confidence-bar">
                                <div class="confidence-track"><div class="confidence-fill ${confClass}" style="width:${confPct}%"></div></div>
                                <span class="confidence-text">${confPct}%</span>
                            </div>
                        </div>
                    </div>
                    <div style="text-align:right">
                        ${c.old_reference ? `<div style="font-size:0.72rem;color:var(--text-muted)">p.${(c.old_reference.page||'')} → p.${(c.new_reference||{}).page||''}</div>` : ''}
                    </div>
                </div>
            `;
        }).join('');
    }

    async showChangeDetail(changeId) {
        const change = this.changes.find(c => c.change_id === changeId);
        if (!change) return;

        const modal = document.getElementById('changeModal');
        const content = document.getElementById('modalContent');

        const oldRef = change.old_reference || {};
        const newRef = change.new_reference || {};
        const conf = change.confidence_overall || (change.confidence_breakdown || {}).overall || 0;
        const catLabel = CATEGORIES[change.category] || change.category;

        // Build diff HTML
        let oldHtml = this.escapeHtml(change.old_requirement || '(New content — no old version)');
        let newHtml = this.escapeHtml(change.new_requirement || '(Removed — no new version)');

        if (change.diff_highlights && change.diff_highlights.length > 0) {
            const dh = change.diff_highlights[0];
            if (dh.old_html) oldHtml = dh.old_html;
            if (dh.new_html) newHtml = dh.new_html;
        }

        // Numerical changes
        let numHtml = '';
        const numChanges = typeof change.numerical_changes === 'string'
            ? JSON.parse(change.numerical_changes || '[]')
            : (change.numerical_changes || []);

        if (numChanges.length > 0) {
            numHtml = `<div class="numerical-changes">
                <h4 style="margin-bottom:12px; font-size:0.85rem; color:var(--change-modified)">📊 Numerical Changes Detected</h4>
                ${numChanges.map(nc => {
                    const arrow = nc.direction === 'INCREASE' ? '↑' : nc.direction === 'DECREASE' ? '↓' : '↔';
                    const arrowClass = nc.direction === 'INCREASE' ? 'increase' : 'decrease';
                    return `<div class="numerical-change-item">
                        <span class="num-arrow ${arrowClass}">${arrow}</span>
                        <span><strong>${nc.old_value}</strong> → <strong>${nc.new_value}</strong></span>
                        ${nc.magnitude_percent ? `<span style="color:var(--text-muted); font-size:0.8rem">(${nc.magnitude_percent.toFixed(0)}% ${nc.direction.toLowerCase()})</span>` : ''}
                    </div>`;
                }).join('')}
            </div>`;
        }

        // Obligation change
        let obligationHtml = '';
        const obligation = typeof change.obligation_change === 'string'
            ? JSON.parse(change.obligation_change || '{}')
            : (change.obligation_change || {});

        if (obligation.direction && obligation.direction !== 'UNCHANGED') {
            const dirColor = obligation.direction === 'STRENGTHENED' ? 'var(--impact-high)' : 'var(--change-added)';
            obligationHtml = `<div class="ai-interpretation" style="border-color:${dirColor}30; background:${dirColor}08">
                <div class="ai-interpretation-header" style="color:${dirColor}">⚖️ Obligation Change: ${obligation.direction}</div>
                <div class="ai-interpretation-text">${this.escapeHtml(obligation.explanation || '')}</div>
            </div>`;
        }

        // LLM explanation
        let llmHtml = '';
        if (change.llm_explanation) {
            llmHtml = `<div class="ai-interpretation">
                <div class="ai-interpretation-header">🤖 AI Interpretation</div>
                <div class="ai-interpretation-text">${this.escapeHtml(change.llm_explanation)}</div>
            </div>`;
        } else if (change.impact_explanation) {
            llmHtml = `<div class="ai-interpretation">
                <div class="ai-interpretation-header">📋 Impact Analysis</div>
                <div class="ai-interpretation-text">${this.escapeHtml(change.impact_explanation)}</div>
            </div>`;
        }

        content.innerHTML = `
            <div class="modal-header">
                <div style="display:flex; align-items:center; gap:16px; flex-wrap:wrap">
                    <span class="change-id" style="font-size:0.9rem">${change.change_id}</span>
                    <span class="badge badge-impact-${change.impact}" style="font-size:0.8rem">${change.impact}</span>
                    <span class="badge badge-type-${change.change_type}">${change.change_type}</span>
                    <span class="badge badge-category">${catLabel}</span>
                    ${change.is_substantive ? '<span class="badge badge-substantive">Substantive</span>' : '<span class="badge badge-editorial">Editorial</span>'}
                    <div class="confidence-bar">
                        <div class="confidence-track" style="width:80px"><div class="confidence-fill ${conf >= 0.8 ? 'high' : conf >= 0.5 ? 'medium' : 'low'}" style="width:${Math.round(conf*100)}%"></div></div>
                        <span class="confidence-text">${Math.round(conf*100)}% confidence</span>
                    </div>
                </div>
                <button class="modal-close" onclick="app.closeModal()">×</button>
            </div>
            <div class="modal-body">
                <p style="color:var(--text-secondary); margin-bottom:20px; font-size:0.95rem; line-height:1.6">${this.escapeHtml(change.change_summary || '')}</p>

                <div class="side-by-side">
                    <div class="side-panel old">
                        <div class="side-panel-header">
                            <span class="side-panel-title">Old Version</span>
                            <span class="side-panel-ref">Page ${oldRef.page || '?'} • ${oldRef.section || oldRef.clause || 'N/A'}</span>
                        </div>
                        <div class="side-panel-text">${oldHtml}</div>
                    </div>
                    <div class="side-panel new">
                        <div class="side-panel-header">
                            <span class="side-panel-title">New Version</span>
                            <span class="side-panel-ref">Page ${newRef.page || '?'} • ${newRef.section || newRef.clause || 'N/A'}</span>
                        </div>
                        <div class="side-panel-text">${newHtml}</div>
                    </div>
                </div>

                ${numHtml}
                ${obligationHtml}
                ${llmHtml}

                <div class="review-actions">
                    <button class="btn btn-accept btn-sm" onclick="app.reviewChange('${change.change_id}', 'ACCEPTED')">✓ Accept</button>
                    <button class="btn btn-reject btn-sm" onclick="app.reviewChange('${change.change_id}', 'REJECTED')">✗ Reject</button>
                    <button class="btn btn-ghost btn-sm" onclick="app.reviewChange('${change.change_id}', 'EDITED')">✏️ Mark Editorial</button>
                    <button class="btn btn-ghost btn-sm" onclick="app.reviewChange('${change.change_id}', 'FLAGGED')">🚩 Flag for Review</button>
                </div>
            </div>
        `;

        modal.style.display = 'flex';
    }

    closeModal() {
        document.getElementById('changeModal').style.display = 'none';
    }

    async reviewChange(changeId, status) {
        try {
            await fetch(`${API}/changes/${changeId}/review`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status, comment: '' }),
            });

            // Update local state
            const change = this.changes.find(c => c.change_id === changeId);
            if (change) change.review_status = status;

            this.closeModal();
            this.filterChanges();
        } catch (err) {
            console.error('Review failed:', err);
        }
    }

    async exportExcel() {
        if (!this.comparisonId) {
            try {
                const res = await fetch(`${API}/comparisons`);
                const data = await res.json();
                if (data.comparisons && data.comparisons.length > 0) {
                    const completed = data.comparisons.find(c => c.status === 'completed') || data.comparisons[0];
                    if (completed) this.comparisonId = completed.comparison_id;
                }
            } catch (e) {}
        }

        if (!this.comparisonId) {
            alert('No completed comparison found to export. Please analyze a circular first.');
            return;
        }

        const downloadUrl = `${API}/comparisons/${this.comparisonId}/export/excel`;
        
        // Permanent fix: Direct anchor click triggers native browser file download
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.setAttribute('download', `RegChange_AI_${this.comparisonId}_Changes.xlsx`);
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        
        setTimeout(() => {
            if (document.body.contains(link)) {
                document.body.removeChild(link);
            }
        }, 1000);
    }

    exportJSON() {
        const data = {
            comparison_id: this.comparisonId,
            statistics: this.stats,
            changes: this.changes,
            exported_at: new Date().toISOString(),
        };
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `regchange_analysis_${this.comparisonId || 'export'}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize
const app = new RegChangeApp();
