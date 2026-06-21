import os
import re

filepath = r"C:\Users\parkj\.gemini\antigravity\worktrees\SCM-dashboad\refactor-add-error-handling\web\templates\users.html"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all section-gap classes with settings-section
content = content.replace('section class="card section-gap"', 'section class="card settings-section"')
content = content.replace('section class="content-grid content-grid--two section-gap"', 'section class="content-grid content-grid--two settings-section"')

# Create the layout wrapper
sidebar_html = """
<div class="settings-layout" style="display: flex; gap: var(--space-xl); align-items: flex-start;">
    <!-- Settings Navigation -->
    <div class="card settings-sidebar" style="width: 240px; flex-shrink: 0; position: sticky; top: 20px;">
        <div class="card-header"><h3 class="card-title">운영 메뉴</h3></div>
        <div class="card-body card-body--no-pad">
            <ul class="settings-nav-list" style="list-style: none; padding: 0; margin: 0;">
                <li class="settings-nav-item active" onclick="AdminPage.showTab('template', this)" style="padding: 12px 16px; cursor: pointer; border-bottom: 1px solid var(--border-default); font-weight: 500;">데이터 양식 관리</li>
                <li class="settings-nav-item" onclick="AdminPage.showTab('warehouse', this)" style="padding: 12px 16px; cursor: pointer; border-bottom: 1px solid var(--border-default);">창고 관리</li>
                <li class="settings-nav-item" onclick="AdminPage.showTab('product', this)" style="padding: 12px 16px; cursor: pointer; border-bottom: 1px solid var(--border-default);">품목 관리</li>
                <li class="settings-nav-item" onclick="AdminPage.showTab('user', this)" style="padding: 12px 16px; cursor: pointer; border-bottom: 1px solid var(--border-default);">사용자 관리</li>
                <li class="settings-nav-item" onclick="AdminPage.showTab('snapshot', this)" style="padding: 12px 16px; cursor: pointer; border-bottom: 1px solid var(--border-default);">백업/스냅샷</li>
                <li class="settings-nav-item" onclick="AdminPage.showTab('moq', this)" style="padding: 12px 16px; cursor: pointer;">이관 MOQ 설정</li>
            </ul>
        </div>
    </div>
    
    <!-- Settings Content Wrapper -->
    <div class="settings-content" style="flex: 1; min-width: 0;">
"""

# Find where to inject the wrapper: after the page-header div
page_header_end = content.find('</div>\n            </div>\n\n            <!-- 데이터 양식 관리 -->')
if page_header_end == -1:
    page_header_end = content.find('</div>\n            </div>') + 20

content = content[:page_header_end] + "\n" + sidebar_html + content[page_header_end:]

# Close the wrappers before {% endblock %}
content = content.replace('{% endblock %}\n\n{% block scripts %}', '    </div>\n</div>\n{% endblock %}\n\n{% block scripts %}')

# Add CSS and JS for tabs
js_addition = """
            showTab(tabId, el) {
                // Update active nav
                document.querySelectorAll('.settings-nav-item').forEach(li => {
                    li.classList.remove('active');
                    li.style.background = 'transparent';
                    li.style.color = 'var(--text-main)';
                    li.style.fontWeight = 'normal';
                });
                el.classList.add('active');
                el.style.background = 'rgba(27, 100, 218, 0.08)';
                el.style.color = 'var(--accent-main)';
                el.style.fontWeight = '600';

                // Update content sections
                const sections = document.querySelectorAll('.settings-section');
                sections.forEach(sec => sec.style.display = 'none');

                if (tabId === 'template') {
                    sections[0].style.display = 'block';
                } else if (tabId === 'warehouse') {
                    sections[1].style.display = 'block';
                } else if (tabId === 'product') {
                    sections[2].style.display = 'block';
                } else if (tabId === 'user' || tabId === 'snapshot') {
                    // It's a grid with two cards
                    sections[3].style.display = 'grid';
                } else if (tabId === 'moq') {
                    sections[4].style.display = 'block';
                }
            },
"""
content = content.replace('const AdminPage = {\n            async load()', 'const AdminPage = {\n' + js_addition + '\n            async load()')

# Also, add an initial hide script to AdminPage.load()
init_hide = """
                // Initial hide
                setTimeout(() => {
                    const firstTab = document.querySelector('.settings-nav-item');
                    if (firstTab) AdminPage.showTab('template', firstTab);
                }, 50);
"""
content = content.replace('await Promise.all([this.loadUsers(), this.loadSnapshots(), this.loadWarehouses(), this.loadMOQ(), this.loadProducts()]);', 'await Promise.all([this.loadUsers(), this.loadSnapshots(), this.loadWarehouses(), this.loadMOQ(), this.loadProducts()]);' + init_hide)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("users.html refactored!")
