/**
 * [임시 테스트용 모듈 — 추후 삭제 예정]
 * 데스크톱/비-HTTPS 환경에서 스마트폰 GPS 수신을 시뮬레이션하기 위한 임시 모의 GPS 유틸리티
 */

export interface MockGpsPreset {
  id: string
  label: string
  coords: [number, number] // [lng, lat]
  accuracy: number
  desc: string
}

const STORAGE_KEY = '__TEMP_TEST_MOCK_GPS__'

export const MOCK_GPS_PRESETS: MockGpsPreset[] = [
  {
    id: 'hongdae',
    label: '홍대 연남동',
    coords: [126.9218, 37.5612],
    accuracy: 12,
    desc: '마포구 연남동 (홍대입구역 도보 약 450m)',
  },
  {
    id: 'gangnam',
    label: '강남 역삼동',
    coords: [127.0328, 37.4998],
    accuracy: 15,
    desc: '강남구 역삼동 (강남역 도보 약 420m)',
  },
  {
    id: 'yeouido',
    label: '여의도 공원',
    coords: [126.9285, 37.5262],
    accuracy: 10,
    desc: '영등포구 여의도동 (여의도역 도보 약 380m)',
  },
  {
    id: 'seongsu',
    label: '성수 카페거리',
    coords: [127.0558, 37.5425],
    accuracy: 14,
    desc: '성동구 성수동 (성수역 도보 약 350m)',
  },
  {
    id: 'gwanghwamun',
    label: '광화문 광장',
    coords: [126.9769, 37.5742],
    accuracy: 11,
    desc: '종로구 세종로 (광화문역 도보 약 300m)',
  },
]

export function getActiveMockGps(): MockGpsPreset | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (parsed && Array.isArray(parsed.coords) && parsed.coords.length === 2) {
      return parsed as MockGpsPreset
    }
  } catch {}
  return null
}

export function setActiveMockGps(preset: MockGpsPreset | null): void {
  if (typeof window === 'undefined') return
  try {
    if (!preset) {
      localStorage.removeItem(STORAGE_KEY)
    } else {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(preset))
    }
    window.dispatchEvent(new CustomEvent('mock-gps-changed', { detail: preset }))
  } catch {}
}

/**
 * 임시 모의 GPS가 설정되어 있으면 즉시 해당 좌표를 반환하고,
 * 없으면 실제 navigator.geolocation.getCurrentPosition을 호출합니다.
 */
export function getPositionWithMock(
  onSuccess: (pos: { coords: { longitude: number; latitude: number; accuracy: number }; isMock?: boolean; mockLabel?: string }) => void,
  onError?: (err: GeolocationPositionError | { code: number; message: string }) => void,
  options?: PositionOptions,
): void {
  const mock = getActiveMockGps()
  if (mock) {
    setTimeout(() => {
      onSuccess({
        coords: {
          longitude: mock.coords[0],
          latitude: mock.coords[1],
          accuracy: mock.accuracy,
        },
        isMock: true,
        mockLabel: mock.label,
      })
    }, 120)
    return
  }

  if (typeof window === 'undefined' || !navigator.geolocation) {
    onError?.({ code: 2, message: 'Geolocation not supported' })
    return
  }

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      onSuccess({
        coords: {
          longitude: pos.coords.longitude,
          latitude: pos.coords.latitude,
          accuracy: pos.coords.accuracy,
        },
        isMock: false,
      })
    },
    (err) => {
      onError?.(err)
    },
    options,
  )
}
