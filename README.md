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
   - 가상 강수량(0~10mm/h) 조절에 따른 실시간 대중교통 수요 전이 시뮬레이터 제공
   - 📖 **자세한 내용은 [프론트엔드 전용 README](Weather-Transport%20Recommendation%20UI/README.md)를 참조하세요.**

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

프로젝트 루트 경로에 `.env` 파일을 생성하고 발급받은 API 키를 설정합니다.

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

### 3. 프론트엔드 웹 대시보드 실행 (React / Vite)
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
├── .env                                # API 키 및 환경 변수 설정 파일 (git 제외)
├── .gitignore                          # Git 추적 제외 목록 (.env, venv 등)
├── requirements.txt                    # Python 의존성 라이브러리 목록
├── test_api.py                         # 날씨/버스/지하철 외부 API 연동 검증 스크립트
├── README.md                           # 프로젝트 전체 안내 문서
├── map.html                            # MapLibre GL JS + OSM 단독 테스트 페이지
├── data/                               # 📊 정류장 및 교통 마스터 데이터 (Git 제외 관리)
│   └── subway_stations.json            # 수도권 전체 지하철역 마스터 데이터셋 (696개)
├── docs/
│   └── REQUIREMENTS.md                 # 프로젝트 요구사항 명세서 (팀 선견지명)
├── api_example/                        # API 규격 및 공식 활용 가이드 문서
└── Weather-Transport Recommendation UI/ # 🌐 프론트엔드 React 웹 대시보드
    ├── README.md                       # 프론트엔드 전용 안내 문서
    ├── data/                           # 📊 지하철역 원천 엑셀 및 JSON 데이터
    │   ├── 실시간도착_역정보(20260902).xlsx
    │   └── subway_stations.json
    ├── package.json                    # Node.js 패키지 의존성
    ├── tsconfig.json                   # TypeScript 설정
    ├── vite.config.ts                  # Vite 개발 서버 설정
    ├── index.html                      # HTML 템플릿 (MapLibre GL CDN 연동)
    └── src/
        ├── App.tsx                     # 메인 대시보드 및 탭 레이아웃
        ├── TransitMap.tsx              # MapLibre GL JS + OSM 지도 컴포넌트
        ├── subwayData.ts               # 수도권 563개 전체 역 마스터 데이터 & 검색 엔진
        ├── apiLogger.ts                # 개발자 콘솔용 실시간 API 로거
        ├── main.tsx                    # React 진입점
        └── index.css                   # 글로벌 스타일
```

