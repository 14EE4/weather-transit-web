/**
 * API Base URL 단일 해석 모듈 (DIP / SSoT)
 * Docker Nginx 환경에서는 VITE_API_BASE_URL="" 이므로 `new URL()` 대신
 * 문자열 템플릿 + URLSearchParams 조합을 사용합니다.
 */
export function getApiBaseUrl(): string {
  const envVal = (import.meta as unknown as { env?: Record<string, unknown> }).env?.VITE_API_BASE_URL
  if (typeof envVal === 'string') return envVal
  if (typeof window !== 'undefined' && window.location) {
    const proto = window.location.protocol || 'http:'
    const host = window.location.hostname || 'localhost'
    return `${proto}//${host}:8000`
  }
  return 'http://localhost:8000'
}

export const API_BASE_URL: string = getApiBaseUrl()

export function buildApiUrl(path: string, params?: Record<string, string | number | boolean | undefined>): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const base = `${API_BASE_URL}${normalizedPath}`
  if (!params) return base
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) sp.set(k, String(v))
  }
  const qs = sp.toString()
  return qs ? `${base}?${qs}` : base
}
