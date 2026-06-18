"""
FastAPI 메인 엔드포인트 및 라우팅 제어 모듈
- 정적 파일 서빙 (web/ 디렉토리)
- REST API 엔드포인트
- 명세서 CH 1.1 §4 기준 사내망 포트 개방 서빙
"""

import os
import shutil
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Optional
import urllib.parse

from app.database import get_db, init_db, BASE_DIR, BACKUP_DIR
from app.models import (
    ProductMaster,
    FFCMaster,
    FFCProductMOQ,
    LogisticsCostMaster,
    InboundList,
    ExpectedInbound,
    CurrentInventory,
    OutflowHistory,
    TransferPlan,
    MatchingHistoryLog,
    MonthlyOrderPlan,
    UserAccount,
    SystemSnapshot,
    SalesHistory,
    OrderQuantity,
    ProductionComplete,
    InvoiceQuantity,
)
from app.schemas import (
    ProductMasterCreate,
    ProductMasterResponse,
    FFCMasterCreate,
    FFCMasterResponse,
    FFCProductMOQCreate,
    FFCProductMOQResponse,
    LogisticsCostCreate,
    LogisticsCostResponse,
    InboundListResponse,
    ExpectedInboundCreate,
    ExpectedInboundResponse,
    CurrentInventoryResponse,
    OutflowHistoryResponse,
    MonthlyOrderPlanResponse,
    MonthlyOrderPlanUpdate,
    MessageResponse,
    FileUploadResponse,
    Token,
    UserAccountResponse,
    UserAccountCreate,
    SystemSnapshotResponse,
    OrderPlanBulkSave,
    SalesHistoryCreate,
    SalesHistoryResponse,
    OrderQuantityCreate,
    OrderQuantityResponse,
    ProductionCompleteCreate,
    ProductionCompleteResponse,
    InvoiceQuantityCreate,
    InvoiceQuantityResponse,
    PendingMatchesResponse,
)
from app.core.auth import verify_password, get_password_hash, create_access_token, get_current_user, get_current_admin
from app.core.snapshot import start_scheduler, stop_scheduler, create_snapshot
from app.core.excel_parser import generate_template, get_template_filename, parse_inventory_excel, generate_order_plan_export, TEMPLATE_LABELS
from app.core.forecasting import (
    calc_weekly_smoothing_constant,
    calc_dynamic_loss_buffer,
    simulate_future_inventory,
    calc_order_suggestion,
    calc_remaining_expiry_days,
    calc_inventory_value,
)


# ── DB 마이그레이션 (새 컬럼 추가) ────────────────────────────────────
def _run_migrations():
    """기존 DB에 새 컬럼이 없으면 ALTER TABLE로 추가"""
    import sqlite3
    db_path = os.path.join(BASE_DIR, "data", "local_erp.db")
    if not os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # FFCMaster: avg_transport_cost
    try:
        cursor.execute("SELECT avg_transport_cost FROM FFC_MASTER LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE FFC_MASTER ADD COLUMN avg_transport_cost REAL DEFAULT 0")
        print("[MIGRATION] Added avg_transport_cost to FFC_MASTER")
    # MonthlyOrderPlan: version
    try:
        cursor.execute("SELECT version FROM MONTHLY_ORDER_PLAN LIMIT 1")
    except sqlite3.OperationalError:
        cursor.execute("ALTER TABLE MONTHLY_ORDER_PLAN ADD COLUMN version INTEGER DEFAULT 1")
        print("[MIGRATION] Added version to MONTHLY_ORDER_PLAN")
    conn.commit()
    conn.close()


# ── 애플리케이션 수명주기 ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 DB 테이블 자동 생성 및 백그라운드 구동"""
    init_db()
    _run_migrations()
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        admin = db.query(UserAccount).filter(UserAccount.username == "admin").first()
        if not admin:
            pw_hash = get_password_hash("admin")
            db.add(UserAccount(username="admin", password_hash=pw_hash, role="ADMIN", name="시스템 관리자"))
            db.commit()
            print("[INIT] Default admin account created (admin/admin)")
    except Exception as e:
        print("Initialization error:", e)
        db.rollback()
    finally:
        db.close()
        
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="SCM ERP Dashboard",
    description="독립형 로컬 SCM ERP 시스템 - 분유 재고/수요 관리",
    version="2.0.0",
    lifespan=lifespan,
)


# ── 정적 파일 서빙 설정 ──────────────────────────────────────────────
WEB_DIR = os.path.join(BASE_DIR, "web")
STATIC_DIR = os.path.join(WEB_DIR, "static")

# static 디렉토리 존재 확인 및 마운트
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ═══════════════════════════════════════════════════════════════════════
# HTML 페이지 라우팅
# ═══════════════════════════════════════════════════════════════════════


