"""
SCM 코어 연산 및 수요 평탄화 엔진
- 명세서 CH 5 기준 단순 출고량 평탄화, 동적 감모 버퍼, 미래 재고 시뮬레이션
- 머신러닝 라이브러리 사용 절대 금지 (CH 1.2 §1)
- 모든 예측은 사칙연산 기반의 통계적 평탄화 모델로 제한
"""

import math
from typing import List, Dict, Optional
from datetime import date, timedelta


def calc_weekly_smoothing_constant(outflow_data: List[int]) -> float:
    """
    5.1. 주차별 기준 출고량 평균치 (Smoothing Constant) 산출
    - 직전 12주 단순 출고량 총합 / 12
    - 미래 24주 타임라인에 Flat 상수로 배치

    Args:
        outflow_data: 직전 12주 주차별 단순 출고량 리스트 (최대 12개)
    Returns:
        주차별 기준 출고량 평균치
    """
    if not outflow_data:
        return 0.0

    recent_12w = outflow_data[-12:]  # 직전 12주만 사용
    return sum(recent_12w) / len(recent_12w)


def calc_dynamic_loss_buffer(
    outflow_data: List[int], sales_data: List[int]
) -> float:
    """
    5.2. 동적 감모 버퍼(Dynamic Loss Buffer) 산출
    - (1/12) * Σ(단순출고량 - 순수판매량) for w=1..12

    Args:
        outflow_data: 직전 12주 단순 출고량 리스트
        sales_data: 직전 12주 순수 판매(주문 완료) 수량 리스트
    Returns:
        동적 감모 버퍼 상수
    """
    if not outflow_data or not sales_data:
        return 0.0

    weeks = min(len(outflow_data), len(sales_data), 12)
    loss_sum = sum(
        outflow_data[-(weeks - i)] - sales_data[-(weeks - i)]
        for i in range(weeks)
    )
    return loss_sum / weeks


def simulate_future_inventory(
    current_stock: int,
    smoothing_constant: float,
    loss_buffer: float,
    pipeline_inbounds: Dict[int, int],
    expected_inbounds: Dict[int, int],
    weight_factor: float = 1.0,
    weeks: int = 24,
) -> List[Dict]:
    """
    5.3. 미래 예상 기말재고 시뮬레이션 (24주)

    공식:
        예상기말재고(W) = 이전주차기말재고(W-1)
                       + 파이프라인 입고 확정량
                       + 입고 예정 리스트 수량
                       - (주차별 기준 출고량 평균치 * 가중치 계수 + 동적 감모 버퍼)

    Args:
        current_stock: 현재 보유 재고 수량
        smoothing_constant: 주차별 기준 출고량 평균치
        loss_buffer: 동적 감모 버퍼 상수
        pipeline_inbounds: {주차번호: 입고확정수량} 딕셔너리
        expected_inbounds: {주차번호: 입고예정수량} 딕셔너리
        weight_factor: 실무자 수동 가중치 계수 (기본 1.0)
        weeks: 시뮬레이션 기간 (기본 24주)
    Returns:
        주차별 예상 기말재고 배열
    """
    weekly_demand = smoothing_constant * weight_factor + loss_buffer
    result = []
    prev_stock = current_stock

    for w in range(1, weeks + 1):
        inbound_pipeline = pipeline_inbounds.get(w, 0)
        inbound_expected = expected_inbounds.get(w, 0)

        ending_stock = prev_stock + inbound_pipeline + inbound_expected - weekly_demand

        result.append({
            "week": w,
            "beginning_stock": prev_stock,
            "inbound_pipeline": inbound_pipeline,
            "inbound_expected": inbound_expected,
            "weekly_demand": round(weekly_demand, 1),
            "ending_stock": round(ending_stock, 1),
        })

        prev_stock = ending_stock

    return result


def calc_order_suggestion(
    shortage_qty: float,
    hub_moq: int,
) -> int:
    """
    5.3. 최종 제안 발주 수량 규격화
    - 부족분을 hub_moq로 나누어 올림 처리 후 다시 곱함

    Args:
        shortage_qty: 부족 수량 (양수)
        hub_moq: 상품 마스터의 최소 발주 단위
    Returns:
        규격화된 제안 발주 수량
    """
    if shortage_qty <= 0 or hub_moq <= 0:
        return 0
    return math.ceil(shortage_qty / hub_moq) * hub_moq


def check_air_shipment_trigger(
    simulation_result: List[Dict],
    safety_stock: float,
) -> Optional[Dict]:
    """
    5.4. 비상 에어(Air) 수송 트리거 감지
    - 12주 뒤(W+12) 시점에 재고 공백(마이너스) 발생 여부 확인

    Args:
        simulation_result: simulate_future_inventory() 결과 배열
        safety_stock: 안전재고 기준 수량
    Returns:
        트리거 발동 시 경고 정보 딕셔너리, 미발동 시 None
    """
    if len(simulation_result) < 12:
        return None

    week_12 = simulation_result[11]  # 0-indexed, 12번째 주차

    if week_12["ending_stock"] < 0:
        return {
            "trigger": True,
            "week": 12,
            "shortage_qty": abs(week_12["ending_stock"]),
            "message": (
                f"비상 에어 수송 전환 제안: 12주 뒤 예상 재고 부족량 "
                f"{abs(week_12['ending_stock']):.0f}개. "
                f"항공편 전환 시 2주 만에 긴급 입고 가능."
            ),
        }

    return None


def calc_remaining_expiry_days(expiry_date_str: str, today: Optional[date] = None) -> int:
    """
    6.1. 잔여 유통기한 일수 연산
    - 잔여 유통기한 = 최종 유통기한 - 현재 시스템 날짜

    Args:
        expiry_date_str: 유통기한 문자열 (YYYY-MM-DD)
        today: 기준 날짜 (기본값: 오늘)
    Returns:
        잔여 일수
    """
    if today is None:
        today = date.today()

    expiry = date.fromisoformat(expiry_date_str)
    return (expiry - today).days


def calc_inventory_value(can_qty: int, fixed_unit_price: float, exchange_rate: float) -> int:
    """
    6.2. 재고 자산 원화 가치 산출
    - 캔수 * 고정 외화 단가 * 적용 환율

    Args:
        can_qty: 캔 수량
        fixed_unit_price: 연간 고정 외화 매입 단가
        exchange_rate: 결제 적용 환율
    Returns:
        원화 기준 자산 금액 (정수 반올림)
    """
    return round(can_qty * fixed_unit_price * exchange_rate)
