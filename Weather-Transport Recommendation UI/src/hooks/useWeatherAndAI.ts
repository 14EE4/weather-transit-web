import { useEffect, useRef, useState } from 'react'
import { API_BASE_URL } from '../api/client'
import {
  logAIPredictionCall,
  logDistrictCongestionCall,
  logHourlyForecastCall,
  logWeatherApiCall,
} from '../apiLogger'
import { DISTRICTS } from '../constants/districts'
import {
  DEFAULT_24H_DATA,
  FALLBACK_DISTRICT_DATA as DISTRICT_DATA,
  FALLBACK_TRANSPORT_SCORES as TRANSPORT_SCORES,
  type HourlyTransitData,
} from '../constants/fallbackData'
import { resolveDistrict } from '../districtResolver'

export interface LiveWeatherData {
  status: string
  district: string
  nx: number
  ny: number
  base_date: string
  base_time: string
  temp: number
  rain: number
  pty: string
  pty_desc: string
  humidity: number
  wind: number
  source: string
}

export type TransportScoreViewItem = (typeof TRANSPORT_SCORES)[number] & {
  predicted_volume?: number
}

export interface DistrictHotspotItem {
  name: string
  district?: string
  bus: number
  subway: number
  bike: number
  weather: string
  temp: number
  rain?: number
}

