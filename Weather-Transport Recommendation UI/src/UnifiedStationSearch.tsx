import { useEffect, useMemo, useRef, useState } from 'react'
import { searchSubwayStations, type SubwayStation } from './subwayData'
import type { BusStationResult } from './BusStationSearch'
import type { BikeStationResult } from './BikeStationSearch'
import { MOCK_GPS_PRESETS, getActiveMockGps, setActiveMockGps, getPositionWithMock, type MockGpsPreset } from './mockGps'

export type SearchTransport = 'all' | 'subway' | 'bus' | 'bike'

export interface UnifiedStationSearchProps {
  transport?: SearchTransport
  value?: string
  onChange?: (val: string) => void
  onSelectSubway?: (station: SubwayStation) => void
  onSelectBus?: (station: BusStationResult) => void
  onSelectBike?: (station: BikeStationResult) => void
  /** [이슈 #90] 내 위치(GPS) 선택 시 콜백 */
  onSelectLocation?: (loc: { name: string; coords: [number, number]; type: string }) => void
  /** [이슈 #90] 출발지 검색창 등에서 '내 위치' 사용 버튼 활성화 */
  allowCurrentLocation?: boolean
  /** [이슈 #90] 지도에서 위치 직접 찍기 활성화 */
  allowMapPick?: boolean
  onPickOnMap?: () => void
  placeholder?: string
  title?: string
  headerColor?: string
  variant?: 'sidebar' | 'route'
  onClear?: () => void
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

export default function UnifiedStationSearch({
  transport = 'all',
  value,
  onChange,
  onSelectSubway,
  onSelectBus,
  onSelectBike,
  placeholder,
  title,
  headerColor,
  variant = 'sidebar',
  onClear,
  onSelectLocation,
  allowCurrentLocation = false,
  allowMapPick = false,
  onPickOnMap,
}: UnifiedStationSearchProps) {
  const [query, setQuery] = useState(value ?? '')
  const [open, setOpen] = useState(false)
  const [activeIdx, setActiveIdx] = useState(0)
  const [busResults, setBusResults] = useState<BusStationResult[]>([])
  const [bikeResults, setBikeResults] = useState<BikeStationResult[]>([])
  const [loading, setLoading] = useState(false)
  const [isLocating, setIsLocating] = useState(false)
  const [activeMock, setActiveMock] = useState<MockGpsPreset | null>(() => getActiveMockGps())
  const [error, setError] = useState('')
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onMockChange = () => setActiveMock(getActiveMockGps())
    window.addEventListener('mock-gps-changed', onMockChange)
    return () => window.removeEventListener('mock-gps-changed', onMockChange)
  }, [])

  const applyMockPreset = (preset: MockGpsPreset) => {
    setActiveMockGps(preset)
    setActiveMock(preset)
    const locName = '내 위치 (GPS)'
    setQuery(locName)
    onChange?.(locName)
    setOpen(false)
    onSelectLocation?.({ name: locName, coords: preset.coords, type: 'gps' })
  }

  const handleUseCurrentLocation = () => {
    setIsLocating(true)
    getPositionWithMock(
      (pos) => {
        setIsLocating(false)
        const coords: [number, number] = [pos.coords.longitude, pos.coords.latitude]
        const locName = '내 위치 (GPS)'
        setQuery(locName)
        onChange?.(locName)
        setOpen(false)
        onSelectLocation?.({ name: locName, coords, type: 'gps' })
      },
      (err: any) => {
        setIsLocating(false)
        let msg = '현재 위치를 확인할 수 없습니다.'
        if (err.code === 1) {
          msg = '위치 정보 접근 권한이 거부되었습니다. 브라우저 설정에서 위치 권한을 허용해 주세요.'
        } else if (err.code === 2) {
          msg = '현재 위치 정보를 수신할 수 없습니다.'
        } else if (err.code === 3) {
          msg = '위치 확인 요청 시간이 초과되었습니다.'
        }
        alert(msg)
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 30000 }
    )
  }

  // 외부 value 동기화 (맞바꾸기, 지도 팝업 등 부모 변경 반영)
  useEffect(() => {
    if (value !== undefined && value !== query) {
      setQuery(value)
    }
  }, [value])

  const keyword = query.trim()
  const cleanKeyword = keyword.replace(/^(따릉이|버스|정류장|정류소|대여소|지하철):\s*/, '').trim()
  const isBikeExplicit = keyword.startsWith('따릉이:')
  const isBusExplicit = keyword.startsWith('버스:')
  const wantSubway = (transport === 'all' || transport === 'subway') && !isBikeExplicit && !isBusExplicit
  const wantBus = (transport === 'all' || transport === 'bus') && !isBikeExplicit
  const wantBike = (transport === 'all' || transport === 'bike') && !isBusExplicit
  const limit = transport === 'all' ? PER_KIND_ALL : PER_KIND_SINGLE

  // 탭이 바뀌면 드롭다운 닫기 (입력값은 유지)
  useEffect(() => {
    setOpen(false)
  }, [transport])

  // 버스/따릉이: 백엔드 병렬 검색 (debounce 350ms, 요청 취소)
  useEffect(() => {
    const searchTarget = cleanKeyword || keyword
    if (searchTarget.length < 2 || (!wantBus && !wantBike)) {
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
      const q = encodeURIComponent(searchTarget)
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
  }, [cleanKeyword, keyword, wantBus, wantBike])

  const items: Item[] = useMemo(() => {
    const searchTarget = cleanKeyword || keyword
    if (!searchTarget) return []
    const out: Item[] = []
    if (wantSubway) {
      searchSubwayStations(searchTarget).slice(0, limit).forEach(s =>
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
  }, [cleanKeyword, keyword, wantSubway, wantBus, wantBike, busResults, bikeResults, limit])

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
    onChange?.(item.name)
    setOpen(false)
    if (item.kind === 'subway') onSelectSubway?.(item.data)
    else if (item.kind === 'bus') onSelectBus?.(item.data)
    else onSelectBike?.(item.data)
  }

  const handleClear = () => {
    setQuery('')
    onChange?.('')
    setOpen(false)
    onClear?.()
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
  const defaultPlaceholder = transport === 'all' ? '지하철·버스·따릉이 통합 검색 (예: 강남)' : META[transport].placeholder
  const finalPlaceholder = placeholder || defaultPlaceholder
  const defaultTitle = transport === 'all' ? '통합 검색 & 바로가기' : `${META[transport].label} 검색 & 바로가기`
  const finalTitle = title || defaultTitle
  const showDropdown = open && keyword.length >= 1
  const needMore = keyword.length < 2 && (wantBus || wantBike) && !wantSubway

  const isRouteVariant = variant === 'route'

  return (
    <div
      ref={rootRef}
      style={{
        padding: isRouteVariant ? '12px 18px 16px' : '16px 20px 14px',
        borderBottom: isRouteVariant ? 'none' : '1px solid var(--color-border)',
        position: 'relative',
      }}
    >
      {/* 헤더 */}
      {isRouteVariant ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
          <div style={{ fontSize: 10, color: headerColor || 'var(--color-primary)', fontFamily: 'JetBrains Mono', letterSpacing: '0.07em' }}>
            {finalTitle}
          </div>
          {query && (
            <button
              type="button"
              onClick={handleClear}
              title="지우기"
              style={{
                background: 'var(--color-card2)', border: 'none', borderRadius: 999,
                padding: '2px 8px', fontSize: 10, color: 'var(--color-muted)', cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 3,
              }}
            >
              <span>✕</span> 지우기
            </button>
          )}
        </div>
      ) : (
        <div style={{ fontSize: 11, fontWeight: 700, color: headerColor || headerMeta?.color || 'var(--color-primary)', letterSpacing: '0.04em', marginBottom: 8, display: 'flex', alignItems: 'center', gap: 6 }}>
          <span>🔍</span> {finalTitle}
        </div>
      )}

      {/* 검색 입력창 */}
      <div style={{
        background: 'var(--color-card)', border: '1px solid var(--color-border)', borderRadius: 12,
        padding: '10px 14px', display: 'flex', alignItems: 'center', gap: 8,
        transition: 'all 0.15s ease',
      }}>
        <span style={{ fontSize: 14 }}>{headerMeta?.icon ?? '🔎'}</span>
        <input
          value={query}
          onChange={e => {
            const next = e.target.value
            setQuery(next)
            onChange?.(next)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={onKeyDown}
          placeholder={finalPlaceholder}
          style={{
            flex: 1, minWidth: 0, background: 'transparent', border: 'none', outline: 'none',
            fontSize: isRouteVariant ? 14 : 13, color: 'var(--app-text)', fontFamily: "'Outfit','Noto Sans KR',sans-serif",
            fontWeight: isRouteVariant ? 500 : 400,
          }}
        />
        {allowCurrentLocation && (
          <button
            type="button"
            onClick={handleUseCurrentLocation}
            disabled={isLocating}
            title="현재 내 위치(GPS)를 출발지로 설정"
            style={{
              background: 'rgba(56, 189, 248, 0.15)',
              border: '1px solid rgba(56, 189, 248, 0.35)',
              borderRadius: 6,
              padding: '3px 8px',
              fontSize: 10,
              fontWeight: 700,
              color: '#38BDF8',
              cursor: isLocating ? 'wait' : 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 3,
              whiteSpace: 'nowrap',
              flexShrink: 0,
            }}
          >
            <span>{isLocating ? '⏳' : '📍'}</span>
            <span>{isLocating ? '확인 중' : '내 위치'}</span>
          </button>
        )}
        {allowMapPick && onPickOnMap && (
          <button
            type="button"
            onClick={onPickOnMap}
            title="지도에서 위치 직접 찍기"
            style={{
              background: 'rgba(52, 211, 153, 0.15)',
              border: '1px solid rgba(52, 211, 153, 0.35)',
              borderRadius: 6,
              padding: '3px 8px',
              fontSize: 10,
              fontWeight: 700,
              color: '#34D399',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: 3,
              whiteSpace: 'nowrap',
              flexShrink: 0,
            }}
          >
            <span>🎯</span>
            <span>지도에서 찍기</span>
          </button>
        )}
        {query && (
          <button
            type="button"
            onClick={handleClear}
            style={{ background: 'transparent', border: 'none', color: 'var(--color-muted)', cursor: 'pointer', fontSize: 12 }}
          >
            ✕
          </button>
        )}
      </div>

      {/* [임시 테스트용 GPS 설정 — 추후 삭제] */}
      {allowCurrentLocation && (
        <div
          style={{
            marginTop: 8,
            padding: '8px 10px',
            borderRadius: 10,
            background: 'rgba(245, 158, 11, 0.08)',
            border: '1px dashed rgba(245, 158, 11, 0.45)',
            display: 'flex',
            flexDirection: 'column',
            gap: 6,
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 10.5, fontWeight: 800, color: '#F59E0B' }}>
              🧪 임시 GPS 테스트 위치 (클릭 시 출발지에 모의 GPS 즉시 적용)
            </span>
            {activeMock && (
              <button
                type="button"
                onClick={() => {
                  setActiveMockGps(null)
                  setActiveMock(null)
                }}
                style={{
                  background: 'rgba(255,255,255,0.08)',
                  border: '1px solid var(--color-border)',
                  borderRadius: 6,
                  padding: '2px 6px',
                  fontSize: 9.5,
                  color: 'var(--color-muted)',
                  cursor: 'pointer',
                  fontWeight: 700,
                }}
              >
                🔄 실제 브라우저 위치로 복원
              </button>
            )}
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            {MOCK_GPS_PRESETS.map(p => {
              const isSelected = activeMock?.id === p.id
              return (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => applyMockPreset(p)}
                  title={`${p.desc} [${p.coords[1].toFixed(4)}, ${p.coords[0].toFixed(4)}]`}
                  style={{
                    padding: '4px 8px',
                    borderRadius: 6,
                    fontSize: 10.5,
                    fontWeight: 700,
                    cursor: 'pointer',
                    border: isSelected ? '1px solid #F59E0B' : '1px solid var(--color-border)',
                    background: isSelected ? 'rgba(245, 158, 11, 0.24)' : 'var(--color-card)',
                    color: isSelected ? '#FBBF24' : 'var(--app-text)',
                    transition: 'all 0.15s ease',
                  }}
                >
                  📍 {p.label}
                </button>
              )
            })}
          </div>
          {activeMock && (
            <div style={{ fontSize: 10, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono' }}>
              적용 중: <strong style={{ color: '#FBBF24' }}>{activeMock.desc}</strong> ({activeMock.coords[1].toFixed(4)}°N, {activeMock.coords[0].toFixed(4)}°E · 오차 ±{activeMock.accuracy}m)
            </div>
          )}
        </div>
      )}

      {/* 드롭다운 자동완성 리스트 */}
      {showDropdown && (
        <div style={{
          position: 'absolute', top: '100%', left: isRouteVariant ? 18 : 20, right: isRouteVariant ? 18 : 20,
          zIndex: isRouteVariant ? 150 : 200,
          background: 'var(--color-surface)', border: '1px solid color-mix(in srgb, var(--color-primary) 35%, transparent)',
          borderRadius: 12, boxShadow: '0 8px 30px rgba(0,0,0,0.6)', maxHeight: 320, overflowY: 'auto',
        }}>
          {allowCurrentLocation && (
            <div
              onClick={handleUseCurrentLocation}
              style={{
                padding: '9px 14px',
                borderBottom: '1px solid var(--color-border)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: 'rgba(14, 165, 233, 0.08)',
                color: '#38BDF8',
                fontSize: 12,
                fontWeight: 700,
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(14, 165, 233, 0.18)' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(14, 165, 233, 0.08)' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span>{isLocating ? '⏳' : '📍'}</span>
                <span>{isLocating ? 'GPS 위치 수신 중...' : '현재 내 위치 사용 (GPS)'}</span>
              </div>
              <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: 'rgba(56, 189, 248, 0.18)' }}>
                GPS
              </span>
            </div>
          )}
          {allowMapPick && onPickOnMap && (
            <div
              onClick={() => {
                setOpen(false)
                onPickOnMap()
              }}
              style={{
                padding: '9px 14px',
                borderBottom: '1px solid var(--color-border)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                background: 'rgba(52, 211, 153, 0.08)',
                color: '#34D399',
                fontSize: 12,
                fontWeight: 700,
              }}
              onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(52, 211, 153, 0.18)' }}
              onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(52, 211, 153, 0.08)' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <span>🎯</span>
                <span>지도에서 위치 직접 찍기</span>
              </div>
              <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: 'rgba(52, 211, 153, 0.18)' }}>
                지도 선택
              </span>
            </div>
          )}
          {items.length > 0 && (
            <div style={{ padding: '6px 12px', fontSize: 10, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono', borderBottom: '1px solid var(--color-border)', display: 'flex', justifyContent: 'space-between' }}>
              <span>검색 결과 {items.length}건 (지하철·버스·따릉이)</span>
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

          {loading && <div style={{ padding: 12, fontSize: 12, color: 'var(--color-muted)' }}>통합 검색 중...</div>}
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
