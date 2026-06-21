import re

file_path = r"c:\MyMain\Eibe\SCM-Dashboard\web\matching.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace dummy alert buttons with actual calls
content = content.replace("onclick=\"alert('엑셀 업로드 준비중')\"", "onclick=\"MatchingPage.triggerUpload(this)\"")
content = content.replace("onclick=\"alert('수동 입력 모달 준비중')\"", "onclick=\"MatchingPage.showManualModal(this)\"")

# Inject Hidden Inputs into the Action Cards
order_action = """<h3>1. 발주 (Order)</h3>
                    <div class="action-btn-group">
                        <input type="file" id="upload-order" style="display:none;" accept=".xlsx" onchange="MatchingPage.handleUpload('order', this)">
                        <button class="btn btn--secondary btn--sm" onclick="document.getElementById('upload-order').click()">엑셀 업로드</button>
                        <button class="btn btn--primary btn--sm" onclick="MatchingPage.showManualModal('order')">수동 입력</button>
                    </div>"""
prod_action = """<h3>2. 생산 (Production)</h3>
                    <div class="action-btn-group">
                        <input type="file" id="upload-production" style="display:none;" accept=".xlsx" onchange="MatchingPage.handleUpload('production', this)">
                        <button class="btn btn--secondary btn--sm" onclick="document.getElementById('upload-production').click()">엑셀 업로드</button>
                        <button class="btn btn--primary btn--sm" onclick="MatchingPage.showManualModal('production')">수동 입력</button>
                    </div>"""
inbound_action = """<h3>3. 입고 (Inbound)</h3>
                    <div class="action-btn-group">
                        <input type="file" id="upload-inbound" style="display:none;" accept=".xlsx" onchange="MatchingPage.handleUpload('inbound', this)">
                        <button class="btn btn--secondary btn--sm" onclick="document.getElementById('upload-inbound').click()">엑셀 업로드</button>
                        <button class="btn btn--primary btn--sm" onclick="MatchingPage.showManualModal('inbound')">수동 입력</button>
                    </div>"""

# Find and replace the action-cards
content = re.sub(r"<h3>1\. 발주 \(Order\).*?</div>\s*</div>", order_action + "\n                </div>", content, flags=re.DOTALL)
content = re.sub(r"<h3>2\. 생산 \(Production\).*?</div>\s*</div>", prod_action + "\n                </div>", content, flags=re.DOTALL)
content = re.sub(r"<h3>3\. 입고 \(Inbound\).*?</div>\s*</div>", inbound_action + "\n                </div>", content, flags=re.DOTALL)

