import { useEffect, useState } from 'react'

export interface BusStationResult {
  id: string
  name: string
  arsId: string
  coords: [number, number]
}

interface Props {
  onSelect: (station: BusStationResult) => void
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'

export default function BusStationSearch({ onSelect }: Props) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<BusStationResult[]>([])
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
          `${API_BASE}/api/v1/transit/bus/stations/search?q=${encodeURIComponent(keyword)}`,
          { signal: controller.signal }
        )

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`)
        }

        const data = await response.json()
        setResults(data.stations || [])
      } catch (err: unknown) {
        if (controller.signal.aborted) return
        setResults([])
        setError('정류장 정보를 불러오지 못했습니다.')
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
    <div style={{
      padding: '16px 20px',
      borderBottom: '1px solid rgba(255,255,255,0.08)',
      position: 'relative'
    }}>
      <div style={{
        color: '#34D399',
        fontSize: 12,
        fontWeight: 700,
        marginBottom: 9
      }}>
        🚌 버스정류장 검색
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
        placeholder="정류장 이름 입력 (예: 강남역)"
        style={{
          width: '100%',
          boxSizing: 'border-box',
          padding: '12px',
          borderRadius: 10,
          border: '1px solid rgba(52,211,153,0.4)',
          background: '#162040',
          color: '#FFFFFF',
          outline: 'none'
        }}
      />

      {open && query.trim().length >= 2 && (
        <div style={{
          position: 'absolute',
          left: 20,
          right: 20,
          top: '100%',
          background: '#111D35',
          border: '1px solid rgba(52,211,153,0.4)',
          borderRadius: 10,
          maxHeight: 300,
          overflowY: 'auto',
          zIndex: 200,
          boxShadow: '0 8px 24px rgba(0,0,0,0.5)'
        }}>
          {loading && (
            <div style={{ padding: 12, color: '#94A3B8' }}>
              정류장 검색 중...
            </div>
          )}

          {error && (
            <div style={{ padding: 12, color: '#FCA5A5' }}>
              {error}
            </div>
          )}

          {!loading && !error && results.length === 0 && (
            <div style={{ padding: 12, color: '#94A3B8' }}>
              검색 결과가 없습니다.
            </div>
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
                color: '#FFFFFF'
              }}
            >
              <div style={{ fontSize: 13, fontWeight: 700 }}>
                🚌 {station.name}
              </div>
              <div style={{
                fontSize: 11,
                color: '#94A3B8',
                marginTop: 3
              }}>
                정류장 번호: {station.arsId}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
