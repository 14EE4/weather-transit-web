import { useEffect, useRef, useState } from 'react'
import { logBusApiCall, logSubwayApiCall, logAIPredictionCall } from './apiLogger'
import { SUBWAY_STATIONS } from './subwayData'
import { TransitRouteResult } from './subwayGraph'

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
}

// ── 서울 주요 지하철역(전체 확장) + 버스 정류소 + 따릉이 대여소 ──
export const TRANSIT_STOPS: TransitStop[] = [
  // 지하철역 (SUBWAY_STATIONS 마스터 데이터 연동)
  ...SUBWAY_STATIONS.map(s => ({
    id: s.id,
    name: s.name,
    type: 'subway' as const,
    coords: s.coords,
    lineInfo: s.lines.join(' · '),
    baseCrowd: s.baseCrowd,
    rainSensitivity: 1.2
  })),

  // 버스 정류소
  { id: 'bus-gn-center', name: '강남역(중앙차로)', type: 'bus', coords: [127.0282, 37.4988], lineInfo: '140, 472, 9408 등', baseCrowd: 75, rainSensitivity: 1.3 },
  { id: 'bus-sinnonhyeon', name: '신논현역.구보건소', type: 'bus', coords: [127.0252, 37.5045], lineInfo: '144, 360, 6411 등', baseCrowd: 68, rainSensitivity: 1.25 },
  { id: 'bus-samseong', name: '무역센터(삼성역)', type: 'bus', coords: [127.0601, 37.5097], lineInfo: '143, 301, 3412 등', baseCrowd: 64, rainSensitivity: 1.2 },
  { id: 'bus-yeouido-tc', name: '여의도환승센터', type: 'bus', coords: [126.9255, 37.5248], lineInfo: '160, 260, 8600 등', baseCrowd: 70, rainSensitivity: 1.35 },
  { id: 'bus-seoul-tc', name: '서울역버스환승센터', type: 'bus', coords: [126.9723, 37.5562], lineInfo: '150, 503, 702 등', baseCrowd: 78, rainSensitivity: 1.3 },

  // 따릉이 대여소
  { id: 'bike-gn-exit9', name: '따릉이: 강남역 9번출구', type: 'bike', coords: [127.0264, 37.4984], lineInfo: '거치대 20대 (대여가능)', baseCrowd: 80, rainSensitivity: -2.5 },
  { id: 'bike-samseong', name: '따릉이: 삼성역 5번출구', type: 'bike', coords: [127.0612, 37.5090], lineInfo: '거치대 15대 (대여가능)', baseCrowd: 65, rainSensitivity: -2.2 },
  { id: 'bike-yeouinaru', name: '따릉이: 여의나루역 앞', type: 'bike', coords: [126.9328, 37.5271], lineInfo: '거치대 30대 (대여가능)', baseCrowd: 88, rainSensitivity: -3.0 },
  { id: 'bike-jamsil', name: '따릉이: 잠실역 8번출구', type: 'bike', coords: [127.1015, 37.5142], lineInfo: '거치대 25대 (대여가능)', baseCrowd: 70, rainSensitivity: -2.4 },
]

// 2호선 강남-잠실 구간 GeoJSON 경로 좌표
const SUBWAY_LINE_COORDS = [
  [127.0276, 37.4979], // 강남역
  [127.0365, 37.5006], // 역삼역
  [127.0460, 37.5042], // 선릉역
  [127.0631, 37.5088], // 삼성역
  [127.0737, 37.5109], // 종합운동장역
  [127.0863, 37.5116], // 잠실새내역
  [127.1002, 37.5133], // 잠실역
]

interface TransitMapProps {
  filterType: 'all' | 'subway' | 'bus' | 'bike'
  rainMm: number
  selectedTime: string
  focusedCoords?: [number, number] | null
  onSelectStop?: (stop: TransitStop) => void
  activeRoute?: TransitRouteResult | null
  onClearRoute?: () => void
}

