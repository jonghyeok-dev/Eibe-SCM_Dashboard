# EIBE SCM Dashboard — Project Rules & Guidelines

> **Last Updated:** 2026-06-19
> 이 파일은 이 프로젝트에서 코드 작성 시 반드시 준수해야 할 규칙과 참고사항을 정리한 문서입니다.

---

## 1. 전체 수정 원칙 (★ 최우선)

### 1.1. 연쇄 오류 방지 — "한 파일 수정 시 연관 파일 전수 검사"
- **하나의 함수/변수/CSS 클래스를 수정하면, 해당 심볼을 참조하는 모든 파일을 반드시 검색하여 영향도를 확인한다.**
- `app.js`의 공통 함수(Format, API, Toast, Theme, ChartDefaults 등)를 변경할 경우, 6개 모든 페이지 HTML을 확인한다.
- CSS 클래스를 추가/변경/삭제할 경우, 해당 클래스를 사용하는 모든 HTML 파일을 확인한다.
- **수정 완료 후 반드시 HTML 태그 매칭(div/section/script 등) 및 ID 중복 검사를 수행한다.**

### 1.2. 샘플 데이터 일관성
- 모든 페이지의 샘플 데이터는 동일한 상품 마스터(SN-001~SN-004)와 창고 목록(hub, online, offline, buyout, coupang)을 사용한다.
- API가 미연결 상태에서도 샘플 데이터로 완전히 동작해야 한다.
- 샘플 데이터 수정 시 모든 페이지에서 동일한 값이 사용되는지 확인한다.

### 1.3. Null Safety
- API 응답 데이터의 모든 필드 접근 시 `null`/`undefined` 체크를 반드시 수행한다.
- DOM 요소 접근 시 `document.getElementById()` 결과가 `null`일 수 있으므로 가드를 둔다.
- `d.saved_qty`, `d.hub_moq` 같은 옵션 필드는 반드시 fallback 값을 제공한다.

---

## 2. 기술 스택 & 아키텍처

### 2.1. 프론트엔드
- **HTML/CSS/JS만 사용** — 프레임워크(React, Vue 등) 사용 금지
- CSS: `web/static/css/style.css` 단일 파일
- JS: `web/static/js/app.js` 공통 유틸 + 각 HTML 페이지 내 인라인 `<script>`
- 차트: Chart.js 4.x (CDN)

### 2.2. 백엔드
- Python 3.11 + FastAPI + Uvicorn
- 데이터베이스: SQLite 3 (data/local_erp.db)
- 머신러닝 라이브러리 사용 금지 (사칙연산 기반 예측만 허용)

### 2.3. 파일 구조
```
web/
├── static/
│   ├── css/style.css    ← 전역 CSS (유일한 스타일시트)
│   ├── js/app.js        ← 공통 JS (API, Format, Theme, Toast, ChartDefaults 등)
│   └── img/             ← 이미지 자산
├── index.html           ← 요약 대시보드
├── inventory.html       ← 현재고 현황
├── order_plan.html      ← 발주 계획
├── matching.html        ← 입고 관리
├── expiry.html          ← 유통기한 관리
├── users.html           ← 시스템 운영
└── login.html           ← 로그인
```

---

## 3. UI/UX 디자인 규칙

### 3.1. 레이아웃
- 모든 페이지: 좌측 사이드바(`app-sidebar`) + 우측 메인(`main-content`)
- 페이지 헤더(`page-header`): **제목/소제목 중앙 정렬**, 날짜 우측 상단 (absolute)
- 페이지 헤더 내부 제목/소제목은 `page-header-left` div로 래핑

### 3.2. 서브 네비게이션 (탭)
- 한 페이지에 너무 많은 내용을 넣지 않는다
- 주제가 다른 콘텐츠는 `sub-nav` + `sub-view` 탭으로 분리
- 예: 현재고 현황 → 재고 현황 | 이관 계획 | 데이터 관리

### 3.3. 날짜/주차 표기
- **주차 표기**: `Jun-W3` 형식 (영문 월약어 3글자 + `-W` + 주차번호)
- **한국어 주차 사용 금지** (6월 3주차 → `Jun-W3`)
- **날짜 표시**: `2026년 6월 19일 (목)` 형식으로 각 페이지 헤더 우측
- **날짜/시간**: `YYYY-MM-DD HH:MM:SS` (업데이트 일시 등)
- `Format.weekLabel()`, `Format.weekLabels()`, `Format.monthLabel()` 함수 사용

### 3.4. 테이블
- 세로 구분선 포함 (컬럼 명확 구분)
- 텍스트: 왼쪽 정렬
- 숫자: 오른쪽 정렬 (`text-right` 클래스)
- 상태: 가운데 정렬
- 코드: `mono` 클래스 (고정폭 서체)

