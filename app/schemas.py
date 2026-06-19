"""
Pydantic 데이터 검증 명세 모듈
- FastAPI 요청/응답 직렬화용 스키마
- 모든 '마스터' 용어를 'DB'로 교체
"""

from typing import Optional, List
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════
# 공통 응답
# ═══════════════════════════════════════════════════════════════════════

class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════
# 시스템 관리
# ═══════════════════════════════════════════════════════════════════════

class UserAccountBase(BaseModel):
    username: str
    role: str = Field(pattern="^(ADMIN|OPERATOR)$")
    name: str

class UserAccountCreate(UserAccountBase):
    password: str

class UserAccountResponse(UserAccountBase):
    id: int
    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None

class SystemSnapshotResponse(BaseModel):
    id: int
    snapshot_path: str
    created_at: str
    created_by: Optional[int] = None
    is_auto: bool
    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 품목 DB
# ═══════════════════════════════════════════════════════════════════════

class ProductCreate(BaseModel):
    product_code: str = Field(..., description="품목코드 (수정 불가)")
    product_name: str = Field(..., description="품목명")
    pack_qty_per_tu: Optional[int] = Field(default=24, ge=1, description="카툰당 입수량")
    currency_unit: Optional[str] = Field(default="USD", description="환율단위")
    purchase_price: Optional[float] = Field(default=0, ge=0, description="매입가")

class ProductUpdate(BaseModel):
    """품목 수정 — product_code는 변경 불가"""
    product_name: Optional[str] = None
    pack_qty_per_tu: Optional[int] = Field(default=None, ge=1)
    currency_unit: Optional[str] = None
    purchase_price: Optional[float] = Field(default=None, ge=0)

class ProductResponse(BaseModel):
    id: int
    product_code: str
    product_name: str
    pack_qty_per_tu: int
    currency_unit: str
    purchase_price: float
    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 창고 DB
# ═══════════════════════════════════════════════════════════════════════

class WarehouseCreate(BaseModel):
    warehouse_name: str = Field(..., description="창고명 (수정 불가)")
    warehouse_type: str = Field(default="ONLINE", pattern="^(ONLINE|OFFLINE|BUYOUT)$")
    allowed_expiry_days: int = Field(default=90, ge=0)
    moq: int = Field(default=0, ge=0)

class WarehouseUpdate(BaseModel):
    """창고 수정 — warehouse_name은 변경 불가"""
    warehouse_type: Optional[str] = Field(default=None, pattern="^(ONLINE|OFFLINE|BUYOUT)$")
    allowed_expiry_days: Optional[int] = Field(default=None, ge=0)
    moq: Optional[int] = Field(default=None, ge=0)

class WarehouseResponse(BaseModel):
    id: int
    warehouse_name: str
    warehouse_type: str
    allowed_expiry_days: int
    moq: int
    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 물류비 DB
# ═══════════════════════════════════════════════════════════════════════

class LogisticsCostCreate(BaseModel):
    departure_wh_id: int
    arrival_wh_id: int
    cost_per_tu: int = Field(..., ge=0)

class LogisticsCostResponse(BaseModel):
    departure_wh_id: int
    arrival_wh_id: int
    cost_per_tu: int
    departure_name: Optional[str] = None
    arrival_name: Optional[str] = None
    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 창고-품목 MOQ
# ═══════════════════════════════════════════════════════════════════════

class WarehouseProductMOQCreate(BaseModel):
    warehouse_id: int
    product_id: int
    transfer_moq: int = Field(default=0, ge=0)

class WarehouseProductMOQResponse(BaseModel):
    id: int
    warehouse_id: int
    product_id: int
    transfer_moq: int
    warehouse_name: Optional[str] = None
    product_name: Optional[str] = None
    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 발주 DB
# ═══════════════════════════════════════════════════════════════════════

class OrderCreate(BaseModel):
    order_month: str = Field(..., description="발주월 (YYYY-MM)")
    product_code: str
    order_qty: int = Field(..., ge=0)

class OrderResponse(BaseModel):
    id: int
    order_month: str
    product_code: str
    order_qty: int
    created_at: Optional[str] = None
    product_name: Optional[str] = None
    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 생산 DB
# ═══════════════════════════════════════════════════════════════════════

