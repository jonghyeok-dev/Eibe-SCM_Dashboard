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
    _FORECASTING_AVAILABLE = True
except Exception:
    _FORECASTING_AVAILABLE = False

router = APIRouter()
WEB_DIR = os.path.join(BASE_DIR, "web")

@router.get("/api/inventory-snapshot", response_model=List[InventorySnapshotResponse], tags=["재고 관리"])
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


@router.post("/api/inventory-snapshot", response_model=InventorySnapshotResponse, tags=["재고 관리"])
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


@router.delete("/api/inventory-snapshot/{snap_id}", response_model=MessageResponse, tags=["재고 관리"])
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


@router.post("/api/inventory-snapshot/upload", response_model=MessageResponse, tags=["재고 관리"])
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
    try:
        for _, row in df.iterrows():
            snap_date = str(row["snapshot_date"]).strip()
            if not snap_date or pd.isna(row["snapshot_date"]):
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
    except ValueError as ve:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"입력값 형식이 올바르지 않습니다 (숫자 오류 등): {ve}")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"엑셀 데이터 처리 중 오류 발생: {e}")
    return MessageResponse(message=f"스냅샷 업로드 완료: {created}건 등록")


@router.get("/api/inventory/summary", tags=["재고 관리"])
def get_inventory_summary(db: Session = Depends(get_db)):
    """전체 현재고 요약 (창고별, 품목별 집계 — InventorySnapshot 기반)"""
    
    # Helper to calculate actual unit price
    unit_price_cache = {}
    def get_unit_price(p_code, exp_date):
        if not p_code or not exp_date:
            return 0
        cache_key = (p_code, exp_date)
        if cache_key in unit_price_cache:
            return unit_price_cache[cache_key]
            
        inbound = db.query(InboundDB).filter(InboundDB.product_code == p_code, InboundDB.expiry_date == exp_date).first()
        price = 0
        if inbound and inbound.invoice_no:
            invoice = db.query(InvoiceDB).filter(InvoiceDB.invoice_no == inbound.invoice_no).first()
            if invoice and invoice.payment_amount_krw:
                qty = inbound.can_qty
                if not qty and inbound.carton_qty:
                    prod = db.query(ProductDB).filter(ProductDB.product_code == p_code).first()
                    if prod:
                        qty = inbound.carton_qty * prod.pack_qty_per_tu
                if qty and qty > 0:
                    price = int(invoice.payment_amount_krw / qty)
        
        if not price:
            prod = db.query(ProductDB).filter(ProductDB.product_code == p_code).first()
            if prod:
                price = int(prod.purchase_price * 1350)
        
        unit_price_cache[cache_key] = price
        return price
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
                "total_value_krw": 0,
            }

        prod_key = snap.product_code or snap.product_name or "UNKNOWN"
        if prod_key not in summary_by_wh[wh_key]["products"]:
            summary_by_wh[wh_key]["products"][prod_key] = {
                "product_code": snap.product_code,
                "product_name": snap.product_name,
                "total_qty": 0,
                "total_value_krw": 0,
                "batches": [],
            }

        remaining_days = None
        if snap.expiry_date and _FORECASTING_AVAILABLE:
            try:
                remaining_days = calc_remaining_expiry_days(snap.expiry_date)
            except Exception:
                pass

        summary_by_wh[wh_key]["products"][prod_key]["total_qty"] += snap.qty_cans
        
        unit_price = get_unit_price(snap.product_code, snap.expiry_date)
        batch_value = snap.qty_cans * unit_price
        summary_by_wh[wh_key]["products"][prod_key]["total_value_krw"] += batch_value
        summary_by_wh[wh_key]["total_value_krw"] += batch_value

        summary_by_wh[wh_key]["products"][prod_key]["batches"].append({
            "snapshot_id": snap.id,
            "qty_cans": snap.qty_cans,
            "expiry_date": snap.expiry_date,
            "remaining_days": remaining_days,
            "unit_price_krw": unit_price,
            "total_value_krw": batch_value,
        })
        summary_by_wh[wh_key]["total_qty"] += snap.qty_cans

    result = []
    for wh_data in summary_by_wh.values():
        wh_data["products"] = list(wh_data["products"].values())
        result.append(wh_data)
    return result


