import { useEffect, useMemo, useRef, useState } from 'react'
import { searchSubwayStations, type SubwayStation } from './subwayData'
import type { BusStationResult } from './BusStationSearch'
import type { BikeStationResult } from './BikeStationSearch'

export type SearchTransport = 'all' | 'subway' | 'bus' | 'bike'

interface Props {
  transport: SearchTransport
  onSelectSubway: (station: SubwayStation) => void
  onSelectBus: (station: BusStationResult) => void
  onSelectBike: (station: BikeStationResult) => void
}

type Item =
  | { kind: 'subway'; key: string; name: string; sub: string; data: SubwayStation }
  | { kind: 'bus'; key: string; name: string; sub: string; data: BusStationResult }
  | { kind: 'bike'; key: string; name: string; sub: string; data: BikeStationResult }

// 빈 문자열("")은 Docker/Nginx 리버스 프록시용 유효값이므로 `||` 대신 typeof 로 판별한다.
const envApiBase = import.meta.env.VITE_API_BASE_URL
const API_BASE: string = typeof envApiBase === 'string' ? envApiBase : 'http://127.0.0.1:8000'

const META = {
  subway: { icon: '🚇', label: '지하철역', color: 'var(--color-primary)', placeholder: '지하철역 이름 입력 (예: 강남, 시청)' },
  bus: { icon: '🚌', label: '버스정류장', color: '#FB923C', placeholder: '정류장 이름 입력 (예: 강남역)' },
  bike: { icon: '🚲', label: '따릉이 대여소', color: '#34D399', placeholder: '대여소 이름 입력 (예: 강남역)' },
} as const

const PER_KIND_ALL = 5
const PER_KIND_SINGLE = 15

