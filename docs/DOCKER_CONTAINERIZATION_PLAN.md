# 🐳 Weather & Transit Web - Docker 컨테이너화 아키텍처 및 배포 계획서

> **문서 버전**: v1.0.0  
> **작성일자**: 2026-10-06  
> **대상 시스템**: 기상 및 대중교통 데이터 기반 실시간 수요 예측 웹 플랫폼  
> **관련 문서**: [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) | [REQUIREMENTS.md](./REQUIREMENTS.md) | [TODO_MOCK_AND_UNVERIFIED_DATA.md](./TODO_MOCK_AND_UNVERIFIED_DATA.md)

---

## 📌 1. 개요 및 목적

본 문서는 Weather & Transit Web 서비스를 프로덕션 환경 및 다양한 개발 환경에서 일관되고 안정적으로 실행하기 위한 **Docker 멀티 컨테이너 아키텍처 설계와 실행 계획**을 기술합니다.

### 🎯 핵심 목표
1. **환경 일관성 보장**: 개발 머신(Windows)과 클라우드 배포 머신(Linux/Docker) 간 Python 버전, C 라이브러리(ONNX Runtime용 OpenMP 등), Node.js 버전 차이 원천 배제.
2. **CORS 이슈 제로화**: Nginx 리버스 프록시를 전면에 배치하여 프론트엔드 정적 파일 서빙과 백엔드 API 포워딩을 단일 오리진(포트 80 또는 3000)으로 일원화.
3. **데이터 및 캐시 영속화**: 컨테이너 재시작 및 업데이트 시에도 2계층 시계열 캐시(`data/timeseries_feature_cache.db`) 및 외부 공공 API 스냅샷 보존.
4. **원클릭 오케스트레이션**: `docker compose up -d` 명령어 하나로 백엔드 AI 추론 세션 로딩, 헬스체크 통과, 프론트엔드 웹서버 기동을 완전 자동화.

---

## 🏗️ 2. 전체 컨테이너 아키텍처

```mermaid
flowchart TD
    subgraph Client ["브라우저 / 클라이언트"]
        User["사용자 웹 브라우저 (포트 80 or 3000)"]
    end

    subgraph DockerHost ["Docker Compose 오케스트레이션 (weather-transit-net)"]
        subgraph FrontendContainer ["frontend (Nginx Alpine)"]
            Nginx["Nginx Web Server"]
            SPA["React SPA 정적 번들 (/usr/share/nginx/html)"]
        end

        subgraph BackendContainer ["backend (Python 3.11-slim)"]
            FastAPI["FastAPI App (Uvicorn, Port 8000)"]
            ONNX["3대 ONNX 모델 세션 (bike/bus/subway)"]
            DB["timeseries_cache.db (SQLite WAL)"]
            CircuitBreaker["3상 서킷 브레이커 & 캐시 레이어"]
        end
    end

    subgraph PublicAPIs ["외부 공공 API"]
        KMA["기상청 API허브"]
        SubwayAPI["서울 지하철 도착 API"]
        BusAPI["공공데이터포털 버스 도착 API"]
    end

    subgraph HostVolume ["호스트 영속 볼륨"]
        DataVol[("./data ➔ SQLite DB & 캐시 영속화")]
    end

    User -->|정적 자산 요청 (HTML/CSS/JS)| Nginx
    Nginx -->|정적 파일 서빙| SPA
    User -->|API 요청 (/api/*, /health)| Nginx
    Nginx -->|리버스 프록시 (내부망 http://backend:8000)| FastAPI

    FastAPI --> ONNX
    FastAPI --> DB
    FastAPI --> CircuitBreaker
    DB -.->|영속성 바인딩| DataVol

    CircuitBreaker -->|HTTP 요청| KMA
    CircuitBreaker -->|HTTP 요청| SubwayAPI
    CircuitBreaker -->|HTTP 요청| BusAPI
```

---

## 📦 3. 구성 요소별 상세 설계 명세

### 3.1 백엔드 컨테이너 (`backend`)

- **베이스 이미지**: `python:3.11-slim`
- **시스템 패키지**:
  - `libgomp1`: ONNX Runtime의 OpenMP 멀티스레드 병렬 추론을 위한 필수 C 라이브러리
  - `curl`: Docker 내부 헬스체크용
