/**
 * 공공 API 및 AI 예측 모델 통신 모니터링 로거
 * 브라우저 개발자 콘솔(F12 -> Console)에 컬러풀하고 구조화된 형태로 API 송수신 데이터를 출력합니다.
 */

// 1. 기상청 초단기실황 API 로깅
export function logWeatherApiCall(grid: { nx: number; ny: number }, weatherData: any) {
  console.groupCollapsed(
    '%c🌦️ [기상청 API허브] 초단기실황(getUltraSrtNcst) 연동 데이터',
    'background: #0284c7; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;'
  )
  console.log('%c[엔드포인트 URL]', 'color: #38bdf8; font-weight: bold;', 
    'https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtNcst')
  console.log('%c[Request Params]', 'color: #94a3b8; font-weight: bold;', {
    service: '초단기실황조회',
    authKey: 'KMA_APIHUB_KEY (보안 마스킹)',
    dataType: 'JSON',
    base_date: new Date().toISOString().slice(0, 10).replace(/-/g, ''),
    base_time: `${new Date().getHours().toString().padStart(2, '0')}00`,
    nx: grid.nx,
    ny: grid.ny,
  })
  console.log('%c[Response Data - 기상 관측 Feature]', 'color: #34d399; font-weight: bold;', {
    기온_T1H: `${weatherData.temp}°C`,
    강수량_RN1: `${weatherData.rain}mm/h`,
    강수형태_PTY: weatherData.rain > 0 ? '1 (비)' : '0 (없음/맑음)',
    습도_REH: `${weatherData.humidity}%`,
    풍속_WSD: `${weatherData.wind}m/s`,
  })
  console.groupEnd()
}

// 2. 서울시 버스도착정보조회 API 로깅
export function logBusApiCall(routeId: string, stId: string, arrivalData: any) {
  console.groupCollapsed(
    '%c🚌 [공공데이터포털] 서울특별시_버스도착정보조회(getArrInfoByRouteAll / getLowArrInfoByStId)',
    'background: #ea580c; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;'
  )
  console.log('%c[엔드포인트 URL]', 'color: #fb923c; font-weight: bold;', 
    'http://ws.bus.go.kr/api/rest/arrive/getArrInfoByRouteAll')
  console.log('%c[Request Params]', 'color: #94a3b8; font-weight: bold;', {
    serviceKey: 'DATA_GO_KR_API_KEY (unquote 디코딩 적용)',
    resultType: 'json',
    busRouteId: routeId,
    stId: stId,
  })
  console.log('%c[Response Data - 실시간 버스 도착 현황]', 'color: #34d399; font-weight: bold;', arrivalData)
  console.groupEnd()
}

// 3. 서울시 지하철 실시간 도착정보 API 로깅
export function logSubwayApiCall(stationName: string, arrivalList: any) {
  console.groupCollapsed(
    '%c🚇 [서울 열린데이터광장] 지하철 실시간 도착정보(realtimeStationArrival)',
    'background: #2563eb; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold;'
  )
  console.log('%c[엔드포인트 URL]', 'color: #60a5fa; font-weight: bold;', 
    `http://swopenAPI.seoul.go.kr/api/subway/{KEY}/json/realtimeStationArrival/0/5/${encodeURIComponent(stationName)}`)
  console.log('%c[Request Params]', 'color: #94a3b8; font-weight: bold;', {
    KEY: 'SEOUL_SUBWAY_API_KEY',
    TYPE: 'json',
    SERVICE: 'realtimeStationArrival',
    START_INDEX: 0,
    END_INDEX: 5,
    statnNm: stationName,
  })
  console.log('%c[Response Data - 열린데이터 실시간 도착 리스트]', 'color: #34d399; font-weight: bold;', arrivalList)
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