export default function UnifiedStationSearch({ transport, onSelectSubway, onSelectBus, onSelectBike }: Props) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [activeIdx, setActiveIdx] = useState(0)
  const [busResults, setBusResults] = useState<BusStationResult[]>([])
  const [bikeResults, setBikeResults] = useState<BikeStationResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const rootRef = useRef<HTMLDivElement>(null)

  const keyword = query.trim()
  const wantSubway = transport === 'all' || transport === 'subway'
  const wantBus = transport === 'all' || transport === 'bus'
  const wantBike = transport === 'all' || transport === 'bike'
  const limit = transport === 'all' ? PER_KIND_ALL : PER_KIND_SINGLE

  // 탭이 바뀌면 드롭다운 닫기 (입력값은 유지)
  useEffect(() => {
    setOpen(false)
  }, [transport])

  // 버스/따릉이: 백엔드 병렬 검색 (debounce 350ms, 요청 취소)
  useEffect(() => {
    if (keyword.length < 2 || (!wantBus && !wantBike)) {
      setBusResults([])
      setBikeResults([])
      setLoading(false)
      setError('')
      return
    }

    const controller = new AbortController()
    const timer = setTimeout(async () => {
      setLoading(true)
      setError('')
      const q = encodeURIComponent(keyword)
      const call = async (path: string) => {
        const res = await fetch(`${API_BASE}/api/v1/transit/${path}/stations/search?q=${q}`, { signal: controller.signal })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.json()
        return (data.stations || []) as any[]
      }
      const [bus, bike] = await Promise.allSettled([
        wantBus ? call('bus') : Promise.resolve([]),
        wantBike ? call('bike') : Promise.resolve([]),
      ])
      if (controller.signal.aborted) return
      setBusResults(bus.status === 'fulfilled' ? bus.value : [])
      setBikeResults(bike.status === 'fulfilled' ? bike.value : [])
      const failed: string[] = []
      if (bus.status === 'rejected') failed.push('버스')
      if (bike.status === 'rejected') failed.push('따릉이')
      setError(failed.length ? `${failed.join('·')} 정보를 불러오지 못했습니다.` : '')
      setLoading(false)
    }, 350)

    return () => {
      clearTimeout(timer)
      controller.abort()
    }
  }, [keyword, wantBus, wantBike])

  const items: Item[] = useMemo(() => {
    if (!keyword) return []
    const out: Item[] = []
    if (wantSubway) {
      searchSubwayStations(keyword).slice(0, limit).forEach(s =>
        out.push({ kind: 'subway', key: `s-${s.id}`, name: s.name, sub: `${s.lines[0] ?? ''} · ${s.zone}`, data: s }))
    }
    if (wantBus) {
      busResults.slice(0, limit).forEach(s =>
        out.push({ kind: 'bus', key: `b-${s.id}`, name: s.name, sub: `정류장 번호 ${s.arsId}`, data: s }))
    }
    if (wantBike) {
      bikeResults.slice(0, limit).forEach(s =>
        out.push({ kind: 'bike', key: `k-${s.id}`, name: s.name, sub: `대여 ${s.availableBikes}대 / 거치대 ${s.rackTotal}개`, data: s }))
    }
    return out
  }, [keyword, wantSubway, wantBus, wantBike, busResults, bikeResults, limit])

  useEffect(() => { setActiveIdx(0) }, [items.length, keyword])

  // 바깥 클릭 시 드롭다운 닫기
  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [])

  const select = (item: Item) => {
    setQuery(item.name)
    setOpen(false)
    if (item.kind === 'subway') onSelectSubway(item.data)
    else if (item.kind === 'bus') onSelectBus(item.data)
    else onSelectBike(item.data)
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') { setOpen(false); return }
    if (items.length === 0) return
    if (e.key === 'ArrowDown' || (e.key === 'Tab' && !e.shiftKey)) {
      e.preventDefault()
      setActiveIdx(i => (i + 1) % items.length)
    } else if (e.key === 'ArrowUp' || (e.key === 'Tab' && e.shiftKey)) {
      e.preventDefault()
      setActiveIdx(i => (i - 1 + items.length) % items.length)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      select(items[activeIdx] ?? items[0])
    }
  }

  const headerMeta = transport === 'all' ? null : META[transport]
  const placeholder = transport === 'all' ? '지하철·버스·따릉이 통합 검색 (예: 강남)' : META[transport].placeholder
  const title = transport === 'all' ? '통합 검색 & 바로가기' : `${META[transport].label} 검색 & 바로가기`
  const showDropdown = open && keyword.length >= 1
  const needMore = keyword.length < 2 && (wantBus || wantBike) && !wantSubway

  return (
    <div ref={rootRef} style={{ padding: '16px 20px 14px', borderBottom: '1px solid var(--color-border)', position: 'relative' }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: headerMeta?.color ?? 'var(--color-primary)', letterSpacing: '0.04em', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
        <span>🔍</span> {title}
      </div>

      <div style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: 12, padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ fontSize: 14 }}>{headerMeta?.icon ?? '🔎'}</span>
        <input
          value={query}
          onChange={e => { setQuery(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder={placeholder}
          style={{ flex: 1, minWidth: 0, background: 'transparent', border: 'none', outline: 'none', fontSize: 13, color: 'var(--app-text)', fontFamily: "'Outfit','Noto Sans KR',sans-serif" }}
        />
        {query && (
          <button
            type="button"
            onClick={() => { setQuery(''); setOpen(false) }}
            style={{ background: 'transparent', border: 'none', color: 'var(--color-muted)', cursor: 'pointer', fontSize: 12 }}
          >
            ✕
          </button>
        )}
      </div>

      {showDropdown && (
        <div style={{
          position: 'absolute', top: '100%', left: 20, right: 20, zIndex: 200,
          background: 'var(--color-surface)', border: '1px solid color-mix(in srgb, var(--color-primary) 35%, transparent)',
          borderRadius: 12, boxShadow: '0 8px 30px rgba(0,0,0,0.6)', maxHeight: 320, overflowY: 'auto',
        }}>
          {items.length > 0 && (
            <div style={{ padding: '6px 12px', fontSize: 10, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between' }}>
              <span>검색 결과 {items.length}건</span>
              <span>⌨️ [↑↓ / Tab] 이동 · [Enter] 선택</span>
            </div>
          )}

          {items.map((item, idx) => {
            const m = META[item.kind]
            const active = idx === activeIdx
            const showGroup = transport === 'all' && (idx === 0 || items[idx - 1].kind !== item.kind)
            return (
              <div key={item.key}>
                {showGroup && (
                  <div style={{ padding: '5px 12px', fontSize: 10, fontWeight: 700, color: m.color, background: 'color-mix(in srgb, var(--color-card) 70%, transparent)' }}>
                    {m.icon} {m.label}
                  </div>
                )}
                <div
                  ref={el => { if (active && el) el.scrollIntoView({ block: 'nearest' }) }}
                  onClick={() => select(item)}
                  onMouseEnter={() => setActiveIdx(idx)}
                  style={{
                    padding: '10px 14px', borderBottom: '1px solid var(--color-border)', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
                    background: active ? 'color-mix(in srgb, var(--color-primary) 22%, transparent)' : 'transparent',
                    borderLeft: active ? `3px solid ${m.color}` : '3px solid transparent',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
                    <span style={{ fontSize: 15 }}>{m.icon}</span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--app-text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{item.name}</span>
                  </div>
                  <span style={{ fontSize: 11, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono', flexShrink: 0 }}>{item.sub}</span>
                </div>
              </div>
            )
          })}

          {loading && <div style={{ padding: 12, fontSize: 12, color: 'var(--color-muted)' }}>검색 중...</div>}
          {error && <div style={{ padding: 12, fontSize: 12, color: '#FCA5A5' }}>{error}</div>}
          {needMore && <div style={{ padding: 12, fontSize: 12, color: 'var(--color-muted)' }}>2글자 이상 입력해 주세요.</div>}
          {!loading && !error && !needMore && items.length === 0 && (
            <div style={{ padding: 14, fontSize: 12, color: 'var(--color-muted)', textAlign: 'center' }}>검색 결과가 없습니다.</div>
          )}
        </div>
      )}
    </div>
  )
}
