import React from 'react'

/**
 * 은은한 그라디언트 펄스 애니메이션이 적용된 공통 스켈레톤 컴포넌트
 */
export function SkeletonBlock({
  width = '100%',
  height = 16,
  borderRadius = 8,
  style = {}
}: {
  width?: string | number
  height?: string | number
  borderRadius?: number | string
  style?: React.CSSProperties
}) {
  return (
    <div
      className="animate-pulse"
      style={{
        width,
        height,
        borderRadius,
        background: 'linear-gradient(90deg, rgba(255,255,255,0.03) 0%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.03) 100%)',
        backgroundSize: '200% 100%',
        ...style
      }}
    />
  )
}

/**
 * 3대 대중교통 추천 카드 전용 로딩 스켈레톤
 */
export function TransportScoreSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {[0, 1, 2].map((idx) => (
        <div
          key={idx}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            padding: '12px 14px',
            borderRadius: 14,
            background: 'rgba(255,255,255,0.02)',
            border: '1px solid rgba(255,255,255,0.05)',
          }}
        >
          {/* 아이콘 자리 */}
          <SkeletonBlock width={32} height={32} borderRadius={16} />

          {/* 중앙 텍스트 및 프로그레스 바 자리 */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <SkeletonBlock width={60} height={14} borderRadius={4} />
              <SkeletonBlock width={50} height={12} borderRadius={999} />
            </div>
            <SkeletonBlock width="100%" height={6} borderRadius={3} />
          </div>

          {/* 우측 점수 자리 */}
          <SkeletonBlock width={36} height={24} borderRadius={6} />
        </div>
      ))}
    </div>
  )
}

/**
 * 주요 권역별 혼잡도 테이블용 스켈레톤
 */
export function DistrictCongestionSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {Array.from({ length: 6 }).map((_, idx) => (
        <div
          key={idx}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '10px 12px',
            borderRadius: 10,
            background: 'rgba(255,255,255,0.015)',
            border: '1px solid rgba(255,255,255,0.04)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <SkeletonBlock width={20} height={20} borderRadius={10} />
            <SkeletonBlock width={80} height={14} borderRadius={4} />
          </div>
          <div style={{ display: 'flex', gap: 16 }}>
            <SkeletonBlock width={45} height={12} borderRadius={4} />
            <SkeletonBlock width={45} height={12} borderRadius={4} />
            <SkeletonBlock width={45} height={12} borderRadius={4} />
          </div>
        </div>
      ))}
    </div>
  )
}
