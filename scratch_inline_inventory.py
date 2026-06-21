import re

file_path = r"c:\MyMain\Eibe\SCM-Dashboard\web\inventory.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Remove the modal HTML completely
content = re.sub(r'<div id="inv-manage-modal".*?</div>\s*</div>\s*</div>', '', content, flags=re.DOTALL)

# 2. Add the "+ 행 추가" button to the header
header_pattern = r'<button class="btn btn--primary btn--sm" onclick="InventoryPage\.showManageModal\(\)">\+ 재고 추가</button>'
header_replace = r'<button class="btn btn--primary btn--sm" onclick="InventoryPage.addInlineRow()">+ 행 추가</button>'
content = re.sub(header_pattern, header_replace, content)

# Also fix the button if it says something else or is missing
if '+ 행 추가' not in content:
    btn_group_pattern = r'<div class="btn-group">\s*<button class="btn btn--secondary btn--sm" onclick="downloadTemplate\(\'current_inventory\'\)">양식 다운로드</button>'
    btn_group_replace = r'<div class="btn-group">\n                        <button class="btn btn--primary btn--sm" onclick="InventoryPage.addInlineRow()">+ 행 추가</button>\n                        <button class="btn btn--secondary btn--sm" onclick="downloadTemplate(\'current_inventory\')">양식 다운로드</button>'
    content = re.sub(btn_group_pattern, btn_group_replace, content)

# 3. Inject JS for inline row addition
inline_js = """
            addInlineRow() {
                const tbody = document.querySelector('#inventory-detail-table tbody');
                // Remove empty state if present
                if (tbody.querySelector('.empty-state')) tbody.innerHTML = '';
                
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><select id="inline-ffc" class="form-select"><option value="1">용인 메인창고</option><option value="2">온라인 FFC</option><option value="3">오프라인 FFC</option></select></td>
                    <td><select id="inline-product" class="form-select"><option value="1">SN-001</option><option value="2">SN-002</option></select></td>
                    <td>-</td>
                    <td><input type="number" id="inline-qty" class="form-input" min="0" value="0" style="width:100px;"></td>
                    <td>-</td>
                    <td>자동 생성됨</td>
                    <td>
                        <button class="btn btn--primary btn--sm" onclick="InventoryPage.saveInlineRow(this)">저장</button>
                        <button class="btn btn--secondary btn--sm" onclick="this.closest('tr').remove()">취소</button>
                    </td>
                `;
                tbody.insertBefore(tr, tbody.firstChild);
                
                // Fetch dynamic options
                API.get('/api/warehouses').then(res => {
                    document.getElementById('inline-ffc').innerHTML = res.map(w => `<option value="${w.id}">${w.warehouse_name}</option>`).join('');
                });
                API.get('/api/products').then(res => {
                    document.getElementById('inline-product').innerHTML = res.map(p => `<option value="${p.id}">${p.product_code}</option>`).join('');
                });
            },
            async saveInlineRow(btn) {
                const tr = btn.closest('tr');
                const whId = tr.querySelector('#inline-ffc').value;
                const prodId = tr.querySelector('#inline-product').value;
                const qty = parseInt(tr.querySelector('#inline-qty').value);
                
                const today = new Date().toISOString().split('T')[0];
                try {
                    await API.post('/api/inventory-snapshot', {
                        snapshot_date: today,
                        warehouse_id: parseInt(whId),
                        product_id: parseInt(prodId),
                        qty_cans: qty,
                        expiry_date: null
                    });
                    Toast.show('재고가 성공적으로 추가되었습니다.', 'success');
                    this.loadData();
                } catch(e) {
                    console.error(e);
                }
            },
"""

# Find `init()` method and insert before it
content = content.replace('init() {', inline_js + '\n            init() {')

# Find and replace old JS modal methods
content = re.sub(r'showManageModal\(.*?\).*?closeManageModal\(\) {.*?},', '', content, flags=re.DOTALL)
content = re.sub(r'async saveInventory\(\) {.*?},', '', content, flags=re.DOTALL)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Inventory inline add injected.")
