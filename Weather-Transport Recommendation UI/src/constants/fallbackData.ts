/**
 * @file fallbackData.ts
 * @description 네트워크 지연 또는 백엔드 API 장애 시에만 제한적으로 사용되는 정적 폴백 상수 모듈
 * (App.tsx 및 AppM.tsx에서 분리 격리하여 초기 렌더링 시 하드코딩 노출을 방지하고 스켈레톤 UI와 연동)
 */

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

export interface TransportScoreItem {
  id: string
  icon: string
  name: string
  score: number
  scoreLabel: string
  scoreColor: string
  reasons: string[]
  time: string
  price: string
  crowd: number
  crowdLabel: string
  crowdColor: string
  dataset: string
  predicted_volume?: number
}

export interface DistrictCongestionItem {
  name: string
  bus: number
  subway: number
  bike: number
  weather: string
  temp: number
}

export interface RainCorrelationItem {
  rain: number
  subway: number
  bus: number
  bike: number
  note: string
}

// ── 24시간 시간대별(00시~23시) 날씨 + 교통 통합 기본 데이터 ──
export const DEFAULT_24H_DATA: HourlyTransitData[] = Array.from({ length: 24 }, (_, h) => {
  const isPeak = (h >= 8 && h <= 9) || (h >= 17 && h <= 18)
  const isNight = h < 6 || h >= 23
  const subMult = isPeak ? 1.25 : (isNight ? 0.35 : 0.8)
  const busMult = isPeak ? 1.2 : (isNight ? 0.25 : 0.75)
  const bikeMult = isPeak ? 1.1 : (isNight ? 0.15 : 0.7)
  return {
    hour: `${String(h).padStart(2, '0')}시`,
    hour_num: h,
    temp: Math.round((16.0 + 3.5 * Math.sin(((h - 8) * Math.PI) / 12)) * 10) / 10,
    rain: 0,
    humidity: 60,
    wind: 2.0,
    subway: Math.round(45000 * subMult),
    bus: Math.round(18000 * busMult),
    bike: Math.round(350 * bikeMult),
    subway_crowd: Math.round(55 * subMult),
    bus_crowd: Math.round(50 * busMult),
    bike_crowd: Math.round(45 * bikeMult),
    is_peak: isPeak,
  }
})

// ── 교통수단 추천 기본 스코어 (폴백 전용) ──
export const FALLBACK_TRANSPORT_SCORES: TransportScoreItem[] = [
  {
    id: 'subway',
    icon: '🚇',
    name: '지하철',
    score: 95,
    scoreLabel: '추천',
    scoreColor: '#38BDF8',
    reasons: ['실시간 데이터 수신 대기 중', '정시성 우수', '배차 간격 2~5분'],
    time: '28분',
    price: '1,550원',
    crowd: 50,
    crowdLabel: '보통',
    crowdColor: '#34D399',
    dataset: '지하철 호선별 역별 시간대별 승하차',
  },
  {
    id: 'bus',
    icon: '🚌',
    name: '버스',
    score: 70,
    scoreLabel: '보통',
    scoreColor: '#FB923C',
    reasons: ['실시간 데이터 수신 대기 중', '승객 분산 효과', '노선 다양'],
    time: '40분',
    price: '1,300원',
    crowd: 65,
    crowdLabel: '보통',
    crowdColor: '#FB923C',
    dataset: '버스노선별 정류장별 시간대별 승하차',
  },
  {
    id: 'bike',
    icon: '🚲',
    name: '따릉이',
    score: 30,
    scoreLabel: '참고',
    scoreColor: '#94A3B8',
    reasons: ['실시간 데이터 수신 대기 중', '단거리 이동 적합', '기상 확인 필요'],
    time: '50분',
    price: '1,000원/시간',
    crowd: 15,
    crowdLabel: '여유',
    crowdColor: '#94A3B8',
    dataset: '공공자전거 따릉이 대여이력',
  },
]

// ── 강우량-이용객 상관관계 데이터 (서울시 교통·기상 실측 빅데이터 캘리브레이션) ──
export const CORRELATION_DATA: RainCorrelationItem[] = [
  { rain: 0, subway: 82, bus: 76, bike: 100, note: '맑음: 따릉이 최우선 추천 (기준 100%)' },
  { rain: 0.5, subway: 88, bus: 72, bike: 27.2, note: '소우(0.5mm): 따릉이 실측 -72.8% 급감 이탈' },
  { rain: 1.0, subway: 93, bus: 65, bike: 18.9, note: '약한 비(1mm): 지하철 우천 집중 가속' },
  { rain: 2.0, subway: 97, bus: 56, bike: 16.0, note: '보통 비(2mm): 버스 노면 감속 지연 심화' },
  { rain: 3.0, subway: 100, bus: 48, bike: 13.8, note: '강한 비(3mm): 지하철 정시성(99.2%) 정점' },
  { rain: 5.0, subway: 98, bus: 36, bike: 9.4, note: '호우(5mm): 자전거 안전 한계(운행 중단권)' },
]

// ── 권역별 주요 거점 교통 혼잡 현황 기본값 (폴백 전용) ──
export const FALLBACK_DISTRICT_DATA: DistrictCongestionItem[] = [
  { name: '강남 역삼동', bus: 82, subway: 91, bike: 45, weather: '☀️', temp: 18 },
  { name: '도심 명동', bus: 92, subway: 85, bike: 18, weather: '☀️', temp: 18 },
  { name: '여의도동', bus: 88, subway: 72, bike: 24, weather: '☀️', temp: 18 },
  { name: '홍대 서교동', bus: 71, subway: 63, bike: 88, weather: '☀️', temp: 18 },
  { name: '성수동 카페거리', bus: 68, subway: 84, bike: 52, weather: '☀️', temp: 18 },
  { name: '가산디지털단지', bus: 79, subway: 88, bike: 30, weather: '☀️', temp: 18 },
  { name: '잠실 롯데월드', bus: 55, subway: 94, bike: 31, weather: '☀️', temp: 18 },
  { name: '판교 테크노밸리', bus: 74, subway: 86, bike: 42, weather: '☀️', temp: 18 },
]