@router.get("/api/expiry/summary", tags=["유통기한 관리"])
def get_expiry_summary(db: Session = Depends(get_db)):
    """유통기한 임박 재고 요약 (InventorySnapshot + WarehouseDB.allowed_expiry_days)"""
    
    # Helper to calculate actual unit price
    unit_price_cache = {}
    def get_unit_price(p_code, exp_date):
        if not p_code or not exp_date:
            return 0
        cache_key = (p_code, exp_date)
        if cache_key in unit_price_cache:
            return unit_price_cache[cache_key]
            
        inbound = db.query(InboundDB).filter(InboundDB.product_code == p_code, InboundDB.expiry_date == exp_date).first()
        price = 0
        if inbound and inbound.invoice_no:
            invoice = db.query(InvoiceDB).filter(InvoiceDB.invoice_no == inbound.invoice_no).first()
            if invoice and invoice.payment_amount_krw:
                qty = inbound.can_qty
                if not qty and inbound.carton_qty:
                    prod = db.query(ProductDB).filter(ProductDB.product_code == p_code).first()
                    if prod:
                        qty = inbound.carton_qty * prod.pack_qty_per_tu
                if qty and qty > 0:
                    price = int(invoice.payment_amount_krw / qty)
        
        if not price:
            prod = db.query(ProductDB).filter(ProductDB.product_code == p_code).first()
            if prod:
                price = int(prod.purchase_price * 1350)
        
        unit_price_cache[cache_key] = price
        return price

    # Helper for weekly outflow
    outflow_cache = {}
    def get_weekly_outflow(wh_id, p_code):
        if not wh_id or not p_code:
            return 0.0
        cache_key = (wh_id, p_code)
        if cache_key in outflow_cache:
            return outflow_cache[cache_key]
            
        prod = db.query(ProductDB).filter(ProductDB.product_code == p_code).first()
        if not prod:
            outflow_cache[cache_key] = 0.0
            return 0.0
            
        outflows = db.query(OutflowHistory).filter(
            OutflowHistory.warehouse_id == wh_id,
            OutflowHistory.product_id == prod.id
        ).order_by(OutflowHistory.base_date.desc()).limit(12).all()
        
        if not outflows:
            outflow_cache[cache_key] = 0.0
            return 0.0
            
        avg = sum(o.simple_outflow_qty for o in outflows) / len(outflows)
        outflow_cache[cache_key] = avg
        return avg

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
        
        sellable_days = remaining - threshold
        if sellable_days < 0:
            sellable_days = 0
            
        weekly_outflow = get_weekly_outflow(snap.warehouse_id, snap.product_code)
        daily_outflow = weekly_outflow / 7.0 if weekly_outflow > 0 else 0
        
        depletion_date = "-"
        if daily_outflow > 0:
            days_to_deplete = int(snap.qty_cans / daily_outflow)
            depletion_date = (date.today() + timedelta(days=days_to_deplete)).isoformat()
            
        expected_sales = daily_outflow * sellable_days
        additional_sales_required = snap.qty_cans - expected_sales
        if additional_sales_required < 0:
            additional_sales_required = 0
            
        unit_price = get_unit_price(snap.product_code, snap.expiry_date)
        disposal_value_krw = int(additional_sales_required) * unit_price

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
            "sellable_days": sellable_days,
            "depletion_date": depletion_date,
            "additional_sales_required": int(additional_sales_required),
            "disposal_value": disposal_value_krw,
            "unit_price_krw": unit_price
        })

    items.sort(key=lambda x: x["remaining_days"])
    wh_set = set(i["warehouse_id"] for i in items if i["warehouse_id"])
    return {
        "items": items,
        "total_risk_count": len(items),
        "critical_count": sum(1 for i in items if i["remaining_days"] <= 30),
        "warehouse_count": len(wh_set),
    }


@router.get("/api/transfer-plan", response_model=List[TransferPlanResponse], tags=["이관 계획"])
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


@router.post("/api/transfer-plan", response_model=MessageResponse, tags=["이관 계획"])
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


@router.put("/api/transfer-plan/{plan_id}/confirm", response_model=MessageResponse, tags=["이관 계획"])
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


@router.delete("/api/transfer-plan/{plan_id}", response_model=MessageResponse, tags=["이관 계획"])
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


@router.get("/api/order-plan/simulation", tags=["발주 계획"])
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

        # 도착월 기준 발주 계획 데이터 통합
        today = date.today()
        plans = db.query(MonthlyOrderPlan).filter(MonthlyOrderPlan.product_id == product.id).all()
        expected_inbounds_dict = {}
        for p in plans:
            if p.arrival_month and p.user_modified_qty > 0:
                try:
                    arr_date = datetime.strptime(p.arrival_month, "%Y-%m").date()
                    delta_days = (arr_date - today).days
                    wk = int(delta_days / 7) + 1
                    if wk < 1: wk = 1
                    if wk <= 24:
                        expected_inbounds_dict[wk] = expected_inbounds_dict.get(wk, 0) + p.user_modified_qty
                except Exception:
                    pass

        # 시뮬레이션
        simulation = simulate_future_inventory(
            current_stock=total_stock,
            smoothing_constant=smoothing,
            loss_buffer=loss_buffer,
            pipeline_inbounds={},
            expected_inbounds=expected_inbounds_dict,
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


@router.post("/api/order-plan/save", response_model=MessageResponse, tags=["발주 계획"])
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
            if item.arrival_month is not None:
                existing.arrival_month = item.arrival_month
            existing.version = (existing.version or 1) + 1
            existing.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            new_plan = MonthlyOrderPlan(
                target_month=item.target_month,
                arrival_month=item.arrival_month,
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


@router.get("/api/order-plan", response_model=List[OrderPlanResponse], tags=["발주 계획"])
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
                arrival_month=p.arrival_month,
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


@router.delete("/api/order-plan/{plan_id}", response_model=MessageResponse, tags=["발주 계획"])
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


@router.get("/api/outflow", tags=["출고 관리"])
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


@router.get("/api/sales", tags=["판매 실적"])
def get_sales(
    product_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """판매 실적 조회"""
    query = db.query(SalesHistory)
    if product_id:
        query = query.filter(SalesHistory.product_id == product_id)
    return query.order_by(SalesHistory.base_date.desc()).all()


@router.post("/api/sales", tags=["판매 실적"])
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


@router.get("/api/templates/{template_type}", tags=["데이터 수집"])
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


@router.get("/api/excel/template-types", tags=["데이터 수집"])
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
