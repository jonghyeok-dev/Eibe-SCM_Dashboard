import re

file_path = r"c:\MyMain\Eibe\SCM-Dashboard\web\matching.html"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Replace the buttons
content = content.replace("MatchingPage.showManualModal('order')", "MatchingPage.addInlineRow('order')")
content = content.replace("MatchingPage.showManualModal('production')", "MatchingPage.addInlineRow('production')")
content = content.replace("MatchingPage.showManualModal('inbound')", "MatchingPage.addInlineRow('inbound')")

# 2. Remove the modals (Lines 163 to 211)
modal_pattern = r'<!-- Pipeline Manual Input Modals -->.*?<div id="toast-container" class="toast-container">'
content = re.sub(modal_pattern, '<div id="toast-container" class="toast-container">', content, flags=re.DOTALL)

# 3. Inject addInlineRow and saveInline into MatchingPage
js_inject = """
            addInlineRow(type) {
                let tbody, trHtml;
                if (type === 'order') {
                    tbody = document.querySelector('#orders-table tbody');
                    if (tbody.querySelector('.empty-state') || tbody.innerHTML.includes('발주 데이터가 없습니다')) tbody.innerHTML = '';
                    trHtml = `
                        <td><input type="month" id="inline-po-month" class="form-input"></td>
                        <td><input type="text" id="inline-po-code" class="form-input"></td>
                        <td class="text-right"><input type="number" id="inline-po-qty" class="form-input" min="0" style="width:100px;"></td>
                        <td>
                            <button class="btn btn--primary btn--sm" onclick="MatchingPage.saveInline('order', this)">저장</button>
                            <button class="btn btn--secondary btn--sm" onclick="this.closest('tr').remove()">취소</button>
                        </td>
                    `;
                } else if (type === 'production') {
                    document.getElementById('detail-panel').style.display = 'block';
                    document.getElementById('detail-title').textContent = '새로운 생산 데이터 추가 (미연결)';
                    tbody = document.querySelector('#production-detail-table tbody');
                    if (tbody.querySelector('.empty-state') || tbody.innerHTML.includes('매칭된 생산 내역이 없습니다')) tbody.innerHTML = '';
                    trHtml = `
                        <td>
                            <input type="text" id="inline-pr-purchase" class="form-input" placeholder="구매코드" style="width:100px; display:inline-block;">
                            <input type="text" id="inline-pr-code" class="form-input" placeholder="생산코드" style="width:100px; display:inline-block;">
                        </td>
                        <td class="text-right"><input type="number" id="inline-pr-qty" class="form-input" min="0" style="width:80px;"></td>
                        <td>
                            <input type="text" id="inline-pr-order" class="form-input" placeholder="매칭 발주ID" style="width:80px; display:inline-block;">
                            <button class="btn btn--primary btn--sm" onclick="MatchingPage.saveInline('production', this)">저장</button>
                            <button class="btn btn--secondary btn--sm" onclick="this.closest('tr').remove()">취소</button>
                        </td>
                    `;
                } else if (type === 'inbound') {
                    document.getElementById('detail-panel').style.display = 'block';
                    document.getElementById('detail-title').textContent = '새로운 입고 데이터 추가 (미연결)';
                    tbody = document.querySelector('#inbound-detail-table tbody');
                    if (tbody.querySelector('.empty-state') || tbody.innerHTML.includes('매칭된 입고 내역이 없습니다')) tbody.innerHTML = '';
                    trHtml = `
                        <td>
                            <input type="text" id="inline-in-inv" class="form-input" placeholder="인보이스">
                        </td>
                        <td><input type="text" id="inline-in-status" class="form-input" value="입고완료"></td>
                        <td class="text-right">
                            <input type="number" id="inline-in-price" class="form-input" step="0.01" placeholder="단가">
                        </td>
                        <td class="text-right">
                            <input type="text" id="inline-in-prodcode" class="form-input" placeholder="품목코드" style="width:80px; display:inline-block;">
                            <input type="text" id="inline-in-bl" class="form-input" placeholder="B/L번호" style="width:80px; display:inline-block;">
                            <input type="text" id="inline-in-match" class="form-input" placeholder="매칭 생산ID" style="width:80px; display:inline-block;">
                            <button class="btn btn--primary btn--sm" onclick="MatchingPage.saveInline('inbound', this)">저장</button>
                            <button class="btn btn--secondary btn--sm" onclick="this.closest('tr').remove()">취소</button>
                        </td>
                    `;
                }
                
                const tr = document.createElement('tr');
                tr.innerHTML = trHtml;
                tbody.insertBefore(tr, tbody.firstChild);
            },
            async saveInline(type, btn) {
                const tr = btn.closest('tr');
                try {
                    if (type === 'order') {
                        await API.post('/api/orders', {
                            order_month: tr.querySelector('#inline-po-month').value,
                            product_code: tr.querySelector('#inline-po-code').value,
                            order_qty: parseInt(tr.querySelector('#inline-po-qty').value)
                        });
                    } else if (type === 'production') {
                        const orderId = tr.querySelector('#inline-pr-order').value;
                        await API.post('/api/productions', {
                            purchase_code: tr.querySelector('#inline-pr-purchase').value,
                            production_code: tr.querySelector('#inline-pr-code').value,
                            production_qty: parseInt(tr.querySelector('#inline-pr-qty').value),
                            matched_order_id: orderId ? parseInt(orderId) : null
                        });
                    } else if (type === 'inbound') {
                        const matchId = tr.querySelector('#inline-in-match').value;
                        await API.post('/api/inbound', {
                            invoice_no: tr.querySelector('#inline-in-inv').value,
                            bl_no: tr.querySelector('#inline-in-bl').value,
                            product_code: tr.querySelector('#inline-in-prodcode').value,
                            unit_price: parseFloat(tr.querySelector('#inline-in-price').value || 0),
                            status: tr.querySelector('#inline-in-status').value,
                            matched_production_id: matchId ? parseInt(matchId) : null
                        });
                    }
                    Toast.show('등록 완료', 'success');
                    this.load();
                } catch(e) {
                    console.error(e);
                }
            },
"""

# Now selectively remove `showManualModal`, `closeModal`, `saveManual`
pattern_methods = r'showManualModal\(type\) \{[\s\S]*?async saveManual\(type\) \{[\s\S]*?\}\s*\} catch\(e\) \{[\s\S]*?\}\s*\},'

content = re.sub(pattern_methods, js_inject, content)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Matching safely fixed.")