interface MarkerItem {
  marker: any
  stop: TransitStop
  el: HTMLDivElement
  priority: number
}

export default function TransitMap({ filterType, rainMm, selectedTime, focusedCoords, onSelectStop, activeRoute, onClearRoute }: TransitMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<any>(null)
  const markerItemsRef = useRef<MarkerItem[]>([])
  const routeMarkersRef = useRef<any[]>([])
  const animFrameRef = useRef<number | null>(null)
  const [activeStop, setActiveStop] = useState<TransitStop | null>(null)
  const [mapLoaded, setMapLoaded] = useState(false)

  // 혼잡도 계산 헬퍼 (AI 시계열 예측 시뮬레이션: 비가 올수록 따릉이 급감, 지하철/버스 집중)
  const calculateCrowd = (stop: TransitStop) => {
    let crowd = stop.baseCrowd
    if (stop.type === 'bike') {
      // 비가 오면 자전거 이용 급격히 감소
      crowd = Math.max(5, Math.min(100, Math.round(crowd + stop.rainSensitivity * rainMm * 8)))
    } else {
      // 비가 오면 대중교통 이용 및 혼잡도 증가
      crowd = Math.max(10, Math.min(99, Math.round(crowd + (stop.rainSensitivity * rainMm * 2.5))))
    }
    return crowd
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
      // 2호선 경로 GeoJSON 레이어 추가
      map.addSource('subway-line-2', {
        type: 'geojson',
        data: {
          type: 'Feature',
          properties: { name: '지하철 2호선' },
          geometry: {
            type: 'LineString',
            coordinates: SUBWAY_LINE_COORDS,
          },
        },
      })

      // 외곽선 (글로우 효과)
      map.addLayer({
        id: 'subway-line-glow',
        type: 'line',
        source: 'subway-line-2',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: {
          'line-color': '#38BDF8',
          'line-width': 8,
          'line-opacity': 0.35,
        },
      })

      // 중심선
      map.addLayer({
        id: 'subway-line-core',
        type: 'line',
        source: 'subway-line-2',
        layout: { 'line-join': 'round', 'line-cap': 'round' },
        paint: {
          'line-color': '#38BDF8',
          'line-width': 4,
          'line-dasharray': [2, 1],
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

  // 역/정류소 중요도 가중치 계산 (환승역 및 주요 거점 역이 축소 시 우선 표시됨)
  const calculateStationPriority = (stop: TransitStop): number => {
    let score = 0
    if (stop.type === 'subway') score += 120
    else if (stop.type === 'bus') score += 50
    else score += 20

    const lineCount = stop.lineInfo ? stop.lineInfo.split(/[·,]/).length : 1
    score += lineCount * 30
    score += stop.baseCrowd * 0.2

    const majorHubs = [
      '서울역', '강남역', '신도림역', '구로역', '잠실역', '여의도역', '홍대입구역',
      '시청역', '고속터미널역', '왕십리역', '용산역', '청량리역', '수원역', '판교역',
      '사당역', '동대문역사문화공원역', '종로3가역', '가산디지털단지역', '교대역', '선릉역',
      '건대입구역', '신림역', '노원역', '영등포역'
    ]
    if (majorHubs.includes(stop.name)) {
      score += 200
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

    const placedBoxes: { x1: number; y1: number; x2: number; y2: number }[] = []

    // 줌 레벨에 따라 겹침 감지 박스 크기 동적 조절 (확대할수록 간격 좁아져 많은 역 등장)
    const halfW = currentZoom >= 16 ? 32 : (currentZoom >= 14 ? 44 : 54)
    const halfH = currentZoom >= 16 ? 12 : (currentZoom >= 14 ? 16 : 20)

    const hasActiveRoute = !!(activeRoute && activeRoute.path && activeRoute.path.length >= 2)
    const routeStationNames = hasActiveRoute ? new Set(activeRoute.path.map(p => p.name)) : null

    for (const item of markerItemsRef.current) {
      const [lng, lat] = item.stop.coords

      // 1. 활성 경로가 있는 경우: 경로에 포함된 역 이외의 모든 역/정류소는 완전히 숨김
      if (hasActiveRoute && routeStationNames) {
        if (!routeStationNames.has(item.stop.name)) {
          item.el.style.display = 'none'
          continue
        }
        // 출발역, 도착역, 환승역은 전용 핀 마커가 배치되므로 일반 알약 마커는 숨겨서 중복 방지
        const isSpecialPinStation = item.stop.name === activeRoute!.from || 
                                    item.stop.name === activeRoute!.to || 
                                    (activeRoute!.transferStations && activeRoute!.transferStations.includes(item.stop.name))
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

      // 4. 현재 검색되었거나 클릭하여 선택된 역, 또는 활성 경로 경유 역은 무조건 우선 표시!
      const isFocused = focusedCoords && Math.abs(lng - focusedCoords[0]) < 0.0002 && Math.abs(lat - focusedCoords[1]) < 0.0002
      const isSelected = activeStop && activeStop.id === item.stop.id
      const isOnRoute = hasActiveRoute && routeStationNames && routeStationNames.has(item.stop.name)
      const isTransferStation = hasActiveRoute && activeRoute?.transferStations?.includes(item.stop.name)

      if (isFocused || isSelected || isOnRoute) {
        item.el.style.display = 'flex'
        item.el.style.zIndex = isTransferStation ? '1500' : (isOnRoute ? '900' : '9999')

        const pill = item.el.querySelector('.marker-pill') as HTMLElement | null
        if (pill) {
          if (isTransferStation) {
            pill.style.borderColor = '#F59E0B'
            pill.style.boxShadow = '0 4px 18px rgba(245, 158, 11, 0.75)'
          } else {
            const crowd = calculateCrowd(item.stop)
            const { color } = getCrowdLevel(crowd)
            pill.style.borderColor = color
            pill.style.boxShadow = '0 4px 14px rgba(0,0,0,0.5)'
          }
        }

        placedBoxes.push({
          x1: pt.x - halfW,
          y1: pt.y - halfH,
          x2: pt.x + halfW,
          y2: pt.y + halfH,
        })
        continue
      }

      item.el.style.zIndex = '1'

      // 4. 고배율(Zoom >= 17)에서는 겹침 없이 모두 표시
      if (currentZoom >= 17) {
        item.el.style.display = 'flex'
        continue
      }

      // 5. 이미 배치된 상위 중요도 역과 겹치는지 충돌(Collision) 검사
      const x1 = pt.x - halfW
      const y1 = pt.y - halfH
      const x2 = pt.x + halfW
      const y2 = pt.y + halfH

      let overlaps = false
      for (const box of placedBoxes) {
        if (x1 < box.x2 && x2 > box.x1 && y1 < box.y2 && y2 > box.y1) {
          overlaps = true
          break
        }
      }

      // 겹치면 하나만 나오게 숨김, 여유가 생기면(확대 시) 표시
      if (overlaps) {
        item.el.style.display = 'none'
      } else {
        item.el.style.display = 'flex'
        placedBoxes.push({ x1, y1, x2, y2 })
      }
    }
  }

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
          <span style="
            background: ${color};
            color: #FFFFFF;
            font-size: 9px;
            font-weight: 800;
            padding: 1px 5px;
            border-radius: 6px;
            margin-left: 2px;
          ">${crowd}%</span>
        </div>
        <div style="
          width: 0; height: 0;
          border-left: 5px solid transparent;
          border-right: 5px solid transparent;
          border-top: 6px solid ${color};
        "></div>
      `

      // MapLibre Marker의 transform(translate 위치값)을 훼손하지 않도록 내부 뱃지(pill)에만 호버 확대 적용
      const pill = el.querySelector('.marker-pill') as HTMLElement | null
      if (pill) {
        el.addEventListener('mouseenter', () => {
          pill.style.transform = 'scale(1.1) translateY(-2px)'
          pill.style.boxShadow = `0 6px 20px ${color}88`
          el.style.zIndex = '1000'
        })
        el.addEventListener('mouseleave', () => {
          pill.style.transform = 'scale(1) translateY(0)'
          pill.style.boxShadow = '0 4px 14px rgba(0,0,0,0.5)'
          el.style.zIndex = '1'
        })
      }

      // 팝업 설정
      const popupHtml = `
        <div style="color: #1a202c; font-family: sans-serif; padding: 4px;">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 6px;">
            <strong style="font-size: 14px; color: #1e293b;">${typeIcon} ${stop.name}</strong>
            <span style="font-size: 10px; font-weight: 700; color: ${color}; background: #f1f5f9; padding: 2px 6px; border-radius: 4px;">${label} (${crowd}%)</span>
          </div>
          <div style="font-size: 12px; color: #64748b; margin-bottom: 6px;">${stop.lineInfo}</div>
          <div style="font-size: 11px; color: #475569; background: #f8fafc; padding: 6px 8px; border-radius: 6px; border-left: 3px solid ${color}; line-height: 1.4;">
            ${rainMm > 0 
              ? `🌧 강수(${rainMm}mm) 영향으로 ${stop.type === 'bike' ? '이용률 70% 이상 급감' : '평소 대비 승객 18% 증가 예상'}` 
              : '☀️ 맑은 날씨로 평시 출퇴근 패턴 유지'}
          </div>
        </div>
      `

      const popup = new maplibregl.Popup({ offset: 20 }).setHTML(popupHtml)

      const marker = new maplibregl.Marker({ element: el })
        .setLngLat(stop.coords)
        .setPopup(popup)
        .addTo(mapInstanceRef.current)

      el.addEventListener('click', () => {
        setActiveStop(stop)
        if (onSelectStop) onSelectStop(stop)

        // 브라우저 개발자 콘솔(F12)에 해당 거점의 실제 API 송수신 규격 데이터 출력
        if (stop.type === 'subway') {
          const cleanName = stop.name.replace(/역$/, '')
          fetch(`${API_BASE_URL}/api/v1/transit/subway/arrival?station=${encodeURIComponent(cleanName)}`)
            .then(res => res.json())
            .then(data => {
              if (data.status === 'success' && data.arrivals) {
                logSubwayApiCall(cleanName, data.arrivals, data)
              } else {
                logSubwayApiCall(cleanName, [
                  { trainLineNm: `${stop.name} 경유 - 성수/역삼 방면`, arvlMsg2: '전역 도착', barvlDt: '75', btrainSttus: '일반' },
                  { trainLineNm: `${stop.name} 경유 - 신사/신논현 방면`, arvlMsg2: '3분 후 (2번째 전역)', barvlDt: '180', btrainSttus: '일반' },
                ])
              }
            })
            .catch(() => {
              logSubwayApiCall(cleanName, [
                { trainLineNm: `${stop.name} 경유 - 성수/역삼 방면`, arvlMsg2: '전역 도착', barvlDt: '75', btrainSttus: '일반' },
                { trainLineNm: `${stop.name} 경유 - 신사/신논현 방면`, arvlMsg2: '3분 후 (2번째 전역)', barvlDt: '180', btrainSttus: '일반' },
              ])
            })
        } else if (stop.type === 'bus') {
          fetch(`${API_BASE_URL}/api/v1/transit/bus/arrival?stId=111000299`)
            .then(res => res.json())
            .then(data => {
              if (data.status === 'success' && data.arrivals) {
                logBusApiCall('100100118', '111000299', data.arrivals, data)
              } else {
                logBusApiCall('100100118', '111000299', [
                  { rtNm: '472', stNm: stop.name, arrmsg1: '2분45초후[1번째 전]', arrmsg2: '8분20초후[4번째 전]', reride_Num1: '보통' },
                  { rtNm: '140', stNm: stop.name, arrmsg1: '곧 도착', arrmsg2: '6분50초후[3번째 전]', reride_Num1: '여유' },
                ])
              }
            })
            .catch(() => {
              logBusApiCall('100100118', '111000299', [
                { rtNm: '472', stNm: stop.name, arrmsg1: '2분45초후[1번째 전]', arrmsg2: '8분20초후[4번째 전]', reride_Num1: '보통' },
                { rtNm: '140', stNm: stop.name, arrmsg1: '곧 도착', arrmsg2: '6분50초후[3번째 전]', reride_Num1: '여유' },
              ])
            })
        }

        // AI 추론 결과 로깅
        logAIPredictionCall(
          { stop: stop.name, type: stop.type, rainMm, hour: selectedTime },
          { predictedCrowd: `${crowd}%`, status: label, weatherEffect: rainMm > 0 ? `강수량 ${rainMm}mm로 인한 수요 변동 반영` : '맑음 (평시 패턴)' }
        )
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

    // 지도 조작(이동, 확대, 축소) 시 고속 겹침 재계산
    const onMapMove = () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
      animFrameRef.current = requestAnimationFrame(() => {
        updateCollisions()
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
      updateCollisions()
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
        setActiveStop(startStop)
        if (onSelectStop) onSelectStop(startStop)
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
            setActiveStop(trStop)
            if (onSelectStop) onSelectStop(trStop)
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
        setActiveStop(endStop)
        if (onSelectStop) onSelectStop(endStop)
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
  }, [activeRoute, mapLoaded])

  // focusedCoords 변경 시 부드럽게 해당 거점으로 카메라 이동 (flyTo)
  useEffect(() => {
    if (focusedCoords && mapInstanceRef.current) {
      mapInstanceRef.current.flyTo({
        center: focusedCoords,
        zoom: 15,
        pitch: 35,
        essential: true,
      })
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
                onClick={onClearRoute}
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

      {/* 실시간 날씨 및 시뮬레이션 상태 오버레이 */}
      <div style={{
        position: 'absolute',
        top: 16,
        right: 56, // 지도 컨트롤러 피해서 배치
        zIndex: 10,
        background: 'rgba(17, 29, 53, 0.92)',
        backdropFilter: 'blur(12px)',
        border: '1px solid rgba(56, 189, 248, 0.3)',
        borderRadius: 14,
        padding: '10px 14px',
        display: 'flex',
        alignItems: 'center',
        gap: 12,
        boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
      }}>
        <span style={{ fontSize: 24 }}>{rainMm > 0 ? '🌧' : '☀️'}</span>
        <div>
          <div style={{ fontSize: 12, fontWeight: 700, color: '#F0F6FF' }}>
            기준 시각: {selectedTime} | {rainMm > 0 ? `강수량 ${rainMm.toFixed(1)}mm/h` : '강수 없음 (맑음)'}
          </div>
          <div style={{ fontSize: 10, color: '#38BDF8', marginTop: 2 }}>
            OpenStreetMap 래스터 타일 + MapLibre GL 실시간 연동
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
        <span style={{ fontSize: 12 }}>{activeRoute ? '🧭' : '🔍'}</span>
        <span style={{ fontSize: 11, color: '#E2E8F0', fontWeight: 600 }}>
          {activeRoute
            ? `최소 환승 경로 집중 모드: ${activeRoute.transferCount === 0 ? '직통' : `${activeRoute.transferCount}회 환승`} 경로상의 역만 표시 중입니다 (닫기 클릭 시 전체 역 복원)`
            : '지도를 확대하면 겹쳤던 주변 세부 역이 자동으로 모두 표시됩니다'}
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
          수요/혼잡도 범례
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
            <div style={{ width: 16, height: 3, background: '#38BDF8', borderRadius: 2 }} />
            <span style={{ fontSize: 10, color: 'rgba(255,255,255,0.6)' }}>지하철 2호선 권역 경로</span>
          </div>
        </div>
      </div>
    </div>
  )
}
