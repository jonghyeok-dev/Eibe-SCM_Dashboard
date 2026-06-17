# System Specification: Standalone Local SCM ERP System

> **Document Version:** 2026.06.15-Final
> **Target Environment:** Windows 11 Standalone Local PC (Host IP: `추후 확정 예정')
> **Core Tech Stack:** Python 3.11 · FastAPI · Uvicorn · SQLite 3 · Pandas · NumPy · Tailwind CSS · Chart.js

---

## 목차

- [CH 1. 시스템 아키텍처 및 구동 제약 조건](#ch-1-시스템-아키텍처-및-구동-제약-조건-architectural-constraints)
- [CH 2. 표준 폴더 구조 명세](#ch-2-표준-폴더-구조-명세-directory-tree-declaration)
- [CH 3. 관계형 데이터베이스 3차 정규화(3NF) 스키마 명세](#ch-3-관계형-데이터베이스-3차-정규화3nf-스키마-명세)
- [CH 4. 데이터 수집 및 멱등성 보장](#ch-4-데이터-수집-및-멱등성-보장-data-ingestion-pipeline)
- [CH 5. SCM 코어 연산 및 수요 평탄화 엔진](#ch-5-scm-코어-연산-및-수요-평탄화-엔진-calculation-core-logic)
- [CH 6. 멀티 채널 FEFO 및 재고 자산 금액 시뮬레이터](#ch-6-멀티-채널-fefo-및-재고-자산-금액-시뮬레이터-fulfillment-logic)
- [CH 7. 프론트엔드 대시보드 화면 및 인터페이스 명세](#ch-7-프론트엔드-대시보드-화면-및-인터페이스-명세-uiux)

---

## CH 1. 시스템 아키텍처 및 구동 제약 조건 (Architectural Constraints)

### 1.1. 하드웨어 및 인프라 구동 가이드

1. 본 시스템은 클라우드 서버(AWS, Azure, Supabase Cloud 등) 인프라 비용 및 데이터 유출을 원천 차단하기 위해 사내 호스트 PC(`192.168.10.200`)의 로컬 자원(8GB RAM 환경)만을 단독 사용하는 **'독립형 로컬 웹 어플리케이션'**으로 구동한다.
2. 데이터베이스는 파일 기반의 경량 데이터베이스인 **SQLite 3**를 사용하며, 물리 파일명은 `data/local_erp.db`로 고정한다. 별도의 DB 엔진 데몬 프로세스를 요구하지 않도록 설계한다.
3. 백엔드는 Python 3.11 환경의 **FastAPI** 프레임워크를 기반으로 하며, 비동기 ASGI 서버인 **Uvicorn**을 통해 로컬 포트로 서빙한다.
4. 모든 프론트엔드 UI 리소스는 로컬 백엔드가 정적 파일(Static Files) 라우팅을 통해 서빙하며, 웹 브라우저를 통해 사내망 내부의 타 클라이언트 PC들이 접근할 수 있도록 포트를 개방한다.

### 1.2. 에이전트 개발 절대 금지 조항 (Strict Red Lines)

1. **머신러닝 알고리즘 및 라이브러리 도입 전면 금지**
   Scikit-learn, XGBoost, LightGBM, TensorFlow, PyTorch 등 머신러닝/딥러닝 패키지를 프로젝트 내부 코드에 포함하거나 종속성(`requirements.txt`)에 추가하는 행위를 절대 금지한다. 소량 데이터(2년 치 주차 레코드) 환경에서의 과적합(Overfitting)을 방지하기 위해 모든 수요 예측은 사칙연산 기반의 통계적 평탄화 모델로 제한한다.
2. **변동 단가 추적 로직 배제**
   모든 제품의 외화 매입 단가는 연간 고정 계약 구조를 따르므로, 인보이스 회차별 변동 단가 추적 로직을 설계하지 않는다. 단가는 전적으로 상품 마스터 테이블의 고정 필드를 기준으로 연산한다.
3. **클라우드 종속적 인증/인가 시스템 배제 및 자체 권한 제어**
   외부 인증(OAuth 등)은 배제하되, 내부 SQLite DB의 `USER_ACCOUNT` 테이블을 활용하여 `ADMIN`, `OPERATOR` 역할 기반의 독립 계정 체계를 구축한다. 비밀번호는 Bcrypt 등으로 해싱하여 최소한의 로컬 보안을 적용한다.

### 1.3. 윈도우 11 백그라운드 무인 구동 자동화 프로세스

1. 실무자가 출근 후 터미널이나 아이콘을 통해 프로그램을 수동 구동하는 번거로움을 제거하기 위해 윈도우 11 커널의 **'작업 스케줄러(Task Scheduler)'** 메커니즘에 100% 호환되도록 구성한다.
2. 프로젝트 루트 디렉토리에 백엔드 구동용 윈도우 배치 파일(`start_server.bat`)을 생성한다. 해당 파일은 로컬 가상환경 가동 후 Uvicorn 구동 명령을 순차 실행해야 한다.

   ```bat
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

3. 윈도우 작업 스케줄러 등록 트리거는 **'시스템 시작 시(At startup)'**로 세팅하며, '사용자의 로그온 여부에 관계없이 실행' 및 '가장 높은 수준의 권한으로 실행' 속성을 반드시 통과할 수 있도록 백그라운드 서비스 상주 구조로 안정성을 확보한다.

---

## CH 2. 표준 폴더 구조 명세 (Directory Tree Declaration)

에이전트는 소스코드 및 정적 자산 생성 시 아래 선언된 디렉토리 트리를 엄격히 준수해야 하며, 임의의 상위 폴더나 중복 디렉토리를 생성할 수 없다.

```text
local_erp/
├── .cursorrules               # 에이전트 구동 제약 파일
├── system_spec.md             # 본 마스터 명세서
├── start_server.bat           # 윈도우 무인 부팅 배치 파일
├── requirements.txt           # 파이썬 최소 의존성 패키지 명세
├── app/                       # 백엔드 애플리케이션 코어
│   ├── __init__.py
│   ├── main.py                # FastAPI 엔드포인트 및 라우팅 제어
│   ├── database.py            # SQLite 연결 및 SQLAlchemy ORM 설정
│   ├── models.py              # 3NF 관계형 테이블 스키마 정의
│   ├── schemas.py             # Pydantic 데이터 검증 명세
│   └── core/
│       ├── __init__.py
│       └── forecasting.py     # 단순 출고량 평탄화 및 감모 버퍼 연산 엔진
├── data/                      # 로컬 데이터 및 DB 적재 자산
│   ├── local_erp.db           # SQLite 단일 파일 데이터베이스
│   └── backups/               # 실무자 업로드 원본 엑셀 강제 격리 폴더
└── web/                       # 정적 웹 프론트엔드 자산
    ├── static/
    │   ├── css/               # Tailwind CSS 아티팩트
    │   └── js/                # API 호출 및 Chart.js 차트 렌더링 스크립트
    ├── index.html             # 메인 통합 대시보드 화면
    └── order_plan.html        # 월 1회 발주 제안 편집 및 수정 저장 화면
```

---

## CH 3. 관계형 데이터베이스 3차 정규화(3NF) 스키마 명세

모든 테이블은 중복 데이터를 원천 차단하고 데이터 이행적 종속 관계를 격리하기 위해 **3차 정규화(3NF)** 규칙에 의거하여 설계한다. 모든 테이블의 대리 기본키는 1씩 자동 증가하는 정수형 고유 식별자(`INTEGER PRIMARY KEY AUTOINCREMENT`) 구조를 취하여 추후 데이터 자산화 시 데이터 무결성을 보장한다.

### 3.0. 시스템 관리 영역 (System Admin Tables)

#### 3.0.1. 사용자 계정 테이블 (`USER_ACCOUNT`)
**설명:** 시스템 접근 인가 및 권한 제어를 위한 로컬 계정 정보.

```sql
CREATE TABLE USER_ACCOUNT (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('ADMIN', 'OPERATOR')),
    name TEXT NOT NULL
);
```

#### 3.0.2. 시스템 스냅샷 테이블 (`SYSTEM_SNAPSHOT`)
**설명:** 3시간 단위 자동 데이터 백업 및 Admin의 수동 백업을 추적하기 위한 테이블.

```sql
CREATE TABLE SYSTEM_SNAPSHOT (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_path TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    is_auto BOOLEAN DEFAULT 1
);
```

### 3.1. 기준 정보 영역 (Master Data Tables)

#### 3.1.1. 상품 마스터 테이블 (`PRODUCT_MASTER`)

**설명:** 취급하는 모든 분유 제품의 고유 식별 및 연간 고정 단가 정보 기준점.

```sql
CREATE TABLE PRODUCT_MASTER (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_code TEXT UNIQUE NOT NULL,       -- 실제 현업 품목 코드 (예: SN-001)
    product_name TEXT NOT NULL,              -- 브랜드 및 단계 포함 명칭
    pack_qty_per_tu INTEGER NOT NULL,        -- 카툰(Box)당 입수량 (낱개 캔 수)
    fixed_unit_price REAL NOT NULL,          -- 연간 고정 외화 매입 단가 (1년 1회 변경)
    hub_moq INTEGER NOT NULL                 -- 메인 허브 해외 발주 최소 수량 (단위: 캔)
);
```

#### 3.1.2. 풀필먼트 마스터 테이블 (`FFC_MASTER`)

**설명:** 온/오프라인 물류 거점, 사입 채널별 가용 유통기한 및 제약 조건 제어판.

```sql
CREATE TABLE FFC_MASTER (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ffc_code TEXT UNIQUE NOT NULL,           -- 거점 코드 (예: HUB, FFC_ON, FFC_COUPANG)
    ffc_name TEXT NOT NULL,                  -- 거점 채널명
    ffc_type TEXT NOT NULL CHECK (ffc_type IN ('ONLINE', 'OFFLINE', 'BUYOUT')),
    allowed_expiry_days INTEGER DEFAULT 90,  -- 채널별 허용 잔여 유통기한 임계일수
    ffc_moq INTEGER DEFAULT 0                -- 메인 허브에서 해당 거점 이관 시 최소 수량
);
```

#### 3.1.3. 구간별 물류비 마스터 테이블 (`LOGISTICS_COST_MASTER`)

**설명:** 출발 거점과 도착 거점 간의 카툰(TU)당 물리적 물류 이동 단가 매트릭스.

```sql
CREATE TABLE LOGISTICS_COST_MASTER (
    departure_ffc_id INTEGER NOT NULL,
    arrival_ffc_id INTEGER NOT NULL,
    cost_per_tu INTEGER NOT NULL,            -- 카툰(TU)당 이관 물류 비용 단가
    PRIMARY KEY (departure_ffc_id, arrival_ffc_id),
    FOREIGN KEY (departure_ffc_id) REFERENCES FFC_MASTER (id),
    FOREIGN KEY (arrival_ffc_id) REFERENCES FFC_MASTER (id)
);
```

### 3.2. 입고 및 파이프라인 영역 (Inbound Pipeline Tables)

#### 3.2.1. 입고 리스트 테이블 (`INBOUND_LIST`)

**설명:** 실무자 요구사항을 취합하여 정규화한 코어 공급망 파이프라인 이력 테이블. 인보이스 공통 속성 및 상품 개별 라인을 통합 적재하는 무결성 베이스.

```sql
CREATE TABLE INBOUND_LIST (
    inbound_id INTEGER PRIMARY KEY AUTOINCREMENT,
    production_ym_code TEXT NOT NULL,        -- 공급사 제공 생산년월 코드
    order_code TEXT NOT NULL,                -- 발주 코드값
    invoice_no TEXT NOT NULL,                -- 매입 인보이스 번호 (수동 매칭 바인딩 키)
    bl_no TEXT NOT NULL,                     -- 선하증권 번호
    product_id INTEGER NOT NULL,             -- 상품 마스터 테이블 참조 FK
    tu_qty INTEGER NOT NULL,                 -- 카툰 수 (TU 단위 수량)
    actual_can_qty INTEGER NOT NULL,         -- 실제 캔 수 (낱개 단위 수량)
    manufactured_date TEXT NOT NULL,         -- 제조년월 (YYYY-MM)
    expiry_date TEXT NOT NULL,               -- 제품 인쇄 최종 유통기한 (YYYY-MM-DD)
    shipping_date TEXT,                      -- 선적일 (YYYY-MM-DD)
    arrival_date TEXT,                       -- 한국 도착일 (YYYY-MM-DD)
    actual_inbound_date TEXT,                -- 실제 창고 완료일 (스탠바이 일자)
    payment_due_date TEXT,                   -- 결제 기일 (YYYY-MM-DD)
    exchange_rate REAL NOT NULL,             -- 결제 당시 적용 환율
    total_inventory_value INTEGER,           -- 연산 적재: 캔수 * 마스터고정단가 * 환율
    FOREIGN KEY (product_id) REFERENCES PRODUCT_MASTER (id)
);
```

#### 3.2.2. 입고 예정 리스트 테이블 (`EXPECTED_INBOUND`)

**설명:** 해상 운송 중이거나 통관 대기 중인 '근미래 가용 확정 재고' 모듈.

```sql
CREATE TABLE EXPECTED_INBOUND (
    expected_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,             -- 상품 마스터 테이블 참조 FK
    inbound_ref_no TEXT NOT NULL,            -- B/L No 또는 공급사 출하 번호
    expected_qty INTEGER NOT NULL,           -- 입고 예정 수량 (캔 단위)
    eta_date TEXT NOT NULL,                  -- 국내 메인 허브 입고 예정일 (YYYY-MM-DD)
    status TEXT NOT NULL CHECK (status IN ('IN_TRANSIT', 'CUSTOMS')),
    FOREIGN KEY (product_id) REFERENCES PRODUCT_MASTER (id)
);
```

### 3.3. 현장 실적 및 계획 데이터 영역 (Execution & Simulation Tables)

#### 3.3.1. 현재고 테이블 (`CURRENT_INVENTORY`)

**설명:** 각 거점 창고에 보관 중인 실시간 실재고 상황. `INBOUND_LIST`와 외래키로 결합하여 매입 환율 및 배치의 유통기한 정보를 실시간 역추적한다.

```sql
CREATE TABLE CURRENT_INVENTORY (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ffc_id INTEGER NOT NULL,                 -- 보관 거점 ID 참조 FK
    inbound_id INTEGER NOT NULL,             -- 최초 매입 연계용 입고 리스트 ID 참조 FK
    current_can_qty INTEGER NOT NULL DEFAULT 0, -- 현재 보관 실재고 수량 (캔 단위)
    last_updated TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ffc_id) REFERENCES FFC_MASTER (id),
    FOREIGN KEY (inbound_id) REFERENCES INBOUND_LIST (inbound_id)
);
```

#### 3.3.2. 출고 이력 테이블 (`OUTFLOW_HISTORY`)

**설명:** 매월/매주 업로드되는 재고 파일 스냅샷을 기반으로 사후 연산된 실질 재고 소멸 로그.

```sql
CREATE TABLE OUTFLOW_HISTORY (
    outflow_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ffc_id INTEGER NOT NULL,                 -- 출고 발생 거점 ID 참조 FK
    product_id INTEGER NOT NULL,             -- 상품 마스터 테이블 참조 FK
    base_date TEXT NOT NULL,                 -- 주차 기준일 또는 기록 일자 (YYYY-MM-DD)
    beginning_inventory INTEGER NOT NULL,    -- 당기 기초 재고량
    ending_inventory INTEGER NOT NULL,       -- 당기 기말 재고량
    simple_outflow_qty INTEGER NOT NULL,     -- 연산 적재: 기초 재고 - 기말 재고
    outflow_type TEXT DEFAULT 'SALES' CHECK (outflow_type IN ('SALES', 'LOSS', 'TRANSFER')),
    FOREIGN KEY (ffc_id) REFERENCES FFC_MASTER (id),
    FOREIGN KEY (product_id) REFERENCES PRODUCT_MASTER (id)
);
```

#### 3.3.3. 이관 계획 및 실행 테이블 (`TRANSFER_PLAN`)

**설명:** 거점 간 재고 밸런싱 이동 및 물류비 예측 시뮬레이션용 바인딩 테이블.

```sql
CREATE TABLE TRANSFER_PLAN (
    transfer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,             -- 상품 마스터 테이블 참조 FK
    departure_ffc_id INTEGER NOT NULL,       -- 출발 거점 ID 참조 FK
    arrival_ffc_id INTEGER NOT NULL,         -- 도착 거점 ID 참조 FK
    target_tu_qty INTEGER NOT NULL,          -- 이관 대상 카툰 수
    target_can_qty INTEGER NOT NULL,         -- 이관 대상 실제 캔 수
    estimated_logistics_cost INTEGER,        -- 연산 적재: 카툰수 * 구간별 물류단가
    transfer_status TEXT DEFAULT 'PLANNED' CHECK (transfer_status IN ('PLANNED', 'IN_TRANSIT', 'DONE')),
    FOREIGN KEY (product_id) REFERENCES PRODUCT_MASTER (id),
    FOREIGN KEY (departure_ffc_id) REFERENCES FFC_MASTER (id),
    FOREIGN KEY (arrival_ffc_id) REFERENCES FFC_MASTER (id)
);
```

#### 3.3.4. 파이프라인 수동 매칭 학습 로그 테이블 (`MATCHING_HISTORY_LOG`)

**설명:** 공통 식별자가 없는 엑셀 파일들을 실무자가 화면을 통해 수동 매칭한 행위를 정형화하여 미래 무인화 데이터셋으로 축적하는 핵심 로깅 테이블.

```sql
CREATE TABLE MATCHING_HISTORY_LOG (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    production_ym_code TEXT NOT NULL,        -- 공급사 생산완료 엑셀의 생산년월 코드
    matched_invoice_no TEXT NOT NULL,        -- 실무자가 짝지어준 매입 인보이스 번호
    product_id INTEGER NOT NULL,             -- 상품 마스터 테이블 참조 FK
    production_qty INTEGER NOT NULL,         -- 생산 완료 파일에 기록된 수량
    invoice_qty INTEGER NOT NULL,            -- 인보이스 파일에 기록된 수량
    discrepancy_rate REAL,                   -- 연산 적재: 수량 불일치 백분율
    date_gap_days INTEGER,                   -- 연산 적재: 생산월과 송장일의 격차 일수
    matched_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES PRODUCT_MASTER (id)
);
```

#### 3.3.5. 월별 발주 계획 및 저장 테이블 (`MONTHLY_ORDER_PLAN`)

**설명:** 시스템 연산 제안 수량을 실무자가 언제든 화면에서 오버라이드하여 영구 적재하는 CRUD 바인딩 테이블.

```sql
CREATE TABLE MONTHLY_ORDER_PLAN (
    plan_id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_month TEXT NOT NULL,              -- 발주 대상 연월 (YYYY-MM)
    product_id INTEGER NOT NULL,             -- 상품 마스터 테이블 참조 FK
    system_suggested_qty INTEGER NOT NULL,   -- 최초 시스템 6개월 뒤 공백 역산 제안 수량
    user_modified_qty INTEGER NOT NULL,      -- 실무자가 직접 수정하여 덮어쓴 최종 저장 수량
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES PRODUCT_MASTER (id)
);
```

---

## CH 4. 데이터 수집 및 멱등성 보장 (Data Ingestion Pipeline)

### 4.1. 고정 엑셀 양식 기반 업로드 파싱 및 무결성 제어 규칙

1. 모든 정형 데이터는 시스템이 제공하는 다운로드 가능한 **고정 엑셀 템플릿**을 통해서만 업로드되어야 한다.
2. 백엔드 FastAPI 엔진은 업로드 스트림 수신 즉시 파일 바이트를 검증하고, 파이썬 Pandas 라이브러리를 가동하여 양식(마스터, 생산, 인보이스, 현재고 등)별 템플릿 구조 일치 여부를 파싱한다.
3. **이력 추적성(Auditing) 원칙:** 정상 파싱이 확인되는 즉시, 파일 유실 방지를 위해 원본 파일명을 `[YYYYMMDD_HHMMSS]_[실무자ID]_[템플릿유형].xlsx` 규격으로 강제 치환하여 `data/backups/` 내 지정된 도메인 폴더로 복사 이동한다.
4. **수동 새로고침 및 스냅샷 보장:** 데이터가 업데이트 될 때마다 실시간 감지하여 화면을 바꾸는 대신, 대시보드의 화면 갱신은 실무자가 직접 **[새로고침]** 버튼을 누를 때만 동작한다. 화면 상단에는 데이터를 마지막으로 읽어온 **업데이트 일시**를 명시한다. 시스템은 백그라운드에서 3시간마다 전체 DB 스냅샷을 생성하여 서버 다운 시에도 안전하게 복구할 수 있도록 보장한다.

### 4.2. 파이프라인 매칭 시스템 로직 (고정 양식 연계)

과거의 비정형 수동 매칭 방식 대신, 정형화된 양식을 통해 발주, 생산, 인보이스, 입고 데이터를 논리적으로 매칭한다.
1. 사용자는 "파이프라인 매칭 시스템" 메뉴에서 발주~입고까지의 단계를 모니터링한다.
2. 누락된 인보이스나 수량 불일치 내역은 시스템이 자동 필터링하여 사용자에게 알림을 제공하고, 수정 가능한 그리드를 통해 확정 처리한다.

---

## CH 5. SCM 코어 연산 및 수요 평탄화 엔진 (Calculation Core Logic)

모든 수학적 시뮬레이션 로직은 파이썬 백엔드 소스코드(`app/core/forecasting.py`) 내에 선형 연산식으로 구현되어야 하며, 데이터베이스 데이터프레임 구조와 긴밀히 락인되어야 한다.

### 5.1. 물류창고 변동 기반 단순 출고량 및 평탄화 수식

영업 부서의 일시적인 프로모션이나 매출 목표 의욕치에 의해 수동 발주량이 왜곡되는 **채찍효과(Bullwhip Effect)**를 원천 봉쇄하기 위해, 순수하게 창고에서 소멸한 실재고 소진량만을 예측 기저값으로 취급한다.

특정 거점의 주차별 단순 출고량 산출 공식은 다음과 같다:

```text
주차별 단순 출고량 = 해당 주차의 기초 실재고 수량 - 해당 주차의 기말 실재고 수량
```

- 이 값은 반품, 반출, 교환 등 모든 물류적 자산 유출 허수가 포함된 현실적인 현장 실적 데이터이다.
- 백엔드 엔진은 매 업데이트 주기마다 `OUTFLOW_HISTORY`에 적재된 주차별 단순 출고량 데이터를 호출하여 **직전 3개월(12주)** 동안의 단순 출고량 총합을 계산한 뒤, 이를 **12로 나누어** '주차별 기준 출고량 평균치(Smoothing Constant)'를 도출한다.
- 도출된 주차별 기준 출고량 평균치는 향후 다가올 미래 **6개월(24주)**의 타임라인상 모든 주차별 수요 예측 칸에 변하지 않는 플랫(Flat) 상수로 사전 배치(고정)된다.

### 5.2. 동적 감모 버퍼(Dynamic Loss Buffer) 보정 로직

단순 세일즈 주문 데이터와 실제 창고 출고량 간의 격차(파손, 폐기, 이관 시 발생하는 누수 비용 및 손실량)를 시스템이 능동적으로 감지하여 안전재고 설계에 결합한다.

동적 감모 버퍼 산출 공식은 다음과 같다:

$$\text{Dynamic Loss Buffer} = \frac{1}{12} \sum_{w=1}^{12} (\text{Simple Outflow Qty}_w - \text{Pure Sales Qty}_w)$$

- 즉, 직전 12주간 발생한 실제 총 단순 출고량에서 세일즈 팀이 제공한 주문 완료 실적 수량을 차감한 순수 물류 손실 영역의 주차별 평균값이다.
- 백엔드 엔진은 미래 재고 소멸선을 연산할 때, 위에서 산출된 동적 감모 버퍼 상수를 주차별로 누적 가산하여 물류 현장의 미세한 소진 리스크를 소수점 단위까지 수치적으로 방어한다.

### 5.3. 미래 예상 기말재고 및 월별 발주 제안 역산 알고리즘

해외 공급사의 리드타임이 총 6개월(발주부터 생산 3개월, 생산부터 국내 도착 3개월 = 총 24주)이 걸리는 제약 조건을 주차별 Weekly Bucket 타임라인 제어계에 결합한다.

미래 특정 주차(W)의 예상 기말재고 산출 공식은 다음과 같다:

```text
예상 기말재고(W) = 이전 주차 기말재고(W-1)
                + 해당 주차 파이프라인 입고 확정량
                + 해당 주차 입고 예정 리스트 수량
                - (주차별 기준 출고량 평균치 * 실무자 수동 가중치 계수 + 동적 감모 버퍼)
```

- **실무자 수동 가중치 계수**는 프론트엔드 대시보드 화면상에서 슬라이더 바를 조절하여 인입되는 변수이며, 미조정 시 기본 연산값은 `1.0`(0% 증감)으로 세팅된다. 만약 실무자가 현장 판단으로 슬라이더를 플러스 10%로 당기면 계수는 `1.1`로 연산에 대입된다.
- 백엔드 엔진은 금주 시점부터 미래 1주 차부터 24주 차까지 위 공식을 누적 대입하여 시뮬레이션 배열을 생성한다.
- 해외 리드타임과 정확히 일치하는 **'6개월 뒤(24주 뒤)'**의 특정 미래 주차를 상시 모니터링하여, 해당 주차의 예상 기말재고 수량이 마스터 테이블에서 설정된 안전재고 타겟 기준(예: 1.5개월분에 근사하는 6주치 평탄화 출고량 총합) 미만으로 소진되는 위험 도래 시점을 역산한다.
- 공백 리스크가 포착되는 즉시 대시보드에 발주 경고 시그널을 출력하며, 이때 제안되는 **최종 제안 발주 수량**은 단순 부족분 수량이 아닌, 부족분을 상품 마스터 테이블의 최소 발주 단위인 `hub_moq`로 나누어 **소수점 첫째 자리에서 무조건 올림(`Math.ceil`)** 처리한 뒤 다시 `hub_moq`를 곱한 철저한 공급사 주문 규격 규격화 수량으로 화면에 바인딩한다.

### 5.4. 비상 에어(Air) 수송 트리거 다운스트림 로직

1. 현장의 일시적인 출고량 폭증이나 슬라이더 가중치 상향으로 인해, 6개월 뒤가 아닌 **3개월 뒤(미래 12주 뒤 시점)**에 메인 허브의 재고 공백(마이너스 쇼트)이 발생하는 예외 상황을 백엔드가 실시간 감지한다.
2. 12주 뒤 쇼트 발생이 확정되는 즉시, 시스템은 정상 해상 운송 파이프라인을 중단하고 공급사 공장에 이미 생산 완료 상태로 대기 중인 `EXPECTED_INBOUND` 테이블의 특정 배치 물량을 에어로 전환하는 비상 모듈을 가동한다.
3. 프론트엔드 대시보드 정중앙에 다음 형태의 의사결정 위젯 팝업을 강제 렌더링하도록 API 응답을 제어한다:

   > **비상 에어 수송 전환 제안:** 공급사 대기 물량 중 **X개**를 항공편으로 전환 시 2주 만에 긴급 입고되어 W+12주 차의 품절 공백을 방어할 수 있습니다. 단, 긴급 항공 물류비 **Y원**이 추가 발생하며, 단기 캐시플로우 압박이 14일 앞당겨집니다.

---

## CH 6. 멀티 채널 FEFO 및 재고 자산 금액 시뮬레이터 (Fulfillment Logic)

### 6.1. 유통기한 기반 선한출고(FEFO) 거점 가용성 필터링 알고리즘

분유 제품의 유효기간 제약을 방어하기 위해 단순 선입선출을 차단하고, **유통기한 기준 출고(FEFO)** 제어 로직을 구현한다.

각 생산 배치별 실질 잔여 유통기한 일수 연산 공식은 다음과 같다:

```text
잔여 유통기한 일수 = 해당 배치의 최종 유통기한 날짜 - 현재 시스템 날짜
```

- 현재고 테이블(`CURRENT_INVENTORY`) 내에 물량이 존재하더라도, 해당 재고가 보관된 풀필먼트 거점의 마스터 설정값인 `allowed_expiry_days`보다 잔여 유통기한 일수가 작다면 백엔드 연산 엔진은 해당 수량을 **'실질 가용 재고'에서 즉시 제외**해야 한다.
- 가용 재고에서 차감된 물량은 시스템 내부적으로 **'출고 불가능(락인) 리스크 재고'**로 강제 분류 처리되어 프론트엔드 대시보드 화면상에 적색 리스크 지표 및 폐기 대상 수량으로 격리 표기된다.
  - **예시:** 오프라인 채널 마스터 기준이 180일인데 잔여 유통기한이 150일 남은 배치는 창고에 1,000캔이 쌓여 있어도 **가용 재고 0개, 락인 재고 1,000개**로 매칭 분류함.

### 6.2. 연간 고정 단가 기반 자산 가치 및 매칭형 폐기 손실 금액 계산 수식

**전사 총 현재고 금액 산출 식:**
각 거점 창고별 `CURRENT_INVENTORY.current_can_qty` 수량에 상품 마스터의 `fixed_unit_price`를 곱하고, 해당 배치가 최초 입고 적재될 당시 `INBOUND_LIST` 테이블에 박제된 실제 적용 환율(`exchange_rate`)을 사칙 연산하여 전사 자산 규모의 실시간 원화 가치를 대시보드 상단에 서빙한다.

**매칭형 폐기 손실 금액 산출 식:**
유통기한 가용성 필터링에 의해 폐기 위험 재고로 락인된 수량이 포착되는 즉시, 시스템은 단순 전사 평균 단가를 대입하는 논리적 오류를 배제한다. 해당 물량이 국내 입고될 당시 매칭되었던 인보이스 행의 실제 결제 환율과 마스터 고정 단가를 추적하여 다이렉트로 곱한 정밀 원화 기준 손실 원가를 산출하여 화면에 뿌려준다.

### 6.3. 풀필먼트 간 교차 이관(Transshipment) 및 물류비 예측 시뮬레이터

1. 허용 기준이 엄격한 오프라인 풀필먼트 창고(180일 기준)에서 유통기한 임박 경고 리스크 수량이 포착되는 즉시, 백엔드 엔진은 수용 기준이 상대적으로 완화된 온라인 풀필먼트 창고(90일 기준)의 주차별 출고 속도와 현재 가용 공간을 역산한다.
2. 온라인 채널의 소화 능력이 양수로 판명되면, 시스템은 대시보드 화면에 다음과 같은 교차 이관 추천 인디케이터를 생성한다:

   > 오프라인 창고의 A배치 재고 수량 **X개**를 온라인 창고로 이관하십시오. 이관 실행 시 전사 폐기 리스크가 100% 소멸합니다.

3. 이때 제안되는 추천 이관 수량은 단순 부족분이 아니며, 마스터 설정 테이블에 등록된 `ffc_moq` 또는 풀필먼트별 기본 입수량 단위의 배수에 맞추어 자동 반올림(`Math.round`) 및 절사 처리된 정형화된 묶음 단위로 화면에 출력되어야 한다.
4. 동시에 출발지와 도착지 간의 카툰 단가를 `LOGISTICS_COST_MASTER`에서 호출하여 다음 비용을 실시간 비용 시뮬레이션 결과로 대시보드 하단에 매칭 렌더링한다:

   ```text
   최종 예상 물류비 = 이관 카툰 수 * 카툰당 물류 단가
   ```

---

## CH 7. 프론트엔드 대시보드 화면 및 인터페이스 명세 (UI/UX)

시스템 UI는 상단 헤더 대신 좌측 **확장/축소 가능한 사이드바(Sidebar) 레이아웃**을 채택하여 공간 활용도와 메뉴 접근성을 극대화한다. 사이드바 하단에는 로그인 계정 정보 및 권한이 표기된다.

### 7.1. 5대 핵심 메뉴 구조

**① 메인 대시보드 (`/`)**
핵심만 볼 수 있는 시각화 메인 화면. 상단 KPI 카드(총 현재고, 재고자산 금액, 품절 위험 품목, 폐기 리스크 총액)와 중앙 수요-물류 이중 트랙 시각화 차트를 집중 배치한다.

**② 현재고 보유량 상세 (`/inventory`)**
거점별(풀필먼트별) 현재고 테이블 상세. 
특정 거점 간의 재고 이관(Transfer) 및 밸런싱을 통제하는 UI 위젯 제공.

**③ 재고 유통기한 상세 (`/expiry`)**
FEFO 기반 유통기한 임박 및 폐기 예상 물량 리스트, 추가 판매량 도출 등 유효기간 방어 계산기 화면.

**④ 발주 계획 (`/order-plan`)**
대상 연월 셀렉터를 통해 시스템 역산 제안 수량 확인 및 실무자 덮어쓰기 저장을 수행하는 편집 그리드.

**⑤ 파이프라인 매칭 시스템 (`/matching`)**
발주 - 생산 - 인보이스 발행 - 입고에 이르는 SCM 파이프라인 정형 엑셀 업로드 및 매칭 추적 화면. 다운로드 가능한 고정 양식을 여기서 제공한다.

**⑥ 운영 (`/users` - Admin 전용)**
사용자 계정(ID, PW, 역할, 이름) 생성/수정/삭제. 전체 데이터 강제 스냅샷 백업 기능 제공.
