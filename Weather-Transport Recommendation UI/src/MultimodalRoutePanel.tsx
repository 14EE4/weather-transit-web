import React, { useEffect, useState } from 'react'
import { SUBWAY_STATIONS } from './subwayData'
import { MultimodalSegment, TransitRouteResult } from './subwayGraph'

const VALID_STATION_NAMES = new Set(
  SUBWAY_STATIONS.map(st => st.name)
)

const MULTIMODAL_MEMORY_CACHE = new Map<string, MultimodalSearchResponse>()
const LOCAL_STORAGE_CACHE_KEY = 'weather_transit_multimodal_cache_v3'

function getCachedMultimodalResult(key: string): MultimodalSearchResponse | null {
  if (!key) return null
  const mem = MULTIMODAL_MEMORY_CACHE.get(key)
  if (mem) return mem
  if (typeof window !== 'undefined') {
    try {
      const raw = localStorage.getItem(LOCAL_STORAGE_CACHE_KEY)
      if (raw) {
        const parsed = JSON.parse(raw) as Record<string, MultimodalSearchResponse>
        if (parsed && parsed[key]) {
          MULTIMODAL_MEMORY_CACHE.set(key, parsed[key])
          return parsed[key]
        }
      }
    } catch {}
  }
  return null
}

function setCachedMultimodalResult(key: string, value: MultimodalSearchResponse): void {
  if (!key) return
  MULTIMODAL_MEMORY_CACHE.set(key, value)
  if (typeof window !== 'undefined') {
    try {
      const raw = localStorage.getItem(LOCAL_STORAGE_CACHE_KEY)
      const parsed: Record<string, MultimodalSearchResponse> = raw ? JSON.parse(raw) : {}
      parsed[key] = value
      // 최근 12개 검색 기록까지만 유지 (용량 관리)
      const keys = Object.keys(parsed)
      if (keys.length > 12) {
        delete parsed[keys[0]]
      }
      localStorage.setItem(LOCAL_STORAGE_CACHE_KEY, JSON.stringify(parsed))
    } catch {}
  }
}

export interface MultimodalBriefing {
  headline: string
  summary: string
  weather_advice: string
  recommended_route_id: string
  model: string
  source: string
  bullets: string[]
}

export interface LangGraphTraceStep {
  step: number
  node: string
  status: string
  decision: string
  detail: string
  latency_ms: number
}

export interface MultimodalRouteCandidate extends TransitRouteResult {
  id: string
  category: string
  title: string
  badge: string
  badge_color: string
  is_ai_recommended: boolean
  total_minutes: number
  total_fare_krw: number
  total_distance_km: number
  transfer_count: number
  outdoor_walk_minutes: number
  crowd_percent: number
  crowd_label: string
  crowd_color: string
  comfort_score: number
  modes_used: string[]
  highlights: string[]
  segments: MultimodalSegment[]
  geometry: [number, number][]
}

export interface MultimodalSearchResponse {
  status: string
  engine: string
  langgraph_native: boolean
  latency_ms: number
  district: string
  hour: number
  weather_gate: 'CLEAR_MULTIMODAL' | 'RAIN_SAFE_ONLY' | string
  weather_context: {
    temp: number
    rain: number
    humidity: number
    wind: number
    pty_desc?: string
    sky_desc?: string
    bike_enabled: boolean
    weather_gate_reason: string
    source?: string
  }
  ai_congestion: {
    subway_crowd: number
    bus_crowd: number
    bike_crowd: number
    subway_score: number
    bus_score: number
    bike_score: number
  }
  ai_briefing: MultimodalBriefing
  langgraph_trace: LangGraphTraceStep[]
  routes: MultimodalRouteCandidate[]
}

interface MultimodalRoutePanelProps {
  apiBaseUrl: string
  fromStation: string
  toStation: string
  district: string
  selectedHour: number
  temp: number
  rain: number
  humidity: number
  wind: number
  onSelectRouteForMap: (route: TransitRouteResult) => void
  compact?: boolean
}

const MODE_ICON: Record<string, string> = {
  walk: '🚶',
  bike: '🚲',
  bus: '🚌',
  subway: '🚇',
}

const MODE_NAME: Record<string, string> = {
  walk: '도보',
  bike: '따릉이',
  bus: '버스',
  subway: '지하철',
}

