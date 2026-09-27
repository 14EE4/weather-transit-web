# 🚇 Weather & Transit Web - Frontend Dashboard

> **팀명**: 선견지명  
> **상위 프로젝트 문서**: [`../../README.md`](../README.md)  
> **요구사항 명세서**: [`../../docs/REQUIREMENTS.md`](../docs/REQUIREMENTS.md)  

기상 및 교통 데이터를 기반으로 지역별 대중교통 이용 수요와 혼잡도를 예측하고 시각화하는 React/Vite 기반 웹 대시보드입니다.

---

## 📌 주요 화면 및 기능

### 1. 메인 대시보드 (`page === 'main'`)
- **실시간 기상 요약**: 기온, 강수량, 습도, 풍속 상태 표시
- **교통수단 추천 스코어**: 현재 기상 상황에 따른 최적 이동 수단(지하철/버스/따릉이) 추천 및 추천 사유 제시
- **강우량-이용객 상관관계 시각화**: 강수량 변화에 따른 교통수단별 수요 변동 추이 차트
- **행정동별 실시간 혼잡도**: 서울 주요 행정동 단위 지하철/버스/따릉이 혼잡도 게이지

### 2. 기상 맞춤형 경로 추천 (`page === 'route'`)
- 출발지 및 도착지 입력 기반 경로 탐색
- 기상 악화(우천, 강설 등) 시 교통수단별 예상 소요 시간 및 요금, 혼잡도 비교 안내

### 3. 실시간 인터랙티브 지도 (`page === 'map'`) — `TransitMap.tsx`
- **MapLibre GL JS & OpenStreetMap(OSM)**: 오픈소스 래스터 타일을 활용한 부드러운 3D 틸트/회전 지도 렌더링
- **실제 좌표 기반 거점 마커**:
  - 서울 주요 지하철역(강남, 역삼, 삼성, 종합운동장, 잠실, 서울역, 여의도, 홍대입구 등)
  - 주요 버스 환승 정류소(강남역 중앙차로, 신논현역, 여의도환승센터, 서울역버스환승센터 등)
  - 따릉이 대여소(강남역 9번출구, 여의나루역 앞, 잠실역 등)
- **AI 예측 혼잡도 동적 컬러링**:
  - 🟢 여유 (&lt; 45%) / 🔵 보통 (45% ~ 75%) / 🔴 혼잡 (&gt; 75%)
  - 마커 클릭 시 정류소별 노선 정보 및 기상 민감도 분석 팝업 표출
- **⚡ AI 날씨-수요 시뮬레이터**:
  - 가상 강수량 슬라이더(0.0 ~ 10.0 mm/h) 조절 시 실시간 수요 전이(따릉이 급감, 대중교통 집중) 시뮬레이션
  - 시간대별(07시~21시) 시계열 예측 필터
- **권역 원클릭 카메라 이동(FlyTo)**: 강남·역삼, 잠실·송파, 여의도, 서울역·도심

---

## 🛠️ 기술 스택

- **Framework**: React 19, TypeScript
- **Bundler / Dev Server**: Vite 8
- **Styling**: Tailwind CSS v4, Custom Dark Glassmorphism Theme
- **Map Engine**: MapLibre GL JS v4, OpenStreetMap (Raster Tiles)

---

## 📁 디렉토리 구조

```text
Weather-Transport Recommendation UI/
├── index.html                  # HTML 진입점 (MapLibre GL JS CDN 연동)
├── package.json                # 의존성 및 스크립트 정의
├── tsconfig.json               # TypeScript 컴파일러 설정
├── vite.config.ts              # Vite 설정 (포트 8443)
└── src/
    ├── main.tsx                # React Root 진입 파일
    ├── index.css               # Tailwind CSS 및 글로벌 스타일
    ├── vite-env.d.ts           # 전역 타입 정의 (maplibregl 등)
    ├── App.tsx                 # 전체 대시보드 레이아웃 및 탭 라우팅
    └── TransitMap.tsx          # MapLibre GL JS + OSM 연동 핵심 지도 컴포넌트
```

---

## 🚀 실행 및 빌드 방법

### 1. 의존성 패키지 설치
```bash
npm install
```

### 2. 개발 서버 구동
```bash
npm run dev
```
- 브라우저 접속: **`http://localhost:8443/`**

### 3. 프로덕션 빌드
```bash
npm run build
```
- 빌드 결과물은 `dist/` 디렉토리에 생성됩니다.
