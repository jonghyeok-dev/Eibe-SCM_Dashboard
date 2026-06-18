/**
 * EIBE SCM - Main JavaScript Module
 */

const API = {
    BASE: '',
    getToken() { return localStorage.getItem('scm_token'); },
    async request(endpoint, options = {}) {
        const token = this.getToken();
        const headers = { ...options.headers };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        try {
            const res = await fetch(`${this.BASE}${endpoint}`, { ...options, headers });
            if (res.status === 401) {
                Auth.redirectToLogin();
                throw new Error('Unauthorized');
            }
            if (res.status === 409) {
                const err = await res.json().catch(() => ({}));
                Toast.show(err.detail || '다른 사용자가 이미 수정했습니다. 새로고침 후 다시 시도하세요.', 'error');
                throw new Error(err.detail || 'Conflict');
            }
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `API Error: ${res.status}`);
            }
            return await res.json();
        } catch (error) {
            if (error.message !== 'Unauthorized' && error.message !== 'Conflict') {
                Toast.show(error.message, 'error');
            }
            throw error;
        }
    },
    async get(endpoint) { return this.request(endpoint); },
    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    },
    async put(endpoint, data) {
        return this.request(endpoint, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
    },
    async postFormData(endpoint, formData) {
        const token = this.getToken();
        const headers = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;
        try {
            const res = await fetch(`${this.BASE}${endpoint}`, {
                method: 'POST',
                headers,
                body: formData
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `Upload Error: ${res.status}`);
            }
            return await res.json();
        } catch (error) {
            Toast.show(error.message, 'error');
            throw error;
        }
    },
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }
};

const Auth = {
    init() {
        const isLoginPage = window.location.pathname === '/login';
        if (!this.isLoggedIn() && !isLoginPage) {
            this.redirectToLogin();
            return false;
        }
        if (this.isLoggedIn() && isLoginPage) {
            window.location.href = '/';
            return false;
        }
        this.updateSidebarUI();
        return true;
    },
    isLoggedIn() { return !!API.getToken(); },
    redirectToLogin() {
        localStorage.removeItem('scm_token');
        if (window.location.pathname !== '/login') {
            window.location.href = '/login';
        }
    },
    async login(username, password) {
        const formData = new URLSearchParams();
        formData.append('username', username);
        formData.append('password', password);
        try {
            const res = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: formData
            });
            if (!res.ok) throw new Error('로그인 실패');
            const data = await res.json();
            localStorage.setItem('scm_token', data.access_token);
            window.location.href = '/';
        } catch (err) {
            throw err;
        }
    },
    logout() {
        localStorage.removeItem('scm_token');
        window.location.href = '/login';
    },
    async updateSidebarUI() {
        const nameEl = document.getElementById('sidebar-user-name');
        const roleEl = document.getElementById('sidebar-user-role');
        const avatarEl = document.getElementById('sidebar-user-avatar');
        if (!nameEl) return;
        
        if (this.isLoggedIn()) {
            try {
                const user = await API.get('/api/auth/me');
                nameEl.textContent = user.name;
                roleEl.textContent = user.role;
                avatarEl.textContent = user.name.charAt(0);
                window._currentUserRole = user.role;
            } catch(e) {
                // Token might be expired - silently ignore
            }
        } else {
            nameEl.textContent = 'Guest';
            roleEl.textContent = '';
            avatarEl.textContent = '?';
        }
    }
};

const Format = {
    number(val) { return val == null || isNaN(val) ? '0' : Number(val).toLocaleString('ko-KR'); },
    currency(val) { return val == null || isNaN(val) ? '₩0' : '₩' + Number(val).toLocaleString('ko-KR'); },
    percent(val) { return val == null || isNaN(val) ? '0%' : Number(val).toFixed(1) + '%'; }
};

const Theme = {
    _initialized: false,
    init() {
        if (this._initialized) return;
        this._initialized = true;
        
        const authOk = Auth.init();
        if (authOk === false) return; // redirect happening
        
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);
        this.updateToggleButton(savedTheme);
        Sidebar.init();
    },
    toggle() {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
        this.updateToggleButton(next);
        
        if (typeof Chart !== 'undefined') {
            Chart.helpers.each(Chart.instances, function(instance) {
                const isDark = next === 'dark';
                if (instance.options.scales?.x?.grid) instance.options.scales.x.grid.color = isDark ? 'rgba(100, 100, 100, 0.15)' : '#e5e8eb';
                if (instance.options.scales?.y?.grid) instance.options.scales.y.grid.color = isDark ? 'rgba(100, 100, 100, 0.15)' : '#e5e8eb';
                if (instance.options.plugins?.tooltip) {
                    instance.options.plugins.tooltip.backgroundColor = isDark ? 'rgba(26, 26, 26, 0.95)' : 'rgba(255, 255, 255, 0.95)';
                    instance.options.plugins.tooltip.titleColor = isDark ? '#e8e8e8' : '#191f28';
                    instance.options.plugins.tooltip.bodyColor = isDark ? '#e8e8e8' : '#191f28';
                }
                instance.update();
            });
        }
    },
    updateToggleButton(theme) {
        const btn = document.getElementById('theme-toggle');
        if (btn) {
            const icon = btn.querySelector('.toggle-icon');
            const text = btn.querySelector('.theme-toggle-text');
            if (icon) icon.textContent = theme === 'dark' ? '☀' : '☾';
            if (text) text.textContent = theme === 'dark' ? 'Light' : 'Dark';
        }
    }
};

