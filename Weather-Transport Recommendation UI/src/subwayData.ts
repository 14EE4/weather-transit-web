// 서울 주요 지하철역 마스터 데이터 (위경도 GPS 좌표 및 호선 정보)
export interface SubwayStation {
  id: string
  name: string
  lines: string[]
  coords: [number, number] // [lng, lat]
  zone: string // 권역 (강남권, 도심권, 여의도권, 서남권, 동북권 등)
  baseCrowd: number // 기본 혼잡도
}

export const SUBWAY_STATIONS: SubwayStation[] = [
  // ── 2호선 및 강남권 ──
  { id: 'sub-gangnam', name: '강남역', lines: ['2호선', '신분당선'], coords: [127.0276, 37.4979], zone: '강남구', baseCrowd: 88 },
  { id: 'sub-yeoksam', name: '역삼역', lines: ['2호선'], coords: [127.0365, 37.5006], zone: '강남구', baseCrowd: 78 },
  { id: 'sub-seolleung', name: '선릉역', lines: ['2호선', '수인분당선'], coords: [127.0488, 37.5043], zone: '강남구', baseCrowd: 82 },
  { id: 'sub-samseong', name: '삼성역', lines: ['2호선'], coords: [127.0631, 37.5088], zone: '강남구', baseCrowd: 76 },
  { id: 'sub-sports', name: '종합운동장역', lines: ['2호선', '9호선'], coords: [127.0737, 37.5109], zone: '송파구', baseCrowd: 65 },
  { id: 'sub-jamsilsaenae', name: '잠실새내역', lines: ['2호선'], coords: [127.0863, 37.5116], zone: '송파구', baseCrowd: 70 },
  { id: 'sub-jamsil', name: '잠실역', lines: ['2호선', '8호선'], coords: [127.1002, 37.5133], zone: '송파구', baseCrowd: 89 },
  { id: 'sub-gyodae', name: '교대역', lines: ['2호선', '3호선'], coords: [127.0141, 37.4934], zone: '서초구', baseCrowd: 84 },
  { id: 'sub-seocho', name: '서초역', lines: ['2호선'], coords: [127.0078, 37.4918], zone: '서초구', baseCrowd: 68 },
  { id: 'sub-sadang', name: '사당역', lines: ['2호선', '4호선'], coords: [126.9816, 37.4765], zone: '동작/관악', baseCrowd: 91 },
  { id: 'sub-sinnonhyeon', name: '신논현역', lines: ['9호선', '신분당선'], coords: [127.0255, 37.5046], zone: '강남/서초', baseCrowd: 82 },
  { id: 'sub-sinsa', name: '신사역', lines: ['3호선', '신분당선'], coords: [127.0205, 37.5163], zone: '강남구', baseCrowd: 80 },
  { id: 'sub-yangjae', name: '양재역', lines: ['3호선', '신분당선'], coords: [127.0348, 37.4842], zone: '서초구', baseCrowd: 79 },
  { id: 'sub-apgujeong', name: '압구정역', lines: ['3호선'], coords: [127.0284, 37.5268], zone: '강남구', baseCrowd: 74 },
  { id: 'sub-cheongdam', name: '청담역', lines: ['7호선'], coords: [127.0532, 37.5193], zone: '강남구', baseCrowd: 71 },
  { id: 'sub-gangnam-gucheong', name: '강남구청역', lines: ['7호선', '수인분당선'], coords: [127.0416, 37.5172], zone: '강남구', baseCrowd: 75 },
  { id: 'sub-express-bus', name: '고속터미널역', lines: ['3호선', '7호선', '9호선'], coords: [127.0051, 37.5049], zone: '서초구', baseCrowd: 93 },

  // ── 도심 및 종로/중구 ──
  { id: 'sub-seoul', name: '서울역', lines: ['1호선', '4호선', '공항철도', '경의중앙선'], coords: [126.9706, 37.5547], zone: '중구/용산구', baseCrowd: 92 },
  { id: 'sub-cityhall', name: '시청역', lines: ['1호선', '2호선'], coords: [126.9770, 37.5654], zone: '중구', baseCrowd: 81 },
  { id: 'sub-euljiro-entrance', name: '을지로입구역', lines: ['2호선'], coords: [126.9826, 37.5660], zone: '중구', baseCrowd: 79 },
  { id: 'sub-euljiro3', name: '을지로3가역', lines: ['2호선', '3호선'], coords: [126.9926, 37.5663], zone: '중구', baseCrowd: 83 },
  { id: 'sub-jonggak', name: '종각역', lines: ['1호선'], coords: [126.9831, 37.5702], zone: '종로구', baseCrowd: 80 },
  { id: 'sub-jongno3', name: '종로3가역', lines: ['1호선', '3호선', '5호선'], coords: [126.9918, 37.5716], zone: '종로구', baseCrowd: 87 },
  { id: 'sub-gwanghwamun', name: '광화문역', lines: ['5호선'], coords: [126.9768, 37.5716], zone: '종로구', baseCrowd: 85 },
  { id: 'sub-myeongdong', name: '명동역', lines: ['4호선'], coords: [126.9863, 37.5609], zone: '중구', baseCrowd: 86 },
  { id: 'sub-dongdaemun', name: '동대문역사문화공원역', lines: ['2호선', '4호선', '5호선'], coords: [127.0090, 37.5657], zone: '중구', baseCrowd: 85 },

  // ── 여의도 및 영등포 ──
  { id: 'sub-yeouido', name: '여의도역', lines: ['5호선', '9호선'], coords: [126.9242, 37.5219], zone: '영등포구', baseCrowd: 88 },
  { id: 'sub-yeouinaru', name: '여의나루역', lines: ['5호선'], coords: [126.9328, 37.5271], zone: '영등포구', baseCrowd: 72 },
  { id: 'sub-national-assembly', name: '국회의사당역', lines: ['9호선'], coords: [126.9179, 37.5281], zone: '영등포구', baseCrowd: 74 },
  { id: 'sub-dangsan', name: '당산역', lines: ['2호선', '9호선'], coords: [126.9026, 37.5348], zone: '영등포구', baseCrowd: 83 },
  { id: 'sub-yeongdeungpo-gucheong', name: '영등포구청역', lines: ['2호선', '5호선'], coords: [126.8964, 37.5257], zone: '영등포구', baseCrowd: 78 },
  { id: 'sub-sindorim', name: '신도림역', lines: ['1호선', '2호선'], coords: [126.8913, 37.5087], zone: '구로구', baseCrowd: 94 },
  { id: 'sub-noryangjin', name: '노량진역', lines: ['1호선', '9호선'], coords: [126.9427, 37.5142], zone: '동작구', baseCrowd: 86 },

  // ── 마포 및 서북권 ──
  { id: 'sub-hongdae', name: '홍대입구역', lines: ['2호선', '공항철도', '경의중앙선'], coords: [126.9240, 37.5575], zone: '마포구', baseCrowd: 90 },
  { id: 'sub-hapjeong', name: '합정역', lines: ['2호선', '6호선'], coords: [126.9144, 37.5495], zone: '마포구', baseCrowd: 82 },
  { id: 'sub-sinchon', name: '신촌역', lines: ['2호선'], coords: [126.9368, 37.5552], zone: '마포/서대문', baseCrowd: 81 },
  { id: 'sub-gongdeok', name: '공덕역', lines: ['5호선', '6호선', '공항철도', '경의중앙선'], coords: [126.9519, 37.5444], zone: '마포구', baseCrowd: 87 },

  // ── 성동 / 광진 / 동북권 ──
  { id: 'sub-wangsimni', name: '왕십리역', lines: ['2호선', '5호선', '수인분당선', '경의중앙선'], coords: [127.0374, 37.5615], zone: '성동구', baseCrowd: 88 },
  { id: 'sub-seongsu', name: '성수역', lines: ['2호선'], coords: [127.0559, 37.5446], zone: '성동구', baseCrowd: 83 },
  { id: 'sub-konkuk', name: '건대입구역', lines: ['2호선', '7호선'], coords: [127.0699, 37.5404], zone: '광진구', baseCrowd: 89 },
  { id: 'sub-nowon', name: '노원역', lines: ['4호선', '7호선'], coords: [127.0614, 37.6548], zone: '노원구', baseCrowd: 85 },
  { id: 'sub-cheongnyangni', name: '청량리역', lines: ['1호선', '수인분당선', '경의중앙선', '경춘선'], coords: [127.0450, 37.5802], zone: '동대문구', baseCrowd: 84 },
]

// ── 검색 함수: 검색어(초성/부분 일치)에 맞는 지하철역 리스트 반환 ──
export function searchSubwayStations(query: string): SubwayStation[] {
  if (!query || !query.trim()) return []
  const cleanQuery = query.trim().replace(/역$/, '').toLowerCase()

  return SUBWAY_STATIONS.filter(s => {
    const rawName = s.name.toLowerCase()
    const nameWithoutSuffix = s.name.replace(/역$/, '').toLowerCase()
    return rawName.includes(cleanQuery) || 
           nameWithoutSuffix.includes(cleanQuery) ||
           s.zone.toLowerCase().includes(cleanQuery) ||
           s.lines.some(l => l.includes(cleanQuery))
  })
}