- **레이어 캐싱 최적화**:
  - `requirements.txt`를 소스 코드보다 먼저 복사하여 `pip install` 실행. 소스 코드 수정 시 재빌드 시간을 수 초 내로 단축.
- **포트**: 컨테이너 내부 `8000` (Docker 내부 네트워크 통신용)
- **헬스체크**: `curl -f http://localhost:8000/health || exit 1`
  - 10초 간격 점검, 모델 로딩 완료(`models_loaded: true`) 확인 후 정상(healthy) 판정.

```dockerfile
# [설계 예시] Dockerfile.backend
FROM python:3.11-slim

WORKDIR /app

# 런타임 필수 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 레이어 캐시 활용을 위한 의존성 선반영
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 소스 및 AI 모델 복사
COPY main.py timeseries_cache.py ./
COPY models/ ./models/
COPY data/ ./data/

# 디렉터리 권한 및 포트 정의
EXPOSE 8000

# 헬스체크 설정
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
```

---

### 3.2 프론트엔드 컨테이너 (`frontend`)

- **멀티 스테이지 빌드 전략**:
  - **Stage 1 (Builder)**: `node:20-alpine`에서 의존성 설치 및 Vite 프로덕션 빌드 실행 (`npm ci` ➔ `npm run build`).
  - **Stage 2 (Runner)**: 초경량 `nginx:alpine` 이미지(약 25MB)에 산출물(`dist/`) 및 커스텀 `nginx.conf` 복사.
- **Nginx 리버스 프록시 및 SPA 라우팅**:
  - `location /`: SPA 히스토리 라우팅 (`try_files $uri $uri/ /index.html;`)
  - `location /api/`: `proxy_pass http://backend:8000/api/;` 포워딩
  - `location /health`: `proxy_pass http://backend:8000/health;` 포워딩
  - 정적 자산(CSS, JS, SVG, WebP)에 Gzip 압축 및 1년 유효기간 브라우저 캐싱 헤더 적용.

```dockerfile
# [설계 예시] Dockerfile.frontend
# --- Stage 1: Build Stage ---
FROM node:20-alpine AS builder

WORKDIR /app

COPY "Weather-Transport Recommendation UI/package*.json" ./
RUN npm ci

COPY "Weather-Transport Recommendation UI/" ./
RUN npm run build

# --- Stage 2: Runtime Stage ---
FROM nginx:alpine

# 기본 nginx 설정 교체
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 빌드 결과물 복사
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

```nginx
# [설계 예시] nginx.conf
server {
    listen 80;
    server_name localhost;

    # Gzip 압축 설정
    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;
    gzip_min_length 1024;

    # SPA 정적 파일 서빙
    location / {
        root /usr/share/nginx/html;
        index index.html index.htm;
        try_files $uri $uri/ /index.html;
    }

    # 정적 자산 캐싱
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        root /usr/share/nginx/html;
        expires 1y;
        add_header Cache-Control "public, no-transform";
    }

    # 백엔드 API 리버스 프록시 (CORS 원천 해소)
    location /api/ {
        proxy_pass http://backend:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 30s;
    }

    # 헬스체크 프록시
    location /health {
        proxy_pass http://backend:8000/health;
        proxy_set_header Host $host;
    }
}
```

---

### 3.3 오케스트레이션 명세 (`docker-compose.yml`)

- **서비스 의존성**: `frontend`는 `backend`가 헬스체크(`condition: service_healthy`)를 통과한 후 기동되도록 강제하여, 초기 접속 시 API 502/503 에러 발생 방지.
- **환경 변수**: 호스트의 `.env` 파일을 자동으로 읽어 백엔드 컨테이너에 주입.
- **볼륨**: `./data:/app/data` 마운트로 SQLite 시계열 캐시 DB 영속화.

```yaml
# [설계 예시] docker-compose.yml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    container_name: weather-transit-backend
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./data:/app/data
    ports:
      - "8000:8000" # 개발/디버깅 및 Swagger UI 문서 확인용 (선택적)
    networks:
      - weather-transit-net

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    container_name: weather-transit-frontend
    restart: unless-stopped
    ports:
      - "3000:80"   # 호스트 3000 포트 접속 시 웹 UI 표출
    depends_on:
      backend:
        condition: service_healthy
    networks:
      - weather-transit-net

networks:
  weather-transit-net:
    driver: bridge
