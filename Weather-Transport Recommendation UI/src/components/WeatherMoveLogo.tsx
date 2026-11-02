import React from 'react'

interface WeatherMoveLogoProps {
  size?: 'sm' | 'md' | 'lg'
  showText?: boolean
  onClick?: () => void
  style?: React.CSSProperties
}

export default function WeatherMoveLogo({
  size = 'md',
  showText = true,
  onClick,
  style,
}: WeatherMoveLogoProps) {
  const iconSize = size === 'sm' ? 28 : size === 'lg' ? 40 : 34
  const fontSize = size === 'sm' ? 14 : size === 'lg' ? 18 : 16
  const subSize = size === 'sm' ? 8 : 9

  return (
    <div
      onClick={onClick}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: size === 'sm' ? 8 : 10,
        cursor: onClick ? 'pointer' : 'default',
        userSelect: 'none',
        ...style,
      }}
      title="WeatherMove | 기상 맞춤형 대중교통 인텔리전스"
    >
      {/* ── 브랜드 심볼 (SVG 벡터) ── */}
      <svg
        width={iconSize}
        height={iconSize}
        viewBox="0 0 64 64"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ flexShrink: 0, transition: 'transform 0.2s ease' }}
        onMouseEnter={e => (e.currentTarget.style.transform = 'scale(1.06)')}
        onMouseLeave={e => (e.currentTarget.style.transform = 'scale(1.0)')}
      >
        <defs>
          {/* 배경 다크 스퀴클 */}
          <linearGradient id="wm-logo-bg" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#0F172A" />
            <stop offset="100%" stopColor="#020617" />
          </linearGradient>

          {/* 모빌리티 쾌속 궤적선 (스카이블루 -> 네온 에메랄드) */}
          <linearGradient id="wm-logo-rail" x1="0%" y1="100%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#38BDF8" />
            <stop offset="60%" stopColor="#0EA5E9" />
            <stop offset="100%" stopColor="#10B981" />
          </linearGradient>

          {/* 기상 햇살 그라데이션 */}
          <linearGradient id="wm-logo-sun" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#FDE047" />
            <stop offset="100%" stopColor="#F59E0B" />
          </linearGradient>

          {/* 네온 글로우 필터 */}
          <filter id="wm-logo-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow dx="0" dy="2" stdDeviation="2.5" floodColor="#0284C7" floodOpacity="0.45" />
          </filter>
        </defs>

        {/* 배경 스퀴클 */}
        <rect x="2" y="2" width="60" height="60" rx="16" fill="url(#wm-logo-bg)" stroke="#1E293B" strokeWidth="1.5" />

        {/* 기상 햇살 (우측 상단) */}
        <circle cx="43" cy="20" r="6.5" fill="url(#wm-logo-sun)" />

        {/* 은은한 기상 구름 아크 (점선) */}
        <path
          d="M17 35c-3.8 0-7-3.1-7-7 0-3.4 2.5-6.3 5.8-6.9C17 14.5 21.8 10 27.5 10c5.7 0 10.4 4.3 11 9.8.7-.1 1.3-.2 2-.2"
          stroke="#64748B"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeDasharray="2 3"
          opacity="0.65"
        />

        {/* 모빌리티 쾌속 궤적선 */}
        <path
          d="M13 43 C 14 34, 21 29, 29 33 C 36 37, 42 32, 47 23"
          stroke="url(#wm-logo-rail)"
          strokeWidth="4.5"
          strokeLinecap="round"
          filter="url(#wm-logo-glow)"
        />

        {/* 쾌속 화살촉 */}
        <path
          d="M40 22.5 L47.5 23 L46.5 30.5"
          stroke="url(#wm-logo-rail)"
          strokeWidth="4.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* 궤적 상의 거점 핀 (출발 -> 환승 -> 도착) */}
        <circle cx="14" cy="42" r="3" fill="#38BDF8" stroke="#0F172A" strokeWidth="1.5" />
        <circle cx="29" cy="33" r="3.5" fill="#34D399" stroke="#0F172A" strokeWidth="1.5" />
        <circle cx="47.5" cy="23" r="2.5" fill="#FFFFFF" />
      </svg>

      {/* ── 타이포그래피 (Weather + Move) ── */}
      {showText && (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span
              style={{
                fontSize,
                fontWeight: 900,
                letterSpacing: '-0.4px',
                lineHeight: 1.15,
                color: 'var(--app-text)',
                fontFamily: "'Outfit', sans-serif",
              }}
            >
              Weather
              <span
                style={{
                  background: 'linear-gradient(135deg, #38BDF8 0%, #34D399 100%)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                }}
              >
                Move
              </span>
            </span>
            <span
              style={{
                fontSize: 8,
                fontWeight: 800,
                fontFamily: "'JetBrains Mono', monospace",
                color: '#38BDF8',
                background: 'rgba(56, 189, 248, 0.12)',
                border: '1px solid rgba(56, 189, 248, 0.35)',
                padding: '1px 5px',
                borderRadius: 4,
                letterSpacing: '0.04em',
                lineHeight: 1.2,
              }}
            >
              AI
            </span>
          </div>
          <span
            style={{
              fontSize: subSize,
              color: 'var(--color-muted)',
              fontFamily: "'JetBrains Mono', monospace",
              letterSpacing: '0.08em',
              marginTop: 1,
              lineHeight: 1,
            }}
          >
            TRANSIT INTELLIGENCE
          </span>
        </div>
      )}
    </div>
  )
}
