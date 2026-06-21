import os
import re

WEB_DIR = r"C:\Users\parkj\.gemini\antigravity\worktrees\SCM-dashboad\refactor-add-error-handling\web"
TEMPLATE_DIR = os.path.join(WEB_DIR, "templates")
os.makedirs(TEMPLATE_DIR, exist_ok=True)

files_to_migrate = [
    "inventory.html",
    "order_plan.html",
    "matching.html",
    "expiry.html",
    "users.html",
    "login.html"
]

def migrate_file(filename):
    filepath = os.path.join(WEB_DIR, filename)
    if not os.path.exists(filepath):
        print(f"Skipping {filename}, not found.")
        return

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Login page is a special case, it might not have the same structure
    if filename == "login.html":
        # Keep login standalone or wrap it. Let's just wrap it cleanly.
        # If it doesn't have a sidebar, we can create a minimalist layout or just serve it as is.
        # Actually, let's just copy login.html completely but replace the token check script if any.
        # For simplicity, we just copy login.html directly to templates.
        with open(os.path.join(TEMPLATE_DIR, filename), 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Copied {filename}")
        return

    # Extract extra head (chart.js etc)
    extra_head = ""
    head_match = re.search(r'<head>(.*?)</head>', content, re.DOTALL)
    if head_match:
        head_content = head_match.group(1)
        # Find any <script src="..."> not related to style.css or basic tags
        for line in head_content.split('\n'):
            if '<script src="' in line and 'chart.js' in line:
                extra_head += line + "\n"

    # Extract main content
    main_match = re.search(r'<main class="main-content">(.*?)</main>', content, re.DOTALL)
    if not main_match:
        print(f"Failed to find <main> in {filename}")
        return
    main_content = main_match.group(1).strip()

    # Extract scripts at the end
    script_match = re.search(r'(<div id="toast-container".*?</body>)', content, re.DOTALL)
    scripts = ""
    if script_match:
        # Extract toast and scripts
        toast_scripts = script_match.group(1).replace('</body>', '').strip()
        scripts = toast_scripts
    else:
        # Fallback to search for just scripts
        scripts_only = re.search(r'(<script>.*?</script>)', content, re.DOTALL)
        if scripts_only:
            scripts = scripts_only.group(1).strip()

    # Construct the Jinja2 template
    template_str = "{% extends \"base.html\" %}\n\n"
    if extra_head:
        template_str += "{% block extra_head %}\n" + extra_head.strip() + "\n{% endblock %}\n\n"

    template_str += "{% block content %}\n" + main_content + "\n{% endblock %}\n\n"
    template_str += "{% block scripts %}\n" + scripts + "\n{% endblock %}\n"

    outpath = os.path.join(TEMPLATE_DIR, filename)
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(template_str)
    print(f"Migrated {filename}")

for file in files_to_migrate:
    migrate_file(file)

print("Migration completed.")
