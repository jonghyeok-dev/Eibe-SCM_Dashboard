import os
import pandas as pd
from io import BytesIO

def generate_template() -> BytesIO:
    """고정 엑셀 양식 템플릿 생성"""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # 1. 상품마스터
        pd.DataFrame(columns=[
            '품목코드', '품목명', '카툰당입수량', '연간고정단가', '허브MOQ'
        ]).to_excel(writer, sheet_name='상품마스터', index=False)
        
        # 2. 거점마스터
        pd.DataFrame(columns=[
            '거점코드', '거점명', '거점타입(ONLINE/OFFLINE/BUYOUT)', '허용유통기한일수', '거점MOQ'
        ]).to_excel(writer, sheet_name='거점마스터', index=False)
        
        # 3. 물류비마스터
        pd.DataFrame(columns=[
            '출발거점코드', '도착거점코드', '카툰당물류비'
        ]).to_excel(writer, sheet_name='물류비마스터', index=False)
        
        # 4. 생산완료 (Overview)
        pd.DataFrame(columns=[
            '생산년월코드', '발주코드', '품목코드', '생산완료수량', '제조년월(YYYY-MM)', '유통기한(YYYY-MM-DD)'
        ]).to_excel(writer, sheet_name='생산완료', index=False)
        
        # 5. 매입인보이스 (Invoice)
        pd.DataFrame(columns=[
            '인보이스번호', '선하증권(BL)번호', '품목코드', '카툰수(TU)', '낱개수량(Can)', 
            '선적일(YYYY-MM-DD)', '한국도착일', '결제기일', '결제환율'
        ]).to_excel(writer, sheet_name='매입인보이스', index=False)
        
        # 6. 입고예정
        pd.DataFrame(columns=[
            '참조번호(BL등)', '품목코드', '입고예정수량', '국내도착예정일(YYYY-MM-DD)', '상태(IN_TRANSIT/CUSTOMS)'
        ]).to_excel(writer, sheet_name='입고예정', index=False)
        
        # 7. 현재고스냅샷
        pd.DataFrame(columns=[
            '거점코드', '입고인보이스번호', '현재고수량(캔)'
        ]).to_excel(writer, sheet_name='현재고스냅샷', index=False)

    output.seek(0)
    return output

def parse_excel_file(file_path: str) -> dict:
    """
    업로드된 엑셀 파일을 읽어 각 시트별 DataFrame을 dict로 반환
    """
    try:
        # 모든 시트를 읽어옴 (None 전달 시 dictionary 반환)
        dfs = pd.read_excel(file_path, sheet_name=None, engine='openpyxl')
        return dfs
    except Exception as e:
        print(f"Excel parsing error: {e}")
        raise ValueError("엑셀 파일을 파싱하는 데 실패했습니다. 양식을 확인해주세요.")

def validate_dataframe(df: pd.DataFrame, expected_columns: list) -> bool:
    """DataFrame 컬럼 검증"""
    if df.empty:
        return False
    # 예상 컬럼들이 모두 존재하는지 확인
    return all(col in df.columns for col in expected_columns)