export default function MultimodalRoutePanel({
  apiBaseUrl,
  fromStation,
  toStation,
  district,
  selectedHour,
  temp,
  rain,
  humidity,
  wind,
  onSelectRouteForMap,
  compact = false,
}: MultimodalRoutePanelProps) {
  const cleanFrom = (fromStation || '').trim()
  const cleanTo = (toStation || '').trim()
  const cleanDistrict = (district || '').split(' ')[0] || '강남구'
  const hasValidRouteInput = Boolean(
    cleanFrom &&
      cleanTo &&
      cleanFrom !== cleanTo &&
      VALID_STATION_NAMES.has(cleanFrom) &&
      VALID_STATION_NAMES.has(cleanTo)
  )
  const cacheKey = hasValidRouteInput
    ? `${cleanFrom}|${cleanTo}|${cleanDistrict}|${selectedHour}|${Math.round(temp)}|${Math.round(rain * 10) / 10}`
    : ''

  const [data, setData] = useState<MultimodalSearchResponse | null>(() =>
    cacheKey ? getCachedMultimodalResult(cacheKey) : null
  )
  const [loading, setLoading] = useState<boolean>(false)
  const [selectedIdx, setSelectedIdx] = useState<number>(0)
  const [showTrace, setShowTrace] = useState<boolean>(false)

  useEffect(() => {
    if (!hasValidRouteInput) {
      setData(null)
      setLoading(false)
      return
    }

    const cached = getCachedMultimodalResult(cacheKey)
    if (cached) {
      setData(cached)
      setLoading(false)
      return
    }

    let cancelled = false
    const timer = setTimeout(async () => {
      setLoading(true)
      const requestPayload = {
        from_station: cleanFrom,
        to_station: cleanTo,
        district: cleanDistrict,
        hour: selectedHour,
        weather: {
          temp,
          rain,
          humidity,
          wind,
        },
      }
      console.log(
        `%c[LangGraph × FactChat] 🚀 멀티모달 경로 탐색 시작: ${cleanFrom} ➔ ${cleanTo} (${selectedHour}:00, ${temp}°C, 강수 ${rain}mm)`,
        'color: #38BDF8; font-weight: bold;',
        requestPayload
      )
      try {
        const res = await fetch(`${apiBaseUrl}/api/v1/routes/multimodal-search`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(requestPayload),
        })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const json: MultimodalSearchResponse = await res.json()
        if (!cancelled && json.status === 'success') {
          setCachedMultimodalResult(cacheKey, json)
          setData(json)
          setSelectedIdx(0)
          console.groupCollapsed(
            `%c[LangGraph × FactChat] 🧠 멀티모달 경로 탐색 완료: ${cleanFrom} ➔ ${cleanTo} (${json.latency_ms}ms · ${json.weather_gate})`,
            'color: #34D399; font-weight: bold;'
          )
          console.log('🌦️ 기상 게이트 판정:', json.weather_gate, json.weather_context)
          console.log('📊 32차원 ONNX 혼잡도:', json.ai_congestion)
          console.log('🤖 FactChat LLM 브리핑:', json.ai_briefing)
          if (json.langgraph_trace) {
            console.log('🔗 LangGraph 5단계 노드 트레이스:')
            console.table(json.langgraph_trace)
          }
          if (json.routes) {
            console.log('🗺️ 멀티모달 추천 경로 후보 3종:')
            console.table(
              json.routes.map(r => ({
                순위: r.badge,
                경로명: r.title,
                소요시간_분: r.total_minutes,
                요금_원: r.total_fare_krw,
                거리_km: r.total_distance_km,
                환승횟수: r.transfer_count,
                혼잡도: `${r.crowd_percent}% (${r.crowd_label})`,
                구간요약: r.segments.map(s => `${s.from_name}➔${s.to_name}`).join(' | '),
              }))
            )
          }
          console.groupEnd()
        }
      } catch (err) {
        console.warn('[MultimodalEngine] 경로 탐색 조회 폴백:', err)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }, 220)

    return () => {
      cancelled = true
      clearTimeout(timer)
    }
  }, [apiBaseUrl, cacheKey, cleanFrom, cleanTo, cleanDistrict, hasValidRouteInput, selectedHour, temp, rain, humidity, wind])

  if (!hasValidRouteInput) {
    return (
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.92), rgba(22, 32, 64, 0.92))',
          border: '1px dashed rgba(56, 189, 248, 0.3)',
          borderRadius: 20,
          padding: compact ? 16 : 20,
          marginBottom: 20,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 14,
          flexWrap: 'wrap',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div
            style={{
              width: 42,
              height: 42,
              borderRadius: 12,
              background: 'rgba(168, 85, 247, 0.15)',
              border: '1px solid rgba(168, 85, 247, 0.35)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 20,
              flexShrink: 0,
            }}
          >
            🧠
          </div>
          <div>
            <div style={{ fontSize: 13.5, fontWeight: 800, color: '#F0F6FF', marginBottom: 3 }}>
              LangGraph × FactChat LLM 멀티모달 통합 경로 탐색 대기 중
            </div>
            <div style={{ fontSize: 11.5, color: 'rgba(255,255,255,0.5)' }}>
              좌측에서 <b>출발지</b>와 <b>도착지</b>를 입력하면 현재 날씨({temp}°C · 강수 {rain}mm)에 맞춘{' '}
              <b>지하철 + 버스 + 따릉이(First-Mile)</b> 복합 경로와 AI 브리핑이 표시됩니다.
            </div>
          </div>
        </div>
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            padding: '4px 10px',
            borderRadius: 999,
            background: rain > 0 ? 'rgba(245, 158, 11, 0.16)' : 'rgba(16, 185, 129, 0.16)',
            color: rain > 0 ? '#FBBF24' : '#34D399',
            fontFamily: 'JetBrains Mono',
          }}
        >
          {rain > 0 ? '🌧️ 우천 안전 게이트 작동 중' : '☀️ 따릉이 First-Mile 활성'}
        </span>
      </div>
    )
  }

  const routes = data?.routes || []
  const selectedRoute = routes[selectedIdx] || routes[0] || null
  const briefing = data?.ai_briefing
  const bikeEnabled = data?.weather_context?.bike_enabled ?? rain <= 0

  return (
    <div style={{ marginBottom: 22 }}>
      {/* ── 0. 경로 탐색 로딩 배너 (탐색 진행 중일 때 눈에 띄게 표시) ── */}
      {loading && (
        <div
          style={{
            background: 'linear-gradient(135deg, rgba(14, 165, 233, 0.16), rgba(168, 85, 247, 0.16))',
            border: '1px solid rgba(56, 189, 248, 0.5)',
            borderRadius: 18,
            padding: '14px 18px',
            marginBottom: 14,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            flexWrap: 'wrap',
            boxShadow: '0 8px 24px rgba(56, 189, 248, 0.18)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div
              style={{
                width: 34,
                height: 34,
                borderRadius: '50%',
                border: '3px solid rgba(56, 189, 248, 0.25)',
                borderTopColor: '#38BDF8',
                animation: 'mmSpin 0.8s linear infinite',
                flexShrink: 0,
              }}
            />
            <div>
              <div style={{ fontSize: 13.5, fontWeight: 800, color: '#F0F6FF', marginBottom: 2 }}>
                ⏳ 경로 탐색 로딩 중... ({cleanFrom} ➔ {cleanTo})
              </div>
              <div style={{ fontSize: 11, color: '#BAE6FD' }}>
                LangGraph 에이전트가 기상 게이트 판정 · 지하철/버스/따릉이 복합 탐색 · FactChat AI 브리핑을 생성하고 있습니다.
              </div>
            </div>
          </div>
          <span
            style={{
              fontSize: 10,
              fontWeight: 800,
              padding: '4px 10px',
              borderRadius: 999,
              background: 'rgba(56, 189, 248, 0.2)',
              color: '#38BDF8',
              fontFamily: 'JetBrains Mono',
            }}
          >
            SEARCHING...
          </span>
          <style>{`
            @keyframes mmSpin {
              from { transform: rotate(0deg); }
              to { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      )}

      {/* ── 1. LangGraph × FactChat LLM 브리핑 헤더 카드 ── */}
      <div
        style={{
          background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(22, 32, 64, 0.96))',
          border: `1px solid ${bikeEnabled ? 'rgba(16, 185, 129, 0.35)' : 'rgba(56, 189, 248, 0.38)'}`,
          borderRadius: 20,
          padding: compact ? 16 : 20,
          marginBottom: 16,
          boxShadow: '0 10px 30px rgba(0, 0, 0, 0.35)',
        }}
      >
        {/* 상단 상태 배지 바 */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: 8,
            marginBottom: 12,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span
              style={{
                fontSize: 10,
                fontWeight: 800,
                padding: '3px 9px',
                borderRadius: 999,
                background: 'rgba(168, 85, 247, 0.18)',
                border: '1px solid rgba(168, 85, 247, 0.4)',
                color: '#C084FC',
                fontFamily: 'JetBrains Mono',
              }}
            >
              ⚡ LangGraph StateGraph
            </span>
            <span
              style={{
                fontSize: 10,
                fontWeight: 800,
                padding: '3px 9px',
                borderRadius: 999,
                background: bikeEnabled ? 'rgba(16, 185, 129, 0.16)' : 'rgba(245, 158, 11, 0.18)',
                border: `1px solid ${bikeEnabled ? 'rgba(16, 185, 129, 0.4)' : 'rgba(245, 158, 11, 0.45)'}`,
                color: bikeEnabled ? '#34D399' : '#FBBF24',
                fontFamily: 'JetBrains Mono',
              }}
            >
              {bikeEnabled
                ? '☀️ CLEAR_MULTIMODAL · 따릉이 First-Mile 활성'
                : '🌧️ RAIN_SAFE_ONLY · 따릉이 자동 차단'}
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {briefing && (
              <span
                style={{
                  fontSize: 10,
                  color: briefing.source === 'FACTCHAT_BAZE_GATEWAY' ? '#38BDF8' : '#94A3B8',
                  fontFamily: 'JetBrains Mono',
                  fontWeight: 700,
                }}
              >
                {briefing.source === 'FACTCHAT_BAZE_GATEWAY'
                  ? `🟢 FactChat Live (${briefing.model})`
                  : `🧠 XAI Engine (${briefing.model})`}
              </span>
            )}
            <button
              onClick={() => setShowTrace(prev => !prev)}
              style={{
                fontSize: 10,
                padding: '2px 8px',
                borderRadius: 6,
                background: 'rgba(255,255,255,0.06)',
                border: '1px solid rgba(255,255,255,0.12)',
                color: 'rgba(255,255,255,0.65)',
                cursor: 'pointer',
                fontFamily: 'JetBrains Mono',
              }}
            >
              {showTrace ? '그래프 트레이스 접기 ▲' : 'LangGraph 노드 보기 ▼'}
            </button>
          </div>
        </div>

        {/* 브리핑 본문 */}
        <div style={{ fontSize: 14, fontWeight: 800, color: '#F0F6FF', marginBottom: 6 }}>
          {briefing?.headline || '🤖 FactChat LLM × LangGraph 멀티모달 경로 브리핑'}
        </div>
        <div
          style={{
            fontSize: 12.5,
            lineHeight: 1.6,
            color: '#E2E8F0',
            background: 'rgba(0, 0, 0, 0.28)',
            borderRadius: 12,
            padding: '10px 14px',
            borderLeft: `3px solid ${bikeEnabled ? '#10B981' : '#38BDF8'}`,
            marginBottom: 10,
          }}
        >
          {loading
            ? '⏳ LangGraph 에이전트가 기상청 예보·32차원 ONNX 혼잡도·실시간 따릉이/열차 데이터를 결합해 최적 멀티모달 경로를 추론 중입니다...'
            : briefing?.summary ||
              '현재 기상 및 혼잡도를 반영하여 지하철·버스·따릉이 복합 경로를 탐색했습니다.'}
        </div>

        {/* 기상 게이트 판정 사유 */}
        {data?.weather_context?.weather_gate_reason && (
          <div style={{ fontSize: 11, color: bikeEnabled ? '#6EE7B7' : '#7DD3FC', display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>🛡️</span>
            <span>{data.weather_context.weather_gate_reason}</span>
          </div>
        )}

        {/* LangGraph 노드 실행 트레이스 (토글) */}
        {showTrace && data?.langgraph_trace && (
          <div
            style={{
              marginTop: 12,
              paddingTop: 12,
              borderTop: '1px solid rgba(255,255,255,0.08)',
              display: 'grid',
              gridTemplateColumns: compact ? '1fr' : 'repeat(2, 1fr)',
              gap: 8,
            }}
          >
            {data.langgraph_trace.map(t => (
              <div
                key={t.step}
                style={{
                  background: 'rgba(255,255,255,0.03)',
                  border: '1px solid rgba(255,255,255,0.08)',
                  borderRadius: 10,
                  padding: '8px 10px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                  <span style={{ fontSize: 10, fontWeight: 800, color: '#C084FC', fontFamily: 'JetBrains Mono' }}>
                    #{t.step} {t.node}
                  </span>
                  <span style={{ fontSize: 9, color: '#34D399', fontFamily: 'JetBrains Mono' }}>
                    {t.latency_ms}ms
                  </span>
                </div>
                <div style={{ fontSize: 10.5, color: 'rgba(255,255,255,0.65)', lineHeight: 1.4 }}>
                  {t.detail}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── 2. 멀티모달 경로 후보 선택 탭 (3종) ── */}
      {routes.length > 0 && (
        <div>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: 10,
            }}
          >
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.45)', fontFamily: 'JetBrains Mono', letterSpacing: '0.05em' }}>
              MULTIMODAL ROUTE CANDIDATES ({cleanFrom} ➔ {cleanTo})
            </div>
            <span style={{ fontSize: 10, color: '#38BDF8', fontFamily: 'JetBrains Mono' }}>
              ⏱️ {selectedHour}시 기상({temp}°C · 강수 {rain}mm) 기준
            </span>
          </div>

          {/* 후보 카드 탭 그리드 */}
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: compact ? '1fr' : `repeat(${Math.min(3, routes.length)}, 1fr)`,
              gap: 10,
              marginBottom: 14,
            }}
          >
            {routes.map((rt, idx) => {
              const isSelected = idx === selectedIdx
              return (
                <div
                  key={rt.id}
                  onClick={() => setSelectedIdx(idx)}
                  style={{
                    cursor: 'pointer',
                    borderRadius: 16,
                    padding: '12px 14px',
                    background: isSelected ? 'rgba(56, 189, 248, 0.13)' : '#162040',
                    border: isSelected
                      ? `1.5px solid ${rt.badge_color || '#38BDF8'}`
                      : '1px solid rgba(255,255,255,0.08)',
                    transition: 'all 0.15s ease',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span
                      style={{
                        fontSize: 9.5,
                        fontWeight: 800,
                        padding: '2px 7px',
                        borderRadius: 999,
                        background: `${rt.badge_color || '#38BDF8'}22`,
                        color: rt.badge_color || '#38BDF8',
                        fontFamily: 'JetBrains Mono',
                      }}
                    >
                      {rt.badge}
                    </span>
                    <span style={{ fontSize: 11 }}>
                      {rt.modes_used.map(m => MODE_ICON[m] || '🚇').join(' + ')}
                    </span>
                  </div>

                  <div style={{ fontSize: 13, fontWeight: 800, color: '#F0F6FF', marginBottom: 6, lineHeight: 1.3 }}>
                    {rt.title}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between' }}>
                    <div>
                      <span style={{ fontSize: 20, fontWeight: 900, color: rt.badge_color || '#38BDF8', fontFamily: 'JetBrains Mono' }}>
                        {rt.total_minutes}
                      </span>
                      <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', marginLeft: 2 }}>분</span>
                    </div>
                    <div style={{ fontSize: 10.5, color: 'rgba(255,255,255,0.55)', fontFamily: 'JetBrains Mono' }}>
                      {rt.total_fare_krw.toLocaleString()}원 · {rt.total_distance_km}km
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          {/* ── 3. 선택된 멀티모달 후보 상세 구간 타임라인 카드 ── */}
          {selectedRoute && (
            <div
              style={{
                background: '#162040',
                border: `1px solid ${selectedRoute.badge_color || '#38BDF8'}44`,
                borderRadius: 20,
                padding: compact ? 16 : 20,
              }}
            >
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexWrap: 'wrap',
                  gap: 10,
                  marginBottom: 14,
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <span style={{ fontSize: 16, fontWeight: 800, color: '#F0F6FF' }}>
                      {selectedRoute.title}
                    </span>
                    {selectedRoute.is_ai_recommended && (
                      <span
                        style={{
                          fontSize: 10,
                          padding: '2px 8px',
                          borderRadius: 999,
                          background: 'rgba(16, 185, 129, 0.2)',
                          color: '#34D399',
                          fontWeight: 800,
                        }}
                      >
                        ★ AI 최적 추천
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 11.5, color: 'rgba(255,255,255,0.5)' }}>
                    총 {selectedRoute.total_minutes}분 소요 · {selectedRoute.total_distance_km}km · 요금{' '}
                    {selectedRoute.total_fare_krw.toLocaleString()}원 · 환승 {selectedRoute.transfer_count}회 · 혼잡도{' '}
                    <span style={{ color: selectedRoute.crowd_color, fontWeight: 700 }}>
                      {selectedRoute.crowd_label}({selectedRoute.crowd_percent}%)
                    </span>
                  </div>
                </div>

                <button
                  onClick={() => onSelectRouteForMap(selectedRoute)}
                  style={{
                    padding: '9px 16px',
                    borderRadius: 12,
                    cursor: 'pointer',
                    background: 'linear-gradient(135deg, #38BDF8, #10B981)',
                    color: '#0A1628',
                    fontSize: 12.5,
                    fontWeight: 800,
                    border: 'none',
                    boxShadow: '0 4px 16px rgba(56, 189, 248, 0.3)',
                  }}
                >
                  🗺️ 이 멀티모달 경로 지도 보기
                </button>
              </div>

              {/* 구간 비율 컬러 바 */}
              <div
                style={{
                  display: 'flex',
                  height: 10,
                  borderRadius: 999,
                  overflow: 'hidden',
                  background: 'rgba(255,255,255,0.06)',
                  marginBottom: 16,
                  gap: 2,
                }}
              >
                {selectedRoute.segments.map((seg, i) => {
                  const weight = Math.max(8, seg.minutes)
                  return (
                    <div
                      key={i}
                      title={`${seg.label}: ${seg.minutes}분`}
                      style={{
                        flex: weight,
                        background: seg.color || '#38BDF8',
                        borderRadius: 4,
                      }}
                    />
                  )
                })}
              </div>

              {/* 구간별 스텝 리스트 */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 14 }}>
                {selectedRoute.segments.map((seg, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      gap: 12,
                      padding: '10px 14px',
                      borderRadius: 12,
                      background: 'rgba(0, 0, 0, 0.25)',
                      borderLeft: `4px solid ${seg.color || '#38BDF8'}`,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0, flex: 1 }}>
                      <span style={{ fontSize: 18 }}>{MODE_ICON[seg.mode] || '🚇'}</span>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                          <span
                            style={{
                              fontSize: 11,
                              fontWeight: 800,
                              color: seg.color || '#38BDF8',
                              fontFamily: 'JetBrains Mono',
                            }}
                          >
                            [{MODE_NAME[seg.mode] || seg.mode}] {seg.label}
                          </span>
                          {seg.live_badge && (
                            <span
                              style={{
                                fontSize: 9.5,
                                padding: '1px 6px',
                                borderRadius: 4,
                                background: 'rgba(255,255,255,0.08)',
                                color: '#FCD34D',
                                fontFamily: 'JetBrains Mono',
                                fontWeight: 700,
                              }}
                            >
                              {seg.live_badge}
                            </span>
                          )}
                        </div>
                        <div
                          style={{
                            fontSize: 12,
                            color: '#E2E8F0',
                            marginTop: 2,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {seg.detail}
                        </div>
                      </div>
                    </div>

                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <div style={{ fontSize: 13, fontWeight: 800, color: '#F0F6FF', fontFamily: 'JetBrains Mono' }}>
                        {seg.minutes}분
                      </div>
                      <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono' }}>
                        {seg.distance_km}km
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* 핵심 추천 사유 태그 */}
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {selectedRoute.highlights.map(hl => (
                  <span
                    key={hl}
                    style={{
                      fontSize: 11,
                      padding: '4px 10px',
                      borderRadius: 999,
                      background: 'rgba(56, 189, 248, 0.09)',
                      border: '1px solid rgba(56, 189, 248, 0.22)',
                      color: '#BAE6FD',
                    }}
                  >
                    {hl}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
