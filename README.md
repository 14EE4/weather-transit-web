# 🌤️ Weather & Transit Web (날씨 및 대중교통 실시간 안내 서비스)

실시간 날씨 정보(기상청 초단기실황)와 서울시 대중교통(지하철 및 버스 실시간 도착 정보)을 통합 제공하는 웹 서비스 프로젝트입니다.

---

## 📌 주요 기능

1. **기상청 초단기실황 날씨 정보**
   - 현재 위치(격자 좌표) 기준 실시간 기온(T1H), 1시간 강수량(RN1), 강수 형태(PTY), 습도(REH), 풍속(WSD) 조회
   - 기상청 API허브 기준 매시 정각 발표 자료 자동 동기화 (매시 10분 이전 호출 시 전 시간대 데이터 자동 보정)

2. **서울시 지하철 실시간 도착 정보**
   - 지하철역별 실시간 열차 도착 현황 (방면, 도착 메시지, 남은 시간, 급행/일반 여부)
   - 서울 열린데이터광장 OpenAPI 연동

3. **서울시 버스 도착 정보 (공공데이터포털)**
   - **노선 전체 정류소 도착 예정 정보 조회 (`getArrInfoByRouteAll`)**: 노선 ID(`busRouteId`) 기준 전체 경유 정류소별 첫차/막차 도착 예정 메시지(`arrmsg1`, `arrmsg2`) 및 정류소 순번(`staOrd`) 제공
   - **정류소별 저상버스 도착 예정 정보 조회 (`getLowArrInfoByStId`)**: 정류소 고유 ID(`stId`, 9자리) 기준 저상버스 실시간 도착 정보 제공
   - `resultType="json"` 응답 처리 및 인증키 이중 인코딩(Double Encoding) 방지 적용

