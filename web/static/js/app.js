/**
 * EIBE SCM - 메인 JavaScript 모듈
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
            if (error.message !== 'Unauthorized') Toast.show(error.message, 'error');
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
            return;
        }
        if (this.isLoggedIn() && isLoginPage) {
            window.location.href = '/';
            return;
        }
        this.updateSidebarUI();
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
            } catch(e) {}
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
    init() {
        Auth.init();
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
                    instance.options.plugins.tooltip.backgroundColor = isDark ? 'rgba(30, 30, 38, 0.95)' : 'rgba(255, 255, 255, 0.95)';
                    instance.options.plugins.tooltip.titleColor = isDark ? '#ececf1' : '#191f28';
                    instance.options.plugins.tooltip.bodyColor = isDark ? '#ececf1' : '#191f28';
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
        Chart.defaults.color = isDark ? '#a1a1aa' : '#8b95a1';
        Chart.defaults.elements.line.tension = 0.35;
        Chart.defaults.scale.grid = {
            color: isDark ? 'rgba(100, 100, 100, 0.15)' : '#e5e8eb',
            drawBorder: false,
        };
        Chart.defaults.plugins.tooltip.backgroundColor = isDark ? 'rgba(30, 30, 38, 0.95)' : 'rgba(255, 255, 255, 0.95)';
        Chart.defaults.plugins.tooltip.titleColor = isDark ? '#ececf1' : '#191f28';
        Chart.defaults.plugins.tooltip.bodyColor = isDark ? '#ececf1' : '#191f28';
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
    show(message) {
        if (!this.container) this.init();
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = message;
        this.container.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
};

/** 엑셀 양식 다운로드 헬퍼 */
function downloadTemplate(type) {
    const url = type === 'all' ? '/api/excel/template' : `/api/excel/template/${type}`;
    window.location.href = url;
}

/** 접기/열기 토글 */
function toggleCollapsible(headerId) {
    const header = document.getElementById(headerId);
    if (!header) return;
    const body = header.nextElementSibling;
    if (!body) return;
    header.classList.toggle('collapsed');
    body.classList.toggle('hidden');
}

const Dashboard = {
    async loadKPIs() {
        try {
            const [products, inventory, ffcs] = await Promise.all([
                API.get('/api/products'), API.get('/api/inventory'), API.get('/api/ffc')
            ]);
            const totalStock = inventory.reduce((sum, inv) => sum + (inv.current_can_qty || 0), 0);
            
            document.getElementById('kpi-total-stock').textContent = Format.number(totalStock);
            document.getElementById('ffc-count-badge').textContent = `${ffcs.length}`;
        } catch (err) {
            // silent
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    Theme.init();
    Toast.init();
    ChartDefaults.init();
    if (document.getElementById('dashboard-page')) { Dashboard.loadKPIs(); }
});