```

---

### 3.4 빌드 컨텍스트 최적화 (`.dockerignore`)

불필요한 파일 복사로 인한 빌드 시간 지연 및 이미지 비대화를 방지하기 위해 정밀한 무시 규칙 적용:

```
# [설계 예시] .dockerignore
.git
.github
.vscode
__pycache__
*.pyc
*.pyo
*.pyd
venv
.env.local
.DS_Store
dist
node_modules
tests
api_example
*.log
```

---

## 📋 4. 파일 생성 및 수정 목록

```
weather-transit-web/
├── Dockerfile.backend                     # 백엔드 FastAPI + ONNX 빌드 명세
├── Dockerfile.frontend                    # 프론트엔드 Vite + Nginx 멀티스테이지 빌드 명세
├── nginx.conf                             # Nginx 라우팅 및 백엔드 리버스 프록시 설정
├── docker-compose.yml                     # 2개 컨테이너 연동 및 볼륨/네트워크 오케스트레이션
├── .dockerignore                          # 루트 디렉터리 빌드 제외 규칙 (venv, __pycache__ 등)
├── Weather-Transport Recommendation UI/
│   └── .dockerignore                      # 프론트엔드 빌드 제외 규칙 (node_modules, dist 등)
└── docs/
    └── DOCKER_CONTAINERIZATION_PLAN.md    # [본 문서] 컨테이너화 아키텍처 및 실행 계획서
```

---

## 🚀 5. 단계별 실행 로드맵 (Action Roadmap)

| 단계 | 작업 내용 | 검증 기준 | 산출물 |
| :---: | :--- | :--- | :--- |
| **Phase 4-1** | `.dockerignore` 파일 작성 | 루트 및 프론트엔드의 대용량 불필요 파일 제외 확인 | `.dockerignore`, UI `.dockerignore` |
| **Phase 4-2** | `Dockerfile.backend` 작성 | `python:3.11-slim`, `libgomp1`, 헬스체크 설정 검증 | `Dockerfile.backend` |
| **Phase 4-3** | `nginx.conf` 및 `Dockerfile.frontend` 작성 | 멀티스테이지 빌드 및 `/api/` 프록시 경로 검증 | `nginx.conf`, `Dockerfile.frontend` |
| **Phase 4-4** | `docker-compose.yml` 작성 | `depends_on: service_healthy`, `.env` 주입, `./data` 볼륨 매핑 | `docker-compose.yml` |
| **Phase 4-5** | 컨테이너 빌드 및 로컬 구동 검증 | `docker compose up --build -d` 실행 후 브라우저(`http://localhost:3000`) 정상 작동 확인 | 로컬 컨테이너 구동 |
| **Phase 4-6** | 엔드포인트 무결성 점검 | `http://localhost:3000/health`, 실시간 기상/지하철/버스 및 ONNX 추론 정상 확인 | 검증 보고서 |

---

## 🛠️ 6. 운영 및 유지보수 명령어 가이드

### 1) 서비스 빌드 및 백그라운드 기동
```bash
docker compose up --build -d
```

### 2) 서비스 상태 및 헬스체크 확인
```bash
docker compose ps
```
> `STATUS` 열에서 `healthy` 상태 확인.

### 3) 실시간 로그 모니터링
```bash
# 전체 서비스 로그
docker compose logs -f

# 백엔드 AI 추론 로그만 확인
docker compose logs -f backend
```

### 4) 서비스 정상 중지
```bash
docker compose down
```

### 5) 캐시 DB 볼륨을 유지한 채 코드만 재배포
```bash
git pull origin main
docker compose up --build -d
```

---

## 🔒 7. 보안 및 운영 권장사항

1. **환경변수(.env) 보안**:
   - 기상청, 서울시 지하철, 공공데이터포털 API 키가 포함된 `.env` 파일은 Git 저장소에 커밋하지 않고 호스트 파일시스템에만 안전하게 보관.
2. **비루트 사용자 권한**:
   - 컨테이너 런타임 보안을 위해 필요 시 Nginx 및 FastAPI 프로세스를 `appuser` 또는 `nginx` 비루트 계정으로 실행하도록 보안 강화 가능.
3. **리소스 제한 (Resource Limits)**:
   - 프로덕션 클라우드 배포 시 ONNX 추론 폭주 방지를 위해 `deploy.resources.limits`에 CPU(예: 2.0 코어), 메모리(예: 1.5GB) 상한을 설정할 것을 권장.
