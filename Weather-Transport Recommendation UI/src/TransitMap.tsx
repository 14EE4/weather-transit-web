import { useEffect, useRef, useState } from 'react'
import { logWeatherApiCall, logBusApiCall, logSubwayApiCall, logAIPredictionCall } from './apiLogger'
import { SUBWAY_STATIONS } from './subwayData'
import { BUS_STOPS } from './busStopData'
import { BIKE_STATIONS } from './bikeStopData'
import { TransitRouteResult } from './subwayGraph'
import { resolveDistrict } from './districtResolver'
import { SUBWAY_NETWORK_GEOJSON } from './subwayNetworkLayer'

const API_BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000'

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

export default function TransitMap({ filterType, rainMm, selectedTime, liveWeather, focusedCoords, onSelectStop, activeRoute, onClearRoute }: TransitMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<any>(null)
  const markerItemsRef = useRef<MarkerItem[]>([])
  const routeMarkersRef = useRef<any[]>([])
  const animFrameRef = useRef<number | null>(null)
  const activePopupRef = useRef<any>(null)
  const popupOpenedZoomRef = useRef<number | null>(null)
  const isFlyingRef = useRef<boolean>(false)
  const [activeStop, setActiveStop] = useState<TransitStop | null>(null)
  const [mapLoaded, setMapLoaded] = useState(false)
  const [zoomLevel, setZoomLevel] = useState<number>(13)

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

    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: {
        version: 8,
        sources: {
          'osm-tiles': {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            tileSize: 256,
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a>',
          },
        },
        layers: [
          {
            id: 'osm-tiles-layer',
            type: 'raster',
            source: 'osm-tiles',
            minzoom: 0,
            maxzoom: 19,
          },
        ],
      },
      center: [127.050, 37.505], // 강남구 중심
      zoom: 13,
      pitch: 30, // 3D 입체감
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

      setMapLoaded(true)
    })

    mapInstanceRef.current = map

    return () => {
      map.remove()
    }
  }, [])

  // 1-2. 검색 등으로 focusedCoords 지정 시 카메라 부드러운 이동 (flyTo)
  useEffect(() => {
    if (!mapLoaded || !mapInstanceRef.current || !focusedCoords) return
    mapInstanceRef.current.flyTo({
      center: focusedCoords,
      zoom: 15,
      pitch: 45,
      essential: true,
    })
  }, [focusedCoords, mapLoaded])

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
      popupOpenedZoomRef.current = null
    }

    const hasActiveRoute = !!(currentRoute && currentRoute.path && currentRoute.path.length >= 2)
    const routeStationNames = hasActiveRoute ? new Set(currentRoute.path.map(p => p.name)) : null

    // 0. 일정 배율 이하로 많이 줌아웃한 경우 (currentZoom < 11.0, 활성 경로가 없을 때만):
    // 광역 지도 탐색 시 화면이 수백 개의 마커로 가려지지 않도록 주요 거점(지하철 환승역) 위주로 표출
    if (currentZoom < 11.0 && !hasActiveRoute) {
      for (const item of markerItemsRef.current) {
        const [lng, lat] = item.stop.coords
        const isFocused = currentFocused && Math.abs(lng - currentFocused[0]) < 0.0002 && Math.abs(lat - currentFocused[1]) < 0.0002
        const isSelected = currentActiveStop && currentActiveStop.id === item.stop.id
        const isMajorHub = item.priority >= 250 // Tier 1, Tier 2 거점 역

        if (isFocused || isSelected || isMajorHub) {
          item.el.style.display = 'flex'
          item.el.style.zIndex = '9999'
        } else {
          item.el.style.display = 'none'
        }
      }
      return
    }

    // 0-1. 중거리 도심 탐색 구간 (11.0 <= currentZoom < 13.0, 전체 모드 시):
    // 일반 지엽 버스/따릉이는 상세 배율(13.0+)에서 띄우고, 주요 환승센터/대형공원 거점 위주로 단계적 노출
    const isMidRangeZoom = currentZoom < 13.0 && !hasActiveRoute && filterType === 'all'

    const placedBoxes: { x1: number; y1: number; x2: number; y2: number }[] = []

    // 줌 레벨에 따라 겹침 감지 박스 크기 동적 조절 (확대할수록 간격 좁아져 많은 역 등장, 12~13구간은 넓혀 주요 거점만)
    const halfW = currentZoom >= 16 ? 32 : (currentZoom >= 14 ? 44 : (currentZoom >= 13 ? 56 : 72))
    const halfH = currentZoom >= 16 ? 12 : (currentZoom >= 14 ? 16 : (currentZoom >= 13 ? 20 : 26))

    for (const item of markerItemsRef.current) {
      const [lng, lat] = item.stop.coords

      // 1. 활성 경로가 있는 경우: 경로에 포함된 역 이외의 모든 역/정류소는 완전히 숨김
      if (hasActiveRoute && routeStationNames && currentRoute) {
        if (!routeStationNames.has(item.stop.name)) {
          item.el.style.display = 'none'
          continue
        }
        // 출발역, 도착역, 환승역은 전용 핀 마커가 배치되므로 일반 알약 마커는 숨겨서 중복 방지
        const isSpecialPinStation = item.stop.name === currentRoute.from || 
                                    item.stop.name === currentRoute.to || 
                                    (currentRoute.transferStations && currentRoute.transferStations.includes(item.stop.name))
        if (isSpecialPinStation) {
          item.el.style.display = 'none'
          continue
        }
      }

      // 1-1. 중거리 뷰(11.0~13.0)에서 전체 모드일 경우 지엽 정류소 필터링
      if (isMidRangeZoom) {
        const isSelectedOrFocused = (currentFocused && Math.abs(lng - currentFocused[0]) < 0.0002 && Math.abs(lat - currentFocused[1]) < 0.0002) ||
                                    (currentActiveStop && currentActiveStop.id === item.stop.id)
        if (!isSelectedOrFocused) {
          if (item.stop.type === 'bus' && !item.stop.isHub) {
            item.el.style.display = 'none'
            continue
          }
          if (item.stop.type === 'bike' && !item.stop.isPopularSpot) {
            item.el.style.display = 'none'
            continue
          }
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

      // 4. 현재 검색되었거나 클릭하여 선택된 역, 또는 활성 경로 경유 역은 무조건 우선 표시!
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

      // 겹치면 완전히 숨기지 않고 혼잡도 색상의 원형 점(Dot) 마커로 전환 표출!
      if (overlaps) {
        if (pillView) pillView.style.display = 'none'
        if (dotView) dotView.style.display = 'flex'
        item.el.style.display = 'flex'
        item.el.style.zIndex = '5'
      } else {
        // 여유 공간이 확보되면 알약 마커(이름 + 아이콘 + 혼잡도%)로 온전히 표시
        if (pillView) pillView.style.display = 'flex'
        if (dotView) dotView.style.display = 'none'
        item.el.style.display = 'flex'
        item.el.style.zIndex = '10'
        placedBoxes.push({ x1, y1, x2, y2 })
      }
    }
  }

  updateCollisionsRef.current = updateCollisions

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

    const filtered = filterType === 'all'
      ? TRANSIT_STOPS
      : TRANSIT_STOPS.filter(s => s.type === filterType)

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

        <!-- 2. 점 마커 뷰 (이름 겹침 시 대체 표출되는 미니 원형 점) -->
        <div class="marker-dot-view" style="
          display: none;
          align-items: center;
          justify-content: center;
          padding: 3px;
        " title="${stop.name} (${label} ${crowd}%)">
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
        },
        isLoadingArrivalsArg = false
      ) => {
        let arrivalsList: any[] = []
        let isLoadingArrivals = false
        let weatherData: any = null
        let aiData: any = null
        let isLoadingAll = false

        if (Array.isArray(arrivalsOrOptions)) {
          arrivalsList = arrivalsOrOptions
          isLoadingArrivals = isLoadingArrivalsArg
        } else if (arrivalsOrOptions && typeof arrivalsOrOptions === 'object') {
          arrivalsList = arrivalsOrOptions.arrivalsList || []
          isLoadingArrivals = !!arrivalsOrOptions.isLoadingArrivals
          weatherData = arrivalsOrOptions.weather || null
          aiData = arrivalsOrOptions.aiPrediction || null
          isLoadingAll = !!arrivalsOrOptions.isLoadingAll
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
                <div style="display: flex; flex-direction: column; gap: 4px; max-height: 130px; overflow-y: auto;">
                  ${arrivalsList.slice(0, 4).map((arr: any) => `
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
                  <span style="font-size: 9px; color: #34D399; background: rgba(52,211,153,0.15); padding: 1px 5px; border-radius: 4px; font-weight: 700;">실시간 API</span>
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
          const rackTotal = stop.rackCount || 20
          // 혼잡도와 강수량에 따른 실시간 대여 가능 잔여 대수 추정
          const crowdRatio = (displayCrowd || 60) / 100
          const availableBikes = rainMm > 0 ? Math.max(0, Math.round(rackTotal * 0.85)) : Math.max(1, Math.round(rackTotal * (1 - crowdRatio * 0.65)))
          arrivalSection = `
            <div style="margin-top: 8px; padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.1);">
              <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px;">
                <span style="font-size: 11px; font-weight: 800; color: #34D399; display: flex; align-items: center; gap: 4px;">
                  <span>🚲</span> 따릉이 실시간 거치 현황
                </span>
                <span style="font-size: 9px; color: #34D399; background: rgba(52,211,153,0.15); padding: 1px 5px; border-radius: 4px; font-weight: 700;">
                  ${stop.stationNo ? `대여소 #${stop.stationNo}` : '거점 대여소'}
                </span>
              </div>
              <div style="display: flex; align-items: center; justify-content: space-between; background: rgba(0,0,0,0.35); padding: 6px 10px; border-radius: 6px; font-size: 11px; border-left: 2px solid #34D399;">
                <span style="color: #E2E8F0;">대여 가능 자전거</span>
                <span style="color: #34D399; font-weight: 800; font-family: monospace;">약 ${availableBikes}대 / 총 ${rackTotal}대</span>
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
        if (onSelectStop) onSelectStop(null)
      })

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat(stop.coords)
        .setPopup(popup)
        .addTo(mapInstanceRef.current)

      el.addEventListener('click', async () => {
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
        if (mapInstanceRef.current) {
          const currentZ = mapInstanceRef.current.getZoom()
          const targetZoom = currentZ < 15.5 ? 15.5 : Math.min(17.5, currentZ + 0.5)
          isFlyingRef.current = true
          mapInstanceRef.current.flyTo({
            center: stop.coords,
            zoom: targetZoom,
            pitch: 35,
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
              logSubwayApiCall(cleanName, arrivals, arrivalData)
            } catch {
              arrivals = [
                { line: stop.lineInfo.split(' · ')[0] || '지하철', destination: `${stop.name} 경유 방면`, message: '정상 운행중', remaining_minutes: 2, updn_line: '상/하행' }
              ]
              logSubwayApiCall(cleanName, arrivals)
            }
          } else if (stop.type === 'bus') {
            const targetStId = stop.stId || '111000299'
            const defaultRoutes = stop.lineInfo ? stop.lineInfo.split(/[·,]/).map(s => s.trim().replace(/등$/, '')).filter(Boolean) : ['간선']
            const r1 = defaultRoutes[0] || '140'
            const r2 = defaultRoutes[1] || '472'
            try {
              const busRes = await fetch(`${API_BASE_URL}/api/v1/transit/bus/arrival?stId=${encodeURIComponent(targetStId)}`)
              const busData = await busRes.json()
              arrivals = (busData.status === 'success' && busData.arrivals && busData.arrivals.length > 0)
                ? busData.arrivals
                : [
                    { route_name: r1, arrival_msg1: '곧 도착' },
                    { route_name: r2, arrival_msg1: '3분 후' }
                  ]
              logBusApiCall(r1, targetStId, arrivals, busData)
            } catch {
              arrivals = [
                { route_name: r1, arrival_msg1: '곧 도착' },
                { route_name: r2, arrival_msg1: '3분 후' }
              ]
              logBusApiCall(r1, targetStId, arrivals)
            }
          }

          // 최종 통합 데이터로 팝업 갱신
          if (activePopupRef.current === popup) {
            popup.setHTML(buildPopupContent({
              weather: weatherData,
              aiPrediction: aiData,
              arrivalsList: arrivals,
              isLoadingArrivals: false
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
  }, [filterType, rainMm, mapLoaded, selectedTime])

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
      // 경로 닫기 시 모든 마커의 display를 원상 복원하고 충돌 필터링 재계산
      markerItemsRef.current.forEach(item => {
        item.el.style.display = 'flex'
      })
      updateCollisions()

      // 경로 핏바운즈로 인해 줌이 너무 축소되어 있다면 (zoom < 12.8) 일반 시야각(13.0)으로 부드럽게 복귀
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
      return
    }

    const coords = activeRoute.path.map(p => p.coords)
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

    // 경로 전체를 한눈에 볼 수 있도록 카메라 바운드 자동 맞춤 (fitBounds)
    const bounds = new maplibregl.LngLatBounds()
    coords.forEach(c => bounds.extend(c))
    map.fitBounds(bounds, {
      padding: { top: 90, bottom: 90, left: 100, right: 100 },
      maxZoom: 15,
      duration: 1000,
    })

    // 출발지 마커 핀 (초록색 캡슐 + 탑승 열차 잔여 시간 표시)
    const startStop = TRANSIT_STOPS.find(s => s.name === activeRoute.from)
    const startCrowd = startStop ? calculateCrowd(startStop) : 65
    const depTrain = activeRoute.departureTrain
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
            pitch: 35,
            duration: 700,
            essential: true,
          })
        }
      })
    }
    const startMarker = new maplibregl.Marker({ element: startEl })
      .setLngLat(coords[0])
      .addTo(map)
    routeMarkersRef.current.push(startMarker)

    // 환승역 마커 핀 (앰버색 캡슐 + 환승 열차 잔여 시간 표시)
    if (activeRoute.transferTrains && activeRoute.transferTrains.length > 0) {
      activeRoute.transferTrains.forEach(tr => {
        const trStep = activeRoute.path.find(p => p.name === tr.station)
        if (!trStep) return
        const trStop = TRANSIT_STOPS.find(s => s.name === tr.station)
        const trCrowd = trStop ? calculateCrowd(trStop) : 70

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
                pitch: 35,
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

    // 도착지 마커 핀 (로즈색 캡슐)
    const endStop = TRANSIT_STOPS.find(s => s.name === activeRoute.to)
    const endCrowd = endStop ? calculateCrowd(endStop) : 75
    const endEl = document.createElement('div')
    endEl.className = 'route-end-pin'
    endEl.style.display = 'flex'
    endEl.style.flexDirection = 'column'
    endEl.style.alignItems = 'center'
    endEl.style.cursor = 'pointer'
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
            pitch: 35,
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
        pitch: 35,
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
      pitch: 35,
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
            : (zoomLevel < 11.5
                ? '광역 지도 모드: 수도권 핵심 거점 위주 표시 (지도를 확대하면 버스 환승센터 및 따릉이 거점 표출)'
                : '상세 지도 모드: 주변 세부 버스 정류소와 따릉이 거점 대여소가 실시간 연동 표시됩니다')}
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
