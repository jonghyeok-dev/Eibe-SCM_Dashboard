"""
FastAPI 메인 엔드포인트 및 라우팅 제어 모듈
- 정적 파일 서빙 (web/ 디렉토리)
- REST API 엔드포인트
- 명세서 CH 1.1 §4 기준 사내망 포트 개방 서빙
"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db, init_db, BASE_DIR
from app.models import (
    ProductMaster,
    FFCMaster,
    LogisticsCostMaster,
    InboundList,
    ExpectedInbound,
    CurrentInventory,
    OutflowHistory,
    TransferPlan,
    MatchingHistoryLog,
    MonthlyOrderPlan,
)
from app.schemas import (
    ProductMasterCreate,
    ProductMasterResponse,
    FFCMasterCreate,
    FFCMasterResponse,
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
)


# ── 애플리케이션 수명주기 ────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작 시 DB 테이블 자동 생성"""
    init_db()
    yield


app = FastAPI(
    title="SCM ERP Dashboard",
    description="독립형 로컬 SCM ERP 시스템 - 분유 재고/수요 관리",
    version="1.0.0",
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


@app.get("/order-plan", include_in_schema=False)
async def serve_order_plan():
    """월 1회 발주 제안 편집 및 수정 저장 화면"""
    return FileResponse(os.path.join(WEB_DIR, "order_plan.html"))


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
# 풀필먼트 마스터 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/ffc", response_model=List[FFCMasterResponse], tags=["마스터 데이터"])
def get_ffcs(db: Session = Depends(get_db)):
    """전체 풀필먼트 거점 목록 조회"""
    return db.query(FFCMaster).all()


@app.post("/api/ffc", response_model=FFCMasterResponse, tags=["마스터 데이터"])
def create_ffc(ffc: FFCMasterCreate, db: Session = Depends(get_db)):
    """풀필먼트 거점 등록"""
    existing = db.query(FFCMaster).filter(FFCMaster.ffc_code == ffc.ffc_code).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"거점코드 '{ffc.ffc_code}' 이미 존재")

    db_ffc = FFCMaster(**ffc.model_dump())
    db.add(db_ffc)
    db.commit()
    db.refresh(db_ffc)
    return db_ffc


# ═══════════════════════════════════════════════════════════════════════
# 현재고 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/inventory", response_model=List[CurrentInventoryResponse], tags=["재고 관리"])
def get_inventory(
    ffc_id: Optional[int] = Query(None, description="거점 ID 필터"),
    db: Session = Depends(get_db),
):
    """현재고 목록 조회 (거점별 필터 지원)"""
    query = db.query(CurrentInventory)
    if ffc_id:
        query = query.filter(CurrentInventory.ffc_id == ffc_id)
    return query.all()


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
    """출고 이력 조회 (품목/거점 필터 지원)"""
    query = db.query(OutflowHistory)
    if product_id:
        query = query.filter(OutflowHistory.product_id == product_id)
    if ffc_id:
        query = query.filter(OutflowHistory.ffc_id == ffc_id)
    return query.order_by(OutflowHistory.base_date.desc()).all()


# ═══════════════════════════════════════════════════════════════════════
# 발주 계획 API (CH 7.2)
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
    발주 계획 실무자 수정 저장 (CH 7.2 §3)
    - Local Storage 휘발성 저장 차단
    - SQLite 영구 수정 적재
    """
    db_plan = db.query(MonthlyOrderPlan).filter(MonthlyOrderPlan.plan_id == plan_id).first()
    if not db_plan:
        raise HTTPException(status_code=404, detail="발주 계획을 찾을 수 없습니다")

    db_plan.user_modified_qty = plan.user_modified_qty
    db.commit()
    return MessageResponse(message="발주 계획이 저장되었습니다", detail=f"plan_id={plan_id}")


# ═══════════════════════════════════════════════════════════════════════
# 시스템 상태 API
# ═══════════════════════════════════════════════════════════════════════


@app.get("/api/health", response_model=MessageResponse, tags=["시스템"])
def health_check():
    """서버 상태 확인"""
    return MessageResponse(message="OK", detail="SCM ERP 서버가 정상 가동 중입니다.")
