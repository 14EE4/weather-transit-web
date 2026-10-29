/**
 * 공공 API 및 AI 예측 모델 통신 모니터링 로거
 * 브라우저 개발자 콘솔(F12 -> Console)에 컬러풀하고 구조화된 형태로 API 송수신 및 디버깅 데이터를 출력합니다.
 */

// 동일한 이벤트가 1초 내에 중복 호출되는 것을 방지하는 캐시 (디버깅용으로 300ms로 완화)
const recentLogs = new Map<string, number>()
const DEDUPE_WINDOW_MS = 300

function shouldLog(key: string): boolean {
  const now = Date.now()
  const last = recentLogs.get(key)
  if (last && now - last < DEDUPE_WINDOW_MS) {
    return false
  }
  recentLogs.set(key, now)
  if (recentLogs.size > 100) {
    for (const [k, time] of recentLogs) {
      if (now - time > 10000) recentLogs.delete(k)
    }
  }
  return true
}

// 1. 기상청 초단기실황 API 로깅
export function logWeatherApiCall(grid: { nx: number; ny: number }, weatherData: any, rawPayload?: any) {
  const key = `weather_${grid.nx}_${grid.ny}_${weatherData?.district || ''}_${weatherData?.temp}_${weatherData?.rain}`
  if (!shouldLog(key)) return

  console.groupCollapsed(
    `%c🌦️ [기상청 API허브] 실시간 초단기실황(getUltraSrtNcst): ${weatherData.district || '서울'} (${weatherData.temp ?? '--'}°C, 강수 ${weatherData.rain ?? 0}mm/h, 격자: ${grid.nx}, ${grid.ny})`,
    'background: #0284c7; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;'
  )
  console.log('%c[실제 엔드포인트 URL]', 'color: #38bdf8; font-weight: bold;', 
    'https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtNcst')
  console.log('%c[Backend Proxy API]', 'color: #38bdf8;', `/api/v1/weather/current?district=${encodeURIComponent(weatherData.district || '강남구')}`)
  console.log('%c[Request Params]', 'color: #94a3b8; font-weight: bold;', {
    service: '기상청 초단기실황조회 (VilageFcstInfoService_2.0)',
    authKey: 'KMA_APIHUB_KEY (인증 완료)',
    dataType: 'JSON',
    base_date: weatherData.base_date || new Date().toISOString().slice(0, 10).replace(/-/g, ''),
    base_time: weatherData.base_time || `${new Date().getHours().toString().padStart(2, '0')}00`,
    nx: grid.nx,
    ny: grid.ny,
  })
  console.log('%c[Live Response Data - 실시간 기상 관측치]', 'color: #34d399; font-weight: bold;', {
    지역명: weatherData.district,
    기온_T1H: `${weatherData.temp}°C`,
    강수량_RN1: `${weatherData.rain}mm/h`,
    강수형태_PTY: `${weatherData.pty_desc || (weatherData.rain > 0 ? '1 (비)' : '0 (맑음)')}`,
    습도_REH: `${weatherData.humidity}%`,
    풍속_WSD: `${weatherData.wind}m/s`,
    발표시각: `${weatherData.base_date} ${weatherData.base_time}`,
    데이터_출처: weatherData.source || 'KMA_APIHUB_LIVE'
  })
  if (rawPayload) {
    console.log('%c[원천 응답 페이로드 (Raw JSON)]', 'color: #a7f3d0;', rawPayload)
  }
  console.groupEnd()
}

// 2. 서울시 버스도착정보조회 API 로깅
export function logBusApiCall(routeId: string, stId: string, arrivalData: any, rawPayload?: any) {
  const key = `bus_${stId}`
  if (!shouldLog(key)) return

  console.groupCollapsed(
    `%c🚌 [공공데이터포털] 실시간 서울시 버스도착정보 (정류소: ${stId})`,
    'background: #ea580c; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;'
  )
  console.log('%c[실제 엔드포인트 URL]', 'color: #fb923c; font-weight: bold;', 
    'http://ws.bus.go.kr/api/rest/arrive/getLowArrInfoByStId')
  console.log('%c[Backend Proxy API]', 'color: #fb923c;', `/api/v1/transit/bus/arrival?stId=${stId}`)
  console.log('%c[Live Response Data - 실시간 버스 도착 현황]', 'color: #34d399; font-weight: bold;', arrivalData)
  if (rawPayload) {
    console.log('%c[원천 응답 페이로드 (Raw JSON)]', 'color: #fdba74;', rawPayload)
  }
  console.groupEnd()
}

