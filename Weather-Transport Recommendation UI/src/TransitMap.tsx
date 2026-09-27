import { useEffect, useRef, useState } from 'react'
import { logBusApiCall, logSubwayApiCall, logAIPredictionCall } from './apiLogger'
import { SUBWAY_STATIONS } from './subwayData'

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
}

export default function TransitMap({ filterType, rainMm, selectedTime, focusedCoords, onSelectStop }: TransitMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null)
  const mapInstanceRef = useRef<any>(null)
  const markersRef = useRef<any[]>([])
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

  // 2. 필터링 및 날씨에 따른 마커 동적 갱신
  useEffect(() => {
    if (!mapLoaded || !mapInstanceRef.current) return

    // 이전 마커 제거
    markersRef.current.forEach(m => m.remove())
    markersRef.current = []

    const filtered = filterType === 'all'
      ? TRANSIT_STOPS
      : TRANSIT_STOPS.filter(s => s.type === filterType)

    filtered.forEach(stop => {
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
        <div style="
          background: #111D35;
          border: 2px solid ${color};
          border-radius: 9999px;
          padding: 3px 8px;
          box-shadow: 0 4px 14px rgba(0,0,0,0.5);
          display: flex;
          align-items: center;
          gap: 4px;
          transition: transform 0.2s ease;
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

      el.addEventListener('mouseenter', () => {
        el.style.transform = 'scale(1.12) translateY(-2px)'
      })
      el.addEventListener('mouseleave', () => {
        el.style.transform = 'scale(1) translateY(0)'
      })

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
          logSubwayApiCall(stop.name.replace('역', ''), [
            { trainLineNm: `${stop.name} 경유 - 성수/역삼 방면`, arvlMsg2: '전역 도착', barvlDt: '75', btrainSttus: '일반' },
            { trainLineNm: `${stop.name} 경유 - 신사/신논현 방면`, arvlMsg2: '3분 후 (2번째 전역)', barvlDt: '180', btrainSttus: '일반' },
          ])
        } else if (stop.type === 'bus') {
          logBusApiCall('100100118', '111000299', [
            { rtNm: '472', stNm: stop.name, arrmsg1: '2분45초후[1번째 전]', arrmsg2: '8분20초후[4번째 전]', reride_Num1: '보통' },
            { rtNm: '140', stNm: stop.name, arrmsg1: '곧 도착', arrmsg2: '6분50초후[3번째 전]', reride_Num1: '여유' },
          ])
        }

        // AI 추론 결과 로깅
        logAIPredictionCall(
          { stop: stop.name, type: stop.type, rainMm, hour: selectedTime },
          { predictedCrowd: `${crowd}%`, status: label, weatherEffect: rainMm > 0 ? `강수량 ${rainMm}mm로 인한 수요 변동 반영` : '맑음 (평시 패턴)' }
        )
      })

      markersRef.current.push(marker)
    })
  }, [filterType, rainMm, mapLoaded, selectedTime])

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
