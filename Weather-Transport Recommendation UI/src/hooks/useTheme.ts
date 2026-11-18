import { useEffect, useState } from 'react'
import { getInitialTheme, safeGetStorage, safeSetStorage, type Theme } from '../utils/storage'

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(getInitialTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    safeSetStorage('weather-transit-theme', theme)
  }, [theme])

  // OS/기기 시스템 테마 실시간 변경 감지 (수동 설정 없을 때 동기화)
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    const handleChange = (e: MediaQueryListEvent) => {
      const saved = safeGetStorage('weather-transit-theme')
      if (!saved) {
        setTheme(e.matches ? 'dark' : 'light')
      }
    }
    mediaQuery.addEventListener('change', handleChange)
    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [])

  const toggleTheme = () => {
    setTheme(current => (current === 'dark' ? 'light' : 'dark'))
  }

  return { theme, setTheme, toggleTheme }
}