class ProductionCreate(BaseModel):
    purchase_code: str
    production_code: str
    order_month: Optional[str] = None
    production_qty: int = Field(..., ge=0)
    product_code: str
    matched_order_id: Optional[int] = None

class ProductionResponse(BaseModel):
    id: int
    purchase_code: str
    production_code: str
    order_month: Optional[str] = None
    production_qty: int
    product_code: str
    matched_order_id: Optional[int] = None
    created_at: Optional[str] = None
    product_name: Optional[str] = None
    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 인보이스 DB
# ═══════════════════════════════════════════════════════════════════════

class InvoiceCreate(BaseModel):
    invoice_no: str
    mapping_value: Optional[str] = None
    purchase_code: Optional[str] = None
    production_code: Optional[str] = None
    carton_qty: Optional[int] = None
    unit_price: Optional[float] = None
    total_price: Optional[float] = None
    product_name: Optional[str] = None
    product_code: Optional[str] = None
    eta: Optional[str] = None
    payment_date: Optional[str] = None
    invoice_date: Optional[str] = None
    exchange_rate: Optional[float] = None
    payment_amount_krw: Optional[int] = None
    matched_production_id: Optional[int] = None

class InvoiceResponse(InvoiceCreate):
    id: int
    created_at: Optional[str] = None
    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 입고 DB
# ═══════════════════════════════════════════════════════════════════════

class InboundCreate(BaseModel):
    invoice_no: Optional[str] = None
    bl_no: Optional[str] = None
    shipping_date: Optional[str] = None
    korea_arrival_date: Optional[str] = None
    manufacture_date: Optional[str] = None
    expiry_date: Optional[str] = None
    carton_qty: Optional[int] = None
    can_qty: Optional[int] = None
    product_code: Optional[str] = None
    status: str = Field(default="생산국출발")

class InboundResponse(InboundCreate):
    id: int
    created_at: Optional[str] = None
    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 현재고 스냅샷
# ═══════════════════════════════════════════════════════════════════════

class InventorySnapshotCreate(BaseModel):
    snapshot_date: str
    warehouse_id: Optional[int] = None
    warehouse_name: Optional[str] = None
    product_name: Optional[str] = None
    product_code: Optional[str] = None
    expiry_date: Optional[str] = None
    qty_cans: int = Field(default=0, ge=0)

class InventorySnapshotResponse(InventorySnapshotCreate):
    id: int
    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 이관 계획
# ═══════════════════════════════════════════════════════════════════════

class TransferPlanCreate(BaseModel):
    product_id: int
    departure_wh_id: int
    arrival_wh_id: int
    target_tu_qty: int = Field(default=0, ge=0)
    target_can_qty: int = Field(default=0, ge=0)
    estimated_logistics_cost: Optional[int] = None
    transfer_date: Optional[str] = None

class TransferPlanResponse(BaseModel):
    transfer_id: int
    product_id: int
    departure_wh_id: int
    arrival_wh_id: int
    target_tu_qty: int
    target_can_qty: int
    estimated_logistics_cost: Optional[int] = None
    transfer_date: Optional[str] = None
    transfer_status: str
    product_name: Optional[str] = None
    departure_name: Optional[str] = None
    arrival_name: Optional[str] = None
    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 발주 계획 (시뮬레이션)
# ═══════════════════════════════════════════════════════════════════════

class OrderPlanCreate(BaseModel):
    target_month: str
    product_id: int
    user_modified_qty: int = Field(default=0, ge=0)

class OrderPlanBulkSave(BaseModel):
    plans: List[OrderPlanCreate]

class OrderPlanResponse(BaseModel):
    plan_id: int
    target_month: str
    product_id: int
    system_suggested_qty: int
    user_modified_qty: int
    version: int
    updated_at: Optional[str] = None
    product_code: Optional[str] = None
    product_name: Optional[str] = None
    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 매칭 요청
# ═══════════════════════════════════════════════════════════════════════

class MatchRequest(BaseModel):
    """3단 매칭 요청"""
    order_id: Optional[int] = None
    production_id: Optional[int] = None
    invoice_id: Optional[int] = None

class MatchResponse(BaseModel):
    message: str
    matched_order_id: Optional[int] = None
    matched_production_id: Optional[int] = None
    matched_invoice_id: Optional[int] = None