modals_html = """
    <!-- Pipeline Manual Input Modals -->
    <div id="pipe-modal-order" style="display:none;">
        <div class="modal-backdrop" onclick="event.target===this && MatchingPage.closeModal('order')">
            <div class="modal-content" style="max-width: 400px;">
                <h2>발주 수동 입력</h2>
                <div class="form-group"><label class="form-label">발주월</label><input type="month" id="po-month" class="form-input"></div>
                <div class="form-group"><label class="form-label">품목코드</label><input type="text" id="po-code" class="form-input"></div>
                <div class="form-group"><label class="form-label">발주수량(캔)</label><input type="number" id="po-qty" class="form-input" min="0"></div>
                <div class="modal-actions" style="margin-top:20px;">
                    <button class="btn btn--secondary" onclick="MatchingPage.closeModal('order')">취소</button>
                    <button class="btn btn--primary" onclick="MatchingPage.saveManual('order')">저장</button>
                </div>
            </div>
        </div>
    </div>
    
    <div id="pipe-modal-production" style="display:none;">
        <div class="modal-backdrop" onclick="event.target===this && MatchingPage.closeModal('production')">
            <div class="modal-content" style="max-width: 400px;">
                <h2>생산 수동 입력</h2>
                <div class="form-group"><label class="form-label">품의번호(구매)</label><input type="text" id="pr-purchase" class="form-input"></div>
                <div class="form-group"><label class="form-label">생산코드(제조)</label><input type="text" id="pr-code" class="form-input"></div>
                <div class="form-group"><label class="form-label">발주수량(캔)</label><input type="number" id="pr-qty" class="form-input" min="0"></div>
                <div class="form-group"><label class="form-label">매칭 발주코드</label><input type="text" id="pr-order" class="form-input" placeholder="옵션"></div>
                <div class="modal-actions" style="margin-top:20px;">
                    <button class="btn btn--secondary" onclick="MatchingPage.closeModal('production')">취소</button>
                    <button class="btn btn--primary" onclick="MatchingPage.saveManual('production')">저장</button>
                </div>
            </div>
        </div>
    </div>
    
    <div id="pipe-modal-inbound" style="display:none;">
        <div class="modal-backdrop" onclick="event.target===this && MatchingPage.closeModal('inbound')">
            <div class="modal-content" style="max-width: 400px; height:80vh; overflow-y:auto;">
                <h2>입고 수동 입력</h2>
                <div class="form-group"><label class="form-label">인보이스 번호</label><input type="text" id="in-inv" class="form-input"></div>
                <div class="form-group"><label class="form-label">B/L 번호</label><input type="text" id="in-bl" class="form-input"></div>
                <div class="form-group"><label class="form-label">품목코드</label><input type="text" id="in-prodcode" class="form-input"></div>
                <div class="form-group"><label class="form-label">단가</label><input type="number" id="in-price" class="form-input" step="0.01"></div>
                <div class="form-group"><label class="form-label">상태</label><input type="text" id="in-status" class="form-input" value="입고완료"></div>
                <div class="form-group"><label class="form-label">매칭 생산코드</label><input type="text" id="in-match" class="form-input" placeholder="옵션"></div>
                <div class="modal-actions" style="margin-top:20px;">
                    <button class="btn btn--secondary" onclick="MatchingPage.closeModal('inbound')">취소</button>
                    <button class="btn btn--primary" onclick="MatchingPage.saveManual('inbound')">저장</button>
                </div>
            </div>
        </div>
    </div>
"""

content = content.replace('<div id="toast-container" class="toast-container"></div>', modals_html + '\n    <div id="toast-container" class="toast-container"></div>')

js_inject = """
            showManualModal(type) {
                document.getElementById('pipe-modal-' + type).style.display = 'block';
            },
            closeModal(type) {
                document.getElementById('pipe-modal-' + type).style.display = 'none';
            },
            async handleUpload(type, inputElem) {
                const file = inputElem.files[0];
                if (!file) return;
                inputElem.value = '';
                const formData = new FormData();
                formData.append('file', file);
                try {
                    let endpoint = type === 'order' ? '/api/orders/upload' : (type === 'production' ? '/api/productions/upload' : '/api/inbound/upload');
                    const res = await API.postFormData(endpoint, formData);
                    Toast.show(res.message, 'success');
                    this.load();
                } catch(e) { console.error(e); }
            },
            async saveManual(type) {
                try {
                    if (type === 'order') {
                        await API.post('/api/orders', {
                            order_month: document.getElementById('po-month').value,
                            product_code: document.getElementById('po-code').value,
                            order_qty: parseInt(document.getElementById('po-qty').value)
                        });
                    } else if (type === 'production') {
                        await API.post('/api/productions', {
                            purchase_code: document.getElementById('pr-purchase').value,
                            production_code: document.getElementById('pr-code').value,
                            production_qty: parseInt(document.getElementById('pr-qty').value),
                            matched_order_id: document.getElementById('pr-order').value ? parseInt(document.getElementById('pr-order').value) : null
                        });
                    } else if (type === 'inbound') {
                        await API.post('/api/inbound', {
                            invoice_no: document.getElementById('in-inv').value,
                            bl_no: document.getElementById('in-bl').value,
                            product_code: document.getElementById('in-prodcode').value,
                            unit_price: parseFloat(document.getElementById('in-price').value),
                            status: document.getElementById('in-status').value,
                            matched_production_id: document.getElementById('in-match').value ? parseInt(document.getElementById('in-match').value) : null
                        });
                    }
                    Toast.show('등록 완료', 'success');
                    this.closeModal(type);
                    this.load();
                } catch(e) {
                    console.error(e);
                }
            },
"""

content = content.replace('async load() {', js_inject + '\n            async load() {')

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("matching.html updated with modals!")