const Sidebar = {
    init() {
        const sidebar = document.querySelector('.app-sidebar');
        if (!sidebar) return;
        const collapsed = localStorage.getItem('sidebar_collapsed') === 'true';
        if (collapsed) sidebar.classList.add('collapsed');
    },
    toggle() {
        const sidebar = document.querySelector('.app-sidebar');
        if (!sidebar) return;
        sidebar.classList.toggle('collapsed');
        localStorage.setItem('sidebar_collapsed', sidebar.classList.contains('collapsed'));
    }
};

const ChartDefaults = {
    init() {
        if (typeof Chart === 'undefined') return;
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        
        Chart.defaults.font.family = "'Inter', sans-serif";
        Chart.defaults.color = isDark ? '#a0a0a0' : '#8b95a1';
        Chart.defaults.elements.line.tension = 0.35;
        Chart.defaults.scale.grid = {
            color: isDark ? 'rgba(100, 100, 100, 0.15)' : '#e5e8eb',
            drawBorder: false,
        };
        Chart.defaults.plugins.tooltip.backgroundColor = isDark ? 'rgba(26, 26, 26, 0.95)' : 'rgba(255, 255, 255, 0.95)';
        Chart.defaults.plugins.tooltip.titleColor = isDark ? '#e8e8e8' : '#191f28';
        Chart.defaults.plugins.tooltip.bodyColor = isDark ? '#e8e8e8' : '#191f28';
    },

    createDualTrackChart(canvasId, labels, demandData, depletionData) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;

        return new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'A선 - 순수 수요 예측',
                        data: demandData,
                        borderColor: '#1b64da',
                        backgroundColor: 'rgba(27, 100, 218, 0.06)',
                        fill: true, borderWidth: 2,
                    },
                    {
                        label: 'B선 - 실제 재고 소멸',
                        data: depletionData,
                        borderColor: '#e53535',
                        backgroundColor: 'rgba(229, 53, 53, 0.04)',
                        fill: true, borderWidth: 2, borderDash: [6, 3],
                    },
                ],
            },
            options: { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false } }
        });
    }
};

const Toast = {
    container: null,
    init() {
        this.container = document.getElementById('toast-container');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'toast-container';
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        }
    },
    show(message, type) {
        if (!this.container) this.init();
        const toast = document.createElement('div');
        toast.className = 'toast';
        if (type === 'error') toast.className += ' toast--error';
        else if (type === 'success') toast.className += ' toast--success';
        toast.textContent = message;
        this.container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(12px)';
            toast.style.transition = 'all 0.2s ease';
            setTimeout(() => toast.remove(), 200);
        }, 3000);
    }
};

/** Excel template download helper */
function downloadTemplate(type) {
    const url = type === 'all' ? '/api/excel/template' : `/api/excel/template/${type}`;
    window.location.href = url;
}

/** Collapsible toggle */
function toggleCollapsible(headerId) {
    const header = document.getElementById(headerId);
    if (!header) return;
    const body = header.nextElementSibling;
    if (!body) return;
    header.classList.toggle('collapsed');
    body.classList.toggle('hidden');
}

const Dashboard = {
    dualTrackChart: null,
    
    async loadKPIs() {
        try {
            const [products, inventory, ffcs] = await Promise.all([
                API.get('/api/products'), API.get('/api/inventory'), API.get('/api/ffc')
            ]);
            const totalStock = inventory.reduce((sum, inv) => sum + (inv.current_can_qty || 0), 0);
            
            const el = (id) => document.getElementById(id);
            if (el('kpi-total-stock')) el('kpi-total-stock').textContent = Format.number(totalStock);
            if (el('ffc-count-badge')) el('ffc-count-badge').textContent = `${ffcs.length}`;
        } catch (err) {
            // API not available yet, keep sample data
        }
    },

    async loadSimulation(weightFactor) {
        try {
            const data = await API.get(`/api/order-plan/simulation?weight_factor=${weightFactor}`);
            if (!data || !data.length) return;

            // Update chart with real simulation data
            const canvas = document.getElementById('dual-track-chart');
            if (!canvas || typeof Chart === 'undefined') return;

            // Aggregate all products
            const labels = [];
            const demandData = [];
            const depletionData = [];
            
            const weeks = data[0].simulation.length;
            for (let i = 0; i < weeks; i++) {
                labels.push(`W${i + 1}`);
                let totalDemand = 0;
                let totalEnding = 0;
                data.forEach(d => {
                    if (d.simulation[i]) {
                        totalDemand += d.simulation[i].weekly_demand;
                        totalEnding += d.simulation[i].ending_stock;
                    }
                });
                demandData.push(Math.round(totalDemand));
                depletionData.push(Math.round(totalEnding));
            }

            if (this.dualTrackChart) {
                this.dualTrackChart.destroy();
                this.dualTrackChart = null;
            }
            ChartDefaults.init();
            this.dualTrackChart = ChartDefaults.createDualTrackChart('dual-track-chart', labels, 
                demandData.map((d, i) => depletionData[0] - demandData.slice(0, i+1).reduce((a,b)=>a+b, 0) + depletionData[0]),
                depletionData
            );
        } catch(e) {
            // Keep sample data if API fails
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    Theme.init();
    Toast.init();
    if (typeof Chart !== 'undefined') ChartDefaults.init();
    if (document.getElementById('dashboard-page')) { Dashboard.loadKPIs(); }
});