// 3. 서울시 지하철 실시간 도착정보 API 로깅
export function logSubwayApiCall(stationName: string, arrivalList: any, rawPayload?: any) {
  const key = `subway_${stationName}`
  if (!shouldLog(key)) return

  console.groupCollapsed(
    `%c🚇 [서울 열린데이터광장] 실시간 지하철 도착정보 (${stationName}역)`,
    'background: #2563eb; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;'
  )
  console.log('%c[실제 엔드포인트 URL]', 'color: #60a5fa; font-weight: bold;', 
    `http://swopenAPI.seoul.go.kr/api/subway/{SEOUL_SUBWAY_API_KEY}/json/realtimeStationArrival/0/8/${encodeURIComponent(stationName)}`)
  console.log('%c[Backend Proxy API]', 'color: #60a5fa;', `/api/v1/transit/subway/arrival?station=${encodeURIComponent(stationName)}`)
  console.log('%c[Live Response Data - 실시간 열차 도착 리스트]', 'color: #34d399; font-weight: bold;', arrivalList)
  if (rawPayload) {
    console.log('%c[원천 응답 페이로드 (Raw JSON)]', 'color: #93c5fd;', rawPayload)
  }
  console.groupEnd()
}

// 4. AI 수요 예측 머신러닝 모델 추론 로깅
export function logAIPredictionCall(inputFeatures: any, predictionResults: any) {
  const targetName = inputFeatures.station || inputFeatures.district || inputFeatures.location || '서울'
  const key = `ai_${targetName}_${inputFeatures.hour}_${inputFeatures.temp}_${inputFeatures.rain}`
  if (!shouldLog(key)) return

  const corridorText = predictionResults?.corridor_district ? ` (광역 진입축: ${predictionResults.corridor_district})` : ''
  console.groupCollapsed(
    `%c⚡ [AI 머신러닝 엔진] 기상 및 시간대별 대중교통 이용 수요 추론: ${targetName}${corridorText}`,
    'background: #7c3aed; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;'
  )
  console.log('%c[Backend Proxy API]', 'color: #c084fc;', '/api/v1/predict/recommendation')
  console.log('%c[Model Input Features (32차원 투입 피처)]', 'color: #c084fc; font-weight: bold;', inputFeatures)
  console.log('%c[Model Output Predictions (수단별 추천 점수, 혼잡도 %, 예측량)]', 'color: #34d399; font-weight: bold;', predictionResults)
  console.groupEnd()
}

// 5. 서울시 주요 거점 및 동별 실시간 교통 혼잡도 ONNX 추론 로깅
export function logDistrictCongestionCall(params: { rain: number; temp: number; hour: number }, data: any) {
  const key = `congestion_${params.rain}_${params.temp}_${params.hour}`
  if (!shouldLog(key)) return

  const hotspotCount = data?.hotspots?.length ?? 0
  console.groupCollapsed(
    `%c📊 [AI 머신러닝 엔진] 주요 거점 및 동별 실시간 교통 혼잡도 추론: ${hotspotCount}개소 (${params.hour}시, ${params.temp}°C, 강수 ${params.rain}mm, latency: ${data?.latency_ms ?? 0}ms)`,
    'background: #4f46e5; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;'
  )
  console.log('%c[Backend Proxy API]', 'color: #818cf8;', `/api/v1/districts/live-congestion?rain=${params.rain}&temp=${params.temp}&hour=${params.hour}`)
  console.log('%c[32차원 ONNX 배치 추론 결과 (거점별 실시간 혼잡도)]', 'color: #34d399; font-weight: bold;',
    (data?.hotspots || []).map((h: any) => ({
      거점명: h.name,
      자치구: h.district,
      버스_혼잡도: `${h.bus}%`,
      지하철_혼잡도: `${h.subway}%`,
      따릉이_혼잡도: `${h.bike}%`,
      날씨: `${h.weather} (${h.condition})`
    }))
  )
  console.log('%c[원천 응답 페이로드 (Raw JSON)]', 'color: #a5b4fc;', data)
  console.groupEnd()
}

