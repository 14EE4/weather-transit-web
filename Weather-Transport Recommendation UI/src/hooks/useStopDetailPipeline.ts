import { useEffect, useRef, useState } from 'react'
import { API_BASE_URL } from '../api/client'
import { logAIPredictionCall, logBusApiCall, logSubwayApiCall, logWeatherApiCall } from '../apiLogger'
import { resolveDistrict } from '../districtResolver'
import type { StopDetailData, TransitStop } from '../TransitMap'
import type { LiveWeatherData } from './useWeatherAndAI'

export interface StopArrivalState {
  loading: boolean
  subwayArrivals?: any[]
  busArrivals?: any[]
  lastUpdated?: string
}

export function useStopDetailPipeline(liveWeather: LiveWeatherData | null) {
  const [selectedStop, setSelectedStop] = useState<TransitStop | null>(null)
  const [stopArrivalData, setStopArrivalData] = useState<StopArrivalState>({ loading: false })
  const [stopWeatherData, setStopWeatherData] = useState<any | null>(null)
  const [stopAIData, setStopAIData] = useState<any | null>(null)
  const [stopDataLoading, setStopDataLoading] = useState(false)
  const lastFetchedStopIdRef = useRef<string | null>(null)

  const handleSelectStop = (stop: TransitStop | null, details?: StopDetailData) => {
    if (!stop) {
      lastFetchedStopIdRef.current = null
      setSelectedStop(null)
      setStopWeatherData(null)
      setStopAIData(null)
      setStopArrivalData({ loading: false })
      setStopDataLoading(false)
      return
    }

    lastFetchedStopIdRef.current = stop.id
    setSelectedStop(stop)

    if (details?.loading) {
      setStopDataLoading(true)
      setStopArrivalData({ loading: true })
    } else if (details && !details.loading) {
      setStopDataLoading(false)
      setStopWeatherData(details.weather || null)
      setStopAIData(details.aiPrediction || null)
      setStopArrivalData({
        loading: false,
        subwayArrivals: stop.type === 'subway' ? (details.arrivals || []) : [],
        busArrivals: stop.type === 'bus' ? (details.arrivals || []) : [],
        lastUpdated: new Date().toLocaleTimeString('ko-KR', {
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        }),
      })
    }
  }

  useEffect(() => {
    if (!selectedStop) {
      setStopArrivalData({ loading: false })
      setStopWeatherData(null)
      setStopAIData(null)
      setStopDataLoading(false)
      return
    }

    if (lastFetchedStopIdRef.current === selectedStop.id && (stopWeatherData || stopAIData)) {
      return
    }

    let isMounted = true
    const stop = selectedStop
    const district = resolveDistrict(stop.name, stop.coords)
    const cleanName = stop.name.replace(/역$/, '').trim()

    setStopDataLoading(true)
    setStopArrivalData({ loading: true })

    const runStopPipeline = async () => {
      try {
        const weatherUrl = `${API_BASE_URL}/api/v1/weather/current?district=${encodeURIComponent(district)}&lat=${stop.coords[1]}&lng=${stop.coords[0]}&station=${encodeURIComponent(cleanName)}`
        const weatherRes = await fetch(weatherUrl)
        const weatherJson = await weatherRes.json()

        if (!isMounted) return
        setStopWeatherData(weatherJson)
        logWeatherApiCall({ nx: weatherJson.nx, ny: weatherJson.ny }, weatherJson, weatherJson)

        const currentHour = liveWeather
          ? parseInt(liveWeather.base_time.slice(0, 2), 10)
          : new Date().getHours()
        const aiPayload = {
          district,
          station: stop.name,
          point_id: stop.stId || stop.stationNo || stop.id,
          stop_type: stop.type,
          base_crowd: stop.baseCrowd,
          hour: currentHour,
          weather: {
            temp: weatherJson.temp,
            rain: weatherJson.rain,
            humidity: weatherJson.humidity,
            wind: weatherJson.wind,
          },
        }

        const aiRes = await fetch(`${API_BASE_URL}/api/v1/predict/recommendation`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(aiPayload),
        })
        const aiJson = await aiRes.json()

        if (!isMounted) return
        setStopAIData(aiJson)
        logAIPredictionCall(aiPayload, aiJson)

        if (stop.type === 'subway') {
          const arrivalRes = await fetch(
            `${API_BASE_URL}/api/v1/transit/subway/arrival?station=${encodeURIComponent(cleanName)}`
          )
          const arrivalData = await arrivalRes.json()
          if (!isMounted) return

          const arrivals =
            arrivalData.status === 'success' &&
            Array.isArray(arrivalData.arrivals) &&
            arrivalData.arrivals.length > 0
              ? arrivalData.arrivals
              : []
          setStopArrivalData({
            loading: false,
            subwayArrivals: arrivals,
            lastUpdated: new Date().toLocaleTimeString('ko-KR', {
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
            }),
          })
          logSubwayApiCall(cleanName, arrivals, arrivalData)
        } else if (stop.type === 'bus') {
          const targetStId = stop.stId || ''
          if (!targetStId) {
            setStopArrivalData({ loading: false, busArrivals: [] })
          } else {
            const busRes = await fetch(
              `${API_BASE_URL}/api/v1/transit/bus/arrival?stId=${encodeURIComponent(targetStId)}`
            )
            const busData = await busRes.json()
            if (!isMounted) return

            const arrivals =
              busData.status === 'success' &&
              Array.isArray(busData.arrivals) &&
              busData.arrivals.length > 0
                ? busData.arrivals
                : []
            setStopArrivalData({
              loading: false,
              busArrivals: arrivals,
              lastUpdated: new Date().toLocaleTimeString('ko-KR', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
              }),
            })
            logBusApiCall(stop.lineInfo || targetStId, targetStId, arrivals, busData)
          }
        } else {
          setStopArrivalData({ loading: false })
        }
      } catch (err) {
        console.error('거점 상세 파이프라인 조회 오류:', err)
        if (isMounted) {
          setStopArrivalData({
            loading: false,
            subwayArrivals: [],
            lastUpdated: new Date().toLocaleTimeString('ko-KR', {
              hour: '2-digit',
              minute: '2-digit',
              second: '2-digit',
            }),
          })
        }
      } finally {
        if (isMounted) {
          setStopDataLoading(false)
        }
      }
    }

    runStopPipeline()

    return () => {
      isMounted = false
    }
  }, [selectedStop])

  return {
    selectedStop,
    setSelectedStop,
    stopArrivalData,
    stopWeatherData,
    stopAIData,
    stopDataLoading,
    handleSelectStop,
  }
}
