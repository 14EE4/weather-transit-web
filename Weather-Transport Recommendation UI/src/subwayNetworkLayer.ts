// 수도권 전철 전체 노선망 배경 벡터(GeoJSON Polyline) 생성 모듈
import { SUBWAY_STATIONS, SubwayStation } from './subwayData'
import { SUBWAY_GRAPH } from './subwayGraph'

// ── 수도권 전철 공식 노선별 색상 코드 (서울교통공사 및 한국철도공사 표준) ──
export const SUBWAY_LINE_COLORS: Record<string, string> = {
  '1호선': '#0052A4',
  '2호선': '#00A84D',
  '3호선': '#EF7C1C',
  '4호선': '#00A5DE',
  '5호선': '#996CAC',
  '6호선': '#CD7C2F',
  '7호선': '#747F00',
  '8호선': '#E6186C',
  '9호선': '#BDB092',
  '수인분당선': '#F5A200',
  '신분당선': '#D4003B',
  '공항철도': '#0090D2',
  '경의중앙선': '#77C4A3',
  '경춘선': '#0C8E72',
  '서해선': '#81A914',
  '신림선': '#6789CA',
  '우이신설선': '#B7C452',
  '김포골드라인': '#AD8605',
  'GTX-A': '#9A6292',
  '인천1호선': '#7CA8D5',
  '인천2호선': '#ED8B00',
  '에버라인': '#56AD2D',
  '의정부경전철': '#FDA600',
  '경강선': '#0054A6',
}

/**
 * SUBWAY_GRAPH 인접 리스트와 SUBWAY_STATIONS 좌표 데이터를 결합하여
 * MapLibre GL 렌더링용 수도권 전철 전체 노선망 GeoJSON FeatureCollection을 생성합니다.
 */
export function buildSubwayNetworkGeoJSON(): any {
  const stationMap = new Map<string, SubwayStation>()
  SUBWAY_STATIONS.forEach(s => {
    stationMap.set(s.name, s)
  })

  const features: any[] = []
  const visitedEdges = new Set<string>()

  for (const [stName, neighbors] of Object.entries(SUBWAY_GRAPH)) {
    const stA = stationMap.get(stName)
    if (!stA) continue

    for (const neighborName of neighbors) {
      const stB = stationMap.get(neighborName)
      if (!stB) continue

      // 무방향 그래프이므로 엣지 중복 방지 (A-B 순서 정렬)
      const edgeKey = [stName, neighborName].sort().join('___')
      if (visitedEdges.has(edgeKey)) continue
      visitedEdges.add(edgeKey)

      // 두 역 간 공통 노선 찾기
      const commonLines = stA.lines.filter(l => stB.lines.includes(l))
      const targetLines = commonLines.length > 0 ? commonLines : [stA.lines[0] || '1호선']

      for (const line of targetLines) {
        const color = SUBWAY_LINE_COLORS[line] || '#4B5563'
        features.push({
          type: 'Feature',
          properties: {
            line,
            color,
            from: stName,
            to: neighborName,
          },
          geometry: {
            type: 'LineString',
            coordinates: [stA.coords, stB.coords],
          },
        })
      }
    }
  }

  return {
    type: 'FeatureCollection',
    features,
  }
}

// 런타임 메모이제이션 (싱글톤)
export const SUBWAY_NETWORK_GEOJSON = buildSubwayNetworkGeoJSON()

