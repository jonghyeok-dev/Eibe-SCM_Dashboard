"""
3NF 관계형 테이블 스키마 정의 모듈
- 명세서 CH 3 기준 전체 10개 테이블 구현
- 모든 대리 기본키: INTEGER PRIMARY KEY AUTOINCREMENT
"""

from sqlalchemy import (
    Column,
    Integer,
    Text,
    Float,
    Boolean,
    ForeignKey,
    CheckConstraint,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.database import Base


# ═══════════════════════════════════════════════════════════════════════
# 3.0. 시스템 관리 영역 (System Admin Tables)
# ═══════════════════════════════════════════════════════════════════════

class UserAccount(Base):
    """3.0.1. 사용자 계정 테이블 - 권한 및 인증 관리"""
    __tablename__ = "USER_ACCOUNT"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(Text, unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(Text, nullable=False) # ADMIN or OPERATOR
    name = Column(Text, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "role IN ('ADMIN', 'OPERATOR')",
            name="chk_user_role",
        ),
    )


class SystemSnapshot(Base):
    """3.0.2. 시스템 스냅샷 테이블 - 백업 관리"""
    __tablename__ = "SYSTEM_SNAPSHOT"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_path = Column(Text, nullable=False)
    created_at = Column(Text, nullable=False) # 기본값은 DB 삽입 시 처리 예정
    created_by = Column(Integer, ForeignKey("USER_ACCOUNT.id"), nullable=True)
    is_auto = Column(Boolean, default=True)

    # Relationships
    creator = relationship("UserAccount")


# ═══════════════════════════════════════════════════════════════════════
# 3.1. 기준 정보 영역 (Master Data Tables)
# ═══════════════════════════════════════════════════════════════════════


class ProductMaster(Base):
    """3.1.1. 상품 마스터 테이블 - 분유 제품 고유 식별 및 연간 고정 단가"""

    __tablename__ = "PRODUCT_MASTER"

    id = Column(Integer, primary_key=True, autoincrement=True)
    product_code = Column(Text, unique=True, nullable=False)        # 품목 코드 (예: SN-001)
    product_name = Column(Text, nullable=False)                     # 브랜드 및 단계 포함 명칭
    pack_qty_per_tu = Column(Integer, nullable=False)               # 카툰(Box)당 입수량
    fixed_unit_price = Column(Float, nullable=False)                 # 연간 고정 외화 매입 단가
    hub_moq = Column(Integer, nullable=False)                       # 메인 허브 해외 발주 최소 수량 (캔)

    # Relationships
    inbound_items = relationship("InboundList", back_populates="product")
    expected_inbounds = relationship("ExpectedInbound", back_populates="product")
    outflow_histories = relationship("OutflowHistory", back_populates="product")
    transfer_plans = relationship("TransferPlan", back_populates="product")
    matching_logs = relationship("MatchingHistoryLog", back_populates="product")
    order_plans = relationship("MonthlyOrderPlan", back_populates="product")


class FFCMaster(Base):
    """3.1.2. 풀필먼트 마스터 테이블 - 물류 거점 채널별 유통기한 제약 조건"""

    __tablename__ = "FFC_MASTER"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ffc_code = Column(Text, unique=True, nullable=False)            # 거점 코드 (예: HUB, FFC_ON)
    ffc_name = Column(Text, nullable=False)                         # 거점 채널명
    ffc_type = Column(Text, nullable=False)                         # ONLINE / OFFLINE / BUYOUT
    allowed_expiry_days = Column(Integer, default=90)               # 허용 잔여 유통기한 임계일수
    ffc_moq = Column(Integer, default=0)                            # 거점 이관 최소 수량

    __table_args__ = (
        CheckConstraint(
            "ffc_type IN ('ONLINE', 'OFFLINE', 'BUYOUT')",
            name="chk_ffc_type",
        ),
    )

    # Relationships
    inventories = relationship("CurrentInventory", back_populates="ffc")
    outflow_histories = relationship("OutflowHistory", back_populates="ffc")
    departures = relationship(
        "TransferPlan",
        foreign_keys="TransferPlan.departure_ffc_id",
        back_populates="departure_ffc",
    )
    arrivals = relationship(
        "TransferPlan",
        foreign_keys="TransferPlan.arrival_ffc_id",
        back_populates="arrival_ffc",
    )
    departure_costs = relationship(
        "LogisticsCostMaster",
        foreign_keys="LogisticsCostMaster.departure_ffc_id",
        back_populates="departure_ffc",
    )
    arrival_costs = relationship(
        "LogisticsCostMaster",
        foreign_keys="LogisticsCostMaster.arrival_ffc_id",
        back_populates="arrival_ffc",
    )


class LogisticsCostMaster(Base):
    """3.1.3. 구간별 물류비 마스터 테이블 - 거점 간 카툰당 물류 이동 단가"""

    __tablename__ = "LOGISTICS_COST_MASTER"

    departure_ffc_id = Column(
        Integer, ForeignKey("FFC_MASTER.id"), primary_key=True, nullable=False
    )
    arrival_ffc_id = Column(
        Integer, ForeignKey("FFC_MASTER.id"), primary_key=True, nullable=False
    )
    cost_per_tu = Column(Integer, nullable=False)                   # 카툰당 이관 물류 비용 단가

    # Relationships
    departure_ffc = relationship(
        "FFCMaster", foreign_keys=[departure_ffc_id], back_populates="departure_costs"
    )
    arrival_ffc = relationship(
        "FFCMaster", foreign_keys=[arrival_ffc_id], back_populates="arrival_costs"
    )


# ═══════════════════════════════════════════════════════════════════════
# 3.2. 입고 및 파이프라인 영역 (Inbound Pipeline Tables)
# ═══════════════════════════════════════════════════════════════════════


class InboundList(Base):
    """3.2.1. 입고 리스트 테이블 - 코어 공급망 파이프라인 이력"""

    __tablename__ = "INBOUND_LIST"

    inbound_id = Column(Integer, primary_key=True, autoincrement=True)
    production_ym_code = Column(Text, nullable=False)               # 생산년월 코드
    order_code = Column(Text, nullable=False)                       # 발주 코드값
    invoice_no = Column(Text, nullable=False)                       # 매입 인보이스 번호
    bl_no = Column(Text, nullable=False)                            # 선하증권 번호
    product_id = Column(Integer, ForeignKey("PRODUCT_MASTER.id"), nullable=False)
    tu_qty = Column(Integer, nullable=False)                        # 카툰 수 (TU)
    actual_can_qty = Column(Integer, nullable=False)                # 실제 캔 수
    manufactured_date = Column(Text, nullable=False)                # 제조년월 (YYYY-MM)
    expiry_date = Column(Text, nullable=False)                      # 유통기한 (YYYY-MM-DD)
    shipping_date = Column(Text)                                    # 선적일
    arrival_date = Column(Text)                                     # 한국 도착일
    actual_inbound_date = Column(Text)                              # 실제 창고 완료일
    payment_due_date = Column(Text)                                 # 결제 기일
    exchange_rate = Column(Float, nullable=False)                   # 결제 적용 환율
    total_inventory_value = Column(Integer)                         # 캔수 * 고정단가 * 환율

    # Relationships
    product = relationship("ProductMaster", back_populates="inbound_items")
    inventories = relationship("CurrentInventory", back_populates="inbound")


class ExpectedInbound(Base):
    """3.2.2. 입고 예정 리스트 테이블 - 해상 운송/통관 대기 물량"""

    __tablename__ = "EXPECTED_INBOUND"

    expected_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("PRODUCT_MASTER.id"), nullable=False)
    inbound_ref_no = Column(Text, nullable=False)                   # B/L No 또는 출하 번호
    expected_qty = Column(Integer, nullable=False)                  # 입고 예정 수량 (캔)
    eta_date = Column(Text, nullable=False)                         # 입고 예정일 (YYYY-MM-DD)
    status = Column(Text, nullable=False)                           # IN_TRANSIT / CUSTOMS

    __table_args__ = (
        CheckConstraint(
            "status IN ('IN_TRANSIT', 'CUSTOMS')",
            name="chk_expected_status",
        ),
    )

    # Relationships
    product = relationship("ProductMaster", back_populates="expected_inbounds")


