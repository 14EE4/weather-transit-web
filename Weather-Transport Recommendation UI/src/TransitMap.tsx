import { useEffect, useRef, useState } from 'react'
import { logWeatherApiCall, logBusApiCall, logSubwayApiCall, logAIPredictionCall, logBikeApiCall, logBikeNearbyCall } from './apiLogger'
import { SUBWAY_STATIONS } from './subwayData'
import { BUS_STOPS } from './busStopData'
import { BIKE_STATIONS } from './bikeStopData'
import { TransitRouteResult } from './subwayGraph'
import { resolveDistrict } from './districtResolver'
import { SUBWAY_NETWORK_GEOJSON } from './subwayNetworkLayer'

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
// API Base URL: Docker Nginx 환경에서는 동일 오리진("") 리버스 프록시 적용
if (import.meta.env.DEV) {
  console.log('[API 환경변수]', import.meta.env.VITE_API_BASE_URL || '(동일 오리진 프록시)')
}

// ── 로컬 스토리지 키 (새로고침 시 지도 카메라 위치 및 선택 역 복원) ──
const STORAGE_MAP_VIEW_KEY = 'weather_transit_map_view'
const STORAGE_SELECTED_STOP_KEY = 'weather_transit_selected_stop_id'

// ── 기본 카메라 뷰 각도 (탑뷰: 3D 틸트 없이 수직 상공에서 내려다보는 시점) ──
// 새로고침 시 복원하는 것은 위치(중심·줌)뿐이며, 시야각(틸트)과 방위각은 항상 아래 기본값으로 초기화한다.
const DEFAULT_MAP_PITCH = 0 // 시야각 0° = 탑뷰 (수직 하향)
const DEFAULT_MAP_BEARING = 0 // 방위각 0° = 정북 방향

// 저장 뷰 규격 — 위치(중심·줌)만 영속화하고 시야각·방위각은 저장하지 않는다.
interface SavedMapView {
  center: [number, number]
  zoom: number
}

// ── 대한민국 영역 경계 (전 세계 타일 로딩 방지 및 한국 영토 내 이동 제한) ──
const KOREA_BOUNDS: [[number, number], [number, number]] = [
  [124.0, 32.8], // 서남단 (서해 격렬비열도/마라도 남단)
  [132.0, 39.2], // 동북단 (동해 독도 동단/휴전선 북방)
]

const getSavedMapView = (): SavedMapView | null => {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(STORAGE_MAP_VIEW_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (
      Array.isArray(parsed.center) &&
      parsed.center.length === 2 &&
      typeof parsed.center[0] === 'number' &&
      !isNaN(parsed.center[0]) &&
      typeof parsed.center[1] === 'number' &&
      !isNaN(parsed.center[1]) &&
      typeof parsed.zoom === 'number' &&
      !isNaN(parsed.zoom)
    ) {
      const lng = parsed.center[0]
      const lat = parsed.center[1]
      const isInsideKorea = lng >= 124.0 && lng <= 132.0 && lat >= 32.8 && lat <= 39.2
      const validCenter: [number, number] = isInsideKorea ? [lng, lat] : [127.050, 37.505]
      const validZoom = Math.max(7.0, Math.min(18.5, parsed.zoom))
      // 시야각(틸트)·방위각은 저장값을 신뢰하지 않는다 — 새로고침 시 항상 탑뷰·정북으로 초기화.
      return {
        center: validCenter,
        zoom: validZoom,
      }
    }
  } catch {}
  return null
}

// ── 역 및 정류장 데이터 규격 ──
export interface TransitStop {
  id: string
  name: string
  type: 'subway' | 'bus' | 'bike'
  coords: [number, number] // [lng, lat]
  lineInfo: string
  baseCrowd: number // 기본 혼잡도 (0~100)
  rainSensitivity: number // 강수 민감도 (지하철: +, 버스: +, 따릉이: -)
  district?: string
  stId?: string // 버스 정류소 고유 ID (공공 API 연동)
  arsId?: string // 버스 정류소 5자리 번호
  isHub?: boolean // 환승센터 등 메이저 거점
  stationNo?: string // 따릉이 대여소 번호
  rackCount?: number // 따릉이 총 거치대 수
  isPopularSpot?: boolean // 따릉이 인기 핫스팟
}

// ── 서울 및 수도권 전체 지하철역(561개) + 버스 환승센터(55개) + 따릉이 거점(52개) ──
export const TRANSIT_STOPS: TransitStop[] = [
  // 1. 지하철역 (SUBWAY_STATIONS 마스터 데이터 561개 연동)
  ...SUBWAY_STATIONS.map(s => ({
    id: s.id,
    name: s.name,
    type: 'subway' as const,
    coords: s.coords,
    lineInfo: s.lines.join(' · '),
    baseCrowd: s.baseCrowd,
    rainSensitivity: 1.2
  })),

  // 2. 버스 정류소 및 주요 환승센터 (BUS_STOPS 55개 연동)
  ...BUS_STOPS.map(b => ({
    id: b.id,
    name: b.name,
    type: 'bus' as const,
    coords: b.coords,
    lineInfo: b.lineInfo,
    baseCrowd: b.baseCrowd,
    rainSensitivity: b.rainSensitivity,
    district: b.district,
    stId: b.stId,
    arsId: b.arsId,
    isHub: b.isHub
  })),

  // 3. 따릉이 거점 대여소 (BIKE_STATIONS 52개 연동)
  ...BIKE_STATIONS.map(k => ({
    id: k.id,
    name: k.name,
    type: 'bike' as const,
    coords: k.coords,
    lineInfo: k.lineInfo,
    baseCrowd: k.baseCrowd,
    rainSensitivity: k.rainSensitivity,
    district: k.district,
    stationNo: k.stationNo,
    rackCount: k.rackCount,
    isPopularSpot: k.isPopularSpot
  }))
]


export interface StopDetailData {
  loading?: boolean
  weather?: any
  aiPrediction?: any
  arrivals?: any[]
}

interface TransitMapProps {
  filterType: 'all' | 'subway' | 'bus' | 'bike'
  rainMm: number
  selectedTime: string
  liveWeather?: any
  focusedCoords?: [number, number] | null
  selectedBusStation?: {
  id: string
  name: string
  arsId: string
  coords: [number, number]
} | null
  onSelectStop?: (stop: TransitStop | null, details?: StopDetailData) => void
  activeRoute?: TransitRouteResult | null
  onClearRoute?: () => void
}

interface MarkerItem {
  marker: any
  stop: TransitStop
  el: HTMLDivElement
  priority: number
}

// 🚌 서울시 버스 노선별 경유 정류장 데이터 (기존 지하철 경로 타입과 분리)
type BusRouteStation = {
  sequence: number
  name: string
  stId: string
  arsId: string
  coords: [number, number]
}

type SelectedBusRoute = {
  id: string
  name: string
  stationId: string
}

// 서울시 도착정보와 GPS 위치를 차량 ID로 연결한 첫차·다음 차 정보
type ApproachingBusVehicle = {
  vehicle_id: string
  plate_no: string
  coords: [number, number]
  section_order: string | number
  at_stop: boolean
  data_time?: string
  arrival_order: number
  arrival_message: string
}

// 버스 도착정보 표시
type BusArrival = {
  route_name: string
  station_name: string
  arrival_msg1: string
  arrival_msg2: string
  station_order: string
  bus_route_id: string
}

async function loadBusArrivals(
  stationId: string,
  container: HTMLElement,
  onSelectRoute?: (routeId: string, routeName: string, stationId: string) => void
) {
  container.textContent = '버스 도착정보 불러오는 중...'
  container.style.color = '#94A3B8'
  container.style.fontSize = '12px'

  try {
    const response = await fetch(
      `${API_BASE_URL}/api/v1/transit/bus/arrival?stId=${encodeURIComponent(stationId)}`
    )

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const data = await response.json()
    const arrivals: BusArrival[] = data.arrivals || []

    container.replaceChildren()

    if (arrivals.length === 0) {
      container.textContent = '현재 조회 가능한 도착정보가 없습니다.'
      return
    }

    for (const arrival of arrivals) {
      const row = document.createElement('div')

      Object.assign(row.style, {
        marginTop: '12px',
        paddingTop: '10px',
        borderTop: '1px solid rgba(255,255,255,0.12)'
      })

      const route = document.createElement('button')
      route.type = 'button'
      route.textContent = `🚌 ${arrival.route_name}번  ·  노선 보기 ↗`
      route.title = `${arrival.route_name}번 버스 노선 표시`
      route.disabled = !arrival.bus_route_id || !onSelectRoute

      Object.assign(route.style, {
        color: '#34D399',
        fontWeight: '700',
        fontSize: '14px',
        background: 'transparent',
        border: 'none',
        padding: '0',
        cursor: route.disabled ? 'default' : 'pointer',
        textAlign: 'left',
        opacity: route.disabled ? '0.65' : '1'
      })
      if (!route.disabled && onSelectRoute) {
        route.addEventListener('click', (event) => {
          event.stopPropagation()
          onSelectRoute(arrival.bus_route_id, arrival.route_name, stationId)
        })
      }

      const firstArrival = document.createElement('div')
      firstArrival.textContent =
        `첫 번째: ${arrival.arrival_msg1 || '정보 없음'}`
      firstArrival.style.color = '#F0F6FF'
      firstArrival.style.marginTop = '6px'

      const secondArrival = document.createElement('div')
      secondArrival.textContent =
        `두 번째: ${arrival.arrival_msg2 || '정보 없음'}`
      secondArrival.style.color = '#94A3B8'
      secondArrival.style.marginTop = '4px'

      row.append(route, firstArrival, secondArrival)
      container.appendChild(row)
    }
  } catch (error) {
    console.error('버스 도착정보 조회 실패:', error)
    container.textContent = '도착정보를 불러오지 못했습니다.'
    container.style.color = '#FCA5A5'
  }
}


