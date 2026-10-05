/**
 * 공공 API 및 AI 예측 모델 통신 모니터링 로거
 * 브라우저 개발자 콘솔(F12 -> Console)에 컬러풀하고 구조화된 형태로 API 송수신 데이터를 출력합니다.
 */

// 1. 기상청 초단기실황 API 로깅
export function logWeatherApiCall(grid: { nx: number; ny: number }, weatherData: any, rawPayload?: any) {
  console.groupCollapsed(
    `%c🌦️ [기상청 API허브] 실시간 초단기실황(getUltraSrtNcst) 연동: ${weatherData.district || '서울'} (${weatherData.temp ?? '--'}°C, 격자: ${grid.nx}, ${grid.ny})`,
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
    기온_T1H: `${weatherData.temp}°C`,
    강수량_RN1: `${weatherData.rain}mm/h`,
    강수형태_PTY: `${weatherData.pty_desc || (weatherData.rain > 0 ? '1 (비)' : '0 (맑음)')}`,
    습도_REH: `${weatherData.humidity}%`,
    풍속_WSD: `${weatherData.wind}m/s`,
    데이터_출처: weatherData.source || 'KMA_APIHUB_LIVE'
  })
  if (rawPayload) {
    console.log('%c[원천 응답 페이로드 (Raw JSON)]', 'color: #a7f3d0;', rawPayload)
  }
  console.groupEnd()
}

// 2. 서울시 버스도착정보조회 API 로깅
export function logBusApiCall(routeId: string, stId: string, arrivalData: any, rawPayload?: any) {
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
  console.groupCollapsed(
    '%c⚡ [AI 머신러닝 엔진] 기상 및 시간대별 대중교통 이용 수요 추론 (Inference)',
    'background: #7c3aed; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;'
  )
  console.log('%c[Model Input Features (입력 변수)]', 'color: #c084fc; font-weight: bold;', inputFeatures)
  console.log('%c[Model Output Predictions (예측 혼잡도 및 수단별 전환율)]', 'color: #34d399; font-weight: bold;', predictionResults)
  console.groupEnd()
}