// 6. 24시간 시계열 AI 대중교통 예측 로깅
export function logHourlyForecastCall(params: { district: string; rain: number; temp: number }, data: any) {
  const key = `hourly_${params.district}_${params.rain}_${params.temp}`
  if (!shouldLog(key)) return

  const count = (data?.forecast || data?.hourly || []).length
  console.groupCollapsed(
    `%c📈 [AI 머신러닝 엔진] 24시간 시간대별 시계열 대중교통 예측: ${params.district} (${count}개 시간대, ${params.temp}°C, 강수 ${params.rain}mm)`,
    'background: #0d9488; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;'
  )
  console.log('%c[Backend Proxy API]', 'color: #2dd4bf;', `/api/v1/transit/hourly-forecast?district=${encodeURIComponent(params.district)}&rain=${params.rain}&temp=${params.temp}`)
  console.log('%c[24시간 예측 데이터]', 'color: #34d399; font-weight: bold;', data)
  console.groupEnd()
}

// 7. 서울시 따릉이 실시간 대여정보(bikeList) API 로깅
export function logBikeApiCall(
  info: {
    stationNo?: string
    stationName: string
    method: 'by-number' | 'nearest-200m' | 'estimated'
    proxyPath: string
  },
  liveStation: any | null,
  rawPayload?: any
) {
  const key = `bike_${info.stationNo || info.stationName}`
  if (!shouldLog(key)) return

  const live = !!liveStation
  console.groupCollapsed(
    `%c🚲 [서울 열린데이터광장] 따릉이 실시간 대여정보(bikeList): ${info.stationName} ${live ? `(${liveStation.availableBikes}대 / 거치대 ${liveStation.rackTotal}개)` : '(실시간 조회 실패 → 추정값)'}`,
    `background: ${live ? '#059669' : '#b45309'}; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;`
  )
  console.log('%c[실제 엔드포인트 URL]', 'color: #34d399; font-weight: bold;',
    'http://openapi.seoul.go.kr:8088/{SEOUL_DATA_API_KEY}/json/bikeList/{start}/{end}/')
  console.log('%c[Backend Proxy API]', 'color: #34d399;', info.proxyPath)
  console.log('%c[조회 방식]', 'color: #94a3b8; font-weight: bold;', {
    방식: info.method === 'by-number' ? '대여소 번호 정확 일치' : info.method === 'nearest-200m' ? '좌표 기준 200m 이내 최근접 대여소' : '실시간 값 없음 (혼잡도 기반 추정)',
    대여소번호: info.stationNo || '-'
  })
  if (live) {
    console.log('%c[Live Response Data - 실시간 대여소 현황]', 'color: #34d399; font-weight: bold;', {
      대여소명: liveStation.name,
      대여가능_자전거: `${liveStation.availableBikes}대`,
      거치대_수: `${liveStation.rackTotal}개`,
      거치율_shared: `${liveStation.shared}%`,
      데이터_출처: rawPayload?.source || 'SEOUL_BIKE_LIVE'
    })
  }
  if (rawPayload) {
    console.log('%c[원천 응답 페이로드 (Raw JSON)]', 'color: #6ee7b7;', rawPayload)
  }
  console.groupEnd()
}

// 8. 따릉이 주변 대여소 일괄 조회(지도 이동) 로깅
export function logBikeNearbyCall(params: { lat: number; lng: number; radius: number }, data: any) {
  const key = `bike_nearby_${params.lat.toFixed(4)}_${params.lng.toFixed(4)}`
  if (!shouldLog(key)) return

  console.groupCollapsed(
    `%c🚲 [서울 열린데이터광장] 따릉이 주변 대여소 조회: ${data?.count ?? 0}곳 (반경 ${params.radius}m, ${data?.source || '-'})`,
    'background: #059669; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;'
  )
  console.log('%c[Backend Proxy API]', 'color: #34d399;', `/api/v1/transit/bike/stations/nearby?lat=${params.lat}&lng=${params.lng}&radius=${params.radius}`)
  console.log('%c[Live Response Data - 주변 대여소 (잔여 자전거/거치대)]', 'color: #34d399; font-weight: bold;',
    (data?.stations || []).map((s: any) => ({ 대여소: s.name, 잔여: s.availableBikes, 거치대: s.rackTotal, 거리m: s.distance })))
  console.log('%c[원천 응답 페이로드 (Raw JSON)]', 'color: #6ee7b7;', data)
  console.groupEnd()
}
