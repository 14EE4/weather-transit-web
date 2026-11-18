export interface CrowdLevelInfo {
  label: string
  color: string
  bg: string
}

export interface MarkerCrowdInfo {
  crowd: number
  label: string
  color: string
}

/** 역/정류장별 시간대 첨두곡선 및 기상 강수 민감도 반영 혼잡도 계산 */
export function calculateStopCrowd(
  baseCrowd: number,
  rainSensitivity: number,
  stopName: string,
  stopType: 'subway' | 'bus' | 'bike' | 'gps',
  selectedTime: string,
  rainMm: number
): number {
  const base = baseCrowd || 55
  const hour = parseInt(selectedTime.replace(/[^0-9]/g, ''), 10) || 8

  let timeMultiplier = 1.0
  if (hour >= 8 && hour <= 9) {
    timeMultiplier = 1.25
  } else if (hour === 7) {
    timeMultiplier = 1.15
  } else if (hour >= 18 && hour <= 19) {
    timeMultiplier = 1.22
  } else if (hour === 17) {
    timeMultiplier = 1.15
  } else if (hour === 20) {
    timeMultiplier = 1.12
  } else if (hour >= 12 && hour <= 13) {
    timeMultiplier = 1.02
  } else if (hour >= 10 && hour <= 16) {
    timeMultiplier = 0.78
  } else if (hour >= 21 && hour <= 22) {
    timeMultiplier = 0.70
  } else {
    timeMultiplier = 0.42
  }

  const hash = stopName.split('').reduce((acc, char) => ((acc << 5) - acc) + char.charCodeAt(0), 0)
  const hashOffset = (Math.abs(hash) % 7) - 3

  if (stopType === 'bike') {
    const bikeRainPenalty = Math.round(rainSensitivity * rainMm * 7.5)
    const crowd = Math.round(base * (hour >= 23 || hour <= 5 ? 0.35 : 1.0)) + bikeRainPenalty
    return Math.max(5, Math.min(95, crowd))
  }

  const rainBonus = Math.min(15, Math.round(rainSensitivity * rainMm * 2.2))
  const crowd = Math.round(base * timeMultiplier) + hashOffset + rainBonus
  return Math.max(10, Math.min(99, crowd))
}

/** 혼잡도 퍼센트에 따른 색상 및 라벨 반환 */
export function getCrowdLevel(crowd: number): CrowdLevelInfo {
  if (crowd < 45) return { label: '여유', color: '#10B981', bg: 'rgba(16, 185, 129, 0.15)' }
  if (crowd < 75) return { label: '보통', color: '#38BDF8', bg: 'rgba(56, 189, 248, 0.15)' }
  return { label: '혼잡', color: '#F43F5E', bg: 'rgba(244, 63, 94, 0.15)' }
}

/** 알약·점 마커 DOM 전체(배지, 테두리, 화살표, 원형 점, 툴팁)에 혼잡도 색상·수치 일괄 반영 */
export function applyMarkerCrowdStyle(
  el: HTMLElement,
  crowdInfo: MarkerCrowdInfo,
  isSelected = false
): void {
  const pillBadge = el.querySelector('.marker-crowd-badge') as HTMLElement | null
  const pillBox = el.querySelector('.marker-pill') as HTMLElement | null
  const pillArrow = el.querySelector('.marker-pill-arrow') as HTMLElement | null
  const dotCircle = el.querySelector('.marker-dot-circle') as HTMLElement | null
  const dotTooltip = el.querySelector('.marker-dot-tooltip') as HTMLElement | null
  const dotTooltipBadge = el.querySelector('.marker-dot-tooltip-badge') as HTMLElement | null

  if (pillBadge) {
    pillBadge.textContent = `${crowdInfo.crowd}%`
    pillBadge.style.background = crowdInfo.color
  }
  if (pillBox) {
    pillBox.style.borderColor = crowdInfo.color
    pillBox.style.boxShadow = isSelected ? `0 0 20px ${crowdInfo.color}` : '0 4px 14px var(--app-shadow)'
  }
  if (pillArrow) {
    pillArrow.style.borderTopColor = crowdInfo.color
  }
  if (dotCircle) {
    dotCircle.style.background = crowdInfo.color
    dotCircle.style.boxShadow = `0 2px 8px var(--app-shadow), 0 0 10px ${crowdInfo.color}bb`
  }
  if (dotTooltip) {
    dotTooltip.style.borderColor = crowdInfo.color
  }
  if (dotTooltipBadge) {
    dotTooltipBadge.textContent = `${crowdInfo.crowd}% (${crowdInfo.label})`
    dotTooltipBadge.style.color = crowdInfo.color
  }
}
