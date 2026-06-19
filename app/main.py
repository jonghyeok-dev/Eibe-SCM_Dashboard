"""
FastAPI 메인 엔드포인트 및 라우팅 제어 모듈 (v3.0)
- 3NF 관계형 스키마 기반 전면 재작성
- 입고 파이프라인: 발주 → 생산 → 인보이스 → 입고
- 정적 파일 서빙 (web/ 디렉토리)
"""

import os
import io
import math
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import urllib.parse

from app.database import get_db, init_db, BASE_DIR, BACKUP_DIR

# ── 모델 임포트 (새 3NF 스키마) ──────────────────────────────────────
from app.models import (
    ProductDB,
    WarehouseDB,
    WarehouseProductMOQ,
    LogisticsCostDB,
    OrderDB,
    ProductionDB,
    InvoiceDB,
    InboundDB,
    InventorySnapshot,
    OutflowHistory,
    TransferPlan,
    MonthlyOrderPlan,
    SalesHistory,
    UserAccount,
    SystemSnapshot,
)

# ── 스키마 임포트 ────────────────────────────────────────────────────
from app.schemas import (
    # 공통
    MessageResponse,
    # 인증 / 시스템
    Token,
    UserAccountCreate,
    UserAccountResponse,
    SystemSnapshotResponse,
    # 품목
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    # 창고
    WarehouseCreate,
    WarehouseUpdate,
    WarehouseResponse,
    # 물류비
    LogisticsCostCreate,
    LogisticsCostResponse,
    # 창고-품목 MOQ
    WarehouseProductMOQCreate,
    WarehouseProductMOQResponse,
    # 발주
    OrderCreate,
    OrderResponse,
    # 생산
    ProductionCreate,
    ProductionResponse,
    # 인보이스
    InvoiceCreate,
    InvoiceResponse,
    # 입고
    InboundCreate,
    InboundResponse,
    # 현재고 스냅샷
    InventorySnapshotCreate,
    InventorySnapshotResponse,
    # 이관 계획
    TransferPlanCreate,
    TransferPlanResponse,
    # 발주 계획
    OrderPlanCreate,
    OrderPlanBulkSave,
    OrderPlanResponse,
    # 매칭
    MatchRequest,
    MatchResponse,
)

from app.core.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    get_current_user,
    get_current_admin,
)
from app.core.snapshot import start_scheduler, stop_scheduler, create_snapshot

# ── 엑셀 파서 (기존 모듈 — 호환 래핑) ─────────────────────────────────
try:
    from app.core.excel_parser import (
        generate_template,
        get_template_filename,
        parse_inventory_excel,
        generate_order_plan_export,
        TEMPLATE_LABELS,
    )
    _EXCEL_PARSER_AVAILABLE = True
except Exception:
    _EXCEL_PARSER_AVAILABLE = False
    TEMPLATE_LABELS = {}

# ── 포캐스팅 (기존 모듈 — 호환 래핑) ─────────────────────────────────
try:
    from app.core.forecasting import (
        calc_weekly_smoothing_constant,
        calc_dynamic_loss_buffer,
        simulate_future_inventory,
        calc_order_suggestion,
        calc_remaining_expiry_days,
        calc_inventory_value,
        check_air_shipment_trigger,
    )
    _FORECASTING_AVAILABLE = True
except Exception:
    _FORECASTING_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════
