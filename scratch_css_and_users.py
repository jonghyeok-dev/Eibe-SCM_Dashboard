import os
import re

# 1. Update style.css
css_path = r"c:\MyMain\Eibe\SCM-Dashboard\web\static\css\style.css"
with open(css_path, "r", encoding="utf-8") as f:
    css_content = f.read()

new_css = """
/* Modern Sidebar Toggle UX */
.sidebar-toggle-modern {
    position: absolute;
    top: 36px;
    right: -14px;
    width: 28px;
    height: 28px;
    background: var(--bg-card);
    border: 1px solid var(--border-default);
    border-radius: 50%;
    color: var(--text-muted);
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    z-index: 200;
    transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1), background 0.2s, color 0.2s;
}
.sidebar-toggle-modern:hover {
    background: var(--bg-secondary);
    color: var(--text-primary);
}
.app-sidebar.collapsed .sidebar-toggle-modern {
    transform: rotate(180deg);
}
/* Ensure sidebar is relative so absolute positioning works */
.app-sidebar {
    position: sticky;
    top: 0;
}
"""

if ".sidebar-toggle-modern" not in css_content:
    css_content += new_css

with open(css_path, "w", encoding="utf-8") as f:
    f.write(css_content)


# 2. Update users.html to act as an SPA
users_path = r"c:\MyMain\Eibe\SCM-Dashboard\web\users.html"
with open(users_path, "r", encoding="utf-8") as f:
    users_content = f.read()

spa_script = """
        // Settings SPA Router
        function routeSettings() {
            const hash = window.location.hash || '#template-header';
            const sections = ['#template-header', '#warehouse-header', '#product-header', '#user-header', '#snapshot-header', '#moq-header'];
            
            sections.forEach(sec => {
                const el = document.querySelector(sec);
                if (el) {
                    if (sec === hash) {
                        el.style.display = 'block';
                        // Update title dynamically to mimic new page
                        const titleMap = {
                            '#template-header': '데이터 양식',
                            '#warehouse-header': '창고 관리',
                            '#product-header': '품목 관리',
                            '#user-header': '사용자 관리',
                            '#snapshot-header': '백업/스냅샷',
                            '#moq-header': '이관 MOQ'
                        };
                        document.getElementById('main-page-title').textContent = titleMap[hash] || '설정';
                    } else {
                        el.style.display = 'none';
                    }
                }
            });
            
            // Highlight active link in sidebar
            document.querySelectorAll('.nav-sub a').forEach(a => {
                if (a.getAttribute('href').endsWith(hash)) {
                    a.style.color = 'var(--accent-main)';
                    a.style.fontWeight = '600';
                } else {
                    a.style.color = 'var(--text-secondary)';
                    a.style.fontWeight = 'normal';
                }
            });
        }
        
        window.addEventListener('hashchange', routeSettings);
        document.addEventListener('DOMContentLoaded', () => {
            Theme.init();
            routeSettings();
        });
"""

# Replace the DOMContentLoaded block in users.html
users_content = re.sub(r'document\.addEventListener\(\'DOMContentLoaded\', \(\) => \{\s*Theme\.init\(\);\s*\}\);', spa_script, users_content)

with open(users_path, "w", encoding="utf-8") as f:
    f.write(users_content)

print("CSS and Users SPA updated.")
