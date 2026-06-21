import os
import re

seed_path = r"c:\MyMain\Eibe\SCM-Dashboard\seed_data.py"

with open(seed_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Remove InvoiceDB from imports
content = content.replace("ProductionDB, InvoiceDB, InboundDB,", "ProductionDB, InboundDB,")
content = content.replace("db.query(InvoiceDB).delete()\n    ", "")

# Remove Invoice seeding logic and combine into Inbound
invoice_old = r"""                # Invoice
                carton_qty = int\(order_qty / prod.pack_qty_per_tu\)
                invoice = InvoiceDB\(
                    invoice_no=f"INV-\{month_str\}-\{prod.product_code\}",
                    purchase_code=production.purchase_code,
                    production_code=production.production_code,
                    carton_qty=carton_qty,
                    unit_price=prod.purchase_price,
                    total_price=carton_qty \* prod.pack_qty_per_tu \* prod.purchase_price,
                    product_name=prod.product_name,
                    product_code=prod.product_code,
                    eta=\(today - timedelta\(days=30\*i - 15\)\).strftime\("%Y-%m-%d"\),
                    payment_date=\(today - timedelta\(days=30\*i - 20\)\).strftime\("%Y-%m-%d"\),
                    invoice_date=\(today - timedelta\(days=30\*i\)\).strftime\("%Y-%m-%d"\),
                    exchange_rate=1400.0,
                    payment_amount_krw=int\(carton_qty \* prod.pack_qty_per_tu \* prod.purchase_price \* 1400.0\),
                    arrival_wh_id=wh_main,
                    matched_production_id=production.id,
                    created_at=datetime.now\(\).strftime\("%Y-%m-%d %H:%M:%S"\)
                \)
                db.add\(invoice\)
                db.commit\(\)
                
                # Inbound
                inbound = InboundDB\(
                    invoice_no=invoice.invoice_no,
                    bl_no=f"BL-\{month_str\}-\{prod.product_code\}",
                    shipping_date=\(today - timedelta\(days=30\*i - 5\)\).strftime\("%Y-%m-%d"\),
                    korea_arrival_date=\(today - timedelta\(days=30\*i - 25\)\).strftime\("%Y-%m-%d"\),
                    manufacture_date=\(today - timedelta\(days=30\*i \+ 15\)\).strftime\("%Y-%m-%d"\),
                    expiry_date=\(today \+ timedelta\(days=365\*2 - 30\*i\)\).strftime\("%Y-%m-%d"\),
                    carton_qty=carton_qty,
                    can_qty=order_qty,
                    product_code=prod.product_code,
                    status="입고완료"
                \)
                db.add\(inbound\)
                db.commit\(\)"""

inbound_new = """                # Inbound (Invoice merged)
                carton_qty = int(order_qty / prod.pack_qty_per_tu)
                inbound = InboundDB(
                    invoice_no=f"INV-{month_str}-{prod.product_code}",
                    bl_no=f"BL-{month_str}-{prod.product_code}",
                    purchase_code=production.purchase_code,
                    production_code=production.production_code,
                    shipping_date=(today - timedelta(days=30*i - 5)).strftime("%Y-%m-%d"),
                    korea_arrival_date=(today - timedelta(days=30*i - 25)).strftime("%Y-%m-%d"),
                    eta=(today - timedelta(days=30*i - 15)).strftime("%Y-%m-%d"),
                    manufacture_date=(today - timedelta(days=30*i + 15)).strftime("%Y-%m-%d"),
                    expiry_date=(today + timedelta(days=365*2 - 30*i)).strftime("%Y-%m-%d"),
                    carton_qty=carton_qty,
                    can_qty=order_qty,
                    unit_price=prod.purchase_price,
                    total_price=carton_qty * prod.pack_qty_per_tu * prod.purchase_price,
                    payment_date=(today - timedelta(days=30*i - 20)).strftime("%Y-%m-%d"),
                    invoice_date=(today - timedelta(days=30*i)).strftime("%Y-%m-%d"),
                    exchange_rate=1400.0,
                    payment_amount_krw=int(carton_qty * prod.pack_qty_per_tu * prod.purchase_price * 1400.0),
                    arrival_wh_id=wh_main,
                    matched_production_id=production.id,
                    product_code=prod.product_code,
                    status="입고완료",
                    created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
                db.add(inbound)
                db.commit()"""

content = re.sub(invoice_old, inbound_new, content)

# Also rename "Invoices" in print
content = content.replace("Seeding Orders, Productions, Invoices (Pipeline)...", "Seeding Orders, Productions, Inbounds (Pipeline)...")

with open(seed_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("seed_data.py updated.")
