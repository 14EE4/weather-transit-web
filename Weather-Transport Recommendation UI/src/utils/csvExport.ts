/** CSV 수식 인젝션(Formula Injection) 방어 및 RFC 4180 이스케이프 */
function sanitizeCsvCell(value: string | number): string {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? String(value) : ''
  }
  const raw = String(value ?? '')
  const isFormulaPrefix =
    /^[=@\t\r]/.test(raw) ||
    (/^[+-]/.test(raw) && !/^[+-]\d+(\.\d+)?%?$/.test(raw.trim()))
  const safe = isFormulaPrefix ? `'${raw}` : raw
  if (/[",\n\r]/.test(safe)) {
    return `"${safe.replace(/"/g, '""')}"`
  }
  return safe
}

/** 범용 CSV 다운로드 유틸리티 (UTF-8 BOM + 수식 인젝션 방어 + RFC 4180 이스케이프) */
export function downloadCsv(
  headers: string[],
  rows: Array<Array<string | number>>,
  filename: string
): void {
  const csvLines = [
    headers.map(sanitizeCsvCell).join(','),
    ...rows.map(row => row.map(sanitizeCsvCell).join(',')),
  ].join('\n')
  const blob = new Blob(['\uFEFF' + csvLines], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.setAttribute('href', url)
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