@app.get("/", include_in_schema=False)
async def serve_dashboard():
    """메인 통합 대시보드 화면"""
    return FileResponse(os.path.join(WEB_DIR, "index.html"))

@app.get("/inventory", include_in_schema=False)
async def serve_inventory():
    return FileResponse(os.path.join(WEB_DIR, "inventory.html"))

@app.get("/expiry", include_in_schema=False)
async def serve_expiry():
    return FileResponse(os.path.join(WEB_DIR, "expiry.html"))

@app.get("/order-plan", include_in_schema=False)
async def serve_order_plan():
    """월 1회 발주 제안 편집 및 수정 저장 화면"""
    return FileResponse(os.path.join(WEB_DIR, "order_plan.html"))

@app.get("/matching", include_in_schema=False)
async def serve_matching():
    return FileResponse(os.path.join(WEB_DIR, "matching.html"))

@app.get("/users", include_in_schema=False)
async def serve_users():
    return FileResponse(os.path.join(WEB_DIR, "users.html"))

@app.get("/login", include_in_schema=False)
async def serve_login():
    return FileResponse(os.path.join(WEB_DIR, "login.html"))

# ═══════════════════════════════════════════════════════════════════════
# 시스템 및 인증 API
# ═══════════════════════════════════════════════════════════════════════

