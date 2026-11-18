import { SUBWAY_STATIONS } from '../subwayData'

/** 대한민국 영역 경계 (전 세계 타일 로딩 방지 및 한국 영토 내 이동 제한) */
export const KOREA_BOUNDS: [[number, number], [number, number]] = [
  [124.0, 32.8],
  [132.0, 39.2],
]

/** 두 위경도 좌표 간 Haversine 거리 계산 (미터 단위) */
export function getDistanceFromLatLonInMeters(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const R = 6371e3
  const phi1 = (lat1 * Math.PI) / 180
  const phi2 = (lat2 * Math.PI) / 180
  const deltaPhi = ((lat2 - lat1) * Math.PI) / 180
  const deltaLambda = ((lon2 - lon1) * Math.PI) / 180

  const a =
    Math.sin(deltaPhi / 2) * Math.sin(deltaPhi / 2) +
    Math.cos(phi1) * Math.cos(phi2) * Math.sin(deltaLambda / 2) * Math.sin(deltaLambda / 2)
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return Math.round(R * c)
}

/** 좌표 기준 가장 가까운 수도권 지하철역 검색 */
export function getNearestSubwayStation(
  coords: [number, number]
): { name: string; distanceMeters: number; lines: string[] } | null {
  if (!coords || !SUBWAY_STATIONS || SUBWAY_STATIONS.length === 0) return null
  let nearest: { name: string; distanceMeters: number; lines: string[] } | null = null
  let minDistance = Infinity

  for (const s of SUBWAY_STATIONS) {
    const dist = getDistanceFromLatLonInMeters(coords[1], coords[0], s.coords[1], s.coords[0])
    if (dist < minDistance) {
      minDistance = dist
      nearest = { name: s.name, distanceMeters: dist, lines: s.lines || [] }
    }
  }
  return nearest
}

/** 데스크톱(PC) 브라우저 환경 판별 (터치/모바일 UA 배제) */
export function isDesktopDevice(): boolean {
  if (typeof window === 'undefined') return true
  const isTouch = 'ontouchstart' in window || (navigator.maxTouchPoints && navigator.maxTouchPoints > 0)
  const isMobileUa = /Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent)
  return !isTouch && !isMobileUa
}

/** GPS 오차 반경 원형 GeoJSON 폴리곤 생성 헬퍼 */
export function createGeoJsonCircle(center: [number, number], radiusInMeters: number, points = 64) {
  const [lng, lat] = center
  const coords: [number, number][] = []
  const km = Math.max(0.005, radiusInMeters / 1000)
  const distanceX = km / (111.32 * Math.cos((lat * Math.PI) / 180))
  const distanceY = km / 110.574

  for (let i = 0; i < points; i++) {
    const theta = (i / points) * (2 * Math.PI)
    const x = distanceX * Math.cos(theta)
    const y = distanceY * Math.sin(theta)
    coords.push([lng + x, lat + y])
  }
  coords.push(coords[0])

  return {
    type: 'Feature' as const,
    geometry: {
      type: 'Polygon' as const,
      coordinates: [coords],
    },
    properties: {},
  }
}