### 3.5. 색상 시스템
- 메인 브랜드: `--accent-main` (#29AD3A)
- 성공/긍정: `--accent-green` (#29AD3A)
- 경고/주의: `--accent-amber` (#e08a00)
- 위험/부정: `--accent-red` (#e53535)
- **이모지 사용 금지** — SVG 아이콘만 사용
- 버튼: 플랫 디자인 (box-shadow/gradient 없음)

### 3.6. 접기/열기 (Collapsible)
- 차트/히트맵 등 큰 시각화 영역에 적용
- `collapsible-header` + `collapsible-body` 클래스
- `toggleCollapsible()` 함수 사용

---

## 4. 데이터 & 비즈니스 로직

### 4.1. 상품 마스터
| 코드 | 품명 | 단가 |
|------|------|------|
| SN-001 | 산양분유 1단계 | ₩22,500 |
| SN-002 | 산양분유 2단계 | ₩21,000 |
| SN-003 | 산양분유 3단계 | ₩22,500 |
| SN-004 | 산양분유 4단계 | ₩20,000 |

### 4.2. 창고 목록
| ID | 이름 |
|----|------|
| hub | 용인 메인창고 |
| online | 온라인 FFC |
| offline | 오프라인 FFC |
| buyout | 바이아웃 채널 |
| coupang | 쿠팡 FFC |

### 4.3. 발주 계획 핵심 규칙
- **발주는 6개월 뒤 도착분을 주문하는 것** — 이를 UI에 명확히 표시
- 리드타임: 생산 + 해상운송 + 통관 = 약 6개월
- 발주 수량 변경 → 시뮬레이션 자동 재계산 → 히트맵 + 차트 모두 반영
- 시뮬레이션 가중치 변경 → 동일하게 히트맵 + 차트 모두 반영
- 발주 상태: 수정 중(draft) ↔ 확정(confirmed), 확정 후에도 "수정" 가능

### 4.4. 재고일수 히트맵 기준 (3개월 = 13주 적정)
| 범위 | 색상 | 의미 |
|------|------|------|
| < 6주 | 빨강 (`risk-high`) | 위험 |
| 6~9주 | 노랑 (`risk-mid`) | 주의 |
| 9~13주 | 녹색 (`risk-low`) | 양호 (적정) |
| > 13주 | 파랑 (`risk-safe`) | 과잉 |

### 4.5. 재고 자산 계산
- 자산 금액 = 수량 × 품목별 고정 단가
- 창고별로 자산 단가가 다를 수 있음 (품목 단가 기준)
- 변동 단가 추적 배제 (연간 고정 계약)

### 4.6. 이관 계획
- 용인 메인창고(HUB) → 각 풀필먼트 창고로 이관
- 이관 모달: 창고 선택 → 전체 SKU 테이블 형태로 수량 입력
- 한 창고에 여러 SKU가 일정에 맞추어 이동
- 엑셀 업로드 지원

---

## 5. app.js 공통 유틸리티 참조

### 전역 객체
| 이름 | 용도 |
|------|------|
| `API` | REST API 호출 (get, post, put, delete, postFormData) |
| `Auth` | 인증 관리 (init, login, logout, isLoggedIn) |
| `Format` | 숫자/날짜/주차 포맷팅 |
| `Theme` | 다크모드 토글 |
| `Sidebar` | 사이드바 접기/펼치기 |
| `ChartDefaults` | Chart.js 기본 스타일 설정 |
| `Toast` | 토스트 알림 |

### 전역 함수
| 이름 | 용도 |
|------|------|
| `switchTab(groupId, tabName)` | 탭 전환 |
| `downloadTemplate(type)` | 엑셀 템플릿 다운로드 |
| `toggleCollapsible(headerId)` | 섹션 접기/열기 |
| `injectTodayDate()` | 페이지 헤더에 오늘 날짜 주입 |

### Format 주요 함수
| 함수 | 반환 예시 |
|------|-----------|
| `Format.number(12345)` | `12,345` |
| `Format.currency(22500)` | `₩22,500` |
| `Format.weekLabel(3)` | `Jun-W3` |
| `Format.weekLabels(24)` | `['Jun-W3', 'Jun-W4', ...]` |
| `Format.monthLabel(2)` | `Aug 2026` |
| `Format.today()` | `2026년 6월 19일 (목)` |
| `Format.dateTime()` | `2026-06-19 15:13:17` |

---

## 6. 체크리스트 (수정 시 반드시 확인)

- [ ] HTML 태그 매칭 (div, section, script, table, thead, tbody)
- [ ] ID 중복 없음
- [ ] CSS 변수 참조가 `:root`에 정의되어 있는지
- [ ] app.js 공통 함수/객체 참조가 유효한지
- [ ] 샘플 데이터가 API 미연결 시에도 동작하는지
- [ ] null/undefined 가드가 모든 DOM 접근/API 데이터에 적용되었는지
- [ ] 주차 표기가 `Month-W#` 영문 패턴인지
- [ ] 테이블 정렬 규칙 (텍스트 좌, 숫자 우, 상태 중앙)
- [ ] 모바일 반응형 고려 (최소 min-width 기준)
- [ ] 다크모드 호환 (CSS 변수 사용)
