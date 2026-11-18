import { useEffect, useRef, useState } from 'react'
import { DISTRICTS } from '../constants/districts'
import { resolveDistrictNameFromPoint } from '../districtResolver'

export interface MyLocationState {
  coords: [number, number]
  accuracy: number
  district?: string
  isManual?: boolean
}

interface UseGeoDistrictOptions {
  setSelectedDistrict: (idx: number) => void
  setMyLocation: (loc: MyLocationState | null) => void
  showRouteToast: (message: string, actionLabel?: string) => void
}

export function useGeoDistrict({
  setSelectedDistrict,
  setMyLocation,
  showRouteToast,
}: UseGeoDistrictOptions) {
  const [isLocatingDistrict, setIsLocatingDistrict] = useState(false)
  const userManuallyChangedDistrictRef = useRef(false)
  const hasAutoLocatedRef = useRef(false)

  const locateCurrentDistrict = (isManualClick = false) => {
    if (typeof window === 'undefined' || !navigator.geolocation) {
      if (isManualClick) {
        showRouteToast('이 브라우저는 위치 정보(GPS) 서비스를 지원하지 않습니다.')
      }
      return
    }

    setIsLocatingDistrict(true)
    navigator.geolocation.getCurrentPosition(
      pos => {
        setIsLocatingDistrict(false)
        const lng = pos.coords.longitude
        const lat = pos.coords.latitude
        const accuracy = Math.round(pos.coords.accuracy || 25)
        const coords: [number, number] = [lng, lat]

        const isInsideKorea = lng >= 124.0 && lng <= 132.0 && lat >= 32.8 && lat <= 39.2
        if (!isInsideKorea) {
          if (isManualClick) {
            showRouteToast('⚠️ 대한민국 영역 밖의 위치가 감지되었습니다.')
          }
          return
        }

        const detectedDistrict = resolveDistrictNameFromPoint('내 위치 (GPS)', coords)
        const matchedIdx = DISTRICTS.findIndex(
          d => d.startsWith(detectedDistrict) || d.includes(detectedDistrict)
        )

        if (matchedIdx !== -1 && (isManualClick || !userManuallyChangedDistrictRef.current)) {
          setSelectedDistrict(matchedIdx)
          setMyLocation({ coords, accuracy, district: detectedDistrict, isManual: false })
          if (isManualClick) {
            showRouteToast(`📍 내 위치 감지: ${detectedDistrict} (정확도 ±${accuracy}m)`)
          } else {
            showRouteToast(`📍 현재 위치(${detectedDistrict}) 기준으로 메인 지역 날씨가 자동 설정되었습니다.`)
          }
        }
      },
      err => {
        setIsLocatingDistrict(false)
        if (isManualClick) {
          let msg = '현재 위치를 확인할 수 없습니다.'
          if (err.code === 1) {
            msg = '위치 정보 접근 권한이 거부되었습니다. 브라우저 주소창에서 위치 접근을 허용해 주세요.'
          } else if (err.code === 2) {
            msg = '현재 위치 정보를 수신할 수 없습니다.'
          } else if (err.code === 3) {
            msg = '위치 확인 요청 시간이 초과되었습니다.'
          }
          showRouteToast(`❌ ${msg}`)
        }
      },
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 }
    )
  }

  useEffect(() => {
    if (hasAutoLocatedRef.current) return
    hasAutoLocatedRef.current = true
    locateCurrentDistrict(false)
  }, [])

  return {
    isLocatingDistrict,
    userManuallyChangedDistrictRef,
    locateCurrentDistrict,
  }
}
