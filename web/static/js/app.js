/**
 * SCM ERP Dashboard - 메인 JavaScript 모듈
 */

const API = {
    BASE: '',
    async get(endpoint) {
        try {
            const res = await fetch(`${this.BASE}${endpoint}`);
            if (!res.ok) throw new Error(`API Error: ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error(`GET ${endpoint} failed:`, err);
            throw err;
        }
    },
    async post(endpoint, data) {
        try {
            const res = await fetch(`${this.BASE}${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            if (!res.ok) throw new Error(`API Error: ${res.status}`);
            return await res.json();
        } catch (err) {
            console.error(`POST ${endpoint} failed:`, err);
            throw err;
        }
    }
};

const Format = {
    number(val) { return val == null || isNaN(val) ? '0' : Number(val).toLocaleString('ko-KR'); },
    currency(val) { return val == null || isNaN(val) ? '₩0' : '₩' + Number(val).toLocaleString('ko-KR'); }
};

const Theme = {
    init() {
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
