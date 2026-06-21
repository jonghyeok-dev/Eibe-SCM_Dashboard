import os
import re

base_dir = r"c:\MyMain\Eibe\SCM-Dashboard\web"
files = ["index.html", "inventory.html", "expiry.html", "order_plan.html", "matching.html", "users.html"]

for fname in files:
    fpath = os.path.join(base_dir, fname)
    if not os.path.exists(fpath): continue
    
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Replace brand logo and title
    brand_pattern = r'<div class="sidebar-brand">\s*<img src="/static/img/eibelogo.png"[^>]*>\s*<h1>EIBE SCM</h1>\s*</div>'
    new_brand = """<div class="sidebar-brand" style="justify-content: center;">
                <h1 style="font-size: 1.1rem; letter-spacing: -0.5px;">EIBE SCM System</h1>
            </div>"""
    content = re.sub(brand_pattern, new_brand, content)
    
    # Also catch cases where it might have been slightly modified
    content = re.sub(r'<img src="/static/img/eibelogo\.png"[^>]*>', '', content)
    content = content.replace('<h1>EIBE SCM</h1>', '<h1 style="font-size: 1.1rem; letter-spacing: -0.5px;">EIBE SCM System</h1>')

    # 2. Improve Sidebar Toggle button HTML (Move it out of normal flow or style it better)
    # We will replace the existing button with a modernized one
    old_btn = r'<button class="sidebar-toggle" id="sidebar-toggle"[^>]*>.*?</button>'
    new_btn = """<button class="sidebar-toggle-modern" id="sidebar-toggle" aria-label="Toggle Sidebar">
                <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none">
                    <polyline points="15 18 9 12 15 6"></polyline>
                </svg>
            </button>"""
    content = re.sub(old_btn, new_btn, content, flags=re.DOTALL)

    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)

print("Sidebar UX HTML updated.")
