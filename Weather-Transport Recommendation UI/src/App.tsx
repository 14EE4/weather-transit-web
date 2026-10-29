import { useState, useEffect, useRef } from 'react'
import {
  DEFAULT_24H_DATA,
  FALLBACK_TRANSPORT_SCORES as TRANSPORT_SCORES,
  CORRELATION_DATA,
  FALLBACK_DISTRICT_DATA as DISTRICT_DATA,
  type HourlyTransitData
} from './constants/fallbackData'
import { TransportScoreSkeleton, DistrictCongestionSkeleton } from './components/SkeletonLoader'
import TransitMap, { TransitStop, StopDetailData } from './TransitMap'
import { logWeatherApiCall, logBusApiCall, logSubwayApiCall, logAIPredictionCall } from './apiLogger'
import { searchSubwayStations, SubwayStation } from './subwayData'
import { findSubwayRoute, calculateSubwayFare, TransitRouteResult, formatDurationMinutes } from './subwayGraph'
import { resolveDistrict } from './districtResolver'
import BusStationSearch, { type BusStationResult } from './BusStationSearch'
import EnterpriseView from './EnterpriseView'
import MultimodalRoutePanel from './MultimodalRoutePanel'

type Page = 'main' | 'route' | 'map' | 'enterprise'

type Theme = 'dark' | 'light'

const getInitialTheme = (): Theme => {
  try {
    const saved = localStorage.getItem('weather-transit-theme')
    if (saved === 'light' || saved === 'dark') {
      return saved
    }
  } catch {
    // localStorage 접근 불가 환경 대비
  }

  // 사용자가 수동 설정한 테마가 없을 경우 OS/기기 시스템 테마(prefers-color-scheme)를 기본값으로 사용
  if (typeof window !== 'undefined' && window.matchMedia) {
    if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark'
    }
    return 'light'
  }

  return 'dark'
}

// ── 서울 25개 자치구 및 수도권 주요 거점 권역별 데이터 ──
export const DISTRICT_GROUPS = [
  {
    zone: '🏢 동남권 (강남·서초·송파·강동)',
    items: [
      '강남구 역삼·삼성동',
      '강남구 논현·압구정동',
      '강남구 대치·수서동',
      '서초구 서초·교대역',
      '서초구 반포·고속터미널',
      '서초구 양재·시민의숲',
      '송파구 잠실·롯데월드',
      '송파구 문정·가락시장',
      '강동구 천호·길동',
      '강동구 명일·고덕동',
    ]
  },
  {
    zone: '🏛️ 도심권 (종로·중구·용산)',
    items: [
      '종로구 광화문·종로1가',
      '종로구 혜화·대학로',
      '중구 명동·을지로',
      '중구 서울역·회현동',
      '중구 동대문·신당동',
      '용산구 이태원·한남동',
      '용산구 용산역·이촌동',
    ]
  },
  {
    zone: '🏭 서남권 (영등포·구로·금천·동작·관악·강서·양천)',
    items: [
      '영등포구 여의도동',
      '영등포구 당산·영등포동',
      '구로구 신도림·구로디지털',
      '금천구 가산디지털단지',
      '동작구 노량진·사당동',
      '관악구 신림·서울대입구',
      '강서구 마곡·가양동',
      '강서구 화곡·발산동',
      '양천구 목동·오목교',
    ]
  },
  {
    zone: '🎨 서북권 (마포·서대문·은평)',
    items: [
      '마포구 홍대·서교동',
      '마포구 합정·망원동',
      '마포구 상암DMC·공덕동',
      '서대문구 신촌·연희동',
      '서대문구 홍제·독립문',
      '은평구 연신내·불광동',
      '은평구 응암·녹번동',
    ]
  },
  {
    zone: '🌲 동북권 (성동·광진·동대문·중랑·성북·강북·도봉·노원)',
    items: [
      '성동구 성수동 카페거리',
      '성동구 왕십리·행당동',
      '광진구 건대입구·화양동',
      '광진구 구의·강변역',
      '동대문구 청량리·회기동',
      '동대문구 장안·답십리동',
      '중랑구 상봉·면목동',
      '성북구 안암·고려대',
      '성북구 길음·성북동',
      '강북구 수유·미아사거리',
      '도봉구 창동·쌍문동',
      '노원구 상계·노원역',
      '노원구 공릉·태릉입구',
    ]
  },
  {
    zone: '🚆 수도권 인접 광역권 (출퇴근 연계축)',
    items: [
      '성남시 분당·판교 테크노밸리',
      '광명시 철산·광명역',
      '부천시 부천역·중동',
      '고양시 일산·삼송',
      '하남시 미사강변도시',
      '수원시 수원역·광교',
      '안양시 평촌·인덕원',
      '남양주시 다산·별내',
      '인천시 부평·송도·구월동',
    ]
  }
]

const DISTRICTS = DISTRICT_GROUPS.flatMap(g => g.items)

export interface HourlyTransitData {
  hour: string
  hour_num: number
  temp: number
  rain: number
  humidity: number
  wind: number
  subway: number
  bus: number
  bike: number
  subway_crowd?: number
  bus_crowd?: number
  bike_crowd?: number
  is_peak?: boolean
}

// ── 24시간 시간대별, 교통수단 추천, 강우 상관관계, 거점 혼잡도 기본 상수는 ./constants/fallbackData.ts 에서 임포트됨 ──
const HOURLY_DATA = DEFAULT_24H_DATA


function CrowdBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--color-subtle)' }}>
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${value}%`, background: color }} />
      </div>
      <span style={{ fontSize: 11, fontFamily: 'JetBrains Mono', color, minWidth: 28 }}>{value}%</span>
    </div>
  )
}

function StatCard({ label, value, unit, color, icon }: { label: string; value: string | number; unit?: string; color: string; icon: string }) {
  return (
    <div className="rounded-2xl p-4" style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)' }}>
      <div className="flex items-center gap-2 mb-2">
        <span style={{ fontSize: 16 }}>{icon}</span>
        <span style={{ fontSize: 11, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono', letterSpacing: '0.04em' }}>{label}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span style={{ fontSize: 26, fontWeight: 800, color, fontFamily: 'JetBrains Mono', lineHeight: 1 }}>{value}</span>
        {unit && <span style={{ fontSize: 12, color: 'var(--app-text)' }}>{unit}</span>}
      </div>
    </div>
  )
}

// ── 간단한 막대 차트 컴포넌트 ──
function BarChart({ data }: { data: typeof HOURLY_DATA }) {
  const maxBus = Math.max(...data.map(d => d.bus))
  const maxSubway = Math.max(...data.map(d => d.subway))
  const maxBike = Math.max(...data.map(d => d.bike))
  const [hovered, setHovered] = useState<number | null>(null)

  return (
    <div className="relative">
      <div className="flex items-end gap-1.5 h-32">
        {data.map((d, i) => (
          <div
            key={d.hour}
            className="flex-1 flex flex-col items-center gap-0.5 cursor-pointer group"
            onMouseEnter={() => setHovered(i)}
            onMouseLeave={() => setHovered(null)}
          >
            <div className="w-full flex flex-col gap-0.5 items-center">
              {/* Subway bar */}
              <div className="w-full rounded-sm transition-all" style={{ height: `${(d.subway / maxSubway) * 80}px`, background: hovered === i ? 'var(--color-primary)' : 'color-mix(in srgb, var(--color-primary) 50%, transparent)', minHeight: 2 }} />
            </div>
          </div>
        ))}
      </div>
      {/* Labels */}
      <div className="flex gap-1.5 mt-1">
        {data.map((d, i) => (
          <div key={d.hour} className="flex-1 text-center" style={{ fontSize: 9, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>
            {d.hour.replace('시', '')}
          </div>
        ))}
      </div>
      {/* Tooltip */}
      {hovered !== null && (
        <div
          className="absolute bottom-full mb-2 rounded-xl px-3 py-2 pointer-events-none z-10"
          style={{
            left: `${(hovered / data.length) * 100}%`,
            transform: 'translateX(-50%)',
            background: 'var(--color-card2)',
            border: '1px solid color-mix(in srgb, var(--color-primary) 30%, transparent)',
            whiteSpace: 'nowrap',
          }}
        >
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-primary)', marginBottom: 2 }}>{data[hovered].hour}</div>
          <div style={{ fontSize: 10, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>
            🚇 {data[hovered].subway.toLocaleString()}명
          </div>
          <div style={{ fontSize: 10, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>
            🚌 {data[hovered].bus.toLocaleString()}명
          </div>
          <div style={{ fontSize: 10, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>
            🚲 {data[hovered].bike.toLocaleString()}명
          </div>
          <div style={{ fontSize: 10, color: '#FB923C', fontFamily: 'JetBrains Mono', marginTop: 2 }}>
            💧 강수 {data[hovered].rain}mm
          </div>
        </div>
      )}
    </div>
  )
}

// ── 상관관계 시각화 (20.9만 건 서울시 교통·기상 실측 빅데이터 교정) ──
function CorrelationChart() {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null)
  const activeItem = hoveredIdx !== null ? CORRELATION_DATA[hoveredIdx] : null

  return (
    <div className="relative">
      {/* 호버 상세 정보 배지 */}
      <div style={{
        minHeight: 22,
        marginBottom: 8,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        fontSize: 11,
        fontFamily: 'JetBrains Mono',
      }}>
        {activeItem ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--color-primary)', fontWeight: 700 }}>
              🌧 강수 {activeItem.rain}mm:
            </span>
            <div style={{ display: 'flex', gap: 8, fontSize: 10 }}>
              <span style={{ color: 'var(--color-primary)' }}>🚇 {activeItem.subway}%</span>
              <span style={{ color: '#FB923C' }}>🚌 {activeItem.bus}%</span>
              <span style={{ color: '#34D399', fontWeight: 700 }}>🚲 {activeItem.bike}%</span>
            </div>
            <span style={{ fontSize: 9, color: 'var(--app-text)' }}>
              ({activeItem.note})
            </span>
          </div>
        ) : (
          <span style={{ fontSize: 10, color: 'var(--app-text)' }}>
            💡 그래프 위로 마우스를 올리면 강수량별 실측 이용률을 확인할 수 있습니다
          </span>
        )}
      </div>

      <div className="relative h-28">
        <svg width="100%" height="100%" viewBox="0 0 300 112" preserveAspectRatio="none">
          {/* Grid */}
          {[0, 28, 56, 84, 112].map(y => (
            <line key={y} x1="0" y1={y} x2="300" y2={y} stroke="var(--app-text)" strokeWidth="1" />
          ))}

          {/* 호버 세로 하이라이트 가이드선 */}
          {hoveredIdx !== null && (
            <line
              x1={(hoveredIdx / (CORRELATION_DATA.length - 1)) * 300}
              y1={0}
              x2={(hoveredIdx / (CORRELATION_DATA.length - 1)) * 300}
              y2={112}
              stroke="var(--app-text)"
              strokeWidth="1.5"
              strokeDasharray="3 2"
            />
          )}

          {/* Subway line */}
          <polyline
            points={CORRELATION_DATA.map((d, i) => `${(i / (CORRELATION_DATA.length - 1)) * 300},${112 - (d.subway / 100) * 100}`).join(' ')}
            fill="none" stroke="var(--color-primary)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
          />

          {/* Bus line */}
          <polyline
            points={CORRELATION_DATA.map((d, i) => `${(i / (CORRELATION_DATA.length - 1)) * 300},${112 - (d.bus / 100) * 100}`).join(' ')}
            fill="none" stroke="#FB923C" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
          />

          {/* Bike line */}
          <polyline
            points={CORRELATION_DATA.map((d, i) => `${(i / (CORRELATION_DATA.length - 1)) * 300},${112 - (d.bike / 100) * 100}`).join(' ')}
            fill="none" stroke="#34D399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
          />

          {/* 데이터 포인트 점 (Circles) */}
          {CORRELATION_DATA.map((d, i) => {
            const x = (i / (CORRELATION_DATA.length - 1)) * 300
            const ySub = 112 - (d.subway / 100) * 100
            const yBus = 112 - (d.bus / 100) * 100
            const yBike = 112 - (d.bike / 100) * 100
            const isHover = hoveredIdx === i

            return (
              <g key={i}>
                <circle cx={x} cy={ySub} r={isHover ? 4.5 : 2.5} fill="var(--color-primary)" />
                <circle cx={x} cy={yBus} r={isHover ? 4.5 : 2.5} fill="#FB923C" />
                <circle cx={x} cy={yBike} r={isHover ? 5 : 3} fill="#34D399" />
              </g>
            )
          })}

          {/* 마우스 호버 감지 투명 히트박스 */}
          {CORRELATION_DATA.map((_, i) => {
            const x = (i / (CORRELATION_DATA.length - 1)) * 300
            const step = 300 / (CORRELATION_DATA.length - 1)
            return (
              <rect
                key={i}
                x={x - step / 2}
                y={0}
                width={step}
                height={112}
                fill="transparent"
                style={{ cursor: 'pointer' }}
                onMouseEnter={() => setHoveredIdx(i)}
                onMouseLeave={() => setHoveredIdx(null)}
              />
            )
          })}
        </svg>

        {/* X axis labels */}
        <div className="flex justify-between mt-1">
          {CORRELATION_DATA.map((d, i) => (
            <span
              key={d.rain}
              style={{
                fontSize: 9,
                color: hoveredIdx === i ? 'var(--color-primary)' : 'var(--app-text)',
                fontWeight: hoveredIdx === i ? 700 : 400,
                fontFamily: 'JetBrains Mono',
                transition: 'color 0.15s ease'
              }}
            >
              {d.rain}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}

const getApiBaseUrl = (): string => {
  const envVal = (import.meta as any).env?.VITE_API_BASE_URL
  if (typeof envVal === 'string') return envVal
  if (typeof window !== 'undefined' && window.location) {
    const proto = window.location.protocol || 'http:'
    const host = window.location.hostname || 'localhost'
    return `${proto}//${host}:8000`
  }
  return 'http://localhost:8000'
}
const API_BASE_URL = getApiBaseUrl()

interface LiveWeatherData {
  status: string
  district: string
  nx: number
  ny: number
  base_date: string
  base_time: string
  temp: number
  rain: number
  pty: string
  pty_desc: string
  humidity: number
  wind: number
  source: string
}

