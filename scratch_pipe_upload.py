import os

pipe_path = r"c:\MyMain\Eibe\SCM-Dashboard\app\routers\pipeline.py"
with open(pipe_path, "r", encoding="utf-8") as f:
    content = f.read()

upload_code = """
from app.core.excel_parser import parse_excel_file

@router.post("/api/orders/upload", response_model=MessageResponse, tags=["입고 파이프라인"])
def upload_orders(
    file: UploadFile = File(...),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        contents = file.file.read()
        records = parse_excel_file(contents, "order")
        created = 0
        for r in records:
            obj = OrderDB(**r)
            db.add(obj)
            created += 1
        db.commit()
        return MessageResponse(message=f"발주 업로드 완료: {created}건 등록")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"엑셀 처리 중 오류: {str(e)}")

@router.post("/api/productions/upload", response_model=MessageResponse, tags=["입고 파이프라인"])
def upload_productions(
    file: UploadFile = File(...),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        contents = file.file.read()
        records = parse_excel_file(contents, "production")
        created = 0
        for r in records:
            obj = ProductionDB(**r)
            db.add(obj)
            created += 1
        db.commit()
        return MessageResponse(message=f"생산 업로드 완료: {created}건 등록")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"엑셀 처리 중 오류: {str(e)}")

@router.post("/api/inbound/upload", response_model=MessageResponse, tags=["입고 파이프라인"])
def upload_inbound(
    file: UploadFile = File(...),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        contents = file.file.read()
        records = parse_excel_file(contents, "inbound")
        created = 0
        for r in records:
            obj = InboundDB(**r)
            db.add(obj)
            created += 1
        db.commit()
        return MessageResponse(message=f"입고 업로드 완료: {created}건 등록")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"엑셀 처리 중 오류: {str(e)}")
"""

if "def upload_orders" not in content:
    content += upload_code
    with open(pipe_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Added upload endpoints to pipeline.py")
else:
    print("Upload endpoints already exist.")
