const MULTIMODAL_MEMORY_CACHE = new Map<string, unknown>()
const LOCAL_STORAGE_CACHE_KEY = 'weather_transit_multimodal_cache_v7'

export function getCachedMultimodalResult<T>(key: string): T | null {
  if (!key) return null
  const mem = MULTIMODAL_MEMORY_CACHE.get(key) as T | undefined
  if (mem) return mem
  if (typeof window !== 'undefined') {
    try {
      const raw = localStorage.getItem(LOCAL_STORAGE_CACHE_KEY)
      if (raw) {
        const parsed = JSON.parse(raw) as Record<string, T>
        if (parsed && parsed[key]) {
          MULTIMODAL_MEMORY_CACHE.set(key, parsed[key])
          return parsed[key]
        }
      }
    } catch {}
  }
  return null
}

export function setCachedMultimodalResult<T>(key: string, value: T, maxEntries = 12): void {
  if (!key) return
  MULTIMODAL_MEMORY_CACHE.set(key, value)
  if (typeof window !== 'undefined') {
    try {
      const raw = localStorage.getItem(LOCAL_STORAGE_CACHE_KEY)
      const parsed: Record<string, T> = raw ? JSON.parse(raw) : {}
      parsed[key] = value
      const keys = Object.keys(parsed)
      if (keys.length > maxEntries) {
        delete parsed[keys[0]]
      }
      localStorage.setItem(LOCAL_STORAGE_CACHE_KEY, JSON.stringify(parsed))
    } catch {}
  }
}
