/** 범용 CSV 다운로드 유틸리티 (UTF-8 BOM 포함) */
export function downloadCsv(
  headers: string[],
  rows: Array<Array<string | number>>,
  filename: string
): void {
  const csvContent =
    'data:text/csv;charset=utf-8,\uFEFF' +
    [headers.join(','), ...rows.map(row => row.join(','))].join('\n')
  const encodedUri = encodeURI(csvContent)
  const link = document.createElement('a')
  link.setAttribute('href', encodedUri)
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}
