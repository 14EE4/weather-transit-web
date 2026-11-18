import { useState } from 'react'
import { CORRELATION_DATA, type HourlyTransitData } from '../constants/fallbackData'

export function CrowdBar({ value, color }: { value: number; color: string }) {
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full overflow-hidden" style={{ background: 'var(--color-subtle)' }}>
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${value}%`, background: color }} />
      </div>
      <span style={{ fontSize: 11, fontFamily: 'JetBrains Mono', color, minWidth: 28 }}>{value}%</span>
    </div>
  )
}

export function StatCard({
  label,
  value,
  unit,
  color,
  icon,
}: {
  label: string
  value: string | number
  unit?: string
  color: string
  icon: string
}) {
  return (
    <div className="rounded-2xl p-4" style={{ background: 'var(--color-card)', border: '1px solid var(--color-border)' }}>
      <div className="flex items-center gap-2 mb-2">
        <span style={{ fontSize: 16 }}>{icon}</span>
        <span style={{ fontSize: 11, color: 'var(--color-muted)', fontFamily: 'JetBrains Mono', letterSpacing: '0.04em' }}>{label}</span>
      </div>
      <div className="flex items-baseline gap-1">
        <span style={{ fontSize: 26, fontWeight: 800, color, fontFamily: 'JetBrains Mono', lineHeight: 1 }}>{value}</span>
        {unit && <span style={{ fontSize: 12, color: 'var(--app-text)' }}>{unit}</span>}
      </div>
    </div>
  )
}

export function BarChart({ data }: { data: HourlyTransitData[] }) {
  const maxSubway = Math.max(...data.map(d => d.subway))
  const [hovered, setHovered] = useState<number | null>(null)

  return (
    <div className="relative">
      <div className="flex items-end gap-1.5 h-32">
        {data.map((d, i) => (
          <div
            key={d.hour}
            className="flex-1 flex flex-col items-center gap-0.5 cursor-pointer group"
            onMouseEnter={() => setHovered(i)}
            onMouseLeave={() => setHovered(null)}
          >
            <div className="w-full flex flex-col gap-0.5 items-center">
              <div
                className="w-full rounded-sm transition-all"
                style={{
                  height: `${(d.subway / maxSubway) * 80}px`,
                  background: hovered === i ? 'var(--color-primary)' : 'color-mix(in srgb, var(--color-primary) 50%, transparent)',
                  minHeight: 2,
                }}
              />
            </div>
          </div>
        ))}
      </div>
      <div className="flex gap-1.5 mt-1">
        {data.map(d => (
          <div key={d.hour} className="flex-1 text-center" style={{ fontSize: 9, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>
            {d.hour.replace('시', '')}
          </div>
        ))}
      </div>
      {hovered !== null && (
        <div
          className="absolute bottom-full mb-2 rounded-xl px-3 py-2 pointer-events-none z-10"
          style={{
            left: `${(hovered / data.length) * 100}%`,
            transform: 'translateX(-50%)',
            background: 'var(--color-card2)',
            border: '1px solid color-mix(in srgb, var(--color-primary) 30%, transparent)',
            whiteSpace: 'nowrap',
          }}
        >
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-primary)', marginBottom: 2 }}>{data[hovered].hour}</div>
          <div style={{ fontSize: 10, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>
            🚇 {data[hovered].subway.toLocaleString()}명
          </div>
          <div style={{ fontSize: 10, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>
            🚌 {data[hovered].bus.toLocaleString()}명
          </div>
          <div style={{ fontSize: 10, color: 'var(--app-text)', fontFamily: 'JetBrains Mono' }}>
            🚲 {data[hovered].bike.toLocaleString()}명
          </div>
          <div style={{ fontSize: 10, color: '#FB923C', fontFamily: 'JetBrains Mono', marginTop: 2 }}>
            💧 강수 {data[hovered].rain}mm
          </div>
        </div>
      )}
    </div>
  )
}

export function CorrelationChart() {
  const [hoveredIdx, setHoveredIdx] = useState<number | null>(null)
  const activeItem = hoveredIdx !== null ? CORRELATION_DATA[hoveredIdx] : null

  return (
    <div className="relative">
      <div
        style={{
          minHeight: 22,
          marginBottom: 8,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: 11,
          fontFamily: 'JetBrains Mono',
        }}
      >
        {activeItem ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', justifyContent: 'space-between' }}>
            <span style={{ color: 'var(--color-primary)', fontWeight: 700 }}>
              🌧 강수 {activeItem.rain}mm:
            </span>
            <div style={{ display: 'flex', gap: 8, fontSize: 10 }}>
              <span style={{ color: 'var(--color-primary)' }}>🚇 {activeItem.subway}%</span>
              <span style={{ color: '#FB923C' }}>🚌 {activeItem.bus}%</span>
              <span style={{ color: '#34D399', fontWeight: 700 }}>🚲 {activeItem.bike}%</span>
            </div>
            <span style={{ fontSize: 9, color: 'var(--app-text)' }}>
              ({activeItem.note})
            </span>
          </div>
        ) : (
          <span style={{ fontSize: 10, color: 'var(--app-text)' }}>
            💡 그래프 위로 마우스를 올리면 강수량별 실측 이용률을 확인할 수 있습니다
          </span>
        )}
      </div>

      <div className="relative h-28">
        <svg width="100%" height="100%" viewBox="0 0 300 112" preserveAspectRatio="none">
          {[0, 28, 56, 84, 112].map(y => (
            <line key={y} x1="0" y1={y} x2="300" y2={y} stroke="var(--app-text)" strokeWidth="1" />
          ))}

          {hoveredIdx !== null && (
            <line
              x1={(hoveredIdx / (CORRELATION_DATA.length - 1)) * 300}
              y1={0}
              x2={(hoveredIdx / (CORRELATION_DATA.length - 1)) * 300}
              y2={112}
              stroke="var(--app-text)"
              strokeWidth="1.5"
              strokeDasharray="3 2"
            />
          )}

          <polyline
            points={CORRELATION_DATA.map((d, i) => `${(i / (CORRELATION_DATA.length - 1)) * 300},${112 - (d.subway / 100) * 100}`).join(' ')}
            fill="none" stroke="var(--color-primary)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
          />
          <polyline
            points={CORRELATION_DATA.map((d, i) => `${(i / (CORRELATION_DATA.length - 1)) * 300},${112 - (d.bus / 100) * 100}`).join(' ')}
            fill="none" stroke="#FB923C" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
          />
          <polyline
            points={CORRELATION_DATA.map((d, i) => `${(i / (CORRELATION_DATA.length - 1)) * 300},${112 - (d.bike / 100) * 100}`).join(' ')}
            fill="none" stroke="#34D399" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
          />

          {CORRELATION_DATA.map((d, i) => {
            const x = (i / (CORRELATION_DATA.length - 1)) * 300
            const ySub = 112 - (d.subway / 100) * 100
            const yBus = 112 - (d.bus / 100) * 100
            const yBike = 112 - (d.bike / 100) * 100
            const isHover = hoveredIdx === i

            return (
              <g key={i}>
                <circle cx={x} cy={ySub} r={isHover ? 4.5 : 2.5} fill="var(--color-primary)" />
                <circle cx={x} cy={yBus} r={isHover ? 4.5 : 2.5} fill="#FB923C" />
                <circle cx={x} cy={yBike} r={isHover ? 5 : 3} fill="#34D399" />
              </g>
            )
          })}

          {CORRELATION_DATA.map((_, i) => {
            const x = (i / (CORRELATION_DATA.length - 1)) * 300
            const step = 300 / (CORRELATION_DATA.length - 1)
            return (
              <rect
                key={i}
                x={x - step / 2}
                y={0}
                width={step}
                height={112}
                fill="transparent"
                style={{ cursor: 'pointer' }}
                onMouseEnter={() => setHoveredIdx(i)}
                onMouseLeave={() => setHoveredIdx(null)}
              />
            )
          })}
        </svg>

        <div className="flex justify-between mt-1">
          {CORRELATION_DATA.map((d, i) => (
            <span
              key={d.rain}
              style={{
                fontSize: 9,
                color: hoveredIdx === i ? 'var(--color-primary)' : 'var(--app-text)',
                fontWeight: hoveredIdx === i ? 700 : 400,
                fontFamily: 'JetBrains Mono',
                transition: 'color 0.15s ease',
              }}
            >
              {d.rain}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}
