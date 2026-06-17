/**
 * SCM ERP Dashboard - 메인 JavaScript 모듈
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
                Auth.showLoginModal();
                throw new Error('Unauthorized');
            }
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || `API Error: ${res.status}`);
            }
            return await res.json();
        } catch (error) {
            Toast.show(error.message, 'error');
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
    }
};

const Auth = {
    init() {
        this.updateSidebarUI();
        if(!this.isLoggedIn() && window.location.pathname !== '/login') {
            // Optional: require login
        }
    },
    isLoggedIn() { return !!API.getToken(); },
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
            await this.updateSidebarUI();
            document.getElementById('login-modal').style.display = 'none';
            Toast.show('로그인 성공', 'success');
            window.location.reload();
        } catch (err) {
            Toast.show('아이디 또는 비밀번호가 틀렸습니다.', 'error');
        }
    },
    logout() {
        localStorage.removeItem('scm_token');
        this.updateSidebarUI();
        Toast.show('로그아웃 되었습니다.', 'info');
        window.location.reload();
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
                avatarEl.style.cursor = 'pointer';
                avatarEl.onclick = () => { if(confirm('로그아웃 하시겠습니까?')) Auth.logout(); };
            } catch(e) {}
        } else {
            nameEl.textContent = '로그인 필요';
            roleEl.textContent = '';
            avatarEl.textContent = '?';
            avatarEl.style.cursor = 'pointer';
            avatarEl.onclick = () => this.showLoginModal();
        }
    },
    showLoginModal() {
        let modal = document.getElementById('login-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'login-modal';
            modal.innerHTML = `
                <div style="position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(0,0,0,0.5); z-index:9999; display:flex; align-items:center; justify-content:center;">
                    <div class="card" style="width: 350px; padding: 20px;">
                        <h2 style="margin-bottom: 20px;">시스템 로그인</h2>
                        <input type="text" id="login-id" class="form-input" placeholder="아이디" style="margin-bottom: 10px;">
                        <input type="password" id="login-pw" class="form-input" placeholder="비밀번호" style="margin-bottom: 20px;">
                        <div style="display:flex; gap:10px;">
                            <button class="btn btn--primary" style="flex:1;" onclick="Auth.login(document.getElementById('login-id').value, document.getElementById('login-pw').value)">로그인</button>
                            <button class="btn btn--secondary" onclick="document.getElementById('login-modal').style.display='none'">취소</button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }
        modal.style.display = 'block';
    }
};

const Format = {
    number(val) { return val == null || isNaN(val) ? '0' : Number(val).toLocaleString('ko-KR'); },
    currency(val) { return val == null || isNaN(val) ? '₩0' : '₩' + Number(val).toLocaleString('ko-KR'); }
};

const Theme = {
    init() {
        Auth.init();
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);
        this.updateToggleButton(savedTheme);
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
                instance.options.scales.x.grid.color = isDark ? 'rgba(148, 163, 184, 0.06)' : '#e2e8f0';
                instance.options.scales.y.grid.color = isDark ? 'rgba(148, 163, 184, 0.06)' : '#e2e8f0';
                instance.options.plugins.tooltip.backgroundColor = isDark ? 'rgba(10, 14, 26, 0.9)' : 'rgba(255, 255, 255, 0.9)';
                instance.options.plugins.tooltip.titleColor = isDark ? '#fff' : '#0f172a';
                instance.options.plugins.tooltip.bodyColor = isDark ? '#fff' : '#0f172a';
                instance.update();
            });
        }
    },
    updateToggleButton(theme) {
        const btn = document.getElementById('theme-toggle');
        if (btn) btn.textContent = theme === 'dark' ? 'Light Mode' : 'Dark Mode';
    }
};

const ChartDefaults = {
    init() {
        if (typeof Chart === 'undefined') return;
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        
        Chart.defaults.font.family = "'Inter', sans-serif";
        Chart.defaults.color = '#94a3b8';
        Chart.defaults.elements.line.tension = 0.35;
        Chart.defaults.scale.grid = {
            color: isDark ? 'rgba(148, 163, 184, 0.06)' : '#e2e8f0',
            drawBorder: false,
        };
        Chart.defaults.plugins.tooltip.backgroundColor = isDark ? 'rgba(10, 14, 26, 0.9)' : 'rgba(255, 255, 255, 0.9)';
        Chart.defaults.plugins.tooltip.titleColor = isDark ? '#fff' : '#0f172a';
        Chart.defaults.plugins.tooltip.bodyColor = isDark ? '#fff' : '#0f172a';
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
                        borderColor: '#29AD39',
                        backgroundColor: 'rgba(41, 173, 57, 0.1)',
                        fill: true, borderWidth: 2,
                    },
                    {
                        label: 'B선 - 실제 재고 소멸',
                        data: depletionData,
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.05)',
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

const Dashboard = {
    async loadKPIs() {
        try {
            const [products, inventory, ffcs] = await Promise.all([
                API.get('/api/products'), API.get('/api/inventory'), API.get('/api/ffc')
            ]);
            const totalStock = inventory.reduce((sum, inv) => sum + (inv.current_can_qty || 0), 0);
            
            document.getElementById('kpi-total-stock').textContent = Format.number(totalStock);
            document.getElementById('ffc-count-badge').textContent = `${ffcs.length}개 거점`;
            Toast.show('대시보드 데이터 로드 완료');
        } catch (err) {
            Toast.show('데이터 로드 실패');
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    Theme.init();
    Toast.init();
    ChartDefaults.init();
    if (document.getElementById('dashboard-page')) { Dashboard.loadKPIs(); }
});