# 애플리케이션 수명주기
# ═══════════════════════════════════════════════════════════════════════


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 DB 테이블 자동 생성 및 기본 관리자 계정 초기화"""
    init_db()
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        admin = db.query(UserAccount).filter(UserAccount.username == "admin").first()
        if not admin:
            pw_hash = get_password_hash("admin")
            db.add(
                UserAccount(
                    username="admin",
                    password_hash=pw_hash,
                    role="ADMIN",
                    name="시스템 관리자",
                )
            )
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
    description="독립형 로컬 SCM ERP 시스템 — 3NF 관계형 스키마 v3",
    version="3.0.0",
    lifespan=lifespan,
)


# ── 정적 파일 서빙 설정 ──────────────────────────────────────────────
WEB_DIR = os.path.join(BASE_DIR, "web")
STATIC_DIR = os.path.join(WEB_DIR, "static")

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


@app.get("/inventory/transfer", include_in_schema=False)
async def serve_inventory_transfer():
    """이관 계획 페이지 — inventory.html의 이관 탭으로 라우팅"""
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
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
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
# 시스템 상태
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/health", response_model=MessageResponse, tags=["시스템"])
def health_check():
    """서버 상태 확인"""
    return MessageResponse(message="OK", detail="SCM ERP 서버가 정상 가동 중입니다.")


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
def list_snapshots(
    db: Session = Depends(get_db),
    current_user: UserAccount = Depends(get_current_admin),
):
    return db.query(SystemSnapshot).order_by(SystemSnapshot.created_at.desc()).limit(20).all()


# ═══════════════════════════════════════════════════════════════════════
# 사용자 관리 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/users", response_model=List[UserAccountResponse], tags=["사용자 관리"])
def get_users(db: Session = Depends(get_db)):
    """전체 사용자 목록 조회"""
    return db.query(UserAccount).all()


@app.post("/api/users", response_model=UserAccountResponse, tags=["사용자 관리"])
def create_user(
    user: UserAccountCreate,
    admin: UserAccount = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """사용자 계정 생성 (ADMIN 전용)"""
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


@app.put("/api/users/{user_id}", response_model=MessageResponse, tags=["사용자 관리"])
def update_user(
    user_id: int,
    data: dict,
    admin: UserAccount = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """사용자 정보 수정 (비밀번호/역할/이름)"""
    user = db.query(UserAccount).filter(UserAccount.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    if "password" in data and data["password"]:
        user.password_hash = get_password_hash(data["password"])
    if "name" in data:
        user.name = data["name"]
    if "role" in data and data["role"] in ("ADMIN", "OPERATOR"):
        user.role = data["role"]
    db.commit()
    return MessageResponse(message="사용자 정보가 수정되었습니다")


@app.delete("/api/users/{user_id}", response_model=MessageResponse, tags=["사용자 관리"])
def delete_user(
    user_id: int,
    admin: UserAccount = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """사용자 계정 삭제 (ADMIN 전용)"""
    user = db.query(UserAccount).filter(UserAccount.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다")
    if user.username == "admin":
        raise HTTPException(status_code=403, detail="기본 관리자 계정은 삭제할 수 없습니다")
    db.delete(user)
    db.commit()
    return MessageResponse(message="삭제 완료", detail=f"사용자 '{user.username}' 삭제됨")


# ═══════════════════════════════════════════════════════════════════════
# 품목 DB API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/products", response_model=List[ProductResponse], tags=["기준 정보"])
def get_products(db: Session = Depends(get_db)):
    """전체 품목 목록 조회"""
    return db.query(ProductDB).all()


@app.post("/api/products", response_model=ProductResponse, tags=["기준 정보"])
def create_product(
    product: ProductCreate,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """품목 등록 — product_code는 생성 후 수정 불가"""
    existing = db.query(ProductDB).filter(ProductDB.product_code == product.product_code).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"품목코드 '{product.product_code}' 이미 존재")
    db_product = ProductDB(**product.model_dump())
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product


@app.put("/api/products/{product_id}", response_model=ProductResponse, tags=["기준 정보"])
def update_product(
    product_id: int,
    product: ProductUpdate,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """품목 수정 — product_code는 변경 불가"""
    db_product = db.query(ProductDB).filter(ProductDB.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="품목을 찾을 수 없습니다")
    update_data = product.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_product, key, value)
    db.commit()
    db.refresh(db_product)
    return db_product


@app.delete("/api/products/{product_id}", response_model=MessageResponse, tags=["기준 정보"])
def delete_product(
    product_id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """품목 삭제"""
    db_product = db.query(ProductDB).filter(ProductDB.id == product_id).first()
    if not db_product:
        raise HTTPException(status_code=404, detail="품목을 찾을 수 없습니다")
    db.delete(db_product)
    db.commit()
    return MessageResponse(message="품목 삭제 완료", detail=f"'{db_product.product_name}' 삭제됨")


@app.get("/api/products/{product_id}", response_model=ProductResponse, tags=["기준 정보"])
def get_product(product_id: int, db: Session = Depends(get_db)):
    """특정 품목 상세 조회"""
    product = db.query(ProductDB).filter(ProductDB.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="품목을 찾을 수 없습니다")
    return product


@app.post("/api/products/upload", response_model=MessageResponse, tags=["기준 정보"])
def upload_products(
    file: UploadFile = File(...),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """품목 엑셀 업로드 (일괄 등록/갱신)"""
    import pandas as pd

    content = file.file.read()
    try:
        df = pd.read_excel(io.BytesIO(content))
    except Exception:
        raise HTTPException(status_code=400, detail="엑셀 파일을 읽을 수 없습니다")

    required_cols = {"product_code", "product_name"}
    if not required_cols.issubset(set(df.columns)):
        raise HTTPException(status_code=400, detail=f"필수 컬럼 누락: {required_cols - set(df.columns)}")

    created, updated = 0, 0
    for _, row in df.iterrows():
        code = str(row["product_code"]).strip()
        if not code:
            continue
        existing = db.query(ProductDB).filter(ProductDB.product_code == code).first()
        qty_col = (
            "pack_qty_per_tu"
            if "pack_qty_per_tu" in df.columns
            else "pcs_per_carton"
            if "pcs_per_carton" in df.columns
            else None
        )
        if existing:
            existing.product_name = str(row.get("product_name", existing.product_name)).strip()
            if qty_col and pd.notna(row.get(qty_col)):
                existing.pack_qty_per_tu = int(row[qty_col])
            if "currency_unit" in df.columns and pd.notna(row.get("currency_unit")):
                existing.currency_unit = str(row["currency_unit"]).strip()
            if "purchase_price" in df.columns and pd.notna(row.get("purchase_price")):
                existing.purchase_price = float(row["purchase_price"])
            updated += 1
        else:
            new_product = ProductDB(
                product_code=code,
                product_name=str(row.get("product_name", "")).strip(),
                pack_qty_per_tu=(
                    int(row.get(qty_col, 24)) if qty_col and pd.notna(row.get(qty_col)) else 24
                ),
                currency_unit=(
                    str(row["currency_unit"]).strip()
                    if "currency_unit" in df.columns and pd.notna(row.get("currency_unit"))
                    else "USD"
                ),
                purchase_price=(
                    float(row["purchase_price"])
                    if "purchase_price" in df.columns and pd.notna(row.get("purchase_price"))
                    else 0
                ),
            )
            db.add(new_product)
            created += 1
    db.commit()
    return MessageResponse(message=f"업로드 완료: {created}건 신규, {updated}건 갱신")


# ═══════════════════════════════════════════════════════════════════════
# 창고 DB API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/warehouses", response_model=List[WarehouseResponse], tags=["기준 정보"])
def get_warehouses(db: Session = Depends(get_db)):
    """전체 창고 목록 조회"""
    return db.query(WarehouseDB).all()


@app.post("/api/warehouses", response_model=WarehouseResponse, tags=["기준 정보"])
def create_warehouse(
    wh: WarehouseCreate,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """창고 등록 — id 자동생성, warehouse_name 수정 불가"""
    existing = db.query(WarehouseDB).filter(WarehouseDB.warehouse_name == wh.warehouse_name).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"창고명 '{wh.warehouse_name}' 이미 존재")
    db_wh = WarehouseDB(**wh.model_dump())
    db.add(db_wh)
    db.commit()
    db.refresh(db_wh)
    return db_wh


@app.put("/api/warehouses/{wh_id}", response_model=WarehouseResponse, tags=["기준 정보"])
def update_warehouse(
    wh_id: int,
    wh: WarehouseUpdate,
    current_user: UserAccount = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """창고 수정 — warehouse_name은 변경 불가 (ADMIN 전용)"""
    db_wh = db.query(WarehouseDB).filter(WarehouseDB.id == wh_id).first()
    if not db_wh:
        raise HTTPException(status_code=404, detail="창고를 찾을 수 없습니다")
    update_data = wh.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_wh, key, value)
    db.commit()
    db.refresh(db_wh)
    return db_wh


@app.delete("/api/warehouses/{wh_id}", response_model=MessageResponse, tags=["기준 정보"])
def delete_warehouse(
    wh_id: int,
    current_user: UserAccount = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """창고 삭제 (ADMIN 전용)"""
    db_wh = db.query(WarehouseDB).filter(WarehouseDB.id == wh_id).first()
    if not db_wh:
        raise HTTPException(status_code=404, detail="창고를 찾을 수 없습니다")
    db.delete(db_wh)
    db.commit()
    return MessageResponse(message="삭제 완료", detail=f"창고 '{db_wh.warehouse_name}' 삭제됨")


# ═══════════════════════════════════════════════════════════════════════
# 물류비 DB API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/logistics-cost", response_model=List[LogisticsCostResponse], tags=["기준 정보"])
def get_logistics_costs(db: Session = Depends(get_db)):
    """물류비 단가 목록 조회"""
    costs = db.query(LogisticsCostDB).all()
    result = []
    for c in costs:
        dep = db.query(WarehouseDB).filter(WarehouseDB.id == c.departure_wh_id).first()
        arr = db.query(WarehouseDB).filter(WarehouseDB.id == c.arrival_wh_id).first()
        result.append(
            LogisticsCostResponse(
                departure_wh_id=c.departure_wh_id,
                arrival_wh_id=c.arrival_wh_id,
                cost_per_tu=c.cost_per_tu,
                departure_name=dep.warehouse_name if dep else None,
                arrival_name=arr.warehouse_name if arr else None,
            )
        )
    return result


@app.post("/api/logistics-cost", response_model=MessageResponse, tags=["기준 정보"])
def upsert_logistics_cost(
    cost: LogisticsCostCreate,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """물류비 단가 등록/수정 (Upsert)"""
    existing = (
        db.query(LogisticsCostDB)
        .filter(
            LogisticsCostDB.departure_wh_id == cost.departure_wh_id,
            LogisticsCostDB.arrival_wh_id == cost.arrival_wh_id,
        )
        .first()
    )
    if existing:
        existing.cost_per_tu = cost.cost_per_tu
        db.commit()
        return MessageResponse(message="물류비 단가가 수정되었습니다")
    else:
        new_cost = LogisticsCostDB(**cost.model_dump())
        db.add(new_cost)
        db.commit()
        return MessageResponse(message="물류비 단가가 등록되었습니다")


@app.delete("/api/logistics-cost", response_model=MessageResponse, tags=["기준 정보"])
def delete_logistics_cost(
    departure_wh_id: int = Query(...),
    arrival_wh_id: int = Query(...),
    current_user: UserAccount = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """물류비 단가 삭제"""
    existing = (
        db.query(LogisticsCostDB)
        .filter(
            LogisticsCostDB.departure_wh_id == departure_wh_id,
            LogisticsCostDB.arrival_wh_id == arrival_wh_id,
        )
        .first()
    )
    if not existing:
        raise HTTPException(status_code=404, detail="물류비 데이터를 찾을 수 없습니다")
    db.delete(existing)
    db.commit()
    return MessageResponse(message="물류비 삭제 완료")


# ═══════════════════════════════════════════════════════════════════════
# 창고-품목별 이관 MOQ API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/warehouse-moq", response_model=List[WarehouseProductMOQResponse], tags=["기준 정보"])
def get_warehouse_moqs(
    warehouse_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """창고-품목별 이관 MOQ 조회"""
    query = db.query(WarehouseProductMOQ)
    if warehouse_id:
        query = query.filter(WarehouseProductMOQ.warehouse_id == warehouse_id)
    moqs = query.all()
    result = []
    for m in moqs:
        wh = db.query(WarehouseDB).filter(WarehouseDB.id == m.warehouse_id).first()
        prod = db.query(ProductDB).filter(ProductDB.id == m.product_id).first()
        result.append(
            WarehouseProductMOQResponse(
                id=m.id,
                warehouse_id=m.warehouse_id,
                product_id=m.product_id,
                transfer_moq=m.transfer_moq,
                warehouse_name=wh.warehouse_name if wh else None,
                product_name=prod.product_name if prod else None,
            )
        )
    return result


@app.post("/api/warehouse-moq", response_model=WarehouseProductMOQResponse, tags=["기준 정보"])
def upsert_warehouse_moq(
    moq: WarehouseProductMOQCreate,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """창고-품목별 이관 MOQ 등록/수정 (Upsert)"""
    existing = (
        db.query(WarehouseProductMOQ)
        .filter(
            WarehouseProductMOQ.warehouse_id == moq.warehouse_id,
            WarehouseProductMOQ.product_id == moq.product_id,
        )
        .first()
    )
    if existing:
        existing.transfer_moq = moq.transfer_moq
        db.commit()
        db.refresh(existing)
        obj = existing
    else:
        db_moq = WarehouseProductMOQ(**moq.model_dump())
        db.add(db_moq)
        db.commit()
        db.refresh(db_moq)
        obj = db_moq

    wh = db.query(WarehouseDB).filter(WarehouseDB.id == obj.warehouse_id).first()
    prod = db.query(ProductDB).filter(ProductDB.id == obj.product_id).first()
    return WarehouseProductMOQResponse(
        id=obj.id,
        warehouse_id=obj.warehouse_id,
        product_id=obj.product_id,
        transfer_moq=obj.transfer_moq,
        warehouse_name=wh.warehouse_name if wh else None,
        product_name=prod.product_name if prod else None,
    )


@app.delete("/api/warehouse-moq", response_model=MessageResponse, tags=["기준 정보"])
def delete_warehouse_moq(
    warehouse_id: int = Query(...),
    product_id: int = Query(...),
    current_user: UserAccount = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """창고-품목별 이관 MOQ 삭제"""
    existing = (
        db.query(WarehouseProductMOQ)
        .filter(
            WarehouseProductMOQ.warehouse_id == warehouse_id,
            WarehouseProductMOQ.product_id == product_id,
        )
        .first()
    )
    if not existing:
        raise HTTPException(status_code=404, detail="MOQ 데이터를 찾을 수 없습니다")
    db.delete(existing)
    db.commit()
    return MessageResponse(message="MOQ 삭제 완료")


# ═══════════════════════════════════════════════════════════════════════
# 발주 DB API (Order)
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/orders", response_model=List[OrderResponse], tags=["입고 파이프라인"])
def get_orders(
    product_code: Optional[str] = Query(None),
    order_month: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """발주 목록 조회"""
    query = db.query(OrderDB)
    if product_code:
        query = query.filter(OrderDB.product_code == product_code)
    if order_month:
        query = query.filter(OrderDB.order_month == order_month)
    orders = query.order_by(OrderDB.id.desc()).all()
    result = []
    for o in orders:
        prod = db.query(ProductDB).filter(ProductDB.product_code == o.product_code).first()
        result.append(
            OrderResponse(
                id=o.id,
                order_month=o.order_month,
                product_code=o.product_code,
                order_qty=o.order_qty,
                created_at=o.created_at,
                product_name=prod.product_name if prod else None,
            )
        )
    return result


@app.post("/api/orders", response_model=OrderResponse, tags=["입고 파이프라인"])
def create_order(
    order: OrderCreate,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """발주 등록"""
    # 품목코드 유효성 검증
    prod = db.query(ProductDB).filter(ProductDB.product_code == order.product_code).first()
    if not prod:
        raise HTTPException(status_code=400, detail=f"품목코드 '{order.product_code}'가 존재하지 않습니다")
    db_order = OrderDB(
        **order.model_dump(),
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    return OrderResponse(
        id=db_order.id,
        order_month=db_order.order_month,
        product_code=db_order.product_code,
        order_qty=db_order.order_qty,
        created_at=db_order.created_at,
        product_name=prod.product_name,
    )


@app.delete("/api/orders/{order_id}", response_model=MessageResponse, tags=["입고 파이프라인"])
def delete_order(
    order_id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """발주 삭제"""
    obj = db.query(OrderDB).filter(OrderDB.id == order_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="발주 데이터를 찾을 수 없습니다")
    db.delete(obj)
    db.commit()
    return MessageResponse(message="발주 삭제 완료")


# ═══════════════════════════════════════════════════════════════════════
# 생산 DB API (Production)
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/productions", response_model=List[ProductionResponse], tags=["입고 파이프라인"])
def get_productions(
    product_code: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """생산 목록 조회"""
    query = db.query(ProductionDB)
    if product_code:
        query = query.filter(ProductionDB.product_code == product_code)
    productions = query.order_by(ProductionDB.id.desc()).all()
    result = []
    for p in productions:
        prod = db.query(ProductDB).filter(ProductDB.product_code == p.product_code).first()
        result.append(
            ProductionResponse(
                id=p.id,
                purchase_code=p.purchase_code,
                production_code=p.production_code,
                order_month=p.order_month,
                production_qty=p.production_qty,
                product_code=p.product_code,
                matched_order_id=p.matched_order_id,
                created_at=p.created_at,
                product_name=prod.product_name if prod else None,
            )
        )
    return result


@app.post("/api/productions", response_model=ProductionResponse, tags=["입고 파이프라인"])
def create_production(
    prod_data: ProductionCreate,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """생산 등록"""
    product = db.query(ProductDB).filter(ProductDB.product_code == prod_data.product_code).first()
    if not product:
        raise HTTPException(status_code=400, detail=f"품목코드 '{prod_data.product_code}'가 존재하지 않습니다")
    db_prod = ProductionDB(
        **prod_data.model_dump(),
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    db.add(db_prod)
    db.commit()
    db.refresh(db_prod)
    return ProductionResponse(
        id=db_prod.id,
        purchase_code=db_prod.purchase_code,
        production_code=db_prod.production_code,
        order_month=db_prod.order_month,
        production_qty=db_prod.production_qty,
        product_code=db_prod.product_code,
        matched_order_id=db_prod.matched_order_id,
        created_at=db_prod.created_at,
        product_name=product.product_name,
    )


@app.delete("/api/productions/{prod_id}", response_model=MessageResponse, tags=["입고 파이프라인"])
def delete_production(
    prod_id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """생산 삭제"""
    obj = db.query(ProductionDB).filter(ProductionDB.id == prod_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="생산 데이터를 찾을 수 없습니다")
    db.delete(obj)
    db.commit()
    return MessageResponse(message="생산 삭제 완료")


# ═══════════════════════════════════════════════════════════════════════
# 인보이스 DB API (Invoice)
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/invoices", response_model=List[InvoiceResponse], tags=["입고 파이프라인"])
def get_invoices(
    invoice_no: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """인보이스 목록 조회"""
    query = db.query(InvoiceDB)
    if invoice_no:
        query = query.filter(InvoiceDB.invoice_no == invoice_no)
    return query.order_by(InvoiceDB.id.desc()).all()


@app.post("/api/invoices", response_model=InvoiceResponse, tags=["입고 파이프라인"])
def create_invoice(
    inv: InvoiceCreate,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """인보이스 등록"""
    db_inv = InvoiceDB(
        **inv.model_dump(),
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    db.add(db_inv)
    db.commit()
    db.refresh(db_inv)
    return db_inv


@app.delete("/api/invoices/{inv_id}", response_model=MessageResponse, tags=["입고 파이프라인"])
def delete_invoice(
    inv_id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """인보이스 삭제"""
    obj = db.query(InvoiceDB).filter(InvoiceDB.id == inv_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="인보이스 데이터를 찾을 수 없습니다")
    db.delete(obj)
    db.commit()
    return MessageResponse(message="인보이스 삭제 완료")


# ═══════════════════════════════════════════════════════════════════════
# 입고 DB API (Inbound — 상태 추적 포함)
# ═══════════════════════════════════════════════════════════════════════


VALID_INBOUND_STATUSES = ["생산국출발", "해상운송중", "한국도착", "통관중", "입고일선정중", "입고완료"]


@app.get("/api/inbound", response_model=List[InboundResponse], tags=["입고 파이프라인"])
def get_inbounds(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    """입고 리스트 조회 (상태 필터 지원)"""
    query = db.query(InboundDB)
    if status_filter:
        query = query.filter(InboundDB.status == status_filter)
    return query.order_by(InboundDB.id.desc()).all()


@app.post("/api/inbound", response_model=InboundResponse, tags=["입고 파이프라인"])
def create_inbound(
    inbound: InboundCreate,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """입고 등록"""
    db_inbound = InboundDB(**inbound.model_dump())
    db.add(db_inbound)
    db.commit()
    db.refresh(db_inbound)
    return db_inbound


@app.put("/api/inbound/{inbound_id}", response_model=InboundResponse, tags=["입고 파이프라인"])
def update_inbound(
    inbound_id: int,
    data: dict,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """입고 수정 (상태 업데이트 포함)"""
    db_inbound = db.query(InboundDB).filter(InboundDB.id == inbound_id).first()
    if not db_inbound:
        raise HTTPException(status_code=404, detail="입고 데이터를 찾을 수 없습니다")
    # 상태 변경 유효성 검증
    if "status" in data and data["status"] not in VALID_INBOUND_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"유효하지 않은 상태입니다. 허용: {VALID_INBOUND_STATUSES}",
        )
    allowed_fields = {
        "invoice_no", "bl_no", "shipping_date", "korea_arrival_date",
        "manufacture_date", "expiry_date", "carton_qty", "can_qty",
        "product_code", "status",
    }
    for key, value in data.items():
        if key in allowed_fields:
            setattr(db_inbound, key, value)
    db.commit()
    db.refresh(db_inbound)
    return db_inbound


@app.delete("/api/inbound/{inbound_id}", response_model=MessageResponse, tags=["입고 파이프라인"])
def delete_inbound(
    inbound_id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """입고 삭제"""
    obj = db.query(InboundDB).filter(InboundDB.id == inbound_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="입고 데이터를 찾을 수 없습니다")
    db.delete(obj)
    db.commit()
    return MessageResponse(message="입고 삭제 완료")


# ═══════════════════════════════════════════════════════════════════════
# 현재고 스냅샷 API (InventorySnapshot)
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/inventory-snapshot", response_model=List[InventorySnapshotResponse], tags=["재고 관리"])
def get_inventory_snapshots(
    warehouse_id: Optional[int] = Query(None),
    snapshot_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """현재고 스냅샷 조회"""
    query = db.query(InventorySnapshot)
    if warehouse_id:
        query = query.filter(InventorySnapshot.warehouse_id == warehouse_id)
    if snapshot_date:
        query = query.filter(InventorySnapshot.snapshot_date == snapshot_date)
    return query.order_by(InventorySnapshot.id.desc()).all()


@app.post("/api/inventory-snapshot", response_model=InventorySnapshotResponse, tags=["재고 관리"])
def create_inventory_snapshot(
    snap: InventorySnapshotCreate,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """현재고 스냅샷 단건 등록"""
    db_snap = InventorySnapshot(**snap.model_dump())
    db.add(db_snap)
    db.commit()
    db.refresh(db_snap)
    return db_snap


@app.delete("/api/inventory-snapshot/{snap_id}", response_model=MessageResponse, tags=["재고 관리"])
def delete_inventory_snapshot(
    snap_id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """현재고 스냅샷 삭제"""
    obj = db.query(InventorySnapshot).filter(InventorySnapshot.id == snap_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="스냅샷 데이터를 찾을 수 없습니다")
    db.delete(obj)
    db.commit()
    return MessageResponse(message="스냅샷 삭제 완료")


@app.post("/api/inventory-snapshot/upload", response_model=MessageResponse, tags=["재고 관리"])
def upload_inventory_snapshot(
    file: UploadFile = File(...),
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """현재고 스냅샷 엑셀 업로드"""
    import pandas as pd

    if not file.filename.endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="xlsx 파일만 업로드 가능합니다")

    content = file.file.read()
    try:
        df = pd.read_excel(io.BytesIO(content))
    except Exception:
        raise HTTPException(status_code=400, detail="엑셀 파일을 읽을 수 없습니다")

    required_cols = {"snapshot_date", "qty_cans"}
    if not required_cols.issubset(set(df.columns)):
        raise HTTPException(status_code=400, detail=f"필수 컬럼 누락: {required_cols - set(df.columns)}")

    created = 0
    for _, row in df.iterrows():
        snap_date = str(row["snapshot_date"]).strip()
        if not snap_date:
            continue

        # 창고 매핑 시도
        wh_id = None
        wh_name = None
        if "warehouse_name" in df.columns and pd.notna(row.get("warehouse_name")):
            wh_name = str(row["warehouse_name"]).strip()
            wh = db.query(WarehouseDB).filter(WarehouseDB.warehouse_name == wh_name).first()
            if wh:
                wh_id = wh.id

        new_snap = InventorySnapshot(
            snapshot_date=snap_date,
            warehouse_id=wh_id,
            warehouse_name=wh_name or (str(row.get("warehouse_name", "")).strip() if "warehouse_name" in df.columns else None),
            product_name=str(row.get("product_name", "")).strip() if "product_name" in df.columns and pd.notna(row.get("product_name")) else None,
            product_code=str(row.get("product_code", "")).strip() if "product_code" in df.columns and pd.notna(row.get("product_code")) else None,
            expiry_date=str(row.get("expiry_date", "")).strip() if "expiry_date" in df.columns and pd.notna(row.get("expiry_date")) else None,
            qty_cans=int(row["qty_cans"]) if pd.notna(row.get("qty_cans")) else 0,
        )
        db.add(new_snap)
        created += 1

    db.commit()
    return MessageResponse(message=f"스냅샷 업로드 완료: {created}건 등록")


# ═══════════════════════════════════════════════════════════════════════
# 재고 요약 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/inventory/summary", tags=["재고 관리"])
def get_inventory_summary(db: Session = Depends(get_db)):
    """전체 현재고 요약 (창고별, 품목별 집계 — InventorySnapshot 기반)"""
    # 가장 최신 스냅샷 날짜 기준
    latest_date_row = db.query(func.max(InventorySnapshot.snapshot_date)).first()
    latest_date = latest_date_row[0] if latest_date_row and latest_date_row[0] else None
    if not latest_date:
        return []

    snapshots = (
        db.query(InventorySnapshot)
        .filter(InventorySnapshot.snapshot_date == latest_date)
        .all()
    )

    warehouses = {w.id: w for w in db.query(WarehouseDB).all()}
    summary_by_wh: dict = {}

    for snap in snapshots:
        wh_key = snap.warehouse_id or 0
        wh = warehouses.get(snap.warehouse_id) if snap.warehouse_id else None
        wh_name = wh.warehouse_name if wh else (snap.warehouse_name or "미지정")

        if wh_key not in summary_by_wh:
            summary_by_wh[wh_key] = {
                "warehouse_id": snap.warehouse_id,
                "warehouse_name": wh_name,
                "products": {},
                "total_qty": 0,
            }

        prod_key = snap.product_code or snap.product_name or "UNKNOWN"
        if prod_key not in summary_by_wh[wh_key]["products"]:
            summary_by_wh[wh_key]["products"][prod_key] = {
                "product_code": snap.product_code,
                "product_name": snap.product_name,
                "total_qty": 0,
                "batches": [],
            }

        remaining_days = None
        if snap.expiry_date and _FORECASTING_AVAILABLE:
            try:
                remaining_days = calc_remaining_expiry_days(snap.expiry_date)
            except Exception:
                pass

        summary_by_wh[wh_key]["products"][prod_key]["total_qty"] += snap.qty_cans
        summary_by_wh[wh_key]["products"][prod_key]["batches"].append({
            "snapshot_id": snap.id,
            "qty_cans": snap.qty_cans,
            "expiry_date": snap.expiry_date,
            "remaining_days": remaining_days,
        })
        summary_by_wh[wh_key]["total_qty"] += snap.qty_cans

    result = []
    for wh_data in summary_by_wh.values():
        wh_data["products"] = list(wh_data["products"].values())
        result.append(wh_data)
    return result


# ═══════════════════════════════════════════════════════════════════════
# 유통기한 요약 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/expiry/summary", tags=["유통기한 관리"])
def get_expiry_summary(db: Session = Depends(get_db)):
    """유통기한 임박 재고 요약 (InventorySnapshot + WarehouseDB.allowed_expiry_days)"""
    # 최신 스냅샷 기준
    latest_date_row = db.query(func.max(InventorySnapshot.snapshot_date)).first()
    latest_date = latest_date_row[0] if latest_date_row and latest_date_row[0] else None
    if not latest_date:
        return {"items": [], "total_risk_count": 0, "critical_count": 0, "warehouse_count": 0}

    snapshots = (
        db.query(InventorySnapshot)
        .filter(InventorySnapshot.snapshot_date == latest_date)
        .all()
    )
    warehouses = {w.id: w for w in db.query(WarehouseDB).all()}

    items = []
    for snap in snapshots:
        if not snap.expiry_date:
            continue
        try:
            expiry = date.fromisoformat(snap.expiry_date)
            remaining = (expiry - date.today()).days
        except Exception:
            continue

        if remaining > 180:
            continue

        wh = warehouses.get(snap.warehouse_id) if snap.warehouse_id else None
        threshold = wh.allowed_expiry_days if wh else 90

        items.append({
            "snapshot_id": snap.id,
            "warehouse_id": snap.warehouse_id,
            "warehouse_name": wh.warehouse_name if wh else (snap.warehouse_name or "미지정"),
            "product_code": snap.product_code,
            "product_name": snap.product_name,
            "qty_cans": snap.qty_cans,
            "expiry_date": snap.expiry_date,
            "remaining_days": remaining,
            "threshold_days": threshold,
            "is_locked": remaining <= threshold,
        })

    items.sort(key=lambda x: x["remaining_days"])
    wh_set = set(i["warehouse_id"] for i in items if i["warehouse_id"])
    return {
        "items": items,
        "total_risk_count": len(items),
        "critical_count": sum(1 for i in items if i["remaining_days"] <= 30),
        "warehouse_count": len(wh_set),
    }


# ═══════════════════════════════════════════════════════════════════════
# 매칭 API (3단 매칭: 발주→생산→인보이스)
# ═══════════════════════════════════════════════════════════════════════


@app.post("/api/matching/link", response_model=MatchResponse, tags=["매칭"])
def link_matching(
    req: MatchRequest,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    3단 매칭 링크 처리
    - order_id + production_id → 생산에 matched_order_id 설정
    - production_id + invoice_id → 인보이스에 matched_production_id 설정
    """
    matched_order_id = None
    matched_production_id = None
    matched_invoice_id = None

    # Stage 1: 발주 → 생산 연결
    if req.order_id and req.production_id:
        order = db.query(OrderDB).filter(OrderDB.id == req.order_id).first()
        if not order:
            raise HTTPException(status_code=404, detail="발주를 찾을 수 없습니다")
        production = db.query(ProductionDB).filter(ProductionDB.id == req.production_id).first()
        if not production:
            raise HTTPException(status_code=404, detail="생산을 찾을 수 없습니다")
        production.matched_order_id = req.order_id
        matched_order_id = req.order_id
        matched_production_id = req.production_id

    # Stage 2: 생산 → 인보이스 연결
    if req.production_id and req.invoice_id:
        production = db.query(ProductionDB).filter(ProductionDB.id == req.production_id).first()
        if not production:
            raise HTTPException(status_code=404, detail="생산을 찾을 수 없습니다")
        invoice = db.query(InvoiceDB).filter(InvoiceDB.id == req.invoice_id).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="인보이스를 찾을 수 없습니다")
        invoice.matched_production_id = req.production_id
        matched_production_id = req.production_id
        matched_invoice_id = req.invoice_id

    db.commit()
    return MatchResponse(
        message="매칭이 완료되었습니다",
        matched_order_id=matched_order_id,
        matched_production_id=matched_production_id,
        matched_invoice_id=matched_invoice_id,
    )


