import os
import re

# 1. Update excel_parser.py
parser_path = r"c:\MyMain\Eibe\SCM-Dashboard\app\core\excel_parser.py"
with open(parser_path, "r", encoding="utf-8") as f:
    parser_content = f.read()

# Remove updated_at from inventory_snapshot template columns and example
parser_content = parser_content.replace(
    '["스냅샷일자(YYYY-MM-DD)", "창고이름", "품목명", "품목코드", "유통기한(YYYY-MM-DD)", "수량(캔)", "업데이트일시(YYYY-MM-DD HH:MM:SS)"]',
    '["스냅샷일자(YYYY-MM-DD)", "창고이름", "품목명", "품목코드", "유통기한(YYYY-MM-DD)", "수량(캔)"]'
)
parser_content = parser_content.replace(
    '["2026-06-19", "용인 메인창고", "슈누프로1단계", "SN-001", "2028-05-15", 12000, "2026-06-19 15:30:00"]',
    '["2026-06-19", "용인 메인창고", "슈누프로1단계", "SN-001", "2028-05-15", 12000]'
)

# Remove updated_at from parse_inventory_excel
parser_content = re.sub(
    r'"updated_at": str\(row\.iloc\[6\]\)\.strip\(\) if len\(row\) > 6 and pd\.notna\(row\.iloc\[6\]\) else None,',
    '',
    parser_content
)

with open(parser_path, "w", encoding="utf-8") as f:
    f.write(parser_content)

# 2. Update upload_inventory_snapshot in inventory.py
router_path = r"c:\MyMain\Eibe\SCM-Dashboard\app\routers\inventory.py"
with open(router_path, "r", encoding="utf-8") as f:
    router_content = f.read()

# Replace the body of upload_inventory_snapshot to use excel_parser
# The user wants current time to be automatically added, so we just use datetime.now().strftime('%Y-%m-%d %H:%M:%S')

new_upload_code = """@router.post("/api/inventory-snapshot/upload", response_model=MessageResponse, tags=["재고 관리"])
def upload_inventory_snapshot(
    file: UploadFile = File(...),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    \"\"\"현재고 스냅샷 엑셀 업로드\"\"\"
    from app.core.excel_parser import parse_inventory_excel
    import datetime

    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="xlsx 파일만 업로드 가능합니다")

    content = file.file.read()
    try:
        records = parse_inventory_excel(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"엑셀 파일 파싱 실패: {e}")

    if not records:
        raise HTTPException(status_code=400, detail="엑셀 파일에 데이터가 없습니다.")

    created = 0
    now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        for row in records:
            # 창고 및 품목 ID 매핑
            wh = db.query(WarehouseDB).filter(WarehouseDB.warehouse_name == row.get("warehouse_name")).first()
            prod = db.query(ProductDB).filter(ProductDB.product_code == row.get("product_code")).first()
            
            if not wh or not prod:
                continue
                
            snapshot = InventorySnapshot(
                snapshot_date=row.get("snapshot_date"),
                warehouse_id=wh.id,
                product_id=prod.id,
                qty_cans=row.get("qty_cans", 0),
                expiry_date=row.get("expiry_date"),
                updated_at=now_str
            )
            db.add(snapshot)
            created += 1
            
        db.commit()
        return MessageResponse(message=f"스냅샷 업로드 완료: {created}건 생성")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"데이터베이스 저장 중 오류: {str(e)}")"""

# Regex to replace the function
pattern = r'@router\.post\("/api/inventory-snapshot/upload".*?raise HTTPException\(status_code=500, detail=f"DB 저장 중 오류: {e}"\)'
router_content = re.sub(pattern, new_upload_code, router_content, flags=re.DOTALL)

with open(router_path, "w", encoding="utf-8") as f:
    f.write(router_content)

print("Excel Parser and Router updated.")
