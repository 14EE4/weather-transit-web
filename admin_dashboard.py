"""
admin_dashboard.py - 백엔드 독립형 실시간 시스템 헬스체크 및 로그 모니터링 대시보드
FastAPI의 /health/dashboard 엔드포인트에서 단독 웹 페이지로 렌더링됩니다.
"""

import os
import sqlite3
import time
from datetime import datetime
from typing import Any, Dict

from in_memory_log_handler import in_memory_log_handler

SERVER_START_TIME = time.time()


def get_system_uptime_str() -> str:
    """서버 가동 시간(Uptime) 포맷팅"""
    uptime_sec = int(time.time() - SERVER_START_TIME)
    hours, rem = divmod(uptime_sec, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours > 0:
        return f"{hours}시간 {minutes}분 {seconds}초"
    elif minutes > 0:
        return f"{minutes}분 {seconds}초"
    return f"{seconds}초"


def get_cache_stats() -> Dict[str, Any]:
    """timeseries_cache.db 통계 조회"""
    db_candidates = [
        os.path.join(os.getcwd(), "timeseries_cache.db"),
        os.path.join(os.getcwd(), "data", "timeseries_cache.db"),
        "/app/data/timeseries_cache.db",
        "/app/timeseries_cache.db",
    ]
    db_path = None
    for p in db_candidates:
        if os.path.exists(p):
            db_path = p
            break

    if not db_path:
        return {"exists": False, "count": 0, "size_kb": 0, "path": "미생성"}

    try:
        size_kb = round(os.path.getsize(db_path) / 1024, 1)
        conn = sqlite3.connect(db_path, timeout=1.0)
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM timeseries_cache")
        row = cur.fetchone()
        count = row[0] if row else 0
        conn.close()
        return {"exists": True, "count": count, "size_kb": size_kb, "path": db_path}
    except Exception as exc:
        return {"exists": True, "count": 0, "size_kb": 0, "error": str(exc)}


def render_dashboard_html() -> str:
    """
    단일 파일 경량 반응형 HTML/CSS/JS 대시보드 생성
    """
    html_content = """<!DOCTYPE html>
<html lang="ko" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Weather & Transit | Backend Health & Live Logs</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Pretendard:wght@400;600;700;800&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: {
            sans: ['Pretendard', '-apple-system', 'sans-serif'],
            mono: ['JetBrains Mono', 'monospace'],
          },
          colors: {
            brand: {
              50: '#F0FDF4',
              500: '#10B981',
              600: '#059669',
            }
          }
        }
      }
    }
  </script>
  <style>
    /* Custom Scrollbar */
    ::-webkit-scrollbar {
      width: 8px;
      height: 8px;
    }
    ::-webkit-scrollbar-track {
      background: #0F172A;
    }
    ::-webkit-scrollbar-thumb {
      background: #334155;
      border-radius: 4px;
    }
    ::-webkit-scrollbar-thumb:hover {
      background: #475569;
    }
    .log-line:hover {
      background-color: rgba(255, 255, 255, 0.04);
    }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen font-sans flex flex-col selection:bg-emerald-500 selection:text-white">

  <!-- Header -->
  <header class="bg-slate-900/80 backdrop-blur border-b border-slate-800 sticky top-0 z-50 px-6 py-3.5 flex flex-wrap items-center justify-between gap-4">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-emerald-600 to-sky-500 flex items-center justify-center shadow-lg shadow-emerald-500/20 text-white font-bold text-lg">
        ⚡
      </div>
      <div>
        <div class="flex items-center gap-2">
          <h1 class="text-base font-bold tracking-tight text-white">Weather & Transit Observability</h1>
          <span class="px-2 py-0.5 text-xs font-semibold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
            System Live
          </span>
        </div>
        <p class="text-xs text-slate-400 font-mono" id="server-uptime">Uptime: 계산 중...</p>
      </div>
    </div>

    <!-- Quick Actions -->
    <div class="flex items-center gap-2.5">
      <a href="/docs" target="_blank" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors border border-slate-700 flex items-center gap-1.5">
        <span>📖 Swagger API Docs</span>
        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg>
      </a>
      <a href="/health" target="_blank" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors border border-slate-700 flex items-center gap-1.5">
        <span>🔍 Raw /health JSON</span>
      </a>
      <button onclick="fetchSystemStatus()" class="px-3 py-1.5 text-xs font-semibold rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition-all shadow-md shadow-emerald-600/20 flex items-center gap-1.5">
        <svg id="refresh-icon" class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
        <span>상태 새로고침</span>
      </button>
    </div>
  </header>

  <!-- Main Container -->
  <main class="flex-1 p-6 max-w-7xl w-full mx-auto space-y-6">

    <!-- KPI Metric Cards Grid -->
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      
      <!-- Card 1: 기상청 API & 서킷브레이커 -->
      <div class="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between shadow-sm">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2 text-sky-400 font-bold text-sm">
            <span class="text-base">🌦️</span> 기상청 API 허브
          </div>
          <span id="cb-kma-badge" class="px-2 py-0.5 text-[11px] font-bold rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            CLOSED (정상)
          </span>
        </div>
        <div class="space-y-1.5 text-xs">
          <div class="flex justify-between text-slate-400">
            <span>초단기실황 연동:</span>
            <span class="text-slate-200 font-semibold" id="kma-endpoint-status">25개 자치구 지원</span>
          </div>
          <div class="flex justify-between text-slate-400">
            <span>서킷 실패 카운트:</span>
            <span class="text-slate-200 font-mono" id="cb-kma-failures">0회</span>
          </div>
          <div class="flex justify-between text-slate-400">
            <span>성공 누적 / 폴백:</span>
            <span class="text-slate-200 font-mono" id="cb-kma-totals">0 / 0</span>
          </div>
        </div>
      </div>

      <!-- Card 2: 서울 버스 & 지하철 -->
      <div class="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between shadow-sm">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2 text-emerald-400 font-bold text-sm">
            <span class="text-base">🚌</span> 서울 버스 & 지하철
          </div>
          <span id="cb-transit-badge" class="px-2 py-0.5 text-[11px] font-bold rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            CLOSED (정상)
          </span>
        </div>
        <div class="space-y-1.5 text-xs">
          <div class="flex justify-between text-slate-400">
            <span>지하철 서킷 상태:</span>
            <span class="text-emerald-400 font-mono font-bold" id="cb-subway-state">CLOSED</span>
          </div>
          <div class="flex justify-between text-slate-400">
            <span>버스 서킷 상태:</span>
            <span class="text-emerald-400 font-mono font-bold" id="cb-bus-state">CLOSED</span>
          </div>
          <div class="flex justify-between text-slate-400">
            <span>지하철 환승 실측 쌍:</span>
            <span class="text-slate-200 font-semibold">119개 쌍 검증</span>
          </div>
        </div>
      </div>

      <!-- Card 3: 서울 따릉이 & 서킷브레이커 -->
      <div class="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between shadow-sm">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2 text-teal-400 font-bold text-sm">
            <span class="text-base">🚲</span> 서울시 따릉이 실시간
          </div>
          <span id="cb-bike-badge" class="px-2 py-0.5 text-[11px] font-bold rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            CLOSED (정상)
          </span>
        </div>
        <div class="space-y-1.5 text-xs">
          <div class="flex justify-between text-slate-400">
            <span>서킷 상태:</span>
            <span class="text-teal-400 font-mono font-bold" id="cb-bike-state">CLOSED</span>
          </div>
          <div class="flex justify-between text-slate-400">
            <span>성공 / 폴백 누적:</span>
            <span class="text-slate-200 font-mono" id="cb-bike-totals">0 / 0</span>
          </div>
          <div class="flex justify-between text-slate-400">
            <span>실시간 대여소 수신:</span>
            <span class="text-slate-200 font-semibold">정상 (반경 800m)</span>
          </div>
        </div>
      </div>

      <!-- Card 4: AI ONNX 엔진 & 시계열 캐시 -->
      <div class="bg-slate-900/70 border border-slate-800 rounded-2xl p-4 flex flex-col justify-between shadow-sm">
        <div class="flex items-center justify-between mb-3">
          <div class="flex items-center gap-2 text-purple-400 font-bold text-sm">
            <span class="text-base">🧠</span> AI ONNX & 시계열 캐시
          </div>
          <span id="model-status-badge" class="px-2 py-0.5 text-[11px] font-bold rounded-md bg-purple-500/10 text-purple-400 border border-purple-500/20">
            32차원 Verified
          </span>
        </div>
        <div class="space-y-1.5 text-xs">
          <div class="flex justify-between text-slate-400">
            <span>모델 로드 현황:</span>
            <span class="text-emerald-400 font-semibold font-mono" id="models-loaded-text">3종 완료</span>
          </div>
          <div class="flex justify-between items-center text-slate-400">
            <span>캐시 레코드 / 용량:</span>
            <span class="text-slate-200 font-mono" id="cache-stats-text">0건 (0 KB)</span>
          </div>
          <div class="pt-1 flex justify-end">
            <button onclick="clearCache()" class="px-2.5 py-1 text-[11px] font-bold rounded bg-slate-800 hover:bg-rose-950 hover:text-rose-400 hover:border-rose-800 text-slate-300 border border-slate-700 transition-all flex items-center gap-1">
              <span>🗑️ 캐시 비우기</span>
            </button>
          </div>
        </div>
      </div>

    </div>

    <!-- Live Log Terminal Section -->
    <div class="bg-slate-900/90 border border-slate-800 rounded-2xl flex flex-col shadow-xl overflow-hidden">
      
      <!-- Terminal Controls Bar -->
      <div class="px-5 py-3.5 bg-slate-900 border-b border-slate-800 flex flex-wrap items-center justify-between gap-3">
        <div class="flex items-center gap-3">
          <div class="flex items-center gap-1.5">
            <span class="w-3 h-3 rounded-full bg-rose-500/80 inline-block"></span>
            <span class="w-3 h-3 rounded-full bg-amber-500/80 inline-block"></span>
            <span class="w-3 h-3 rounded-full bg-emerald-500/80 inline-block"></span>
          </div>
          <span class="text-xs font-mono font-bold text-slate-300 tracking-wide flex items-center gap-2">
            <span>SERVER LOG CONSOLE</span>
            <span class="text-[11px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700/60 font-normal" id="log-count-badge">0건 캡처</span>
          </span>
        </div>

        <!-- Filter & Control Buttons -->
        <div class="flex flex-wrap items-center gap-2 text-xs">
          
          <!-- Auto Stream Toggle -->
          <button id="toggle-stream-btn" onclick="toggleStreaming()" class="px-2.5 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-semibold flex items-center gap-1.5 hover:bg-emerald-500/20 transition-colors">
            <span class="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
            <span id="stream-btn-label">스트리밍 중 (1.5s)</span>
          </button>

          <!-- Auto Scroll Toggle -->
          <button id="toggle-autoscroll-btn" onclick="toggleAutoScroll()" class="px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 font-semibold transition-colors">
            스크롤 고정: <span id="autoscroll-status" class="text-emerald-400">ON</span>
          </button>

          <!-- Level Filter -->
          <select id="log-level-filter" onchange="filterLogs()" class="bg-slate-800 text-slate-200 border border-slate-700 rounded-lg px-2.5 py-1.5 font-mono text-xs focus:ring-1 focus:ring-emerald-500 focus:outline-none">
            <option value="ALL">전체 레벨 (ALL)</option>
            <option value="INFO">INFO 만</option>
            <option value="WARN">WARN / ERROR 만</option>
            <option value="ERROR">ERROR 만</option>
          </select>

          <!-- Domain Filter -->
          <select id="log-domain-filter" onchange="filterLogs()" class="bg-slate-800 text-slate-200 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs focus:ring-1 focus:ring-emerald-500 focus:outline-none">
            <option value="전체">모든 도메인</option>
            <option value="기상청">기상청</option>
            <option value="지하철">지하철</option>
            <option value="버스">버스</option>
            <option value="따릉이">따릉이</option>
            <option value="LangGraph">LangGraph</option>
            <option value="AI추론">AI추론</option>
            <option value="서킷브레이커">서킷브레이커</option>
            <option value="HTTP">HTTP</option>
          </select>

          <!-- Search Input -->
          <div class="relative">
            <input type="text" id="log-search-input" onkeyup="filterLogs()" placeholder="로그 메시지 검색..." class="bg-slate-950 border border-slate-700 text-slate-200 placeholder-slate-500 rounded-lg pl-7 pr-2.5 py-1.5 text-xs w-44 focus:w-56 transition-all focus:outline-none focus:ring-1 focus:ring-emerald-500">
            <svg class="w-3.5 h-3.5 text-slate-500 absolute left-2 top-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg>
          </div>

          <!-- Log Actions -->
          <button onclick="downloadLogs()" class="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors" title="로그 다운로드 (.txt)">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
          </button>
          <button onclick="clearLogs()" class="p-1.5 rounded-lg bg-slate-800 hover:bg-rose-950 hover:text-rose-400 text-slate-400 border border-slate-700 transition-colors" title="화면 로그 지우기">
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"></path></svg>
          </button>

        </div>
      </div>

      <!-- Log Terminal Body -->
      <div id="log-terminal" class="h-[520px] p-4 font-mono text-xs overflow-y-auto space-y-1 bg-slate-950 text-slate-300 leading-relaxed">
        <div class="text-slate-600 italic">서버 실시간 로그 버퍼를 수신 중입니다...</div>
      </div>

      <!-- Terminal Footer -->
      <div class="px-5 py-2.5 bg-slate-900 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-500 font-mono">
        <div>단축키: <kbd class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">Space</kbd> 일시정지/재개</div>
        <div id="last-updated-text">마지막 갱신: 대기 중</div>
      </div>

    </div>

  </main>

  <!-- Script Logic -->
  <script>
    let isStreaming = true;
    let autoScroll = true;
    let streamInterval = null;
    let allLogs = [];
    let lastSeq = 0;

    // 도메인별 뱃지 스타일 맵
    const domainStyles = {
      '기상청': 'bg-sky-500/15 text-sky-400 border-sky-500/30',
      '지하철': 'bg-amber-500/15 text-amber-400 border-amber-500/30',
      '버스': 'bg-blue-500/15 text-blue-400 border-blue-500/30',
      '따릉이': 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30',
      'LangGraph': 'bg-purple-500/15 text-purple-400 border-purple-500/30',
      'AI추론': 'bg-fuchsia-500/15 text-fuchsia-400 border-fuchsia-500/30',
      '서킷브레이커': 'bg-rose-500/15 text-rose-400 border-rose-500/30',
      '캐시': 'bg-indigo-500/15 text-indigo-400 border-indigo-500/30',
      'HTTP': 'bg-slate-500/15 text-slate-400 border-slate-500/30',
      '시스템': 'bg-slate-700/20 text-slate-400 border-slate-700/40'
    };

    // 레벨별 텍스트 색상
    const levelColors = {
      'INFO': 'text-slate-300',
      'WARNING': 'text-amber-400 font-medium',
      'ERROR': 'text-rose-400 font-bold',
      'DEBUG': 'text-slate-500'
    };

    async function fetchSystemStatus() {
      const refreshIcon = document.getElementById('refresh-icon');
      if (refreshIcon) refreshIcon.classList.add('animate-spin');

      try {
        const res = await fetch('/api/v1/admin/status');
        if (!res.ok) throw new Error('Status fetch failed');
        const data = await res.json();

        // Uptime
        document.getElementById('server-uptime').textContent = `Uptime: ${data.uptime}`;

        // Circuit Breakers
        const cb = data.circuit_breakers || {};
        updateCircuitBadge('cb-kma-badge', cb.kma_weather);
        document.getElementById('cb-kma-failures').textContent = `${cb.kma_weather?.failure_count || 0}회`;
        document.getElementById('cb-kma-totals').textContent = `${cb.kma_weather?.total_success || 0} / ${cb.kma_weather?.total_fallback || 0}`;

        const subState = cb.seoul_subway?.state || 'CLOSED';
        const busState = cb.seoul_bus?.state || 'CLOSED';
        document.getElementById('cb-subway-state').textContent = subState;
        document.getElementById('cb-bus-state').textContent = busState;
        updateCircuitBadge('cb-transit-badge', (subState === 'OPEN' || busState === 'OPEN') ? 'OPEN' : 'CLOSED');

        const bikeState = cb.seoul_bike?.state || 'CLOSED';
        document.getElementById('cb-bike-state').textContent = bikeState;
        document.getElementById('cb-bike-totals').textContent = `${cb.seoul_bike?.total_success || 0} / ${cb.seoul_bike?.total_fallback || 0}`;
        updateCircuitBadge('cb-bike-badge', bikeState);

        // Cache Stats
        const cs = data.cache_stats || {};
        document.getElementById('cache-stats-text').textContent = `${cs.count || 0}건 (${cs.size_kb || 0} KB)`;

      } catch (err) {
        console.error('System status error:', err);
      } finally {
        if (refreshIcon) setTimeout(() => refreshIcon.classList.remove('animate-spin'), 400);
      }
    }

    function updateCircuitBadge(elementId, stateOrObj) {
      const el = document.getElementById(elementId);
      if (!el) return;
      const state = typeof stateOrObj === 'string' ? stateOrObj : (stateOrObj?.state || 'CLOSED');
      if (state === 'OPEN') {
        el.className = 'px-2 py-0.5 text-[11px] font-bold rounded-md bg-rose-500/10 text-rose-400 border border-rose-500/20';
        el.textContent = 'OPEN (차단/폴백)';
      } else if (state === 'HALF_OPEN') {
        el.className = 'px-2 py-0.5 text-[11px] font-bold rounded-md bg-amber-500/10 text-amber-400 border border-amber-500/20';
        el.textContent = 'HALF_OPEN (복구시도)';
      } else {
        el.className = 'px-2 py-0.5 text-[11px] font-bold rounded-md bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
        el.textContent = 'CLOSED (정상)';
      }
    }

    async function fetchLogs() {
      try {
        const url = lastSeq > 0 ? `/api/v1/admin/logs?since_id=${lastSeq}&limit=300` : '/api/v1/admin/logs?limit=300';
        const res = await fetch(url);
        if (!res.ok) return;
        const newLogs = await res.json();

        if (Array.isArray(newLogs) && newLogs.length > 0) {
          allLogs = allLogs.concat(newLogs);
          if (allLogs.length > 2000) allLogs = allLogs.slice(-2000);
          lastSeq = newLogs[newLogs.length - 1].id;
          renderLogs();
        }

        document.getElementById('last-updated-text').textContent = `마지막 갱신: ${new Date().toLocaleTimeString()}`;
        document.getElementById('log-count-badge').textContent = `${allLogs.length}건 캡처`;
      } catch (err) {
        console.error('Log fetch error:', err);
      }
    }

    function renderLogs() {
      const terminal = document.getElementById('log-terminal');
      const levelFilter = document.getElementById('log-level-filter').value;
      const domainFilter = document.getElementById('log-domain-filter').value;
      const query = document.getElementById('log-search-input').value.toLowerCase().trim();

      const filtered = allLogs.filter(log => {
        if (levelFilter === 'INFO' && log.level !== 'INFO') return false;
        if (levelFilter === 'WARN' && log.level !== 'WARNING' && log.level !== 'ERROR') return false;
        if (levelFilter === 'ERROR' && log.level !== 'ERROR') return false;
        if (domainFilter !== '전체' && log.domain !== domainFilter) return false;
        if (query && !log.message.toLowerCase().includes(query) && !log.logger.toLowerCase().includes(query)) return false;
        return true;
      });

      if (filtered.length === 0) {
        terminal.innerHTML = '<div class="text-slate-600 italic py-4 text-center">조건에 일치하는 로그가 없습니다.</div>';
        return;
      }

      const html = filtered.map(log => {
        const domBadge = domainStyles[log.domain] || domainStyles['시스템'];
        const lvlColor = levelColors[log.level] || 'text-slate-300';
        const safeMsg = escapeHtml(log.message);

        return `
          <div class="log-line py-0.5 px-1.5 rounded flex items-start gap-2.5 transition-colors">
            <span class="text-slate-500 shrink-0 select-none">${log.time}</span>
            <span class="px-1.5 py-0.2 rounded text-[10px] font-bold border shrink-0 ${domBadge}">[${log.domain}]</span>
            <span class="font-bold shrink-0 ${log.level === 'ERROR' ? 'text-rose-400' : (log.level === 'WARNING' ? 'text-amber-400' : 'text-slate-400')}">${log.level.padEnd(5)}</span>
            <span class="${lvlColor} break-all flex-1">${safeMsg}</span>
          </div>
        `;
      }).join('');

      terminal.innerHTML = html;

      if (autoScroll) {
        terminal.scrollTop = terminal.scrollHeight;
      }
    }

    function filterLogs() {
      renderLogs();
    }

    function toggleStreaming() {
      isStreaming = !isStreaming;
      const btn = document.getElementById('toggle-stream-btn');
      const label = document.getElementById('stream-btn-label');
      if (isStreaming) {
        btn.className = 'px-2.5 py-1.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 font-semibold flex items-center gap-1.5 hover:bg-emerald-500/20 transition-colors';
        label.textContent = '스트리밍 중 (1.5s)';
        startStreaming();
      } else {
        btn.className = 'px-2.5 py-1.5 rounded-lg bg-slate-800 text-slate-400 border border-slate-700 font-semibold flex items-center gap-1.5 hover:bg-slate-700 transition-colors';
        label.textContent = '일시 정지됨';
        stopStreaming();
      }
    }

    function toggleAutoScroll() {
      autoScroll = !autoScroll;
      const status = document.getElementById('autoscroll-status');
      status.textContent = autoScroll ? 'ON' : 'OFF';
      status.className = autoScroll ? 'text-emerald-400' : 'text-slate-500';
    }

    function startStreaming() {
      if (streamInterval) clearInterval(streamInterval);
      streamInterval = setInterval(() => {
        fetchLogs();
      }, 1500);
    }

    function stopStreaming() {
      if (streamInterval) {
        clearInterval(streamInterval);
        streamInterval = null;
      }
    }

    function clearLogs() {
      allLogs = [];
      renderLogs();
    }

    async function clearCache() {
      if (!confirm('SQLite 시계열 캐시(timeseries_cache.db)를 모두 비우시겠습니까?\\n비운 후 실시간 외부 API가 강제 재호출됩니다.')) return;
      try {
        const res = await fetch('/api/v1/admin/cache/clear', { method: 'POST' });
        const data = await res.json();
        alert(data.message || '캐시가 비워졌습니다.');
        fetchSystemStatus();
      } catch (err) {
        alert('캐시 비우기 실패: ' + err.message);
      }
    }

    function downloadLogs() {
      const text = allLogs.map(l => `[${l.timestamp}] [${l.level}] [${l.domain}] [${l.logger}] ${l.message}`).join('\\n');
      const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `weather-transit-logs-${new Date().toISOString().slice(0,10)}.txt`;
      a.click();
      URL.revokeObjectURL(url);
    }

    function escapeHtml(str) {
      return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // 키보드 Spacebar로 일시정지/재개
    window.addEventListener('keydown', (e) => {
      if (e.code === 'Space' && e.target === document.body) {
        e.preventDefault();
        toggleStreaming();
      }
    });

    // 초기 실행
    fetchSystemStatus();
    fetchLogs();
    startStreaming();
    setInterval(fetchSystemStatus, 10000); // 10초마다 시스템 상태 자동 갱신
  </script>
</body>
</html>
"""
    return html_content
