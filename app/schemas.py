"""
Pydantic 데이터 검증 명세 모듈
- FastAPI 요청/응답 직렬화용 스키마
- 명세서 CH 3 테이블 구조와 1:1 대응
"""

from typing import Optional
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════
# 상품 마스터 스키마
# ═══════════════════════════════════════════════════════════════════════


class ProductMasterBase(BaseModel):
    product_code: str = Field(..., description="품목 코드 (예: SN-001)")
    product_name: str = Field(..., description="브랜드 및 단계 포함 명칭")
    pack_qty_per_tu: int = Field(..., ge=1, description="카툰당 입수량")
    fixed_unit_price: float = Field(..., gt=0, description="연간 고정 외화 매입 단가")
    hub_moq: int = Field(..., ge=1, description="허브 최소 발주 수량 (캔)")


class ProductMasterCreate(ProductMasterBase):
    pass


class ProductMasterResponse(ProductMasterBase):
    id: int

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 풀필먼트 마스터 스키마
# ═══════════════════════════════════════════════════════════════════════


class FFCMasterBase(BaseModel):
    ffc_code: str = Field(..., description="거점 코드")
    ffc_name: str = Field(..., description="거점 채널명")
    ffc_type: str = Field(..., pattern="^(ONLINE|OFFLINE|BUYOUT)$")
    allowed_expiry_days: int = Field(default=90, ge=0)
    ffc_moq: int = Field(default=0, ge=0)


class FFCMasterCreate(FFCMasterBase):
    pass


class FFCMasterResponse(FFCMasterBase):
    id: int

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 물류비 마스터 스키마
# ═══════════════════════════════════════════════════════════════════════


class LogisticsCostBase(BaseModel):
    departure_ffc_id: int
    arrival_ffc_id: int
    cost_per_tu: int = Field(..., ge=0, description="카툰당 이관 물류 비용")


class LogisticsCostCreate(LogisticsCostBase):
    pass


class LogisticsCostResponse(LogisticsCostBase):
    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 입고 리스트 스키마
# ═══════════════════════════════════════════════════════════════════════


class InboundListBase(BaseModel):
    production_ym_code: str
    order_code: str
    invoice_no: str
    bl_no: str
    product_id: int
    tu_qty: int = Field(..., ge=0)
    actual_can_qty: int = Field(..., ge=0)
    manufactured_date: str = Field(..., description="제조년월 (YYYY-MM)")
    expiry_date: str = Field(..., description="유통기한 (YYYY-MM-DD)")
    shipping_date: Optional[str] = None
    arrival_date: Optional[str] = None
    actual_inbound_date: Optional[str] = None
    payment_due_date: Optional[str] = None
    exchange_rate: float = Field(..., gt=0)
    total_inventory_value: Optional[int] = None


class InboundListCreate(InboundListBase):
    pass


class InboundListResponse(InboundListBase):
    inbound_id: int

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 입고 예정 스키마
# ═══════════════════════════════════════════════════════════════════════


class ExpectedInboundBase(BaseModel):
    product_id: int
    inbound_ref_no: str
    expected_qty: int = Field(..., ge=0)
    eta_date: str = Field(..., description="입고 예정일 (YYYY-MM-DD)")
    status: str = Field(..., pattern="^(IN_TRANSIT|CUSTOMS)$")


class ExpectedInboundCreate(ExpectedInboundBase):
    pass


class ExpectedInboundResponse(ExpectedInboundBase):
    expected_id: int

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 현재고 스키마
# ═══════════════════════════════════════════════════════════════════════


class CurrentInventoryBase(BaseModel):
    ffc_id: int
    inbound_id: int
    current_can_qty: int = Field(default=0, ge=0)


class CurrentInventoryCreate(CurrentInventoryBase):
    pass


class CurrentInventoryResponse(CurrentInventoryBase):
    inventory_id: int
    last_updated: Optional[str] = None

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 출고 이력 스키마
# ═══════════════════════════════════════════════════════════════════════


class OutflowHistoryBase(BaseModel):
    ffc_id: int
    product_id: int
    base_date: str = Field(..., description="주차 기준일 (YYYY-MM-DD)")
    beginning_inventory: int = Field(..., ge=0)
    ending_inventory: int = Field(..., ge=0)
    simple_outflow_qty: int
    outflow_type: str = Field(default="SALES", pattern="^(SALES|LOSS|TRANSFER)$")


class OutflowHistoryCreate(OutflowHistoryBase):
    pass


class OutflowHistoryResponse(OutflowHistoryBase):
    outflow_id: int

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 이관 계획 스키마
# ═══════════════════════════════════════════════════════════════════════


class TransferPlanBase(BaseModel):
    product_id: int
    departure_ffc_id: int
    arrival_ffc_id: int
    target_tu_qty: int = Field(..., ge=0)
    target_can_qty: int = Field(..., ge=0)
    estimated_logistics_cost: Optional[int] = None
    transfer_status: str = Field(
        default="PLANNED", pattern="^(PLANNED|IN_TRANSIT|DONE)$"
    )


class TransferPlanCreate(TransferPlanBase):
    pass


class TransferPlanResponse(TransferPlanBase):
    transfer_id: int

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 매칭 히스토리 로그 스키마
# ═══════════════════════════════════════════════════════════════════════


class MatchingHistoryLogBase(BaseModel):
    production_ym_code: str
    matched_invoice_no: str
    product_id: int
    production_qty: int = Field(..., ge=0)
    invoice_qty: int = Field(..., ge=0)
    discrepancy_rate: Optional[float] = None
    date_gap_days: Optional[int] = None


class MatchingHistoryLogCreate(MatchingHistoryLogBase):
    pass


class MatchingHistoryLogResponse(MatchingHistoryLogBase):
    log_id: int
    matched_at: Optional[str] = None

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 월별 발주 계획 스키마
# ═══════════════════════════════════════════════════════════════════════


class MonthlyOrderPlanBase(BaseModel):
    target_month: str = Field(..., description="발주 대상 연월 (YYYY-MM)")
    product_id: int
    system_suggested_qty: int = Field(..., ge=0)
    user_modified_qty: int = Field(..., ge=0)


class MonthlyOrderPlanCreate(MonthlyOrderPlanBase):
    pass


class MonthlyOrderPlanUpdate(BaseModel):
    user_modified_qty: int = Field(..., ge=0, description="실무자 수정 최종 수량")


class MonthlyOrderPlanResponse(MonthlyOrderPlanBase):
    plan_id: int
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# 공통 응답 스키마
# ═══════════════════════════════════════════════════════════════════════


class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None


class FileUploadResponse(BaseModel):
    message: str
    filename: str
    rows_processed: int
    rows_inserted: int
    rows_updated: int = 0
