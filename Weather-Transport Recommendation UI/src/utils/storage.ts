import { DISTRICTS } from '../constants/districts'

export type Page = 'main' | 'route' | 'map' | 'enterprise'
export type Theme = 'dark' | 'light'

export function safeGetStorage(key: string): string | null {
  if (typeof window === 'undefined') return null
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

export function safeSetStorage(key: string, value: string): void {
  if (typeof window === 'undefined') return
  try {
    localStorage.setItem(key, value)
  } catch {
    // localStorage 접근 불가 환경 대비
  }
}

export function getInitialTheme(): Theme {
  const saved = safeGetStorage('weather-transit-theme')
  if (saved === 'light' || saved === 'dark') return saved

  if (typeof window !== 'undefined' && window.matchMedia) {
    if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark'
    }
    return 'light'
  }
  return 'dark'
}

export function getInitialPage<T extends Page>(allowedPages: readonly T[]): T {
  if (typeof window !== 'undefined') {
    const hash = window.location.hash.replace(/^#/, '') as T
    if (allowedPages.includes(hash)) return hash
    const saved = safeGetStorage('weather_transit_page') as T | null
    if (saved && allowedPages.includes(saved)) return saved
  }
  return 'main' as T
}

export function getInitialDistrict(): number {
  const savedName = safeGetStorage('weather_transit_district_name')
  if (savedName) {
    const idx = DISTRICTS.indexOf(savedName)
    if (idx !== -1) return idx
    const partialIdx = DISTRICTS.findIndex(d => d.includes(savedName) || savedName.includes(d))
    if (partialIdx !== -1) return partialIdx
  }
  const savedIdx = safeGetStorage('weather_transit_district')
  if (savedIdx !== null) {
    const num = Number(savedIdx)
    if (!isNaN(num) && num >= 0 && num < DISTRICTS.length) return num
  }
  return 0
}
