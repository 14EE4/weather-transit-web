import { useState, useEffect } from 'react'
import TransitMap, { TransitStop } from './TransitMap'
import { logWeatherApiCall, logBusApiCall, logSubwayApiCall, logAIPredictionCall } from './apiLogger'
import { searchSubwayStations, SubwayStation } from './subwayData'
import { findSubwayRoute, TransitRouteResult } from './subwayGraph'

type Page = 'main' | 'route' | 'map'

// ── 서울 행정동 데이터 (샘플) ──
const DISTRICTS = [
  '강남구 역삼동', '강남구 삼성동', '강남구 논현동',
  '서초구 서초동', '서초구 반포동',
  '마포구 서교동', '마포구 합정동',
  '송파구 잠실동', '송파구 방이동',
  '영등포구 여의도동', '영등포구 당산동',
  '중구 명동', '중구 을지로동',
]

// ── 시간대별 날씨 + 교통 통합 데이터 ──
const HOURLY_DATA = [
  { hour: '06시', temp: 11, rain: 0, humidity: 68, wind: 1.8, bus: 4200, subway: 18000, bike: 320 },
  { hour: '07시', temp: 12, rain: 0, humidity: 70, wind: 2.1, bus: 12800, subway: 62000, bike: 510 },
  { hour: '08시', temp: 13, rain: 0, humidity: 72, wind: 2.4, bus: 18400, subway: 95000, bike: 780 },
  { hour: '09시', temp: 14, rain: 1.2, humidity: 82, wind: 3.2, bus: 14200, subway: 78000, bike: 210 },
  { hour: '10시', temp: 14, rain: 2.8, humidity: 86, wind: 3.8, bus: 9600, subway: 52000, bike: 85 },
  { hour: '11시', temp: 13, rain: 3.1, humidity: 88, wind: 4.1, bus: 8200, subway: 44000, bike: 62 },
  { hour: '12시', temp: 14, rain: 1.5, humidity: 85, wind: 3.5, bus: 11400, subway: 56000, bike: 140 },
  { hour: '13시', temp: 15, rain: 0.8, humidity: 80, wind: 3.0, bus: 10800, subway: 51000, bike: 190 },
  { hour: '14시', temp: 15, rain: 0, humidity: 76, wind: 2.8, bus: 9200, subway: 46000, bike: 380 },
]

// ── 교통수단 추천 스코어 (비 오는 날 기준) ──
const TRANSPORT_SCORES = [
  {
    id: 'subway',
    icon: '🚇',
    name: '지하철',
    score: 97,
    scoreLabel: '최우선 추천',
    scoreColor: '#38BDF8',
    reasons: ['날씨 영향 없음', '정시성 99.2%', '배차 간격 2~5분'],
    time: '28분',
    price: '1,400원',
    crowd: 52,
    crowdLabel: '보통',
    crowdColor: '#34D399',
    dataset: '지하철 호선별 역별 시간대별 승하차',
  },
  {
    id: 'bus',
    icon: '🚌',
    name: '버스',
    score: 68,
    scoreLabel: '주의 필요',
    scoreColor: '#FB923C',
    reasons: ['강수 시 평균 8분 지연', '승객 분산 효과', '우산 필수'],
    time: '42분',
    price: '1,300원',
    crowd: 78,
    crowdLabel: '혼잡',
    crowdColor: '#FB923C',
    dataset: '버스노선별 정류장별 시간대별 승하차',
  },
  {
    id: 'bike',
    icon: '🚲',
    name: '따릉이',
    score: 14,
    scoreLabel: '비추천',
    scoreColor: '#94A3B8',
    reasons: ['강수량 2.8mm — 운행 위험', '미끄러짐 사고 위험', '반납 지연 빈번'],
    time: '55분',
    price: '1,000원/시간',
    crowd: 8,
    crowdLabel: '여유',
    crowdColor: '#94A3B8',
    dataset: '공공자전거 따릉이 대여이력',
  },
]

// ── 강우량-이용객 상관관계 데이터 ──
const CORRELATION_DATA = [
  { rain: 0, subway: 82, bus: 76, bike: 100 },
  { rain: 0.5, subway: 85, bus: 74, bike: 78 },
  { rain: 1.0, subway: 90, bus: 68, bike: 52 },
  { rain: 2.0, subway: 96, bus: 60, bike: 28 },
  { rain: 3.0, subway: 100, bus: 54, bike: 12 },
  { rain: 5.0, subway: 98, bus: 42, bike: 4 },
]

// ── 동별 교통 혼잡 현황 ──
const DISTRICT_DATA = [
  { name: '역삼동', bus: 82, subway: 91, bike: 45, weather: '🌧', temp: 14 },
  { name: '삼성동', bus: 65, subway: 78, bike: 38, weather: '🌧', temp: 14 },
  { name: '서교동', bus: 71, subway: 63, bike: 88, weather: '🌧', temp: 13 },
  { name: '잠실동', bus: 55, subway: 94, bike: 31, weather: '🌦', temp: 15 },
  { name: '여의도동', bus: 88, subway: 72, bike: 24, weather: '🌧', temp: 14 },
  { name: '명동', bus: 92, subway: 85, bike: 18, weather: '🌧', temp: 13 },
]

function CrowdBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.08)' }}>
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${value}%`, background: color }} />
      </div>
      <span style={{ fontSize: 11, fontFamily: 'JetBrains Mono', color, minWidth: 28 }}>{value}%</span>
    </div>
  )
}

function StatCard({ label, value, unit, color, icon }: { label: string; value: string | number; unit?: string; color: string; icon: string }) {
  return (
    <div className="rounded-2xl p-4" style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
      <div className="flex items-center gap-2 mb-2">
        <span style={{ fontSize: 16 }}>{icon}</span>
        <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono', letterSpacing: '0.04em' }}>{label}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span style={{ fontSize: 26, fontWeight: 800, color, fontFamily: 'JetBrains Mono', lineHeight: 1 }}>{value}</span>
        {unit && <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)' }}>{unit}</span>}
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
              <div className="w-full rounded-sm transition-all" style={{ height: `${(d.subway / maxSubway) * 80}px`, background: hovered === i ? '#38BDF8' : 'rgba(56,189,248,0.5)', minHeight: 2 }} />
            </div>
          </div>
        ))}
      </div>
      {/* Labels */}
      <div className="flex gap-1.5 mt-1">
        {data.map((d, i) => (
          <div key={d.hour} className="flex-1 text-center" style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', fontFamily: 'JetBrains Mono' }}>
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
            background: '#1C2B50',
            border: '1px solid rgba(56,189,248,0.3)',
            whiteSpace: 'nowrap',
          }}
        >
          <div style={{ fontSize: 11, fontWeight: 700, color: '#38BDF8', marginBottom: 2 }}>{data[hovered].hour}</div>
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.6)', fontFamily: 'JetBrains Mono' }}>
            🚇 {data[hovered].subway.toLocaleString()}명
          </div>
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.6)', fontFamily: 'JetBrains Mono' }}>
            🚌 {data[hovered].bus.toLocaleString()}명
          </div>
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.6)', fontFamily: 'JetBrains Mono' }}>
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

// ── 상관관계 시각화 ──
function CorrelationChart() {
  return (
    <div className="relative h-28">
      <svg width="100%" height="100%" viewBox="0 0 300 112" preserveAspectRatio="none">
        {/* Grid */}
        {[0,28,56,84,112].map(y => (
          <line key={y} x1="0" y1={y} x2="300" y2={y} stroke="rgba(255,255,255,0.06)" strokeWidth="1" />
        ))}
        {/* Subway line */}
        <polyline
          points={CORRELATION_DATA.map((d, i) => `${(i / (CORRELATION_DATA.length-1)) * 300},${112 - (d.subway / 100) * 100}`).join(' ')}
          fill="none" stroke="#38BDF8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        />
        {/* Bus line */}
        <polyline
          points={CORRELATION_DATA.map((d, i) => `${(i / (CORRELATION_DATA.length-1)) * 300},${112 - (d.bus / 100) * 100}`).join(' ')}
          fill="none" stroke="#FB923C" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
        />
        {/* Bike line */}
        <polyline
          points={CORRELATION_DATA.map((d, i) => `${(i / (CORRELATION_DATA.length-1)) * 300},${112 - (d.bike / 100) * 100}`).join(' ')}
          fill="none" stroke="#94A3B8" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="4 3"
        />
      </svg>
      {/* X axis labels */}
      <div className="flex justify-between mt-1">
        {CORRELATION_DATA.map(d => (
          <span key={d.rain} style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', fontFamily: 'JetBrains Mono' }}>{d.rain}</span>
        ))}
      </div>
    </div>
  )
}

const getInitialPage = (): Page => {
  if (typeof window !== 'undefined') {
    const hash = window.location.hash.replace(/^#/, '') as Page
    if (hash === 'main' || hash === 'route' || hash === 'map') return hash
    try {
      const saved = localStorage.getItem('weather_transit_page') as Page
      if (saved === 'main' || saved === 'route' || saved === 'map') return saved
    } catch {}
  }
  return 'main'
}

export default function App() {
  const [page, setPage] = useState<Page>(getInitialPage)
  const [selectedDistrict, setSelectedDistrict] = useState(0)
  const [selectedHour, setSelectedHour] = useState(4) // 10시 기본
  const [departure, setDeparture] = useState('')
  const [destination, setDestination] = useState('')
  const [mapTransport, setMapTransport] = useState<'all' | 'subway' | 'bus' | 'bike'>('all')
  const [districtQuery, setDistrictQuery] = useState('')
  const [rainSimulation, setRainSimulation] = useState<number>(2.8)
  const [simulatedTime, setSimulatedTime] = useState<string>('08시')
  const [selectedStop, setSelectedStop] = useState<TransitStop | null>(null)
  const [subwaySearchQuery, setSubwaySearchQuery] = useState('')
  const [focusedCoords, setFocusedCoords] = useState<[number, number] | null>(null)
  const [showSearchResults, setShowSearchResults] = useState(false)
  const [showDepartureList, setShowDepartureList] = useState(false)
  const [showDestinationList, setShowDestinationList] = useState(false)

  // 활성 경로 탐색 결과 상태
  const [activeRoute, setActiveRoute] = useState<TransitRouteResult | null>(null)

  // 키보드(Arrow, Tab, Enter) 탐색용 인덱스 상태
  const [selectedSubwayIndex, setSelectedSubwayIndex] = useState(0)
  const [selectedDepartureIndex, setSelectedDepartureIndex] = useState(0)
  const [selectedDestinationIndex, setSelectedDestinationIndex] = useState(0)

  // 경로 검색 실행 함수 (출발역-도착역 최단 경로 계산 후 지도 탭으로 전환)
  const handleSearchRoute = (from = departure, to = destination) => {
    if (!from.trim() || !to.trim()) {
      alert('출발역과 도착역을 입력해주세요.')
      return
    }
    const route = findSubwayRoute(from, to)
    if (route) {
      setActiveRoute(route)
      setPage('map')
      if (mapTransport === 'bus' || mapTransport === 'bike') {
        setMapTransport('all')
      }
    } else {
      alert(`'${from}'에서 '${to}'까지의 지하철 경로를 찾을 수 없습니다. 역 이름을 정확히 입력해주세요.`)
    }
  }

  // 탭 상태 로컬 스토리지 및 URL 해시 동기화 (새로고침 시 현재 탭 유지)
  useEffect(() => {
    try {
      localStorage.setItem('weather_transit_page', page)
    } catch {}
    if (window.location.hash.replace(/^#/, '') !== page) {
      window.location.hash = page
    }
  }, [page])

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

  // ── 지하철역 선택 시 지도 카메라 이동 및 실시간 도착/AI 분석 로깅 ──
  const handleSelectStation = (station: SubwayStation) => {
    setActiveRoute(null)
    setSubwaySearchQuery(station.name)
    setFocusedCoords(station.coords)
    setShowSearchResults(false)
    setSelectedStop({
      id: station.id,
      name: station.name,
      type: 'subway',
      coords: station.coords,
      lineInfo: station.lines.join(' · '),
      baseCrowd: station.baseCrowd,
      rainSensitivity: 1.2
    })
    logSubwayApiCall(station.name.replace('역', ''), [
      { trainLineNm: `${station.name} 경유 - 상행/외선방면`, arvlMsg2: '전역 도착', barvlDt: '60', btrainSttus: '일반' },
      { trainLineNm: `${station.name} 경유 - 하행/내선방면`, arvlMsg2: '2분 후 (2번째 전역)', barvlDt: '150', btrainSttus: '일반' },
    ])
  }

  const currentHour = HOURLY_DATA[selectedHour]
  const isRaining = currentHour.rain > 0

  // ── 브라우저 개발자 콘솔(F12)에 실시간 공공 API 데이터 일괄 출력 ──
  const triggerApiConsoleLog = () => {
    console.clear()
    console.log(
      '%c📡 [Weather & Transit Web] 실시간 공공 API 및 AI 모델 데이터 스트림 모니터링',
      'background: #1e1b4b; color: #38bdf8; font-size: 13px; font-weight: 800; padding: 6px 12px; border-radius: 6px; border: 1px solid #38bdf8;'
    )

    // 1. 기상청 초단기실황
    logWeatherApiCall({ nx: 61, ny: 125 }, currentHour)

    // 2. 공공데이터포털 버스도착정보
    logBusApiCall('100100118 (472번)', '111000299 (구산동사거리)', [
      { rtNm: '472', stNm: '구산동사거리', arrmsg1: '출발대기', arrmsg2: '출발대기', staOrd: '1', busRouteId: '100100118' },
      { rtNm: '753', stNm: '구산동사거리', arrmsg1: '곧 도착', arrmsg2: '8분후[5번째 전]', staOrd: '3', busRouteId: '100100120' },
    ])

    // 3. 서울 열린데이터광장 지하철 실시간도착
    logSubwayApiCall('강남', [
      { trainLineNm: '성수행 - 역삼방면', arvlMsg2: '전역 도착', barvlDt: '90', btrainSttus: '일반' },
      { trainLineNm: '신사행 - 신논현방면', arvlMsg2: '전역 진입', barvlDt: '0', btrainSttus: '일반' },
    ])

    // 4. AI 수요 예측 추론
    logAIPredictionCall(
      { location: '강남구 역삼동', rain: `${currentHour.rain}mm`, temp: `${currentHour.temp}°C`, hour: currentHour.hour },
      { subwayScore: 97, busScore: 68, bikeScore: currentHour.rain > 0 ? 14 : 85, recommendation: isRaining ? '지하철 최우선 추천 (정시성 99%)' : '따릉이 및 대중교통 원활' }
    )
  }

  // 첫 진입 시 자동으로 콘솔에 API 데이터 스트림 기록
  useEffect(() => {
    triggerApiConsoleLog()
  }, [])

  return (
    <div style={{ minHeight: '100vh', background: '#0A1628', fontFamily: "'Outfit', 'Noto Sans KR', sans-serif", color: '#F0F6FF' }}>

      {/* ── TOP NAV ── */}
      <nav style={{ background: 'rgba(10,22,40,0.95)', backdropFilter: 'blur(20px)', borderBottom: '1px solid rgba(255,255,255,0.08)', position: 'sticky', top: 0, zIndex: 50 }}>
        <div style={{ maxWidth: 1280, margin: '0 auto', padding: '0 32px', display: 'flex', alignItems: 'center', height: 60, gap: 32 }}>
          {/* Logo */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
            <div style={{ width: 32, height: 32, borderRadius: 10, background: 'linear-gradient(135deg,#38BDF8,#22D3EE)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16 }}>
              🌦
            </div>
            <div>
              <div style={{ fontSize: 15, fontWeight: 800, letterSpacing: '-0.3px', color: '#F0F6FF' }}>WeatherMove</div>
              <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.35)', fontFamily: 'JetBrains Mono', letterSpacing: '0.06em', marginTop: -1 }}>SEOUL TRANSPORT AI</div>
            </div>
          </div>

          {/* Nav tabs */}
          <div style={{ display: 'flex', gap: 4, flex: 1 }}>
            {([
              { id: 'main', label: '날씨 · 현황', icon: '🏠' },
              { id: 'route', label: '경로 추천', icon: '🔍' },
              { id: 'map', label: '지도 보기', icon: '🗺' },
            ] as { id: Page; label: string; icon: string }[]).map(nav => (
              <button
                key={nav.id}
                onClick={() => setPage(nav.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6, padding: '6px 16px', borderRadius: 10,
                  background: page === nav.id ? 'rgba(56,189,248,0.15)' : 'transparent',
                  border: page === nav.id ? '1px solid rgba(56,189,248,0.35)' : '1px solid transparent',
                  color: page === nav.id ? '#38BDF8' : 'rgba(255,255,255,0.5)',
                  fontSize: 13, fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s',
                }}
              >
                <span style={{ fontSize: 15 }}>{nav.icon}</span>
                {nav.label}
              </button>
            ))}
          </div>

          {/* Live indicator & Console trigger button */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexShrink: 0 }}>
            <button
              onClick={triggerApiConsoleLog}
              title="브라우저 개발자 도구(F12 -> Console)에 실시간 공공 API 송수신 데이터를 출력합니다."
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '6px 12px', borderRadius: 8,
                background: 'rgba(56,189,248,0.12)', border: '1px solid rgba(56,189,248,0.3)',
                color: '#38BDF8', fontSize: 11, fontWeight: 700, cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
            >
              <span>📡</span> API 콘솔 로그 확인
            </button>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#34D399', boxShadow: '0 0 8px #34D399', animation: 'pulse 2s infinite' }} />
              <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', fontFamily: 'JetBrains Mono' }}>LIVE · 실시간 연동</span>
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
              <h1 style={{ fontSize: 28, fontWeight: 800, color: '#F0F6FF', margin: 0, letterSpacing: '-0.5px' }}>
                날씨 기반 교통 현황
              </h1>
              <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.45)', margin: '6px 0 0', lineHeight: 1.5 }}>
                서울시 날씨 + 버스·지하철·따릉이 이용 데이터를 실시간으로 분석합니다
              </p>
            </div>

            {/* 동 선택 */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 13, color: 'rgba(255,255,255,0.4)' }}>지역</span>
              <select
                value={selectedDistrict}
                onChange={e => setSelectedDistrict(Number(e.target.value))}
                style={{
                  background: '#162040', border: '1px solid rgba(255,255,255,0.12)',
                  color: '#F0F6FF', borderRadius: 12, padding: '8px 14px', fontSize: 13,
                  fontFamily: "'Outfit', 'Noto Sans KR', sans-serif", outline: 'none', cursor: 'pointer',
                }}
              >
                {DISTRICTS.map((d, i) => <option key={d} value={i}>{d}</option>)}
              </select>
            </div>
          </div>

          {/* 시간대 슬라이더 */}
          <div
            style={{
              background: '#162040', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 20,
              padding: '16px 20px', marginBottom: 24,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono', letterSpacing: '0.06em' }}>
                시간대 선택 · {HOURLY_DATA[selectedHour].hour}
              </span>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                {isRaining
                  ? <><span style={{ fontSize: 14 }}>🌧</span><span style={{ fontSize: 12, color: '#38BDF8', fontFamily: 'JetBrains Mono' }}>강수 {currentHour.rain}mm</span></>
                  : <><span style={{ fontSize: 14 }}>☀️</span><span style={{ fontSize: 12, color: '#FB923C', fontFamily: 'JetBrains Mono' }}>맑음</span></>
                }
              </div>
            </div>
            <div style={{ display: 'flex', gap: 6 }}>
              {HOURLY_DATA.map((d, i) => (
                <button
                  key={d.hour}
                  onClick={() => setSelectedHour(i)}
                  style={{
                    flex: 1, padding: '8px 4px', borderRadius: 10, cursor: 'pointer', transition: 'all 0.15s',
                    background: i === selectedHour ? 'rgba(56,189,248,0.2)' : d.rain > 0 ? 'rgba(56,189,248,0.06)' : 'rgba(255,255,255,0.04)',
                    border: i === selectedHour ? '1px solid rgba(56,189,248,0.5)' : '1px solid rgba(255,255,255,0.06)',
                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
                  }}
                >
                  <span style={{ fontSize: 13 }}>{d.rain > 0 ? '🌧' : '☀️'}</span>
                  <span style={{ fontSize: 10, fontFamily: 'JetBrains Mono', color: i === selectedHour ? '#38BDF8' : 'rgba(255,255,255,0.4)' }}>
                    {d.hour}
                  </span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: i === selectedHour ? '#F0F6FF' : 'rgba(255,255,255,0.6)' }}>
                    {d.temp}°
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* 3열 그리드 */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20, marginBottom: 24 }}>

            {/* 날씨 카드 */}
            <div style={{ background: 'linear-gradient(135deg, #162040 0%, #0D1B3A 100%)', border: '1px solid rgba(56,189,248,0.2)', borderRadius: 24, padding: 24, gridColumn: '1' }}>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono', letterSpacing: '0.07em', marginBottom: 12 }}>
                날씨 데이터 · {DISTRICTS[selectedDistrict]}
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20 }}>
                <span style={{ fontSize: 52 }}>{isRaining ? '🌧' : '☀️'}</span>
                <div>
                  <div style={{ fontSize: 52, fontWeight: 800, color: '#F0F6FF', lineHeight: 1, letterSpacing: '-2px', fontFamily: 'JetBrains Mono' }}>
                    {currentHour.temp}°
                  </div>
                  <div style={{ fontSize: 13, color: isRaining ? '#38BDF8' : '#FB923C', fontWeight: 600 }}>
                    {isRaining ? `비 · ${currentHour.rain}mm/h` : '맑음'}
                  </div>
                </div>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {[
                  { label: '습도', value: `${currentHour.humidity}%`, icon: '💧' },
                  { label: '풍속', value: `${currentHour.wind}m/s`, icon: '💨' },
                  { label: '강수량', value: `${currentHour.rain}mm`, icon: '🌧' },
                  { label: '체감온도', value: `${currentHour.temp - 2}°C`, icon: '🌡' },
                ].map(item => (
                  <div key={item.label} style={{ background: 'rgba(255,255,255,0.05)', borderRadius: 12, padding: '10px 12px' }}>
                    <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', fontFamily: 'JetBrains Mono', marginBottom: 2 }}>
                      {item.icon} {item.label}
                    </div>
                    <div style={{ fontSize: 16, fontWeight: 700, fontFamily: 'JetBrains Mono', color: '#F0F6FF' }}>{item.value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* 이용자 현황 */}
            <div style={{ background: '#162040', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 24, padding: 24 }}>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono', letterSpacing: '0.07em', marginBottom: 16 }}>
                교통 이용자 현황 · {currentHour.hour}
              </div>
              {[
                { icon: '🚇', name: '지하철', value: currentHour.subway, color: '#38BDF8', max: 95000 },
                { icon: '🚌', name: '버스', value: currentHour.bus, color: '#FB923C', max: 18400 },
                { icon: '🚲', name: '따릉이', value: currentHour.bike, color: '#34D399', max: 780 },
              ].map(t => (
                <div key={t.name} style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <span style={{ fontSize: 18 }}>{t.icon}</span>
                      <span style={{ fontSize: 13, fontWeight: 600, color: '#F0F6FF' }}>{t.name}</span>
                    </div>
                    <span style={{ fontSize: 14, fontWeight: 700, color: t.color, fontFamily: 'JetBrains Mono' }}>
                      {t.value.toLocaleString()}명
                    </span>
                  </div>
                  <div style={{ height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${(t.value / t.max) * 100}%`, background: t.color, borderRadius: 3, transition: 'width 0.5s ease' }} />
                  </div>
                </div>
              ))}
              <div style={{ marginTop: 4, padding: '10px 14px', background: isRaining ? 'rgba(56,189,248,0.08)' : 'rgba(251,146,60,0.08)', borderRadius: 12, border: `1px solid ${isRaining ? 'rgba(56,189,248,0.2)' : 'rgba(251,146,60,0.2)'}` }}>
                <div style={{ fontSize: 11, color: isRaining ? '#38BDF8' : '#FB923C' }}>
                  {isRaining
                    ? `⚠️ 비 ${currentHour.rain}mm — 지하철 수요 ${Math.round((currentHour.subway / 95000) * 100)}% · 따릉이 급감`
                    : '✅ 맑은 날씨 — 전 교통수단 정상 운행'}
                </div>
              </div>
            </div>

            {/* AI 추천 카드 */}
            <div style={{ background: '#162040', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 24, padding: 24 }}>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono', letterSpacing: '0.07em', marginBottom: 16 }}>
                모델 추천 결과 · {currentHour.hour}
              </div>
              {TRANSPORT_SCORES.map((t, i) => (
                <div
                  key={t.id}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 12, marginBottom: i < 2 ? 12 : 0,
                    padding: '10px 12px', borderRadius: 14,
                    background: i === 0 ? 'rgba(56,189,248,0.08)' : 'rgba(255,255,255,0.03)',
                    border: i === 0 ? '1px solid rgba(56,189,248,0.2)' : '1px solid rgba(255,255,255,0.06)',
                  }}
                >
                  <span style={{ fontSize: 24 }}>{t.icon}</span>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
                      <span style={{ fontSize: 13, fontWeight: 700, color: '#F0F6FF' }}>{t.name}</span>
                      <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 999, background: `${t.scoreColor}22`, color: t.scoreColor, fontWeight: 600 }}>
                        {t.scoreLabel}
                      </span>
                    </div>
                    <div style={{ height: 4, background: 'rgba(255,255,255,0.08)', borderRadius: 2, overflow: 'hidden' }}>
                      <div style={{ height: '100%', width: `${t.score}%`, background: t.scoreColor, borderRadius: 2 }} />
                    </div>
                  </div>
                  <div style={{ fontSize: 20, fontWeight: 800, color: t.scoreColor, fontFamily: 'JetBrains Mono', minWidth: 32, textAlign: 'right' }}>
                    {t.score}
                  </div>
                </div>
              ))}
              <button
                onClick={() => setPage('route')}
                style={{
                  width: '100%', marginTop: 14, padding: '10px', borderRadius: 14, cursor: 'pointer',
                  background: 'linear-gradient(135deg, #38BDF8, #22D3EE)', color: '#0A1628',
                  fontSize: 13, fontWeight: 700, border: 'none', letterSpacing: '0.02em',
                }}
              >
                🔍 경로 상세 검색
              </button>
            </div>
          </div>

          {/* 하단 2열: 시간대별 차트 + 상관관계 + 동별 현황 */}
          <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 20 }}>

            {/* 시간대별 이용자 추이 */}
            <div style={{ background: '#162040', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 24, padding: 24 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
                <div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: '#F0F6FF' }}>시간대별 이용자 추이</div>
                  <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', marginTop: 2 }}>날씨 변화와 교통 수요 연관성</div>
                </div>
                <div style={{ display: 'flex', gap: 12 }}>
                  {[['🚇', '지하철', '#38BDF8'], ['🚌', '버스', '#FB923C'], ['🚲', '따릉이', '#34D399']].map(([icon, name, color]) => (
                    <div key={name as string} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                      <div style={{ width: 8, height: 3, background: color as string, borderRadius: 2 }} />
                      <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono' }}>{name as string}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Multi-line chart */}
              <div style={{ position: 'relative', height: 140 }}>
                <svg width="100%" height="140" viewBox="0 0 560 140" preserveAspectRatio="none">
                  {/* Grid */}
                  {[0, 35, 70, 105, 140].map(y => (
                    <line key={y} x1="0" y1={y} x2="560" y2={y} stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
                  ))}
                  {/* Subway */}
                  <polyline
                    points={HOURLY_DATA.map((d, i) => `${(i / (HOURLY_DATA.length-1)) * 560},${140 - (d.subway / 95000) * 120}`).join(' ')}
                    fill="none" stroke="#38BDF8" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
                  />
                  <polyline
                    points={HOURLY_DATA.map((d, i) => `${(i / (HOURLY_DATA.length-1)) * 560},${140 - (d.subway / 95000) * 120}`).join(' ')}
                    fill="rgba(56,189,248,0.08)" strokeWidth="0"
                  />
                  {/* Bus */}
                  <polyline
                    points={HOURLY_DATA.map((d, i) => `${(i / (HOURLY_DATA.length-1)) * 560},${140 - (d.bus / 18400) * 120}`).join(' ')}
                    fill="none" stroke="#FB923C" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" strokeDasharray="5 3"
                  />
                  {/* Bike */}
                  <polyline
                    points={HOURLY_DATA.map((d, i) => `${(i / (HOURLY_DATA.length-1)) * 560},${140 - (d.bike / 780) * 120}`).join(' ')}
                    fill="none" stroke="#34D399" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                  />
                  {/* Rain markers */}
                  {HOURLY_DATA.map((d, i) => d.rain > 0 && (
                    <rect key={i} x={(i / (HOURLY_DATA.length-1)) * 560 - 4} y={0} width={8} height={140}
                      fill="rgba(56,189,248,0.06)" />
                  ))}
                  {/* Current time marker */}
                  <line
                    x1={(selectedHour / (HOURLY_DATA.length-1)) * 560}
                    y1={0}
                    x2={(selectedHour / (HOURLY_DATA.length-1)) * 560}
                    y2={140}
                    stroke="rgba(255,255,255,0.3)" strokeWidth="1.5" strokeDasharray="4 3"
                  />
                </svg>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 4 }}>
                {HOURLY_DATA.map(d => (
                  <span key={d.hour} style={{ fontSize: 9, color: 'rgba(255,255,255,0.25)', fontFamily: 'JetBrains Mono' }}>
                    {d.hour.replace('시', '')}시
                  </span>
                ))}
              </div>
            </div>

            {/* 동별 혼잡도 */}
            <div style={{ background: '#162040', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 24, padding: 24 }}>
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 700, color: '#F0F6FF' }}>동별 교통 혼잡도</div>
                <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', marginTop: 2 }}>서울시 주요 행정동 현황</div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {DISTRICT_DATA.map(d => (
                  <div key={d.name} style={{ padding: '10px 14px', background: 'rgba(255,255,255,0.03)', borderRadius: 14, border: '1px solid rgba(255,255,255,0.06)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <span style={{ fontSize: 14 }}>{d.weather}</span>
                        <span style={{ fontSize: 13, fontWeight: 600, color: '#F0F6FF' }}>{d.name}</span>
                      </div>
                      <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono' }}>{d.temp}°C</span>
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 6 }}>
                      <div>
                        <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', fontFamily: 'JetBrains Mono', marginBottom: 3 }}>지하철</div>
                        <CrowdBar value={d.subway} color="#38BDF8" />
                      </div>
                      <div>
                        <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', fontFamily: 'JetBrains Mono', marginBottom: 3 }}>버스</div>
                        <CrowdBar value={d.bus} color="#FB923C" />
                      </div>
                      <div>
                        <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', fontFamily: 'JetBrains Mono', marginBottom: 3 }}>따릉이</div>
                        <CrowdBar value={d.bike} color="#34D399" />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 데이터 출처 */}
          <div style={{ marginTop: 24, padding: '16px 20px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 16, display: 'flex', gap: 24, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)', fontFamily: 'JetBrains Mono' }}>DATA SOURCES</span>
            {[
              '서울시 버스노선별 정류장별 시간대별 승하차',
              '서울시 지하철 호선별 역별 시간대별 승하차',
              '서울시 공공자전거 따릉이 대여이력',
              '기상청 동단위 시간별 날씨 데이터',
            ].map(src => (
              <span key={src} style={{ fontSize: 10, color: 'rgba(255,255,255,0.3)', fontFamily: 'JetBrains Mono' }}>
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
            <h1 style={{ fontSize: 28, fontWeight: 800, color: '#F0F6FF', margin: 0, letterSpacing: '-0.5px' }}>
              경로 추천
            </h1>
            <p style={{ fontSize: 14, color: 'rgba(255,255,255,0.45)', margin: '6px 0 0' }}>
              현재 날씨를 반영해 최적 교통수단과 경로를 추천합니다
            </p>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '400px 1fr', gap: 24, alignItems: 'start' }}>

            {/* 입력 패널 */}
            <div>
              {/* 날씨 현황 배지 */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', background: 'rgba(56,189,248,0.08)', border: '1px solid rgba(56,189,248,0.2)', borderRadius: 16, marginBottom: 16 }}>
                <span style={{ fontSize: 22 }}>🌧</span>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 700, color: '#38BDF8' }}>강남구 역삼동 · 비 · 14°C · 강수 2.8mm/h</div>
                  <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', marginTop: 1 }}>현재 날씨 기준으로 교통수단을 추천합니다</div>
                </div>
              </div>

              {/* 출발/도착 입력 (지하철역 실시간 자동완성 검색 연동) */}
              <div style={{ background: '#162040', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 20, marginBottom: 16 }}>
                {/* 출발지 */}
                <div style={{ padding: '16px 18px 12px', borderBottom: '1px solid rgba(255,255,255,0.07)', position: 'relative' }}>
                  <div style={{ fontSize: 10, color: '#34D399', fontFamily: 'JetBrains Mono', letterSpacing: '0.07em', marginBottom: 6 }}>
                    🟢  출발지 (지하철역 검색)
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
                      fontSize: 15, fontWeight: 500, color: '#F0F6FF',
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
                        background: '#111D35', border: '1px solid rgba(52,211,153,0.4)', borderRadius: 12,
                        boxShadow: '0 8px 30px rgba(0,0,0,0.7)', maxHeight: 240, overflowY: 'auto',
                      }}>
                        <div style={{ padding: '6px 12px', fontSize: 10, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between' }}>
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
                              padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.05)',
                              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                              background: idx === selectedDepartureIndex ? 'rgba(52,211,153,0.22)' : 'transparent',
                              borderLeft: idx === selectedDepartureIndex ? '3px solid #34D399' : '3px solid transparent',
                              transition: 'background 0.1s ease',
                            }}
                            onMouseEnter={() => setSelectedDepartureIndex(idx)}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ fontSize: 14 }}>🚇</span>
                              <span style={{ fontSize: 13, fontWeight: 700, color: '#F0F6FF' }}>{st.name}</span>
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

                {/* 도착지 */}
                <div style={{ padding: '12px 18px 16px', position: 'relative' }}>
                  <div style={{ fontSize: 10, color: '#38BDF8', fontFamily: 'JetBrains Mono', letterSpacing: '0.07em', marginBottom: 6 }}>
                    🔵  도착지 (지하철역 검색)
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
                      fontSize: 15, fontWeight: 500, color: '#F0F6FF',
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
                        background: '#111D35', border: '1px solid rgba(56,189,248,0.4)', borderRadius: 12,
                        boxShadow: '0 8px 30px rgba(0,0,0,0.7)', maxHeight: 240, overflowY: 'auto',
                      }}>
                        <div style={{ padding: '6px 12px', fontSize: 10, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between' }}>
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
                              padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.05)',
                              cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                              background: idx === selectedDestinationIndex ? 'rgba(56,189,248,0.22)' : 'transparent',
                              borderLeft: idx === selectedDestinationIndex ? '3px solid #38BDF8' : '3px solid transparent',
                              transition: 'background 0.1s ease',
                            }}
                            onMouseEnter={() => setSelectedDestinationIndex(idx)}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                              <span style={{ fontSize: 14 }}>🚇</span>
                              <span style={{ fontSize: 13, fontWeight: 700, color: '#F0F6FF' }}>{st.name}</span>
                              <span style={{ fontSize: 10, color: '#38BDF8', background: 'rgba(56,189,248,0.15)', padding: '2px 6px', borderRadius: 4 }}>
                                {st.lines.join(', ')}
                              </span>
                            </div>
                            {idx === selectedDestinationIndex && (
                              <span style={{ fontSize: 10, color: '#38BDF8', fontFamily: 'JetBrains Mono' }}>↵ Enter</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )
                  })()}
                </div>
              </div>

              <button
                onClick={() => handleSearchRoute(departure, destination)}
                style={{
                  width: '100%', padding: '14px', borderRadius: 16, cursor: 'pointer', marginBottom: 20,
                  background: 'linear-gradient(135deg, #38BDF8, #22D3EE)', color: '#0A1628',
                  fontSize: 15, fontWeight: 800, border: 'none',
                  boxShadow: '0 8px 32px rgba(56,189,248,0.3)',
                }}
              >
                🔍  경로 검색 및 지도 보기
              </button>

              {/* 자주 찾는 경로 */}
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.3)', fontFamily: 'JetBrains Mono', letterSpacing: '0.06em', marginBottom: 10 }}>
                  자주 찾는 경로
                </div>
                {[
                  { from: '강남역', to: '서울역', icon: '🚇', time: '35분', price: '1,400원' },
                  { from: '홍대입구역', to: '이태원역', icon: '🚇', time: '24분', price: '1,400원' },
                  { from: '잠실역', to: '강동구청역', icon: '🚇', time: '14분', price: '1,400원' },
                  { from: '여의도역', to: '시청역', icon: '🚇', time: '16분', price: '1,400원' },
                ].map(r => (
                  <button
                    key={r.from}
                    onClick={() => {
                      setDeparture(r.from)
                      setDestination(r.to)
                      handleSearchRoute(r.from, r.to)
                    }}
                    style={{
                      width: '100%', display: 'flex', alignItems: 'center', gap: 12,
                      padding: '10px 14px', marginBottom: 6, borderRadius: 12, cursor: 'pointer',
                      background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.07)',
                      textAlign: 'left', transition: 'all 0.15s',
                    }}
                  >
                    <span style={{ fontSize: 18 }}>{r.icon}</span>
                    <div style={{ flex: 1 }}>
                      <span style={{ fontSize: 13, fontWeight: 500, color: '#F0F6FF' }}>{r.from}</span>
                      <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.3)', margin: '0 6px' }}>→</span>
                      <span style={{ fontSize: 13, fontWeight: 500, color: '#F0F6FF' }}>{r.to}</span>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: 12, fontWeight: 700, color: '#38BDF8', fontFamily: 'JetBrains Mono' }}>{r.time}</div>
                      <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)' }}>{r.price}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            {/* 추천 결과 */}
            <div>
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono', letterSpacing: '0.06em', marginBottom: 16 }}>
                날씨 기반 교통수단 추천 결과
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                {TRANSPORT_SCORES.map((t, i) => (
                  <div
                    key={t.id}
                    style={{
                      background: i === 0 ? 'rgba(56,189,248,0.06)' : '#162040',
                      border: i === 0 ? '1px solid rgba(56,189,248,0.25)' : '1px solid rgba(255,255,255,0.08)',
                      borderRadius: 20, padding: 20,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14 }}>
                      <div style={{
                        width: 52, height: 52, borderRadius: 16, background: 'rgba(255,255,255,0.06)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28, flexShrink: 0,
                      }}>
                        {t.icon}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                          <span style={{ fontSize: 17, fontWeight: 800, color: '#F0F6FF' }}>{t.name}</span>
                          <span style={{ fontSize: 11, padding: '2px 8px', borderRadius: 999, background: `${t.scoreColor}22`, color: t.scoreColor, fontWeight: 700 }}>
                            {t.scoreLabel}
                          </span>
                          {i === 0 && <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 999, background: 'rgba(52,211,153,0.15)', color: '#34D399', fontWeight: 700 }}>AI 추천</span>}
                        </div>
                        <div style={{ height: 5, background: 'rgba(255,255,255,0.08)', borderRadius: 3, overflow: 'hidden' }}>
                          <div style={{ height: '100%', width: `${t.score}%`, background: t.scoreColor, borderRadius: 3 }} />
                        </div>
                      </div>
                      <div style={{ textAlign: 'right', flexShrink: 0 }}>
                        <div style={{ fontSize: 36, fontWeight: 900, color: t.scoreColor, fontFamily: 'JetBrains Mono', lineHeight: 1 }}>{t.score}</div>
                        <div style={{ fontSize: 9, color: 'rgba(255,255,255,0.3)', fontFamily: 'JetBrains Mono' }}>/ 100</div>
                      </div>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10, marginBottom: 14 }}>
                      {[
                        { label: '예상 소요', value: t.time },
                        { label: '예상 요금', value: t.price },
                        { label: '혼잡도', value: t.crowdLabel },
                      ].map(item => (
                        <div key={item.label} style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 12, padding: '10px 12px' }}>
                          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', fontFamily: 'JetBrains Mono', marginBottom: 3 }}>{item.label}</div>
                          <div style={{ fontSize: 14, fontWeight: 700, color: item.label === '혼잡도' ? t.crowdColor : '#F0F6FF' }}>{item.value}</div>
                        </div>
                      ))}
                    </div>

                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      {t.reasons.map(reason => (
                        <span
                          key={reason}
                          style={{
                            fontSize: 11, padding: '3px 10px', borderRadius: 999,
                            background: 'rgba(255,255,255,0.06)', color: 'rgba(255,255,255,0.5)',
                          }}
                        >
                          {reason}
                        </span>
                      ))}
                    </div>

                    <div style={{ marginTop: 10, fontSize: 10, color: 'rgba(255,255,255,0.2)', fontFamily: 'JetBrains Mono' }}>
                      데이터: {t.dataset}
                    </div>
                  </div>
                ))}
              </div>

              {/* 강수량-이용률 상관관계 차트 */}
              <div style={{ marginTop: 20, background: '#162040', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 20, padding: 20 }}>
                <div style={{ marginBottom: 12 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: '#F0F6FF' }}>강수량 vs 교통수단 이용률 상관관계</div>
                  <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.35)', marginTop: 2 }}>모델 학습에 사용된 핵심 변수</div>
                </div>
                <CorrelationChart />
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 6 }}>
                  <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.25)', fontFamily: 'JetBrains Mono' }}>강수량(mm/h) →</span>
                  <div style={{ display: 'flex', gap: 14 }}>
                    {[['#38BDF8', '지하철'], ['#FB923C', '버스'], ['#94A3B8', '따릉이']].map(([c, n]) => (
                      <div key={n} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <div style={{ width: 12, height: 2, background: c as string, borderRadius: 1 }} />
                        <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', fontFamily: 'JetBrains Mono' }}>{n}</span>
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
          PAGE: 지도
      ══════════════════════════════════════ */}
      {page === 'map' && (
        <div style={{ display: 'flex', height: 'calc(100vh - 60px)' }}>

          {/* 사이드패널 */}
          <div style={{
            width: 360, flexShrink: 0, background: '#111D35',
            borderRight: '1px solid rgba(255,255,255,0.08)',
            display: 'flex', flexDirection: 'column', overflow: 'hidden',
          }}>
            {/* 지하철역 검색 및 자동완성 입력창 */}
            <div style={{ padding: '16px 20px 14px', borderBottom: '1px solid rgba(255,255,255,0.08)', position: 'relative' }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#38BDF8', letterSpacing: '0.04em', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
                <span>🔍</span> 지하철역 검색 & 바로가기
              </div>
              <div style={{ background: '#162040', border: '1px solid rgba(56,189,248,0.3)', borderRadius: 12, padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8 }}>
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
                  style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', fontSize: 13, color: '#F0F6FF', fontFamily: "'Outfit','Noto Sans KR',sans-serif" }}
                />
                {subwaySearchQuery && (
                  <button
                    onClick={() => {
                      setSubwaySearchQuery('')
                      setShowSearchResults(false)
                    }}
                    style={{ background: 'transparent', border: 'none', color: 'rgba(255,255,255,0.4)', cursor: 'pointer', fontSize: 12 }}
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
                    background: '#111D35', border: '1px solid rgba(56,189,248,0.35)', borderRadius: 12,
                    boxShadow: '0 8px 30px rgba(0,0,0,0.6)', maxHeight: 260, overflowY: 'auto',
                  }}>
                    {results.length > 0 && (
                      <div style={{ padding: '6px 12px', fontSize: 10, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono', borderBottom: '1px solid rgba(255,255,255,0.05)', display: 'flex', justifyContent: 'space-between' }}>
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
                            padding: '10px 14px', borderBottom: '1px solid rgba(255,255,255,0.05)',
                            cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                            background: idx === selectedSubwayIndex ? 'rgba(56,189,248,0.22)' : 'transparent',
                            borderLeft: idx === selectedSubwayIndex ? '3px solid #38BDF8' : '3px solid transparent',
                            transition: 'background 0.1s ease',
                          }}
                          onMouseEnter={() => setSelectedSubwayIndex(idx)}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <span style={{ fontSize: 15 }}>🚇</span>
                            <span style={{ fontSize: 13, fontWeight: 700, color: '#F0F6FF' }}>{st.name}</span>
                            <span style={{ fontSize: 10, color: '#38BDF8', background: 'rgba(56,189,248,0.15)', padding: '2px 6px', borderRadius: 4 }}>
                              {st.lines[0]}
                            </span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono' }}>
                              {st.zone}
                            </span>
                            {idx === selectedSubwayIndex && (
                              <span style={{ fontSize: 10, color: '#38BDF8', fontFamily: 'JetBrains Mono' }}>↵</span>
                            )}
                          </div>
                        </div>
                      ))
                    ) : (
                      <div style={{ padding: '14px', fontSize: 12, color: 'rgba(255,255,255,0.4)', textAlign: 'center' }}>
                        검색된 지하철역이 없습니다.
                      </div>
                    )}
                  </div>
                )
              })()}
            </div>

            {/* 교통수단 탭 */}
            <div style={{ display: 'flex', gap: 6, padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.08)' }}>
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
                    background: mapTransport === t.id ? 'rgba(56,189,248,0.15)' : 'rgba(255,255,255,0.04)',
                    border: mapTransport === t.id ? '1px solid rgba(56,189,248,0.4)' : '1px solid rgba(255,255,255,0.07)',
                  }}
                >
                  <span style={{ fontSize: 18 }}>{t.icon}</span>
                  <span style={{ fontSize: 10, fontWeight: 600, color: mapTransport === t.id ? '#38BDF8' : 'rgba(255,255,255,0.5)' }}>{t.label}</span>
                </button>
              ))}
            </div>

            {/* AI 날씨-수요 시뮬레이터 (요구사항 FR-02-3 & FR-03-3) */}
            <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.08)', background: 'rgba(56,189,248,0.03)' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#38BDF8', letterSpacing: '0.04em' }}>⚡ AI 수요 예측 시뮬레이터</span>
                <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono' }}>실시간 연동</span>
              </div>

              {/* 강수량 슬라이더 */}
              <div style={{ marginBottom: 10 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 4 }}>
                  <span style={{ color: 'rgba(255,255,255,0.6)' }}>가상 강수량 (Rainfall)</span>
                  <b style={{ color: rainSimulation > 0 ? '#38BDF8' : '#34D399', fontFamily: 'JetBrains Mono' }}>
                    {rainSimulation.toFixed(1)} mm/h
                  </b>
                </div>
                <input
                  type="range"
                  min="0"
                  max="10"
                  step="0.5"
                  value={rainSimulation}
                  onChange={e => setRainSimulation(parseFloat(e.target.value))}
                  style={{ width: '100%', accentColor: '#38BDF8', cursor: 'pointer' }}
                />
              </div>

              {/* 시간대 선택 버튼 */}
              <div>
                <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.6)', marginBottom: 5 }}>시계열 예측 시간대</div>
                <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                  {['07시', '08시', '09시', '12시', '18시', '21시'].map(t => (
                    <button
                      key={t}
                      onClick={() => setSimulatedTime(t)}
                      style={{
                        padding: '3px 8px', borderRadius: 6, fontSize: 10, cursor: 'pointer', border: 'none',
                        background: simulatedTime === t ? '#38BDF8' : 'rgba(255,255,255,0.06)',
                        color: simulatedTime === t ? '#0A1628' : 'rgba(255,255,255,0.6)',
                        fontWeight: simulatedTime === t ? 700 : 500
                      }}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* 경로 및 선택 정류장 상세 정보 */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px' }}>
              {activeRoute ? (
                <div style={{ background: 'rgba(56,189,248,0.12)', border: '1px solid rgba(56,189,248,0.4)', borderRadius: 16, padding: '14px 16px', marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div style={{ fontSize: 10, color: '#38BDF8', fontFamily: 'JetBrains Mono', fontWeight: 700 }}>
                      🗺️ 추천 지하철 이동 경로
                    </div>
                    <button
                      onClick={() => setActiveRoute(null)}
                      style={{ background: 'transparent', border: 'none', color: 'rgba(255,255,255,0.4)', fontSize: 11, cursor: 'pointer' }}
                    >
                      초기화 ✕
                    </button>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
                    <div>
                      <div style={{ fontSize: 15, fontWeight: 800, color: '#F0F6FF' }}>
                        {activeRoute.from} ➔ {activeRoute.to}
                      </div>
                      <div style={{ fontSize: 11, color: '#38BDF8', marginTop: 2 }}>
                        {activeRoute.summary}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: 26, fontWeight: 900, color: '#38BDF8', fontFamily: 'JetBrains Mono', lineHeight: 1 }}>
                        {activeRoute.estimatedMinutes}
                      </div>
                      <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', fontFamily: 'JetBrains Mono' }}>분 소요</div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
                    <div style={{ flex: 1, background: 'rgba(255,255,255,0.06)', borderRadius: 8, padding: '6px 8px', textAlign: 'center' }}>
                      <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)' }}>경유 역</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: '#F0F6FF' }}>{activeRoute.stationCount}개 역</div>
                    </div>
                    <div style={{ flex: 1, background: 'rgba(255,255,255,0.06)', borderRadius: 8, padding: '6px 8px', textAlign: 'center' }}>
                      <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)' }}>기본 요금</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: '#F0F6FF' }}>1,400원</div>
                    </div>
                    <div style={{ flex: 1, background: 'rgba(255,255,255,0.06)', borderRadius: 8, padding: '6px 8px', textAlign: 'center' }}>
                      <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)' }}>날씨 영향</div>
                      <div style={{ fontSize: 12, fontWeight: 700, color: '#10B981' }}>정시 운행</div>
                    </div>
                  </div>

                  {/* 경유역 경로 리스트 */}
                  <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono', marginBottom: 6 }}>
                    경유 역 목록 (클릭 시 해당 역 위치로 이동):
                  </div>
                  <div style={{
                    maxHeight: 140, overflowY: 'auto', background: 'rgba(0,0,0,0.25)', borderRadius: 8, padding: '6px 10px',
                    display: 'flex', flexDirection: 'column', gap: 4
                  }}>
                    {activeRoute.path.map((p, idx) => (
                      <div
                        key={p.name + idx}
                        onClick={() => setFocusedCoords(p.coords)}
                        style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11, cursor: 'pointer', padding: '3px 0' }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                          <span style={{ fontSize: 10, color: idx === 0 ? '#10B981' : idx === activeRoute.path.length - 1 ? '#F43F5E' : 'rgba(255,255,255,0.3)' }}>
                            {idx === 0 ? '🟢' : idx === activeRoute.path.length - 1 ? '🔴' : '○'}
                          </span>
                          <span style={{ color: idx === 0 || idx === activeRoute.path.length - 1 ? '#FFFFFF' : 'rgba(255,255,255,0.75)', fontWeight: idx === 0 || idx === activeRoute.path.length - 1 ? 700 : 400 }}>
                            {p.name}
                          </span>
                        </div>
                        <span style={{ fontSize: 9, color: '#38BDF8', background: 'rgba(56,189,248,0.1)', padding: '1px 5px', borderRadius: 4 }}>
                          {p.lines[0] || '지하철'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : selectedStop ? (
                <div style={{ background: 'rgba(56,189,248,0.1)', border: '1px solid rgba(56,189,248,0.3)', borderRadius: 16, padding: '14px 16px', marginBottom: 16 }}>
                  <div style={{ fontSize: 10, color: '#38BDF8', fontFamily: 'JetBrains Mono', marginBottom: 4 }}>선택된 거점 상세 정보</div>
                  <div style={{ fontSize: 15, fontWeight: 700, color: '#F0F6FF', marginBottom: 4 }}>
                    {selectedStop.type === 'subway' ? '🚇' : selectedStop.type === 'bus' ? '🚌' : '🚲'} {selectedStop.name}
                  </div>
                  <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.5)', marginBottom: 8 }}>{selectedStop.lineInfo}</div>
                  <div style={{ fontSize: 11, color: '#F0F6FF', background: 'rgba(0,0,0,0.25)', padding: '8px 10px', borderRadius: 8, lineHeight: 1.5 }}>
                    {rainSimulation > 0 ? (
                      <>🌧 비({rainSimulation}mm)로 인해 <b>{selectedStop.type === 'bike' ? '따릉이 이용 위험 및 비추천' : '실내 환승 및 지하철 이용 집중'}</b> 상태입니다.</>
                    ) : (
                      <>☀️ 맑은 날씨로 평시 쾌적한 출퇴근 흐름을 유지하고 있습니다.</>
                    )}
                  </div>
                </div>
              ) : (
                <div style={{ background: 'rgba(56,189,248,0.08)', border: '1px solid rgba(56,189,248,0.2)', borderRadius: 16, padding: '14px 16px', marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: '#F0F6FF' }}>강남구청 → 잠실역</div>
                      <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', marginTop: 2 }}>
                        {mapTransport === 'subway' ? '지하철 2호선' : mapTransport === 'bus' ? '버스 145' : '따릉이 대여'}
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontSize: 28, fontWeight: 900, color: '#38BDF8', fontFamily: 'JetBrains Mono', lineHeight: 1 }}>
                        {mapTransport === 'subway' ? '28' : mapTransport === 'bus' ? '42' : '55'}
                      </div>
                      <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.35)', fontFamily: 'JetBrains Mono' }}>분</div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8 }}>
                    {[
                      ['💰', mapTransport === 'subway' ? '1,400원' : mapTransport === 'bus' ? '1,300원' : '1,000원/h'],
                      ['👥', rainSimulation > 3 ? (mapTransport === 'bike' ? '운행중단' : '매우혼잡') : (mapTransport === 'bike' ? '여유' : '보통')],
                    ].map(([icon, val]) => (
                      <div key={val as string} style={{ flex: 1, background: 'rgba(255,255,255,0.06)', borderRadius: 10, padding: '7px 10px', display: 'flex', alignItems: 'center', gap: 5 }}>
                        <span style={{ fontSize: 13 }}>{icon}</span>
                        <span style={{ fontSize: 12, fontWeight: 600, color: '#F0F6FF' }}>{val}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* 안내 문구 */}
              <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.4)', lineHeight: 1.5, background: 'rgba(255,255,255,0.02)', padding: '10px 12px', borderRadius: 10 }}>
                💡 <b>안내</b>: 지도 위의 마커를 클릭하면 해당 정류장 및 역의 상세 혼잡도와 날씨 민감도 분석을 확인하실 수 있습니다.
              </div>
            </div>

            {/* 안내 시작 버튼 */}
            <div style={{ padding: '16px 20px', borderTop: '1px solid rgba(255,255,255,0.08)' }}>
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
                  background: 'linear-gradient(135deg, #38BDF8, #22D3EE)', color: '#0A1628',
                  fontSize: 15, fontWeight: 800, border: 'none',
                  boxShadow: '0 8px 24px rgba(56,189,248,0.35)',
                }}
              >
                🧭  실시간 대중교통 경로 안내
              </button>
            </div>
          </div>

          {/* MapLibre GL JS + OpenStreetMap 실제 지도 컨테이너 (요구사항 FR-03-1, FR-03-2, FR-03-3) */}
          <div style={{ flex: 1, height: '100%', position: 'relative' }}>
            <TransitMap
              filterType={mapTransport}
              rainMm={rainSimulation}
              selectedTime={simulatedTime}
              focusedCoords={focusedCoords}
              onSelectStop={setSelectedStop}
              activeRoute={activeRoute}
              onClearRoute={() => setActiveRoute(null)}
            />
          </div>
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        * { scrollbar-width: thin; scrollbar-color: rgba(56,189,248,0.3) transparent; }
        input::placeholder { color: rgba(255,255,255,0.2); }
        button { transition: all 0.15s ease; }
        button:hover { opacity: 0.88; }
        select option { background: #162040; }
      `}</style>
    </div>
  )
}
