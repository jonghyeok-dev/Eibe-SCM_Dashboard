import os
import re

base_dir = r"c:\MyMain\Eibe\SCM-Dashboard\web"
files = ["index.html", "inventory.html", "expiry.html", "order_plan.html", "matching.html", "users.html"]

for fname in files:
    fpath = os.path.join(base_dir, fname)
    if not os.path.exists(fpath): continue
    
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()

    # Add onclick="Sidebar.toggle()" to the sidebar-toggle-modern button
    content = content.replace(
        '<button class="sidebar-toggle-modern" id="sidebar-toggle" aria-label="Toggle Sidebar">',
        '<button class="sidebar-toggle-modern" id="sidebar-toggle" aria-label="Toggle Sidebar" onclick="Sidebar.toggle()">'
    )

    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)

print("Toggle button onclick added.")