export default function TransitMap({ filterType, rainMm, selectedTime, liveWeather, focusedCoords, selectedBusStation ,onSelectStop, activeRoute, onClearRoute }: TransitMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<any>(null)
  const markerItemsRef = useRef<MarkerItem[]>([])
  const routeMarkersRef = useRef<any[]>([])
  const animFrameRef = useRef<number | null>(null)
  const activePopupRef = useRef<any>(null)
  const popupOpenedZoomRef = useRef<number | null>(null)
  const isFlyingRef = useRef<boolean>(false)
  const initialRestoreDoneRef = useRef<boolean>(false)
  const isInitialRestoringRef = useRef<boolean>(false)
  const prevActiveRouteRef = useRef<any>(null)
  const [activeStop, setActiveStop] = useState<TransitStop | null>(null)
  const [mapLoaded, setMapLoaded] = useState(false)
  // 실시간 API로 불러온 거점 외 따릉이 대여소 (기존 마커 파이프라인에 합쳐 표시)
  const [liveBikeStops, setLiveBikeStops] = useState<TransitStop[]>([])
  const [zoomLevel, setZoomLevel] = useState<number>(13)

  // 🚌 선택한 버스 노선은 지하철 activeRoute와 별도 레이어로 관리
  const [selectedBusRoute, setSelectedBusRoute] = useState<SelectedBusRoute | null>(null)
  const [busRouteStations, setBusRouteStations] = useState<BusRouteStation[]>([])
  const [busRouteLoading, setBusRouteLoading] = useState(false)
  const [busRouteError, setBusRouteError] = useState('')
  const [approachingBusVehicles, setApproachingBusVehicles] = useState<ApproachingBusVehicle[]>([])
  const [approachingBusLoading, setApproachingBusLoading] = useState(false)
  const [approachingBusError, setApproachingBusError] = useState('')
  const [approachingBusMessage, setApproachingBusMessage] = useState('')
  const selectBusRouteRef = useRef<(routeId: string, routeName: string, stationId: string) => void>(() => {})
  selectBusRouteRef.current = (routeId, routeName, stationId) => {
    if (routeId && stationId) setSelectedBusRoute({ id: routeId, name: routeName, stationId })
  }

  // 클로저 트랩 방지용 최신 상태 참조 Refs
  const activeRouteRef = useRef<TransitRouteResult | null>(activeRoute || null)
  activeRouteRef.current = activeRoute || null

  const focusedCoordsRef = useRef<[number, number] | null>(focusedCoords || null)
  focusedCoordsRef.current = focusedCoords || null

  const activeStopRef = useRef<TransitStop | null>(activeStop || null)
  activeStopRef.current = activeStop || null

  const updateCollisionsRef = useRef<() => void>(() => {})

  // 혼잡도 계산 헬퍼 (AI 시계열 예측 시뮬레이션: 역별 위계, 시간대별 출퇴근 첨두곡선, 날씨 강수 민감도 반영)
  const calculateCrowd = (stop: TransitStop) => {
    const base = stop.baseCrowd || 55

    // 1. 시간대(selectedTime) 승하차 계수 반영 (출퇴근 피크 / 낮 시간 완화 / 심야 급감)
    const hour = parseInt(selectedTime.replace(/[^0-9]/g, ''), 10) || 8
    let timeMultiplier = 1.0
    if (hour >= 8 && hour <= 9) {
      timeMultiplier = 1.25 // 오전 출근 첨두시간 (Peak)
    } else if (hour === 7) {
      timeMultiplier = 1.15 // 출근 초입
    } else if (hour >= 18 && hour <= 19) {
      timeMultiplier = 1.22 // 퇴근 첨두시간 (Peak)
    } else if (hour === 17) {
      timeMultiplier = 1.15 // 퇴근 초입 (17시)
    } else if (hour === 20) {
      timeMultiplier = 1.12 // 퇴근 후반
    } else if (hour >= 12 && hour <= 13) {
      timeMultiplier = 1.02 // 점심시간 이동
    } else if (hour >= 10 && hour <= 16) {
      timeMultiplier = 0.78 // 평시 낮 시간대 (Off-peak)
    } else if (hour >= 21 && hour <= 22) {
      timeMultiplier = 0.70 // 늦은 저녁
    } else {
      timeMultiplier = 0.42 // 심야 및 첫차 전 (23시~06시)
    }

    // 2. 고유 역 해시 미세 편차 (±3% 결정론적 분산으로 인접 역간 자연스러운 편차 부여)
    const hash = stop.name.split('').reduce((acc, char) => ((acc << 5) - acc) + char.charCodeAt(0), 0)
    const hashOffset = (Math.abs(hash) % 7) - 3

    // 3. 기상(강수량 rainMm) 영향 반영
    if (stop.type === 'bike') {
      // 비가 오면 자전거(따릉이) 이용 급격히 감소
      const bikeRainPenalty = Math.round(stop.rainSensitivity * rainMm * 7.5)
      const crowd = Math.round(base * (hour >= 23 || hour <= 5 ? 0.35 : 1.0)) + bikeRainPenalty
      return Math.max(5, Math.min(95, crowd))
    } else {
      // 비가 오면 대중교통(지하철/버스) 집중 및 환승 혼잡 증가
      const rainBonus = Math.min(15, Math.round(stop.rainSensitivity * rainMm * 2.2))
      const crowd = Math.round(base * timeMultiplier) + hashOffset + rainBonus
      return Math.max(10, Math.min(99, crowd))
    }
  }

  // 혼잡도 색상 및 라벨 헬퍼
  const getCrowdLevel = (crowd: number) => {
    if (crowd < 45) return { label: '여유', color: '#10B981', bg: 'rgba(16, 185, 129, 0.15)' }
    if (crowd < 75) return { label: '보통', color: '#38BDF8', bg: 'rgba(56, 189, 248, 0.15)' }
    return { label: '혼잡', color: '#F43F5E', bg: 'rgba(244, 63, 94, 0.15)' }
  }

  // 1. MapLibre GL 지도 초기화
  useEffect(() => {
    if (!mapContainerRef.current) return
    if (typeof maplibregl === 'undefined') {
      console.error('MapLibre GL JS가 로드되지 않았습니다.')
      return
    }

    const savedView = getSavedMapView()
    const initialCenter = savedView?.center || [127.050, 37.505] // 저장된 위치 또는 기본 강남구 중심
    const initialZoom = savedView?.zoom ?? 13
    // 위치(중심·줌)만 복원하고, 시야각(틸트)·방위각은 저장값과 무관하게 매 새로고침마다 탑뷰·정북으로 초기화
    const initialPitch = DEFAULT_MAP_PITCH
    const initialBearing = DEFAULT_MAP_BEARING

    if (savedView?.zoom) {
      setZoomLevel(savedView.zoom)
    }

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        sources: {
          'osm-tiles': {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            maxzoom: 19,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>',
          },
        },
        layers: [
          {
            id: 'osm-tiles-layer',
            type: 'raster',
            source: 'osm-tiles',
            minzoom: 6,
            maxzoom: 19,
          },
        ],
      },
      center: initialCenter,
      zoom: initialZoom,
      minZoom: 6.8, // 대한민국 전국 뷰 이하로 축소 방지 (글로벌 타일 로딩 원천 차단)
      maxZoom: 18.5, // 세부 역사/정류소 수준 확대 허용
      maxBounds: KOREA_BOUNDS, // 대한민국 영토 밖으로 패닝/이동 차단 (네트워크 & 메모리 리소스 절약)
      pitch: initialPitch,
      bearing: initialBearing,
    })

    // 컨트롤 추가
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'top-right')
    map.addControl(new maplibregl.ScaleControl({ maxWidth: 100, unit: 'metric' }), 'bottom-left')
    map.addControl(new maplibregl.GeolocateControl({ positionOptions: { enableHighAccuracy: true }, trackUserLocation: true }), 'top-right')

    map.on('load', () => {
      // 0. 수도권 전철 전체 노선망 배경 벡터 레이어 (공식 호선별 고유 컬러)
      map.addSource('subway-network', {
        type: 'geojson',
        data: SUBWAY_NETWORK_GEOJSON,
      })

      // 노선 외곽 케이싱 (다크 콘트라스트)
      map.addLayer({
        id: 'subway-network-casing',
        type: 'line',
        source: 'subway-network',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: {
          'line-color': '#0B1120',
          'line-width': [
            'interpolate', ['linear'], ['zoom'],
            9, 2.0,
            12, 3.8,
            15, 6.0,
          ],
          'line-opacity': 0.8,
        },
      })

      // 노선 중심 컬러선 (호선별 고유 색상 매핑)
      map.addLayer({
        id: 'subway-network-line',
        type: 'line',
        source: 'subway-network',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: {
          'line-color': ['get', 'color'],
          'line-width': [
            'interpolate', ['linear'], ['zoom'],
            9, 1.2,
            12, 2.4,
            15, 4.2,
          ],
          'line-opacity': 0.85,
        },
      })

      // 검색된 경로(Active Transit Route) GeoJSON 소스 및 레이어 추가
      map.addSource('active-route', {
        type: 'geojson',
        data: {
          type: 'Feature',
          properties: {},
          geometry: {
            type: 'LineString',
            coordinates: [],
          },
        },
      })

      // 활성 경로 외곽선 (글로우 네온 효과)
      map.addLayer({
        id: 'active-route-glow',
        type: 'line',
        source: 'active-route',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: {
          'line-color': '#06B6D4',
          'line-width': 12,
          'line-opacity': 0.7,
        },
      })

      // 활성 경로 중심선 (선명한 흰/청빛 코어)
      map.addLayer({
        id: 'active-route-core',
        type: 'line',
        source: 'active-route',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: {
          'line-color': '#F0F9FF',
          'line-width': 5,
        },
      })

      // 멀티모달 구간별(따릉이/버스/지하철/도보) 컬러 폴리라인 소스 및 레이어
      map.addSource('multimodal-segments', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: [],
        },
      })

      map.addLayer({
        id: 'multimodal-segments-line',
        type: 'line',
        source: 'multimodal-segments',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: {
          'line-color': ['coalesce', ['get', 'color'], '#38BDF8'],
          'line-width': 6,
          'line-opacity': 0.95,
        },
      })

      setMapLoaded(true)
    })

    const saveCurrentMapView = () => {
      try {
        const center = map.getCenter()
        const zoom = map.getZoom()
        // 위치(중심·줌)만 영속화 — 시야각·방위각은 새로고침 시 항상 기본값(탑뷰·정북)으로 초기화되므로 저장하지 않는다.
        localStorage.setItem(STORAGE_MAP_VIEW_KEY, JSON.stringify({
          center: [Math.round(center.lng * 1000000) / 1000000, Math.round(center.lat * 1000000) / 1000000],
          zoom: Math.round(zoom * 100) / 100,
        }))
      } catch {}
    }

    map.on('moveend', saveCurrentMapView)
    map.on('zoomend', saveCurrentMapView)

    mapInstanceRef.current = map

    return () => {
      saveCurrentMapView()
      map.off('moveend', saveCurrentMapView)
      map.off('zoomend', saveCurrentMapView)
      map.remove()
    }
  }, [])

  // 1-2. 검색 등으로 focusedCoords 지정 시 카메라 부드러운 이동 (flyTo)
  useEffect(() => {
    if (!mapLoaded || !mapInstanceRef.current || !focusedCoords) return
    mapInstanceRef.current.flyTo({
      center: focusedCoords,
      zoom: 15,
      pitch: DEFAULT_MAP_PITCH,
      essential: true,
    })
  }, [focusedCoords, mapLoaded])

  // 검색으로 선택한 버스정류장 마커 표시
  useEffect(() => {
    console.log('[버스 마커 확인]', {
      mapLoaded,
      selectedBusStation,
      mapExists: !!mapInstanceRef.current,
    })

    if (!mapLoaded || !mapInstanceRef.current || !selectedBusStation) {
      return
    }

    const map = mapInstanceRef.current

    const el = document.createElement('div')
    el.textContent = '🚌'
    el.title = selectedBusStation.name

    Object.assign(el.style, {
      fontSize: '24px',
      cursor: 'pointer',
      background: '#111D35',
      border: '2px solid #34D399',
      borderRadius: '50%',
      width: '42px',
      height: '42px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      boxShadow: '0 0 18px rgba(52,211,153,0.5)',
    })
    const popupContent = document.createElement('div')

    Object.assign(popupContent.style, {
      padding: '10px 14px',
      background: '#111D35',
      borderRadius: '10px',
      fontFamily: "'Outfit', 'Noto Sans KR', sans-serif",
      minWidth: '180px'
    })

const title = document.createElement('strong')
title.textContent = `🚌 ${selectedBusStation.name}`

Object.assign(title.style, {
  color: '#F0F6FF',
  fontSize: '14px',
  fontWeight: '800'
})

const number = document.createElement('div')
number.textContent = `정류장 번호: ${selectedBusStation.arsId}`

Object.assign(number.style, {
  marginTop: '8px',
  color: '#94A3B8',
  fontSize: '11px'
})

popupContent.append(title, number)

  const arrivalContainer = document.createElement('div')
  popupContent.appendChild(arrivalContainer)

  const popup = new maplibregl.Popup({ offset: 25 })
    .setDOMContent(popupContent)

  popup.on('open', () => {
    loadBusArrivals(selectedBusStation.id, arrivalContainer, (id, name, stationId) => selectBusRouteRef.current(id, name, stationId))
})


  // 팝업은 위에서 한 번만 생성했으므로 다시 선언하지 않음
  const marker = new maplibregl.Marker({ element: el })
    .setLngLat(selectedBusStation.coords)
    .setPopup(popup)
    .addTo(map)

  return () => {
    marker.remove()
  }
}, [mapLoaded, selectedBusStation])

  // 역/정류소 중요도 가중치 계산 (환승역 및 주요 환승센터/대형 거점 우선 노출)
  const calculateStationPriority = (stop: TransitStop): number => {
    let score = 0
    if (stop.type === 'subway') {
      score += 120
      const lineCount = stop.lineInfo ? stop.lineInfo.split(/[·,]/).length : 1
      score += lineCount * 30
      score += stop.baseCrowd * 0.2
      const majorHubs = [
        '서울역', '강남역', '신도림역', '구로역', '잠실역', '여의도역', '홍대입구역',
        '시청역', '고속터미널역', '왕십리역', '용산역', '청량리역', '수원역', '판교역',
        '사당역', '동대문역사문화공원역', '종로3가역', '가산디지털단지역', '교대역', '선릉역',
        '건대입구역', '신림역', '노원역', '영등포역'
      ]
      if (majorHubs.includes(stop.name)) score += 200
    } else if (stop.type === 'bus') {
      score += 70
      if (stop.isHub) score += 180 // 대형 광역환승센터(서울역, 잠실, 여의도, 사당, 강변 등)
      score += stop.baseCrowd * 0.25
    } else {
      score += 40
      if (stop.isPopularSpot) score += 160 // 한강공원/대형공원 핫스팟
      score += (stop.rackCount || 20) * 1.5
    }
    return score
  }

  // 겹침 방지 및 줌 레벨 기반 마커 가시성 동적 필터링
  const updateCollisions = () => {
    const map = mapInstanceRef.current
    if (!map) return

    const bounds = map.getBounds()
    const container = map.getContainer()
    if (!container) return
    const width = container.clientWidth
    const height = container.clientHeight
    const currentZoom = map.getZoom()

    const currentRoute = activeRouteRef.current
    const currentFocused = focusedCoordsRef.current
    const currentActiveStop = activeStopRef.current

    // 줌아웃(Zoom < 11.0 또는 팝업 오픈 시점 대비 1.2 이상 축소) 시 열려 있던 역 정보 팝업 자동 닫기 (비행 애니메이션 중에는 닫지 않음)
    const isZoomedOut = !isFlyingRef.current && (
      currentZoom < 11.0 || 
      (popupOpenedZoomRef.current !== null && currentZoom < popupOpenedZoomRef.current - 1.2)
    )
    if (isZoomedOut) {
      if (activePopupRef.current) {
        activePopupRef.current.remove()
        activePopupRef.current = null
      }
      if (activeStop) {
        setActiveStop(null)
      }
      try {
        localStorage.removeItem(STORAGE_SELECTED_STOP_KEY)
      } catch {}
      popupOpenedZoomRef.current = null
    }

    const hasActiveRoute = !!(currentRoute && ((currentRoute.path && currentRoute.path.length >= 2) || (currentRoute.segments && currentRoute.segments.length > 0)))
    const routeStationNames = new Set<string>()
    if (hasActiveRoute && currentRoute) {
      if (currentRoute.path) {
        currentRoute.path.forEach(p => routeStationNames.add(p.name))
      }
      if (currentRoute.segments) {
        currentRoute.segments.forEach(seg => {
          if (seg.from_name) routeStationNames.add(seg.from_name)
          if (seg.to_name) routeStationNames.add(seg.to_name)
        })
      }
    }

    // ── 줌 레벨별 단계적 가시성 (Multi-tier Zoom Visibility) 정책 ──
    // 0. 초광역 뷰 (Zoom < 10.5): 모든 마커 100% 숨김 (수도권/전국 단위 축소 시 점 마커 뭉침 현상 원천 차단)
    const isUltraWideZoom = currentZoom < 10.5 && !hasActiveRoute

    // 1. 중간 광역 뷰 (10.5 <= Zoom < 11.5): 버스/따릉이 100% 숨김, 지하철 Tier 1 메이저 허브만 미니 점(Dot) 표출 (점끼리 충돌 필터링 적용)
    const isWideAreaZoom = currentZoom >= 10.5 && currentZoom < 11.5 && !hasActiveRoute

    // 2. 중거리 도심 원경 (11.5 <= Zoom < 12.5):
    //    버스는 주요 환승센터(isHub), 따릉이는 주요 인기거점(isPopularSpot)만 '점(Dot)'으로 표출
    const isMidRangeFar = currentZoom >= 11.5 && currentZoom < 12.5 && !hasActiveRoute

    // 3. 중거리 도심 근경 (12.5 <= Zoom < 13.5):
    //    전체 버스/따릉이가 지도에 등장하되, 글자 가림 방지를 위해 무조건 '점(Dot)' 마커로만 정갈하게 표출!
    const isMidRangeNear = currentZoom >= 12.5 && currentZoom < 13.5 && !hasActiveRoute

    const placedBoxes: { x1: number; y1: number; x2: number; y2: number }[] = []

    // 줌 레벨에 따라 겹침 감지 박스 크기 동적 조절 (확대할수록 간격 좁아져 많은 역 등장)
    const halfW = currentZoom >= 16 ? 32 : (currentZoom >= 14 ? 44 : (currentZoom >= 13 ? 56 : 72))
    const halfH = currentZoom >= 16 ? 12 : (currentZoom >= 14 ? 16 : (currentZoom >= 13 ? 20 : 26))

    for (const item of markerItemsRef.current) {
      const [lng, lat] = item.stop.coords

      // 1. 활성 경로가 있는 경우:
      // - 사용자가 명시적으로 해당 수단 필터(예: 따릉이 filterType='bike')를 선택했거나,
      // - 경로 세그먼트에 포함된 대여소/정류소는 숨기지 않고 표출!
      if (hasActiveRoute && currentRoute) {
        const isFilterMatched = filterType && filterType === item.stop.type
        const isSegmentStop = routeStationNames.has(item.stop.name) || 
                              routeStationNames.has(item.stop.name.replace(/\(.*?\)/g, '').trim()) ||
                              (currentRoute.segments && currentRoute.segments.some(seg => 
                                (seg.mode === item.stop.type) && 
                                (item.stop.name.includes(seg.from_name) || item.stop.name.includes(seg.to_name) ||
                                 seg.from_name.includes(item.stop.name) || seg.to_name.includes(item.stop.name))
                              ))

        if (!isFilterMatched && !isSegmentStop && (item.stop.type !== 'subway' || !routeStationNames.has(item.stop.name))) {
          item.el.style.display = 'none'
          continue
        }
        const firstPathStep = currentRoute.path[0]
        const lastPathStep = currentRoute.path[currentRoute.path.length - 1]
        const nearStartPin = firstPathStep && Math.abs(lng - firstPathStep.coords[0]) < 0.0015 && Math.abs(lat - firstPathStep.coords[1]) < 0.0015
        const nearEndPin = lastPathStep && Math.abs(lng - lastPathStep.coords[0]) < 0.0015 && Math.abs(lat - lastPathStep.coords[1]) < 0.0015
        const isTransferPin = (currentRoute.transferStations && currentRoute.transferStations.includes(item.stop.name)) ||
                              (currentRoute.transferTrains && currentRoute.transferTrains.some(t => t.station === item.stop.name))
        // 출발역, 도착역, 환승역(또는 출발/도착 핀 반경 150m 이내 역)은 전용 핀 마커가 배치되므로 일반 알약 마커를 완전히 숨겨서 겹침 원천 방지
        const isSpecialPinStation = item.stop.name === currentRoute.from || 
                                    item.stop.name === currentRoute.to || 
                                    item.stop.name === firstPathStep?.name ||
                                    item.stop.name === lastPathStep?.name ||
                                    nearStartPin ||
                                    nearEndPin ||
                                    isTransferPin
        if (isSpecialPinStation) {
          item.el.style.display = 'none'
          continue
        }
      }

      // 2. 지도 뷰포트 영역 외는 빠른 제외
      if (!bounds.contains([lng, lat])) {
        item.el.style.display = 'none'
        continue
      }

      // 3. 화면 픽셀 좌표 투영
      const pt = map.project([lng, lat])

      // 화면 경계 밖 체크
      if (pt.x < -halfW || pt.x > width + halfW || pt.y < -halfH || pt.y > height + halfH) {
        item.el.style.display = 'none'
        continue
      }

      // 4. 현재 검색되었거나 클릭하여 선택된 역, 또는 활성 경로 경유 역은 줌 레벨 무관 무조건 우선 알약 표시!
      const isFocused = currentFocused && Math.abs(lng - currentFocused[0]) < 0.0002 && Math.abs(lat - currentFocused[1]) < 0.0002
      const isSelected = currentActiveStop && currentActiveStop.id === item.stop.id
      const isOnRoute = hasActiveRoute && routeStationNames && routeStationNames.has(item.stop.name)
      const isTransferStation = hasActiveRoute && currentRoute?.transferStations?.includes(item.stop.name)

      if (isFocused || isSelected || isOnRoute) {
        const pillView = item.el.querySelector('.marker-pill-view') as HTMLElement | null
        const dotView = item.el.querySelector('.marker-dot-view') as HTMLElement | null
        if (pillView) pillView.style.display = 'flex'
        if (dotView) dotView.style.display = 'none'

        item.el.style.display = 'flex'
        item.el.style.zIndex = isSelected ? '99999' : (isTransferStation ? '1500' : (isOnRoute ? '900' : '9999'))

        const pill = item.el.querySelector('.marker-pill') as HTMLElement | null
        if (pill) {
          if (isTransferStation) {
            pill.style.borderColor = '#F59E0B'
            pill.style.boxShadow = '0 4px 18px rgba(245, 158, 11, 0.75)'
          } else {
            const crowd = calculateCrowd(item.stop)
            const { color } = getCrowdLevel(crowd)
            pill.style.borderColor = color
            pill.style.boxShadow = isSelected ? `0 0 20px ${color}` : '0 4px 14px rgba(0,0,0,0.5)'
          }
        }

        placedBoxes.push({
          x1: pt.x - halfW,
          y1: pt.y - halfH,
          x2: pt.x + halfW,
          y2: pt.y + halfH,
        })

        // 클릭하여 선택된 역의 상단에 열리는 정보 팝업 영역을 충돌 박스로 등록!
        if (isSelected) {
          placedBoxes.push({
            x1: pt.x - 130,
            y1: pt.y - 150,
            x2: pt.x + 130,
            y2: pt.y - 5,
          })
        }
        continue
      }

      // ── [줌 레벨별 단계적 가시성 필터링] ──

      // [규칙 0] 초광역 뷰 (Zoom < 10.5):
      // - 대축척 광역 뷰에서는 점 마커들이 도심부에 까맣게 뭉치므로 모든 마커 100% 숨김
      if (isUltraWideZoom) {
        item.el.style.display = 'none'
        continue
      }

      // [규칙 1] 중간 광역 뷰 (10.5 <= Zoom < 11.5):
      // - 버스와 따릉이는 100% 완전히 숨김 (화면 난잡함 방지)
      // - 지하철도 Tier 1 메이저 허브(priority >= 250)만 점(Dot) 마커로 표출하되, 점끼리도 충돌 검사하여 뭉침 방지
      if (isWideAreaZoom) {
        if (item.stop.type === 'bus' || item.stop.type === 'bike') {
          item.el.style.display = 'none'
          continue
        }
        if (item.priority < 250) {
          item.el.style.display = 'none'
          continue
        }

        // 점 마커 충돌 박스 (반경 12px)
        const dotRadius = 12
        const dotBox = {
          x1: pt.x - dotRadius,
          y1: pt.y - dotRadius,
          x2: pt.x + dotRadius,
          y2: pt.y + dotRadius,
        }

        const hasCollision = placedBoxes.some(b =>
          !(dotBox.x2 < b.x1 || dotBox.x1 > b.x2 || dotBox.y2 < b.y1 || dotBox.y1 > b.y2)
        )

        if (hasCollision) {
          item.el.style.display = 'none'
          continue
        }

        placedBoxes.push(dotBox)

        // 광역 메이저 허브는 점 마커로 표출
        const pillView = item.el.querySelector('.marker-pill-view') as HTMLElement | null
        const dotView = item.el.querySelector('.marker-dot-view') as HTMLElement | null
        if (pillView) pillView.style.display = 'none'
        if (dotView) dotView.style.display = 'flex'
        item.el.style.display = 'flex'
        item.el.style.zIndex = '5'
        continue
      }

      // [규칙 2] 중거리 도심 원경 (11.5 <= Zoom < 12.5):
      // - 버스: 대형 광역환승센터(isHub)만 점(Dot) 마커로 표출, 일반 정류소 숨김
      // - 따릉이: 대형공원 인기 거점(isPopularSpot)만 점(Dot) 마커로 표출, 일반 대여소 숨김
      // - 지하철: 환승역(priority >= 180)만 표출, 일반 지엽 역은 숨김
      if (isMidRangeFar) {
        if (item.stop.type === 'bus' && !item.stop.isHub) {
          item.el.style.display = 'none'
          continue
        }
        if (item.stop.type === 'bike' && !item.stop.isPopularSpot) {
          item.el.style.display = 'none'
          continue
        }
        if (item.stop.type === 'subway' && item.priority < 180 && currentZoom < 12.0) {
          item.el.style.display = 'none'
          continue
        }
      }

      // [규칙 3] 중거리 뷰 (11.5 <= Zoom < 13.5)에서 버스와 따릉이는 거대한 알약 마커 금지!
      // 오직 원형 점(Dot) 마커로만 단정하게 찍혀서 도로와 도시 가림을 원천 방지
      const forceDotForNonSubway = (isMidRangeFar || isMidRangeNear) && (item.stop.type === 'bus' || item.stop.type === 'bike')

      item.el.style.zIndex = '1'

      // 5. 충돌(Collision) 검사
      const x1 = pt.x - halfW
      const y1 = pt.y - halfH
      const x2 = pt.x + halfW
      const y2 = pt.y + halfH

      // 만약 선택된 역의 상단 팝업 창 영역과 직접 겹치면 팝업 가림 방지를 위해 완전히 숨김
      if (currentActiveStop) {
        const activePt = map.project(currentActiveStop.coords)
        const popX1 = activePt.x - 130
        const popY1 = activePt.y - 150
        const popX2 = activePt.x + 130
        const popY2 = activePt.y - 5
        if (x1 < popX2 && x2 > popX1 && y1 < popY2 && y2 > popY1) {
          item.el.style.display = 'none'
          continue
        }
      }

      let overlaps = false
      for (const box of placedBoxes) {
        if (x1 < box.x2 && x2 > box.x1 && y1 < box.y2 && y2 > box.y1) {
          overlaps = true
          break
        }
      }

      const pillView = item.el.querySelector('.marker-pill-view') as HTMLElement | null
      const dotView = item.el.querySelector('.marker-dot-view') as HTMLElement | null

      // 겹치거나 forceDotForNonSubway(중거리 뷰의 버스/따릉이)인 경우 ➔ 혼잡도 색상의 원형 점(Dot) 마커로 표출!
      if (overlaps || forceDotForNonSubway) {
        if (pillView) pillView.style.display = 'none'
        if (dotView) dotView.style.display = 'flex'
        item.el.style.display = 'flex'
        item.el.style.zIndex = '5'
      } else {
        // 상세 배율(Zoom >= 13.5)에서 여유 공간 확보 시 온전한 알약 마커(이름 + 아이콘 + 혼잡도%)로 표시
        if (pillView) pillView.style.display = 'flex'
        if (dotView) dotView.style.display = 'none'
        item.el.style.display = 'flex'
        item.el.style.zIndex = '10'
        placedBoxes.push({ x1, y1, x2, y2 })
      }
    }
  }

  updateCollisionsRef.current = updateCollisions


  // 🚌 지도 주변 실제 버스정류장 자동 표시
  useEffect(() => {
    if (!mapLoaded || !mapInstanceRef.current) return
    if (filterType !== 'bus' && filterType !== 'all') return

    const map = mapInstanceRef.current
    const sourceId = 'live-bus-stations'
    const layerId = 'live-bus-stations-circle'

    let controller: AbortController | null = null
    let timer: ReturnType<typeof setTimeout> | null = null
    let disposed = false

    // 주변 정류장 표시용 GeoJSON 소스
    map.addSource(sourceId, {
      type: 'geojson',
      data: {
        type: 'FeatureCollection',
        features: []
      }
    })

    // 정류장을 초록색 원으로 표시
    map.addLayer({
      id: layerId,
      type: 'circle',
      source: sourceId,
      minzoom: 15,
      paint: {
        'circle-radius': [
          'interpolate', ['linear'], ['zoom'],
          14, 4,
          16, 7,
          18, 10
        ],
        'circle-color': '#34D399',
        'circle-stroke-color': '#FFFFFF',
        'circle-stroke-width': 2,
        'circle-opacity': 0.95
      }
    })

    const setStations = (features: any[]) => {
      const source = map.getSource(sourceId) as any
      source?.setData({
        type: 'FeatureCollection',
        features
      })
    }

    const loadNearbyStations = async () => {
      controller?.abort()
      controller = new AbortController()

      // 너무 멀리 축소한 상태에서는 표시하지 않음
      if (map.getZoom() < 15) {
        setStations([])
        return
      }

      const center = map.getCenter()
      const bounds = map.getBounds()

      try {
        const params = new URLSearchParams({
          lat: String(center.lat),
          lng: String(center.lng),
          radius: '500'
        })
        const reqUrl = `${API_BASE_URL || ''}/api/v1/transit/bus/stations/nearby?${params.toString()}`

        const response = await fetch(reqUrl, {
          signal: controller.signal
        })

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const data = await response.json()

        if (disposed) return

        const stations = (data.stations || []).filter(
          (station: any) =>
            station.id &&
            station.coords &&
            !station.name.includes('(미정차)') &&
            bounds.contains(station.coords)
        )

        const features = stations.map((station: any) => ({
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: station.coords
          },
          properties: {
            stId: station.stId,
            name: station.name,
            arsId: station.arsId
          }
        }))

        setStations(features)
        console.log(
          `[서울 버스] 주변 정류장 ${features.length}개 표시`
        )
      } catch (error) {
        if (controller?.signal.aborted || disposed) return

        console.error('주변 버스정류장 조회 실패:', error)
        setStations([])
      }
    }

    // 지도 이동 후 잠시 기다렸다가 조회
    const scheduleUpdate = () => {
      if (timer) clearTimeout(timer)

      controller?.abort()

      timer = setTimeout(() => {
        loadNearbyStations()
      }, 350)
    }

    // 정류장 원 클릭 시 팝업 표시
    const handleStationClick = (e: any) => {
      const feature = e.features?.[0]
      if (!feature || feature.geometry?.type !== 'Point') return

      const coords = feature.geometry.coordinates as [number, number]
      const properties = feature.properties || {}

      const content = document.createElement('div')
      content.style.padding = '10px'
      content.style.background = '#111D35'
      content.style.borderRadius = '8px'

      const title = document.createElement('strong')
      title.textContent = `🚌 ${properties.name || '버스정류장'}`
      title.style.color = '#F0F6FF'

      const number = document.createElement('div')
      number.textContent = `정류장 번호: ${properties.arsId || '-'}`
      number.style.color = '#94A3B8'
      number.style.marginTop = '7px'

      content.append(title, number)

      // 주변 정류장에서도 검색 마커와 동일한 실시간 도착정보 제공
      const arrivalContainer = document.createElement('div')
      content.appendChild(arrivalContainer)

      const popup = new maplibregl.Popup({ offset: 12 })
        .setLngLat(coords)
        .setDOMContent(content)

      popup.on('open', () => {
        const stationId = String(properties.stId || '')
        if (stationId) {
          loadBusArrivals(stationId, arrivalContainer, (id, name) => selectBusRouteRef.current(id, name, stationId))
        } else {
          arrivalContainer.textContent = '정류장 ID가 없어 도착정보를 조회할 수 없습니다.'
          arrivalContainer.style.color = '#FCA5A5'
        }
      })

      popup.addTo(map)
    }

    const onMouseEnter = () => {
      map.getCanvas().style.cursor = 'pointer'
    }

    const onMouseLeave = () => {
      map.getCanvas().style.cursor = ''
    }

    map.on('moveend', scheduleUpdate)
    map.on('click', layerId, handleStationClick)
    map.on('mouseenter', layerId, onMouseEnter)
    map.on('mouseleave', layerId, onMouseLeave)

    // 지도 로드 직후 최초 조회
    scheduleUpdate()

    return () => {
      disposed = true
      controller?.abort()
      if (timer) clearTimeout(timer)

      map.off('moveend', scheduleUpdate)
      map.off('click', layerId, handleStationClick)
      map.off('mouseenter', layerId, onMouseEnter)
      map.off('mouseleave', layerId, onMouseLeave)

      try {
        if (map.getLayer(layerId)) map.removeLayer(layerId)
        if (map.getSource(sourceId)) map.removeSource(sourceId)
      } catch {
        // 지도 자체가 이미 제거된 경우
      }
    }
  }, [mapLoaded, filterType])

  // 🚲 지도 주변 실제 따릉이 대여소를 기존 거점 마커와 동일한 마커/팝업(AI 모델 + 실시간 잔여 수)으로 통합 표시
  useEffect(() => {
    if (!mapLoaded || !mapInstanceRef.current) return
    if (filterType !== 'bike' && filterType !== 'all') return

    const map = mapInstanceRef.current
    let controller: AbortController | null = null
    let timer: ReturnType<typeof setTimeout> | null = null
    let disposed = false

    const hubNos = new Set(BIKE_STATIONS.map(b => b.stationNo))
    const avgRainSensitivity =
      BIKE_STATIONS.reduce((sum, b) => sum + b.rainSensitivity, 0) / Math.max(1, BIKE_STATIONS.length)

    const loadNearbyBikeStations = async () => {
      controller?.abort()
      controller = new AbortController()

      // 따릉이 필터에서만, 충분히 확대했을 때만 조회 (전체 모드에서는 기존 거점만 표시)
      if (filterType !== 'bike' || map.getZoom() < 14.5) return

      const center = map.getCenter()
      const bounds = map.getBounds()

      try {
        const params = new URLSearchParams({
          lat: String(center.lat),
          lng: String(center.lng),
          radius: '800',
          limit: '150'
        })
        const reqUrl = `${API_BASE_URL || ''}/api/v1/transit/bike/stations/nearby?${params.toString()}`
        const response = await fetch(reqUrl, { signal: controller.signal })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)

        const data = await response.json()
        if (disposed) return
        logBikeNearbyCall({ lat: center.lat, lng: center.lng, radius: 800 }, data)

        const added: TransitStop[] = []
        for (const s of data.stations || []) {
          if (!s.id || !s.coords || !bounds.contains(s.coords)) continue
          const rawName = String(s.name || '')
          const stationNo = rawName.split('.')[0].trim()
          // 모델 기반 거점 마커(BIKE_STATIONS)와 중복되는 대여소는 기존 마커를 사용
          if (hubNos.has(stationNo)) continue
          added.push({
            id: `bike-live-${s.id}`,
            name: rawName.replace(/^\d+\.\s*/, '').trim() || '따릉이 대여소',
            type: 'bike',
            coords: s.coords,
            lineInfo: '서울자전거 따릉이',
            // 거점 데이터가 없는 대여소는 기본 이용 수요도를 사용하고, 잔여 수는 팝업에서 실시간 값으로 채움
            baseCrowd: 45,
            rainSensitivity: avgRainSensitivity,
            stationNo,
            rackCount: Number(s.rackTotal) || undefined
          })
        }

        // 정보 팝업이 열려 있는 동안 마커를 재생성하면 팝업이 닫히므로, 닫힌 뒤 다음 이동 시 반영
        if (activePopupRef.current) return

        setLiveBikeStops(prev => {
          const known = new Set(prev.map(p => p.id))
          const fresh = added.filter(a => !known.has(a.id))
          if (fresh.length === 0) return prev
          // 마커 폭증 방지: 누적 상한 유지 (오래된 항목부터 제거)
          return [...prev, ...fresh].slice(-600)
        })
        console.log(`[서울 따릉이] 주변 대여소 ${added.length}개 통합 (${data.source})`)
      } catch (error) {
        if (controller?.signal.aborted || disposed) return
        console.error('주변 따릉이 대여소 조회 실패:', error)
      }
    }

    const scheduleUpdate = () => {
      if (timer) clearTimeout(timer)
      controller?.abort()
      timer = setTimeout(() => {
        loadNearbyBikeStations()
      }, 400)
    }

    map.on('moveend', scheduleUpdate)
    scheduleUpdate()

    return () => {
      disposed = true
      controller?.abort()
      if (timer) clearTimeout(timer)
      map.off('moveend', scheduleUpdate)
    }
  }, [mapLoaded, filterType])

  // 🚌 선택한 버스 노선 경유 정류장 조회 (지하철 activeRoute에는 영향 없음)
  useEffect(() => {
    if (!selectedBusRoute) {
      setBusRouteStations([])
      setBusRouteError('')
      setBusRouteLoading(false)
      return
    }

    const controller = new AbortController()
    setBusRouteStations([])
    setBusRouteError('')
    setBusRouteLoading(true)

    const loadRoute = async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/api/v1/transit/bus/routes/${encodeURIComponent(selectedBusRoute.id)}/stations`,
          { signal: controller.signal }
        )
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const data = await response.json()
        if (data.status !== 'success' || !Array.isArray(data.stations)) {
          throw new Error('노선 조회 응답 형식 오류')
        }
        const stations: BusRouteStation[] = data.stations
          .filter((station: BusRouteStation) =>
            station && Array.isArray(station.coords) &&
            station.coords.length === 2 &&
            station.coords.every((value: number) => Number.isFinite(value))
          )
          .sort((a: BusRouteStation, b: BusRouteStation) => Number(a.sequence) - Number(b.sequence))
        if (!controller.signal.aborted) {
          setBusRouteStations(stations)
          if (stations.length < 2) setBusRouteError('표시할 경유 정류장이 부족합니다.')
        }
      } catch (error) {
        if (controller.signal.aborted) return
        console.error('버스 노선 조회 실패:', error)
        setBusRouteError('버스 노선을 불러오지 못했습니다.')
      } finally {
        if (!controller.signal.aborted) setBusRouteLoading(false)
      }
    }

    loadRoute()
    return () => controller.abort()
  }, [selectedBusRoute])

  // 🚌 노선 좌표를 별도 GeoJSON 레이어로 표시하고 경유 정류장 클릭 지원
  useEffect(() => {
    if (!mapLoaded || !mapInstanceRef.current || busRouteStations.length < 2) return
    const map = mapInstanceRef.current
    const lineSourceId = 'selected-bus-route-line-source'
    const pointSourceId = 'selected-bus-route-stations-source'
    const lineLayerId = 'selected-bus-route-line'
    const pointLayerId = 'selected-bus-route-stations'
    const coordinates = busRouteStations.map(station => station.coords)

    map.addSource(lineSourceId, {
      type: 'geojson',
      data: {
        type: 'Feature',
        properties: {},
        geometry: { type: 'LineString', coordinates }
      }
    })
    map.addLayer({
      id: lineLayerId,
      type: 'line',
      source: lineSourceId,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#F59E0B',
        'line-width': 5,
        'line-opacity': 0.9
      }
    })

    map.addSource(pointSourceId, {
      type: 'geojson',
      data: {
        type: 'FeatureCollection',
        features: busRouteStations.map(station => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: station.coords },
          properties: {
            sequence: station.sequence,
            name: station.name,
            stId: station.stId,
            arsId: station.arsId
          }
        }))
      }
    })
    map.addLayer({
      id: pointLayerId,
      type: 'circle',
      source: pointSourceId,
      paint: {
        'circle-radius': 5,
        'circle-color': '#FBBF24',
        'circle-stroke-color': '#111D35',
        'circle-stroke-width': 1.5
      }
    })

    const onBusRouteStopClick = (event: any) => {
      const feature = event.features?.[0]
      if (!feature || feature.geometry?.type !== 'Point') return
      const props = feature.properties || {}
      const content = document.createElement('div')
      Object.assign(content.style, {
        padding: '10px 12px',
        background: '#111D35',
        borderRadius: '8px',
        color: '#F0F6FF',
        fontSize: '12px'
      })
      const heading = document.createElement('strong')
      heading.textContent = `${props.sequence}번째 · ${props.name || '경유 정류장'}`
      const number = document.createElement('div')
      number.textContent = `정류장 번호: ${props.arsId || '-'}`
      Object.assign(number.style, { marginTop: '6px', color: '#94A3B8' })
      content.append(heading, number)
      new maplibregl.Popup({ offset: 10 })
        .setLngLat(feature.geometry.coordinates)
        .setDOMContent(content)
        .addTo(map)
    }
    const onEnter = () => { map.getCanvas().style.cursor = 'pointer' }
    const onLeave = () => { map.getCanvas().style.cursor = '' }
    map.on('click', pointLayerId, onBusRouteStopClick)
    map.on('mouseenter', pointLayerId, onEnter)
    map.on('mouseleave', pointLayerId, onLeave)

    const bounds = new maplibregl.LngLatBounds()
    coordinates.forEach(coord => bounds.extend(coord))
    map.fitBounds(bounds, {
      padding: { top: 95, right: 65, bottom: 85, left: 345 },
      maxZoom: 13,
      duration: 900,
      essential: true
    })

    return () => {
      map.off('click', pointLayerId, onBusRouteStopClick)
      map.off('mouseenter', pointLayerId, onEnter)
      map.off('mouseleave', pointLayerId, onLeave)
      try {
        if (map.getLayer(pointLayerId)) map.removeLayer(pointLayerId)
        if (map.getLayer(lineLayerId)) map.removeLayer(lineLayerId)
        if (map.getSource(pointSourceId)) map.removeSource(pointSourceId)
        if (map.getSource(lineSourceId)) map.removeSource(lineSourceId)
      } catch {
        // 지도 컴포넌트가 제거된 경우
      }
    }
  }, [mapLoaded, busRouteStations])


  // 🚌 선택한 정류장에 가장 먼저 도착할 두 차량만 조회 (30초 간격)
  useEffect(() => {
    setApproachingBusVehicles([])
    setApproachingBusError('')
    setApproachingBusMessage('')
    if (!selectedBusRoute) {
      setApproachingBusLoading(false)
      return
    }
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | null = null
    let disposed = false
    const routeId = selectedBusRoute.id
    const stationId = selectedBusRoute.stationId

    const refresh = async () => {
      if (disposed) return
      setApproachingBusLoading(true)
      try {
        const url = `${API_BASE_URL}/api/v1/transit/bus/routes/${encodeURIComponent(routeId)}/approaching?stId=${encodeURIComponent(stationId)}`
        const response = await fetch(url, { signal: controller.signal })
        if (!response.ok) throw new Error(`HTTP ${response.status}`)
        const data = await response.json()
        if (data.status !== 'success' || !Array.isArray(data.vehicles)) {
          throw new Error('접근 차량 응답 형식 오류')
        }
        if (disposed) return
        const vehicles: ApproachingBusVehicle[] = data.vehicles.filter((vehicle: ApproachingBusVehicle) =>
          vehicle && (vehicle.arrival_order === 1 || vehicle.arrival_order === 2) &&
          Array.isArray(vehicle.coords) && vehicle.coords.length === 2 &&
          vehicle.coords.every((value: number) => Number.isFinite(value))
        ).slice(0, 2)
        setApproachingBusVehicles(vehicles)
        setApproachingBusMessage(data.message || '')
        setApproachingBusError('')
      } catch (error) {
        if (disposed || controller.signal.aborted) return
        console.error('선택 노선 첫차·다음 차 위치 조회 실패:', error)
        setApproachingBusVehicles([]) // 실패 시 과거 위치를 실시간처럼 표시하지 않음
        setApproachingBusError('실시간 차량 위치를 불러오지 못했습니다.')
      } finally {
        if (!disposed) {
          setApproachingBusLoading(false)
          timer = setTimeout(refresh, 30000)
        }
      }
    }

    refresh()
    return () => {
      disposed = true
      controller.abort()
      if (timer) clearTimeout(timer)
    }
  }, [selectedBusRoute?.id, selectedBusRoute?.stationId])

  // 🚌 첫차·다음 차 두 대만 표시하며 화살표는 노선 정류장 진행 방향을 따른다.
  useEffect(() => {
    if (!mapLoaded || !mapInstanceRef.current || !selectedBusRoute) return
    const map = mapInstanceRef.current
    const markers: any[] = []
    const orderedStations = [...busRouteStations].sort((a, b) => a.sequence - b.sequence)

    for (const vehicle of approachingBusVehicles) {
      const first = vehicle.arrival_order === 1
      const color = first ? '#10B981' : '#38BDF8'
      const sectionOrder = Number(vehicle.section_order)
      const hereIndex = orderedStations.findIndex(station => Number(station.sequence) === sectionOrder)
      let rotation = 0
      if (hereIndex >= 0 && orderedStations.length > 1) {
        const here = orderedStations[hereIndex].coords
        const next = orderedStations[Math.min(hereIndex + 1, orderedStations.length - 1)].coords
        const previous = orderedStations[Math.max(0, hereIndex - 1)].coords
        const from = hereIndex < orderedStations.length - 1 ? here : previous
        const to = hereIndex < orderedStations.length - 1 ? next : here
        // MapLibre의 프로젝트 좌표로 방향각 계산 (화면상 화살표 방향)
        const fromPoint = map.project(from)
        const toPoint = map.project(to)
        rotation = Math.atan2(toPoint.x - fromPoint.x, fromPoint.y - toPoint.y) * 180 / Math.PI
      }

      const markerElement = document.createElement('div')
      Object.assign(markerElement.style, {
        background: '#111D35', border: `2px solid ${color}`, borderRadius: '12px',
        padding: '5px 8px', color: '#FFFFFF', display: 'flex', alignItems: 'center',
        gap: '5px', fontSize: '12px', fontWeight: '800', cursor: 'pointer',
        whiteSpace: 'nowrap', boxShadow: `0 2px 15px ${color}99`
      })
      const arrow = document.createElement('span')
      arrow.textContent = '▲'
      arrow.style.color = color
      arrow.style.display = 'inline-block'
      arrow.style.transform = `rotate(${rotation}deg)`
      const label = document.createElement('span')
      label.textContent = first ? '🚌 첫차' : '🚌 다음 차'
      markerElement.append(arrow, label)

      const popupContent = document.createElement('div')
      popupContent.style.cssText = 'padding:10px;background:#111D35;color:#F0F6FF;border-radius:8px;font-size:12px;'
      const heading = document.createElement('strong')
      heading.textContent = `${selectedBusRoute.name}번 · ${first ? '첫 번째' : '두 번째'} 도착 차량`
      const details = document.createElement('div')
      details.style.marginTop = '6px'
      const rawTime = String(vehicle.data_time || '')
      const timeLabel = /^\d{14}$/.test(rawTime) ? `${rawTime.slice(8, 10)}:${rawTime.slice(10, 12)}:${rawTime.slice(12, 14)}` : '정보 없음'
      details.textContent = `${vehicle.plate_no || '차량번호 미제공'} · ${vehicle.at_stop ? '정차 중' : '운행 중'} · GPS ${timeLabel}`
      const arrival = document.createElement('div')
      arrival.textContent = vehicle.arrival_message || '도착정보 없음'
      arrival.style.marginTop = '5px'
      popupContent.append(heading, details, arrival)

      const marker = new maplibregl.Marker({ element: markerElement })
        .setLngLat(vehicle.coords)
        .setPopup(new maplibregl.Popup({ offset: 18 }).setDOMContent(popupContent))
        .addTo(map)
      markers.push(marker)
    }
    // 지도 이동 시 마커를 유지하되, 정류장 표시처럼 클릭할 수 있게 함.
    return () => { markers.forEach(marker => marker.remove()) }
  }, [mapLoaded, selectedBusRoute?.id, approachingBusVehicles, busRouteStations])

  // 1-3. 필터 모드에 따른 지하철 노선망 배경 레이어 가시성 제어 (버스/따릉이 모드 시 은은하게 톤다운)
  useEffect(() => {
    if (!mapLoaded || !mapInstanceRef.current) return
    const map = mapInstanceRef.current
    if (map && map.getLayer && map.getLayer('subway-network-line')) {
      const isSubwayFocused = filterType === 'all' || filterType === 'subway'
      map.setPaintProperty('subway-network-line', 'line-opacity', isSubwayFocused ? 0.85 : 0.15)
      if (map.getLayer('subway-network-casing')) {
        map.setPaintProperty('subway-network-casing', 'line-opacity', isSubwayFocused ? 0.8 : 0.1)
      }
    }
  }, [filterType, mapLoaded])

  // 2. 필터링 및 날씨에 따른 마커 동적 갱신
  useEffect(() => {
    if (!mapLoaded || !mapInstanceRef.current) return

    // 이전 마커 제거
    markerItemsRef.current.forEach(item => item.marker.remove())
    markerItemsRef.current = []

    const allStops = liveBikeStops.length > 0 ? [...TRANSIT_STOPS, ...liveBikeStops] : TRANSIT_STOPS
    const filtered = filterType === 'all'
      ? allStops
      : allStops.filter(s => s.type === filterType)

    // 우선순위 정렬 (환승역, 주요 거점 역이 우선적으로 지도에 표시됨)
    const sortedStops = [...filtered].sort((a, b) => calculateStationPriority(b) - calculateStationPriority(a))

    sortedStops.forEach(stop => {
      const crowd = calculateCrowd(stop)
      const { label, color } = getCrowdLevel(crowd)

      // 커스텀 마커 엘리먼트 생성
      const el = document.createElement('div')
      el.className = 'custom-marker'
      el.style.display = 'flex'
      el.style.flexDirection = 'column'
      el.style.alignItems = 'center'
      el.style.cursor = 'pointer'

      const typeIcon = stop.type === 'subway' ? '🚇' : stop.type === 'bus' ? '🚌' : '🚲'

      el.innerHTML = `
        <!-- 1. 알약 마커 뷰 (이름 + 아이콘 + 혼잡도% 표시) -->
        <div class="marker-pill-view" style="display: flex; flex-direction: column; align-items: center;">
          <div class="marker-pill" style="
            background: #111D35;
            border: 2px solid ${color};
            border-radius: 9999px;
            padding: 3px 8px;
            box-shadow: 0 4px 14px rgba(0,0,0,0.5);
            display: flex;
            align-items: center;
            gap: 4px;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
          ">
            <span style="font-size: 13px;">${typeIcon}</span>
            <span style="font-size: 11px; font-weight: 700; color: #FFFFFF; white-space: nowrap;">${stop.name}</span>
            <span class="marker-crowd-badge" style="
              background: ${color};
              color: #FFFFFF;
              font-size: 9px;
              font-weight: 800;
              padding: 1px 5px;
              border-radius: 6px;
              margin-left: 2px;
            ">${crowd}%</span>
          </div>
          <div class="marker-pill-arrow" style="
            width: 0; height: 0;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 6px solid ${color};
          "></div>
        </div>

        <!-- 2. 점 마커 뷰 (이름 겹침 및 중거리 줌아웃 시 대체 표출되는 미니 원형 점) -->
        <div class="marker-dot-view" style="
          display: none;
          align-items: center;
          justify-content: center;
          padding: 3px;
        " title="${typeIcon} ${stop.name} (${label} ${crowd}%)">
          <div class="marker-dot-circle" style="
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: ${color};
            border: 2px solid #FFFFFF;
            box-shadow: 0 2px 8px rgba(0,0,0,0.7), 0 0 10px ${color}bb;
            transition: transform 0.18s ease, box-shadow 0.18s ease;
          "></div>
        </div>
      `

      // 호버 인터랙션 (알약 또는 점 마커 상태에 따라 부드러운 하이라이트)
      const pill = el.querySelector('.marker-pill') as HTMLElement | null
      const dotView = el.querySelector('.marker-dot-view') as HTMLElement | null
      const dotCircle = el.querySelector('.marker-dot-circle') as HTMLElement | null

      el.addEventListener('mouseenter', () => {
        if (dotView && dotView.style.display !== 'none') {
          if (dotCircle) {
            dotCircle.style.transform = 'scale(1.6)'
            dotCircle.style.boxShadow = `0 0 16px ${color}, 0 2px 8px rgba(0,0,0,0.8)`
          }
          el.style.zIndex = '5000'
        } else if (pill) {
          pill.style.transform = 'scale(1.1) translateY(-2px)'
          pill.style.boxShadow = `0 6px 20px ${color}88`
          el.style.zIndex = '5000'
        }
      })

      el.addEventListener('mouseleave', () => {
        if (dotCircle) {
          dotCircle.style.transform = 'scale(1)'
          dotCircle.style.boxShadow = `0 2px 8px rgba(0,0,0,0.7), 0 0 10px ${color}bb`
        }
        if (pill) {
          pill.style.transform = 'scale(1) translateY(0)'
          pill.style.boxShadow = '0 4px 14px rgba(0,0,0,0.5)'
        }
        el.style.zIndex = '1'
      })

      // 팝업 HTML 생성 헬퍼 (실시간 기상 관측, AI 추론 모델, 열차/버스 도착 정보 연동)
      const buildPopupContent = (
        arrivalsOrOptions?: any[] | {
          arrivalsList?: any[]
          isLoadingArrivals?: boolean
          weather?: any
          aiPrediction?: any
          isLoadingAll?: boolean
          source?: string
        },
        isLoadingArrivalsArg = false
      ) => {
        let arrivalsList: any[] = []
        let isLoadingArrivals = false
        let weatherData: any = null
        let aiData: any = null
        let isLoadingAll = false
        let apiSource: string = ''

        if (Array.isArray(arrivalsOrOptions)) {
          arrivalsList = arrivalsOrOptions
          isLoadingArrivals = isLoadingArrivalsArg
        } else if (arrivalsOrOptions && typeof arrivalsOrOptions === 'object') {
          arrivalsList = arrivalsOrOptions.arrivalsList || []
          isLoadingArrivals = !!arrivalsOrOptions.isLoadingArrivals
          weatherData = arrivalsOrOptions.weather || null
          aiData = arrivalsOrOptions.aiPrediction || null
          isLoadingAll = !!arrivalsOrOptions.isLoadingAll
          apiSource = String((arrivalsOrOptions as any).source || '')
        }

        const resolvedDistrict = resolveDistrict(stop.name, stop.coords)
        const rec = aiData?.recommendations?.find((r: any) => r.id === stop.type) || aiData?.recommendations?.[0]
        const displayCrowd = rec ? rec.crowd : crowd
        const displayLabel = rec ? rec.crowdLabel : label
        const displayColor = rec ? rec.crowdColor : color

        let weatherSection = ''
        if (isLoadingAll) {
          weatherSection = `
            <div style="background: rgba(14, 165, 233, 0.08); border: 1px solid rgba(56, 189, 248, 0.25); border-radius: 8px; padding: 9px; margin-bottom: 7px; text-align: center;">
              <div style="font-size: 11px; color: #38BDF8; font-weight: 700; margin-bottom: 2px;">
                ⏳ 기상청 실시간 관측 및 AI 모델 추론 중...
              </div>
              <div style="font-size: 9px; color: #94A3B8;">격자 매핑 및 32차원 ONNX 텐서 연산 진행</div>
            </div>
          `
        } else if (weatherData) {
          const wTemp = typeof weatherData.temp === 'number' ? weatherData.temp.toFixed(1) : (weatherData.weather?.temperature ?? 14.0)
          const wRain = typeof weatherData.rain === 'number' ? weatherData.rain : (weatherData.weather?.precipitation_mm ?? 0.0)
          const wHum = typeof weatherData.humidity === 'number' ? weatherData.humidity : (weatherData.weather?.humidity ?? 60.0)
          const wWind = typeof weatherData.wind === 'number' ? weatherData.wind : (weatherData.weather?.wind_speed ?? 2.0)
          const wNx = weatherData.nx ?? weatherData.grid?.nx ?? 60
          const wNy = weatherData.ny ?? weatherData.grid?.ny ?? 127
          const wDistrict = weatherData.district || resolvedDistrict

          weatherSection = `
            <div style="background: rgba(14, 165, 233, 0.09); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 8px; padding: 7px 9px; margin-bottom: 7px;">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
                <span style="font-size: 10px; font-weight: 800; color: #38BDF8; display: flex; align-items: center; gap: 4px;">
                  <span>🌦️</span> ${wDistrict} 국지 기상 실황
                </span>
                <span style="font-size: 9px; color: #94A3B8; font-family: monospace;">
                  격자 (${wNx}, ${wNy})
                </span>
              </div>
              <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; text-align: center; background: rgba(0,0,0,0.35); border-radius: 6px; padding: 4px 2px; margin-bottom: 5px;">
                <div>
                  <div style="font-size: 8px; color: #94A3B8;">기온</div>
                  <div style="font-size: 11px; font-weight: 800; color: #F8FAFC; font-family: monospace;">${wTemp}°C</div>
                </div>
                <div>
                  <div style="font-size: 8px; color: #94A3B8;">강수</div>
                  <div style="font-size: 11px; font-weight: 800; color: ${wRain > 0 ? '#60A5FA' : '#34D399'}; font-family: monospace;">${wRain}mm</div>
                </div>
                <div>
                  <div style="font-size: 8px; color: #94A3B8;">습도</div>
                  <div style="font-size: 11px; font-weight: 800; color: #F8FAFC; font-family: monospace;">${wHum}%</div>
                </div>
                <div>
                  <div style="font-size: 8px; color: #94A3B8;">풍속</div>
                  <div style="font-size: 11px; font-weight: 800; color: #F8FAFC; font-family: monospace;">${wWind}m/s</div>
                </div>
              </div>
              <div style="font-size: 9px; color: #BAE6FD; display: flex; align-items: center; justify-content: space-between;">
                <span>${wRain > 0 ? `🌧️ ${weatherData.pty_desc || '비'} (강수 관측)` : '☀️ 맑음 (평시 패턴)'}</span>
                <span style="color: #64748B;">기상청 초단기실황</span>
              </div>
            </div>
          `
        } else {
          weatherSection = `
            <div style="font-size: 11px; color: #E2E8F0; background: rgba(255, 255, 255, 0.07); padding: 7px 9px; border-radius: 6px; border-left: 3px solid ${color}; line-height: 1.45; margin-bottom: 7px;">
              ${rainMm > 0 
                ? `🌧 강수(${rainMm.toFixed(1)}mm) 영향으로 ${stop.type === 'bike' ? '따릉이 이용 위험 및 급감' : '지하철·버스 환승 승객 증가'}` 
                : '☀️ 맑은 날씨로 평시 이동 패턴 유지'}
            </div>
          `
        }

        let aiSection = ''
        if (aiData && rec) {
          aiSection = `
            <div style="background: rgba(124, 58, 237, 0.1); border: 1px solid rgba(168, 85, 247, 0.35); border-radius: 8px; padding: 7px 9px; margin-bottom: 7px;">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px;">
                <span style="font-size: 10px; font-weight: 800; color: #C084FC; display: flex; align-items: center; gap: 4px;">
                  <span>🤖</span> AI 수요 추론 (${rec.name})
                </span>
                <span style="font-size: 9px; font-weight: 700; color: #C084FC; background: rgba(168,85,247,0.22); padding: 1px 5px; border-radius: 4px;">
                  ⚡ ONNX ${aiData.latency_ms ?? 1.2}ms
                </span>
              </div>
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 3px; font-size: 10px;">
                <span style="color: #E2E8F0;">예측 혼잡도: <strong style="color: ${displayColor};">${displayCrowd}%</strong> (${displayLabel})</span>
                <span style="color: #94A3B8; font-family: monospace;">시간당 ${rec.predicted_volume ? rec.predicted_volume.toLocaleString() : '1,200'}명</span>
              </div>
              <div style="height: 4px; background: rgba(255,255,255,0.1); border-radius: 2px; overflow: hidden; margin-bottom: 5px;">
                <div style="width: ${displayCrowd}%; height: 100%; background: ${displayColor}; border-radius: 2px;"></div>
              </div>
              <div style="font-size: 9px; color: #DDD6FE; line-height: 1.35; background: rgba(0,0,0,0.25); padding: 4px 6px; border-radius: 4px; border-left: 2px solid #A855F7;">
                ${rec.reasons?.[0] || '기상 관측치 기반 최적 통행 분석'}
              </div>
            </div>
          `
        }

        let arrivalSection = ''

        if (stop.type === 'subway') {
          if (isLoadingArrivals) {
            arrivalSection = `
              <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.1);">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
                  <span style="font-size: 11px; font-weight: 800; color: #38BDF8; display: flex; align-items: center; gap: 4px;">
                    <span>🚇</span> 실시간 열차 도착
                  </span>
                  <span style="font-size: 9px; color: #94A3B8;">수신 중...</span>
                </div>
                <div style="font-size: 10px; color: #94A3B8; background: rgba(0,0,0,0.3); padding: 7px 9px; border-radius: 6px; text-align: center;">
                  ⏳ 실시간 열차 운행 정보 조회 중...
                </div>
              </div>
            `
          } else if (arrivalsList && arrivalsList.length > 0) {
            arrivalSection = `
              <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.1);">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
                  <span style="font-size: 11px; font-weight: 800; color: #38BDF8; display: flex; align-items: center; gap: 4px;">
                    <span>🚇</span> 실시간 열차 도착
                  </span>
                  <span style="font-size: 9px; font-weight: 700; color: #34D399; background: rgba(52,211,153,0.15); padding: 1px 5px; border-radius: 4px;">
                    실시간 API
                  </span>
                </div>
                <div style="display: flex; flex-direction: column; gap: 4px; max-height: 150px; overflow-y: auto;">
                  ${arrivalsList.slice(0, 8).map((arr: any) => `
                    <div style="display: flex; align-items: center; justify-content: space-between; background: rgba(0,0,0,0.35); padding: 5px 8px; border-radius: 6px; font-size: 10px; border-left: 2px solid #38BDF8;">
                      <div style="min-width: 0; flex: 1; margin-right: 6px;">
                        <div style="display: flex; align-items: center; gap: 4px;">
                          <span style="background: rgba(56,189,248,0.22); color: #38BDF8; font-weight: 800; font-size: 9px; padding: 1px 4px; border-radius: 3px; white-space: nowrap;">
                            ${arr.line || '전철'}
                          </span>
                          <span style="color: #F8FAFC; font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                            ${arr.destination ? arr.destination.split(' - ')[0] : '열차'}
                          </span>
                        </div>
                        ${arr.updn_line ? `<div style="font-size: 9px; color: #94A3B8; margin-top: 1px;">${arr.updn_line} ${arr.destination && arr.destination.includes(' - ') ? `(${arr.destination.split(' - ')[1]})` : ''}</div>` : ''}
                      </div>
                      <div style="text-align: right; flex-shrink: 0;">
                        <div style="color: #FCD34D; font-weight: 800; font-family: monospace; font-size: 10px;">
                          ${arr.message}
                        </div>
                        ${arr.remaining_minutes > 0 ? `<div style="font-size: 9px; color: rgba(255,255,255,0.4); margin-top: 1px;">약 ${arr.remaining_minutes}분 후</div>` : ''}
                      </div>
                    </div>
                  `).join('')}
                </div>
              </div>
            `
          } else {
            arrivalSection = `
              <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.1);">
                <div style="font-size: 10px; color: #94A3B8; text-align: center; padding: 4px 0;">배차 간격 2~5분 정상 운행중</div>
              </div>
            `
          }
        } else if (stop.type === 'bus') {
          if (isLoadingArrivals) {
            arrivalSection = `
              <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.1);">
                <div style="font-size: 10px; color: #94A3B8; background: rgba(0,0,0,0.3); padding: 7px 9px; border-radius: 6px; text-align: center;">
                  ⏳ 실시간 버스 도착 정보 수신 중...
                </div>
              </div>
            `
          } else if (arrivalsList && arrivalsList.length > 0) {
            arrivalSection = `
              <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.1);">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
                  <span style="font-size: 11px; font-weight: 800; color: #34D399; display: flex; align-items: center; gap: 4px;">
                    <span>🚌</span> 실시간 버스 도착
                  </span>
                  <span style="font-size: 9px; padding: 1px 5px; border-radius: 4px; font-weight: 700; ${
                    apiSource.includes('FALLBACK') || apiSource.includes('CIRCUIT')
                      ? 'color: #F59E0B; background: rgba(245,158,11,0.15); border: 1px solid rgba(245,158,11,0.3);'
                      : 'color: #34D399; background: rgba(52,211,153,0.15);'
                  }">
                    ${apiSource.includes('FALLBACK') || apiSource.includes('CIRCUIT') ? '⚠️ 시간표 추정' : '실시간 API'}
                  </span>
                </div>
                <div style="display: flex; flex-direction: column; gap: 4px;">
                  ${arrivalsList.slice(0, 3).map((b: any) => `
                    <div style="display: flex; align-items: center; justify-content: space-between; background: rgba(0,0,0,0.35); padding: 5px 8px; border-radius: 6px; font-size: 10px; border-left: 2px solid #34D399;">
                      <span style="color: #34D399; font-weight: 800;">${b.route_name || b.rtNm || '간선'}</span>
                      <span style="color: #FCD34D; font-weight: 700; font-family: monospace;">${b.arrival_msg1 || b.arrmsg1 || '운행중'}</span>
                    </div>
                  `).join('')}
                </div>
              </div>
            `
          }
        } else if (stop.type === 'bike') {
          const liveBike = (arrivalsList || []).find((x: any) => x && x.bikeLive)
          const rackTotal = liveBike ? liveBike.rackTotal : (stop.rackCount || 20)
          // 실시간 값이 있으면 사용, 없으면 혼잡도·강수량 기반 추정
          const crowdRatio = (displayCrowd || 60) / 100
          const availableBikes = liveBike
            ? liveBike.availableBikes
            : (rainMm > 0 ? Math.max(0, Math.round(rackTotal * 0.85)) : Math.max(1, Math.round(rackTotal * (1 - crowdRatio * 0.65))))
          arrivalSection = `
            <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.1);">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
                <span style="font-size: 11px; font-weight: 800; color: #34D399; display: flex; align-items: center; gap: 4px;">
                  <span>🚲</span> 따릉이 실시간 거치 현황
                </span>
                <span style="font-size: 9px; color: #34D399; background: rgba(52,211,153,0.15); padding: 1px 5px; border-radius: 4px; font-weight: 700;">
                  ${liveBike ? '실시간 API' : (stop.stationNo ? `대여소 #${stop.stationNo} · 추정` : '거점 대여소 · 추정')}
                </span>
              </div>
              <div style="display: flex; align-items: center; justify-content: space-between; background: rgba(0,0,0,0.35); padding: 6px 10px; border-radius: 6px; font-size: 11px; border-left: 2px solid #34D399;">
                <span style="color: #E2E8F0;">대여 가능 자전거</span>
                <span style="color: #34D399; font-weight: 800; font-family: monospace;">${liveBike ? '' : '약 '}${availableBikes}대 / 총 ${rackTotal}대</span>
              </div>
              ${rainMm > 0 ? `
                <div style="margin-top: 4px; font-size: 9px; color: #FCA5A5; text-align: center;">
                  🌧️ 우천 감속 및 안전모 착용 필수 (우천 시 대여 자제 권고)
                </div>
              ` : ''}
            </div>
          `
        }

        return `
          <div style="min-width: 250px; max-width: 310px; font-family: 'Outfit', 'Noto Sans KR', sans-serif; padding: 2px;">
            <!-- 닫기(X) 버튼과 겹치지 않도록 padding-right: 36px 적용 -->
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 7px; padding-right: 36px;">
              <div style="display: flex; align-items: center; gap: 5px;">
                <span style="font-size: 15px;">${typeIcon}</span>
                <strong style="font-size: 14px; color: #F0F6FF; font-weight: 800;">${stop.name}</strong>
                <span style="font-size: 9px; color: #94A3B8; background: rgba(255,255,255,0.08); padding: 1px 5px; border-radius: 4px;">${resolvedDistrict}</span>
              </div>
              <span style="font-size: 10px; font-weight: 800; color: #FFFFFF; background: ${displayColor}; padding: 2px 7px; border-radius: 6px; white-space: nowrap;">
                ${displayLabel} (${displayCrowd}%)
              </span>
            </div>
            <div style="font-size: 11px; color: #94A3B8; margin-bottom: 6px; font-family: monospace;">${stop.lineInfo}</div>
            ${weatherSection}
            ${aiSection}
            ${arrivalSection}
          </div>
        `
      }

      const popup = new maplibregl.Popup({ 
        offset: 25,
        closeButton: true,
        closeOnClick: false,
        maxWidth: '310px',
      }).setHTML(buildPopupContent())

      popup.on('open', () => {
        if (activePopupRef.current && activePopupRef.current !== popup) {
          activePopupRef.current.remove()
        }
        activePopupRef.current = popup
        if (mapInstanceRef.current) {
          popupOpenedZoomRef.current = mapInstanceRef.current.getZoom()
        }
      })

      popup.on('close', () => {
        if (activePopupRef.current === popup) {
          activePopupRef.current = null
          popupOpenedZoomRef.current = null
        }
        setActiveStop(null)
        try {
          localStorage.removeItem(STORAGE_SELECTED_STOP_KEY)
        } catch {}
        if (onSelectStop) onSelectStop(null)
      })

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat(stop.coords)
        .setPopup(popup)
        .addTo(mapInstanceRef.current)

      el.addEventListener('click', async () => {
        // 선택된 역 ID 로컬 스토리지에 저장 (새로고침 시 복원용)
        try {
          localStorage.setItem(STORAGE_SELECTED_STOP_KEY, stop.id)
        } catch {}

        // 다른 역 누르면 이전 열려 있던 역 정보 팝업 즉시 제거 (요청사항 반영)
        if (activePopupRef.current && activePopupRef.current !== popup) {
          activePopupRef.current.remove()
        }
        activePopupRef.current = popup
        if (mapInstanceRef.current) {
          popupOpenedZoomRef.current = mapInstanceRef.current.getZoom()
        }

        setActiveStop(stop)
        if (onSelectStop) onSelectStop(stop, { loading: true })

        // 1. 역 클릭 시 중심 이동 및 부드러운 줌인 (기본 15.5 배율로 확대, 비행 애니메이션 중 팝업 유지)
        // 단, 새로고침 시 원래 보던 위치 복원 중일 때는 사용자가 맞춰둔 줌/중심을 유지하기 위해 flyTo 생략
        if (mapInstanceRef.current && !isInitialRestoringRef.current) {
          const currentZ = mapInstanceRef.current.getZoom()
          const targetZoom = currentZ < 15.5 ? 15.5 : Math.min(17.5, currentZ + 0.5)
          isFlyingRef.current = true
          // 이동 후에도 기본 탑뷰(0°)를 유지 — 시야각이 3D 틸트로 되돌아가지 않도록 고정
          mapInstanceRef.current.flyTo({
            center: stop.coords,
            zoom: targetZoom,
            pitch: DEFAULT_MAP_PITCH,
            duration: 700,
            essential: true,
          })
          setTimeout(() => {
            isFlyingRef.current = false
            if (mapInstanceRef.current) {
              popupOpenedZoomRef.current = mapInstanceRef.current.getZoom()
            }
          }, 750)
        }

        const district = resolveDistrict(stop.name, stop.coords)
        const cleanName = stop.name.replace(/역$/, '').trim()

        // 2. 실시간 국지 기상 및 AI 모델 추론 로딩 UI 선반영
        popup.setHTML(buildPopupContent({ isLoadingAll: true }))

        try {
          // (1) 해당 역의 실시간 기상 API 조회 (위도/경도 기반 정밀 KMA 격자 nx, ny 계산)
          const weatherRes = await fetch(
            `${API_BASE_URL}/api/v1/weather/current?district=${encodeURIComponent(district)}&lat=${stop.coords[1]}&lng=${stop.coords[0]}&station=${encodeURIComponent(cleanName)}`
          )
          const weatherData = await weatherRes.json()

          // 기상청 API 호출 로깅
          logWeatherApiCall(
            { nx: weatherData.nx, ny: weatherData.ny },
            weatherData,
            weatherData
          )

          // (2) 실시간 관측 기상 데이터를 투입하여 AI 모델(ONNX 32차원 Feature Vector) 추론 호출
          const parsedHour = parseInt(selectedTime, 10)
          const currentHour = !isNaN(parsedHour) ? parsedHour : new Date().getHours()

          const aiPayload = {
            district,
            station: stop.name,
            stop_type: stop.type,
            base_crowd: stop.baseCrowd,
            hour: currentHour,
            weather: {
              temp: weatherData.temp,
              rain: weatherData.rain,
              humidity: weatherData.humidity,
              wind: weatherData.wind,
            }
          }

          const aiRes = await fetch(`${API_BASE_URL}/api/v1/predict/recommendation`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(aiPayload)
          })
          const aiData = await aiRes.json()

          // AI 모델 추론 결과 로깅
          logAIPredictionCall(aiPayload, aiData)

          // (3) 실시간 대중교통 도착 정보 조회
          let arrivals: any[] = []
          let apiCallSource = ''
          if (stop.type === 'subway') {
            try {
              const arrivalRes = await fetch(
                `${API_BASE_URL}/api/v1/transit/subway/arrival?station=${encodeURIComponent(cleanName)}`
              )
              const arrivalData = await arrivalRes.json()
              arrivals = (arrivalData.status === 'success' && arrivalData.arrivals && arrivalData.arrivals.length > 0)
                ? arrivalData.arrivals
                : [
                    { line: stop.lineInfo.split(' · ')[0] || '지하철', destination: `${stop.name} 경유 방면`, message: '배차 간격 2~5분 정상 운행', remaining_minutes: 2, updn_line: '상/하행' }
                  ]
              apiCallSource = String(arrivalData.source || '')
              logSubwayApiCall(cleanName, arrivals, arrivalData)
            } catch {
              apiCallSource = 'CLIENT_FALLBACK'
              arrivals = [
                { line: stop.lineInfo.split(' · ')[0] || '지하철', destination: `${stop.name} 경유 방면`, message: '정상 운행중', remaining_minutes: 2, updn_line: '상/하행' }
              ]
              logSubwayApiCall(cleanName, arrivals)
            }
          } else if (stop.type === 'bus') {
            let targetStId = stop.stId
            // stop.stId가 누락된 경우 좌표 기반 인근 정류소 API로 동적 해석
            if (!targetStId && stop.coordinates) {
              try {
                const nearRes = await fetch(`${API_BASE_URL}/api/v1/transit/bus/stations/nearby?lat=${stop.coordinates[1]}&lng=${stop.coordinates[0]}&radius=350`)
                if (nearRes.ok) {
                  const nearData = await nearRes.json()
                  if (nearData.stations && nearData.stations.length > 0) {
                    targetStId = nearData.stations[0].stId || nearData.stations[0].station_id
                  }
                }
              } catch {
                // ignore
              }
            }

            const defaultRoutes = stop.lineInfo ? stop.lineInfo.split(/[·,]/).map(s => s.trim().replace(/등$/, '')).filter(Boolean) : []
            const r1 = defaultRoutes[0] || `${stop.name} 경유 노선`
            
            if (targetStId) {
              try {
                const busRes = await fetch(`${API_BASE_URL}/api/v1/transit/bus/arrival?stId=${encodeURIComponent(targetStId)}`)
                const busData = await busRes.json()
                apiCallSource = String(busData.source || '')
                arrivals = (busData.status === 'success' && busData.arrivals && busData.arrivals.length > 0)
                  ? busData.arrivals
                  : [
                      { route_name: r1, arrival_msg1: '배차간격 유지 운행중' }
                    ]
                logBusApiCall(r1, targetStId, arrivals, busData)
              } catch {
                apiCallSource = 'CLIENT_FALLBACK'
                arrivals = [
                  { route_name: r1, arrival_msg1: '배차간격 유지 운행중' }
                ]
                logBusApiCall(r1, targetStId, arrivals)
              }
            } else {
              apiCallSource = 'NO_STID_FALLBACK'
              arrivals = [
                { route_name: r1, arrival_msg1: '배차간격 유지 운행중' }
              ]
            }
          } else if (stop.type === 'bike') {
            // 서울시 따릉이 실시간 대여정보(잔여 자전거 수)로 시뮬레이션 값을 대체
            let live: any = null
            let method: 'by-number' | 'nearest-200m' | 'estimated' = 'estimated'
            let proxyPath = ''
            let rawPayload: any = null
            try {
              if (stop.stationNo) {
                proxyPath = `/api/v1/transit/bike/stations/by-number/${encodeURIComponent(stop.stationNo)}`
                const r = await fetch(`${API_BASE_URL}${proxyPath}`)
                if (r.ok) {
                  rawPayload = await r.json()
                  live = rawPayload.station
                  method = 'by-number'
                  // 하드코딩된 대여소 번호가 실제와 다른 경우 대비: 좌표가 250m 넘게 어긋나면 번호 매칭을 폐기
                  if (live?.coords) {
                    const dLat = (live.coords[1] - stop.coords[1]) * 111320
                    const dLng = (live.coords[0] - stop.coords[0]) * 111320 * Math.cos(stop.coords[1] * Math.PI / 180)
                    if (Math.hypot(dLat, dLng) > 250) {
                      console.warn(`[따릉이] 대여소 번호 #${stop.stationNo}(${live.name})가 '${stop.name}'과 250m 이상 떨어져 있어 최근접 대여소로 대체합니다.`)
                      live = null
                      method = 'estimated'
                    }
                  }
                }
              }
              if (!live) {
                // 대여소 번호로 못 찾으면 좌표 기준 가장 가까운 실제 대여소(200m 이내)로 대체
                const params = new URLSearchParams({ lat: String(stop.coords[1]), lng: String(stop.coords[0]), radius: '200', limit: '1' })
                proxyPath = `/api/v1/transit/bike/stations/nearby?${params.toString()}`
                const r = await fetch(`${API_BASE_URL}${proxyPath}`)
                if (r.ok) {
                  rawPayload = await r.json()
                  live = (rawPayload.stations || [])[0] || null
                  if (live) method = 'nearest-200m'
                }
              }
              if (live) arrivals = [{ bikeLive: true, rackTotal: live.rackTotal, availableBikes: live.availableBikes, name: live.name }]
            } catch (e) {
              console.warn('따릉이 실시간 조회 실패, 추정값 사용:', e)
            }
            logBikeApiCall({ stationNo: stop.stationNo, stationName: stop.name, method, proxyPath }, live, rawPayload)
          }

          // 최종 통합 데이터로 팝업 갱신

          if (activePopupRef.current === popup) {
            popup.setHTML(buildPopupContent({
              weather: weatherData,
              aiPrediction: aiData,
              arrivalsList: arrivals,
              isLoadingArrivals: false,
              source: apiCallSource
            }))
          }

          // 클릭된 역 알약 마커 UI도 AI 추론 혼잡도 수치와 100% 동일하게 실시간 동기화
          const targetRec = aiData?.recommendations?.find((r: any) => r.id === stop.type) || aiData?.recommendations?.[0]
          if (targetRec) {
            const pillBadge = el.querySelector('.marker-crowd-badge') as HTMLElement | null
            const pillBox = el.querySelector('.marker-pill') as HTMLElement | null
            const pillArrow = el.querySelector('.marker-pill-arrow') as HTMLElement | null
            if (pillBadge) {
              pillBadge.textContent = `${targetRec.crowd}%`
              pillBadge.style.background = targetRec.crowdColor
            }
            if (pillBox) {
              pillBox.style.borderColor = targetRec.crowdColor
            }
            if (pillArrow) {
              pillArrow.style.borderTopColor = targetRec.crowdColor
            }
          }

          // 상위 App 컴포넌트에 실시간 기상/AI예측/도착정보 일괄 전달 (중복 API Fetch 방지)
          if (onSelectStop) {
            onSelectStop(stop, {
              loading: false,
              weather: weatherData,
              aiPrediction: aiData,
              arrivals,
            })
          }
        } catch (err) {
          console.error('역 정보 파이프라인 조회 실패:', err)
          if (activePopupRef.current === popup) {
            popup.setHTML(buildPopupContent({
              arrivalsList: [],
              isLoadingArrivals: false
            }))
          }
          if (onSelectStop) {
            onSelectStop(stop, {
              loading: false,
              weather: null,
              aiPrediction: null,
              arrivals: [],
            })
          }
        }
      })

      markerItemsRef.current.push({
        marker,
        stop,
        el,
        priority: calculateStationPriority(stop),
      })
    })

    // 새로고침 시 이전에 선택했던 역/정류소가 있었다면 마커 선택 및 팝업/상세정보 자동 복원
    try {
      const savedStopId = localStorage.getItem(STORAGE_SELECTED_STOP_KEY)
      if (savedStopId && !initialRestoreDoneRef.current) {
        initialRestoreDoneRef.current = true
        const targetItem = markerItemsRef.current.find(item => item.stop.id === savedStopId)
        if (targetItem) {
          isInitialRestoringRef.current = true
          setTimeout(() => {
            targetItem.el.click()
            setTimeout(() => {
              isInitialRestoringRef.current = false
            }, 800)
          }, 150)
        }
      }
    } catch {}

    // 초기 마커 겹침 필터링 실행
    updateCollisions()

    // 지도 조작(이동, 확대, 축소) 시 고속 겹침 재계산 (최신 클로저 Refs 호출)
    const onMapMove = () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
      animFrameRef.current = requestAnimationFrame(() => {
        updateCollisionsRef.current()
        if (mapInstanceRef.current) {
          const z = mapInstanceRef.current.getZoom()
          setZoomLevel(prev => (Math.abs(prev - z) >= 0.2 ? z : prev))
        }
      })
    }

    const map = mapInstanceRef.current
    map.on('move', onMapMove)
    map.on('zoom', onMapMove)
    map.on('resize', onMapMove)

    return () => {
      map.off('move', onMapMove)
      map.off('zoom', onMapMove)
      map.off('resize', onMapMove)
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    }
  }, [filterType, rainMm, mapLoaded, selectedTime, liveBikeStops])

  // focusedCoords, activeStop 또는 activeRoute 변경 시 즉시 마커 겹침 표시 갱신
  useEffect(() => {
    updateCollisions()
  }, [focusedCoords, activeStop, activeRoute])

  // activeRoute 변경 시 GeoJSON 경로선 렌더링, 출발/도착 마커 핀 표시, 카메라 영역 자동 맞춤
  useEffect(() => {
    if (!mapLoaded || !mapInstanceRef.current) return
    const map = mapInstanceRef.current

    // 기존 경로 마커 제거
    routeMarkersRef.current.forEach(m => m.remove())
    routeMarkersRef.current = []

    const source = map.getSource('active-route')
    const mmSource = map.getSource('multimodal-segments')

    const hadRoute = !!(prevActiveRouteRef.current && prevActiveRouteRef.current.path && prevActiveRouteRef.current.path.length >= 2)
    prevActiveRouteRef.current = activeRoute

    if (!activeRoute || activeRoute.path.length < 2) {
      if (source) {
        source.setData({
          type: 'Feature',
          properties: {},
          geometry: {
            type: 'LineString',
            coordinates: [],
          },
        })
      }
      if (mmSource) {
        mmSource.setData({
          type: 'FeatureCollection',
          features: [],
        })
      }
      // 경로 닫기 시 모든 마커의 display를 원상 복원하고 충돌 필터링 재계산
      markerItemsRef.current.forEach(item => {
        item.el.style.display = 'flex'
      })
      updateCollisions()

      // 이전에 경로가 활성화되어 있다가 닫혔을 때만, 경로 핏바운즈로 인해 줌이 너무 축소되어 있다면 (zoom < 12.8) 일반 시야각(13.0)으로 부드럽게 복귀
      if (hadRoute) {
        const currentZ = map.getZoom()
        if (currentZ < 12.8) {
          map.easeTo({
            zoom: 13.0,
            duration: 600,
          })
          map.once('idle', () => {
            updateCollisionsRef.current()
          })
        }
      }
      return
    }

    const coords = (activeRoute.geometry && activeRoute.geometry.length >= 2)
      ? activeRoute.geometry
      : activeRoute.path.map(p => p.coords)
    if (source) {
      source.setData({
        type: 'Feature',
        properties: {},
        geometry: {
          type: 'LineString',
          coordinates: coords,
        },
      })
    }
    if (mmSource) {
      const segFeatures = (activeRoute.segments || [])
        .filter(seg => Array.isArray(seg.coords) && seg.coords.length >= 2)
        .map(seg => ({
          type: 'Feature',
          properties: {
            mode: seg.mode,
            color: seg.color || '#38BDF8',
            label: seg.label,
          },
          geometry: {
            type: 'LineString',
            coordinates: seg.coords,
          },
        }))
      mmSource.setData({
        type: 'FeatureCollection',
        features: segFeatures,
      })
    }

    // 경로 전체를 한눈에 볼 수 있도록 카메라 바운드 자동 맞춤 (fitBounds)
    const bounds = new maplibregl.LngLatBounds()
    coords.forEach(c => bounds.extend(c))
    map.fitBounds(bounds, {
      padding: { top: 90, bottom: 90, left: 100, right: 100 },
      maxZoom: 15,
      duration: 1000,
    })

    const startCoord = coords[0]
    const endCoord = coords[coords.length - 1]

    const firstSegment = activeRoute.segments && activeRoute.segments.length > 0 ? activeRoute.segments[0] : null
    const lastSegment = activeRoute.segments && activeRoute.segments.length > 0 ? activeRoute.segments[activeRoute.segments.length - 1] : null

    // 첫 이동 모드가 지하철인지 확인 (도보나 따릉이로 이동을 시작할 때는 지하철 실시간 도착 정보를 출발 알약에 노출하지 않음)
    const isFirstModeSubway = !firstSegment || firstSegment.mode === 'subway'
    const depTrain = isFirstModeSubway ? activeRoute.departureTrain : null

    // 두 좌표가 인접한지 판별 (위경도 차이 0.001도, 약 90m 이내)
    const isNearbyCoord = (c1?: [number, number], c2?: [number, number], threshold = 0.001) => {
      if (!c1 || !c2) return false
      return Math.abs(c1[0] - c2[0]) < threshold && Math.abs(c1[1] - c2[1]) < threshold
    }

    // 도착지와 인접/일치하는 따릉이 반납 세그먼트 탐색:
    // (전체 경로의 마지막 세그먼트가 따릉이이고, 최종 목적지와 반납 위치가 일치/초근접할 때만 일체형 알약으로 병합)
    const isLastSegBike = lastSegment && lastSegment.mode === 'bike'
    const mergedBikeDrop = (isLastSegBike && Array.isArray(lastSegment.coords) && lastSegment.coords.length >= 2 &&
      (isNearbyCoord(lastSegment.coords[lastSegment.coords.length - 1], endCoord, 0.0015) || 
       lastSegment.to_name === activeRoute.to || 
       activeRoute.to.includes(lastSegment.to_name) || 
       lastSegment.to_name.includes(activeRoute.to))) ? lastSegment : null

    // 출발지와 인접/일치하는 따릉이 대여 세그먼트 탐색:
    // (도보 이동 없이 출발역 위치에서 곧바로 따릉이를 대여하는 경우에만 출발 알약에 병합)
    const isFirstSegBikeDirect = firstSegment && firstSegment.mode === 'bike'
    const mergedBikePickup = (isFirstSegBikeDirect && Array.isArray(firstSegment.coords) && firstSegment.coords.length >= 2 &&
      isNearbyCoord(firstSegment.coords[0], startCoord, 0.0003)) ? firstSegment : null

    // 출발지 마커 핀 (초록색 캡슐 + 이동 모드별 최적화된 안내 표시)
    const startStop = TRANSIT_STOPS.find(s => s.name === activeRoute.from)
    const startCrowd = startStop ? calculateCrowd(startStop) : 65
    const startEl = document.createElement('div')
    startEl.className = 'route-start-pin'
    startEl.style.display = 'flex'
    startEl.style.flexDirection = 'column'
    startEl.style.alignItems = 'center'
    startEl.style.cursor = 'pointer'
    startEl.innerHTML = `
      <div style="
        background: #10B981;
        color: #FFFFFF;
        font-weight: 800;
        font-size: 11px;
        padding: 5px 12px;
        border-radius: 9999px;
        box-shadow: 0 4px 18px rgba(16,185,129,0.65);
        border: 2px solid #FFFFFF;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 2px;
        white-space: nowrap;
      ">
        <div style="display: flex; align-items: center; gap: 5px;">
          <span>🟢 출발</span>
          <span>${activeRoute.from}</span>
          ${depTrain ? `<span style="background: rgba(0,0,0,0.25); font-size: 9px; padding: 1px 5px; border-radius: 4px;">${depTrain.line}</span>` : ''}
          <span style="background: rgba(0,0,0,0.2); font-size: 9px; padding: 1px 5px; border-radius: 4px;">${startCrowd}%</span>
        </div>
        ${depTrain ? `
          <div style="font-size: 10px; color: #D1FAE5; font-weight: 700; display: flex; align-items: center; gap: 4px;">
            <span>⏱️ ${depTrain.destinationOrNext} 방면</span>
            <span style="background: #065F46; color: #6EE7B7; padding: 1px 5px; border-radius: 4px; font-weight: 800;">${depTrain.remainingMinutes}분 후 도착</span>
          </div>
        ` : ''}
        ${!isFirstModeSubway && firstSegment?.mode === 'walk' ? `
          <div style="font-size: 10px; color: #ECFDF5; font-weight: 700; display: flex; align-items: center; gap: 4px; background: rgba(0,0,0,0.2); padding: 1px 7px; border-radius: 9999px; margin-top: 1px;">
            <span>🚶 도보 ${firstSegment.minutes || 2}분</span>
            <span>➔ ${firstSegment.to_name || '따릉이 대여소'}</span>
          </div>
        ` : ''}
        ${!isFirstModeSubway && firstSegment?.mode === 'bike' ? `
          <div style="font-size: 10px; color: #ECFDF5; font-weight: 700; display: flex; align-items: center; gap: 4px; background: rgba(0,0,0,0.2); padding: 1px 7px; border-radius: 9999px; margin-top: 1px;">
            <span>🚲 따릉이 라이딩 시작</span>
            <span>(${firstSegment.minutes || 10}분)</span>
          </div>
        ` : ''}
        ${!isFirstModeSubway && firstSegment?.mode === 'bus' ? `
          <div style="font-size: 10px; color: #ECFDF5; font-weight: 700; display: flex; align-items: center; gap: 4px; background: rgba(0,0,0,0.2); padding: 1px 7px; border-radius: 9999px; margin-top: 1px;">
            <span>🚌 ${firstSegment.label || '버스'} 탑승</span>
            <span>(${firstSegment.minutes || 10}분)</span>
          </div>
        ` : ''}
      </div>
      <div style="width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #10B981;"></div>
    `
    if (startStop) {
      startEl.addEventListener('click', () => {
        if (activePopupRef.current) {
          activePopupRef.current.remove()
          activePopupRef.current = null
          popupOpenedZoomRef.current = null
        }
        setActiveStop(startStop)
        if (onSelectStop) onSelectStop(startStop)
        if (mapInstanceRef.current) {
          const currentZ = mapInstanceRef.current.getZoom()
          const targetZoom = currentZ < 15.5 ? 15.5 : Math.min(17.5, currentZ + 0.5)
          mapInstanceRef.current.flyTo({
            center: startStop.coords,
            zoom: targetZoom,
            pitch: DEFAULT_MAP_PITCH,
            duration: 700,
            essential: true,
          })
        }
      })
    }
    const startMarker = new maplibregl.Marker({ element: startEl })
      .setLngLat(startCoord)
      .addTo(map)
    routeMarkersRef.current.push(startMarker)

    // 따릉이(Bike) 세그먼트 대여소/반납소 마커 핀 (출발/환승/도착과 겹치지 않는 독립 구간만 생성)
    if (activeRoute.segments && activeRoute.segments.length > 0) {
      activeRoute.segments.forEach(seg => {
        if (seg.mode === 'bike' && Array.isArray(seg.coords) && seg.coords.length >= 2) {
          // 대여소 핀 (출발 대여소): 출발역 알약과 완전히 동일한 위치로 병합된 경우가 아니면 100% 무조건 독립 핀 표출!
          if (mergedBikePickup !== seg) {
            const pickupCoord = seg.coords[0]
            const pickupEl = document.createElement('div')
            pickupEl.className = 'route-bike-pickup-pin'
            pickupEl.style.display = 'flex'
            pickupEl.style.flexDirection = 'column'
            pickupEl.style.alignItems = 'center'
            pickupEl.style.cursor = 'pointer'
            pickupEl.innerHTML = `
              <div style="background: #10B981; color: #FFFFFF; font-weight: 800; font-size: 11px; padding: 4px 10px; border-radius: 9999px; box-shadow: 0 4px 14px rgba(16,185,129,0.6); border: 2px solid #FFFFFF; white-space: nowrap; display: flex; align-items: center; gap: 4px;">
                <span>🚲 대여</span>
                <span>${seg.from_name || '따릉이 대여소'}</span>
              </div>
              <div style="width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #10B981;"></div>
            `
            const pMarker = new maplibregl.Marker({ element: pickupEl }).setLngLat(pickupCoord).addTo(map)
            routeMarkersRef.current.push(pMarker)
          }

          // 반납소 핀 (도착 반납소):
          // 1) 최종 도착 알약과 병합된 경우 생략
          // 2) 환승역과 일치하는 경우 환승 알약에 일체형으로 병합되므로 개별 핀 생략하여 겹침 방지
          const dropCoord = seg.coords[seg.coords.length - 1]
          const isDropAtTransfer = activeRoute.transferTrains?.some(tr => {
            const trStep = activeRoute.path.find(p => p.name === tr.station)
            return tr.station === seg.to_name || (trStep && isNearbyCoord(dropCoord, trStep.coords, 0.0015))
          })

          if (mergedBikeDrop !== seg && !isDropAtTransfer) {
            const dropEl = document.createElement('div')
            dropEl.className = 'route-bike-drop-pin'
            dropEl.style.display = 'flex'
            dropEl.style.flexDirection = 'column'
            dropEl.style.alignItems = 'center'
            dropEl.style.cursor = 'pointer'
            dropEl.innerHTML = `
              <div style="background: #059669; color: #FFFFFF; font-weight: 800; font-size: 11px; padding: 4px 10px; border-radius: 9999px; box-shadow: 0 4px 14px rgba(5,150,105,0.6); border: 2px solid #FFFFFF; white-space: nowrap; display: flex; align-items: center; gap: 4px;">
                <span>🚲 반납</span>
                <span>${seg.to_name || '따릉이 반납소'}</span>
              </div>
              <div style="width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #059669;"></div>
            `
            const dMarker = new maplibregl.Marker({ element: dropEl }).setLngLat(dropCoord).addTo(map)
            routeMarkersRef.current.push(dMarker)
          }
        }

        // 버스(Bus) 세그먼트 승차/하차 마커 핀 (Issue #50)
        if (seg.mode === 'bus' && Array.isArray(seg.coords) && seg.coords.length >= 2) {
          const busPickupCoord = seg.coords[0]
          const isPickupAtStart = isNearbyCoord(busPickupCoord, startCoord, 0.001)
          if (!isPickupAtStart) {
            const busPickupEl = document.createElement('div')
            busPickupEl.className = 'route-bus-pickup-pin'
            busPickupEl.style.display = 'flex'
            busPickupEl.style.flexDirection = 'column'
            busPickupEl.style.alignItems = 'center'
            busPickupEl.style.cursor = 'pointer'
            busPickupEl.innerHTML = `
              <div style="background: ${seg.color || '#3B82F6'}; color: #FFFFFF; font-weight: 800; font-size: 11px; padding: 4px 10px; border-radius: 9999px; box-shadow: 0 4px 14px rgba(59,130,246,0.6); border: 2px solid #FFFFFF; white-space: nowrap; display: flex; align-items: center; gap: 4px;">
                <span>🚌 승차</span>
                <span>${seg.from_name || '버스 정류소'}</span>
                ${seg.line_name ? `<span style="background: rgba(0,0,0,0.25); font-size: 9px; padding: 1px 5px; border-radius: 4px;">${seg.line_name}</span>` : ''}
              </div>
              <div style="width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid ${seg.color || '#3B82F6'};"></div>
            `
            const bMarker = new maplibregl.Marker({ element: busPickupEl }).setLngLat(busPickupCoord).addTo(map)
            routeMarkersRef.current.push(bMarker)
          }

          const busDropCoord = seg.coords[seg.coords.length - 1]
          const isDropAtDest = isNearbyCoord(busDropCoord, endCoord, 0.0015)
          const isDropAtTransfer = activeRoute.transferTrains?.some(tr => {
            const trStep = activeRoute.path.find(p => p.name === tr.station)
            return tr.station === seg.to_name || (trStep && isNearbyCoord(busDropCoord, trStep.coords, 0.0015))
          })

          if (!isDropAtDest && !isDropAtTransfer) {
            const busDropEl = document.createElement('div')
            busDropEl.className = 'route-bus-drop-pin'
            busDropEl.style.display = 'flex'
            busDropEl.style.flexDirection = 'column'
            busDropEl.style.alignItems = 'center'
            busDropEl.style.cursor = 'pointer'
            busDropEl.innerHTML = `
              <div style="background: #F97316; color: #FFFFFF; font-weight: 800; font-size: 11px; padding: 4px 10px; border-radius: 9999px; box-shadow: 0 4px 14px rgba(249,115,22,0.6); border: 2px solid #FFFFFF; white-space: nowrap; display: flex; align-items: center; gap: 4px;">
                <span>🚌 하차</span>
                <span>${seg.to_name || '버스 하차정류소'}</span>
              </div>
              <div style="width: 0; height: 0; border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #F97316;"></div>
            `
            const bdMarker = new maplibregl.Marker({ element: busDropEl }).setLngLat(busDropCoord).addTo(map)
            routeMarkersRef.current.push(bdMarker)
          }
        }
      })
    }

    // 환승역 마커 핀 (앰버색 캡슐 + 환승 열차 잔여 시간 / 따릉이 연계 정보 표시)
    if (activeRoute.transferTrains && activeRoute.transferTrains.length > 0) {
      activeRoute.transferTrains.forEach(tr => {
        const trStep = activeRoute.path.find(p => p.name === tr.station)
        if (!trStep) return
        const trStop = TRANSIT_STOPS.find(s => s.name === tr.station)
        const trCrowd = trStop ? calculateCrowd(trStop) : 70

        // 환승역과 일치하는 따릉이 반납 구간 탐색
        const matchedBikeDropForTransfer = activeRoute.segments?.find(seg => 
          seg.mode === 'bike' && Array.isArray(seg.coords) && seg.coords.length >= 2 &&
          (seg.to_name === tr.station || isNearbyCoord(seg.coords[seg.coords.length - 1], trStep.coords, 0.0015))
        )

        const trEl = document.createElement('div')
        trEl.className = 'route-transfer-pin'
        trEl.style.display = 'flex'
        trEl.style.flexDirection = 'column'
        trEl.style.alignItems = 'center'
        trEl.style.cursor = 'pointer'
        trEl.innerHTML = `
          <div style="
            background: #D97706;
            color: #FFFFFF;
            font-weight: 800;
            font-size: 11px;
            padding: 5px 12px;
            border-radius: 9999px;
            box-shadow: 0 4px 18px rgba(217,119,6,0.65);
            border: 2px solid #FFFFFF;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 2px;
            white-space: nowrap;
          ">
            <div style="display: flex; align-items: center; gap: 5px;">
              <span>🔄 환승</span>
              <span>${tr.station}</span>
              <span style="background: rgba(0,0,0,0.25); font-size: 9px; padding: 1px 5px; border-radius: 4px;">${tr.line}</span>
              <span style="background: rgba(0,0,0,0.2); font-size: 9px; padding: 1px 5px; border-radius: 4px;">${trCrowd}%</span>
            </div>
            <div style="font-size: 10px; color: #FEF3C7; font-weight: 700; display: flex; align-items: center; gap: 4px;">
              <span>⏱️ ${tr.destinationOrNext} 방면</span>
              <span style="background: #78350F; color: #FDE68A; padding: 1px 5px; border-radius: 4px; font-weight: 800;">${tr.remainingMinutes}분 후 도착</span>
            </div>
            ${matchedBikeDropForTransfer ? `
              <div style="font-size: 10px; color: #D1FAE5; font-weight: 700; display: flex; align-items: center; gap: 4px; background: rgba(0,0,0,0.25); padding: 1px 7px; border-radius: 9999px; margin-top: 1px;">
                <span>🚲 따릉이 반납 ➔ 🚇 ${tr.line} 환승</span>
              </div>
            ` : ''}
          </div>
          <div style="width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #D97706;"></div>
        `
        if (trStop) {
          trEl.addEventListener('click', () => {
            if (activePopupRef.current) {
              activePopupRef.current.remove()
              activePopupRef.current = null
              popupOpenedZoomRef.current = null
            }
            setActiveStop(trStop)
            if (onSelectStop) onSelectStop(trStop)
            if (mapInstanceRef.current) {
              const currentZ = mapInstanceRef.current.getZoom()
              const targetZoom = currentZ < 15.5 ? 15.5 : Math.min(17.5, currentZ + 0.5)
              mapInstanceRef.current.flyTo({
                center: trStop.coords,
                zoom: targetZoom,
                pitch: DEFAULT_MAP_PITCH,
                duration: 700,
                essential: true,
              })
            }
          })
        }
        const trMarker = new maplibregl.Marker({ element: trEl })
          .setLngLat(trStep.coords)
          .addTo(map)
        routeMarkersRef.current.push(trMarker)
      })
    }

    // 도착지 마커 핀 (로즈색 캡슐 / 따릉이 반납과 인접 시 일체형 병합 알약 표출)
    const endStop = TRANSIT_STOPS.find(s => s.name === activeRoute.to)
    const endCrowd = endStop ? calculateCrowd(endStop) : 75
    const endEl = document.createElement('div')
    endEl.className = 'route-end-pin'
    endEl.style.display = 'flex'
    endEl.style.flexDirection = 'column'
    endEl.style.alignItems = 'center'
    endEl.style.cursor = 'pointer'

    if (mergedBikeDrop) {
      // 도착지와 따릉이 반납소가 겹칠 경우: 유려한 그라디언트 일체형 캡슐 알약으로 통합!
      endEl.innerHTML = `
        <div style="
          background: linear-gradient(135deg, #059669 0%, #E11D48 100%);
          color: #FFFFFF;
          font-weight: 800;
          font-size: 11px;
          padding: 5px 12px;
          border-radius: 9999px;
          box-shadow: 0 4px 18px rgba(225,29,72,0.65);
          border: 2px solid #FFFFFF;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 2px;
          white-space: nowrap;
        ">
          <div style="display: flex; align-items: center; gap: 5px;">
            <span>🏁 도착</span>
            <span>${activeRoute.to}</span>
            <span style="background: rgba(0,0,0,0.25); font-size: 9px; padding: 1px 5px; border-radius: 6px;">${endCrowd}%</span>
          </div>
          <div style="font-size: 10px; color: #D1FAE5; font-weight: 700; display: flex; align-items: center; gap: 4px; background: rgba(0,0,0,0.22); padding: 1px 7px; border-radius: 9999px; margin-top: 1px;">
            <span>🚲 따릉이 반납:</span>
            <span>${mergedBikeDrop.to_name || '반납소'}</span>
          </div>
        </div>
        <div style="width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #E11D48;"></div>
      `
    } else {
      endEl.innerHTML = `
        <div style="
          background: #F43F5E;
          color: #FFFFFF;
          font-weight: 800;
          font-size: 11px;
          padding: 4px 10px;
          border-radius: 9999px;
          box-shadow: 0 4px 18px rgba(244,63,94,0.6);
          border: 2px solid #FFFFFF;
          display: flex;
          align-items: center;
          gap: 5px;
          white-space: nowrap;
        ">
          <span>🔴 도착</span>
          <span>${activeRoute.to}</span>
          <span style="background: rgba(0,0,0,0.25); font-size: 9px; padding: 1px 5px; border-radius: 6px;">${endCrowd}%</span>
        </div>
        <div style="width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #F43F5E;"></div>
      `
    }
    if (endStop) {
      endEl.addEventListener('click', () => {
        if (activePopupRef.current) {
          activePopupRef.current.remove()
          activePopupRef.current = null
          popupOpenedZoomRef.current = null
        }
        setActiveStop(endStop)
        if (onSelectStop) onSelectStop(endStop)
        if (mapInstanceRef.current) {
          const currentZ = mapInstanceRef.current.getZoom()
          const targetZoom = currentZ < 15.5 ? 15.5 : Math.min(17.5, currentZ + 0.5)
          mapInstanceRef.current.flyTo({
            center: endStop.coords,
            zoom: targetZoom,
            pitch: DEFAULT_MAP_PITCH,
            duration: 700,
            essential: true,
          })
        }
      })
    }
    const endMarker = new maplibregl.Marker({ element: endEl })
      .setLngLat(coords[coords.length - 1])
      .addTo(map)
    routeMarkersRef.current.push(endMarker)

    updateCollisions()

    return () => {
      routeMarkersRef.current.forEach(m => m.remove())
      routeMarkersRef.current = []
    }
  }, [activeRoute, mapLoaded, rainMm, selectedTime])

  // focusedCoords 변경 시 부드럽게 해당 거점으로 카메라 이동 (flyTo)
  // focusedCoords 변경 시 부드럽게 해당 거점으로 카메라 이동 (flyTo) 및 해당 마커 팝업 열기
  useEffect(() => {
    if (focusedCoords && mapInstanceRef.current) {
      isFlyingRef.current = true
      mapInstanceRef.current.flyTo({
        center: focusedCoords,
        zoom: 15.5,
        pitch: DEFAULT_MAP_PITCH,
        duration: 700,
        essential: true,
      })
      setTimeout(() => {
        isFlyingRef.current = false
        if (mapInstanceRef.current) {
          popupOpenedZoomRef.current = mapInstanceRef.current.getZoom()
        }
      }, 750)

      // 해당 위치의 마커 엘리먼트를 찾아 클릭 트리거 (실시간 도착 정보 수신 및 팝업 표출)
      const matched = markerItemsRef.current.find(item => {
        const [lng, lat] = item.stop.coords
        return Math.abs(lng - focusedCoords[0]) < 0.0005 && Math.abs(lat - focusedCoords[1]) < 0.0005
      })
      if (matched && matched.el) {
        matched.el.click()
      }
    }
  }, [focusedCoords])

  // 권역 바로가기
  const flyToArea = (coords: [number, number], zoom = 14) => {
    if (!mapInstanceRef.current) return
    mapInstanceRef.current.flyTo({
      center: coords,
      zoom: zoom,
      pitch: DEFAULT_MAP_PITCH,
      essential: true,
    })
  }

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
      {/* 지도 컨테이너 */}
      <div ref={mapContainerRef} style={{ width: '100%', height: '100%' }} />

      {/* 권역 원클릭 카메라 퀵 이동 컨트롤 */}
      <div style={{
        position: 'absolute',
        top: 16,
        left: 16,
        zIndex: 10,
        display: 'flex',
        gap: 6,
        background: 'rgba(17, 29, 53, 0.88)',
        backdropFilter: 'blur(10px)',
        padding: '6px 8px',
        borderRadius: 12,
        border: '1px solid rgba(56, 189, 248, 0.25)',
      }}>
        <button
          onClick={() => flyToArea([127.0276, 37.4979], 14)}
          style={{ background: 'rgba(56,189,248,0.15)', border: 'none', color: '#F0F6FF', padding: '5px 10px', borderRadius: 8, fontSize: 11, fontWeight: 600, cursor: 'pointer' }}
        >
          📍 강남·역삼
        </button>
        <button
          onClick={() => flyToArea([127.0950, 37.5120], 14)}
          style={{ background: 'rgba(255,255,255,0.06)', border: 'none', color: '#F0F6FF', padding: '5px 10px', borderRadius: 8, fontSize: 11, fontWeight: 600, cursor: 'pointer' }}
        >
          📍 잠실·송파
        </button>
        <button
          onClick={() => flyToArea([126.9242, 37.5219], 14)}
          style={{ background: 'rgba(255,255,255,0.06)', border: 'none', color: '#F0F6FF', padding: '5px 10px', borderRadius: 8, fontSize: 11, fontWeight: 600, cursor: 'pointer' }}
        >
          📍 여의도
        </button>
        <button
          onClick={() => flyToArea([126.9750, 37.5580], 14)}
          style={{ background: 'rgba(255,255,255,0.06)', border: 'none', color: '#F0F6FF', padding: '5px 10px', borderRadius: 8, fontSize: 11, fontWeight: 600, cursor: 'pointer' }}
        >
          📍 서울역·도심
        </button>
      </div>

      {/* 🚌 버스 노선 정보 및 경유 정류장 목록 (기존 지하철 안내와 독립) */}
      {selectedBusRoute && (
        <div style={{
          position: 'absolute', top: activeRoute ? 160 : 68, left: 16, zIndex: 12,
          width: 'min(305px, calc(100% - 32px))', maxHeight: 'min(450px, 65vh)',
          overflow: 'hidden', display: 'flex', flexDirection: 'column',
          background: 'rgba(17,29,53,0.96)', border: '1px solid #F59E0B',
          borderRadius: 12, padding: 12, boxShadow: '0 8px 24px rgba(0,0,0,0.55)'
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
            <strong style={{ color: '#FBBF24', fontSize: 14 }}>🚌 {selectedBusRoute.name}번 노선</strong>
            <button
              type="button"
              onClick={() => setSelectedBusRoute(null)}
              style={{ background: 'rgba(255,255,255,0.1)', color: '#F0F6FF', border: 0, borderRadius: 6, padding: '4px 8px', cursor: 'pointer' }}
            >닫기 ✕</button>
          </div>
          <div style={{ color: '#94A3B8', fontSize: 11, marginTop: 6, marginBottom: 8 }}>
            {busRouteLoading ? '경유 정류장 불러오는 중...' :
              busRouteError || `${busRouteStations.length}개 경유 정류장 · 점과 선은 정류장 좌표 기반`}
          </div>
          <div style={{ fontSize: 11, color: '#E2E8F0', marginBottom: 8, padding: '8px', background: 'rgba(255,255,255,0.05)', borderRadius: 8 }}>
            <div style={{ fontWeight: 700, color: '#34D399' }}>📍 선택 정류장 접근 차량 (최대 2대)</div>
            {approachingBusLoading && <div style={{ marginTop: 5, color: '#94A3B8' }}>실시간 위치 갱신 중...</div>}
            {approachingBusError && <div style={{ marginTop: 5, color: '#FCA5A5' }}>{approachingBusError}</div>}
            {!approachingBusLoading && !approachingBusError && approachingBusVehicles.length === 0 && (
              <div style={{ marginTop: 5, color: '#94A3B8' }}>{approachingBusMessage || '현재 접근 차량 위치가 없습니다.'}</div>
            )}
            {approachingBusVehicles.map(vehicle => (
              <button
                key={vehicle.vehicle_id}
                type="button"
                onClick={() => mapInstanceRef.current?.flyTo({ center: vehicle.coords, zoom: 15, pitch: DEFAULT_MAP_PITCH, duration: 700, essential: true })}
                style={{ display: 'block', marginTop: 6, padding: '5px 7px', width: '100%', textAlign: 'left', cursor: 'pointer', borderRadius: 6, border: '1px solid rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.05)', color: vehicle.arrival_order === 1 ? '#34D399' : '#38BDF8', fontWeight: 700, fontSize: 11 }}
              >
                {vehicle.arrival_order === 1 ? '🟢 첫차' : '🔵 다음 차'} · {vehicle.arrival_message || '도착정보 없음'}
              </button>
            ))}
            <div style={{ fontSize: 10, color: '#94A3B8', marginTop: 6 }}>30초마다 갱신 · ▲ 노선 진행 방향</div>
          </div>
          {!busRouteLoading && busRouteStations.length > 0 && (
            <div style={{ overflowY: 'auto', minHeight: 0 }}>
              {busRouteStations.map(station => (
                <button
                  type="button"
                  key={`${selectedBusRoute.id}-${station.sequence}`}
                  onClick={() => mapInstanceRef.current?.flyTo({
                    center: station.coords, zoom: 16, pitch: DEFAULT_MAP_PITCH, duration: 700, essential: true
                  })}
                  style={{
                    display: 'block', width: '100%', textAlign: 'left',
                    background: 'transparent', color: '#E2E8F0', border: 0,
                    borderBottom: '1px solid rgba(255,255,255,0.08)',
                    padding: '7px 3px', fontSize: 11, cursor: 'pointer'
                  }}
                >
                  <span style={{ color: '#FBBF24', marginRight: 8 }}>{station.sequence}</span>
                  {station.name}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* 활성 검색 경로 안내 플로팅 카드 */}
      {activeRoute && (
        <div style={{
          position: 'absolute',
          top: 68,
          left: 16,
          zIndex: 10,
          background: 'rgba(17, 29, 53, 0.95)',
          backdropFilter: 'blur(14px)',
          border: '1px solid rgba(56, 189, 248, 0.45)',
          borderRadius: 14,
          padding: '10px 14px',
          boxShadow: '0 8px 30px rgba(0,0,0,0.6)',
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ background: 'rgba(16, 185, 129, 0.25)', border: '1px solid #10B981', color: '#10B981', borderRadius: 6, padding: '2px 6px', fontSize: 10, fontWeight: 800 }}>
                출발
              </span>
              <span style={{ fontSize: 13, fontWeight: 700, color: '#F0F6FF' }}>{activeRoute.from}</span>
              <span style={{ color: '#38BDF8', fontSize: 12, margin: '0 2px' }}>➔</span>
              <span style={{ background: 'rgba(244, 63, 94, 0.25)', border: '1px solid #F43F5E', color: '#F43F5E', borderRadius: 6, padding: '2px 6px', fontSize: 10, fontWeight: 800 }}>
                도착
              </span>
              <span style={{ fontSize: 13, fontWeight: 700, color: '#F0F6FF' }}>{activeRoute.to}</span>
            </div>

            <div style={{ height: 18, width: 1, background: 'rgba(255,255,255,0.1)' }} />

            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{
                background: activeRoute.transferCount === 0 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                border: activeRoute.transferCount === 0 ? '1px solid #10B981' : '1px solid #F59E0B',
                color: activeRoute.transferCount === 0 ? '#10B981' : '#FBBF24',
                borderRadius: 6,
                padding: '2px 7px',
                fontSize: 10,
                fontWeight: 800,
                whiteSpace: 'nowrap',
              }}>
                {activeRoute.transferCount === 0 ? '환승 0회 (직통)' : `최소 환승: ${activeRoute.transferCount}회`}
              </span>
              <span style={{ fontSize: 12, color: '#38BDF8', fontWeight: 800, fontFamily: 'JetBrains Mono', whiteSpace: 'nowrap' }}>
                약 {activeRoute.estimatedMinutes}분
              </span>
              <span style={{ fontSize: 11, color: 'rgba(255,255,255,0.5)', whiteSpace: 'nowrap' }}>
                ({activeRoute.stationCount}개 역)
              </span>
            </div>

            {onClearRoute && (
              <button
                onClick={() => {
                  if (activePopupRef.current) {
                    activePopupRef.current.remove()
                    activePopupRef.current = null
                    popupOpenedZoomRef.current = null
                  }
                  markerItemsRef.current.forEach(item => {
                    item.el.style.display = 'flex'
                  })
                  onClearRoute()
                }}
                title="경로 안내 닫기"
                style={{
                  background: 'rgba(255,255,255,0.08)',
                  border: 'none',
                  color: 'rgba(255,255,255,0.7)',
                  borderRadius: 8,
                  padding: '4px 8px',
                  fontSize: 11,
                  cursor: 'pointer',
                  marginLeft: 'auto',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                <span>✕</span>
                <span>닫기</span>
              </button>
            )}
          </div>

          {/* 출발역 & 환승역 탑승 열차 잔여 시간 실시간 안내 행 */}
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10, fontSize: 11,
            paddingTop: 6, borderTop: '1px solid rgba(255,255,255,0.08)', flexWrap: 'wrap'
          }}>
            {activeRoute.departureTrain && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ color: '#34D399', fontWeight: 700 }}>🟢 {activeRoute.from}</span>
                <span style={{ color: 'rgba(255,255,255,0.5)', fontSize: 10 }}>[{activeRoute.departureTrain.line}]</span>
                <span style={{ color: '#38BDF8', fontWeight: 800, fontFamily: 'JetBrains Mono' }}>
                  {activeRoute.departureTrain.remainingMinutes}분 후 탑승
                </span>
                <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 10 }}>({activeRoute.departureTrain.destinationOrNext} 방면)</span>
              </div>
            )}
            {activeRoute.transferTrains && activeRoute.transferTrains.map(tr => (
              <div key={tr.station} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ color: 'rgba(255,255,255,0.2)' }}>•</span>
                <span style={{ color: '#FBBF24', fontWeight: 700 }}>🔄 {tr.station} 환승</span>
                <span style={{ color: 'rgba(255,255,255,0.5)', fontSize: 10 }}>[{tr.line}]</span>
                <span style={{ color: '#FBBF24', fontWeight: 800, fontFamily: 'JetBrains Mono' }}>
                  {tr.remainingMinutes}분 후 탑승
                </span>
                <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 10 }}>({tr.destinationOrNext} 방면)</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 실시간 기상청 실황 관측치 오버레이 */}
      <div style={{
        position: 'absolute',
        top: 16,
        right: 56, // 지도 컨트롤러 피해서 배치
        zIndex: 10,
        background: 'rgba(17, 29, 53, 0.94)',
        backdropFilter: 'blur(12px)',
        border: '1px solid rgba(56, 189, 248, 0.35)',
        borderRadius: 14,
        padding: '10px 14px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
      }}>
        <span style={{ fontSize: 24 }}>{rainMm > 0 ? '🌧' : '☀️'}</span>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#F0F6FF' }}>
            🟢 기상청 실시간 관측 실황 | {liveWeather ? `${liveWeather.temp}°C · ` : ''}{rainMm > 0 ? `강수량 ${rainMm.toFixed(1)}mm/h` : '강수 없음 (맑음)'}
          </div>
          <div style={{ fontSize: 10, color: '#38BDF8', marginTop: 2, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>{liveWeather ? `${liveWeather.district || '관측소'} (${liveWeather.base_time ? `${liveWeather.base_time.slice(0, 2)}:${liveWeather.base_time.slice(2, 4)} 발표` : selectedTime})` : '100% 공공데이터 실측 실황'}</span>
            <span style={{ color: 'rgba(255,255,255,0.3)' }}>·</span>
            <span>OpenStreetMap + MapLibre GL</span>
          </div>
        </div>
      </div>

      {/* 줌 확대 안내 배지 / 경로 집중 모드 배지 */}
      <div style={{
        position: 'absolute',
        bottom: 24,
        left: 120,
        zIndex: 10,
        background: 'rgba(17, 29, 53, 0.88)',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(56, 189, 248, 0.25)',
        borderRadius: 10,
        padding: '6px 12px',
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
        pointerEvents: 'none',
      }}>
        <span style={{ fontSize: 12 }}>{activeRoute ? '🧭' : (zoomLevel < 11.5 ? '🗺️' : '🔍')}</span>
        <span style={{ fontSize: 11, color: '#E2E8F0', fontWeight: 600 }}>
          {activeRoute
            ? `최소 환승 경로 집중 모드: ${activeRoute.transferCount === 0 ? '직통' : `${activeRoute.transferCount}회 환승`} 경로상의 역만 표시 중입니다 (닫기 클릭 시 전체 역 복원)`
            : (zoomLevel < 10.5
                ? '광역 지도 (마커 숨김): 지도를 확대하면 주요 거점이 표시됩니다'
                : (zoomLevel < 11.5
                    ? '광역 지도 모드: 수도권 핵심 거점 위주 표시 (지도를 확대하면 버스 환승센터 및 따릉이 거점 표출)'
                    : (zoomLevel < 13.5
                        ? '도심 지도 모드: 버스 및 따릉이 거점이 점(Dot) 마커로 표시 중입니다 (더 확대하면 상세 이름 표출)'
                        : '상세 지도 모드: 주변 세부 버스 정류소와 따릉이 거점 대여소가 실시간 연동 표시됩니다')))}
        </span>
      </div>

      {/* 범례 */}
      <div style={{
        position: 'absolute',
        bottom: 24,
        right: 16,
        zIndex: 10,
        background: 'rgba(17, 29, 53, 0.92)',
        backdropFilter: 'blur(12px)',
        border: '1px solid rgba(255, 255, 255, 0.1)',
        borderRadius: 14,
        padding: '10px 14px',
        boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
      }}>
        <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', fontFamily: 'JetBrains Mono', marginBottom: 6, letterSpacing: '0.05em' }}>
          대중교통 인프라 & 혼잡도
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#10B981' }} />
            <span style={{ fontSize: 11, color: '#F0F6FF' }}>여유 (&lt; 45%)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#38BDF8' }} />
            <span style={{ fontSize: 11, color: '#F0F6FF' }}>보통 (45% ~ 75%)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%', background: '#F43F5E' }} />
            <span style={{ fontSize: 11, color: '#F0F6FF' }}>혼잡 (&gt; 75%)</span>
          </div>
          <div style={{ height: 1, background: 'rgba(255,255,255,0.1)', margin: '4px 0' }} />
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#38BDF8', border: '1.5px solid #FFFFFF', boxShadow: '0 0 6px #38BDF8' }} />
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.7)' }}>밀집 구간 정류소 (점 마커)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 2 }}>
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.45)', fontFamily: 'JetBrains Mono' }}>
              🚇 561역 · 🚌 55개소 · 🚲 52개소
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