export function useWeatherAndAI(selectedDistrict: number) {
  const [liveWeather, setLiveWeather] = useState<LiveWeatherData | null>(null)
  const [viewportWeather, setViewportWeather] = useState<LiveWeatherData | null>(null)
  const [viewportDistrict, setViewportDistrict] = useState<string | null>(null)
  const viewportWeatherKeyRef = useRef<string>('')
  const nowHour = new Date().getHours()
  const [selectedHour, setSelectedHour] = useState<number>(nowHour)

  const [transportScores, setTransportScores] = useState<TransportScoreViewItem[]>(TRANSPORT_SCORES)
  const [aiLatency, setAiLatency] = useState<number | null>(null)
  const [aiStatus, setAiStatus] = useState<'connected' | 'loading' | 'offline'>('loading')
  const [aiWeatherSummary, setAiWeatherSummary] = useState<{
    condition: string
    description: string
  } | null>(null)

  const [districtList, setDistrictList] = useState<DistrictHotspotItem[]>(DISTRICT_DATA)
  const [districtLiveStatus, setDistrictLiveStatus] = useState<'idle' | 'loading' | 'live'>('idle')
  const lastDistrictCongestionKeyRef = useRef<string>('')

  const [hourlyForecast, setHourlyForecast] = useState<HourlyTransitData[]>(DEFAULT_24H_DATA)
  const [hourlyLiveStatus, setHourlyLiveStatus] = useState<'idle' | 'loading' | 'live'>('idle')
  const [hourlyHovered, setHourlyHovered] = useState<number | null>(null)
  const lastHourlyForecastKeyRef = useRef<string>('')

  const lastFetchedDistrictRef = useRef<number | null>(null)
  const lastAIFetchKeyRef = useRef<string>('')

  // 선택된 자치구의 기상청 실시간 초단기실황 데이터 자동 동기화
  useEffect(() => {
    let isMounted = true
    const districtName = DISTRICTS[selectedDistrict] || '강남구 역삼동'
    if (lastFetchedDistrictRef.current === selectedDistrict && liveWeather) {
      return
    }
    lastFetchedDistrictRef.current = selectedDistrict

    fetch(`${API_BASE_URL}/api/v1/weather/current?district=${encodeURIComponent(districtName)}`)
      .then(res => res.json())
      .then((data: LiveWeatherData) => {
        if (isMounted && data.status === 'success') {
          setLiveWeather(data)
          logWeatherApiCall({ nx: data.nx, ny: data.ny }, data, data)
        }
      })
      .catch(err => {
        console.warn('[Live Weather] 기상청 실시간 데이터 연동 실패 (fallback 유지):', err)
      })
    return () => {
      isMounted = false
    }
  }, [selectedDistrict])

  const isLive = liveWeather !== null
  const isCurrentHour = selectedHour === nowHour
  const selectedHourItem = hourlyForecast.find(d => d.hour_num === selectedHour) || null
  const activeTemp = liveWeather ? liveWeather.temp : 14.0
  const activeRain = liveWeather ? liveWeather.rain : 0.0
  const activeHumidity = liveWeather ? liveWeather.humidity : 60.0
  const activeWind = liveWeather ? liveWeather.wind : 2.0

  const displayTemp = !isCurrentHour && selectedHourItem ? selectedHourItem.temp : activeTemp
  const displayRain = !isCurrentHour && selectedHourItem ? selectedHourItem.rain : activeRain
  const displayHumidity =
    !isCurrentHour && selectedHourItem ? selectedHourItem.humidity : activeHumidity
  const displayWind = !isCurrentHour && selectedHourItem ? selectedHourItem.wind : activeWind
  const isRaining =
    displayRain > 0 || (isCurrentHour && isLive && liveWeather.pty !== '0' && liveWeather.pty !== '')
  const activePtyDesc = isLive
    ? liveWeather.pty_desc
    : activeRain > 0
      ? `비 · ${activeRain}mm/h`
      : '맑음'
  const displayPtyDesc = !isCurrentHour
    ? displayRain > 0
      ? `비 · ${displayRain}mm/h`
      : '맑음'
    : activePtyDesc

  const handleViewportChange = (center: { lat: number; lng: number }) => {
    const resolved = resolveDistrict('', [center.lng, center.lat])
    const key = `${resolved}|${center.lat.toFixed(2)}|${center.lng.toFixed(2)}`
    if (viewportWeatherKeyRef.current === key) return
    viewportWeatherKeyRef.current = key
    setViewportDistrict(resolved)
    const url = `${API_BASE_URL}/api/v1/weather/current?district=${encodeURIComponent(resolved)}&lat=${center.lat}&lng=${center.lng}`
    fetch(url)
      .then(res => res.json())
      .then((data: LiveWeatherData) => {
        if (data && data.status === 'success') setViewportWeather(data)
      })
      .catch(err => {
        viewportWeatherKeyRef.current = ''
        console.warn('[지도 뷰포트 기상] 조회 실패 — 기존 자치구 기상 유지:', err)
      })
  }

  const mapWeather = viewportWeather || liveWeather
  const mapTemp = mapWeather ? mapWeather.temp : activeTemp
  const mapRain = mapWeather ? mapWeather.rain : activeRain
  const mapHumidity = mapWeather ? mapWeather.humidity : activeHumidity
  const mapWind = mapWeather ? mapWeather.wind : activeWind
  const mapPtyDesc = mapWeather
    ? mapWeather.pty_desc || (mapWeather.rain > 0 ? '비' : '맑음')
    : activePtyDesc
  const mapDistrictLabel = viewportDistrict || DISTRICTS[selectedDistrict] || '서울특별시'
  const isViewportWeather = Boolean(viewportWeather)

  const fetchAIPrediction = async (
    districtName: string,
    hourVal: number,
    weather: { temp: number; rain: number; humidity: number; wind: number; hour: string }
  ) => {
    setAiStatus('loading')
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/predict/recommendation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          district: districtName,
          hour: hourVal,
          weather: {
            temp: weather.temp,
            rain: weather.rain,
            humidity: weather.humidity,
            wind: weather.wind,
          },
        }),
      })

      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()

      if (data.status === 'success' && Array.isArray(data.recommendations)) {
        const mapped: TransportScoreViewItem[] = data.recommendations.map((r: any) => ({
          id: r.id,
          icon: r.icon,
          name: r.name,
          score: r.score,
          scoreLabel: r.scoreLabel,
          scoreColor: r.scoreColor,
          reasons: r.reasons,
          time: `${r.estimated_time_min}분`,
          price: `${r.fare_krw.toLocaleString()}원${r.id === 'bike' ? '/시간' : ''}`,
          crowd: r.crowd,
          crowdLabel: r.crowdLabel,
          crowdColor: r.crowdColor,
          dataset:
            r.id === 'subway'
              ? '지하철 호선별 역별 시간대별 승하차 (AI 추론)'
              : r.id === 'bus'
                ? '버스노선별 정류장별 시간대별 승하차 (AI 추론)'
                : '공공자전거 따릉이 대여이력 (AI 추론)',
          predicted_volume: r.predicted_volume,
        }))

        setTransportScores(mapped)
        setAiLatency(data.latency_ms)
        setAiWeatherSummary(data.weather_summary)
        setAiStatus('connected')

        logAIPredictionCall(
          {
            district: districtName,
            station: districtName,
            location: districtName,
            rain: `${weather.rain}mm`,
            temp: `${weather.temp}°C`,
            hour: `${hourVal}시`,
            latency: `${data.latency_ms}ms (ONNX Engine)`,
          },
          data.recommendations
        )
      }
    } catch (err) {
      console.warn('[AI Engine] 백엔드 연결 불가, 기본 목데이터 유지:', err)
      setAiStatus('offline')
    }
  }

  const fetchDistrictCongestion = async (rainVal: number, tempVal: number, hourVal: number) => {
    const fetchKey = `${rainVal}_${tempVal}_${hourVal}`
    if (lastDistrictCongestionKeyRef.current === fetchKey) return
    lastDistrictCongestionKeyRef.current = fetchKey

    try {
      setDistrictLiveStatus('loading')
      const res = await fetch(
        `${API_BASE_URL}/api/v1/districts/live-congestion?rain=${rainVal}&temp=${tempVal}&hour=${hourVal}`
      )
      if (res.ok) {
        const data = await res.json()
        if (data.status === 'success' && data.hotspots && data.hotspots.length > 0) {
          setDistrictList(data.hotspots)
          setDistrictLiveStatus('live')
          logDistrictCongestionCall({ rain: rainVal, temp: tempVal, hour: hourVal }, data)
        }
      }
    } catch (err) {
      console.warn('동별 실시간 교통 혼잡도 조회 실패, 기본값 유지:', err)
      setDistrictLiveStatus('idle')
    }
  }

  const fetchHourlyForecast = async (districtName: string, rainVal: number, tempVal: number) => {
    const fetchKey = `${districtName}_${rainVal}_${tempVal}`
    if (lastHourlyForecastKeyRef.current === fetchKey) return
    lastHourlyForecastKeyRef.current = fetchKey

    try {
      setHourlyLiveStatus('loading')
      const targetDistrict = districtName.split(' ')[0] || districtName
      const res = await fetch(
        `${API_BASE_URL}/api/v1/transit/hourly-forecast?district=${encodeURIComponent(targetDistrict)}&rain=${rainVal}&temp=${tempVal}`
      )
      if (res.ok) {
        const data = await res.json()
        const forecastList = data.forecast || data.hourly
        if (data.status === 'success' && forecastList && forecastList.length > 0) {
          setHourlyForecast(forecastList)
          setHourlyLiveStatus('live')
          logHourlyForecastCall({ district: targetDistrict, rain: rainVal, temp: tempVal }, data)
        }
      }
    } catch (err) {
      console.warn('24시간 AI 시계열 예측 조회 실패, 기본값 유지:', err)
      setHourlyLiveStatus('idle')
    }
  }

  useEffect(() => {
    if (!liveWeather) return

    const districtName = DISTRICTS[selectedDistrict] || '강남구 역삼동'
    const fetchKey = `${districtName}_${displayTemp}_${displayRain}_${selectedHour}`

    if (lastAIFetchKeyRef.current !== fetchKey) {
      lastAIFetchKeyRef.current = fetchKey
      fetchAIPrediction(districtName, selectedHour, {
        temp: displayTemp,
        rain: displayRain,
        humidity: displayHumidity,
        wind: displayWind,
        hour: `${selectedHour}시`,
      })
    }

    fetchDistrictCongestion(displayRain, displayTemp, selectedHour)
    fetchHourlyForecast(districtName, activeRain, activeTemp)
  }, [selectedDistrict, liveWeather, displayRain, displayTemp, selectedHour, displayHumidity, displayWind])

  return {
    liveWeather,
    viewportWeather,
    viewportDistrict,
    nowHour,
    selectedHour,
    setSelectedHour,
    transportScores,
    aiLatency,
    aiStatus,
    aiWeatherSummary,
    districtList,
    districtLiveStatus,
    hourlyForecast,
    hourlyLiveStatus,
    hourlyHovered,
    setHourlyHovered,
    isLive,
    isCurrentHour,
    activeTemp,
    activeRain,
    activeHumidity,
    activeWind,
    displayTemp,
    displayRain,
    displayHumidity,
    displayWind,
    isRaining,
    activePtyDesc,
    displayPtyDesc,
    handleViewportChange,
    mapWeather,
    mapTemp,
    mapRain,
    mapHumidity,
    mapWind,
    mapPtyDesc,
    mapDistrictLabel,
    isViewportWeather,
  }
}