@app.get("/api/matching/status", tags=["매칭"])
def get_matching_status(db: Session = Depends(get_db)):
    """현재 매칭 상태 조회 — 미매칭 건수 및 목록"""
    # 미매칭 생산 (matched_order_id가 없는 것)
    unmatched_productions = (
        db.query(ProductionDB)
        .filter(ProductionDB.matched_order_id.is_(None))
        .all()
    )
    # 미매칭 인보이스 (matched_production_id가 없는 것)
    unmatched_invoices = (
        db.query(InvoiceDB)
        .filter(InvoiceDB.matched_production_id.is_(None))
        .all()
    )
    return {
        "unmatched_production_count": len(unmatched_productions),
        "unmatched_invoice_count": len(unmatched_invoices),
        "unmatched_productions": [
            {
                "id": p.id,
                "purchase_code": p.purchase_code,
                "production_code": p.production_code,
                "product_code": p.product_code,
                "production_qty": p.production_qty,
            }
            for p in unmatched_productions
        ],
        "unmatched_invoices": [
            {
                "id": inv.id,
                "invoice_no": inv.invoice_no,
                "product_code": inv.product_code,
                "product_name": inv.product_name,
                "carton_qty": inv.carton_qty,
            }
            for inv in unmatched_invoices
        ],
    }


