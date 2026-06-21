import os
import re

files = {
    "index.html": "/",
    "inventory.html": "/inventory",
    "expiry.html": "/expiry",
    "order_plan.html": "/order-plan",
    "matching.html": "/matching",
    "users.html": "/users"
}

base_dir = r"c:\MyMain\Eibe\SCM-Dashboard\web"

def get_sidebar_html(active_href):
    def active(href):
        return ' active' if href == active_href else ''
    
    return f"""<nav class="sidebar-nav">
                <a href="/" class="nav-item{active('/')}"><span class="nav-icon"><svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg></span><span>요약</span></a>
                <a href="/inventory" class="nav-item{active('/inventory')}"><span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg></span><span>현재고</span></a>
                <a href="/expiry" class="nav-item{active('/expiry')}"><span class="nav-icon"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg></span><span>폐기</span></a>
                <a href="/order-plan" class="nav-item{active('/order-plan')}"><span class="nav-icon"><svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></span><span>발주</span></a>
                <a href="/matching" class="nav-item{active('/matching')}"><span class="nav-icon"><svg viewBox="0 0 24 24"><rect x="1" y="3" width="15" height="13" rx="2"/><path d="M16 8h4a2 2 0 012 2v9a2 2 0 01-2 2H8a2 2 0 01-2-2v-4"/></svg></span><span>입고</span></a>
                <div class="nav-group">
                    <a href="/users" class="nav-parent{active('/users')}"><span class="nav-icon"><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg></span><span>설정</span></a>
                    <div class="nav-sub">
                        <a href="/users#template-header">데이터 양식</a>
                        <a href="/users#warehouse-header">창고 관리</a>
                        <a href="/users#product-header">품목 관리</a>
                        <a href="/users#user-header">사용자 관리</a>
                        <a href="/users#snapshot-header">백업/스냅샷</a>
                        <a href="/users#moq-header">이관 MOQ</a>
                    </div>
                </div>
            </nav>"""

for fname, active_route in files.items():
    fpath = os.path.join(base_dir, fname)
    if not os.path.exists(fpath):
        continue
        
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Replace the entire <nav class="sidebar-nav"> ... </nav> block
    new_nav = get_sidebar_html(active_route)
    new_content = re.sub(r'<nav class="sidebar-nav">.*?</nav>', new_nav, content, flags=re.DOTALL)
    
    # Also fix any rogue order_plan URLs that might be outside the nav
    new_content = new_content.replace('href="/order_plan"', 'href="/order-plan"')
    
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(new_content)

print("Sidebars refactored successfully.")
