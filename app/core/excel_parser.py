"""
엑셀 양식 생성 및 파싱 모듈
- 기능별 개별 다운로드 + 전체 일괄 다운로드
- 고정 양식 헤더 + 입력 가이드 예시 행
- 현재고 엑셀 파싱
"""

import os
import pandas as pd
from io import BytesIO
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


# ── 공통 스타일 ──────────────────────────────────────────────────
HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
HEADER_FILL = PatternFill(start_color="29AD39", end_color="29AD39", fill_type="solid")
EXAMPLE_FONT = Font(italic=True, color="999999", size=10)
EXAMPLE_FILL = PatternFill(start_color="F5F5F5", end_color="F5F5F5", fill_type="solid")
THIN_BORDER = Border(
    left=Side(style="thin", color="D4D4D4"),
    right=Side(style="thin", color="D4D4D4"),
    top=Side(style="thin", color="D4D4D4"),
    bottom=Side(style="thin", color="D4D4D4"),
)


def _apply_sheet_style(ws, columns, example_row=None):
    """시트 헤더 스타일링 및 컬럼 너비 자동 조정"""
    for col_idx, col_name in enumerate(columns, 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = THIN_BORDER
        # 컬럼 너비 자동 조정 (한글 고려)
        width = max(len(col_name) * 2.2, 14)
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    if example_row:
        for col_idx, val in enumerate(example_row, 1):
            cell = ws.cell(row=2, column=col_idx)
            cell.value = val
            cell.font = EXAMPLE_FONT
            cell.fill = EXAMPLE_FILL
            cell.alignment = Alignment(horizontal="center")
            cell.border = THIN_BORDER

    ws.freeze_panes = "A2"


# ── 양식 정의 ──────────────────────────────────────────────────
TEMPLATE_DEFS = {
    "product_master": {
        "sheet_name": "상품마스터",
        "columns": ["품목코드", "품목명", "카툰당입수량", "연간고정단가(외화)", "허브MOQ(캔)"],
        "example": ["SN-001", "슈누프로1단계 800g", 12, 8.50, 3600],
        "filename": "상품마스터_양식.xlsx",
    },
    "ffc_master": {
        "sheet_name": "창고마스터",
        "columns": ["창고코드", "창고명", "창고타입(ONLINE/OFFLINE/BUYOUT)", "허용유통기한일수", "기본이관MOQ(캔)"],
        "example": ["HUB", "용인 메인창고", "OFFLINE", 180, 0],
        "filename": "창고마스터_양식.xlsx",
    },
    "logistics_cost": {
        "sheet_name": "물류비마스터",
        "columns": ["출발창고코드", "도착창고코드", "카툰당물류비(원)"],
        "example": ["HUB", "FFC_COUPANG", 3500],
        "filename": "물류비마스터_양식.xlsx",
    },
    "production": {
        "sheet_name": "생산완료",
        "columns": ["생산년월코드", "발주코드", "품목코드", "생산완료수량(캔)", "제조년월(YYYY-MM)", "유통기한(YYYY-MM-DD)"],
        "example": ["2026-05", "ORD-2026-001", "SN-001", 36000, "2026-05", "2028-05-15"],
        "filename": "생산완료_양식.xlsx",
    },
    "invoice": {
        "sheet_name": "매입인보이스",
        "columns": [
            "인보이스번호", "선하증권(BL)번호", "품목코드", "카툰수(TU)", "낱개수량(Can)",
            "선적일(YYYY-MM-DD)", "한국도착일(YYYY-MM-DD)", "결제기일(YYYY-MM-DD)", "결제환율"
        ],
        "example": ["INV-2026-001", "BL-2026-001", "SN-001", 300, 3600, "2026-03-01", "2026-04-15", "2026-05-15", 1350.5],
        "filename": "매입인보이스_양식.xlsx",
    },
    "expected_inbound": {
        "sheet_name": "입고예정",
        "columns": ["참조번호(BL등)", "품목코드", "입고예정수량(캔)", "국내도착예정일(YYYY-MM-DD)", "상태(IN_TRANSIT/CUSTOMS)"],
        "example": ["BL-2026-002", "SN-001", 7200, "2026-08-20", "IN_TRANSIT"],
        "filename": "입고예정_양식.xlsx",
    },
    "current_inventory": {
        "sheet_name": "현재고스냅샷",
        "columns": ["창고코드", "품목코드", "현재고수량(캔)", "유통기한(YYYY-MM-DD)"],
        "example": ["HUB", "SN-001", 12000, "2028-05-15"],
        "filename": "현재고스냅샷_양식.xlsx",
    },
}

# 지원 타입 이름과 한글 표시명
TEMPLATE_LABELS = {
    "product_master": "상품마스터",
    "ffc_master": "창고마스터",
    "logistics_cost": "물류비마스터",
    "production": "생산완료",
    "invoice": "매입인보이스",
    "expected_inbound": "입고예정",
    "current_inventory": "현재고스냅샷",
}


def generate_template(template_type: str = "all") -> BytesIO:
    """
    고정 엑셀 양식 템플릿 생성

    Args:
        template_type: 'all' 또는 TEMPLATE_DEFS 키 중 하나
    Returns:
        BytesIO 스트림
    """
    output = BytesIO()

    if template_type == "all":
        types_to_generate = list(TEMPLATE_DEFS.keys())
    elif template_type in TEMPLATE_DEFS:
        types_to_generate = [template_type]
    else:
        raise ValueError(f"지원하지 않는 템플릿 유형: {template_type}")

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for t_type in types_to_generate:
            tdef = TEMPLATE_DEFS[t_type]
            pd.DataFrame(columns=tdef["columns"]).to_excel(
                writer, sheet_name=tdef["sheet_name"], index=False
            )
            ws = writer.sheets[tdef["sheet_name"]]
            _apply_sheet_style(ws, tdef["columns"], tdef.get("example"))

    output.seek(0)
    return output


def get_template_filename(template_type: str) -> str:
    """템플릿 타입에 해당하는 파일명 반환"""
    if template_type == "all":
        return "SCM_데이터입력양식_전체.xlsx"
    tdef = TEMPLATE_DEFS.get(template_type)
    if tdef:
        return tdef["filename"]
    return "SCM_양식.xlsx"


def parse_excel_file(file_path: str) -> dict:
    """
    업로드된 엑셀 파일을 읽어 각 시트별 DataFrame을 dict로 반환
    """
    try:
        dfs = pd.read_excel(file_path, sheet_name=None, engine="openpyxl")
        return dfs
    except Exception as e:
        print(f"Excel parsing error: {e}")
        raise ValueError("엑셀 파일을 파싱하는 데 실패했습니다. 양식을 확인해주세요.")


def validate_dataframe(df: pd.DataFrame, expected_columns: list) -> bool:
    """DataFrame 컬럼 검증"""
    if df.empty:
        return False
    return all(col in df.columns for col in expected_columns)


def parse_inventory_excel(file_path: str) -> list:
    """
    현재고 엑셀 파싱 전용 로직
    '현재고스냅샷' 시트에서 데이터를 추출합니다.

    Returns:
        list of dict: [{'ffc_code': ..., 'product_code': ..., 'qty': ..., 'expiry': ...}, ...]
    """
    try:
        dfs = pd.read_excel(file_path, sheet_name=None, engine="openpyxl")
    except Exception as e:
        raise ValueError(f"엑셀 파일 파싱 실패: {e}")

    sheet_name = "현재고스냅샷"
    if sheet_name not in dfs:
        raise ValueError(f"'{sheet_name}' 시트를 찾을 수 없습니다. 양식을 확인해주세요.")

    df = dfs[sheet_name]
    expected = TEMPLATE_DEFS["current_inventory"]["columns"]

    # 헤더에서 예시 행(italic) 제거 - 첫 번째 데이터 행이 예시 행일 수 있음
    if len(df) > 0:
        first_row = df.iloc[0]
        example = TEMPLATE_DEFS["current_inventory"]["example"]
        if all(str(first_row.iloc[i]) == str(example[i]) for i in range(min(len(first_row), len(example)))):
            df = df.iloc[1:].reset_index(drop=True)

    if df.empty:
        return []

    results = []
    for _, row in df.iterrows():
        try:
            item = {
                "ffc_code": str(row.iloc[0]).strip(),
                "product_code": str(row.iloc[1]).strip(),
                "qty": int(row.iloc[2]),
                "expiry_date": str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else None,
            }
            results.append(item)
        except (ValueError, IndexError):
            continue

    return results


def generate_order_plan_export(plan_data: list) -> BytesIO:
    """
    발주 계획 엑셀 내보내기

    Args:
        plan_data: list of dict with keys: target_month, product_code, product_name,
                   system_suggested_qty, user_modified_qty
    Returns:
        BytesIO 스트림
    """
    output = BytesIO()
    columns = ["대상연월", "품목코드", "품목명", "시스템제안수량", "실무자확정수량", "차이"]

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        if plan_data:
            df = pd.DataFrame(plan_data)
            df["차이"] = df["user_modified_qty"] - df["system_suggested_qty"]
            df.columns = columns
        else:
            df = pd.DataFrame(columns=columns)

        df.to_excel(writer, sheet_name="발주계획", index=False)
        ws = writer.sheets["발주계획"]
        _apply_sheet_style(ws, columns)

    output.seek(0)
    return output