@app.post("/api/auth/login", response_model=Token, tags=["인증"])
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(UserAccount).filter(UserAccount.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/auth/me", response_model=UserAccountResponse, tags=["인증"])
def read_users_me(current_user: UserAccount = Depends(get_current_user)):
    return current_user


# ═══════════════════════════════════════════════════════════════════════
# 엑셀 템플릿 다운로드 API (개별 + 전체)
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/excel/template-types", tags=["데이터 수집"])
def get_template_types():
    """사용 가능한 엑셀 양식 종류 목록"""
    return [{"type": k, "label": v} for k, v in TEMPLATE_LABELS.items()]


@app.get("/api/excel/template/{template_type}", tags=["데이터 수집"])
def download_excel_template_by_type(template_type: str):
    """종류별 개별 엑셀 양식 다운로드"""
    try:
        output = generate_template(template_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    filename = urllib.parse.quote(get_template_filename(template_type))
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    return StreamingResponse(output, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/api/excel/template", tags=["데이터 수집"])
def download_excel_template():
    """전체 엑셀 양식 일괄 다운로드"""
    output = generate_template("all")
    filename = urllib.parse.quote(get_template_filename("all"))
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    return StreamingResponse(output, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ═══════════════════════════════════════════════════════════════════════
# 스냅샷 API
# ═══════════════════════════════════════════════════════════════════════


@app.post("/api/snapshot/manual", response_model=SystemSnapshotResponse, tags=["시스템 관리"])
def trigger_manual_snapshot(current_user: UserAccount = Depends(get_current_admin)):
    snapshot = create_snapshot(user_id=current_user.id, is_auto=False)
    if not snapshot:
        raise HTTPException(status_code=500, detail="스냅샷 생성 실패")
    return snapshot

@app.get("/api/snapshot/list", response_model=List[SystemSnapshotResponse], tags=["시스템 관리"])
def list_snapshots(db: Session = Depends(get_db), current_user: UserAccount = Depends(get_current_admin)):
    return db.query(SystemSnapshot).order_by(SystemSnapshot.created_at.desc()).limit(20).all()


# ═══════════════════════════════════════════════════════════════════════
# 사용자 관리 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/users", response_model=List[UserAccountResponse], tags=["사용자 관리"])
def get_users(db: Session = Depends(get_db)):
    """전체 사용자 목록 조회"""
    return db.query(UserAccount).all()


@app.post("/api/users", response_model=UserAccountResponse, tags=["사용자 관리"])
def create_user(user: UserAccountCreate, db: Session = Depends(get_db)):
    """사용자 계정 생성"""
    existing = db.query(UserAccount).filter(UserAccount.username == user.username).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"사용자 '{user.username}' 이미 존재")
    db_user = UserAccount(
        username=user.username,
        password_hash=get_password_hash(user.password),
        role=user.role,
        name=user.name,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


@app.delete("/api/users/{user_id}", response_model=MessageResponse, tags=["사용자 관리"])
def delete_user(user_id: int, db: Session = Depends(get_db)):
    """사용자 계정 삭제"""
    user = db.query(UserAccount).filter(UserAccount.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    if user.username == "admin":
        raise HTTPException(status_code=403, detail="기본 관리자 계정은 삭제할 수 없습니다")
    db.delete(user)
    db.commit()
    return MessageResponse(message="삭제 완료", detail=f"사용자 '{user.username}' 삭제됨")


# ═══════════════════════════════════════════════════════════════════════
# 상품 마스터 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/products", response_model=List[ProductMasterResponse], tags=["마스터 데이터"])
def get_products(db: Session = Depends(get_db)):
    """전체 상품 마스터 목록 조회"""
    return db.query(ProductMaster).all()


@app.post("/api/products", response_model=ProductMasterResponse, tags=["마스터 데이터"])
def create_product(product: ProductMasterCreate, db: Session = Depends(get_db)):
    """상품 마스터 등록"""
    existing = db.query(ProductMaster).filter(
        ProductMaster.product_code == product.product_code
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"품목코드 '{product.product_code}' 이미 존재")

    db_product = ProductMaster(**product.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


@app.get("/api/products/{product_id}", response_model=ProductMasterResponse, tags=["마스터 데이터"])
def get_product(product_id: int, db: Session = Depends(get_db)):
    """특정 상품 상세 조회"""
    product = db.query(ProductMaster).filter(ProductMaster.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다")
    return product


# ═══════════════════════════════════════════════════════════════════════
# 풀필먼트(창고) 마스터 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/ffc", response_model=List[FFCMasterResponse], tags=["마스터 데이터"])
def get_ffcs(db: Session = Depends(get_db)):
    """전체 창고 목록 조회"""
    return db.query(FFCMaster).all()


@app.post("/api/ffc", response_model=FFCMasterResponse, tags=["마스터 데이터"])
def create_ffc(ffc: FFCMasterCreate, db: Session = Depends(get_db)):
    """창고 등록"""
    existing = db.query(FFCMaster).filter(FFCMaster.ffc_code == ffc.ffc_code).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"창고코드 '{ffc.ffc_code}' 이미 존재")

    db_ffc = FFCMaster(**ffc.model_dump())
    db.add(db_ffc)
    db.commit()
    db.refresh(db_ffc)
    return db_ffc


@app.put("/api/ffc/{ffc_id}", response_model=FFCMasterResponse, tags=["마스터 데이터"])
def update_ffc(ffc_id: int, ffc: FFCMasterCreate, db: Session = Depends(get_db), current_user: UserAccount = Depends(get_current_admin)):
    """창고 수정 (ADMIN 전용)"""
    db_ffc = db.query(FFCMaster).filter(FFCMaster.id == ffc_id).first()
    if not db_ffc:
        raise HTTPException(status_code=404, detail="창고를 찾을 수 없습니다")
    db_ffc.ffc_name = ffc.ffc_name
    db_ffc.ffc_type = ffc.ffc_type
    db_ffc.allowed_expiry_days = ffc.allowed_expiry_days
    db_ffc.ffc_moq = ffc.ffc_moq
    db_ffc.avg_transport_cost = ffc.avg_transport_cost
    db.commit()
    db.refresh(db_ffc)
    return db_ffc


@app.delete("/api/ffc/{ffc_id}", response_model=MessageResponse, tags=["마스터 데이터"])
def delete_ffc(ffc_id: int, db: Session = Depends(get_db), current_user: UserAccount = Depends(get_current_admin)):
    """창고 삭제 (ADMIN 전용)"""
    db_ffc = db.query(FFCMaster).filter(FFCMaster.id == ffc_id).first()
    if not db_ffc:
        raise HTTPException(status_code=404, detail="창고를 찾을 수 없습니다")
    db.delete(db_ffc)
    db.commit()
    return MessageResponse(message="삭제 완료", detail=f"창고 '{db_ffc.ffc_name}' 삭제됨")


# ═══════════════════════════════════════════════════════════════════════
# 창고-상품별 이관 MOQ API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/ffc-product-moq", response_model=List[FFCProductMOQResponse], tags=["마스터 데이터"])
def get_ffc_product_moqs(
    ffc_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """SKU별 창고 이관 MOQ 조회"""
    query = db.query(FFCProductMOQ)
    if ffc_id:
        query = query.filter(FFCProductMOQ.ffc_id == ffc_id)
    return query.all()


@app.post("/api/ffc-product-moq", response_model=FFCProductMOQResponse, tags=["마스터 데이터"])
def upsert_ffc_product_moq(moq: FFCProductMOQCreate, db: Session = Depends(get_db)):
    """SKU별 이관 MOQ 등록/수정 (Upsert)"""
    existing = db.query(FFCProductMOQ).filter(
        FFCProductMOQ.ffc_id == moq.ffc_id,
        FFCProductMOQ.product_id == moq.product_id,
    ).first()
    if existing:
        existing.transfer_moq = moq.transfer_moq
        db.commit()
        db.refresh(existing)
        return existing
    else:
        db_moq = FFCProductMOQ(**moq.model_dump())
        db.add(db_moq)
        db.commit()
        db.refresh(db_moq)
        return db_moq


# ═══════════════════════════════════════════════════════════════════════
# 현재고 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/inventory", response_model=List[CurrentInventoryResponse], tags=["재고 관리"])
def get_inventory(
    ffc_id: Optional[int] = Query(None, description="창고 ID 필터"),
    db: Session = Depends(get_db),
):
    """현재고 목록 조회 (창고별 필터 지원)"""
    query = db.query(CurrentInventory)
    if ffc_id:
        query = query.filter(CurrentInventory.ffc_id == ffc_id)
    return query.all()


@app.get("/api/inventory/summary", tags=["재고 관리"])
def get_inventory_summary(db: Session = Depends(get_db)):
    """전체 현재고 요약 (창고별, 상품별 집계)"""
    inventories = db.query(CurrentInventory).all()
    ffcs = {f.id: f for f in db.query(FFCMaster).all()}
    products = {p.id: p for p in db.query(ProductMaster).all()}
    inbounds = {i.inbound_id: i for i in db.query(InboundList).all()}

    summary_by_ffc = {}
    for inv in inventories:
        ffc = ffcs.get(inv.ffc_id)
        inbound = inbounds.get(inv.inbound_id)
        if not ffc or not inbound:
            continue
        product = products.get(inbound.product_id)
        if not product:
            continue

        ffc_key = ffc.id
        if ffc_key not in summary_by_ffc:
            summary_by_ffc[ffc_key] = {
                "ffc_id": ffc.id,
                "ffc_code": ffc.ffc_code,
                "ffc_name": ffc.ffc_name,
                "ffc_type": ffc.ffc_type,
                "products": {},
                "total_qty": 0,
                "total_value": 0,
            }

        prod_key = product.id
        if prod_key not in summary_by_ffc[ffc_key]["products"]:
            summary_by_ffc[ffc_key]["products"][prod_key] = {
                "product_id": product.id,
                "product_code": product.product_code,
                "product_name": product.product_name,
                "total_qty": 0,
                "total_value": 0,
                "batches": [],
            }

        value = calc_inventory_value(inv.current_can_qty, product.fixed_unit_price, inbound.exchange_rate)
        remaining_days = calc_remaining_expiry_days(inbound.expiry_date) if inbound.expiry_date else None

        summary_by_ffc[ffc_key]["products"][prod_key]["total_qty"] += inv.current_can_qty
        summary_by_ffc[ffc_key]["products"][prod_key]["total_value"] += value
        summary_by_ffc[ffc_key]["products"][prod_key]["batches"].append({
            "inventory_id": inv.inventory_id,
            "can_qty": inv.current_can_qty,
            "expiry_date": inbound.expiry_date,
            "remaining_days": remaining_days,
            "value": value,
        })
        summary_by_ffc[ffc_key]["total_qty"] += inv.current_can_qty
        summary_by_ffc[ffc_key]["total_value"] += value

    # products를 list로 변환
    result = []
    for ffc_data in summary_by_ffc.values():
        ffc_data["products"] = list(ffc_data["products"].values())
        result.append(ffc_data)

    return result


@app.get("/api/inventory/transfer-recommendations", tags=["재고 관리"])
def get_transfer_recommendations(db: Session = Depends(get_db)):
    """용인창고(HUB) 재고 기반 이관 추천 계산"""
    # HUB 창고 찾기 (ffc_type이 OFFLINE이고 첫번째이거나, ffc_code가 HUB)
    hub = db.query(FFCMaster).filter(FFCMaster.ffc_code == "HUB").first()
    if not hub:
        # HUB가 없으면 첫 번째 OFFLINE 창고를 HUB로 간주
        hub = db.query(FFCMaster).filter(FFCMaster.ffc_type == "OFFLINE").first()
    if not hub:
        return []

    # 다른 풀필먼트 창고들
    other_ffcs = db.query(FFCMaster).filter(FFCMaster.id != hub.id).all()
    if not other_ffcs:
        return []

    products = {p.id: p for p in db.query(ProductMaster).all()}
    inventories = db.query(CurrentInventory).all()
    inbounds = {i.inbound_id: i for i in db.query(InboundList).all()}

    # 창고별 이관 MOQ
    moqs = db.query(FFCProductMOQ).all()
    moq_map = {(m.ffc_id, m.product_id): m.transfer_moq for m in moqs}

    # HUB 재고 집계 (상품별)
    hub_stock = {}
    for inv in inventories:
        if inv.ffc_id == hub.id:
            inbound = inbounds.get(inv.inbound_id)
            if inbound:
                pid = inbound.product_id
                hub_stock[pid] = hub_stock.get(pid, 0) + inv.current_can_qty

    # 각 풀필먼트 창고별 출고 속도 계산 (직전 12주 평균)
    outflow_data = db.query(OutflowHistory).all()
    ffc_product_outflow = {}
    for of in outflow_data:
        key = (of.ffc_id, of.product_id)
        if key not in ffc_product_outflow:
            ffc_product_outflow[key] = []
        ffc_product_outflow[key].append(of.simple_outflow_qty)

    recommendations = []
    for ffc in other_ffcs:
        for pid, product in products.items():
            # 해당 창고의 현재 재고
            ffc_stock = sum(inv.current_can_qty for inv in inventories
                          if inv.ffc_id == ffc.id and inbounds.get(inv.inbound_id, None)
                          and inbounds[inv.inbound_id].product_id == pid)

            # 주당 출고량 평균
            outflows = ffc_product_outflow.get((ffc.id, pid), [])
            weekly_avg = calc_weekly_smoothing_constant(outflows) if outflows else 0

            if weekly_avg <= 0:
                continue

            # 현재 재고가 몇 주 버틸 수 있는지
            weeks_remaining = ffc_stock / weekly_avg if weekly_avg > 0 else float('inf')

            # 4주 이내로 소진 예상이면 이관 추천
            if weeks_remaining < 4:
                # 추천 수량: 8주치 확보
                suggested_qty = max(0, int(weekly_avg * 8 - ffc_stock))

                # MOQ 적용
                transfer_moq = moq_map.get((ffc.id, pid), ffc.ffc_moq)
                if transfer_moq > 0 and suggested_qty > 0:
                    import math
                    suggested_qty = math.ceil(suggested_qty / transfer_moq) * transfer_moq

                # HUB에 충분한 재고가 있는지 확인
                hub_available = hub_stock.get(pid, 0)
                if suggested_qty > hub_available:
                    suggested_qty = hub_available

                if suggested_qty <= 0:
                    continue

                # 이관 추천일 (재고 소진 예상일 2주 전)
                from datetime import date, timedelta
                transfer_date = date.today() + timedelta(weeks=max(0, int(weeks_remaining) - 2))

                recommendations.append({
                    "ffc_id": ffc.id,
                    "ffc_code": ffc.ffc_code,
                    "ffc_name": ffc.ffc_name,
                    "product_id": pid,
                    "product_code": product.product_code,
                    "product_name": product.product_name,
                    "current_stock": ffc_stock,
                    "weekly_avg_outflow": round(weekly_avg, 1),
                    "weeks_remaining": round(weeks_remaining, 1),
                    "suggested_qty": suggested_qty,
                    "transfer_moq": transfer_moq,
                    "recommended_date": transfer_date.isoformat(),
                    "hub_available": hub_available,
                })

    return recommendations


@app.post("/api/inventory/upload", response_model=FileUploadResponse, tags=["재고 관리"])
async def upload_inventory(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """현재고 엑셀 일괄 업로드"""
    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="xlsx 파일만 업로드 가능합니다")

    # 파일 저장
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved_filename = f"{timestamp}_inventory_{file.filename}"
    saved_path = os.path.join(BACKUP_DIR, saved_filename)

    content = await file.read()
    with open(saved_path, "wb") as f:
        f.write(content)

    # 파싱
    try:
        items = parse_inventory_excel(saved_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not items:
        raise HTTPException(status_code=400, detail="유효한 데이터가 없습니다. 양식을 확인해주세요.")

    # DB 적재
    inserted = 0
    updated = 0
    for item in items:
        # 창고 코드로 ffc_id 조회
        ffc = db.query(FFCMaster).filter(FFCMaster.ffc_code == item["ffc_code"]).first()
        if not ffc:
            continue

        # 품목 코드로 product_id 조회
        product = db.query(ProductMaster).filter(ProductMaster.product_code == item["product_code"]).first()
        if not product:
            continue

        # inbound 매칭 (유통기한 기준 또는 최신 입고건)
        inbound_query = db.query(InboundList).filter(InboundList.product_id == product.id)
        if item.get("expiry_date"):
            inbound = inbound_query.filter(InboundList.expiry_date == item["expiry_date"]).first()
        else:
            inbound = inbound_query.order_by(InboundList.inbound_id.desc()).first()

        if not inbound:
            # inbound가 없으면 가상 입고건 생성 (현재고만 등록하는 경우)
            inbound = InboundList(
                production_ym_code="DIRECT",
                order_code="DIRECT",
                invoice_no="DIRECT-UPLOAD",
                bl_no="DIRECT",
                product_id=product.id,
                tu_qty=0,
                actual_can_qty=item["qty"],
                manufactured_date="N/A",
                expiry_date=item.get("expiry_date") or "2099-12-31",
                exchange_rate=1.0,
            )
            db.add(inbound)
            db.flush()

        # 기존 재고 확인 (같은 창고, 같은 inbound)
        existing_inv = db.query(CurrentInventory).filter(
            CurrentInventory.ffc_id == ffc.id,
            CurrentInventory.inbound_id == inbound.inbound_id,
        ).first()

        if existing_inv:
            existing_inv.current_can_qty = item["qty"]
            existing_inv.last_updated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            updated += 1
        else:
            new_inv = CurrentInventory(
                ffc_id=ffc.id,
                inbound_id=inbound.inbound_id,
                current_can_qty=item["qty"],
                last_updated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            db.add(new_inv)
            inserted += 1

    db.commit()
    return FileUploadResponse(
        message="현재고 업로드 완료",
        filename=file.filename,
        rows_processed=len(items),
        rows_inserted=inserted,
        rows_updated=updated,
    )


# ═══════════════════════════════════════════════════════════════════════
# 입고 리스트 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/inbound", response_model=List[InboundListResponse], tags=["입고 관리"])
def get_inbound_list(db: Session = Depends(get_db)):
    """전체 입고 리스트 조회"""
    return db.query(InboundList).all()


# ═══════════════════════════════════════════════════════════════════════
# 입고 예정 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/expected-inbound", response_model=List[ExpectedInboundResponse], tags=["입고 관리"])
def get_expected_inbound(db: Session = Depends(get_db)):
    """입고 예정 리스트 조회"""
    return db.query(ExpectedInbound).all()


# ═══════════════════════════════════════════════════════════════════════
# 출고 이력 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/outflow", response_model=List[OutflowHistoryResponse], tags=["출고 관리"])
def get_outflow_history(
    product_id: Optional[int] = Query(None),
    ffc_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """출고 이력 조회 (품목/창고 필터 지원)"""
    query = db.query(OutflowHistory)
    if product_id:
        query = query.filter(OutflowHistory.product_id == product_id)
    if ffc_id:
        query = query.filter(OutflowHistory.ffc_id == ffc_id)
    return query.order_by(OutflowHistory.base_date.desc()).all()


# ═══════════════════════════════════════════════════════════════════════
# 발주 계획 API (재설계)
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/order-plan", response_model=List[MonthlyOrderPlanResponse], tags=["발주 계획"])
def get_order_plans(
    target_month: Optional[str] = Query(None, description="대상 연월 (YYYY-MM)"),
    db: Session = Depends(get_db),
):
    """월별 발주 계획 조회"""
    query = db.query(MonthlyOrderPlan)
    if target_month:
        query = query.filter(MonthlyOrderPlan.target_month == target_month)
    return query.all()


@app.post("/api/order-plan/save", response_model=MessageResponse, tags=["발주 계획"])
def save_order_plan(plan: MonthlyOrderPlanUpdate, plan_id: int = Query(...), db: Session = Depends(get_db)):
    """
    발주 계획 실무자 수정 저장
    - SQLite 영구 수정 적재
    """
    db_plan = db.query(MonthlyOrderPlan).filter(MonthlyOrderPlan.plan_id == plan_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="발주 계획을 찾을 수 없습니다")

    db_plan.user_modified_qty = plan.user_modified_qty
    db_plan.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.commit()
    return MessageResponse(message="발주 계획이 저장되었습니다", detail=f"plan_id={plan_id}")


@app.post("/api/order-plan/bulk-save", response_model=MessageResponse, tags=["발주 계획"])
def bulk_save_order_plan(data: OrderPlanBulkSave, db: Session = Depends(get_db)):
    """여러 품목의 발주 수량을 한꺼번에 저장 (Upsert + 낙관적 잠금)"""
    saved = 0
    for item in data.plans:
        existing = db.query(MonthlyOrderPlan).filter(
            MonthlyOrderPlan.target_month == item.target_month,
            MonthlyOrderPlan.product_id == item.product_id,
        ).first()

        if existing:
            # 낙관적 잠금: 클라이언트가 보낸 version과 DB version 비교
            if hasattr(item, 'version') and item.version and existing.version and existing.version != item.version:
                raise HTTPException(
                    status_code=409,
                    detail=f"다른 사용자가 이미 수정했습니다 (품목 ID: {item.product_id}). 새로고침 후 다시 시도하세요."
                )
            existing.user_modified_qty = item.user_modified_qty
            existing.version = (existing.version or 1) + 1
            existing.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            new_plan = MonthlyOrderPlan(
                target_month=item.target_month,
                product_id=item.product_id,
                system_suggested_qty=item.user_modified_qty,
                user_modified_qty=item.user_modified_qty,
                version=1,
                updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
            db.add(new_plan)
        saved += 1

    db.commit()
    return MessageResponse(message=f"{saved}건 발주 계획 저장 완료")


@app.get("/api/order-plan/simulation", tags=["발주 계획"])
def get_order_plan_simulation(
    weight_factor: float = Query(default=1.0, ge=0.5, le=2.0),
    db: Session = Depends(get_db),
):
    """
    6개월(24주) 시뮬레이션 데이터 - 품목별
    현재고, 입고예정, 출고량, 포캐스팅 데이터를 24주 타임라인으로 반환
    """
    products = db.query(ProductMaster).all()
    inventories = db.query(CurrentInventory).all()
    inbounds = {i.inbound_id: i for i in db.query(InboundList).all()}
    expected = db.query(ExpectedInbound).all()
    outflows = db.query(OutflowHistory).all()

    result = []
    for product in products:
        # 현재 총 재고
        total_stock = sum(
            inv.current_can_qty for inv in inventories
            if inbounds.get(inv.inbound_id) and inbounds[inv.inbound_id].product_id == product.id
        )

        # 출고 데이터 (직전 12주)
        product_outflows = sorted(
            [o for o in outflows if o.product_id == product.id],
            key=lambda x: x.base_date
        )
        outflow_values = [o.simple_outflow_qty for o in product_outflows]

        smoothing = calc_weekly_smoothing_constant(outflow_values)
        loss_buffer = 0  # 순수 판매 데이터가 별도 없으므로 0으로 처리

        # 입고 예정 데이터를 주차별로 매핑
        from datetime import date, timedelta
        today = date.today()
        expected_by_week = {}
        for ei in expected:
            if ei.product_id == product.id:
                try:
                    eta = date.fromisoformat(ei.eta_date)
                    weeks_from_now = max(1, (eta - today).days // 7)
                    if 1 <= weeks_from_now <= 24:
                        expected_by_week[weeks_from_now] = expected_by_week.get(weeks_from_now, 0) + ei.expected_qty
                except:
                    pass

        # 시뮬레이션 실행
        simulation = simulate_future_inventory(
            current_stock=total_stock,
            smoothing_constant=smoothing,
            loss_buffer=loss_buffer,
            pipeline_inbounds={},
            expected_inbounds=expected_by_week,
            weight_factor=weight_factor,
            weeks=24,
        )

        # 발주 제안 수량 계산
        suggested_qty = 0
        if simulation and simulation[-1]["ending_stock"] < smoothing * 6:
            shortage = smoothing * 6 - simulation[-1]["ending_stock"]
            suggested_qty = calc_order_suggestion(shortage, product.hub_moq)

        # 기존 저장된 발주 계획 조회
        from datetime import datetime as dt
        target_month = (today + timedelta(weeks=24)).strftime("%Y-%m")
        saved_plan = db.query(MonthlyOrderPlan).filter(
            MonthlyOrderPlan.product_id == product.id,
            MonthlyOrderPlan.target_month == target_month,
        ).first()

        result.append({
            "product_id": product.id,
            "product_code": product.product_code,
            "product_name": product.product_name,
            "hub_moq": product.hub_moq,
            "current_stock": total_stock,
            "weekly_avg_outflow": round(smoothing, 1),
            "simulation": simulation,
            "suggested_qty": suggested_qty,
            "target_month": target_month,
            "saved_qty": saved_plan.user_modified_qty if saved_plan else None,
            "version": saved_plan.version if saved_plan else 1,
        })

    return result


@app.get("/api/order-plan/export", tags=["발주 계획"])
def export_order_plan(db: Session = Depends(get_db)):
    """발주 계획 엑셀 다운로드"""
    plans = db.query(MonthlyOrderPlan).all()
    products = {p.id: p for p in db.query(ProductMaster).all()}

    plan_data = []
    for plan in plans:
        product = products.get(plan.product_id)
        plan_data.append({
            "target_month": plan.target_month,
            "product_code": product.product_code if product else "N/A",
            "product_name": product.product_name if product else "N/A",
            "system_suggested_qty": plan.system_suggested_qty,
            "user_modified_qty": plan.user_modified_qty,
        })

    output = generate_order_plan_export(plan_data)
    filename = urllib.parse.quote("발주계획_내보내기.xlsx")
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    return StreamingResponse(output, headers=headers, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ═══════════════════════════════════════════════════════════════════════
# 시스템 상태 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/health", response_model=MessageResponse, tags=["시스템"])
def health_check():
    """서버 상태 확인"""
    return MessageResponse(message="OK", detail="SCM ERP 서버가 정상 가동 중입니다.")


# ═══════════════════════════════════════════════════════════════════════
# 판매 실적 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/sales", response_model=List[SalesHistoryResponse], tags=["판매 실적"])
def get_sales(
    product_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """판매 실적 조회"""
    query = db.query(SalesHistory)
    if product_id:
        query = query.filter(SalesHistory.product_id == product_id)
    return query.order_by(SalesHistory.base_date.desc()).all()


@app.post("/api/sales", response_model=SalesHistoryResponse, tags=["판매 실적"])
def create_sales(sales: SalesHistoryCreate, db: Session = Depends(get_db)):
    """판매 실적 등록"""
    db_sales = SalesHistory(
        **sales.model_dump(),
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    db.add(db_sales)
    db.commit()
    db.refresh(db_sales)
    return db_sales


# ═══════════════════════════════════════════════════════════════════════
# 입고 관리 3분리 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/inbound/order-qty", response_model=List[OrderQuantityResponse], tags=["입고 관리"])
def get_order_quantities(db: Session = Depends(get_db)):
    """발주수량 목록 조회"""
    return db.query(OrderQuantity).order_by(OrderQuantity.id.desc()).all()


@app.post("/api/inbound/order-qty", response_model=OrderQuantityResponse, tags=["입고 관리"])
def create_order_quantity(oq: OrderQuantityCreate, db: Session = Depends(get_db)):
    """발주수량 등록"""
    db_oq = OrderQuantity(
        **oq.model_dump(),
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    db.add(db_oq)
    db.commit()
    db.refresh(db_oq)
    return db_oq


@app.get("/api/inbound/production", response_model=List[ProductionCompleteResponse], tags=["입고 관리"])
def get_production_complete(db: Session = Depends(get_db)):
    """생산완료수량 목록 조회"""
    return db.query(ProductionComplete).order_by(ProductionComplete.id.desc()).all()


@app.post("/api/inbound/production", response_model=ProductionCompleteResponse, tags=["입고 관리"])
def create_production_complete(pc: ProductionCompleteCreate, db: Session = Depends(get_db)):
    """생산완료수량 등록"""
    db_pc = ProductionComplete(
        **pc.model_dump(),
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    db.add(db_pc)
    db.commit()
    db.refresh(db_pc)
    return db_pc


@app.get("/api/inbound/invoice", response_model=List[InvoiceQuantityResponse], tags=["입고 관리"])
def get_invoice_quantities(db: Session = Depends(get_db)):
    """인보이스수량 목록 조회"""
    return db.query(InvoiceQuantity).order_by(InvoiceQuantity.id.desc()).all()


@app.post("/api/inbound/invoice", response_model=InvoiceQuantityResponse, tags=["입고 관리"])
def create_invoice_quantity(iq: InvoiceQuantityCreate, db: Session = Depends(get_db)):
    """인보이스수량 등록"""
    db_iq = InvoiceQuantity(
        **iq.model_dump(),
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    db.add(db_iq)
    db.commit()
    db.refresh(db_iq)
    return db_iq


@app.get("/api/inbound/pending-matches", response_model=PendingMatchesResponse, tags=["입고 관리"])
def get_pending_matches(db: Session = Depends(get_db)):
    """미매칭 항목 수 조회 (메인 요약 할일 위젯용)"""
    pending_prod = db.query(ProductionComplete).filter(
        ProductionComplete.match_status == "PENDING"
    ).count()
    pending_inv = db.query(InvoiceQuantity).filter(
        InvoiceQuantity.match_status == "PENDING"
    ).count()
    return PendingMatchesResponse(
        pending_count=pending_prod + pending_inv,
        pending_production=pending_prod,
        pending_invoice=pending_inv,
    )


@app.post("/api/inbound/auto-match", response_model=MessageResponse, tags=["입고 관리"])
def run_auto_match(db: Session = Depends(get_db)):
    """자동 매칭 실행 — 상품코드+세일즈오더+생산년월 완벽 일치 기준"""
    matched_count = 0

    # 1) 생산완료 → 발주수량 매칭
    pending_prods = db.query(ProductionComplete).filter(
        ProductionComplete.match_status == "PENDING"
    ).all()
    for prod in pending_prods:
        order = db.query(OrderQuantity).filter(
            OrderQuantity.product_id == prod.product_id,
            OrderQuantity.sales_order_no == prod.sales_order_no,
        ).first()
        if order:
            prod.match_status = "MATCHED"
            prod.matched_order_id = order.id
            matched_count += 1

    # 2) 인보이스 → 생산완료 매칭
    pending_invs = db.query(InvoiceQuantity).filter(
        InvoiceQuantity.match_status == "PENDING"
    ).all()
    for inv in pending_invs:
        prod = db.query(ProductionComplete).filter(
            ProductionComplete.product_id == inv.product_id,
            ProductionComplete.sales_order_no == inv.sales_order_no,
            ProductionComplete.production_ym_no == inv.production_ym_no,
        ).first()
        if prod:
            inv.match_status = "MATCHED"
            inv.matched_production_id = prod.id
            matched_count += 1

    db.commit()
    return MessageResponse(
        message=f"자동 매칭 완료: {matched_count}건 매칭됨",
        detail=f"생산완료 {len(pending_prods)}건 중, 인보이스 {len(pending_invs)}건 중 검사"
    )