# ═══════════════════════════════════════════════════════════════════════
# 3.3. 현장 실적 및 계획 데이터 영역 (Execution & Simulation Tables)
# ═══════════════════════════════════════════════════════════════════════


class CurrentInventory(Base):
    """3.3.1. 현재고 테이블 - 각 거점 창고 실시간 실재고"""

    __tablename__ = "CURRENT_INVENTORY"

    inventory_id = Column(Integer, primary_key=True, autoincrement=True)
    ffc_id = Column(Integer, ForeignKey("FFC_MASTER.id"), nullable=False)
    inbound_id = Column(
        Integer, ForeignKey("INBOUND_LIST.inbound_id"), nullable=False
    )
    current_can_qty = Column(Integer, nullable=False, default=0)    # 현재 보관 실재고 (캔)
    last_updated = Column(Text)                                     # 최종 업데이트 타임스탬프

    # Relationships
    ffc = relationship("FFCMaster", back_populates="inventories")
    inbound = relationship("InboundList", back_populates="inventories")


class OutflowHistory(Base):
    """3.3.2. 출고 이력 테이블 - 주차별 재고 소멸 로그"""

    __tablename__ = "OUTFLOW_HISTORY"

    outflow_id = Column(Integer, primary_key=True, autoincrement=True)
    ffc_id = Column(Integer, ForeignKey("FFC_MASTER.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("PRODUCT_MASTER.id"), nullable=False)
    base_date = Column(Text, nullable=False)                        # 주차 기준일 (YYYY-MM-DD)
    beginning_inventory = Column(Integer, nullable=False)           # 기초 재고량
    ending_inventory = Column(Integer, nullable=False)              # 기말 재고량
    simple_outflow_qty = Column(Integer, nullable=False)            # 기초 - 기말
    outflow_type = Column(Text, default="SALES")                    # SALES / LOSS / TRANSFER

    __table_args__ = (
        CheckConstraint(
            "outflow_type IN ('SALES', 'LOSS', 'TRANSFER')",
            name="chk_outflow_type",
        ),
    )

    # Relationships
    ffc = relationship("FFCMaster", back_populates="outflow_histories")
    product = relationship("ProductMaster", back_populates="outflow_histories")


class TransferPlan(Base):
    """3.3.3. 이관 계획 및 실행 테이블 - 거점 간 재고 밸런싱"""

    __tablename__ = "TRANSFER_PLAN"

    transfer_id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer, ForeignKey("PRODUCT_MASTER.id"), nullable=False)
    departure_ffc_id = Column(Integer, ForeignKey("FFC_MASTER.id"), nullable=False)
    arrival_ffc_id = Column(Integer, ForeignKey("FFC_MASTER.id"), nullable=False)
    target_tu_qty = Column(Integer, nullable=False)                 # 이관 카툰 수
    target_can_qty = Column(Integer, nullable=False)                # 이관 캔 수
    estimated_logistics_cost = Column(Integer)                      # 카툰수 * 구간별 물류단가
    transfer_status = Column(Text, default="PLANNED")               # PLANNED / IN_TRANSIT / DONE

    __table_args__ = (
        CheckConstraint(
            "transfer_status IN ('PLANNED', 'IN_TRANSIT', 'DONE')",
            name="chk_transfer_status",
        ),
    )

    # Relationships
    product = relationship("ProductMaster", back_populates="transfer_plans")
    departure_ffc = relationship(
        "FFCMaster", foreign_keys=[departure_ffc_id], back_populates="departures"
    )
    arrival_ffc = relationship(
        "FFCMaster", foreign_keys=[arrival_ffc_id], back_populates="arrivals"
    )


class MatchingHistoryLog(Base):
    """3.3.4. 파이프라인 수동 매칭 학습 로그 테이블"""

    __tablename__ = "MATCHING_HISTORY_LOG"

    log_id = Column(Integer, primary_key=True, autoincrement=True)
    production_ym_code = Column(Text, nullable=False)               # 생산년월 코드
    matched_invoice_no = Column(Text, nullable=False)               # 매칭된 인보이스 번호
    product_id = Column(Integer, ForeignKey("PRODUCT_MASTER.id"), nullable=False)
    production_qty = Column(Integer, nullable=False)                # 생산 완료 수량
    invoice_qty = Column(Integer, nullable=False)                   # 인보이스 수량
    discrepancy_rate = Column(Float)                                # 수량 불일치 백분율
    date_gap_days = Column(Integer)                                 # 생산월-송장일 격차 일수
    matched_at = Column(Text)                                       # 매칭 일시

    # Relationships
    product = relationship("ProductMaster", back_populates="matching_logs")


class MonthlyOrderPlan(Base):
    """3.3.5. 월별 발주 계획 및 저장 테이블 - CRUD 바인딩"""

    __tablename__ = "MONTHLY_ORDER_PLAN"

    plan_id = Column(Integer, primary_key=True, autoincrement=True)
    target_month = Column(Text, nullable=False)                     # 발주 대상 연월 (YYYY-MM)
    product_id = Column(Integer, ForeignKey("PRODUCT_MASTER.id"), nullable=False)
    system_suggested_qty = Column(Integer, nullable=False)          # 시스템 제안 수량
    user_modified_qty = Column(Integer, nullable=False)             # 실무자 수정 최종 수량
    updated_at = Column(Text)                                       # 수정 일시

    __table_args__ = (
        UniqueConstraint("target_month", "product_id", name="uq_month_product"),
    )

    # Relationships
    product = relationship("ProductMaster", back_populates="order_plans")
