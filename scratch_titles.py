import os
import re

base_dir = r"c:\MyMain\Eibe\SCM-Dashboard\web"

titles = {
    "index.html": ("요약", "전사 요약 대시보드"),
    "inventory.html": ("현재고", "창고별 재고 현황"),
    "expiry.html": ("폐기", "유통기한 임박 관리"),
    "order_plan.html": ("발주", "데이터 기반 발주 제안"),
    "matching.html": ("입고", "입고 파이프라인 (발주-생산-입고)"),
    "users.html": ("설정", "마스터 및 시스템 운영")
}

for fname, (title, subtitle) in titles.items():
    fpath = os.path.join(base_dir, fname)
    if not os.path.exists(fpath): continue
    
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Replace Title and Subtitle inside <div class="page-header-left">
    pattern = r'<h1 class="page-title"[^>]*>.*?</h1>\s*<p class="page-subtitle"[^>]*>.*?</p>'
    replacement = f'<h1 class="page-title" id="main-page-title">{title}</h1>\n                    <p class="page-subtitle" id="main-page-subtitle">{subtitle}</p>'
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    if fname == "expiry.html":
        # Remove KPI section
        content = re.sub(r'<!-- KPI 요약 -->.*?</section>', '', content, flags=re.DOTALL)
        
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)

print("Titles and Expiry KPIs updated.")
