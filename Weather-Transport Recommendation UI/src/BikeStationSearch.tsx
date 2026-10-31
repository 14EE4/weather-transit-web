import { useEffect, useState } from 'react'

export interface BikeStationResult {
  id: string
  name: string
  coords: [number, number]
  rackTotal: number
  availableBikes: number
}

interface Props {
  onSelect: (station: BikeStationResult) => void
}

// 빈 문자열("")은 Docker/Nginx 리버스 프록시용 유효값이므로 `||` 대신 typeof 로 판별한다.
const envApiBase = import.meta.env.VITE_API_BASE_URL
const API_BASE: string = typeof envApiBase === 'string' ? envApiBase : 'http://127.0.0.1:8000'

export default function BikeStationSearch({ onSelect }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<BikeStationResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [open, setOpen] = useState(false)

  useEffect(() => {
    const keyword = query.trim()

    if (keyword.length < 2) {
      setResults([])
      setLoading(false)
      setError('')
      return
    }

    const controller = new AbortController()

    const timer = setTimeout(async () => {
      setLoading(true)
      setError('')

      try {
        const response = await fetch(
          `${API_BASE}/api/v1/transit/bike/stations/search?q=${encodeURIComponent(keyword)}`,
          { signal: controller.signal }
        )
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }
        const data = await response.json()
        setResults(data.stations || [])
      } catch {
        if (controller.signal.aborted) return
        setResults([])
        setError('대여소 정보를 불러오지 못했습니다.')
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false)
        }
      }
    }, 350)

    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [query])

  return (
    <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--color-border)', position: 'relative' }}>
      <div style={{ color: '#34D399', fontSize: 12, fontWeight: 700, marginBottom: 9 }}>
        🚲 따릉이 대여소 검색
      </div>

      <input
        value={query}
        onChange={e => {
          setQuery(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={e => {
          if (e.key === 'Escape') setOpen(false)
          if (e.key === 'Enter' && results.length > 0) {
            onSelect(results[0])
            setQuery(results[0].name)
            setOpen(false)
          }
        }}
        placeholder="대여소 이름 입력 (예: 강남역)"
        style={{
          width: '100%',
          boxSizing: 'border-box',
          padding: '12px',
          borderRadius: 10,
          border: '1px solid rgba(52,211,153,0.4)',
          background: 'var(--color-card)',
          color: 'var(--app-text)',
          outline: 'none'
        }}
      />

      {open && query.trim().length >= 2 && (
        <div style={{
          position: 'absolute',
          left: 20,
          right: 20,
          top: '100%',
          background: 'var(--color-surface)',
          border: '1px solid rgba(52,211,153,0.4)',
          borderRadius: 10,
          maxHeight: 300,
          overflowY: 'auto',
          zIndex: 200,
          boxShadow: '0 8px 24px rgba(0,0,0,0.5)'
        }}>
          {loading && <div style={{ padding: 12, color: 'var(--color-muted)' }}>대여소 검색 중...</div>}
          {error && <div style={{ padding: 12, color: '#FCA5A5' }}>{error}</div>}
          {!loading && !error && results.length === 0 && (
            <div style={{ padding: 12, color: 'var(--color-muted)' }}>검색 결과가 없습니다.</div>
          )}
          {!loading && results.map(station => (
            <button
              key={station.id}
              type="button"
              onClick={() => {
                onSelect(station)
                setQuery(station.name)
                setOpen(false)
              }}
              style={{
                display: 'block',
                width: '100%',
                background: 'transparent',
                border: 'none',
                borderBottom: '1px solid rgba(255,255,255,0.07)',
                padding: '11px 13px',
                textAlign: 'left',
                cursor: 'pointer',
                color: 'var(--app-text)'
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 700 }}>🚲 {station.name}</div>
              <div style={{ fontSize: 11, color: 'var(--color-muted)', marginTop: 3 }}>
                대여 가능 {station.availableBikes}대 / 거치대 {station.rackTotal}개
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