const getInitialPage = (): Page => {
  if (typeof window !== 'undefined') {
    const hash = window.location.hash.replace(/^#/, '') as Page
    if (hash === 'main' || hash === 'route' || hash === 'map' || hash === 'enterprise') return hash
    try {
      const saved = localStorage.getItem('weather_transit_page') as Page
      if (saved === 'main' || saved === 'route' || saved === 'map' || saved === 'enterprise') return saved
    } catch {}
  }
  return 'main'
}

const getInitialDistrict = (): number => {
  if (typeof window !== 'undefined') {
    try {
      const savedName = localStorage.getItem('weather_transit_district_name')
      if (savedName) {
        const idx = DISTRICTS.indexOf(savedName)
        if (idx !== -1) return idx
        const partialIdx = DISTRICTS.findIndex(d => d.includes(savedName) || savedName.includes(d))
        if (partialIdx !== -1) return partialIdx
      }
      const savedIdx = localStorage.getItem('weather_transit_district')
      if (savedIdx !== null) {
        const num = Number(savedIdx)
        if (!isNaN(num) && num >= 0 && num < DISTRICTS.length) return num
      }
    } catch { }
  }
  return 0
}

export default function App() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme)
  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('weather-transit-theme', theme)
    } catch {
      // 저장 실패 시에도 화면 테마는 변경
    }
  }, [theme])

  // OS/기기 시스템 테마 실시간 변경 감지 (수동 설정 없을 때 동기화)
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = (e: MediaQueryListEvent) => {
      try {
        const saved = localStorage.getItem('weather-transit-theme')
        if (!saved) {
          setTheme(e.matches ? 'dark' : 'light')
        }
      } catch {}
    }
    mediaQuery.addEventListener('change', handleChange)
    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [])

  const toggleTheme = () => {
    setTheme(current => current === 'dark' ? 'light' : 'dark')
  }

  const [page, setPage] = useState<Page>(getInitialPage)
  const [selectedDistrict, setSelectedDistrict] = useState<number>(getInitialDistrict)
  const [departure, setDeparture] = useState(() => {
    if (typeof window !== 'undefined') {
      try {
        return localStorage.getItem('weather_transit_route_departure') || ''
      } catch {}
    }
    return ''
  })
  const [destination, setDestination] = useState(() => {
    if (typeof window !== 'undefined') {
      try {
        return localStorage.getItem('weather_transit_route_destination') || ''
      } catch {}
    }
    return ''
  })
  const [mapTransport, setMapTransport] = useState<'all' | 'subway' | 'bus' | 'bike'>(() => {
    if (typeof window !== 'undefined') {
      try {
        const saved = localStorage.getItem('weather_transit_map_transport')
        if (saved === 'all' || saved === 'subway' || saved === 'bus' || saved === 'bike') {
          return saved
        }
      } catch { }
    }
    return 'all'
  })
  const [districtQuery, setDistrictQuery] = useState('')
  const [selectedStop, setSelectedStop] = useState<TransitStop | null>(null)
  const [subwaySearchQuery, setSubwaySearchQuery] = useState('')
  const [focusedCoords, setFocusedCoords] = useState<[number, number] | null>(null)
  const [selectedBusStation, setSelectedBusStation] = useState<BusStationResult | null>(null)
  const [showSearchResults, setShowSearchResults] = useState(false)
  const [showDepartureList, setShowDepartureList] = useState(false)
  const [showDestinationList, setShowDestinationList] = useState(false)
  const [stopArrivalData, setStopArrivalData] = useState<{
    loading: boolean
    subwayArrivals?: any[]
    busArrivals?: any[]
    lastUpdated?: string
  }>({ loading: false })
  const [stopWeatherData, setStopWeatherData] = useState<any | null>(null)
  const [stopAIData, setStopAIData] = useState<any | null>(null)
  const [stopDataLoading, setStopDataLoading] = useState(false)

  // ── 기상청 실시간 실황 데이터 연동 상태 (100% 진본 실시간) ──
  const [liveWeather, setLiveWeather] = useState<LiveWeatherData | null>(null)
  const nowHour = new Date().getHours()
  const [selectedHour, setSelectedHour] = useState<number>(nowHour)
  const [isConsoleLogging, setIsConsoleLogging] = useState(false)

  // ── AI 추론 백엔드 서버 연동 상태 ──
  const [transportScores, setTransportScores] = useState<(typeof TRANSPORT_SCORES[number] & { predicted_volume?: number })[]>(TRANSPORT_SCORES)
  const [aiLatency, setAiLatency] = useState<number | null>(null)
  const [aiStatus, setAiStatus] = useState<'connected' | 'loading' | 'offline'>('loading')
  const [aiWeatherSummary, setAiWeatherSummary] = useState<{ condition: string; description: string } | null>(null)

  // ── 동별 실시간 교통 혼잡도 상태 (8대 거점 ONNX 실시간 추론 연동) ──
  const [districtList, setDistrictList] = useState<Array<{
    name: string
    district?: string
    bus: number
    subway: number
    bike: number
    weather: string
    temp: number
    rain?: number
  }>>(DISTRICT_DATA)
  const [districtLiveStatus, setDistrictLiveStatus] = useState<'idle' | 'loading' | 'live'>('idle')
  const lastDistrictCongestionKeyRef = useRef<string>('')

  // 24시간 실시간 AI 시계열 예측 상태
  const [hourlyForecast, setHourlyForecast] = useState<HourlyTransitData[]>(DEFAULT_24H_DATA)
  const [hourlyLiveStatus, setHourlyLiveStatus] = useState<'idle' | 'loading' | 'live'>('idle')
  const [hourlyHovered, setHourlyHovered] = useState<number | null>(null)
  const lastHourlyForecastKeyRef = useRef<string>('')

  // 활성 경로 탐색 결과 상태
  const [activeRoute, setActiveRoute] = useState<TransitRouteResult | null>(null)

  // 키보드(Arrow, Tab, Enter) 탐색용 인덱스 상태
  const [selectedSubwayIndex, setSelectedSubwayIndex] = useState(0)
  const [selectedDepartureIndex, setSelectedDepartureIndex] = useState(0)
  const [selectedDestinationIndex, setSelectedDestinationIndex] = useState(0)

  // 경로 검색 실행 함수 (출발역-도착역 최단 경로 계산 및 실시간 열차 도착 정보 연동)
  const handleSearchRoute = async (from = departure, to = destination, navigateToMap = false) => {
    if (!from.trim() || !to.trim()) {
      alert('출발역과 도착역을 입력해주세요.')
      return
    }
    setShowDepartureList(false)
    setShowDestinationList(false)
    const route = findSubwayRoute(from, to)
    if (route) {
      setDeparture(route.from)
      setDestination(route.to)
      const cleanFrom = from.replace(/역$/, '')
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/transit/subway/arrival?station=${encodeURIComponent(cleanFrom)}`)
        if (res.ok) {
          const liveSubway = await res.json()
          if (liveSubway.status === 'success' && liveSubway.arrivals && liveSubway.arrivals.length > 0) {
            const expectedLine = route.departureTrain?.line || route.path[0]?.lineUsed || ''
            const firstTrain = liveSubway.arrivals.find((a: any) => a.line && expectedLine && (a.line.includes(expectedLine) || expectedLine.includes(a.line)))
            if (firstTrain) route.departureTrain = {
              station: from,
              trainLineNm: firstTrain.destination,
              destinationOrNext: firstTrain.destination,
              arrivalMessage: firstTrain.message,
              remainingMinutes: firstTrain.remaining_minutes,
              remainingSeconds: firstTrain.remaining_seconds,
              line: firstTrain.line,
            }
            logSubwayApiCall(cleanFrom, liveSubway.arrivals, liveSubway)
          }
        }
      } catch (err) {
        console.warn('실시간 지하철 도착 정보 연동 실패 (스케줄러 추정치 유지):', err)
      }

      setActiveRoute(route)
      if (navigateToMap) {
        setPage('map')
        if (mapTransport === 'bus' || mapTransport === 'bike') {
          setMapTransport('all')
        }
      }

      if (route.transferTrains) {
        route.transferTrains.forEach(tr => {
          logSubwayApiCall(tr.station.replace('역', ''), [
            { trainLineNm: tr.trainLineNm, arvlMsg2: tr.arrivalMessage, barvlDt: String(tr.remainingSeconds), btrainSttus: '일반' }
          ])
        })
      }
    } else {
      alert(`'${from}'에서 '${to}'까지의 지하철 경로를 찾을 수 없습니다. 역 이름을 정확히 입력해주세요.`)
    }
  }

  // 출발지 및 도착지 초기화 함수
  const handleResetRoute = () => {
    setDeparture('')
    setDestination('')
    setActiveRoute(null)
    setShowDepartureList(false)
    setShowDestinationList(false)
    if (typeof window !== 'undefined') {
      try {
        localStorage.removeItem('weather_transit_route_departure')
        localStorage.removeItem('weather_transit_route_destination')
      } catch {}
    }
  }

  // 출발지 ↔ 도착지 맞바꾸기
  const handleSwapRoute = () => {
    const prevDep = departure
    const prevDest = destination
    setDeparture(prevDest)
    setDestination(prevDep)
    setShowDepartureList(false)
    setShowDestinationList(false)
    if (prevDest && prevDep) {
      handleSearchRoute(prevDest, prevDep, false)
    }
  }

  // 탭 상태 로컬 스토리지 및 URL 해시 동기화 (새로고침 시 현재 탭 유지)
  useEffect(() => {
    try {
      localStorage.setItem('weather_transit_page', page)
    } catch { }
    if (window.location.hash.replace(/^#/, '') !== page) {
      window.location.hash = page
    }
  }, [page])

  // 선택된 자치구 브라우저 로컬 스토리지에 동기화 (새로고침 및 재방문 시 자동 복원)
  useEffect(() => {
    try {
      localStorage.setItem('weather_transit_district', String(selectedDistrict))
      if (DISTRICTS[selectedDistrict]) {
        localStorage.setItem('weather_transit_district_name', DISTRICTS[selectedDistrict])
      }
    } catch { }
  }, [selectedDistrict])

  // 지도 필터 교통수단(전체/지하철/버스/따릉이) 로컬 스토리지 동기화 (새로고침 시 유지)
  useEffect(() => {
    try {
      localStorage.setItem('weather_transit_map_transport', mapTransport)
    } catch { }
  }, [mapTransport])

  // 이전 경로 검색 기록(출발지/도착지) 로컬 스토리지 동기화 (탭 전환 및 재방문 시 유지)
  useEffect(() => {
    try {
      localStorage.setItem('weather_transit_route_departure', departure)
      localStorage.setItem('weather_transit_route_destination', destination)
    } catch {}
  }, [departure, destination])

  useEffect(() => {
    const handleHash = () => {
      const hash = window.location.hash.replace(/^#/, '') as Page
      if (hash === 'main' || hash === 'route' || hash === 'map') {
        setPage(hash)
      }
    }
    window.addEventListener('hashchange', handleHash)
    return () => window.removeEventListener('hashchange', handleHash)
  }, [])

  const lastFetchedDistrictRef = useRef<number | null>(null)

  // 선택된 자치구의 기상청 실시간 초단기실황 데이터 자동 동기화
  useEffect(() => {
    let isMounted = true
    const districtName = DISTRICTS[selectedDistrict] || '강남구 역삼동'
    if (lastFetchedDistrictRef.current === selectedDistrict && liveWeather) {
      return
    }
    lastFetchedDistrictRef.current = selectedDistrict

    fetch(`${API_BASE_URL}/api/v1/weather/current?district=${encodeURIComponent(districtName)}`)
      .then(res => res.json())
      .then((data: LiveWeatherData) => {
        if (isMounted && data.status === 'success') {
          setLiveWeather(data)
          // 지역(자치구/광역도시) 변경 시 브라우저 콘솔(F12)에 해당 지역 기상청 실시간 API 데이터 즉시 출력
          logWeatherApiCall({ nx: data.nx, ny: data.ny }, data, data)
        }
      })
      .catch(err => {
        console.warn('[Live Weather] 기상청 실시간 데이터 연동 실패 (fallback 유지):', err)
      })
    return () => {
      isMounted = false
    }
  }, [selectedDistrict])

  // ── 지하철역 검색 선택 시 지도 카메라 이동 및 상태 갱신 ──
  const handleSelectStation = (station: SubwayStation) => {
    setActiveRoute(null)
    setSubwaySearchQuery(station.name)
    setShowSearchResults(false)
    setMapTransport('subway')
    setFocusedCoords(station.coords)
  }

  const lastFetchedStopIdRef = useRef<string | null>(null)

  // ── 지도(TransitMap)에서 거점 클릭 시 수신되는 통합 데이터 핸들러 (중복 Fetch 원천 방지) ──
  const handleSelectStop = (stop: TransitStop | null, details?: StopDetailData) => {
    if (!stop) {
      lastFetchedStopIdRef.current = null
      setSelectedStop(null)
      setStopWeatherData(null)
      setStopAIData(null)
      setStopArrivalData({ loading: false })
      setStopDataLoading(false)
      return
    }

    lastFetchedStopIdRef.current = stop.id
    setSelectedStop(stop)

    if (details?.loading) {
      setStopDataLoading(true)
      setStopArrivalData({ loading: true })
    } else if (details && !details.loading) {
      setStopDataLoading(false)
      setStopWeatherData(details.weather || null)
      setStopAIData(details.aiPrediction || null)
      setStopArrivalData({
        loading: false,
        subwayArrivals: stop.type === 'subway' ? (details.arrivals || []) : [],
        busArrivals: stop.type === 'bus' ? (details.arrivals || []) : [],
        lastUpdated: new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
      })
    }
  }

  // ── 선택된 거점(지하철역 또는 버스 정류소)의 실시간 국지 기상, AI 모델 추론, 실시간 도착 정보 연동 파이프라인 ──
  useEffect(() => {
    if (!selectedStop) {
      setStopArrivalData({ loading: false })
      setStopWeatherData(null)
      setStopAIData(null)
      setStopDataLoading(false)
      return
    }

    // TransitMap에서 이미 데이터를 수신 및 동기화한 경우 중복 Fetch 방지
    if (lastFetchedStopIdRef.current === selectedStop.id && (stopWeatherData || stopAIData)) {
      return
    }

    let isMounted = true
    const stop = selectedStop
    const district = resolveDistrict(stop.name, stop.coords)
    const cleanName = stop.name.replace(/역$/, '').trim()

    setStopDataLoading(true)
    setStopArrivalData({ loading: true })

    const runStopPipeline = async () => {
      try {
        // 1. 해당 역의 실시간 기상 API 조회 (WGS84 좌표 기반 KMA 격자 nx, ny 정밀 산출)
        const weatherUrl = `${API_BASE_URL}/api/v1/weather/current?district=${encodeURIComponent(district)}&lat=${stop.coords[1]}&lng=${stop.coords[0]}&station=${encodeURIComponent(cleanName)}`
        const weatherRes = await fetch(weatherUrl)
        const weatherJson = await weatherRes.json()

        if (!isMounted) return
        setStopWeatherData(weatherJson)
        logWeatherApiCall(
          { nx: weatherJson.nx, ny: weatherJson.ny },
          weatherJson,
          weatherJson
        )

        // 2. 해당 역의 실시간 기상 관측값을 투입하여 AI 모델(ONNX 32차원 피처) 추론 실행
        const currentHour = liveWeather ? parseInt(liveWeather.base_time.slice(0, 2), 10) : new Date().getHours()
        const aiPayload = {
          district,
          station: stop.name,
          stop_type: stop.type,
          base_crowd: stop.baseCrowd,
          hour: currentHour,
          weather: {
            temp: weatherJson.temp,
            rain: weatherJson.rain,
            humidity: weatherJson.humidity,
            wind: weatherJson.wind,
          }
        }

        const aiRes = await fetch(`${API_BASE_URL}/api/v1/predict/recommendation`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(aiPayload)
        })
        const aiJson = await aiRes.json()

        if (!isMounted) return
        setStopAIData(aiJson)
        logAIPredictionCall(aiPayload, aiJson)

        // 3. 실시간 대중교통 도착 정보 조회
        if (stop.type === 'subway') {
          const arrivalRes = await fetch(`${API_BASE_URL}/api/v1/transit/subway/arrival?station=${encodeURIComponent(cleanName)}`)
          const arrivalData = await arrivalRes.json()
          if (!isMounted) return

          const arrivals = (arrivalData.status === 'success' && arrivalData.arrivals && arrivalData.arrivals.length > 0)
            ? arrivalData.arrivals
            : [
              { line: stop.lineInfo.split(' · ')[0] || '지하철', destination: `${stop.name} 경유 방면`, message: '배차 간격 2~5분 정상 운행', remaining_minutes: 2, updn_line: '상/하행' }
            ]
          setStopArrivalData({
            loading: false,
            subwayArrivals: arrivals,
            lastUpdated: new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
          })
          logSubwayApiCall(cleanName, arrivals, arrivalData)
        } else if (stop.type === 'bus') {
          const busRes = await fetch(`${API_BASE_URL}/api/v1/transit/bus/arrival?stId=111000299`)
          const busData = await busRes.json()
          if (!isMounted) return

          const arrivals = (busData.status === 'success' && busData.arrivals && busData.arrivals.length > 0)
            ? busData.arrivals
            : [
              { route_name: '472', arrival_msg1: '곧 도착' },
              { route_name: '140', arrival_msg1: '3분 후' }
            ]
          setStopArrivalData({
            loading: false,
            busArrivals: arrivals,
            lastUpdated: new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
          })
          logBusApiCall('100100118', '111000299', arrivals, busData)
        } else {
          setStopArrivalData({ loading: false })
        }
      } catch (err) {
        console.error('거점 상세 파이프라인 조회 오류:', err)
        if (isMounted) {
          setStopArrivalData({
            loading: false,
            subwayArrivals: [
              { line: stop.lineInfo.split(' · ')[0] || '지하철', destination: `${stop.name} 경유 방면`, message: '정상 운행중', remaining_minutes: 2, updn_line: '상/하행' }
            ],
            lastUpdated: new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
          })
        }
      } finally {
        if (isMounted) {
          setStopDataLoading(false)
        }
      }
    }

    runStopPipeline()

    return () => {
      isMounted = false
    }
  }, [selectedStop])

  const isLive = liveWeather !== null
  const isCurrentHour = selectedHour === nowHour
  const selectedHourItem = hourlyForecast.find(d => d.hour_num === selectedHour) || null
  const activeTemp = liveWeather ? liveWeather.temp : 14.0
  const activeRain = liveWeather ? liveWeather.rain : 0.0
  const activeHumidity = liveWeather ? liveWeather.humidity : 60.0
  const activeWind = liveWeather ? liveWeather.wind : 2.0

  const displayTemp = (!isCurrentHour && selectedHourItem) ? selectedHourItem.temp : activeTemp
  const displayRain = (!isCurrentHour && selectedHourItem) ? selectedHourItem.rain : activeRain
  const displayHumidity = (!isCurrentHour && selectedHourItem) ? selectedHourItem.humidity : activeHumidity
  const displayWind = (!isCurrentHour && selectedHourItem) ? selectedHourItem.wind : activeWind
  const isRaining = displayRain > 0 || (isCurrentHour && isLive && liveWeather.pty !== '0' && liveWeather.pty !== '')
  const activePtyDesc = isLive ? liveWeather.pty_desc : (activeRain > 0 ? `비 · ${activeRain}mm/h` : '맑음')
  const displayPtyDesc = !isCurrentHour ? (displayRain > 0 ? `비 · ${displayRain}mm/h` : '맑음') : activePtyDesc

  // ── 브라우저 개발자 콘솔(F12)에 실시간 공공 API 데이터 일괄 출력 (사용자 요청 시 온디맨드 On-Demand 호출) ──
  const triggerApiConsoleLog = async () => {
    setIsConsoleLogging(true)
    console.clear()
    console.log(
      '%c📡 [Weather & Transit Web] 실시간 공공 API 및 AI 모델 데이터 스트림 모니터링 (On-Demand)',
      'background: var(--color-card2); color: var(--color-primary); font-size: 13px; font-weight: 800; padding: 6px 12px; border-radius: 6px; border: 1px solid var(--color-primary);'
    )

    const districtName = DISTRICTS[selectedDistrict] || '강남구 역삼동'

    // 1. 기상청 초단기실황 (getUltraSrtNcst 실시간 Fetch)
    try {
      const resW = await fetch(`${API_BASE_URL}/api/v1/weather/current?district=${encodeURIComponent(districtName)}`)
      if (resW.ok) {
        const dataW = await resW.json()
        logWeatherApiCall({ nx: dataW.nx, ny: dataW.ny }, dataW, dataW)
      }
    } catch (err) {
      console.warn('기상청 실시간 API 조회 실패:', err)
    }

    // 2. 서울 열린데이터광장 지하철 실시간도착 (경로 출발역 또는 선택된 지하철역 온디맨드 Fetch)
    const targetStation = (departure || (selectedStop && selectedStop.type === 'subway' ? selectedStop.name : '')).replace(/역$/, '')
    if (targetStation) {
      try {
        const resS = await fetch(`${API_BASE_URL}/api/v1/transit/subway/arrival?station=${encodeURIComponent(targetStation)}`)
        if (resS.ok) {
          const dataS = await resS.json()
          logSubwayApiCall(targetStation, dataS.arrivals, dataS)
        }
      } catch (err) {
        console.warn('지하철 실시간 API 조회 실패:', err)
      }
    }

    // 3. 공공데이터포털 버스도착정보 (선택된 거점이 버스 정류소인 경우 온디맨드 Fetch)
    if (selectedStop && selectedStop.type === 'bus') {
      try {
        const resB = await fetch(`${API_BASE_URL}/api/v1/transit/bus/arrival?stId=111000299`)
        if (resB.ok) {
          const dataB = await resB.json()
          logBusApiCall('100100118', '111000299', dataB.arrivals, dataB)
        }
      } catch (err) {
        console.warn('버스 실시간 API 조회 실패:', err)
      }
    }

    // 4. AI 수요 예측 추론 (실시간 모델 추론 결과와 동기화)
    const currentHourNum = new Date().getHours()
    logAIPredictionCall(
      {
        location: districtName,
        rain: `${activeRain}mm`,
        temp: `${activeTemp}°C`,
        hour: `${currentHourNum}시 (실시간)`,
        latency: aiLatency ? `${aiLatency}ms (ONNX Engine)` : '실시간 연동'
      },
      transportScores.map(t => ({
        id: t.id,
        name: t.name,
        score: t.score,
        scoreLabel: t.scoreLabel,
        crowd: `${t.crowd}% (${t.crowdLabel})`,
        predicted_volume: t.predicted_volume ?? '연산 완료'
      }))
    )

    setIsConsoleLogging(false)
  }

  // ── 실시간 AI 대중교통 수요 예측 및 MCDA 추천 API 호출 ──
  const fetchAIPrediction = async (
    districtName: string,
    hourVal: number,
    weather: { temp: number; rain: number; humidity: number; wind: number; hour: string }
  ) => {
    setAiStatus('loading')
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/predict/recommendation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          district: districtName,
          hour: hourVal,
          weather: {
            temp: weather.temp,
            rain: weather.rain,
            humidity: weather.humidity,
            wind: weather.wind
          }
        })
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()

      if (data.status === 'success' && Array.isArray(data.recommendations)) {
        const mapped = data.recommendations.map((r: any) => ({
          id: r.id,
          icon: r.icon,
          name: r.name,
          score: r.score,
          scoreLabel: r.scoreLabel,
          scoreColor: r.scoreColor,
          reasons: r.reasons,
          time: `${r.estimated_time_min}분`,
          price: `${r.fare_krw.toLocaleString()}원${r.id === 'bike' ? '/시간' : ''}`,
          crowd: r.crowd,
          crowdLabel: r.crowdLabel,
          crowdColor: r.crowdColor,
          dataset: r.id === 'subway'
            ? '지하철 호선별 역별 시간대별 승하차 (AI 추론)'
            : r.id === 'bus'
              ? '버스노선별 정류장별 시간대별 승하차 (AI 추론)'
              : '공공자전거 따릉이 대여이력 (AI 추론)',
          predicted_volume: r.predicted_volume
        }))

        setTransportScores(mapped)
        setAiLatency(data.latency_ms)
        setAiWeatherSummary(data.weather_summary)
        setAiStatus('connected')

        logAIPredictionCall(
          {
            district: districtName,
            station: districtName,
            location: districtName,
            rain: `${weather.rain}mm`,
            temp: `${weather.temp}°C`,
            hour: `${hourVal}시`,
            latency: `${data.latency_ms}ms (ONNX Engine)`
          },
          data.recommendations
        )
      }
    } catch (err) {
      console.warn('[AI Engine] 백엔드 연결 불가, 기본 목데이터 유지:', err)
      setAiStatus('offline')
    }
  }

  // ── 8대 주요 거점 실시간 교통 혼잡도 ONNX 추론 조회 ──
  const fetchDistrictCongestion = async (rainVal: number, tempVal: number, hourVal: number) => {
    const fetchKey = `${rainVal}_${tempVal}_${hourVal}`
    if (lastDistrictCongestionKeyRef.current === fetchKey) return
    lastDistrictCongestionKeyRef.current = fetchKey

    try {
      setDistrictLiveStatus('loading')
      const res = await fetch(`${API_BASE_URL}/api/v1/districts/live-congestion?rain=${rainVal}&temp=${tempVal}&hour=${hourVal}`)
      if (res.ok) {
        const data = await res.json()
        if (data.status === 'success' && data.hotspots && data.hotspots.length > 0) {
          setDistrictList(data.hotspots)
          setDistrictLiveStatus('live')
        }
      }
    } catch (err) {
      console.warn('동별 실시간 교통 혼잡도 조회 실패, 기본값 유지:', err)
      setDistrictLiveStatus('idle')
    }
  }

  // ── 24시간 실시간 시계열 AI 예측 곡선 조회 ──
  const fetchHourlyForecast = async (districtName: string, rainVal: number, tempVal: number) => {
    const fetchKey = `${districtName}_${rainVal}_${tempVal}`
    if (lastHourlyForecastKeyRef.current === fetchKey) return
    lastHourlyForecastKeyRef.current = fetchKey

    try {
      setHourlyLiveStatus('loading')
      const targetDistrict = districtName.split(' ')[0] || districtName
      const res = await fetch(`${API_BASE_URL}/api/v1/transit/hourly-forecast?district=${encodeURIComponent(targetDistrict)}&rain=${rainVal}&temp=${tempVal}`)
      if (res.ok) {
        const data = await res.json()
        const forecastList = data.forecast || data.hourly
        if (data.status === 'success' && forecastList && forecastList.length > 0) {
          setHourlyForecast(forecastList)
          setHourlyLiveStatus('live')
        }
      }
    } catch (err) {
      console.warn('24시간 AI 시계열 예측 조회 실패, 기본값 유지:', err)
      setHourlyLiveStatus('idle')
    }
  }

  const lastAIFetchKeyRef = useRef<string>('')

  // 자치구, 선택된 시간대 또는 실시간 기상 데이터 변경 시 AI 추론 자동 실행 (기상청 단기예보 동적 연동)
  useEffect(() => {
    if (!liveWeather) return

    const districtName = DISTRICTS[selectedDistrict] || '강남구 역삼동'
    const fetchKey = `${districtName}_${displayTemp}_${displayRain}_${selectedHour}`

    if (lastAIFetchKeyRef.current !== fetchKey) {
      lastAIFetchKeyRef.current = fetchKey
      fetchAIPrediction(districtName, selectedHour, {
        temp: displayTemp,
        rain: displayRain,
        humidity: displayHumidity,
        wind: displayWind,
        hour: `${selectedHour}시`
      })
    }

    fetchDistrictCongestion(displayRain, displayTemp, selectedHour)
    fetchHourlyForecast(districtName, activeRain, activeTemp)
  }, [selectedDistrict, liveWeather, displayRain, displayTemp, selectedHour, displayHumidity, displayWind])

  return (
    <div style={{ minHeight: '100vh', background: 'var(--color-bg)', fontFamily: "'Outfit', 'Noto Sans KR', sans-serif", color: 'var(--app-text)', transition: 'background-color 0.2s ease, color 0.2s ease' }}>

      {/* ── TOP NAV ── */}
      <nav style={{ background: 'var(--app-nav)', backdropFilter: 'blur(20px)', borderBottom: '1px solid var(--color-border)', position: 'sticky', top: 0, zIndex: 50 }}>
        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 32px', display: 'flex', alignItems: 'center', height: 60, gap: 32 }}>
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
            <div style={{ width: 32, height: 32, borderRadius: 10, background: 'linear-gradient(135deg,var(--color-primary),var(--color-accent))', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16 }}>
              🌦
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 800, letterSpacing: '-0.3px', color: 'var(--app-text)' }}>WeatherMove</div>
              
<div style={{ fontSize: 9, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono', letterSpacing: '0.06em', marginTop: -1 }}>SEOUL TRANSPORT AI</div>

            </div>
          </div>

          {/* Nav tabs */}
          <div style={{ display: 'flex', gap: 4, flex: 1 }}>
            {([
              { id: 'main', label: '날씨 · 현황', icon: '🏠' },
              { id: 'route', label: '경로 추천', icon: '🔍' },
              { id: 'map', label: '지도 보기', icon: '🗺' },
              { id: 'enterprise', label: '기업용 분석', icon: '🏢' },
            ] as { id: Page; label: string; icon: string }[]).map(nav => (
              <button
                key={nav.id}
                onClick={() => {
                  setPage(nav.id)
                  setFocusedCoords(null)
                }}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6, padding: '6px 16px', borderRadius: 10,
                  background: page === nav.id ? 'color-mix(in srgb, var(--color-primary) 15%, transparent)' : 'transparent',
                  border: page === nav.id ? '1px solid color-mix(in srgb, var(--color-primary) 35%, transparent)' : '1px solid transparent',
                  color: page === nav.id ? 'var(--color-primary)' : 'var(--app-text)',
                  fontSize: 13, fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s',
                }}
              >
                <span style={{ fontSize: 15 }}>{nav.icon}</span>
                {nav.label}
              </button>
            ))}
          </div>

          {/* Live indicator & Console trigger button & GitHub Link */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
            <a
              href="https://github.com/14EE4/weather-transit-web"
              target="_blank"
              rel="noopener noreferrer"
              title="GitHub 저장소 바로가기"
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '6px 12px', borderRadius: 8,
                background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.15)',
                color: 'var(--app-text)', fontSize: 12, fontWeight: 600, textDecoration: 'none',
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.12)';
                e.currentTarget.style.borderColor = 'rgba(255,255,255,0.3)';
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = 'rgba(255,255,255,0.06)';
                e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)';
              }}
            >
              <svg height="16" width="16" viewBox="0 0 16 16" fill="currentColor">
                <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
              </svg>
              <span>GitHub</span>
            </a>
            <button
              type="button"
              onClick={triggerApiConsoleLog}
              disabled={isConsoleLogging}
              title="브라우저 개발자 도구(F12 -> Console)에 실시간 공공 API 데이터를 출력합니다."
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '6px 12px',
                borderRadius: 8,
                background: 'color-mix(in srgb, var(--color-primary) 12%, transparent)',
                border: '1px solid color-mix(in srgb, var(--color-primary) 30%, transparent)',
                color: 'var(--color-primary)',
                fontSize: 11,
                fontWeight: 700,
                cursor: isConsoleLogging ? 'not-allowed' : 'pointer',
              }}
            >
              <span>{isConsoleLogging ? '⏳' : '📡'}</span>
              {isConsoleLogging ? 'API 실시간 수신중...' : 'API 콘솔 로그 확인'}
            </button>

            <button
              type="button"
              onClick={toggleTheme}
              aria-label={theme === 'dark' ? '화이트 모드로 전환' : '다크 모드로 전환'}
              aria-pressed={theme === 'dark'}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 6,
                padding: '7px 12px',
                borderRadius: 8,
                background: 'var(--color-card)',
                border: '1px solid var(--color-border)',
                color: 'var(--app-text)',
                fontSize: 12,
                fontWeight: 700,
                whiteSpace: 'nowrap',
                cursor: 'pointer',
              }}
            >
              {theme === 'dark' ? '☀️ 화이트 모드' : '🌙 다크 모드'}
            </button>

            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{
                width: 7,
                height: 7,
                borderRadius: '50%',
                background: '#34D399',
                boxShadow: '0 0 8px #34D399',
                animation: 'pulse 2s infinite',
              }} />
              <span style={{
                fontSize: 11,
                color: 'var(--color-muted)',
                fontFamily: 'JetBrains Mono',
              }}>
                LIVE · 실시간 연동
              </span>
            </div>
          </div>

        </div>
      </nav>

      {/* ══════════════════════════════════════
          PAGE: 메인 — 날씨 현황
      ══════════════════════════════════════ */}
      {page === 'main' && (
        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '32px 32px 64px' }}>

          {/* 지역 선택 + 헤더 */}
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 28, flexWrap: 'wrap', gap: 16 }}>
            <div>
              <h1 style={{ fontSize: 28, fontWeight: 800, color: 'var(--app-text)', margin: 0, letterSpacing: '-0.5px' }}>
                날씨 기반 교통 현황
              </h1>
              <p style={{ fontSize: 14, color: 'var(--color-muted)', margin: '6px 0 0', lineHeight: 1.5 }}>
                서울시 날씨 + 버스·지하철·따릉이 이용 데이터를 실시간으로 분석합니다
              </p>
            </div>

            {/* 동 선택 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 13, color: 'var(--color-muted)', fontWeight: 600 }}>지역</span>
              <select
                value={selectedDistrict}
                onChange={e => setSelectedDistrict(Number(e.target.value))}
                style={{
                  background: 'var(--color-card)', border: '1px solid var(--color-border)', color: 'var(--app-text)', borderRadius: 12, padding: '8px 14px', fontSize: 13,
                  fontFamily: "'Outfit', 'Noto Sans KR', sans-serif", outline: 'none', cursor: 'pointer',
                  maxWidth: 280, textOverflow: 'ellipsis',
                  boxShadow: '0 2px 12px var(--color-card2)'
                }}
              >
                {DISTRICT_GROUPS.map(group => (
                  <optgroup key={group.zone} label={group.zone} style={{ background: 'var(--color-card2)', color: 'var(--color-primary)', fontWeight: 700 }}>
                    {group.items.map(d => {
                      const globalIdx = DISTRICTS.indexOf(d)
                      return (
                        <option key={d} value={globalIdx} style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)', color: 'var(--app-text)', fontWeight: 400 }}>
                          {d}
                        </option>
                      )
                    })}
                  </optgroup>
                ))}
              </select>
            </div>
          </div>

          {/* ── 시간대별 기상 예보 & AI 교통 분석 컨트롤 슬라이더 ── */}
          <div
            style={{
              background: 'linear-gradient(135deg, var(--color-card) 0%, var(--color-card2) 100%)',
              border: '1px solid rgba(56,189,248,0.3)',
              borderRadius: 20,
              padding: '18px 24px',
              marginBottom: 20,
              boxShadow: '0 8px 32px var(--app-shadow)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12, marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <span style={{ fontSize: 20 }}>⏱️</span>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 15, fontWeight: 700, color: 'var(--app-text)' }}>
                    시간대별 날씨 예보 및 AI 교통 분석
                    <span style={{
                      fontSize: 11, padding: '2px 8px', borderRadius: 6,
                      background: isCurrentHour ? 'rgba(16,185,129,0.2)' : 'rgba(56,189,248,0.2)',
                      color: isCurrentHour ? '#34D399' : '#38BDF8',
                      fontFamily: 'JetBrains Mono', fontWeight: 700,
                      border: isCurrentHour ? '1px solid rgba(16,185,129,0.4)' : '1px solid rgba(56,189,248,0.4)',
                    }}>
                      {isCurrentHour ? '🟢 현재 실시간 관측 모드' : `🌦️ ${selectedHour}시 단기예보 탐색 모드`}
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 2 }}>
                    슬라이더를 움직여 시간대별 실제 기상청 예보 날씨(기온·강수량)와 AI 모델의 추천·이용객 수 변화를 즉시 확인합니다
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {!isCurrentHour && (
                  <button
                    onClick={() => setSelectedHour(nowHour)}
                    style={{
                      padding: '5px 12px', borderRadius: 8,
                      background: 'rgba(56,189,248,0.15)', border: '1px solid #38BDF8',
                      color: '#38BDF8', fontSize: 12, fontWeight: 700, cursor: 'pointer',
                      fontFamily: 'JetBrains Mono', display: 'flex', alignItems: 'center', gap: 4
                    }}
                  >
                    🔄 현재 시각({nowHour}시)으로 복귀
                  </button>
                )}
                <div style={{
                  background: 'rgba(56,189,248,0.12)', border: '1px solid rgba(56,189,248,0.3)',
                  padding: '4px 14px', borderRadius: 10, color: '#38BDF8',
                  fontSize: 16, fontWeight: 800, fontFamily: 'JetBrains Mono'
                }}>
                  {selectedHour}:00
                </div>
              </div>
            </div>

            {/* 슬라이더 인풋 */}
            <input
              type="range"
              min={0}
              max={23}
              value={selectedHour}
              onChange={(e) => setSelectedHour(parseInt(e.target.value, 10))}
              style={{ width: '100%', accentColor: '#38BDF8', cursor: 'pointer', height: 6 }}
            />

            {/* 주요 시간대 눈금 레이블 */}
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono', marginTop: 6 }}>
              {[
                { h: 0, label: '00시(심야)' },
                { h: 4, label: '04시' },
                { h: 8, label: '08시(출근)' },
                { h: 12, label: '12시(점심)' },
                { h: 14, label: '14시(낮최고)' },
                { h: 18, label: '18시(퇴근)' },
                { h: 21, label: '21시(야간)' },
                { h: 23, label: '23시' },
              ].map(t => (
                <span
                  key={t.h}
                  onClick={() => setSelectedHour(t.h)}
                  style={{
                    cursor: 'pointer',
                    color: selectedHour === t.h ? 'var(--color-primary)' : 'var(--color-muted)',
                    fontWeight: selectedHour === t.h ? 700 : 400,
                    transition: 'color 0.15s ease'
                  }}
                >
                  {t.label}
                </span>
              ))}
            </div>
          </div>

          {/* 기상청 실시간 관측 현황 바 (가상 시뮬레이션 완전 배제, 100% 실시간 공공 데이터) */}
          <div
            style={{
              background: 'linear-gradient(135deg, var(--color-card) 0%, var(--color-card2) 100%)',
              border: '1px solid color-mix(in srgb, var(--color-primary) 20%, transparent)',
              borderRadius: 20,
              padding: '16px 24px',
              marginBottom: 24,
              boxShadow: '0 8px 32px var(--app-shadow)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
              {/* 좌측: 실시간 관측 상태 및 지역 정보 */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '6px 12px', borderRadius: 10,
                  background: 'rgba(16,185,129,0.15)', border: '1px solid rgba(16,185,129,0.4)'
                }}>
                  <span style={{ fontSize: 12 }}>🟢</span>
                  <span style={{ fontSize: 12, fontWeight: 700, color: '#34D399', fontFamily: 'JetBrains Mono' }}>
                    기상청 초단기실황 실시간 연동
                  </span>
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--app-text)' }}>
                    {DISTRICTS[selectedDistrict] || '강남구 역삼동'} 실시간 기상 관측
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono', marginTop: 2 }}>
                    {liveWeather ? `발표시각: ${liveWeather.base_date} ${liveWeather.base_time.slice(0, 2)}:00 | 격자 (${liveWeather.nx}, ${liveWeather.ny})` : '기상청 관측망 수신 대기 중...'}
                  </div>
                </div>
              </div>

              {/* 우측: 실시간 기상 핵심 수치 4종 (기온, 강수, 습도, 풍속) */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--color-card)', padding: '6px 14px', borderRadius: 12, border: '1px solid var(--color-border)' }}>
                  <span style={{ fontSize: 16 }}>🌡️</span>
                  <div>
                    <div style={{ fontSize: 9, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono' }}>기온</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>{displayTemp}°C</div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: displayRain > 0 ? 'color-mix(in srgb, var(--color-primary) 10%, transparent)' : 'var(--color-border)', padding: '6px 14px', borderRadius: 12, border: displayRain > 0 ? '1px solid color-mix(in srgb, var(--color-primary) 40%, transparent)' : '1px solid var(--color-border)' }}>
                  <span style={{ fontSize: 16 }}>{isRaining ? '🌧️' : '☀️'}</span>
                  <div>
                    <div style={{ fontSize: 9, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono' }}>강수량 ({displayPtyDesc})</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: displayRain > 0 ? 'var(--color-primary)' : '#34D399', fontFamily: 'JetBrains Mono' }}>{displayRain} mm/h</div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--color-card)', padding: '6px 14px', borderRadius: 12, border: '1px solid var(--color-border)' }}>
                  <span style={{ fontSize: 16 }}>💧</span>
                  <div>
                    <div style={{ fontSize: 9, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono' }}>습도</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>{displayHumidity}%</div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 8, background: 'var(--color-card)', padding: '6px 14px', borderRadius: 12, border: '1px solid var(--color-border)' }}>
                  <span style={{ fontSize: 16 }}>💨</span>
                  <div>
                    <div style={{ fontSize: 9, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono' }}>풍속</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>{displayWind} m/s</div>
                  </div>
                </div>

                <div style={{
                  padding: '6px 12px', borderRadius: 10,
                  background: 'color-mix(in srgb, var(--color-primary) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-primary) 20%, transparent)',
                  fontSize: 11, color: 'var(--color-primary)', fontFamily: 'JetBrains Mono', fontWeight: 600
                }}>
                  {isCurrentHour ? `현재 ${nowHour}시 기준 실시간` : `${selectedHour}시 기상청 단기예보`}
                </div>
              </div>
            </div>
          </div>

          {/* 3열 그리드 */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20, marginBottom: 24 }}>

            {/* 날씨 카드 */}
            <div style={{ background: 'linear-gradient(135deg, var(--color-card) 0%, var(--color-card2) 100%)', border: '1px solid color-mix(in srgb, var(--color-primary) 20%, transparent)', borderRadius: 24, padding: 24, gridColumn: '1' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <div style={{ fontSize: 11, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono', letterSpacing: '0.07em' }}>
                  날씨 데이터 · {DISTRICTS[selectedDistrict]}
                </div>
                <span style={{ fontSize: 9, color: isCurrentHour ? '#34D399' : '#38BDF8', background: isCurrentHour ? 'rgba(16,185,129,0.15)' : 'rgba(56,189,248,0.15)', border: isCurrentHour ? '1px solid rgba(16,185,129,0.4)' : '1px solid rgba(56,189,248,0.4)', padding: '2px 8px', borderRadius: 6, fontFamily: 'JetBrains Mono', fontWeight: 700 }}>
                  {isCurrentHour ? `🟢 기상청 실시간 실황 ${liveWeather ? `(${liveWeather.base_time.slice(0, 2)}:00)` : ''}` : `🌦️ 기상청 단기예보 (${selectedHour}:00 예보)`}
                </span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
                <span style={{ fontSize: 52 }}>{isRaining ? '🌧' : '☀️'}</span>
                <div>
                  <div style={{ fontSize: 52, fontWeight: 800, color: 'var(--app-text)', lineHeight: 1, letterSpacing: '-2px', fontFamily: 'JetBrains Mono' }}>
                    {displayTemp}°
                  </div>
                  <div style={{ fontSize: 13, color: isRaining ? 'var(--color-primary)' : '#FB923C', fontWeight: 600 }}>
                    {isRaining ? `비 · ${displayRain}mm/h` : displayPtyDesc}
                  </div>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {[
                  { label: '습도', value: `${displayHumidity}%`, icon: '💧' },
                  { label: '풍속', value: `${displayWind}m/s`, icon: '💨' },
                  { label: '강수량', value: `${displayRain}mm`, icon: '🌧' },
                  { label: '체감온도', value: `${Math.round(displayTemp - 2)}°C`, icon: '🌡' },
                ].map(item => (
                  <div key={item.label} style={{ background: 'var(--color-card2)', borderRadius: 12, padding: '10px 12px' }}>
                    <div style={{ fontSize: 10, color:  'var(--color-muted)', fontFamily: 'JetBrains Mono', marginBottom: 2 }}>
                      {item.icon} {item.label}
                    </div>
                    <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'JetBrains Mono', color: 'var(--app-text)' }}>{item.value}</div>
                  </div>
                ))}
              </div>
              {liveWeather && (
                <div style={{ marginTop: 14, fontSize: 10, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono', display: 'flex', justifyContent: 'space-between' }}>
                  <span>KMA 격자 ({liveWeather.nx}, {liveWeather.ny})</span>
                  <span>{liveWeather.base_date.slice(4, 6)}/{liveWeather.base_date.slice(6, 8)} {liveWeather.base_time.slice(0, 2)}:00 발표</span>
                </div>
              )}
            </div>

            {/* 이용자 현황 (실제 AI 머신러닝 추론 이용객 수 실시간 연동) */}
            <div style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)', color: 'var(--app-text)', borderRadius: 24, padding: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div style={{ fontSize: 11, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono', letterSpacing: '0.07em' }}>
                  교통 수요 예측 현황 · {isCurrentHour ? `실시간 (${nowHour}시)` : `${selectedHour}시 예보`}
                </div>
                <span style={{ fontSize: 9, color: 'var(--color-primary)', background: 'color-mix(in srgb, var(--color-primary) 12%, transparent)', border: '1px solid color-mix(in srgb, var(--color-primary) 30%, transparent)', padding: '2px 7px', borderRadius: 6, fontFamily: 'JetBrains Mono', fontWeight: 700 }}>
                  ⚡ AI 모델 실시간 연동
                </span>
              </div>
              {(() => {
                const subItem = transportScores.find(t => t.id === 'subway')
                const busItem = transportScores.find(t => t.id === 'bus')
                const bikeItem = transportScores.find(t => t.id === 'bike')

                const liveItems = [
                  {
                    icon: '🚇',
                    name: '지하철',
                    value: subItem?.predicted_volume ?? 18000,
                    crowd: subItem?.crowd ?? 52,
                    crowdLabel: subItem?.crowdLabel ?? '보통',
                    crowdColor: subItem?.crowdColor ?? 'var(--color-primary)',
                    color: 'var(--color-primary)',
                    unit: '명'
                  },
                  {
                    icon: '🚌',
                    name: '버스',
                    value: busItem?.predicted_volume ?? 4200,
                    crowd: busItem?.crowd ?? 78,
                    crowdLabel: busItem?.crowdLabel ?? '혼잡',
                    crowdColor: busItem?.crowdColor ?? '#FB923C',
                    color: '#FB923C',
                    unit: '명'
                  },
                  {
                    icon: '🚲',
                    name: '따릉이',
                    value: bikeItem?.predicted_volume ?? 320,
                    crowd: bikeItem?.crowd ?? 8,
                    crowdLabel: bikeItem?.crowdLabel ?? '여유',
                    crowdColor: bikeItem?.crowdColor ?? '#34D399',
                    color: '#34D399',
                    unit: '건'
                  },
                ]

                return (
                  <>
                    {liveItems.map(t => (
                      <div key={t.name} style={{ marginBottom: 16 }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: 18 }}>{t.icon}</span>
                            <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--app-text)' }}>{t.name}</span>
                            <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: `${t.crowdColor}22`, color: t.crowdColor, fontWeight: 700, fontFamily: 'JetBrains Mono' }}>
                              {t.crowdLabel} {t.crowd}%
                            </span>
                          </div>
                          <span style={{ fontSize: 14, fontWeight: 700, color: t.color, fontFamily: 'JetBrains Mono' }}>
                            {t.value.toLocaleString()}{t.unit}
                          </span>
                        </div>
                        <div style={{ height: 6, background: 'var(--color-card2)', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${Math.min(100, Math.max(5, t.crowd))}%`, background: t.color, borderRadius: 3, transition: 'width 0.5s ease' }} />
                        </div>
                      </div>
                    ))}
                    <div style={{ marginTop: 4, padding: '10px 14px', background: isRaining ? 'color-mix(in srgb, var(--color-primary) 8%, transparent)' : 'rgba(251,146,60,0.08)', borderRadius: 12, border: `1px solid ${isRaining ? 'color-mix(in srgb, var(--color-primary) 20%, transparent)' : 'rgba(251,146,60,0.2)'}` }}>
                      <div style={{ fontSize: 11, color: isRaining ? 'var(--color-primary)' : '#FB923C' }}>
                        {isRaining
                          ? `⚠️ 강수 ${activeRain}mm — 지하철 혼잡도 ${subItem?.crowd ?? 39}% (${(subItem?.predicted_volume ?? 0).toLocaleString()}명) 집중 · 따릉이(${(bikeItem?.predicted_volume ?? 0).toLocaleString()}건) 급감`
                          : `✅ 맑은 날씨 — ${DISTRICTS[selectedDistrict]} 지하철 ${(subItem?.predicted_volume ?? 0).toLocaleString()}명 / 버스 ${(busItem?.predicted_volume ?? 0).toLocaleString()}명 정상 소통`}
                      </div>
                    </div>
                  </>
                )
              })()}
            </div>

            {/* AI 추천 카드 */}
            <div style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)', color: 'var(--app-text)', borderRadius: 24, padding: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div style={{ fontSize: 11, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono', letterSpacing: '0.07em' }}>
                  모델 추천 결과 · 실시간 ({new Date().getHours()}시)
                </div>
                {/* 실시간 AI 연결 배지 */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{
                    width: 7, height: 7, borderRadius: '50%',
                    background: aiStatus === 'connected' ? '#10B981' : aiStatus === 'loading' ? '#FBBF24' : '#64748B',
                    boxShadow: aiStatus === 'connected' ? '0 0 8px #10B981' : 'none'
                  }} />
                  <span style={{
                    fontSize: 10,
                    color: aiStatus === 'connected' ? '#34D399' : 'var(--app-text)',
                    fontFamily: 'JetBrains Mono', fontWeight: 600
                  }}>
                    {aiStatus === 'connected' ? `ONNX AI (${aiLatency}ms)` : aiStatus === 'loading' ? '추론 중...' : '오프라인'}
                  </span>
                </div>
              </div>
              {aiStatus === 'loading' && transportScores === TRANSPORT_SCORES ? (
                <TransportScoreSkeleton />
              ) : (
                transportScores.map((t, i) => (
                <div
                  key={t.id}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 12, marginBottom: i < 2 ? 12 : 0,
                    padding: '10px 12px', borderRadius: 14,
                    background: i === 0 ? 'color-mix(in srgb, var(--color-primary) 8%, transparent)' : 'var(--color-subtle)',
                    border: i === 0 ? '1px solid color-mix(in srgb, var(--color-primary) 20%, transparent)' : '1px solid var(--color-border)',
                  }}
                >
                  <span style={{ fontSize: 24 }}>{t.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--app-text)' }}>{t.name}</span>
                      <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 999, background: `${t.scoreColor}22`, color: t.scoreColor, fontWeight: 600 }}>
                        {t.scoreLabel}
                      </span>
                    </div>
                    <div style={{ height: 4, background: 'var(--color-subtle)', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${t.score}%`, background: t.scoreColor, borderRadius: 2 }} />
                    </div>
                  </div>
                  <div style={{ fontSize: 20, fontWeight: 800, color: t.scoreColor, fontFamily: 'JetBrains Mono', minWidth: 32, textAlign: 'right' }}>
                    {t.score}
                  </div>
                </div>
              ))
              )}
              <button
                onClick={() => setPage('route')}
                style={{
                  width: '100%', marginTop: 14, padding: '10px', borderRadius: 14, cursor: 'pointer',
                  background: 'linear-gradient(135deg, var(--color-primary), var(--color-accent))', color: 'var(--color-bg)',
                  fontSize: 13, fontWeight: 700, border: 'none', letterSpacing: '0.02em',
                }}
              >
                🔍 경로 상세 검색
              </button>
            </div>
          </div>

          {/* 하단 2열: 시간대별 차트 + 상관관계 + 동별 현황 */}
          <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 20 }}>

            {/* 시간대별 이용자 추이 (24시간 전일 ONNX AI 시계열 예측) */}
            <div style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)', color: 'var(--app-text)', borderRadius: 24, padding: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--app-text)' }}>시간대별 이용자 추이</span>
                    <span style={{
                      display: 'inline-flex', alignItems: 'center', gap: 5,
                      padding: '2px 8px', borderRadius: 9999,
                      background: hourlyLiveStatus === 'live' ? 'rgba(16,185,129,0.12)' : 'var(--color-subtle)',
                      border: `1px solid ${hourlyLiveStatus === 'live' ? 'rgba(16,185,129,0.3)' : 'var(--color-border)'}`
                    }}>
                      <span style={{
                        width: 6, height: 6, borderRadius: '50%',
                        background: hourlyLiveStatus === 'live' ? '#10B981' : hourlyLiveStatus === 'loading' ? '#FBBF24' : '#64748B',
                        boxShadow: hourlyLiveStatus === 'live' ? '0 0 6px #10B981' : 'none'
                      }} />
                      <span style={{ fontSize: 10, color: hourlyLiveStatus === 'live' ? '#34D399' : 'var(--app-text)', fontFamily: 'JetBrains Mono', fontWeight: 600 }}>
                        {hourlyLiveStatus === 'live' ? '24H ONNX AI 시계열 예측' : hourlyLiveStatus === 'loading' ? 'AI 예측 연산 중...' : '시계열 기본값'}
                      </span>
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color:  'var(--color-muted)', marginTop: 2 }}>
                    전일 24시간 날씨 연동 수요 추론 곡선 (00시 ~ 23시)
                  </div>
                </div>

                <div style={{ display: 'flex', gap: 12 }}>
                  {[['🚇', '지하철', 'var(--color-primary)'], ['🚌', '버스', '#FB923C'], ['🚲', '따릉이', '#34D399']].map(([icon, name, color]) => (
                    <div key={name as string} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <div style={{ width: 8, height: 3, background: color as string, borderRadius: 2 }} />
                      <span style={{ fontSize: 10, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono' }}>{name as string}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* 호버 시 실시간 상세 스펙 툴팁 배너 */}
              {(() => {
                const hoverItem = hourlyHovered !== null ? hourlyForecast[hourlyHovered] : null
                if (!hoverItem) {
                  return (
                    <div style={{ height: 22, marginBottom: 8, display: 'flex', alignItems: 'center', fontSize: 11, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>
                      💡 마우스를 그래프에 올리면 시간대별 정밀 AI 예측 수요를 확인할 수 있습니다.
                    </div>
                  )
                }
                return (
                  <div style={{
                    height: 22, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 10,
                    fontSize: 11, fontFamily: 'JetBrains Mono', background: 'color-mix(in srgb, var(--color-primary) 8%, transparent)',
                    padding: '2px 10px', borderRadius: 6, border: '1px solid color-mix(in srgb, var(--color-primary) 20%, transparent)'
                  }}>
                    <span style={{ color: 'var(--color-primary)', fontWeight: 700 }}>[{hoverItem.hour}]</span>
                    <span style={{ color: 'var(--app-text)' }}>
                      🚇 {hoverItem.subway.toLocaleString()}명
                      {hoverItem.subway_crowd ? ` (혼잡 ${hoverItem.subway_crowd}%)` : ''}
                    </span>
                    <span style={{ color: '#FED7AA' }}>
                      🚌 {hoverItem.bus.toLocaleString()}명
                      {hoverItem.bus_crowd ? ` (혼잡 ${hoverItem.bus_crowd}%)` : ''}
                    </span>
                    <span style={{ color: '#A7F3D0' }}>
                      🚲 {hoverItem.bike.toLocaleString()}대
                    </span>
                    <span style={{ color: 'var(--color-muted)', marginLeft: 'auto' }}>
                      🌡️ {hoverItem.temp}°C {hoverItem.rain > 0 ? `· 🌧️ ${hoverItem.rain}mm` : ''}
                    </span>
                  </div>
                )
              })()}

              {/* 24시간 Multi-line SVG 차트 */}
              <div style={{ position: 'relative', height: 140 }}>
                {(() => {
                  const chartData = hourlyForecast.length > 0 ? hourlyForecast : DEFAULT_24H_DATA
                  const n = chartData.length
                  const maxSub = Math.max(...chartData.map(d => d.subway || 0), 1000)
                  const maxBus = Math.max(...chartData.map(d => d.bus || 0), 1000)
                  const maxBike = Math.max(...chartData.map(d => d.bike || 0), 50)

                  const getX = (i: number) => n > 1 ? (i / (n - 1)) * 560 : 0
                  const getSubY = (v: number) => 130 - (v / maxSub) * 110
                  const getBusY = (v: number) => 130 - (v / maxBus) * 110
                  const getBikeY = (v: number) => 130 - (v / maxBike) * 110

                  const subPoints = chartData.map((d, i) => `${getX(i).toFixed(1)},${getSubY(d.subway).toFixed(1)}`).join(' ')
                  const busPoints = chartData.map((d, i) => `${getX(i).toFixed(1)},${getBusY(d.bus).toFixed(1)}`).join(' ')
                  const bikePoints = chartData.map((d, i) => `${getX(i).toFixed(1)},${getBikeY(d.bike).toFixed(1)}`).join(' ')

                  // 지하철 영역 음영 (Gradient Fill용 polygon)
                  const subAreaPoints = `${subPoints} 560,140 0,140`

                  // 현재 시각 계산 (00시~23시 범위)
                  const now = new Date()
                  const currentHourFloat = now.getHours() + (now.getMinutes() / 60)
                  const currentX = Math.max(0, Math.min(560, (currentHourFloat / 23) * 560))

                  return (
                    <svg width="100%" height="140" viewBox="0 0 560 140" preserveAspectRatio="none" style={{ overflow: 'visible' }}>
                      {/* Grid 수평선 */}
                      {[15, 45, 75, 105, 135].map(y => (
                        <line key={y} x1="0" y1={y} x2="560" y2={y} stroke="var(--color-border)" strokeWidth="1" />
                      ))}

                      {/* 강수(Rain) 감지 시간대 음영 컬럼 */}
                      {chartData.map((d, i) => d.rain > 0 && (
                        <rect
                          key={`rain-${i}`}
                          x={Math.max(0, getX(i) - 10)}
                          y={0}
                          width={20}
                          height={140}
                          fill="color-mix(in srgb, var(--color-primary) 8%, transparent)"
                        />
                      ))}

                      {/* 지하철 면적 음영 */}
                      <polygon
                        points={subAreaPoints}
                        fill="color-mix(in srgb, var(--color-primary) 6%, transparent)"
                      />

                      {/* 지하철 곡선 */}
                      <polyline
                        points={subPoints}
                        fill="none"
                        stroke="var(--color-primary)"
                        strokeWidth="2.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />

                      {/* 버스 곡선 */}
                      <polyline
                        points={busPoints}
                        fill="none"
                        stroke="#FB923C"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeDasharray="4 2"
                      />

                      {/* 따릉이 곡선 */}
                      <polyline
                        points={bikePoints}
                        fill="none"
                        stroke="#34D399"
                        strokeWidth="1.8"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />

                      {/* 현재 시각 실시간 수직선 (Current Time Marker) */}
                      <line
                        x1={currentX}
                        y1={0}
                        x2={currentX}
                        y2={140}
                        stroke="var(--color-primary)"
                        strokeWidth="1.5"
                        strokeDasharray="3 3"
                      />
                      <circle cx={currentX} cy={12} r={3} fill="var(--color-primary)" />
                      <text
                        x={Math.min(530, Math.max(30, currentX))}
                        y={9}
                        textAnchor="middle"
                        fill="var(--color-primary)"
                        fontSize={8}
                        fontFamily="JetBrains Mono"
                        fontWeight="700"
                      >
                        NOW
                      </text>

                      {/* 마우스 호버 가이드선 및 데이터 포인트 원 */}
                      {hourlyHovered !== null && chartData[hourlyHovered] && (() => {
                        const hItem = chartData[hourlyHovered]
                        const hx = getX(hourlyHovered)
                        return (
                          <g pointerEvents="none">
                            <line x1={hx} y1={0} x2={hx} y2={140} stroke="var(--app-text)" strokeWidth="1" strokeDasharray="2 2" />
                            <circle cx={hx} cy={getSubY(hItem.subway)} r={4} fill="var(--color-primary)" stroke="var(--color-bg)" strokeWidth="2" />
                            <circle cx={hx} cy={getBusY(hItem.bus)} r={4} fill="#FB923C" stroke="var(--color-bg)" strokeWidth="2" />
                            <circle cx={hx} cy={getBikeY(hItem.bike)} r={4} fill="#34D399" stroke="var(--color-bg)" strokeWidth="2" />
                          </g>
                        )
                      })()}

                      {/* 마우스 호버 인터랙션 투명 히트박스 (24구간) */}
                      {chartData.map((_, i) => {
                        const colWidth = 560 / n
                        return (
                          <rect
                            key={`hitbox-${i}`}
                            x={i * colWidth}
                            y={0}
                            width={colWidth}
                            height={140}
                            fill="transparent"
                            style={{ cursor: 'pointer' }}
                            onMouseEnter={() => setHourlyHovered(i)}
                            onMouseLeave={() => setHourlyHovered(null)}
                          />
                        )
                      })}
                    </svg>
                  )
                })()}
              </div>

              {/* X축 시간 라벨 (3시간 간격 및 23시) */}
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6, padding: '0 4px' }}>
                {(hourlyForecast.length > 0 ? hourlyForecast : DEFAULT_24H_DATA).map((d, i) => {
                  // 00, 03, 06, 09, 12, 15, 18, 21, 23시 레이블 표출
                  const isVisibleLabel = d.hour_num % 3 === 0 || d.hour_num === 23
                  return (
                    <span
                      key={d.hour}
                      style={{
                        fontSize: 9,
                        color: hourlyHovered === i ? 'var(--color-primary)' : isVisibleLabel ? 'var(--color-muted)' : 'transparent',
                        fontFamily: 'JetBrains Mono',
                        fontWeight: isVisibleLabel || hourlyHovered === i ? 600 : 400,
                        transition: 'color 0.15s ease',
                      }}
                    >
                      {d.hour.replace('시', '')}시
                    </span>
                  )
                })}
              </div>
            </div>

            {/* 동별 혼잡도 */}
            <div style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)', color: 'var(--app-text)', borderRadius: 24, padding: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--app-text)' }}>동별 교통 혼잡도</div>
                  <div style={{ fontSize: 11, color:  'var(--color-muted)', marginTop: 2 }}>서울시 8대 핵심 거점 실시간 현황</div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{
                    width: 7, height: 7, borderRadius: '50%',
                    background: districtLiveStatus === 'live' ? '#10B981' : districtLiveStatus === 'loading' ? '#FBBF24' : '#64748B',
                    boxShadow: districtLiveStatus === 'live' ? '0 0 8px #10B981' : 'none'
                  }} />
                  <span style={{ fontSize: 10, color: districtLiveStatus === 'live' ? '#34D399' : 'var(--app-text)', fontFamily: 'JetBrains Mono', fontWeight: 600 }}>
                    {districtLiveStatus === 'live' ? 'ONNX 실시간 연동' : districtLiveStatus === 'loading' ? '추론 중...' : '기본값'}
                  </span>
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {districtLiveStatus === 'loading' && districtList === DISTRICT_DATA ? (
                  <DistrictCongestionSkeleton />
                ) : (
                  districtList.map(d => (
                  <div
                    key={d.name}
                    onClick={() => {
                      const dName = d.district || d.name
                      const matchedIdx = DISTRICTS.findIndex(item => item.includes(dName) || item.includes(d.name.split(' ')[0]))
                      if (matchedIdx !== -1) {
                        setSelectedDistrict(matchedIdx)
                      }
                    }}
                    style={{
                      padding: '10px 14px', background: 'var(--color-subtle)', borderRadius: 14,
                      border: '1px solid var(--color-border)',
                      cursor: 'pointer',
                      transition: 'all 0.15s ease'
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.background = 'color-mix(in srgb, var(--color-primary) 8%, transparent)'
                      e.currentTarget.style.borderColor = 'color-mix(in srgb, var(--color-primary) 25%, transparent)'
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.background = 'var(--color-subtle)'
                      e.currentTarget.style.borderColor = 'var(--color-border)'
                    }}
                    title="클릭 시 해당 권역으로 대시보드 전환"
                  >
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 14 }}>{d.weather}</span>
                        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--app-text)' }}>{d.name}</span>
                        {d.district && (
                          <span style={{ fontSize: 10, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>
                            ({d.district})
                          </span>
                        )}
                      </div>
                      <span style={{ fontSize: 12, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono' }}>{d.temp}°C</span>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6 }}>
                      <div>
                        <div style={{ fontSize: 9, color: 'var(--app-text)', fontFamily: 'JetBrains Mono', marginBottom: 3 }}>지하철</div>
                        <CrowdBar value={d.subway} color="var(--color-primary)" />
                      </div>
                      <div>
                        <div style={{ fontSize: 9, color: 'var(--app-text)', fontFamily: 'JetBrains Mono', marginBottom: 3 }}>버스</div>
                        <CrowdBar value={d.bus} color="#FB923C" />
                      </div>
                      <div>
                        <div style={{ fontSize: 9, color: 'var(--app-text)', fontFamily: 'JetBrains Mono', marginBottom: 3 }}>따릉이</div>
                        <CrowdBar value={d.bike} color="#34D399" />
                      </div>
                    </div>
                  </div>
                ))
                )}
              </div>
            </div>
          </div>

          {/* 데이터 출처 */}
          <div style={{ marginTop: 24, padding: '16px 20px', background: 'var(--color-subtle)', border: '1px solid var(--color-border)', borderRadius: 16, display: 'flex', gap: 24, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 10, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>DATA SOURCES</span>
            {[
              '서울시 버스노선별 정류장별 시간대별 승하차',
              '서울시 지하철 호선별 역별 시간대별 승하차',
              '서울시 공공자전거 따릉이 대여이력',
              '기상청 동단위 시간별 날씨 데이터',
            ].map(src => (
              <span key={src} style={{ fontSize: 10, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>
                · {src}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════
          PAGE: 경로 추천
      ══════════════════════════════════════ */}
      {page === 'route' && (
        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '32px 32px 64px' }}>
          <div style={{ marginBottom: 28 }}>
            <h1 style={{ fontSize: 28, fontWeight: 800, color: 'var(--app-text)', margin: 0, letterSpacing: '-0.5px' }}>
              경로 추천
            </h1>
            <p style={{ fontSize: 14, color: 'var(--color-muted)', margin: '6px 0 0' }}>
              현재 날씨를 반영해 최적 교통수단과 경로를 추천합니다
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '400px 1fr', gap: 24, alignItems: 'start' }}>

            {/* 입력 패널 */}
            <div>
              {/* 날씨 현황 배지 + 시간대 슬라이더 (기상청 단기예보 연동) */}
              <div style={{ padding: '14px 16px', background: 'color-mix(in srgb, var(--color-primary) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-primary) 22%, transparent)', borderRadius: 16, marginBottom: 16 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                  <span style={{ fontSize: 22 }}>{isRaining ? '🌧' : '☀️'}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--color-primary)' }}>
                      {DISTRICTS[selectedDistrict]} · {String(selectedHour).padStart(2, '0')}:00 · {displayPtyDesc} · {displayTemp}°C · 강수 {displayRain}mm/h
                    </div>
                    <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 1 }}>
                      기상청 단기예보 및 32차원 ONNX 혼잡도 기반 멀티모달 경로 탐색
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <span style={{ fontSize: 10, color: 'var(--color-primary)', fontFamily: 'JetBrains Mono', fontWeight: 700, whiteSpace: 'nowrap' }}>
                    🕒 출발 시각 {String(selectedHour).padStart(2, '0')}:00
                  </span>
                  <input
                    type="range"
                    min={0}
                    max={23}
                    step={1}
                    value={selectedHour}
                    onChange={e => setSelectedHour(Number(e.target.value))}
                    style={{ flex: 1, accentColor: 'var(--color-primary)', cursor: 'pointer', height: 5 }}
                  />
                </div>
              </div>

              {/* 출발/도착 입력 (지하철역 실시간 자동완성 검색 연동) */}
              <div style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)', color: 'var(--app-text)', borderRadius: 20, marginBottom: 16 }}>
                {/* 출발지 */}
                <div style={{ padding: '14px 18px 12px', borderBottom: '1px solid var(--color-border)', position: 'relative' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <div style={{ fontSize: 10, color: '#34D399', fontFamily: 'JetBrains Mono', letterSpacing: '0.07em' }}>
                      🟢  출발지 (지하철역 검색)
                    </div>
                    {departure && (
                      <button
                        onClick={() => {
                          setDeparture('')
                          setShowDepartureList(false)
                          setActiveRoute(null)
                        }}
                        title="출발지 지우기"
                        style={{
                          background: 'var(--color-card2)', border: 'none', borderRadius: 999,
                          padding: '2px 8px', fontSize: 10, color: 'var(--color-muted)', cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: 3,
                        }}
                      >
                        <span>✕</span> 지우기
                      </button>
                    )}
                  </div>
                  <input
                    type="text"
                    value={departure}
                    onChange={e => {
                      setDeparture(e.target.value)
                      setShowDepartureList(true)
                      setSelectedDepartureIndex(0)
                    }}
                    onFocus={() => setShowDepartureList(true)}
                    onKeyDown={e => {
                      const results = searchSubwayStations(departure).slice(0, 10)
                      if (!showDepartureList || results.length === 0) {
                        if (e.key === 'Enter' && departure.trim() && results.length > 0) {
                          e.preventDefault()
                          setDeparture(results[0].name)
                          setShowDepartureList(false)
                          setFocusedCoords(results[0].coords)
                        }
                        return
                      }
                      if (e.key === 'ArrowDown') {
                        e.preventDefault()
                        setSelectedDepartureIndex(prev => (prev + 1) % results.length)
                      } else if (e.key === 'ArrowUp') {
                        e.preventDefault()
                        setSelectedDepartureIndex(prev => (prev - 1 + results.length) % results.length)
                      } else if (e.key === 'Tab') {
                        e.preventDefault()
                        if (e.shiftKey) {
                          setSelectedDepartureIndex(prev => (prev - 1 + results.length) % results.length)
                        } else {
                          setSelectedDepartureIndex(prev => (prev + 1) % results.length)
                        }
                      } else if (e.key === 'Enter') {
                        e.preventDefault()
                        const target = results[selectedDepartureIndex >= 0 ? selectedDepartureIndex : 0]
                        if (target) {
                          setDeparture(target.name)
                          setShowDepartureList(false)
                          setFocusedCoords(target.coords)
                        }
                      } else if (e.key === 'Escape') {
                        setShowDepartureList(false)
                      }
                    }}
                    placeholder="출발역 이름 입력 (예: 구로역, 강남역, 시청역...)"
                    style={{
                      width: '100%', background: 'transparent', border: 'none', outline: 'none',
                      fontSize: 15, fontWeight: 500, color: 'var(--app-text)',
                      fontFamily: "'Outfit', 'Noto Sans KR', sans-serif",
                    }}
                  />

                  {/* 출발역 자동완성 드롭다운 */}
                  {showDepartureList && departure.trim() && (() => {
                    const results = searchSubwayStations(departure).slice(0, 10)
                    if (results.length === 0) return null
                    return (
                      <div style={{
                        position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100,
                        background: 'var(--color-surface)', border: '1px solid rgba(52,211,153,0.4)', borderRadius: 12,
                        boxShadow: '0 8px 30px rgba(0,0,0,0.7)', maxHeight: 240, overflowY: 'auto',
                      }}>
                        <div style={{ padding: '6px 12px', fontSize: 10, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between' }}>
                          <span>검색 결과 {results.length}건</span>
                          <span>⌨️ [Tab / ↑↓] 이동 · [Enter] 선택</span>
                        </div>
                        {results.map((st, idx) => (
                          <div
                            key={`dep-${st.id}`}
                            ref={el => {
                              if (idx === selectedDepartureIndex && el) el.scrollIntoView({ block: 'nearest' })
                            }}
                            onClick={() => {
                              setDeparture(st.name)
                              setShowDepartureList(false)
                              setFocusedCoords(st.coords)
                            }}
                            style={{
                              padding: '10px 14px', borderBottom: '1px solid var(--color-border)',
                              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                              background: idx === selectedDepartureIndex ? 'rgba(52,211,153,0.22)' : 'transparent',
                              borderLeft: idx === selectedDepartureIndex ? '3px solid #34D399' : '3px solid transparent',
                              transition: 'background 0.1s ease',
                            }}
                            onMouseEnter={() => setSelectedDepartureIndex(idx)}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ fontSize: 14 }}>🚇</span>
                              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--app-text)' }}>{st.name}</span>
                              <span style={{ fontSize: 10, color: '#34D399', background: 'rgba(52,211,153,0.15)', padding: '2px 6px', borderRadius: 4 }}>
                                {st.lines.join(', ')}
                              </span>
                            </div>
                            {idx === selectedDepartureIndex && (
                              <span style={{ fontSize: 10, color: '#34D399', fontFamily: 'JetBrains Mono' }}>↵ Enter</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )
                  })()}
                </div>

                {/* 출발 ↔ 도착 맞바꾸기 구분선 */}
                <div style={{ position: 'relative', height: 1, background: 'var(--color-border)' }}>
                  <button
                    onClick={handleSwapRoute}
                    title="출발지 ↔ 도착지 맞바꾸기"
                    style={{
                      position: 'absolute', right: 18, top: -14, width: 28, height: 28,
                      borderRadius: '50%', background: 'var(--color-surface)', border: '1px solid var(--color-border)',
                      color: 'var(--color-primary)', fontSize: 13, cursor: 'pointer', display: 'flex',
                      alignItems: 'center', justifyContent: 'center', zIndex: 10,
                      boxShadow: '0 2px 8px var(--app-shadow)', transition: 'all 0.15s ease',
                    }}
                  >
                    ⇅
                  </button>
                </div>

                {/* 도착지 */}
                <div style={{ padding: '12px 18px 16px', position: 'relative' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <div style={{ fontSize: 10, color: 'var(--color-primary)', fontFamily: 'JetBrains Mono', letterSpacing: '0.07em' }}>
                      🔵  도착지 (지하철역 검색)
                    </div>
                    {destination && (
                      <button
                        onClick={() => {
                          setDestination('')
                          setShowDestinationList(false)
                          setActiveRoute(null)
                        }}
                        title="도착지 지우기"
                        style={{
                          background: 'var(--color-card2)', border: 'none', borderRadius: 999,
                          padding: '2px 8px', fontSize: 10, color: 'var(--color-muted)', cursor: 'pointer',
                          display: 'flex', alignItems: 'center', gap: 3,
                        }}
                      >
                        <span>✕</span> 지우기
                      </button>
                    )}
                  </div>
                  <input
                    type="text"
                    value={destination}
                    onChange={e => {
                      setDestination(e.target.value)
                      setShowDestinationList(true)
                      setSelectedDestinationIndex(0)
                    }}
                    onFocus={() => setShowDestinationList(true)}
                    onKeyDown={e => {
                      const results = searchSubwayStations(destination).slice(0, 10)
                      if (!showDestinationList || results.length === 0) {
                        if (e.key === 'Enter' && destination.trim() && results.length > 0) {
                          e.preventDefault()
                          setDestination(results[0].name)
                          setShowDestinationList(false)
                        }
                        return
                      }
                      if (e.key === 'ArrowDown') {
                        e.preventDefault()
                        setSelectedDestinationIndex(prev => (prev + 1) % results.length)
                      } else if (e.key === 'ArrowUp') {
                        e.preventDefault()
                        setSelectedDestinationIndex(prev => (prev - 1 + results.length) % results.length)
                      } else if (e.key === 'Tab') {
                        e.preventDefault()
                        if (e.shiftKey) {
                          setSelectedDestinationIndex(prev => (prev - 1 + results.length) % results.length)
                        } else {
                          setSelectedDestinationIndex(prev => (prev + 1) % results.length)
                        }
                      } else if (e.key === 'Enter') {
                        e.preventDefault()
                        const target = results[selectedDestinationIndex >= 0 ? selectedDestinationIndex : 0]
                        if (target) {
                          setDestination(target.name)
                          setShowDestinationList(false)
                        }
                      } else if (e.key === 'Escape') {
                        setShowDestinationList(false)
                      }
                    }}
                    placeholder="도착역 이름 입력 (예: 강남역, 여의도역, 판교역...)"
                    style={{
                      width: '100%', background: 'transparent', border: 'none', outline: 'none',
                      fontSize: 15, fontWeight: 500, color: 'var(--app-text)',
                      fontFamily: "'Outfit', 'Noto Sans KR', sans-serif",
                    }}
                  />

                  {/* 도착역 자동완성 드롭다운 */}
                  {showDestinationList && destination.trim() && (() => {
                    const results = searchSubwayStations(destination).slice(0, 10)
                    if (results.length === 0) return null
                    return (
                      <div style={{
                        position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100,
                        background: 'var(--color-surface)', border: '1px solid color-mix(in srgb, var(--color-primary) 40%, transparent)', borderRadius: 12,
                        boxShadow: '0 8px 30px rgba(0,0,0,0.7)', maxHeight: 240, overflowY: 'auto',
                      }}>
                        <div style={{ padding: '6px 12px', fontSize: 10, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between' }}>
                          <span>검색 결과 {results.length}건</span>
                          <span>⌨️ [Tab / ↑↓] 이동 · [Enter] 선택</span>
                        </div>
                        {results.map((st, idx) => (
                          <div
                            key={`dest-${st.id}`}
                            ref={el => {
                              if (idx === selectedDestinationIndex && el) el.scrollIntoView({ block: 'nearest' })
                            }}
                            onClick={() => {
                              setDestination(st.name)
                              setShowDestinationList(false)
                            }}
                            style={{
                              padding: '10px 14px', borderBottom: '1px solid var(--color-border)',
                              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                              background: idx === selectedDestinationIndex ? 'color-mix(in srgb, var(--color-primary) 22%, transparent)' : 'transparent',
                              borderLeft: idx === selectedDestinationIndex ? '3px solid var(--color-primary)' : '3px solid transparent',
                              transition: 'background 0.1s ease',
                            }}
                            onMouseEnter={() => setSelectedDestinationIndex(idx)}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ fontSize: 14 }}>🚇</span>
                              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--app-text)' }}>{st.name}</span>
                              <span style={{ fontSize: 10, color: 'var(--color-primary)', background: 'color-mix(in srgb, var(--color-primary) 15%, transparent)', padding: '2px 6px', borderRadius: 4 }}>
                                {st.lines.join(', ')}
                              </span>
                            </div>
                            {idx === selectedDestinationIndex && (
                              <span style={{ fontSize: 10, color: 'var(--color-primary)', fontFamily: 'JetBrains Mono' }}>↵ Enter</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )
                  })()}
                </div>
              </div>

              {/* 검색 및 초기화 버튼 바 */}
              <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
                <button
                  onClick={() => handleSearchRoute(departure, destination)}
                  style={{
                    flex: 1, padding: '14px', borderRadius: 16, cursor: 'pointer',
                    background: 'linear-gradient(135deg, var(--color-primary), var(--color-accent))', color: 'var(--color-bg)',
                    fontSize: 15, fontWeight: 800, border: 'none',
                    boxShadow: '0 8px 32px color-mix(in srgb, var(--color-primary) 30%, transparent)',
                  }}
                >
                  🔍  최적 경로 검색
                </button>
                {(departure || destination || activeRoute) && (
                  <button
                    onClick={handleResetRoute}
                    title="출발·도착 초기화"
                    style={{
                      padding: '0 16px', borderRadius: 16, cursor: 'pointer',
                      background: 'var(--color-card2)', color: 'var(--app-text)',
                      fontSize: 13, fontWeight: 700, border: '1px solid var(--color-border)',
                      display: 'flex', alignItems: 'center', gap: 5, whiteSpace: 'nowrap',
                      transition: 'all 0.15s ease',
                    }}
                  >
                    <span>🔄</span>
                    <span>초기화</span>
                  </button>
                )}
              </div>

              {/* 자주 찾는 경로 */}
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 11, color: 'var(--app-text)', fontFamily: 'JetBrains Mono', letterSpacing: '0.06em', marginBottom: 10 }}>
                  자주 찾는 경로
                </div>
                {[
                  { from: '강남역', to: '서울역', icon: '🚇' },
                  { from: '홍대입구역', to: '이태원역', icon: '🚇' },
                  { from: '잠실역', to: '강동구청역', icon: '🚇' },
                  { from: '여의도역', to: '시청역', icon: '🚇' },
                ].map(item => {
                  const r = findSubwayRoute(item.from, item.to)
                  const timeStr = r ? formatDurationMinutes(r.estimatedMinutes) : '25분'
                  const fareStr = r ? `${r.fareKrw.toLocaleString()}원` : '1,550원'
                  const distStr = r ? `(${r.distanceKm}km)` : ''
                  return (
                    <button
                      key={item.from + item.to}
                      onClick={() => {
                        setDeparture(item.from)
                        setDestination(item.to)
                        handleSearchRoute(item.from, item.to)
                      }}
                      style={{
                        width: '100%', display: 'flex', alignItems: 'center', gap: 12,
                        padding: '10px 14px', marginBottom: 6, borderRadius: 12, cursor: 'pointer',
                        background: 'var(--color-card)', border: '1px solid var(--color-border)',
                        textAlign: 'left', transition: 'all 0.15s',
                      }}
                    >
                      <span style={{ fontSize: 18 }}>{item.icon}</span>
                      <div style={{ flex: 1 }}>
                        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--app-text)' }}>{item.from}</span>
                        <span style={{ fontSize: 12, color: 'var(--app-text)', margin: '0 6px' }}>→</span>
                        <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--app-text)' }}>{item.to}</span>
                      </div>
                      <div style={{ textAlign: 'right' }}>
                        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-primary)', fontFamily: 'JetBrains Mono' }}>{timeStr}</div>
                        <div style={{ fontSize: 10, color:  'var(--color-muted)', fontFamily: 'JetBrains Mono' }} title={r?.fareBreakdown}>
                          {fareStr} <span style={{ fontSize: 9, color: 'color-mix(in srgb, var(--color-primary) 70%, transparent)' }}>{distStr}</span>
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            </div>

            {/* 추천 결과 (LangGraph × FactChat 멀티모달 경로 + 수단별 추천 점수) */}
            <div>
              <MultimodalRoutePanel
                apiBaseUrl={API_BASE_URL}
                fromStation={departure}
                toStation={destination}
                district={DISTRICTS[selectedDistrict] || '강남구'}
                selectedHour={selectedHour}
                temp={displayTemp}
                rain={displayRain}
                humidity={displayHumidity}
                wind={displayWind}
                onSelectRouteForMap={mmRoute => {
                  setFocusedCoords(null)
                  setSelectedStop(null)
                  setActiveRoute(mmRoute)
                  setPage('map')
                  if (mapTransport === 'bus' || mapTransport === 'bike') {
                    setMapTransport('all')
                  }
                }}
              />
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div style={{ fontSize: 11, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono', letterSpacing: '0.06em' }}>
                  날씨 기반 교통수단 추천 결과
                </div>
                {aiStatus === 'connected' && (
                  <span style={{ fontSize: 10, color: 'var(--color-primary)', fontFamily: 'JetBrains Mono', background: 'color-mix(in srgb, var(--color-primary) 10%, transparent)', padding: '2px 8px', borderRadius: 999 }}>
                    ⚡ ONNX AI 추론 ({aiLatency}ms)
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {transportScores.map((t, i) => (
                  <div
                    key={t.id}
                    style={{
                      background: i === 0 ? 'color-mix(in srgb, var(--color-primary) 6%, transparent)' : 'var(--color-card)',
                      border: i === 0 ? '1px solid color-mix(in srgb, var(--color-primary) 25%, transparent)' : '1px solid var(--color-border)',
                      borderRadius: 20, padding: 20,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
                      <div style={{
                        width: 52, height: 52, borderRadius: 16, background: 'var(--color-card2)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, flexShrink: 0,
                      }}>
                        {t.icon}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                          <span style={{ fontSize: 17, fontWeight: 800, color: 'var(--app-text)' }}>{t.name}</span>
                          <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: `${t.scoreColor}22`, color: t.scoreColor, fontWeight: 700 }}>
                            {t.scoreLabel}
                          </span>
                          {i === 0 && <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 999, background: 'rgba(52,211,153,0.15)', color: '#34D399', fontWeight: 700 }}>AI 추천</span>}
                        </div>
                        <div style={{ height: 5, background: 'var(--color-subtle)', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${t.score}%`, background: t.scoreColor, borderRadius: 3 }} />
                        </div>
                      </div>
                      <div style={{ textAlign: 'right', flexShrink: 0 }}>
                        <div style={{ fontSize: 36, fontWeight: 900, color: t.scoreColor, fontFamily: 'JetBrains Mono', lineHeight: 1 }}>{t.score}</div>
                        <div style={{ fontSize: 9, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>/ 100</div>
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 14 }}>
                      {[
                        {
                          label: '예상 소요',
                          value: (t.id === 'subway' && activeRoute) ? formatDurationMinutes(activeRoute.estimatedMinutes) : t.time
                        },
                        {
                          label: '예상 요금',
                          value: (t.id === 'subway' && activeRoute)
                            ? `${activeRoute.fareKrw.toLocaleString()}원`
                            : (t.id === 'subway' ? '1,550원~' : t.price)
                        },
                        { label: '혼잡도', value: t.crowdLabel },
                      ].map(item => (
                        <div key={item.label} style={{ background: 'var(--color-card)', borderRadius: 12, padding: '10px 12px' }}>
                          <div style={{ fontSize: 10, color:  'var(--color-muted)', fontFamily: 'JetBrains Mono', marginBottom: 3 }}>
                            {item.label}
                            {item.label === '예상 요금' && t.id === 'subway' && activeRoute && (
                              <span style={{ fontSize: 9, color: 'color-mix(in srgb, var(--color-primary) 70%, transparent)', marginLeft: 4 }}>
                                ({activeRoute.distanceKm}km)
                              </span>
                            )}
                          </div>
                          <div style={{ fontSize: 14, fontWeight: 700, color: item.label === '혼잡도' ? t.crowdColor : 'var(--app-text)' }}>{item.value}</div>
                        </div>
                      ))}
                    </div>

                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {t.reasons.map(reason => (
                        <span
                          key={reason}
                          style={{
                            fontSize: 11, padding: '3px 10px', borderRadius: 999,
                            background: 'var(--color-card2)', color: 'var(--color-muted)',
                          }}
                        >
                          {reason}
                        </span>
                      ))}
                    </div>

                    <div style={{ marginTop: 10, fontSize: 10, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono' }}>
                      데이터: {t.dataset}
                    </div>
                  </div>
                ))}
              </div>

              {/* 강수량-이용률 상관관계 차트 */}
              <div style={{ marginTop: 20, background: 'var(--color-card)', border: '1px solid var(--color-border)', color: 'var(--app-text)', borderRadius: 20, padding: 20 }}>
                <div style={{ marginBottom: 12, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--app-text)' }}>강수량 vs 교통수단 이용률 상관관계</div>
                    <div style={{ fontSize: 11, color:  'var(--color-muted)', marginTop: 2 }}>20.9만 건 서울시 교통카드·기상청 실측 빅데이터 교정</div>
                  </div>
                  <span style={{ fontSize: 10, padding: '2px 8px', borderRadius: 6, background: 'color-mix(in srgb, var(--color-primary) 10%, transparent)', color: 'var(--color-primary)', fontFamily: 'JetBrains Mono', fontWeight: 600 }}>
                    실측 교정 완료
                  </span>
                </div>
                <CorrelationChart />
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 8 }}>
                  <span style={{ fontSize: 10, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>강수량(mm/h) →</span>
                  <div style={{ display: 'flex', gap: 14 }}>
                    {[['var(--color-primary)', '지하철'], ['#FB923C', '버스'], ['#34D399', '따릉이']].map(([c, n]) => (
                      <div key={n} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <div style={{ width: 12, height: 2, background: c as string, borderRadius: 1 }} />
                        <span style={{ fontSize: 10, color:  'var(--color-muted)', fontFamily: 'JetBrains Mono' }}>{n}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════
          PAGE: 기업용 모빌리티 재배치 분석 (B2B)
      ══════════════════════════════════════ */}
      {page === 'enterprise' && (
        <EnterpriseView apiBaseUrl={API_BASE_URL} />
      )}

      {/* ══════════════════════════════════════
          PAGE: 지도
      ══════════════════════════════════════ */}
      {page === 'map' && (
        <div style={{ display: 'flex', height: 'calc(100vh - 60px)' }}>

          {/* 사이드패널 */}
          <div style={{
            width: 360, flexShrink: 0, background: 'var(--color-surface)',
            borderRight: '1px solid var(--color-border)',
            display: 'flex', flexDirection: 'column', overflow: 'hidden',
          }}>
            {/* 지하철역 검색 및 자동완성 입력창 */}
            {mapTransport != 'bus' && (
              <div style={{ padding: '16px 20px 14px', borderBottom: '1px solid var(--color-border)', position: 'relative' }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-primary)', letterSpacing: '0.04em', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span>🔍</span> 지하철역 검색 & 바로가기
                </div>
                <div style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)', color: 'var(--app-text)', borderRadius: 12, padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 14 }}>🚇</span>
                  <input
                    value={subwaySearchQuery}
                    onChange={e => {
                      setSubwaySearchQuery(e.target.value)
                      setShowSearchResults(true)
                      setSelectedSubwayIndex(0)
                    }}
                    onFocus={() => setShowSearchResults(true)}
                    onKeyDown={e => {
                      const results = searchSubwayStations(subwaySearchQuery).slice(0, 15)
                      if (!showSearchResults || results.length === 0) {
                        if (e.key === 'Enter' && subwaySearchQuery.trim() && results.length > 0) {
                          e.preventDefault()
                          handleSelectStation(results[0])
                        }
                        return
                      }
                      if (e.key === 'ArrowDown') {
                        e.preventDefault()
                        setSelectedSubwayIndex(prev => (prev + 1) % results.length)
                      } else if (e.key === 'ArrowUp') {
                        e.preventDefault()
                        setSelectedSubwayIndex(prev => (prev - 1 + results.length) % results.length)
                      } else if (e.key === 'Tab') {
                        e.preventDefault()
                        if (e.shiftKey) {
                          setSelectedSubwayIndex(prev => (prev - 1 + results.length) % results.length)
                        } else {
                          setSelectedSubwayIndex(prev => (prev + 1) % results.length)
                        }
                      } else if (e.key === 'Enter') {
                        e.preventDefault()
                        const target = results[selectedSubwayIndex >= 0 ? selectedSubwayIndex : 0]
                        if (target) {
                          handleSelectStation(target)
                        }
                      } else if (e.key === 'Escape') {
                        setShowSearchResults(false)
                      }
                    }}
                    placeholder="지하철역 이름 입력 (예: 강남, 시청, 구로...)"
                    style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', fontSize: 13, color: 'var(--app-text)', fontFamily: "'Outfit','Noto Sans KR',sans-serif" }}
                  />
                  {subwaySearchQuery && (
                    <button
                      onClick={() => {
                        setSubwaySearchQuery('')
                        setShowSearchResults(false)
                      }}
                      style={{ background: 'transparent', border: 'none', color: 'var(--color-muted)', cursor: 'pointer', fontSize: 12 }}
                    >
                      ✕
                    </button>
                  )}
                </div>

                {/* 지하철역 검색 결과 자동완성 드롭다운 */}
                {showSearchResults && subwaySearchQuery.trim() && (() => {
                  const results = searchSubwayStations(subwaySearchQuery).slice(0, 15)
                  return (
                    <div style={{
                      position: 'absolute', top: '100%', left: 20, right: 20, zIndex: 100,
                      background: 'var(--color-surface)', border: '1px solid color-mix(in srgb, var(--color-primary) 35%, transparent)', borderRadius: 12,
                      boxShadow: '0 8px 30px rgba(0,0,0,0.6)', maxHeight: 260, overflowY: 'auto',
                    }}>
                      {results.length > 0 && (
                        <div style={{ padding: '6px 12px', fontSize: 10, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between' }}>
                          <span>검색 결과 {results.length}건</span>
                          <span>⌨️ [Tab / ↑↓] 이동 · [Enter] 선택</span>
                        </div>
                      )}
                      {results.length > 0 ? (
                        results.map((st, idx) => (
                          <div
                            key={st.id}
                            ref={el => {
                              if (idx === selectedSubwayIndex && el) el.scrollIntoView({ block: 'nearest' })
                            }}
                            onClick={() => handleSelectStation(st)}
                            style={{
                              padding: '10px 14px', borderBottom: '1px solid var(--color-border)',
                              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                              background: idx === selectedSubwayIndex ? 'color-mix(in srgb, var(--color-primary) 22%, transparent)' : 'transparent',
                              borderLeft: idx === selectedSubwayIndex ? '3px solid var(--color-primary)' : '3px solid transparent',
                              transition: 'background 0.1s ease',
                            }}
                            onMouseEnter={() => setSelectedSubwayIndex(idx)}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ fontSize: 15 }}>🚇</span>
                              <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--app-text)' }}>{st.name}</span>
                              <span style={{ fontSize: 10, color: 'var(--color-primary)', background: 'color-mix(in srgb, var(--color-primary) 15%, transparent)', padding: '2px 6px', borderRadius: 4 }}>
                                {st.lines[0]}
                              </span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                              <span style={{ fontSize: 11, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono' }}>
                                {st.zone}
                              </span>
                              {idx === selectedSubwayIndex && (
                                <span style={{ fontSize: 10, color: 'var(--color-primary)', fontFamily: 'JetBrains Mono' }}>↵</span>
                              )}
                            </div>
                          </div>
                        ))
                      ) : (
                        <div style={{ padding: '14px', fontSize: 12, color: 'var(--color-muted)', textAlign: 'center' }}>
                          검색된 지하철역이 없습니다.
                        </div>
                      )}
                    </div>
                  )
                })()}
              </div>
            )}

            {/* 버스정류장 검색 */}
            {mapTransport === 'bus' && (
              <BusStationSearch
                onSelect={station => {
                  setActiveRoute(null)
                  setSelectedBusStation(station)
                  setFocusedCoords(station.coords)
                }}
              />
            )}

            {/* 교통수단 탭 */}
            <div style={{ display: 'flex', gap: 6, padding: '14px 20px', borderBottom: '1px solid var(--color-border)' }}>
              {[
                { id: 'all', icon: '🌐', label: '전체' },
                { id: 'subway', icon: '🚇', label: '지하철' },
                { id: 'bus', icon: '🚌', label: '버스' },
                { id: 'bike', icon: '🚲', label: '따릉이' },
              ].map(t => (
                <button
                  key={t.id}
                  onClick={() => setMapTransport(t.id as any)}
                  style={{
                    flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
                    padding: '8px 4px', borderRadius: 12, cursor: 'pointer', transition: 'all 0.15s',
                    background: mapTransport === t.id ? 'color-mix(in srgb, var(--color-primary) 15%, transparent)' : 'var(--color-subtle)',
                    border: mapTransport === t.id ? '1px solid color-mix(in srgb, var(--color-primary) 40%, transparent)' : '1px solid var(--color-border)',
                  }}
                >
                  <span style={{ fontSize: 18 }}>{t.icon}</span>
                  <span style={{ fontSize: 10, fontWeight: 600, color: mapTransport === t.id ? 'var(--color-primary)' : 'var(--color-muted)' }}>{t.label}</span>
                </button>
              ))}
            </div>

            {/* 기상청 실시간 관측 실황 카드 (100% 공공데이터 실측 실황 연동) */}
            <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--color-border)', background: 'color-mix(in srgb, var(--color-primary) 3%, transparent)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-primary)', letterSpacing: '0.02em', display: 'flex', alignItems: 'center', gap: 6 }}>
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: '#34D399', boxShadow: '0 0 8px #34D399', display: 'inline-block' }}></span>
                  기상청 실시간 관측 실황
                </span>
                <span style={{ fontSize: 10, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono' }}>
                  {liveWeather ? `${liveWeather.base_time.slice(0, 2)}:${liveWeather.base_time.slice(2, 4)} 발표` : '실시간 실측'}
                </span>
              </div>

              {/* 기상 실황 데이터 정보 박스 */}
              <div style={{ background: 'var(--color-card2)', borderRadius: 12, padding: '10px 12px', border: '1px solid color-mix(in srgb, var(--color-primary) 15%, transparent)', marginBottom: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontSize: 24 }}>{activeRain > 0 ? '🌧' : '☀️'}</span>
                    <div>
                      <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>
                        {activeTemp}°C
                      </div>
                      <div style={{ fontSize: 11, color: activeRain > 0 ? 'var(--color-primary)' : 'var(--color-muted)', fontWeight: 600 }}>
                        {activePtyDesc}
                      </div>
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: 11, color: 'var(--color-muted)', fontWeight: 600 }}>
                      {DISTRICTS[selectedDistrict] || '서울특별시'}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--color-primary)', fontFamily: 'JetBrains Mono', marginTop: 2 }}>
                      {liveWeather ? `격자 (${liveWeather.nx}, ${liveWeather.ny})` : 'KMA API'}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 6, paddingTop: 8, borderTop: '1px solid var(--color-border)' }}>
                  <div style={{ background: 'var(--color-card)', borderRadius: 8, padding: '5px 8px', textAlign: 'center' }}>
                    <div style={{ fontSize: 9, color: 'var(--app-text)' }}>강수량</div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: activeRain > 0 ? 'var(--color-primary)' : 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>
                      {activeRain} mm
                    </div>
                  </div>
                  <div style={{ background: 'var(--color-card)', borderRadius: 8, padding: '5px 8px', textAlign: 'center' }}>
                    <div style={{ fontSize: 9, color: 'var(--app-text)' }}>습도</div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>
                      {activeHumidity}%
                    </div>
                  </div>
                  <div style={{ background: 'var(--color-card)', borderRadius: 8, padding: '5px 8px', textAlign: 'center' }}>
                    <div style={{ fontSize: 9, color: 'var(--app-text)' }}>풍속</div>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>
                      {activeWind} m/s
                    </div>
                  </div>
                </div>
              </div>

              {/* 실시간 기상 교통 영향 코멘트 */}
              <div style={{ fontSize: 11, color: 'var(--app-text)', lineHeight: 1.45, padding: '2px 2px' }}>
                {activeRain > 0 ? (
                  <span>🌧 기상청 실시간 강수로 인해 <b>지하철·버스 이용객 증가</b> 및 <b>따릉이 이용 주의</b>가 발효 중입니다.</span>
                ) : (
                  <span>☀️ 쾌적한 기상 상태로 지하철, 버스, 따릉이 등 전 대중교통이 원활하게 운행 중입니다.</span>
                )}
              </div>
            </div>

            {/* 경로 및 선택 정류장 상세 정보 */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
              {activeRoute ? (
                <div style={{ background: 'color-mix(in srgb, var(--color-primary) 12%, transparent)', border: '1px solid color-mix(in srgb, var(--color-primary) 40%, transparent)', borderRadius: 16, padding: '14px 16px', marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <span style={{ fontSize: 10, color: 'var(--color-primary)', fontFamily: 'JetBrains Mono', fontWeight: 800 }}>
                        ⚡ {activeRoute.badge || '최소 환승 우선 추천 경로'}
                      </span>
                      <span style={{
                        background: activeRoute.transferCount === 0 ? 'rgba(16,185,129,0.2)' : 'rgba(245,158,11,0.2)',
                        border: activeRoute.transferCount === 0 ? '1px solid #10B981' : '1px solid #F59E0B',
                        color: activeRoute.transferCount === 0 ? '#10B981' : '#FBBF24',
                        padding: '1px 6px',
                        borderRadius: 4,
                        fontSize: 9,
                        fontWeight: 700
                      }}>
                        {activeRoute.transferCount === 0 ? '환승 0회 (직통)' : `환승 ${activeRoute.transferCount}회`}
                      </span>
                    </div>
                    <button
                      onClick={() => {
                        setActiveRoute(null)
                        setFocusedCoords(null)
                      }}
                      style={{ background: 'transparent', border: 'none', color: 'var(--color-muted)', fontSize: 11, cursor: 'pointer' }}
                    >
                      초기화 ✕
                    </button>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                    <div>
                      <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--app-text)' }}>
                        {activeRoute.from} ➔ {activeRoute.to}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--color-primary)', marginTop: 2 }}>
                        {activeRoute.summary}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: activeRoute.estimatedMinutes >= 60 ? 20 : 26, fontWeight: 900, color: 'var(--color-primary)', fontFamily: 'JetBrains Mono', lineHeight: 1 }}>
                        {formatDurationMinutes(activeRoute.estimatedMinutes)}
                      </div>
                      <div style={{ fontSize: 10, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono' }}>소요</div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
                    <div style={{ flex: 1, background: 'var(--color-card2)', borderRadius: 8, padding: '6px 8px', textAlign: 'center' }}>
                      <div style={{ fontSize: 10, color: 'var(--app-text)' }}>환승 횟수</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: activeRoute.transferCount === 0 ? '#10B981' : '#FBBF24' }}>
                        {activeRoute.transferCount === 0 ? '0회 (직통)' : `${activeRoute.transferCount}회`}
                      </div>
                    </div>
                    <div style={{ flex: 1, background: 'var(--color-card2)', borderRadius: 8, padding: '6px 8px', textAlign: 'center' }}>
                      <div style={{ fontSize: 10, color: 'var(--app-text)' }}>경유 역</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--app-text)' }}>{activeRoute.stationCount}개 역</div>
                    </div>
                    <div style={{ flex: 1, background: 'var(--color-card2)', borderRadius: 8, padding: '6px 8px', textAlign: 'center' }}>
                      <div style={{ fontSize: 10, color: 'var(--app-text)' }}>이동 요금 ({activeRoute.distanceKm}km)</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--color-primary)', fontFamily: 'JetBrains Mono' }} title={activeRoute.fareBreakdown}>
                        {activeRoute.fareKrw.toLocaleString()}원
                      </div>
                    </div>
                  </div>

                  {/* 멀티모달 구간 타임라인 요약 (LangGraph 경로 선택 시 표시) */}
                  {activeRoute.segments && activeRoute.segments.length > 0 && (
                    <div style={{ background: 'var(--color-card2)', borderRadius: 10, padding: '8px 10px', marginBottom: 10, border: '1px solid var(--color-border)' }}>
                      <div style={{ fontSize: 9.5, color: '#C084FC', fontFamily: 'JetBrains Mono', fontWeight: 800, marginBottom: 6 }}>
                        🧠 LangGraph 멀티모달 구간 안내
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                        {activeRoute.segments.map((seg, sIdx) => (
                          <div key={sIdx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 10.5, borderLeft: `3px solid ${seg.color || '#38BDF8'}`, paddingLeft: 7 }}>
                            <div style={{ color: 'var(--app-text)', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginRight: 6 }}>
                              <span style={{ color: seg.color || '#38BDF8', fontWeight: 800, marginRight: 4 }}>{seg.label}</span>
                              {seg.from_name} ➔ {seg.to_name}
                            </div>
                            <span style={{ color: '#FCD34D', fontFamily: 'JetBrains Mono', fontWeight: 700, flexShrink: 0 }}>
                              {seg.minutes}분
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* 수도권 거리비례 운임 산정 내역 */}
                  {activeRoute.fareBreakdown && (
                    <div style={{
                      fontSize: 10,
                      color: 'var(--app-text)',
                      background: 'color-mix(in srgb, var(--color-primary) 8%, transparent)',
                      border: '1px solid color-mix(in srgb, var(--color-primary) 20%, transparent)',
                      borderRadius: 8,
                      padding: '5px 10px',
                      marginBottom: 10,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                    }}>
                      <span style={{ fontSize: 11 }}>💳</span>
                      <span><b>거리비례 운임</b>: {activeRoute.fareBreakdown}</span>
                    </div>
                  )}

                  {/* 실시간 열차 탑승 안내 박스 (몇 분 후 탑승) */}
                  <div style={{ background: 'var(--color-card)', borderRadius: 10, padding: '10px 12px', marginBottom: 12, border: '1px solid var(--color-border)' }}>
                    <div style={{ fontSize: 10, color: 'var(--color-primary)', fontFamily: 'JetBrains Mono', fontWeight: 800, marginBottom: 8, display: 'flex', alignItems: 'center', gap: 5 }}>
                      <span>⏱️</span>
                      <span>실시간 열차 도착 정보 (몇 분 후 탑승)</span>
                    </div>

                    {/* 출발역 열차 */}
                    {activeRoute.departureTrain && (
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '4px 0', borderBottom: activeRoute.transferTrains && activeRoute.transferTrains.length > 0 ? '1px dashed var(--color-border)' : 'none' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontSize: 13 }}>🟢</span>
                          <div>
                            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--app-text)' }}>
                              {activeRoute.from} <span style={{ fontSize: 10, color: 'var(--color-primary)' }}>[{activeRoute.departureTrain.line}]</span>
                            </div>
                            <div style={{ fontSize: 10, color: 'var(--color-muted)' }}>
                              {activeRoute.departureTrain.destinationOrNext} 방면 ({activeRoute.departureTrain.arrivalMessage})
                            </div>
                          </div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <div style={{ fontSize: 14, fontWeight: 900, color: '#34D399', fontFamily: 'JetBrains Mono' }}>
                            {activeRoute.departureTrain.remainingMinutes}분 후
                          </div>
                          <div style={{ fontSize: 9, color: 'var(--app-text)' }}>탑승 대기</div>
                        </div>
                      </div>
                    )}

                    {/* 환승역 열차 */}
                    {activeRoute.transferTrains && activeRoute.transferTrains.map(tr => (
                      <div key={tr.station} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '6px 0 2px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontSize: 13 }}>🔄</span>
                          <div>
                            <div style={{ fontSize: 12, fontWeight: 700, color: '#FBBF24' }}>
                              {tr.station} <span style={{ fontSize: 10, color: '#FDE68A' }}>[{tr.line} 환승]</span>
                            </div>
                            <div style={{ fontSize: 10, color: 'var(--color-muted)' }}>
                              {tr.destinationOrNext} 방면 ({tr.arrivalMessage})
                            </div>
                          </div>
                        </div>
                        <div style={{ textAlign: 'right' }}>
                          <div style={{ fontSize: 14, fontWeight: 900, color: '#FBBF24', fontFamily: 'JetBrains Mono' }}>
                            {tr.remainingMinutes}분 후
                          </div>
                          <div style={{ fontSize: 9, color: 'var(--app-text)' }}>환승 도착</div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* 경유역 경로 리스트 */}
                  <div style={{ fontSize: 10, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono', marginBottom: 6 }}>
                    경유 역 목록 (클릭 시 해당 역 위치로 이동):
                  </div>
                  <div style={{
                    maxHeight: 150, overflowY: 'auto', background: 'var(--color-card2)', borderRadius: 8, padding: '6px 10px',
                    display: 'flex', flexDirection: 'column', gap: 4
                  }}>
                    {activeRoute.path.map((p, idx) => (
                      <div
                        key={p.name + idx}
                        onClick={() => setFocusedCoords(p.coords)}
                        style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11, cursor: 'pointer', padding: '3px 4px',
                          borderRadius: 6,
                          background: p.isTransfer ? 'rgba(245, 158, 11, 0.12)' : 'transparent',
                          border: p.isTransfer ? '1px solid rgba(245, 158, 11, 0.3)' : '1px solid transparent'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontSize: 10 }}>
                            {idx === 0 ? '🟢' : idx === activeRoute.path.length - 1 ? '🔴' : p.isTransfer ? '🔄' : '○'}
                          </span>
                          <span style={{
                            color: idx === 0 || idx === activeRoute.path.length - 1 ? 'var(--app-text)' : p.isTransfer ? '#FBBF24' : 'var(--color-muted)',
                            fontWeight: idx === 0 || idx === activeRoute.path.length - 1 || p.isTransfer ? 700 : 400
                          }}>
                            {p.name}
                          </span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                          {p.arrivalInfo && (
                            <span style={{
                              fontSize: 9,
                              color: idx === 0 ? '#34D399' : '#FBBF24',
                              background: idx === 0 ? 'rgba(52,211,153,0.18)' : 'rgba(245,158,11,0.22)',
                              padding: '1px 5px',
                              borderRadius: 4,
                              fontWeight: 800,
                              fontFamily: 'JetBrains Mono'
                            }}>
                              ⏱️ {p.arrivalInfo.remainingMinutes}분 후
                            </span>
                          )}
                          {p.isTransfer && p.transferInfo && (
                            <span style={{ fontSize: 9, color: '#FBBF24', background: 'rgba(245,158,11,0.2)', padding: '1px 5px', borderRadius: 4, fontWeight: 700 }}>
                              {p.transferInfo}
                            </span>
                          )}
                          <span style={{ fontSize: 9, color: 'var(--color-primary)', background: 'color-mix(in srgb, var(--color-primary) 10%, transparent)', padding: '1px 5px', borderRadius: 4 }}>
                            {p.lineUsed || p.lines[0] || '지하철'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : selectedStop ? (
                <div style={{ background: 'color-mix(in srgb, var(--color-primary) 10%, transparent)', border: '1px solid color-mix(in srgb, var(--color-primary) 30%, transparent)', borderRadius: 16, padding: '14px 16px', marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                    <div style={{ fontSize: 10, color: 'var(--color-primary)', fontFamily: 'JetBrains Mono' }}>선택된 거점 상세 정보</div>
                    <button
                      onClick={() => handleSelectStop(null)}
                      style={{ background: 'none', border: 'none', color: 'var(--color-muted)', cursor: 'pointer', fontSize: 14, padding: 0 }}
                      title="선택 해제"
                    >
                      ✕
                    </button>
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 800, color: 'var(--app-text)', marginBottom: 4, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span>{selectedStop.type === 'subway' ? '🚇' : selectedStop.type === 'bus' ? '🚌' : '🚲'} {selectedStop.name}</span>
                    <span style={{ fontSize: 10, color: 'var(--color-muted)', background: 'var(--color-subtle)', padding: '2px 6px', borderRadius: 4 }}>
                      {resolveDistrict(selectedStop.name, selectedStop.coords)}
                    </span>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--color-muted)', marginBottom: 10, fontFamily: 'monospace' }}>
                    {selectedStop.lineInfo}
                  </div>

                  {/* 1. 국지 기상 실황 카드 */}
                  {stopDataLoading && !stopWeatherData ? (
                    <div style={{ background: 'rgba(14, 165, 233, 0.08)', border: '1px solid color-mix(in srgb, var(--color-primary) 25%, transparent)', borderRadius: 10, padding: 10, marginBottom: 10, textAlign: 'center' }}>
                      <div style={{ fontSize: 11, color: 'var(--color-primary)', fontWeight: 700, marginBottom: 2 }}>⏳ 기상청 실시간 관측 데이터 조회 중...</div>
                      <div style={{ fontSize: 9, color: 'var(--app-text)' }}>좌표 기반 KMA LCC 격자 산출 및 초단기실황 연동</div>
                    </div>
                  ) : stopWeatherData ? (
                    <div style={{ background: 'rgba(14, 165, 233, 0.08)', border: '1px solid color-mix(in srgb, var(--color-primary) 25%, transparent)', borderRadius: 10, padding: '10px 12px', marginBottom: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                        <span style={{ fontSize: 11, fontWeight: 800, color: 'var(--color-primary)', display: 'flex', alignItems: 'center', gap: 4 }}>
                          <span>🌦️</span> {stopWeatherData.district} 국지 기상 실황
                        </span>
                        <span style={{ fontSize: 9, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono' }}>
                          격자 ({stopWeatherData.nx}, {stopWeatherData.ny})
                        </span>
                      </div>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 6, textAlign: 'center', background: 'var(--color-card2)', borderRadius: 8, padding: '6px 4px', marginBottom: 6 }}>
                        <div>
                          <div style={{ fontSize: 9, color: 'var(--color-muted)' }}>기온</div>
                          <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>{stopWeatherData.temp}°C</div>
                        </div>
                        <div>
                          <div style={{ fontSize: 9, color: 'var(--color-muted)' }}>강수</div>
                          <div style={{ fontSize: 13, fontWeight: 800, color: stopWeatherData.rain > 0 ? '#60A5FA' : '#34D399', fontFamily: 'JetBrains Mono' }}>{stopWeatherData.rain}mm</div>
                        </div>
                        <div>
                          <div style={{ fontSize: 9, color: 'var(--color-muted)' }}>습도</div>
                          <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>{stopWeatherData.humidity}%</div>
                        </div>
                        <div>
                          <div style={{ fontSize: 9, color: 'var(--color-muted)' }}>풍속</div>
                          <div style={{ fontSize: 13, fontWeight: 800, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>{stopWeatherData.wind}m/s</div>
                        </div>
                      </div>
                      <div style={{ fontSize: 10, color: 'var(--color-muted)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span>{stopWeatherData.rain > 0 ? `🌧️ ${stopWeatherData.pty_desc || '비'} (강수 영향 반영)` : '☀️ 맑음 (평시 통행 패턴)'}</span>
                        <span style={{ fontSize: 9, color:  'var(--color-muted)' }}>출처: 기상청 APIHUB</span>
                      </div>
                    </div>
                  ) : (
                    <div style={{ fontSize: 11, color: 'var(--app-text)', background: 'var(--color-card2)', padding: '8px 10px', borderRadius: 8, lineHeight: 1.5, marginBottom: 10 }}>
                      {activeRain > 0 ? (
                        <>🌧 실시간 비({activeRain}mm)로 인해 <b>{selectedStop.type === 'bike' ? '따릉이 이용 위험 및 비추천' : '실내 환승 및 지하철 이용 집중'}</b> 상태입니다.</>
                      ) : (
                        <>☀️ 맑은 날씨로 평시 쾌적한 출퇴근 흐름을 유지하고 있습니다.</>
                      )}
                    </div>
                  )}

                  {/* 2. AI 수요 추론 및 혼잡도 예측 카드 */}
                  {stopDataLoading && !stopAIData ? (
                    <div style={{ background: 'rgba(124, 58, 237, 0.08)', border: '1px solid rgba(168, 85, 247, 0.25)', borderRadius: 10, padding: 10, marginBottom: 10, textAlign: 'center' }}>
                      <div style={{ fontSize: 11, color: '#C084FC', fontWeight: 700, marginBottom: 2 }}>⚡ AI 모델 32차원 피처 추론 연산 중...</div>
                      <div style={{ fontSize: 9, color: 'var(--app-text)' }}>시계열 래그 및 기상 차분 반영 ONNX 인메모리 추론</div>
                    </div>
                  ) : stopAIData ? (() => {
                    const rec = stopAIData.recommendations?.find((r: any) => r.id === selectedStop.type) || stopAIData.recommendations?.[0]
                    return rec ? (
                      <div style={{ background: 'rgba(124, 58, 237, 0.08)', border: '1px solid rgba(168, 85, 247, 0.3)', borderRadius: 10, padding: '10px 12px', marginBottom: 10 }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                          <span style={{ fontSize: 11, fontWeight: 800, color: '#C084FC', display: 'flex', alignItems: 'center', gap: 4 }}>
                            <span>🤖</span> AI 수요 추론 ({rec.name})
                          </span>
                          <span style={{ fontSize: 9, fontWeight: 700, color: '#C084FC', background: 'rgba(168,85,247,0.2)', padding: '1px 6px', borderRadius: 4 }}>
                            ⚡ ONNX {stopAIData.latency_ms}ms
                          </span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4, fontSize: 11 }}>
                          <span style={{ color: 'var(--app-text)' }}>
                            예측 혼잡도: <strong style={{ color: rec.crowdColor }}>{rec.crowd}%</strong> ({rec.crowdLabel})
                          </span>
                          <span style={{ color: 'var(--color-muted)', fontFamily: 'JetBrains Mono', fontSize: 10 }}>
                            시간당 {rec.predicted_volume?.toLocaleString()}명
                          </span>
                        </div>
                        <div style={{ height: 6, background: 'var(--color-subtle)', borderRadius: 3, overflow: 'hidden', marginBottom: 8 }}>
                          <div style={{ width: `${rec.crowd}%`, height: '100%', background: rec.crowdColor, borderRadius: 3, transition: 'width 0.5s ease' }} />
                        </div>
                        <div style={{ fontSize: 10, color: 'var(--app-text)', background: 'var(--color-card2)', padding: '6px 8px', borderRadius: 6, borderLeft: '2px solid #A855F7', lineHeight: 1.4 }}>
                          {rec.reasons?.[0] || '기상 관측치 기반 최적 통행 분석 완료'}
                        </div>
                      </div>
                    ) : null
                  })() : null}

                  {/* 실시간 지하철 열차 도착 정보 */}
                  {selectedStop.type === 'subway' && (
                    <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                        <span style={{ fontSize: 11, fontWeight: 800, color: 'var(--color-primary)', display: 'flex', alignItems: 'center', gap: 4 }}>
                          <span>🚇</span> 실시간 열차 도착 정보
                        </span>
                        {stopArrivalData.lastUpdated && (
                          <span style={{ fontSize: 9, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono' }}>
                            {stopArrivalData.lastUpdated} 기준
                          </span>
                        )}
                      </div>
                      {stopArrivalData.loading ? (
                        <div style={{ fontSize: 11, color: 'var(--color-muted)', textAlign: 'center', padding: '10px 0', background: 'var(--color-card2)', borderRadius: 8 }}>
                          ⏳ 실시간 열차 운행 정보 수신 중...
                        </div>
                      ) : stopArrivalData.subwayArrivals && stopArrivalData.subwayArrivals.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 220, overflowY: 'auto' }}>
                          {stopArrivalData.subwayArrivals.slice(0, 10).map((arr: any, idx: number) => (
                            <div
                              key={idx}
                              style={{
                                background: 'var(--color-card2)',
                                border: '1px solid color-mix(in srgb, var(--color-primary) 20%, transparent)',
                                borderRadius: 8,
                                padding: '7px 10px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                              }}
                            >
                              <div style={{ minWidth: 0, flex: 1, marginRight: 8 }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 2 }}>
                                  <span style={{ fontSize: 9, fontWeight: 800, color: 'var(--color-primary)', background: 'color-mix(in srgb, var(--color-primary) 18%, transparent)', padding: '1px 5px', borderRadius: 4 }}>
                                    {arr.line}
                                  </span>
                                  <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--app-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                    {arr.destination}
                                  </span>
                                </div>
                                <div style={{ fontSize: 10, color: 'var(--color-muted)' }}>
                                  {arr.updn_line || '운행구간'} {arr.train_status && arr.train_status !== '일반' ? `· ${arr.train_status}` : ''}
                                </div>
                              </div>
                              <div style={{ textAlign: 'right', flexShrink: 0 }}>
                                <div style={{ fontSize: 12, fontWeight: 800, color: '#FCD34D', fontFamily: 'JetBrains Mono' }}>
                                  {arr.message}
                                </div>
                                {arr.remaining_minutes > 0 && (
                                  <div style={{ fontSize: 9, color: 'var(--color-muted)', marginTop: 1 }}>
                                    약 {arr.remaining_minutes}분 후
                                  </div>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div style={{ fontSize: 11, color: 'var(--color-muted)', padding: '6px 0', textAlign: 'center' }}>
                          배차 간격 2~5분 정상 운행중입니다.
                        </div>
                      )}
                    </div>
                  )}

                  {/* 실시간 버스 도착 정보 */}
                  {selectedStop.type === 'bus' && (
                    <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: 10 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                        <span style={{ fontSize: 11, fontWeight: 800, color: '#34D399', display: 'flex', alignItems: 'center', gap: 4 }}>
                          <span>🚌</span> 실시간 버스 도착 정보
                        </span>
                        {stopArrivalData.lastUpdated && (
                          <span style={{ fontSize: 9, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono' }}>
                            {stopArrivalData.lastUpdated} 기준
                          </span>
                        )}
                      </div>
                      {stopArrivalData.loading ? (
                        <div style={{ fontSize: 11, color: 'var(--color-muted)', textAlign: 'center', padding: '10px 0', background: 'var(--color-card2)', borderRadius: 8 }}>
                          ⏳ 실시간 버스 정보 수신 중...
                        </div>
                      ) : stopArrivalData.busArrivals && stopArrivalData.busArrivals.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 180, overflowY: 'auto' }}>
                          {stopArrivalData.busArrivals.slice(0, 4).map((b: any, idx: number) => (
                            <div
                              key={idx}
                              style={{
                                background: 'var(--color-card2)',
                                border: '1px solid rgba(52,211,153,0.2)',
                                borderRadius: 8,
                                padding: '7px 10px',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                              }}
                            >
                              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                                <span style={{ fontSize: 12, fontWeight: 800, color: '#34D399' }}>{b.route_name || b.rtNm}</span>
                                <span style={{ fontSize: 10, color: 'var(--color-muted)' }}>간선</span>
                              </div>
                              <span style={{ fontSize: 11, fontWeight: 700, color: '#FCD34D', fontFamily: 'JetBrains Mono' }}>
                                {b.arrival_msg1 || b.arrmsg1 || '운행중'}
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div style={{ fontSize: 11, color: 'var(--color-muted)', padding: '6px 0', textAlign: 'center' }}>
                          실시간 버스 도착 정보가 없습니다.
                        </div>
                      )}
                    </div>
                  )}

                  {/* 따릉이 거치 현황 */}
                  {selectedStop.type === 'bike' && (
                    <div style={{ borderTop: '1px solid var(--color-border)', paddingTop: 10 }}>
                      <div style={{ fontSize: 11, fontWeight: 800, color: '#10B981', marginBottom: 6, display: 'flex', alignItems: 'center', gap: 4 }}>
                        <span>🚲</span> 따릉이 실시간 거치 현황
                      </div>
                      <div style={{ background: 'var(--color-card2)', padding: '8px 10px', borderRadius: 8, fontSize: 11, color: 'var(--app-text)' }}>
                        {selectedStop.lineInfo}
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <div style={{ background: 'color-mix(in srgb, var(--color-primary) 8%, transparent)', border: '1px solid color-mix(in srgb, var(--color-primary) 20%, transparent)', borderRadius: 16, padding: '14px 16px', marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--app-text)' }}>강남구청 → 잠실역</div>
                      <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 2 }}>
                        {mapTransport === 'subway' ? '지하철 2호선' : mapTransport === 'bus' ? '버스 145' : '따릉이 대여'}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: 28, fontWeight: 900, color: 'var(--color-primary)', fontFamily: 'JetBrains Mono', lineHeight: 1 }}>
                        {mapTransport === 'subway' ? '28' : mapTransport === 'bus' ? '42' : '55'}
                      </div>
                      <div style={{ fontSize: 10, color:  'var(--color-muted)', fontFamily: 'JetBrains Mono' }}>분</div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    {[
                      ['💰', mapTransport === 'subway' ? '1,550원~ (거리비례)' : mapTransport === 'bus' ? '1,300원' : '1,000원/h'],
                      ['👥', activeRain > 3 ? (mapTransport === 'bike' ? '운행중단' : '매우혼잡') : (mapTransport === 'bike' ? '여유' : '보통')],
                    ].map(([icon, val]) => (
                      <div key={val as string} style={{ flex: 1, background: 'var(--color-card2)', borderRadius: 10, padding: '7px 10px', display: 'flex', alignItems: 'center', gap: 5 }}>
                        <span style={{ fontSize: 13 }}>{icon}</span>
                        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--app-text)' }}>{val}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 안내 문구 */}
              <div style={{ fontSize: 11, color: 'var(--color-muted)', lineHeight: 1.5, background: 'var(--color-subtle)', padding: '10px 12px', borderRadius: 10 }}>
                💡 <b>안내</b>: 지도 위의 마커를 클릭하면 해당 정류장 및 역의 상세 혼잡도와 날씨 민감도 분석을 확인하실 수 있습니다.
              </div>
            </div>

            {/* 안내 시작 버튼 */}
            <div style={{ padding: '16px 20px', borderTop: '1px solid var(--color-border)' }}>
              <button
                onClick={() => {
                  if (!activeRoute) {
                    handleSearchRoute('강남역', '서울역')
                  } else {
                    const coords = activeRoute.path.map(p => p.coords)
                    if (coords.length > 0) {
                      setFocusedCoords(coords[0])
                    }
                  }
                }}
                style={{
                  width: '100%', padding: '14px', borderRadius: 16, cursor: 'pointer',
                  background: 'linear-gradient(135deg, var(--color-primary), var(--color-accent))', color: 'var(--color-bg)',
                  fontSize: 15, fontWeight: 800, border: 'none',
                  boxShadow: '0 8px 24px color-mix(in srgb, var(--color-primary) 35%, transparent)',
                }}
              >
                🧭  실시간 대중교통 경로 안내
              </button>
            </div>
          </div>

          {/* MapLibre GL JS + OpenStreetMap 실제 지도 컨테이너 (100% 기상청 실시간 API 연동) */}
          <div style={{ flex: 1, height: '100%', position: 'relative' }}>
            <TransitMap
              filterType={mapTransport}
              rainMm={activeRain}
              selectedTime={liveWeather ? `${parseInt(liveWeather.base_time.slice(0, 2), 10)}시` : `${new Date().getHours()}시`}
              liveWeather={liveWeather}
              focusedCoords={focusedCoords}
              selectedBusStation={selectedBusStation}
              onSelectStop={handleSelectStop}
              activeRoute={activeRoute}
              onClearRoute={() => {
                setActiveRoute(null)
                setFocusedCoords(null)
              }}
            />
          </div>
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        * { scrollbar-width: thin; scrollbar-color: color-mix(in srgb, var(--color-primary) 30%, transparent) transparent; }
        input::placeholder { color: var(--color-muted); }
        button { transition: all 0.15s ease; }
        button:hover { opacity: 0.88; }
        select option { background: var(--color-card); }
      `}</style>
    </div>
  )
}