# ═══════════════════════════════════════════════════════════════════════
# 이관 계획 API (TransferPlan)
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/transfer-plan", response_model=List[TransferPlanResponse], tags=["이관 계획"])
def get_transfer_plans(
    arrival_wh_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """이관 계획 목록 조회"""
    query = db.query(TransferPlan)
    if arrival_wh_id:
        query = query.filter(TransferPlan.arrival_wh_id == arrival_wh_id)
    plans = query.order_by(TransferPlan.transfer_id.desc()).all()
    result = []
    for plan in plans:
        product = db.query(ProductDB).filter(ProductDB.id == plan.product_id).first()
        dep_wh = db.query(WarehouseDB).filter(WarehouseDB.id == plan.departure_wh_id).first()
        arr_wh = db.query(WarehouseDB).filter(WarehouseDB.id == plan.arrival_wh_id).first()
        result.append(
            TransferPlanResponse(
                transfer_id=plan.transfer_id,
                product_id=plan.product_id,
                departure_wh_id=plan.departure_wh_id,
                arrival_wh_id=plan.arrival_wh_id,
                target_tu_qty=plan.target_tu_qty,
                target_can_qty=plan.target_can_qty,
                estimated_logistics_cost=plan.estimated_logistics_cost,
                transfer_date=plan.transfer_date,
                transfer_status=plan.transfer_status,
                product_name=product.product_name if product else None,
                departure_name=dep_wh.warehouse_name if dep_wh else None,
                arrival_name=arr_wh.warehouse_name if arr_wh else None,
            )
        )
    return result


@app.post("/api/transfer-plan", response_model=MessageResponse, tags=["이관 계획"])
def create_transfer_plan(
    plan: TransferPlanCreate,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """이관 계획 생성"""
    # 물류비 자동 계산
    estimated_cost = plan.estimated_logistics_cost
    if estimated_cost is None:
        lc = (
            db.query(LogisticsCostDB)
            .filter(
                LogisticsCostDB.departure_wh_id == plan.departure_wh_id,
                LogisticsCostDB.arrival_wh_id == plan.arrival_wh_id,
            )
            .first()
        )
        if lc:
            estimated_cost = plan.target_tu_qty * lc.cost_per_tu

    new_plan = TransferPlan(
        product_id=plan.product_id,
        departure_wh_id=plan.departure_wh_id,
        arrival_wh_id=plan.arrival_wh_id,
        target_tu_qty=plan.target_tu_qty,
        target_can_qty=plan.target_can_qty,
        estimated_logistics_cost=estimated_cost,
        transfer_date=plan.transfer_date,
        transfer_status="PLANNED",
    )
    db.add(new_plan)
    db.commit()
    return MessageResponse(message="이관 계획이 생성되었습니다")


@app.put("/api/transfer-plan/{plan_id}/confirm", response_model=MessageResponse, tags=["이관 계획"])
def confirm_transfer_plan(
    plan_id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """이관 계획 확정"""
    plan = db.query(TransferPlan).filter(TransferPlan.transfer_id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="이관 계획을 찾을 수 없습니다")
    plan.transfer_status = "IN_TRANSIT"
    db.commit()
    return MessageResponse(message="이관 계획이 확정되었습니다")


@app.delete("/api/transfer-plan/{plan_id}", response_model=MessageResponse, tags=["이관 계획"])
def delete_transfer_plan(
    plan_id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """이관 계획 삭제"""
    plan = db.query(TransferPlan).filter(TransferPlan.transfer_id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="이관 계획을 찾을 수 없습니다")
    db.delete(plan)
    db.commit()
    return MessageResponse(message="이관 계획이 삭제되었습니다")


# ═══════════════════════════════════════════════════════════════════════
# 발주 계획 API (MonthlyOrderPlan — 시뮬레이션)
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/order-plan/simulation", tags=["발주 계획"])
def get_order_plan_simulation(
    weight_factor: float = Query(default=1.0, ge=0.5, le=2.0),
    db: Session = Depends(get_db),
):
    """6개월(24주) 시뮬레이션 데이터 — 품목별"""
    if not _FORECASTING_AVAILABLE:
        raise HTTPException(
            status_code=501,
            detail="포캐스팅 모듈을 사용할 수 없습니다 (app.core.forecasting 로드 실패)",
        )

    products = db.query(ProductDB).all()
    snapshots = db.query(InventorySnapshot).all()
    outflows = db.query(OutflowHistory).all()

    result = []
    for product in products:
        # 현재 총 재고 (최신 스냅샷에서 품목코드 일치 건 합산)
        total_stock = sum(
            s.qty_cans
            for s in snapshots
            if s.product_code == product.product_code
        )

        # 출고 데이터
        product_outflows = sorted(
            [o for o in outflows if o.product_id == product.id],
            key=lambda x: x.base_date,
        )
        outflow_values = [o.simple_outflow_qty for o in product_outflows]
        smoothing = calc_weekly_smoothing_constant(outflow_values) if outflow_values else 0

        # 판매 기반 감모 버퍼
        sales = (
            db.query(SalesHistory)
            .filter(SalesHistory.product_id == product.id)
            .order_by(SalesHistory.base_date.desc())
            .limit(12)
            .all()
        )
        sales_data = [s.sales_qty for s in reversed(sales)] if sales else []
        loss_buffer = (
            calc_dynamic_loss_buffer(outflow_values, sales_data)
            if sales_data and outflow_values
            else 0
        )

        # 시뮬레이션
        simulation = simulate_future_inventory(
            current_stock=total_stock,
            smoothing_constant=smoothing,
            loss_buffer=loss_buffer,
            pipeline_inbounds={},
            expected_inbounds={},
            weight_factor=weight_factor,
            weeks=24,
        )

        suggested_qty = 0
        if simulation and simulation[-1]["ending_stock"] < smoothing * 6:
            shortage = smoothing * 6 - simulation[-1]["ending_stock"]
            suggested_qty = calc_order_suggestion(shortage, 0)

        today = date.today()
        target_month = (today + timedelta(weeks=24)).strftime("%Y-%m")
        saved_plan = (
            db.query(MonthlyOrderPlan)
            .filter(
                MonthlyOrderPlan.product_id == product.id,
                MonthlyOrderPlan.target_month == target_month,
            )
            .first()
        )

        result.append({
            "product_id": product.id,
            "product_code": product.product_code,
            "product_name": product.product_name,
            "current_stock": total_stock,
            "weekly_avg_outflow": round(smoothing, 1),
            "loss_buffer": round(loss_buffer, 2),
            "simulation": simulation,
            "suggested_qty": suggested_qty,
            "target_month": target_month,
            "saved_qty": saved_plan.user_modified_qty if saved_plan else None,
            "version": saved_plan.version if saved_plan else 1,
        })

    return result


@app.post("/api/order-plan/save", response_model=MessageResponse, tags=["발주 계획"])
def save_order_plan(
    data: OrderPlanBulkSave,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """발주 계획 일괄 저장 (Upsert + 낙관적 잠금)"""
    saved = 0
    for item in data.plans:
        existing = (
            db.query(MonthlyOrderPlan)
            .filter(
                MonthlyOrderPlan.target_month == item.target_month,
                MonthlyOrderPlan.product_id == item.product_id,
            )
            .first()
        )
        if existing:
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


@app.get("/api/order-plan", response_model=List[OrderPlanResponse], tags=["발주 계획"])
def get_order_plans(
    target_month: Optional[str] = Query(None, description="대상 연월 (YYYY-MM)"),
    db: Session = Depends(get_db),
):
    """월별 발주 계획 조회"""
    query = db.query(MonthlyOrderPlan)
    if target_month:
        query = query.filter(MonthlyOrderPlan.target_month == target_month)
    plans = query.all()
    result = []
    for p in plans:
        prod = db.query(ProductDB).filter(ProductDB.id == p.product_id).first()
        result.append(
            OrderPlanResponse(
                plan_id=p.plan_id,
                target_month=p.target_month,
                product_id=p.product_id,
                system_suggested_qty=p.system_suggested_qty,
                user_modified_qty=p.user_modified_qty,
                version=p.version or 1,
                updated_at=p.updated_at,
                product_code=prod.product_code if prod else None,
                product_name=prod.product_name if prod else None,
            )
        )
    return result


@app.delete("/api/order-plan/{plan_id}", response_model=MessageResponse, tags=["발주 계획"])
def delete_order_plan(
    plan_id: int,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """발주 계획 삭제"""
    obj = db.query(MonthlyOrderPlan).filter(MonthlyOrderPlan.plan_id == plan_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="발주 계획을 찾을 수 없습니다")
    db.delete(obj)
    db.commit()
    return MessageResponse(message="발주 계획 삭제 완료")


# ═══════════════════════════════════════════════════════════════════════
# 출고 이력 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/outflow", tags=["출고 관리"])
def get_outflow_history(
    product_id: Optional[int] = Query(None),
    warehouse_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """출고 이력 조회 (품목/창고 필터 지원)"""
    query = db.query(OutflowHistory)
    if product_id:
        query = query.filter(OutflowHistory.product_id == product_id)
    if warehouse_id:
        query = query.filter(OutflowHistory.warehouse_id == warehouse_id)
    return query.order_by(OutflowHistory.base_date.desc()).all()


# ═══════════════════════════════════════════════════════════════════════
# 판매 실적 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/sales", tags=["판매 실적"])
def get_sales(
    product_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """판매 실적 조회"""
    query = db.query(SalesHistory)
    if product_id:
        query = query.filter(SalesHistory.product_id == product_id)
    return query.order_by(SalesHistory.base_date.desc()).all()


@app.post("/api/sales", tags=["판매 실적"])
def create_sales(
    data: dict,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """판매 실적 등록"""
    db_sales = SalesHistory(
        warehouse_id=data.get("warehouse_id"),
        product_id=data.get("product_id"),
        base_date=data.get("base_date"),
        sales_qty=data.get("sales_qty", 0),
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    db.add(db_sales)
    db.commit()
    db.refresh(db_sales)
    return {"id": db_sales.sales_id, "message": "판매 실적 등록 완료"}


# ═══════════════════════════════════════════════════════════════════════
# 엑셀 템플릿 다운로드 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/templates/{template_type}", tags=["데이터 수집"])
def download_template(template_type: str):
    """엑셀 양식 다운로드"""
    if not _EXCEL_PARSER_AVAILABLE:
        # 폴백: 기본 빈 엑셀 생성
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = template_type

        # 템플릿 타입별 기본 헤더
        headers_map = {
            "product": ["product_code", "product_name", "pack_qty_per_tu", "currency_unit", "purchase_price"],
            "warehouse": ["warehouse_name", "warehouse_type", "allowed_expiry_days", "moq"],
            "inventory": ["snapshot_date", "warehouse_name", "product_code", "product_name", "expiry_date", "qty_cans"],
            "order": ["order_month", "product_code", "order_qty"],
            "production": ["purchase_code", "production_code", "order_month", "production_qty", "product_code"],
            "invoice": ["invoice_no", "product_code", "product_name", "carton_qty", "unit_price", "total_price", "eta"],
            "inbound": ["invoice_no", "bl_no", "shipping_date", "korea_arrival_date", "manufacture_date", "expiry_date", "carton_qty", "can_qty", "product_code"],
        }
        headers = headers_map.get(template_type, ["column1", "column2"])
        for col_idx, header in enumerate(headers, 1):
            ws.cell(row=1, column=col_idx, value=header)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        filename = urllib.parse.quote(f"{template_type}_양식.xlsx")
        return StreamingResponse(
            output,
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    # 기존 excel_parser 모듈 사용
    try:
        output = generate_template(template_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    filename = urllib.parse.quote(get_template_filename(template_type))
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    return StreamingResponse(
        output,
        headers=headers,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/api/excel/template-types", tags=["데이터 수집"])
def get_template_types():
    """사용 가능한 엑셀 양식 종류 목록"""
    if _EXCEL_PARSER_AVAILABLE and TEMPLATE_LABELS:
        return [{"type": k, "label": v} for k, v in TEMPLATE_LABELS.items()]
    # 폴백
    return [
        {"type": "product", "label": "품목 마스터"},
        {"type": "warehouse", "label": "창고 마스터"},
        {"type": "inventory", "label": "현재고 스냅샷"},
        {"type": "order", "label": "발주"},
        {"type": "production", "label": "생산"},
        {"type": "invoice", "label": "인보이스"},
        {"type": "inbound", "label": "입고"},
    ]
