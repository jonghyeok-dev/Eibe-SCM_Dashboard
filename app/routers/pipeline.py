from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from typing import List, Optional
import os
import io
import math
import urllib.parse
from datetime import datetime, date, timedelta
import pandas as pd

from app.database import get_db, BASE_DIR, BACKUP_DIR
from app.models import *
from app.schemas import *
from app.core.auth import verify_password, get_password_hash, create_access_token, get_current_user, get_current_admin
from app.core.snapshot import create_snapshot

try:
    from app.core.excel_parser import generate_template, get_template_filename, parse_inventory_excel, generate_order_plan_export, TEMPLATE_LABELS
except Exception:
    TEMPLATE_LABELS = {}

try:
    from app.core.forecasting import *
except Exception:
    pass

router = APIRouter()
WEB_DIR = os.path.join(BASE_DIR, "web")

@router.get("/api/orders", response_model=List[OrderResponse], tags=["입고 파이프라인"])
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


@router.post("/api/orders", response_model=OrderResponse, tags=["입고 파이프라인"])
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


@router.delete("/api/orders/{order_id}", response_model=MessageResponse, tags=["입고 파이프라인"])
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


@router.get("/api/productions", response_model=List[ProductionResponse], tags=["입고 파이프라인"])
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


@router.post("/api/productions", response_model=ProductionResponse, tags=["입고 파이프라인"])
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


@router.delete("/api/productions/{prod_id}", response_model=MessageResponse, tags=["입고 파이프라인"])
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


@router.get("/api/inbound", response_model=List[InboundResponse], tags=["입고 파이프라인"])
def get_inbounds(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    """입고 리스트 조회 (상태 필터 지원)"""
    query = db.query(InboundDB)
    if status_filter:
        query = query.filter(InboundDB.status == status_filter)
    return query.order_by(InboundDB.id.desc()).all()


@router.post("/api/inbound", response_model=InboundResponse, tags=["입고 파이프라인"])
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


@router.put("/api/inbound/{inbound_id}", response_model=InboundResponse, tags=["입고 파이프라인"])
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
        "invoice_no", "bl_no", "mapping_value", "purchase_code", "production_code", 
        "shipping_date", "korea_arrival_date", "eta", "manufacture_date", "expiry_date", 
        "carton_qty", "can_qty", "unit_price", "total_price", "payment_date", "invoice_date", 
        "exchange_rate", "payment_amount_krw", "arrival_wh_id", "matched_production_id",
        "product_code", "status",
    }
    for key, value in data.items():
        if key in allowed_fields:
            setattr(db_inbound, key, value)
    db.commit()
    db.refresh(db_inbound)
    return db_inbound


@router.delete("/api/inbound/{inbound_id}", response_model=MessageResponse, tags=["입고 파이프라인"])
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


@router.post("/api/matching/link", response_model=MatchResponse, tags=["매칭"])
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
    matched_inbound_id = None

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

    # Stage 2: 생산 → 입고 연결
    if req.production_id and req.inbound_id:
        production = db.query(ProductionDB).filter(ProductionDB.id == req.production_id).first()
        if not production:
            raise HTTPException(status_code=404, detail="생산을 찾을 수 없습니다")
        inbound = db.query(InboundDB).filter(InboundDB.id == req.inbound_id).first()
        if not inbound:
            raise HTTPException(status_code=404, detail="입고를 찾을 수 없습니다")
        inbound.matched_production_id = req.production_id
        matched_production_id = req.production_id
        matched_inbound_id = req.inbound_id

    db.commit()
    return MatchResponse(
        message="매칭이 완료되었습니다",
        matched_order_id=matched_order_id,
        matched_production_id=matched_production_id,
        matched_inbound_id=matched_inbound_id,
    )


@router.get("/api/matching/status", tags=["매칭"])
def get_matching_status(db: Session = Depends(get_db)):
    """현재 매칭 상태 조회 — 매칭 이력 테이블용"""
    productions = db.query(ProductionDB).all()
    result = []
    for prod in productions:
        order = None
        if prod.matched_order_id:
            order = db.query(OrderDB).filter(OrderDB.id == prod.matched_order_id).first()
            
        inbounds = db.query(InboundDB).filter(InboundDB.matched_production_id == prod.id).all()
        
        if inbounds:
            for inv in inbounds:
                result.append({
                    "order_id": order.id if order else None,
                    "product_code": prod.product_code,
                    "order_month": order.order_month if order else prod.order_month,
                    "order_qty": order.order_qty if order else None,
                    "production_code": prod.production_code,
                    "production_qty": prod.production_qty,
                    "invoice_no": inv.invoice_no,
                    "inbound_status": inv.status,
                    "carton_qty": inv.carton_qty,
                })
        else:
            result.append({
                "order_id": order.id if order else None,
                "product_code": prod.product_code,
                "order_month": order.order_month if order else prod.order_month,
                "order_qty": order.order_qty if order else None,
                "production_code": prod.production_code,
                "production_qty": prod.production_qty,
                "invoice_no": None,
                "inbound_status": None,
                "carton_qty": None,
            })
            
    # 주문만 있고 생산 매칭 안된 건 추가
    unmatched_orders = db.query(OrderDB).filter(
        ~OrderDB.id.in_([p.matched_order_id for p in productions if p.matched_order_id])
    ).all()
    
    for o in unmatched_orders:
        result.append({
            "order_id": o.id,
            "product_code": o.product_code,
            "order_month": o.order_month,
            "order_qty": o.order_qty,
            "production_code": None,
            "production_qty": None,
            "invoice_no": None,
            "carton_qty": None,
        })

    result.sort(key=lambda x: str(x.get("order_month") or ""), reverse=True)
    return result



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