4. **실시간 대화형 대시보드 & MapLibre GL 지도 (React)**
   - OpenStreetMap(OSM) 래스터 타일 기반의 실시간 대화형 웹 지도
   - **수도권 전체 561개 지하철역 정밀 GPS 좌표 완벽 매핑**:
     - 서울 열린데이터광장 역사마스터(`subwayStationMaster`) API 전수 검증을 거친 소수점 6자리 정밀 GPS 좌표 탑재
     - 좌표 불일치 및 특정 위치 뭉침 현상(fallback 좌표) 완전 해결
   - **새로고침 시 탭 상태 유지 (URL Hash & LocalStorage 연동)**:
     - `지도 보기` 탭(#map)이나 `경로 추천` 탭(#route)에서 새로고침(F5)을 해도 기존 탭이 유지되도록 영속화
   - **지하철역 검색 키보드 접근성 완벽 지원**:
     - 지도 탭 및 경로 추천 탭(출발역/도착역) 검색 시 `Enter`, `Tab` + `Enter`, `방향키(↑/↓)`로 역을 선택 가능
     - 하이라이트된 검색 항목 자동 스크롤(Auto Scroll) 및 단축키 안내 툴팁 지원
   - **지도 역 마커 겹침 방지 (화면 충돌 감지 & 확대 시 순차 노출)**:
     - 축소 시 역 마커들이 겹치는 시각적 혼잡을 방지하기 위해 겹치는 구역에서는 핵심 거점 역 1개만 우선 노출
     - 지도를 확대(Zoom-in)하면 인접한 세부 역 및 정류소가 부드럽게 순차적으로 모두 나타남
     - 사용자가 검색하거나 선택한 역은 항상 최우선으로 화면에 100% 표시됨
   - 가상 강수량(0~10mm/h) 조절에 따른 실시간 대중교통 수요 전이 시뮬레이터 제공
   - 📖 **프론트엔드 상세 가이드**: [프론트엔드 README](Weather-Transport%20Recommendation%20UI/README.md)
   - 🧠 **백엔드 AI 추론 모델 사양서**: [AI 추론 모델 개발 가이드](docs/AI_INFERENCE_MODEL_SPEC.md)

---

## 🛠️ 기술 스택 및 환경

- **언어**: Python 3.10+
- **주요 라이브러리**: `requests`, `python-dotenv`
- **외부 API**:
  - [기상청 API허브](https://apihub.kma.go.kr/) - 단기예보조회서비스 (초단기실황조회 `getUltraSrtNcst`)
  - [서울 열린데이터광장](https://data.seoul.go.kr/) - 서울시 지하철 실시간 도착 정보 (`realtimeStationArrival`)
  - [공공데이터포털](https://www.data.go.kr/) - 서울특별시 버스도착정보조회 서비스 (`ws.bus.go.kr/api/rest/arrive`)

---

## ⚙️ 환경 변수 설정 (`.env`)

저장소에 포함된 [`.env.example`](.env.example) 템플릿 파일을 복사하여 루트 경로에 `.env` 파일을 생성하고 발급받은 실제 API 키를 설정합니다.

  ```bash
# Windows PowerShell
Copy-Item .env.example .env

# Bash / Linux
cp .env.example .env
```

```env
# 기상청 API허브 (https://apihub.kma.go.kr - 초단기실황조회)
KMA_APIHUB_KEY=your_kma_apihub_key_here

# 서울 열린데이터광장 (https://data.seoul.go.kr - 지하철 실시간 도착 정보)
SEOUL_SUBWAY_API_KEY=your_seoul_subway_key_here

# 공공데이터포털 (https://www.data.go.kr - 서울특별시 버스도착정보조회)
DATA_GO_KR_API_KEY=your_data_go_kr_key_here

# 백엔드 서버 URL (프론트엔드 연동 시)
VITE_API_BASE_URL=http://localhost:8000
```

---

## 🚀 설치 및 테스트 방법

### 1. 가상환경 활성화 및 패키지 설치
  ```bash
# 가상환경 생성 (최초 1회)
python -m venv venv

# 가상환경 활성화 (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# 필수 의존성 패키지 설치
pip install -r requirements.txt
```

### 2. API 연결 테스트 실행
  ```bash
python test_api.py
```

정상 연동 시 터미널에서 다음과 같은 테스트 결과를 확인할 수 있습니다:
```text
==================================================
[1] 기상청 실시간 날씨 API 테스트 (초단기실황)
==================================================
[성공] 기준 시각: 20260926 1800 (격자: nx=61, ny=125)
- 기온(T1H): 24.3 ℃
- 1시간 강수량(RN1): 0 mm
- 강수 형태(PTY): 없음(맑음/흐림) (0)
- 습도(REH): 59 %
- 풍속(WSD): 0.8 m/s

==================================================
[2] 서울 버스 도착 정보 API 테스트
==================================================

[기능 1] get_arrival_by_route_all(busRouteId='100100118') 테스트:
>> 전체 104개 정류소 중 상위 3개 정류소 도착 현황:
- [1] 구산동사거리(111000299): 1번째=출발대기 | 2번째=출발대기
- [2] 한솔아파트입구.선정중학교후문(111000181): 1번째=출발대기 | 2번째=출발대기
- [3] 갈현동미미아파트(111000182): 1번째=출발대기 | 2번째=출발대기

[기능 2] get_low_bus_arrival_by_stid(stId='111000299') 테스트:
>> 저상버스 도착 정보 3건:
- [753번] @ 구산동사거리: 출발대기 | 출발대기
- [7613번] @ 구산동사거리: [차고지출발]  | 출발대기
- [8774번] @ 구산동사거리: 8분11초후[5번째 전] | 52분54초후[34번째 전]

==================================================
[3] 서울 지하철 도착 정보 API 테스트 (역명: 강남)
==================================================
[성공] '강남'역 실시간 도착 정보 (5건):
- [성수행 - 역삼방면] (일반) 현황: 전역 도착 (예정: 90초)
- [신사행 - 신논현방면] (일반) 현황: 전역 진입 (예정: 0초)
- [성수행 - 역삼방면] (일반) 현황: 7분 후 (예정: 420초)
- [신사행 - 신논현방면] (일반) 현황: [4]번째 전역 (판교) (예정: 0초)
- [광교행 - 양재방면] (일반) 현황: 전역 도착 (예정: 0초)
```

### 3. 백엔드 AI 추론 서버 실행 및 검증 (FastAPI & ONNX)
- **통합 검증 테스트 스위트 실행**:
  ```bash
  python test_inference.py
  ```
  *(ONNX 세션 웜업, 32차원 Feature Vector 정합성, 맑은 날/폭우 모달 시프트, 10회 연속 레이턴시 SLA 벤치마크 검증)*

- **FastAPI 백엔드 서버 실행**:
  ```bash
  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
  ```
  - Swagger 대화형 API 문서: http://localhost:8000/docs
  - 서버 헬스체크: http://localhost:8000/health
  - 📖 **상세 엔드포인트 및 서빙 가이드**: [AI 추론 백엔드 서버 구축 가이드](docs/BACKEND_INFERENCE_SERVER.md)

### 4. 프론트엔드 웹 대시보드 실행 (React / Vite)
  ```bash
# 프론트엔드 디렉토리 이동
cd "Weather-Transport Recommendation UI"

# 의존성 패키지 설치
npm install

# 로컬 개발 서버 구동 (포트 8443)
npm run dev
```
- 브라우저 접속: **`http://localhost:8443/`**
- 상단 메뉴에서 **[지도]** 탭을 클릭하여 MapLibre GL JS + OSM 지도와 AI 예측 시뮬레이터를 확인하실 수 있습니다.

---

## 🔑 API 발급 및 활용 신청 안내

1. **기상청 API허브 (`KMA_APIHUB_KEY`)**
   - [기상청 API허브](https://apihub.kma.go.kr/) 회원가입 후 로그인
   - **[동네예보조회서비스(2.0)]** 검색 후 **초단기실황조회** 활용 신청
   - 마이페이지 > 인증키 복사 후 `.env`의 `KMA_APIHUB_KEY`에 입력

2. **서울 열린데이터광장 (`SEOUL_SUBWAY_API_KEY`)**
   - [서울 열린데이터광장](https://data.seoul.go.kr/) 회원가입 후 인증키 신청
   - **[서울시 지하철 실시간 도착정보]** 데이터셋 검색 후 **활용 신청** (실시간 서비스 사용 권한 획득)
   - 승인된 일반 인증키를 `.env`의 `SEOUL_SUBWAY_API_KEY`에 입력

3. **버스 도착 정보 (`DATA_GO_KR_API_KEY`)**
   - [공공데이터포털](https://www.data.go.kr/)에서 **'서울특별시_버스도착정보조회'** 활용 신청
   - 발급된 일반 인증키를 `.env`의 `DATA_GO_KR_API_KEY`에 입력
   - **[주의 사항]**:
     - 신청/발급 직후 게이트웨이 동기화에 약 1~2시간 소요될 수 있습니다.
     - 본 API는 5자리 정류소 번호(`arsId`) 단독 조회 엔드포인트가 없으므로 노선 ID(`busRouteId`) 또는 9자리 정류소 고유 ID(`stId`)를 사용해야 합니다.
     - 키 전달 시 requests 라이브러리의 자동 인코딩과의 충돌(이중 인코딩 오류) 방지를 위해 `urllib.parse.unquote()` 처리가 필요합니다.

---

## 📁 디렉토리 구조

```text
weather-transit-web/
├── .env                                # API 키 및 환경 변수 설정 파일 (Git 추적 제외)
├── .env.example                        # 환경 변수 예시 템플릿 (Git 포함, 참고용)
├── .gitignore                          # Git 추적 제외 목록 (.env, venv 등)
├── requirements.txt                    # Python 의존성 라이브러리 목록
├── main.py                             # ⚡ FastAPI 백엔드 AI 추론 서버 (ONNX 인메모리 로딩 & 서빙)
├── test_inference.py                   # 🧪 ONNX 모델 및 추천 API 통합 검증 스크립트
├── test_api.py                         # 날씨/버스/지하철 외부 공공 API 연동 검증 스크립트
├── README.md                           # 프로젝트 전체 안내 문서
├── map.html                            # MapLibre GL JS + OSM 단독 테스트 페이지
├── models/                             # 🧠 학습 완료된 ONNX 머신러닝 모델 가중치 파일
│   ├── lgb_bike_demand.onnx            # 따릉이 대여 수요 예측 ONNX 모델
│   ├── lgb_bus_demand.onnx             # 버스 승차 수요 예측 ONNX 모델
│   └── lgb_subway_demand.onnx          # 지하철 승하차 수요 예측 ONNX 모델
├── data/                               # 📊 정류장 및 교통 마스터 데이터 (Git 제외 관리)
│   └── subway_stations.json            # 수도권 전체 지하철역 마스터 데이터셋 (696개)
├── docs/
│   ├── AI_INFERENCE_MODEL_SPEC.md      # AI 추론 모델 개발 사양서 및 구축 가이드
│   ├── BACKEND_INFERENCE_SERVER.md     # FastAPI AI 추론 백엔드 서버 구축 및 운영 가이드
│   └── REQUIREMENTS.md                 # 프로젝트 요구사항 명세서
├── api_example/                        # API 규격 및 공식 활용 가이드 문서
└── Weather-Transport Recommendation UI/ # 🌐 프론트엔드 React 웹 대시보드 (세부 구조 및 변경 이력은 내부 README 참조)
    ├── README.md                       # 프론트엔드 전용 안내 문서
    └── docs/                           # 📖 프론트엔드 상세 문서 (CHANGELOG.md 등)
```

---

## 📋 변경 이력 (Changelog)

- **프론트엔드 변경 이력**: 기능별 상세 변경 내역 및 원인 분석은 **[`Weather-Transport Recommendation UI/docs/CHANGELOG.md`](Weather-Transport%20Recommendation%20UI/docs/CHANGELOG.md)**를 참조하세요.

