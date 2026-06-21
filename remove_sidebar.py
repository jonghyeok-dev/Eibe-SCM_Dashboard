import os, glob

for f in glob.glob('web/*.html'):
    with open(f, 'r', encoding='utf-8') as file:
        content = file.read()
    
    start_idx = content.find('<aside class="app-sidebar">')
    if start_idx != -1:
        end_idx = content.find('</aside>', start_idx)
        if end_idx != -1:
            content = content[:start_idx] + content[end_idx + 8:]
            with open(f, 'w', encoding='utf-8') as file:
                file.write(content)
            print(f'Removed sidebar from {f}')
